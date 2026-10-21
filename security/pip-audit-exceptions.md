# Temporary pip-audit Exceptions

**Last reviewed:** 2026-10-21

These exceptions keep the dependency-audit workflow actionable while compatibility work is completed. They are not assertions that the vulnerabilities are harmless, and they do not suppress Grype, Semgrep, or runtime PHI protections.

| Advisory | Affected package | Fixed version | Why the project cannot upgrade yet | Remove the exception when |
|---|---|---:|---|---|
| `PYSEC-2026-2266` | `pydicom 2.4.5` | `3.0.2` | `pylinac` declares `pydicom<3` (confirmed still true in pylinac 3.47.0); this is a clinical QA dependency and its upgrade requires the documented verification plan. | A compatible Pylinac release permits pydicom 3 **and** the required dependency-bump / ACR-QA verification is complete. |
| `CVE-2026-112895`, `CVE-2026-112400`, `CVE-2026-112397`, `CVE-2026-112896`, `CVE-2026-112897`, `CVE-2026-112395`, `CVE-2026-112404`, `CVE-2026-112899` (PHI-tooling lane only; the PyPI feed lists 8 of the 9 Pillow 13.0.0 GHSAs, `GHSA-8g5g-8vmr-9782` is OSV-only) | `pillow 12.x` in the isolated `requirements-phi-tools.txt` environment | `13.0.0` | `presidio-image-redactor 0.0.60` declares `pillow<13.0.0`. The app and its locks are already on Pillow 13.0.0; only the separate, never-shipped PHI scanning venv stays on 12.x. The advisory-only `pip-audit-phi-tools` job ignores these IDs. The blocking `pip-audit` job has no Pillow exception. | A `presidio-image-redactor` release allowing `pillow>=13` is pinned in `requirements-phi-tools.txt`. |

Previously excepted and **removed on 2026-09-07** after a workflow audit found they no longer match anything in the audited dependency set (`requirements.txt`, `requirements-dev.txt`, `requirements-build.txt`): `PYSEC-2026-2132` (click), `CVE-2026-52870` / `CVE-2026-52869` / `CVE-2026-59950` (all `mcp 1.23.3`, a transitive dev-only dependency of Semgrep). Re-run without the corresponding `--ignore-vuln` before re-adding any of them.

## Monitoring and review

- Dependabot checks root Python requirement files monthly (on the 1st, 03:00 UTC) for version updates; security-update PRs for vulnerable dependencies are not tied to that schedule. It already has an open Pylinac update PR; review every Pylinac or Semgrep update PR against this table before merging.
- The `pip-audit` workflow runs weekly at 06:00 UTC and on requirement changes. The single blocking-job exception is intentional and explicit in the workflow so new findings still fail CI.
- The job resolves package metadata from PyPI live. A PyPI outage can fail it with a `ServiceError` (observed 2026-09-28: `503 … Backend is unhealthy for url: https://pypi.org/pypi/sqlcipher3/0.6.2/json`) — that is infrastructure flakiness, not a security finding; re-run the failed job before investigating dependencies.
- Reassess this exception no later than **2026-12-31**, and immediately after a relevant Dependabot PR or upstream security release.
- Dependabot will create a version-update PR when its monthly check finds a qualifying direct-dependency release. To receive that PR and Dependabot security-alert notifications, the repository owner must watch this repository with **All Activity**, or use **Custom** watch settings with at least **Pull requests** and **Security alerts** enabled. Keep at least one Dependabot PR active (merge, close, or otherwise interact with it) within 90 days: GitHub can pause updates for inactive repositories.

## Required removal process

1. Follow [`dev-docs/plans/completed/DEPENDENCY_BUMP_VERIFICATION_PLAN.md`](../dev-docs/plans/completed/DEPENDENCY_BUMP_VERIFICATION_PLAN.md) for the Pylinac/pydicom path, including clinical QA regression checks.
2. Update the affected requirement and run `pip-audit` without the corresponding `--ignore-vuln` option.
3. Remove the matching workflow exception and this row in the same commit.
