"""Unit tests for the internals of `infrable.files`.

These run in-process inside a scratch directory, using the project's real
`infra.py` for context.
"""

import subprocess as sp
from pathlib import Path

import pytest

from infrable import errors, files, paths


@pytest.fixture(autouse=True)
def scratch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_gen_skip_true(capsys):
    src = _write("t/skipped.j2", "# ---\n# src: s\n# skip: true\n# ---\n")

    files.gen(src)

    assert "╰ skip: true" in capsys.readouterr().out
    assert not list(paths.files.glob("**/*"))


def test_gen_multiple_destinations(capsys):
    src = _write(
        "t/multi.j2",
        "# ---\n# src: s\n# dest:\n#   - dev_host:/etc/a\n#   - root@dev.example.com:/etc/b\n# ---\nbody",
    )

    files.gen(src)

    out = capsys.readouterr().out
    assert "├─ " in out and "╰─ " in out
    assert (paths.files / "dev_host/etc/a.new").exists()
    assert (paths.files / "root@dev.example.com/etc/b.new").exists()


def test_gen_skips_unset_hosts(capsys):
    src = _write(
        "t/none.j2",
        "# ---\n# src: s\n# dest:\n#   - 'None:/etc/a'\n#   - ':/etc/b'\n# ---\nbody",
    )

    files.gen(src)

    out = capsys.readouterr().out
    assert out.count("skipping") == 2
    assert not list(paths.files.glob("**/*.new"))


def test_gen_only_filters_hosts(capsys):
    src = _write(
        "t/two.j2",
        "# ---\n# src: s\n# dest:\n#   - dev.example.com:/etc/a\n#   - prod.example.com:/etc/b\n# ---\nbody",
    )

    files.gen(src, only=["127.0.0.1"])

    assert (paths.files / "dev.example.com/etc/a.new").exists()
    assert not (paths.files / "prod.example.com/etc/b.new").exists()


def test_gen_unknown_only_is_an_error():
    src = _write("t/x.j2", "# ---\n# src: s\n# dest: dev_host:/etc/a\n# ---\n")

    with pytest.raises(errors.HostOrServiceNotFoundError):
        files.gen(src, only=["nope"])


def test_gen_clears_previous_output():
    stale = _write(paths.files / "stale.new", "stale")
    src = _write("t/x.j2", "# ---\n# src: s\n# dest: dev_host:/etc/a\n# ---\nbody")

    files.gen(src)

    assert not stale.exists()


def test_backup_without_generated_files_is_noop(capsys):
    assert files.backup() is None
    assert capsys.readouterr().out == ""
    assert not paths.backups.exists()


def test_backup_never_overwrites(capsys, monkeypatch):
    _write(paths.files / "h/etc/a.new", "n")
    sleeps = []
    monkeypatch.setattr(files.time, "sleep", lambda s: sleeps.append(s))

    # Make the clock return the same second twice, then move on.
    stamps = iter(["2000-01-01T00:00:00"] * 2 + ["2000-01-01T00:00:01"])

    class Clock:
        @staticmethod
        def now():
            return type("T", (), {"strftime": lambda self, fmt: next(stamps)})()

    monkeypatch.setattr(files, "datetime", Clock)

    files.backup()
    files.backup()

    assert sorted(p.name for p in paths.backups.glob("*")) == [
        "2000-01-01T00:00:00",
        "2000-01-01T00:00:01",
    ]
    assert sleeps == [1]


def test_pull_unknown_host(fake_ssh):
    new = _write(paths.files / "ghost@nowhere/etc/a.new", "x")

    with pytest.raises(errors.InvalidDestinationError, match="a.old"):
        files._pull(new)


def test_push_unknown_host(fake_ssh):
    new = _write(
        paths.files / "ghost@nowhere/etc/a.new",
        "# ---\n# src: s\n# dest: ghost@nowhere:/etc/a\n# ---\nx",
    )

    with pytest.raises(errors.InvalidDestinationError):
        files._push(new, "ghost@nowhere:/etc/a")
    assert fake_ssh.calls() == []


def test_push_dest_chmod_chown_override_template(fake_ssh):
    new = _write(
        paths.files / "dev_host/etc/a.new",
        "# ---\n# src: s\n# dest: dev_host:/etc/a\n# chmod: '600'\n# chown: a:b\n# ---\nx",
    )

    files._push(new, "dev_host:/etc/a")

    cmd = fake_ssh.script(fake_ssh.calls()[0])
    assert "sudo chmod -- 600" in cmd and "sudo chown -- a:b" in cmd


