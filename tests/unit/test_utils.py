import threading

import pytest

from infrable import utils


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
