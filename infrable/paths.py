from pathlib import Path

templates = Path("templates")

var = Path(".infrable")
switches = var / Path("switches")
files = var / Path("files")
backups = var / Path("backups")


def ensure_var() -> None:
    """Create the private state directory. It may hold rendered secrets."""

    var.mkdir(mode=0o700, exist_ok=True)
    var.chmod(0o700)