def test_push_destination_has_a_single_leading_slash(fake_ssh):
    new = _write(
        paths.files / "dev_host/etc/a.new",
        "# ---\n# src: s\n# dest: dev_host:/etc/a\n# execute: true\n# ---\nx",
    )

    files._push(new, "dev_host:/etc/a")

    cmd = fake_ssh.script(fake_ssh.calls()[0])
    assert "sudo mkdir -p -- /etc" in cmd
    assert cmd.endswith(" /etc/a && sudo chmod u+rx -- /etc/a && sudo -- /etc/a")
    assert "//" not in cmd


def test_push_destination_without_leading_slash_is_normalised(fake_ssh):
    new = _write(
        paths.files / "dev_host/etc/a.new",
        "# ---\n# src: s\n# dest: dev_host:etc/a\n# ---\nx",
    )

    files._push(new, "dev_host:etc/a")

    assert " /etc/a" in fake_ssh.commands()[0]


def test_sudo_exec_joins_list_commands(fake_ssh):
    files._sudo_exec("a@b", ["echo", "hello world"])

    assert fake_ssh.commands() == ["echo 'hello world'"]


def test_sudo_exec_with_shell_and_options(fake_ssh):
    files._sudo_exec("a@b", "echo hi; echo there", shell="bash", options=["-p", "22"])

    call = fake_ssh.calls()[0]["argv"]
    assert call[:4] == ["-o", "StrictHostKeyChecking=accept-new", "-p", "22"]
    assert call[-2] == "a@b"
    assert call[-1] == "bash -c 'echo hi; echo there'"


def test_sudo_pull_file_uses_ssh_key(fake_ssh):
    fake_ssh.put("/etc/a", "remote\n")

    files._sudo_pull_file("a@b", "/etc/a", "local.old", admin_ssh_key="/keys/id")

    argv = fake_ssh.calls()[0]["argv"]
    assert argv[argv.index("-i") + 1] == "/keys/id"
    assert Path("local.old").read_text() == "remote\n"


def test_sudo_pull_file_quotes_paths(fake_ssh):
    files._sudo_pull_file("a@b", "/etc/my file; rm -rf x", "local.old")

    cmd = fake_ssh.commands()[0]
    assert "'/etc/my file; rm -rf x'" in cmd


def test_sudo_pull_file_retries_then_fails(fake_ssh, monkeypatch):
    monkeypatch.setattr(files._sudo_pull_file.retry, "sleep", lambda _: None)
    monkeypatch.setenv("FAKE_SSH_FAIL", "1")

    with pytest.raises(sp.CalledProcessError):
        files._sudo_pull_file("a@b", "/etc/a", "local.old")

    assert len(fake_ssh.calls()) == 5


def test_sudo_push_file_retries_then_fails(fake_ssh, monkeypatch):
    monkeypatch.setattr(files._sudo_push_file.retry, "sleep", lambda _: None)
    monkeypatch.setenv("FAKE_SSH_FAIL", "1")
    src = _write("src", "content")

    with pytest.raises(sp.CalledProcessError):
        files._sudo_push_file("a@b", src, "/etc/a")

    assert len(fake_ssh.calls()) == 5


def test_sudo_push_file_command(fake_ssh):
    src = _write("src", "content")

    files._sudo_push_file(
        "a@b",
        src,
        "/etc/dir/a",
        chmod="600",
        chown="u:g",
        admin_ssh_key="/keys/id",
        execute=True,
    )

    call = fake_ssh.calls()[0]
    cmd = call["argv"][-1]
    assert call["stdin"] == "content"
    assert "-i" in call["argv"]
    # permissions are set on the temp file, before it's moved into place
    steps = fake_ssh.script(call).split(" && ")
    assert steps[0] == "tmp=$(sudo mktemp /tmp/infrable-push.XXXXXXXXXX)"
    assert steps[1].startswith("trap ")
    assert steps[2] == 'sudo tee -- "$tmp" >/dev/null'
    assert steps[3] == 'sudo chown -- u:g "$tmp"'
    assert steps[4] == 'sudo chmod -- 600 "$tmp"'
    assert steps[5] == "sudo mkdir -p -- /etc/dir"
    assert steps[6] == 'sudo mv -f -- "$tmp" /etc/dir/a'
    assert steps[7] == "sudo -- /etc/dir/a"
    # chmod was given, so no implicit chmod u+rx
    assert "u+rx" not in cmd


