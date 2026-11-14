"""Tests for the file workflows that talk to remote hosts (pull/push/deploy...).

`ssh` is replaced by the `fake_ssh` fixture, so nothing leaves the machine.
"""

import shutil

from sh import infrable

from infrable import paths

HOSTNAME = "root@dev.example.com"


def _new_files():
    return sorted(paths.files.glob("**/*.new"))


def _old_for(new):
    return new.with_suffix(".old")


def _pushed(fake_ssh):
    return [c for c in fake_ssh.calls() if "sudo tee" in c["argv"][-1]]


def _fresh_files():
    shutil.rmtree(paths.files, ignore_errors=True)
    infrable.files.gen()


def _touch_olds(content=lambda new: ""):
    for new in _new_files():
        _old_for(new).write_text(content(new))


def _seed_remote(fake_ssh):
    """Make the remote hold a previous version of every generated file."""

    _fresh_files()
    for new in _new_files():
        loc = new.relative_to(paths.files / HOSTNAME).with_suffix("")
        fake_ssh.put(str(loc), new.read_text() + "# previous version\n")


def test_pull_fetches_remote_content(fake_ssh):
    _fresh_files()
    fake_ssh.put("/etc/nginx/proxy_params", "remote proxy params\n")

    out = infrable.files.pull(_tty_out=False)

    proxy = paths.files / HOSTNAME / "etc/nginx/proxy_params.old"
    assert proxy.read_text() == "remote proxy params\n"
    assert str(proxy.with_suffix(".new")) in out

    # Files that don't exist remotely are pulled as empty
    web = paths.files / HOSTNAME / "etc/nginx/sites-enabled/web.old"
    assert web.read_text() == ""

    # Every pull goes to the right host, using sudo, with the host key option
    calls = fake_ssh.calls()
    assert len(calls) == len(_new_files())
    for call in calls:
        assert call["argv"][-2] == "root@127.0.0.1"
        assert "StrictHostKeyChecking=no" in call["argv"]
        assert "sudo test -f" in call["argv"][-1]


def test_pull_replaces_stale_old_files(fake_ssh):
    _fresh_files()
    stale = paths.files / HOSTNAME / "stale.old"
    stale.write_text("stale")

    infrable.files.pull()

    assert not stale.exists()


def test_pull_without_generated_files_is_noop(fake_ssh):
    shutil.rmtree(paths.files, ignore_errors=True)
    assert infrable.files.pull(_tty_out=False) == ""
    assert fake_ssh.calls() == []


def test_push_yes_pushes_changed_files(fake_ssh):
    _fresh_files()
    infrable.files.pull()
    fake_ssh.log.write_text("")

    out = infrable.files.push(yes=True, _tty_out=False)

    pushed = _pushed(fake_ssh)
    assert len(pushed) == len(_new_files())
    assert "/etc/nginx/proxy_params" in out

    by_dest = {}
    for call in pushed:
        cmd = call["argv"][-1]
        dest = cmd.split("sudo mv -f -- ")[1].split()[1]
        assert not dest.startswith("//"), dest
        by_dest[dest] = call

    proxy = by_dest["/etc/nginx/proxy_params"]
    cmd = proxy["argv"][-1]
    assert "sudo chmod -- 644" in cmd
    assert "sudo chown -- root:root" in cmd
    assert "sudo mkdir -p -- /etc/nginx" in cmd
    assert "# dest: root@dev.example.com:/etc/nginx/proxy_params" in proxy["stdin"]
    assert "proxy_set_header Host $http_host;" in proxy["stdin"]

    # Executable templates are chmod-ed and executed
    robots = by_dest["/root/init/robots.txt.sh"]["argv"][-1]
    assert "sudo chmod u+rx -- /root/init/robots.txt.sh" in robots
    assert robots.endswith("&& sudo -- /root/init/robots.txt.sh")


def test_push_skips_unchanged_files(fake_ssh):
    _fresh_files()
    count = len(_new_files())
    _touch_olds(lambda new: new.read_text())

    out = infrable.files.push(yes=True, _tty_out=False)

    assert _pushed(fake_ssh) == []
    assert out.count("skipping ") == count
    # Skipped files are cleaned up
    assert _new_files() == []


def test_push_prompt_answers(fake_ssh):
    _fresh_files()
    news = _new_files()
    _touch_olds()
    assert len(news) >= 3

    # decline the first, accept the second, accept all remaining
    infrable.files.push(_in="n\ny\nall\n", _tty_out=False)

    assert len(_pushed(fake_ssh)) == len(news) - 1
    assert len(_new_files()) == len(news) - 1


def test_push_prompt_default_is_yes(fake_ssh):
    _fresh_files()
    news = _new_files()
    _touch_olds()

    infrable.files.push(_in="\n" * len(news), _tty_out=False)

    assert len(_pushed(fake_ssh)) == len(news)


def test_push_uses_ssh_key(fake_ssh):
    _fresh_files()
    news = _new_files()
    # Only the push command is under test here, so call the helper directly.
    from infrable import files

    files._sudo_push_file(
        "root@127.0.0.1", news[0], "/etc/x", admin_ssh_key="/path/to/key"
    )
    argv = fake_ssh.calls()[-1]["argv"]
    assert argv[argv.index("-i") + 1] == "/path/to/key"


