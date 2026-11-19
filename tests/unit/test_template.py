import pytest
from jinja2 import UndefinedError

from infrable import errors
from infrable.template import Dest, Metadata, render


def _template(tmp_path, text, name="t.j2"):
    path = tmp_path / name
    path.write_text(text)
    return path


@pytest.fixture(autouse=True)
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def test_dest_parse_string():
    assert Dest.parse("host:/etc/x") == Dest(loc="host:/etc/x")


def test_dest_parse_dict():
    dest = Dest.parse(
        {"loc": "host:/etc/x", "chmod": "600", "chown": "a:b", "ctx": {"k": "v"}}
    )

    assert (dest.loc, dest.chmod, dest.chown, dest.ctx) == (
        "host:/etc/x",
        "600",
        "a:b",
        {"k": "v"},
    )


def test_metadata_single_dest(tmp_path):
    path = _template(
        tmp_path,
        "# ---\n# src: s\n# dest: host:/etc/x\n# chmod: 644\n# chown: root:root\n# ---\nbody\n",
    )

    meta = Metadata.parse(path)

    assert meta.dest == [Dest(loc="host:/etc/x")]
    assert meta.chmod == 644
    assert meta.chown == "root:root"
    assert meta.skip is False
    assert meta.execute is False


def test_metadata_multiple_dests(tmp_path):
    path = _template(
        tmp_path,
        "# ---\n# src: s\n# dest:\n#   - host:/a\n#   - loc: host:/b\n#     ctx:\n#       n: 1\n# ---\n",
    )

    meta = Metadata.parse(path)

    assert [d.loc for d in meta.dest] == ["host:/a", "host:/b"]
    assert meta.dest[1].ctx == {"n": 1}


def test_metadata_without_dest(tmp_path):
    path = _template(tmp_path, "# ---\n# src: s\n# skip: true\n# ---\n")

    meta = Metadata.parse(path)

    assert meta.dest == []
    assert meta.skip is True


def test_metadata_empty_dest(tmp_path):
    path = _template(tmp_path, "# ---\n# src: s\n# dest:\n# ---\n")

    assert Metadata.parse(path).dest == []


def test_metadata_is_rendered_with_context(tmp_path):
    path = _template(
        tmp_path,
        "# ---\n# dest: {{ host }}:/etc/{{ name }}\n# src: {{ _template.src }}\n# ---\n",
    )

    meta = Metadata.parse(path, {"host": "h"}, name="n")

    assert meta.dest[0].loc == "h:/etc/n"
    assert meta.src == "t.j2"


def test_metadata_missing_header(tmp_path):
    path = _template(tmp_path, "just a file\n")

    with pytest.raises(errors.MissingMetadataError, match="t.j2"):
        Metadata.parse(path)


def test_metadata_undefined_variable_is_an_error(tmp_path):
    path = _template(tmp_path, "# ---\n# dest: {{ nope }}:/x\n# ---\n")

    with pytest.raises(UndefinedError):
        Metadata.parse(path)


def test_metadata_ignores_text_after_closing_marker(tmp_path):
    path = _template(
        tmp_path, "# ---\n# src: s\n# dest: h:/x\n# ---\n# ---\n# bogus: [\n# ---\n"
    )

    assert Metadata.parse(path).dest[0].loc == "h:/x"


def test_clean_header_full(tmp_path):
    path = _template(
        tmp_path,
        "# ---\n# src: s\n# dest: h:/x\n# chmod: 644\n# chown: a:b\n"
        "# execute: true\n# skip: false\n# ---\n",
    )

    header = Metadata.parse(path).clean_header("h:/x")

    assert set(header.splitlines()) == {
        "# dest: h:/x",
        "# src: s",
        "# chown: a:b",
        "# chmod: '644'",
        "# execute: true",
    }


def test_clean_header_dest_overrides_template_defaults(tmp_path):
    path = _template(
        tmp_path,
        "# ---\n# src: s\n# chmod: 644\n# chown: a:b\n# dest:\n"
        "#   - loc: h:/x\n#     chmod: 600\n#     chown: c:d\n"
        "#   - h:/y\n# ---\n",
    )
    meta = Metadata.parse(path)

    first = meta.clean_header("h:/x")
    second = meta.clean_header("h:/y")

    assert "chmod: '600'" in first and "chown: c:d" in first
    assert "chmod: '644'" in second and "chown: a:b" in second


def test_clean_header_minimal(tmp_path):
    path = _template(tmp_path, "# ---\n# src: s\n# dest: h:/x\n# ---\n")

    header = Metadata.parse(path).clean_header("h:/x")

    assert set(header.splitlines()) == {"# dest: h:/x", "# src: s"}


def test_render_replaces_header_and_renders_body(tmp_path):
    path = _template(
        tmp_path,
        "# ---\n# src: s\n# dest: h:/x\n# chmod: 644\n# ---\nhello {{ name }}",
    )

    out = render(path, "h:/x", {}, name="world")

    assert out.endswith("# ---\nhello world")
    assert out.startswith("# ---\n# ")
    assert "# dest: h:/x" in out
    assert "{{" not in out


def test_render_does_not_trim_or_add_whitespace(tmp_path):
    header = "# ---\n# src: s\n# dest: h:/x\n# ---\n"
    for body in ("body", "body\n", "body\n\n", "\n  body  \n"):
        path = _template(tmp_path, header + body)

        assert render(path, "h:/x", {}).endswith("# ---\n" + body)


def test_render_undefined_variable_is_an_error(tmp_path):
    path = _template(tmp_path, "# ---\n# src: s\n# dest: h:/x\n# ---\n{{ nope }}")

    with pytest.raises(UndefinedError):
        render(path, "h:/x", {})


def test_metadata_unknown_key_is_an_error(tmp_path):
    path = _template(tmp_path, "# ---\n# src: s\n# dest: h:/x\n# chmodd: 644\n# ---\n")

    with pytest.raises(errors.InvalidMetadataError, match="chmodd"):
        Metadata.parse(path)


def test_metadata_missing_src_is_an_error(tmp_path):
    path = _template(tmp_path, "# ---\n# dest: h:/x\n# ---\n")

    with pytest.raises(errors.InvalidMetadataError, match="missing src"):
        Metadata.parse(path)


def test_metadata_that_is_not_a_mapping(tmp_path):
    path = _template(tmp_path, "# ---\n# just a string\n# ---\n")

    with pytest.raises(errors.MissingMetadataError):
        Metadata.parse(path)


def test_dest_unknown_key_is_an_error():
    with pytest.raises(errors.InvalidMetadataError, match="chmodd"):
        Dest.parse({"loc": "h:/x", "chmodd": "644"})


def test_dest_without_loc_is_an_error():
    with pytest.raises(errors.InvalidMetadataError, match="missing loc"):
        Dest.parse({"chmod": "644"})
