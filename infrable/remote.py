import subprocess as sp
from pathlib import Path
from shlex import quote as q
from typing import IO, Any

from infrable import errors, infra


def _sudo_exec(
    address: str,
    command: list[str] | str,
    options: list[str] | None = None,
    shell: str | None = None,
    stdout: int | IO[Any] = sp.PIPE,
    stderr: int | IO[Any] = sp.PIPE,
    stdin: int | IO[Any] = sp.PIPE,
) -> sp.CompletedProcess[bytes]:
    if isinstance(command, list):
        command = sp.list2cmdline(command)
    if shell:
        command = sp.list2cmdline([shell, "-c", q(command)])
    options = options or []
    return sp.run(
        [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            *options,
            address,
            command,
        ],
        stdout=stdout,
        stderr=stderr,
        stdin=stdin,
    )


def sudo_pull_file_content(address: str, remote_src: str, admin_ssh_key: str | None = None) -> str:
    options = None
    if admin_ssh_key:
        options = ["-i", admin_ssh_key]
    proc = _sudo_exec(
        address,
        f"sudo test -f {q(remote_src)} && sudo cat -- {q(remote_src)} || true",
        options=options,
        stderr=sp.PIPE,
        stdin=sp.PIPE,
    )
    proc.check_returncode()
    return proc.stdout.decode()


def pull_file(remote_dest: str) -> str:
    remote, loc = remote_dest.split(":", 1)
    src = f"/{loc}"
    name = remote.split("@", 1)[-1]
    host = infra.get_host(name)
    if not host:
        raise errors.InvalidDestinationError(dest=remote_dest)
    addr = f"{host.admin}@{host.ip}"
    return sudo_pull_file_content(
        addr, src, admin_ssh_key=host.admin_ssh_key
    )
