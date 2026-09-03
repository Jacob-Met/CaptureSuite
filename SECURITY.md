# Security Policy

## Supported versions

Security fixes are applied to the latest tagged release on `main`.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security problems.

Email the maintainers (or use GitHub private vulnerability reporting if
enabled on the repository) with:

- A description of the issue and its impact
- Steps to reproduce (PoC if available)
- Affected versions / commit SHA

We will acknowledge receipt within 7 days and aim to provide a fix or
mitigation timeline within 30 days for confirmed issues.

## Scope notes

CaptureSuite runs local named-pipe IPC and stores research session packages.
Treat session packages as potentially sensitive human-subjects data; see
`docs/design/research/ETHICS_AND_PRIVACY.md`.
