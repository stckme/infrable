import subprocess as sp
import threading

import pytest

from infrable import errors, utils


def test_item_formatter():
    tmpl = utils.item_formatter("{a},{b}\n")
    assert tmpl.render(a="x", b=1) == "x,1\n"


def test_item_formatter_renders_falsy_as_empty():
    tmpl = utils.item_formatter("[{a}][{b}][{c}]")
    assert tmpl.render(a=None, b="", c="v") == "[][][v]"


def test_item_formatter_does_not_re_render_values():
    assert utils.item_formatter("{a}").render(a="{{ b }}") == "{{ b }}"


def test_concurrent_preserves_order():
    assert utils.concurrent(lambda x: x * 2, range(10), workers=3) == list(
        range(0, 20, 2)
    )


def test_concurrent_empty():
    assert utils.concurrent(lambda x: x, []) == []


def test_concurrent_runs_in_threads():
    main = threading.get_ident()
    idents = utils.concurrent(lambda _: threading.get_ident(), range(4), workers=2)
    assert main not in idents


def test_concurrentcontext_is_lazy_iterator():
    with utils.concurrentcontext(lambda x: x + 1, [1, 2, 3]) as results:
        assert next(results) == 2
        assert list(results) == [3, 4]


def test_concurrent_propagates_errors():
    def boom(x):
        if x == 2:
            raise RuntimeError("boom")
        return x

    with pytest.raises(RuntimeError, match="boom"):
        utils.concurrent(boom, range(4))


@pytest.fixture
def no_sleep(monkeypatch):
    def patch(fn):
        monkeypatch.setattr(fn.retry, "sleep", lambda _: None)
        return fn

    return patch


def test_retryable_retries_until_success(no_sleep):
    calls = []

    @utils.retryable
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("not yet")
        return "ok"

    assert no_sleep(flaky)() == "ok"
    assert len(calls) == 3


def test_retryable_gives_up_after_ten_attempts(no_sleep):
    calls = []

    @utils.retryable
    def broken():
        calls.append(1)
        raise ConnectionError("always")

    with pytest.raises(ConnectionError, match="always"):
        no_sleep(broken)()
    assert len(calls) == 10


def test_item_formatter_is_sandboxed():
    # Format strings are user input: no reaching into Python internals
    out = utils.item_formatter("[{a.__class__}]").render(a=1)
    assert out == "[]"


def test_ssh_host_key_options_default(monkeypatch):
    monkeypatch.delenv("INFRABLE_STRICT_HOST_KEY_CHECKING", raising=False)
    assert utils.ssh_host_key_options() == ["-o", "StrictHostKeyChecking=accept-new"]


@pytest.mark.parametrize("value", ["yes", "no", "off", "ask", "accept-new"])
def test_ssh_host_key_options_override(monkeypatch, value):
    monkeypatch.setenv("INFRABLE_STRICT_HOST_KEY_CHECKING", value)
    assert utils.ssh_host_key_options() == ["-o", f"StrictHostKeyChecking={value}"]


def test_ssh_host_key_options_rejects_unknown_value(monkeypatch):
    monkeypatch.setenv("INFRABLE_STRICT_HOST_KEY_CHECKING", "maybe")
    with pytest.raises(errors.InvalidHostKeyCheckingError, match="maybe"):
        utils.ssh_host_key_options()


def _failing(code, calls):
    @utils.ssh_retryable
    def fn():
        calls.append(1)
        raise sp.CalledProcessError(code, "ssh")

    return fn


def test_ssh_retryable_retries_connection_errors(no_sleep):
    calls = []
    with pytest.raises(sp.CalledProcessError):
        no_sleep(_failing(255, calls))()
    assert len(calls) == 5


def test_ssh_retryable_does_not_rerun_failed_remote_commands(no_sleep):
    calls = []
    with pytest.raises(sp.CalledProcessError):
        no_sleep(_failing(1, calls))()
    assert len(calls) == 1


def test_ssh_retryable_does_not_retry_other_errors(no_sleep):
    calls = []

    @utils.ssh_retryable
    def fn():
        calls.append(1)
        raise ValueError("nope")

    with pytest.raises(ValueError):
        no_sleep(fn)()
    assert len(calls) == 1
