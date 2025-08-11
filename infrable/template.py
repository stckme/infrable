from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml
from jinja2 import StrictUndefined
from jinja2 import Template as JinjaTemplate

from infrable import errors, remote


def _jinja_render(content: str, *args: dict[str, Any], **kwargs: Any) -> str:
    return JinjaTemplate(content, undefined=StrictUndefined).render(*args, **kwargs)


@dataclass(frozen=True)
class Dest:
    """Destination for the rendered template, with optional context."""

    loc: str
    chown: Optional[str] = None
    chmod: Optional[str] = None
    ctx: dict = field(default_factory=dict)

    @classmethod
    def parse(cls, data: str | dict):
        """Parse a destination from the given string or dictionary."""

        if isinstance(data, str):
            return cls(loc=data)

        return cls(**data)


@dataclass(frozen=True)
class Block:
    """A block of text to be inserted into a file."""

    template: str
    marker: str = "# {mark} INFRABLE MANAGED BLOCK"

    @property
    def start_marker(self) -> str:
        return self.marker.format(mark="START")

    @property
    def end_marker(self) -> str:
        return self.marker.format(mark="END")

    def render(self, *args: dict[str, Any], **kwargs: Any) -> str:
        """Render the block with the given context."""

        rendered = _jinja_render(self.template, *args, **kwargs)
        return f"{self.start_marker}\n{rendered}\n{self.end_marker}"


@dataclass(frozen=True)
class Metadata:
    """Metadata defined in each template."""

    src: str
    dest: list[Dest]
    chown: Optional[str] = None
    chmod: Optional[str] = None
    skip: bool = False
    execute: bool = False
    block: Optional[Block] = None

    _raw: str = ""
    _rendered: str = ""

    @classmethod
    def parse(cls, path: Path, *args: dict[str, Any], **kwargs: Any):
        """Parse metadata from the given file content."""

        reading = False
        raw = ""
        rendered = ""
        for line in path.read_text().splitlines():
            if line == "# ---":
                if reading:
                    break
                else:
                    reading = True
                    continue
            if reading:
                raw += f"{line}\n"

        raw = raw.strip()

        kwargs["_template"] = {
            "src": str(path.resolve().relative_to(Path.cwd(), walk_up=True))
        }
        rendered = _jinja_render(raw, *args, **kwargs)
        yamllines = [line.removeprefix("# ") for line in rendered.splitlines()]
        if not yamllines:
            raise errors.MissingMetadataError(src=path)

        meta: dict = yaml.safe_load("\n".join(yamllines))
        meta_dest: str | dict | list[str | dict] | None = meta.pop("dest", None)

        dest = []
        if isinstance(meta_dest, list):
            dest = [Dest.parse(d) for d in meta_dest]
        elif not meta_dest:
            dest = []
        else:
            dest = [Dest.parse(meta_dest)]

        block_template = meta.pop("block", None)
        block = Block(template=block_template) if block_template else None

        return cls(dest=dest, _raw=raw, _rendered=rendered, block=block, **meta)

    def clean_header(self, dest_loc: str) -> str:
        dest = next(d for d in self.dest if d.loc == dest_loc)

        # We don't need "skip" in the final header
        dict_: dict[str, Any] = {"src": self.src, "dest": dest.loc}

        # We need chown and chmod in the final header to diff file permissions
        chown = dest.chown or self.chown
        if chown:
            dict_["chown"] = str(chown)
        chmod = dest.chmod or self.chmod
        if chmod:
            dict_["chmod"] = str(chmod)
        if self.execute:
            dict_["execute"] = self.execute

        header = yaml.safe_dump(dict_, default_flow_style=False)
        header = "\n".join(f"# {l}" for l in header.splitlines())
        return header


def render(path: Path, dest_loc: str, *args: dict[str, Any], **kwargs: Any) -> str:
    """Render the template with the given context, for a single destination."""

    meta = Metadata.parse(path, *args)
    header = meta.clean_header(dest_loc)
    tmpl = path.read_text().replace(meta._raw, header)
    content = _jinja_render(tmpl, *args, **kwargs)

    return f"{content}\n"  # all config, specially sudoers requires a trailing newline


def render_string(content: str, *args: dict[str, Any], **kwargs: Any) -> str:
    """Render the given string with the given context."""

    return _jinja_render(content, *args, **kwargs)


def apply(path: Path, dest_loc: str, *args: dict[str, Any], **kwargs: Any) -> str:
    """Render a block and apply it to the destination file."""

    meta = Metadata.parse(path, *args, **kwargs)
    assert meta.block, "Cannot apply a template without a block"

    content = remote.pull_file(dest_loc)

    # Render the block
    rendered_block = meta.block.render(*args, **kwargs)

    # Check if the block already exists
    start_marker = meta.block.start_marker
    end_marker = meta.block.end_marker
    if start_marker in content and end_marker in content:
        # Replace the existing block
        start_index = content.find(start_marker)
        end_index = content.find(end_marker) + len(end_marker)
        content = content[:start_index] + rendered_block + content[end_index:]
    else:
        # Add the block to the end of the file
        content += f"\n{rendered_block}"

    return content