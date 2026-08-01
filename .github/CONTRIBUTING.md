# Contributing to DICOM Viewer V3

The full contributor guide lives at
**[dev-docs/CONTRIBUTING.md](../dev-docs/CONTRIBUTING.md)** — environment setup,
run/test commands, CI gates, and the privacy/PHI rules.

A few essentials before you start:

- **Never commit patient data (PHI/PII)** — no DICOM study files, pixel data,
  study screenshots, or logs with identifiers. Tests use synthetic or
  de-identified fixtures only. See
  [dev-docs/PHI_PII_REPOSITORY_GUARDRAILS.md](../dev-docs/PHI_PII_REPOSITORY_GUARDRAILS.md).
- Run `ruff`, `basedpyright`, and the test suite locally before opening a PR.
- Read [AGENTS.md](../AGENTS.md) for venv, `src/` layout, and CI notes.
- By participating you agree to the [Code of Conduct](../CODE_OF_CONDUCT.md).

Security issues: please follow [SECURITY.md](../SECURITY.md) and report privately.
