# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues, discussions, or pull requests.**

Instead, use GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability** (under *Advisories*).
3. Provide a description, reproduction steps, affected version/commit, and impact.

This routes the report privately to the maintainer. If private reporting is not
available to you, open a minimal public issue that says only "requesting a
security contact" — with **no vulnerability details** — and the maintainer will
follow up privately.

### Please never include patient data

This is a medical imaging application. **Do not attach or paste DICOM files,
pixel data, screenshots of studies, logs containing patient identifiers, or any
PHI/PII** in a report. Describe the issue with synthetic or fully de-identified
data only. Reports containing patient data may be deleted without review.

## Scope

In scope: the application source under `src/`, build/packaging scripts, and CI
workflows in this repository.

Out of scope: vulnerabilities in third-party dependencies (report those
upstream; we track them via `pip-audit`, Grype, and Dependabot), and issues that
require a pre-compromised host or physical access.

## Supported versions

This project is developed on the `main` branch. Security fixes are applied to
`main` and included in the next release. Please verify an issue reproduces on the
latest `main` before reporting.

## Disclosure

Please allow a reasonable period for a fix before any public disclosure. We aim
to acknowledge reports promptly and will coordinate a disclosure timeline with
you.
