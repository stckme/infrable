# Security Policy

## Supported versions

Infrable is a 0.x project. Security fixes are made in the latest release only.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Report them privately to the maintainers. Include what you found, the steps to reproduce
it and the version you tested. You can expect an acknowledgement within a week.

## Scope and threat model

Infrable runs `infra.py` and your templates as code, and executes commands on your hosts
over SSH with `sudo`. That is by design, so the following are **not** vulnerabilities:

- Code in an `infra.py`, a module or a template running when you run `infrable` in that
  directory.
- Scripts marked `execute: true` running as root on the managed hosts.

Things that **are** in scope: unexpected local file writes or reads outside the project,
shell injection through values Infrable quotes or passes to `ssh`, leaking secrets
(plaintext in logs, `repr()`, permissive file modes), and weaknesses in how files are
transferred to, or written on, the remote hosts. See the
[security model](README.md#security-model-and-limitations).
