import json
import os
import shlex
import shutil
import sys
from pathlib import Path

import pytest
from sh import infrable


def pytest_configure(config):
    Path("infra.py").unlink(missing_ok=True)
    shutil.rmtree("templates", ignore_errors=True)
    shutil.rmtree("modules", ignore_errors=True)
    infrable.init()
    infrable.env.dev()


FAKE_SSH = """#!{python}
import json, os, shlex, sys

argv = sys.argv[1:]
command = argv[-1] if argv else ""
stdin = sys.stdin.read() if "sudo tee" in command else None

with open(os.environ["FAKE_SSH_LOG"], "a") as f:
    f.write(json.dumps({{"argv": argv, "stdin": stdin}}) + "\\n")

if os.environ.get("FAKE_SSH_FAIL"):
    sys.stderr.write(os.environ["FAKE_SSH_FAIL"])
    sys.exit(int(os.environ.get("FAKE_SSH_EXIT", "255")))

if "sudo cat --" in command:
    src = shlex.split(command.split("sudo cat --", 1)[1].split("||")[0])[0]
    remote = os.path.join(os.environ["FAKE_SSH_REMOTE"], src.lstrip("/"))
    if os.path.exists(remote):
        with open(remote) as f:
            sys.stdout.write(f.read())
else:
    print("fake-ssh: " + " ".join(argv))
"""


class FakeSSH:
    """A stand-in for the ssh binary, recording every invocation."""

    def __init__(self, root: Path):
        self.root = root
        self.log = root / "calls.jsonl"
        self.remote = root / "remote"
        self.remote.mkdir()
        self.log.touch()

    def calls(self) -> list[dict]:
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def commands(self) -> list[str]:
        return [c["argv"][-1] for c in self.calls()]

    @staticmethod
    def script(call: dict) -> str:
        """The shell script of a push, which is sent as `sh -c '<script>'`."""

        return shlex.split(call["argv"][-1])[2]

    def put(self, path: str, content: str):
        dest = self.remote / path.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content)


@pytest.fixture
def fake_ssh(tmp_path, monkeypatch) -> FakeSSH:
    """Put a fake `ssh` first in PATH, for this process and its children."""

    bindir = tmp_path / "bin"
    bindir.mkdir()
    ssh = bindir / "ssh"
    ssh.write_text(FAKE_SSH.format(python=sys.executable))
    ssh.chmod(0o755)

    fake = FakeSSH(tmp_path)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_SSH_LOG", str(fake.log))
    monkeypatch.setenv("FAKE_SSH_REMOTE", str(fake.remote))
    monkeypatch.delenv("FAKE_SSH_FAIL", raising=False)
    monkeypatch.delenv("FAKE_SSH_EXIT", raising=False)
    monkeypatch.delenv("INFRABLE_STRICT_HOST_KEY_CHECKING", raising=False)
    return fake
