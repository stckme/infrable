# Changelog

## 0.1.52

### Fixed

- Rendered templates will preserve ending newlines.

## 0.1.51

### Security

- SSH host keys are no longer ignored: the default is now `StrictHostKeyChecking=accept-new`
  (trust on first use, refuse changed keys). Set `INFRABLE_STRICT_HOST_KEY_CHECKING` to
  change it. **Behaviour change**: a host whose key changed now fails instead of connecting.
- Remote pushes write to a private temporary file created with `mktemp`, instead of a
  predictable `/tmp` name with default permissions. Files pushed without `chmod` still end
  up as `644`.
- Only SSH connection failures (exit code 255) are retried, 5 times. Previously every
  failure was retried 10 times, which re-ran failing `execute: true` scripts.
- `meta` is excluded from the `repr()` of `Host`, `Service` and `Switch`, so secrets in it
  are not printed by `infrable hosts --repr` and friends.
- `.infrable/` is created with mode `0700`, and `readfile` creates files with mode `0600`.
- `infrable init` now creates or updates `.gitignore` (`.infrable/`, `secrets/`).
- `--format` strings are rendered in a Jinja sandbox.
- Command quoting for `ssh` uses POSIX rules (`shlex`) instead of Windows rules.
- Templates can no longer write outside `.infrable/files` through a crafted `dest`, and
  `Host` rejects an `ip` or `admin` that is empty, contains whitespace, or (for `admin`)
  starts with `-`.
- A failed pull no longer reports an unreadable remote file as an empty one, and ssh's
  error output is shown when a remote command fails.

### Fixed

- `DuplicateFQDNError` said "Duplicate IP".
- `files revert` without any backup raises a clear error instead of a `ValueError`.
- Template headers with unknown keys, a missing `src`, or that aren't a mapping raise
  `InvalidMetadataError`/`MissingMetadataError` instead of a `TypeError`.

### Changed

- Dependency pins are now ranges (e.g. `tqdm>=4.66,<5`) instead of `~=` pins.
- Linting (`ruff`) runs in CI, which now also runs on pull requests.
