from dataclasses import asdict, dataclass, field

from typer import Typer

from infrable.host import Host
from infrable.meta import Meta
from infrable.utils import item_formatter


@dataclass(unsafe_hash=True, order=True, eq=True)
class Service:
    """A generic service, maybe running on a host."""

    host: Host | None = None
    port: int | None = None
    # Often holds secrets, so keep it out of repr()
    meta: Meta = field(default_factory=Meta, repr=False)
    typer: Typer | None = None

    def format(self, name: str, format: str) -> str:
        return item_formatter(format).render(name=name, **asdict(self))

    def __str__(self) -> str:
        return f"{self.host or ''}:{self.port or ''}"