def test_sudo_push_file_execute_adds_exec_bit_without_chmod(fake_ssh):
    src = _write("src", "content")

    files._sudo_push_file("a@b", src, "/etc/a", execute=True)

    assert "sudo chmod u+rx -- /etc/a" in fake_ssh.commands()[0]


def test_sudo_push_file_does_not_execute_by_default(fake_ssh):
    src = _write("src", "content")

    files._sudo_push_file("a@b", src, "/etc/a")

    cmd = fake_ssh.script(fake_ssh.calls()[0])
    assert "u+rx" not in cmd
    assert not cmd.endswith("sudo -- /etc/a")


def test_iter_files_follows_symlinked_dirs():
    _write("real/a.txt", "a")
    Path("link").symlink_to("real")

    found = sorted(p.name for p in files._iter_files(Path("."), "**/*.txt"))

    assert found.count("a.txt") >= 1


def test_old_path():
    assert files._old_path(Path("a/b.new")) == Path("a/b.old")


def test_diff_empty_when_equal():
    a, b = _write("a.new", "x\ny\n"), _write("a.old", "x\ny\n")

    assert files._diff(a, b) == []


def test_diff_reports_changes():
    a, b = _write("a.new", "x\nz\n"), _write("a.old", "x\ny\n")

    diff = files._diff(a, b)

    assert "-y" in diff and "+z" in diff


def test_print_diff_prints_all_line_kinds(capsys):
    files._print_diff(["--- a", "+++ b", "@@ -1 +1 @@", "-old", "+new", " same"])

    out = capsys.readouterr().out
    for text in ["--- a", "+++ b", "@@ -1 +1 @@", "-old", "+new", " same"]:
        assert text in out


def test_gen_state_directory_is_private():
    src = _write("t/x.j2", "# ---\n# src: s\n# dest: dev_host:/etc/a\n# ---\nbody")

    files.gen(src)

    assert paths.var.stat().st_mode & 0o777 == 0o700


@pytest.mark.parametrize("dest", ["dev_host:/../../../escape", "../x:/etc/a"])
def test_gen_refuses_to_write_outside_the_files_dir(dest):
    src = _write("t/x.j2", f"# ---\n# src: s\n# dest: {dest}\n# ---\nbody")

    with pytest.raises(errors.InvalidDestinationError):
        files.gen(src)

    assert not Path("escape.new").exists()


def test_revert_without_backups_is_an_error():
    with pytest.raises(errors.NoBackupsError, match="backups"):
        files.revert()


def test_sudo_pull_file_missing_remote_file_is_empty(fake_ssh):
    files._sudo_pull_file("a@b", "/etc/nope", "local.old")

    assert Path("local.old").read_text() == ""


def test_sudo_pull_file_failure_is_reported_not_retried(fake_ssh, monkeypatch, capfd):
    # Anything but an ssh connection failure means the remote command failed
    monkeypatch.setenv("FAKE_SSH_FAIL", "sudo: permission denied")
    monkeypatch.setenv("FAKE_SSH_EXIT", "1")

    with pytest.raises(sp.CalledProcessError):
        files._sudo_pull_file("a@b", "/etc/a", "local.old")

    assert len(fake_ssh.calls()) == 1
    assert "sudo: permission denied" in capfd.readouterr().err


def test_sudo_push_file_does_not_rerun_failed_scripts(fake_ssh, monkeypatch):
    monkeypatch.setenv("FAKE_SSH_FAIL", "script failed")
    monkeypatch.setenv("FAKE_SSH_EXIT", "3")
    src = _write("src", "content")

    with pytest.raises(sp.CalledProcessError):
        files._sudo_push_file("a@b", src, "/etc/a", execute=True)

    assert len(fake_ssh.calls()) == 1


def test_sudo_push_file_defaults_to_world_readable(fake_ssh):
    # The temp file is private (0600), so the old default has to be explicit
    src = _write("src", "content")

    files._sudo_push_file("a@b", src, "/etc/a")

    assert 'sudo chmod -- 644 "$tmp"' in fake_ssh.script(fake_ssh.calls()[0])


def test_sudo_push_file_quotes_destination(fake_ssh):
    src = _write("src", "content")

    files._sudo_push_file("a@b", src, "/etc/my dir/a; rm -rf x", chown="a:b; id")

    script = fake_ssh.script(fake_ssh.calls()[0])
    assert "'/etc/my dir/a; rm -rf x'" in script
    assert "'a:b; id'" in script
