from infrable import readfile


def test_readfile_creates_missing_file(tmp_path):
    path = tmp_path / "a" / "b" / "secret"

    assert readfile(path) == ""
    assert path.read_text() == ""


def test_readfile_init_value(tmp_path):
    path = tmp_path / "secret"

    assert readfile(path, init=lambda: "  generated \n") == "generated"
    assert path.read_text() == "  generated \n"


def test_readfile_does_not_overwrite(tmp_path):
    path = tmp_path / "secret"
    path.write_text("existing\n")

    assert readfile(str(path), init=lambda: "other") == "existing"
    assert path.read_text() == "existing\n"


def test_readfile_custom_format(tmp_path):
    path = tmp_path / "n"
    path.write_text("42\n")

    assert readfile(path, fmt=int) == 42


def test_readfile_without_format_returns_raw(tmp_path):
    path = tmp_path / "n"
    path.write_text(" raw \n")

    assert readfile(path, fmt=None) == " raw \n"


def test_readfile_creates_private_files(tmp_path):
    readfile(tmp_path / "secret")

    assert (tmp_path / "secret").stat().st_mode & 0o777 == 0o600
