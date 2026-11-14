import os
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


def readfile(
    path: Path | str,
    *,
    init: Callable[[], str] = str,
    fmt: Callable[[str], T] | None = lambda s: s.strip(),
) -> T:
    """Get the contents of a file, creating it if it doesn't exist."""

    if isinstance(path, str):
        path = Path(path)
    if not path.exists():
        val = init()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Files read through here are usually secrets: owner-only by default.
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600), "w") as f:
            f.write(val)
    else:
        val = path.read_text()
    if fmt:
        return fmt(val)
    return val  # type: ignore
