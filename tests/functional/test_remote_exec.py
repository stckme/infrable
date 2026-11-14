"""Tests for `infrable remote ...`, with `ssh` replaced by the `fake_ssh` fixture."""

import shutil

from sh import infrable

from infrable import paths

SSH_OPTS = "-o StrictHostKeyChecking=no"


def _targets(fake_ssh):
    return sorted(c["argv"][0] for c in fake_ssh.calls())


def test_remote_single_host(fake_ssh):
    out = infrable.remote.dev_host("uptime", _tty_out=False)

    assert f"fake-ssh: root@127.0.0.1 {SSH_OPTS} uptime" in out
    assert _targets(fake_ssh) == ["root@127.0.0.1"]


def test_remote_infra_hosts(fake_ssh):
    out = infrable.remote("infra-hosts", "uptime", _tty_out=False)

    assert _targets(fake_ssh) == [
        "root@127.0.0.1",
        "root@127.0.0.2",
        "root@127.0.0.3",
    ]
    assert "╭ root@dev.example.com" in out
    assert "╭ root@beta.example.com" in out
    assert "╭ root@prod.example.com" in out
    assert "fake-ssh: root@127.0.0.2" in out


def test_remote_infra_hosts_only(fake_ssh):
    out = infrable.remote(
        "infra-hosts",
        "uptime",
        "--only",
        "beta_host",
        "--only",
        "prod.example.com",
        _tty_out=False,
    )

    assert _targets(fake_ssh) == ["root@127.0.0.2", "root@127.0.0.3"]
    assert "╭ root@dev.example.com" not in out


def test_remote_host_group(fake_ssh):
    out = infrable.remote.managed_hosts("uptime", _tty_out=False)

    assert _targets(fake_ssh) == ["root@127.0.0.1"]
    assert "╭ root@dev.example.com" in out


def test_remote_host_group_only(fake_ssh):
    infrable.remote.managed_hosts("uptime", "--only", "dev_host")
    assert _targets(fake_ssh) == ["root@127.0.0.1"]

    infrable.remote.managed_hosts("uptime", "--only", "prod_host")
    assert _targets(fake_ssh) == ["root@127.0.0.1"]  # nothing new: not in the group


def test_remote_from_stdin(fake_ssh):
    stdin = "\n".join(
        [
            "root@dev.example.com some trailing text",
            "beta_host",
            "127.0.0.3 anything",
        ]
    )

    out = infrable.remote("-", "uptime", _in=stdin, _tty_out=False)

    assert _targets(fake_ssh) == ["root@127.0.0.1", "root@127.0.0.2", "root@127.0.0.3"]
    assert "╭ root@beta.example.com" in out


def test_remote_from_stdin_ignores_empty_hostnames(fake_ssh):
    infrable.remote("-", "uptime", _in="@ junk\nroot@ more junk\nbeta_host\n")

    assert _targets(fake_ssh) == ["root@127.0.0.2"]


def test_remote_from_stdin_ignores_blank_lines(fake_ssh):
    stdin = "\n\ndev_host\n   \n\t\nbeta_host extra\n\n"

    infrable.remote("-", "uptime", _in=stdin)

    assert _targets(fake_ssh) == ["root@127.0.0.1", "root@127.0.0.2"]


def test_remote_from_empty_stdin(fake_ssh):
    infrable.remote("-", "uptime", _in="")
    infrable.remote("-", "uptime", _in="\n\n")

    assert fake_ssh.calls() == []


def test_remote_deduplicates_hosts(fake_ssh):
    infrable.remote("-", "uptime", _in="dev_host\n127.0.0.1\ndev.example.com\n")

    assert _targets(fake_ssh) == ["root@127.0.0.1"]


def test_remote_affected_hosts(fake_ssh):
    shutil.rmtree(paths.files, ignore_errors=True)
    infrable.files.gen()
    for new in paths.files.glob("**/*.new"):
        new.with_suffix(".old").write_text("")

    out = infrable.remote("affected-hosts", "uptime", _tty_out=False)

    assert _targets(fake_ssh) == ["root@127.0.0.1"]
    assert "╭ root@dev.example.com" in out


def test_remote_affected_hosts_only(fake_ssh):
    shutil.rmtree(paths.files, ignore_errors=True)
    infrable.files.gen()
    for new in paths.files.glob("**/*.new"):
        new.with_suffix(".old").write_text("")

    infrable.remote("affected-hosts", "uptime", "--only", "prod_host")
    assert fake_ssh.calls() == []

    infrable.remote("affected-hosts", "uptime", "--only", "dev_host")
    assert _targets(fake_ssh) == ["root@127.0.0.1"]
