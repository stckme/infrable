"""Tests for the remaining top-level CLI behaviour."""

from pathlib import Path

import pytest
import sh
from sh import infrable

data = Path("tests/data")


def test_services_repr():
    out = infrable.services(repr=True, _tty_out=False)
    assert "nginx = Service(host=Host(ip='127.0.0.1'" in out
    assert "web = Service(" in out


def test_switches_repr():
    out = infrable.switches(repr=True, _tty_out=False)
    assert out.startswith("env = Switch(options={")
    assert "init='dev'" in out


def test_switches_format():
    out = infrable.switches(format="{name},{init}", _tty_out=False)
    assert out == "env,dev\n"


def test_env_alias_options():
    assert infrable.env(options=True, _tty_out=False).split() == ["beta", "dev", "prod"]


def test_env_alias_get_and_set():
    try:
        infrable.env.beta()
        assert infrable.env(_tty_out=False).strip() == "beta"
    finally:
        infrable.env.dev()
    assert infrable.env(_tty_out=False).strip() == "dev"


def test_env_alias_rejects_unknown_value():
    with pytest.raises(sh.ErrorReturnCode_2):
        infrable.env.staging()


def test_switch_options():
    assert infrable.switch.env(options=True, _tty_out=False).split() == [
        "beta",
        "dev",
        "prod",
    ]


def test_switch_rejects_unknown_value():
    with pytest.raises(sh.ErrorReturnCode_2):
        infrable.switch.env.staging()
    assert infrable.switch.env(_tty_out=False).strip() == "dev"


def test_files_gen_only_skips_other_hosts():
    out = infrable.files.gen(only="prod_host", _tty_out=False)

    assert "skipping root@dev.example.com:/etc/nginx/proxy_params" in out
    assert ".new" not in out
    assert not list(Path(".infrable/files").glob("**/*.new"))


def test_files_gen_single_template_path():
    out = infrable.files.gen("templates/nginx/proxy_params.j2", _tty_out=False)

    assert out.count(".new") == 1
    assert "proxy_params.new" in out


def test_files_deploy_help():
    assert "generate, pull, backup" in infrable.files.deploy("--help")


def test_files_recover_help():
    assert "revert and push" in infrable.files.recover("--help")


def test_files_revert_without_backups(tmp_path):
    # `revert` picks the latest backup; with an explicit empty dir it's a no-op
    out = infrable.files.revert(str(tmp_path), _tty_out=False)
    assert out.strip() == f"reverting from: {tmp_path}"


def test_unknown_command_fails():
    with pytest.raises(sh.ErrorReturnCode_2):
        infrable.nonexistent()
