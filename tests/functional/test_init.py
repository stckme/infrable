import shutil
from pathlib import Path

from sh import infrable

from infrable import __version__

data = Path("tests/data")


def gen_test_data():
    Path("infra.py").unlink(missing_ok=True)
    shutil.rmtree("templates", ignore_errors=True)
    shutil.rmtree("modules", ignore_errors=True)
    infrable.init(_out=data.joinpath("pre_init"))
    infrable.init(_out=data.joinpath("post_init"))


def test_version():
    assert infrable.version().strip() == f"infrable {__version__}"


def test_init():
    Path("infra.py").unlink(missing_ok=True)
    shutil.rmtree("modules", ignore_errors=True)
    shutil.rmtree("templates", ignore_errors=True)
    assert infrable.init() == data.joinpath("pre_init").read_text()
    assert infrable.init() == data.joinpath("post_init").read_text()


def test_init_creates_gitignore(tmp_path, monkeypatch):
    from infrable import init

    monkeypatch.chdir(tmp_path)

    init.init()

    assert Path(".gitignore").read_text().splitlines() == [
        ".infrable/",
        "secrets/",
        "__pycache__/",
    ]


def test_init_appends_missing_entries_to_gitignore(tmp_path, monkeypatch, capsys):
    from infrable import init

    monkeypatch.chdir(tmp_path)
    Path(".gitignore").write_text("*.log\n/secrets")

    init.init()

    assert Path(".gitignore").read_text().splitlines() == [
        "*.log",
        "/secrets",
        ".infrable/",
        "__pycache__/",
    ]
    assert "Updated .gitignore." in capsys.readouterr().out


def test_init_leaves_complete_gitignore_alone(tmp_path, monkeypatch, capsys):
    from infrable import init

    monkeypatch.chdir(tmp_path)
    content = "/.infrable/\n/secrets/\n__pycache__\n"
    Path(".gitignore").write_text(content)

    init.init()

    assert Path(".gitignore").read_text() == content
    assert ".gitignore" not in capsys.readouterr().out


def test_init_appends_to_gitignore_with_trailing_newline(tmp_path, monkeypatch):
    from infrable import init

    monkeypatch.chdir(tmp_path)
    Path(".gitignore").write_text("*.log\n")

    init.init()

    assert Path(".gitignore").read_text().splitlines() == [
        "*.log",
        ".infrable/",
        "secrets/",
        "__pycache__/",
    ]
