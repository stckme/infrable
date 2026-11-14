# Contributing

Thanks for your interest in Infrable! Bug reports, ideas and pull requests are welcome.

## Setup

```bash
git clone https://github.com/stckme/infrable
cd infrable
uv sync --dev
```

## Before you open a pull request

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

- The test suite requires **100% coverage** (see `[tool.pytest]` in `pyproject.toml`), and
  blocks network access (`--disable-socket`). Remote commands are tested against a fake
  `ssh` executable (the `fake_ssh` fixture in `tests/conftest.py`).
- Changes that touch what runs on the remote host (`infrable/files.py`, `infrable/host.py`)
  need tests asserting the exact commands, and extra care about quoting.
- Add a line to `CHANGELOG.md` for anything users will notice.

The tests run `infrable init` in the repository root, which creates a git-ignored
`infra.py`, `templates/`, `modules/` and `secrets/`.

## Reporting security issues

Please don't open a public issue. See [SECURITY.md](SECURITY.md).