def test_deploy_yes(fake_ssh):
    backups = len(list(paths.backups.glob("*")))

    out = infrable.files.deploy(yes=True, _tty_out=False)

    assert "backup:" in out
    assert len(list(paths.backups.glob("*"))) == backups + 1
    assert len(_pushed(fake_ssh)) == len(_new_files())


def test_deploy_with_path_skips_confirmation(fake_ssh):
    out = infrable.files.deploy("templates/nginx", yes=True, _tty_out=False)

    assert "templates/nginx" in out
    assert all("hostname" not in str(p) for p in paths.files.glob("**/*")), (
        "only nginx templates should be generated"
    )
    assert len(_pushed(fake_ssh)) == 3


def test_deploy_confirm_generate(fake_ssh):
    shutil.rmtree(paths.files, ignore_errors=True)

    # generate, then accept every push
    infrable.files.deploy(_in="y\nall\n", _tty_out=False)

    assert len(_pushed(fake_ssh)) == 4


def test_deploy_confirm_pull_only(fake_ssh):
    _fresh_files()
    backups = len(list(paths.backups.glob("*")))

    # don't generate, but do pull and back up, then accept every push
    out = infrable.files.deploy(_in="n\ny\nall\n", _tty_out=False)

    assert "backup:" in out
    assert len(list(paths.backups.glob("*"))) == backups + 1
    assert any("sudo test -f" in c for c in fake_ssh.commands())
    assert len(_pushed(fake_ssh)) == 4


def test_deploy_confirm_backup_only(fake_ssh):
    _fresh_files()
    _touch_olds()
    backups = len(list(paths.backups.glob("*")))

    # don't generate, don't pull, but do back up, then accept every push
    out = infrable.files.deploy(_in="n\nn\ny\nall\n", _tty_out=False)

    assert "backup:" in out
    assert len(list(paths.backups.glob("*"))) == backups + 1
    assert not any("sudo test -f" in c for c in fake_ssh.commands())
    assert len(_pushed(fake_ssh)) == 4


def test_deploy_confirm_nothing(fake_ssh):
    _fresh_files()
    _touch_olds(lambda new: new.read_text())
    backups = len(list(paths.backups.glob("*")))

    # decline everything: nothing is generated, pulled, backed up or pushed
    infrable.files.deploy(_in="n\nn\nn\n", _tty_out=False)

    assert len(list(paths.backups.glob("*"))) == backups
    assert fake_ssh.calls() == []


def test_recover_pushes_backup(fake_ssh):
    _seed_remote(fake_ssh)
    infrable.files.deploy(yes=True)
    fake_ssh.log.write_text("")

    out = infrable.files.recover(yes=True, _tty_out=False)

    assert "reverting from:" in out
    pushed = _pushed(fake_ssh)
    assert len(pushed) == 4
    # What got pushed is the previous version of each file
    assert all("# previous version" in c["stdin"] for c in pushed)


def test_recover_from_explicit_backup(fake_ssh):
    _seed_remote(fake_ssh)
    infrable.files.deploy(yes=True)
    backup = max(paths.backups.glob("*"))
    fake_ssh.log.write_text("")

    out = infrable.files.recover(str(backup), yes=True, _tty_out=False)

    assert f"reverting from: {backup}" in out
    assert len(_pushed(fake_ssh)) == 4


def test_recover_when_files_did_not_exist_remotely(fake_ssh):
    # The remote has nothing, so the backup holds only empty "old" files
    _fresh_files()
    infrable.files.deploy(yes=True)
    fake_ssh.log.write_text("")

    out = infrable.files.recover(yes=True, _tty_out=False)

    # There's nothing to restore, so nothing is pushed, and it doesn't crash
    assert "reverting from:" in out
    assert out.count("file is empty") == 4
    assert _pushed(fake_ssh) == []
    assert _new_files() == []


def test_recover_restores_only_files_that_existed_remotely(fake_ssh):
    _fresh_files()
    fake_ssh.put(
        "/etc/nginx/proxy_params",
        "# ---\n# src: s\n# dest: root@dev.example.com:/etc/nginx/proxy_params\n# ---\nold\n",
    )
    infrable.files.deploy(yes=True)
    fake_ssh.log.write_text("")

    out = infrable.files.recover(yes=True, _tty_out=False)

    pushed = _pushed(fake_ssh)
    assert len(pushed) == 1
    assert pushed[0]["stdin"].endswith("old\n")
    assert pushed[0]["argv"][-1].split("sudo mv -f -- ")[1].split()[1] == (
        "/etc/nginx/proxy_params"
    )
    assert out.count("file is empty") == 3


def test_push_skips_empty_files_without_prompting(fake_ssh):
    _fresh_files()
    news = _new_files()
    _touch_olds()
    news[0].write_text("  \n")

    # Only the non-empty files prompt
    out = infrable.files.push(_in="all\n", _tty_out=False)

    assert f"{news[0].name.removesuffix('.new')}: file is empty" in out
    assert len(_pushed(fake_ssh)) == len(news) - 1
    assert not news[0].exists()


def test_push_skips_empty_files_without_old_counterpart(fake_ssh):
    _fresh_files()
    for new in _new_files():
        new.write_text("")

    out = infrable.files.push(yes=True, _tty_out=False)

    assert out.count("file is empty") == 4
    assert _pushed(fake_ssh) == []
