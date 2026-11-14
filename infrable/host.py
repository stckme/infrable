from dataclasses import asdict, dataclass, field

from sh import Command, ssh
from typer import Typer

from infrable import errors
from infrable.meta import Meta
from infrable.utils import item_formatter, ssh_host_key_options


def _check_ssh_field(field_name: str, value: str) -> str:
    # Whitespace would split the ssh address, a leading dash would be read as
    # an ssh option.
    if not value or value.startswith("-") or any(c.isspace() for c in value):
        raise errors.InvalidHostError(field_name, value)
    return value


@dataclass(unsafe_hash=True, order=True, eq=True)
class Host:
    """A generic host in the infrastructure."""

    ip: str  # The only required field

    fqdn: str | None = None
    admin: str = "root"
    admin_ssh_key: str | None = None
    # Often holds secrets, so keep it out of repr()
    meta: Meta = field(default_factory=Meta, repr=False)
    typer: Typer | None = None

    def __post_init__(self):
        _check_ssh_field("ip", self.ip)
        _check_ssh_field("admin", self.admin)

    def remote(self, login=None) -> Command:
        login = _check_ssh_field("login", login or self.admin)
        address = f"{login}@{self.ip}"
        cmd = ssh.bake(address, *ssh_host_key_options())  # type: ignore
        if self.admin_ssh_key:
            cmd = cmd.bake("-i", self.admin_ssh_key)
        return cmd

    def format(self, name: str, format: str) -> str:
        return item_formatter(format).render(name=name, **asdict(self))

    def __str__(self) -> str:
        host = self.fqdn or self.ip
        return f"{self.admin}@{host}"
