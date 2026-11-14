from pathlib import Path

import pytest

from infrable import Switch, errors


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


OPTIONS = {"dev", "beta", "prod"}


def test_init_creates_state_file():
    sw = Switch(OPTIONS, init="dev")

    assert sw.path.as_posix() == ".infrable/switches/beta-dev-prod"
    assert sw.path.read_text() == "dev"


def test_init_keeps_existing_state():
    Switch(OPTIONS, init="dev").set("prod")

    assert Switch(OPTIONS, init="dev")() == "prod"


def test_invalid_init_value():
    with pytest.raises(errors.SwitchValueError):
        Switch(OPTIONS, init="staging")
    # no state is left behind
    assert not list(Path(".infrable/switches").glob("*"))


def test_set_and_get():
    sw = Switch(OPTIONS, init="dev")
    sw.set("beta")

    assert sw() == "beta"
    assert str(sw) == "beta"


def test_set_invalid_value_removes_state():
    sw = Switch(OPTIONS, init="dev")

    with pytest.raises(errors.SwitchValueError, match="Invalid value nope"):
        sw.set("nope")
    assert not sw.path.exists()


def test_call_with_cases():
    sw = Switch(OPTIONS, init="dev")

    assert sw(dev=1, prod=2) == 1
    sw.set("prod")
    assert sw(dev=1, prod=2) == 2
    # a missing case yields None
    sw.set("beta")
    assert sw(dev=1, prod=2) is None


def test_call_rejects_unknown_cases():
    sw = Switch(OPTIONS, init="dev")

    with pytest.raises(errors.SwitchCaseError):
        sw(dev=1, staging=2)


def test_strict_with_cases():
    sw = Switch(OPTIONS, init="dev")

    assert sw.strict(dev="d", beta="b", prod="p") == "d"
    sw.set("prod")
    assert sw.strict(dev="d", beta="b", prod="p") == "p"


def test_strict_requires_every_case():
    sw = Switch(OPTIONS, init="dev")

    with pytest.raises(errors.SwitchCaseError):
        sw.strict(dev="d", beta="b")
    with pytest.raises(errors.SwitchCaseError):
        sw.strict(dev="d", beta="b", prod="p", extra="x")


def test_strict_without_cases_returns_value():
    sw = Switch(OPTIONS, init="beta")

    assert sw.strict() == "beta"


def test_strict_detects_corrupted_state():
    sw = Switch(OPTIONS, init="dev")
    sw.path.write_text("garbage")

    with pytest.raises(errors.SwitchError, match="switch value is set to garbage"):
        sw.strict(dev=1, beta=2, prod=3)


def test_call_without_cases_returns_value():
    assert Switch(OPTIONS, init="prod")() == "prod"


def test_state_file_name_ignores_option_order():
    assert Switch(["b", "a"], init="a").path == Switch(["a", "b"], init="a").path


def test_format():
    sw = Switch(OPTIONS, init="dev")

    assert sw.format("env", "{name},{init}") == "env,dev"
