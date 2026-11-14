import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Callable, Generator, Iterable, Iterator, TypeVar

from jinja2 import Template
from jinja2.sandbox import SandboxedEnvironment
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from infrable import errors

T1 = TypeVar("T1")
T2 = TypeVar("T2")


def item_formatter(template: str) -> Template:
    """Compile a `--format` string. It's user input, so render it sandboxed."""

    env = SandboxedEnvironment(
        variable_start_string="{",
        variable_end_string="}",
        autoescape=False,
        keep_trailing_newline=True,
        finalize=lambda x: x or "",
    )
    return env.from_string(template)


HOST_KEY_CHECKING_OPTIONS = {"yes", "no", "off", "ask", "accept-new"}


def ssh_host_key_options() -> list[str]:
    """The ssh options controlling host key verification.

    Defaults to `accept-new`: unknown hosts are trusted on first use, but a
    changed host key is refused. Override with INFRABLE_STRICT_HOST_KEY_CHECKING.
    """

    value = os.environ.get(errors.HOST_KEY_CHECKING_ENV, "accept-new")
    if value not in HOST_KEY_CHECKING_OPTIONS:
        raise errors.InvalidHostKeyCheckingError(value, HOST_KEY_CHECKING_OPTIONS)
    return ["-o", f"StrictHostKeyChecking={value}"]


def retryable(function: T1) -> T1:
    retryobj = retry(
        wait=wait_random_exponential(min=1, max=30),
        stop=stop_after_attempt(10),
        reraise=True,
    )
    return retryobj(function)  # type: ignore


def _is_ssh_connection_error(exc: BaseException) -> bool:
    # ssh exits with 255 when it fails itself (connection, auth, host key...).
    # Any other code is the remote command's, and re-running it isn't safe.
    return isinstance(exc, subprocess.CalledProcessError) and exc.returncode == 255


def ssh_retryable(function: T1) -> T1:
    """Like `retryable`, but only retries when ssh itself failed to connect."""

    retryobj = retry(
        retry=retry_if_exception(_is_ssh_connection_error),
        wait=wait_random_exponential(min=1, max=10),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    return retryobj(function)  # type: ignore


@contextmanager
def concurrentcontext(
    function: Callable[[T1], T2],
    generator: Iterable[T1],
    *,
    workers: int | None = None,
) -> Generator[Iterator[T2], None, None]:
    """With context, run a function on a batch of arguments concurrently."""

    with ThreadPoolExecutor(max_workers=workers) as executor:
        yield executor.map(function, generator)


def concurrent(
    function: Callable[[T1], T2],
    generator: Iterable[T1],
    *,
    workers: int | None = None,
) -> list[T2]:
    """Run a functions on a batch of arguments in concurrently."""

    with concurrentcontext(function, generator, workers=workers) as results:
        return list(results)
