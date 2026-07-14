# Temporary pip-audit Exceptions

**Last reviewed:** 2026-07-14

These exceptions keep the dependency-audit workflow actionable while compatibility work is completed. They are not assertions that the vulnerabilities are harmless, and they do not suppress Grype, Semgrep, or runtime PHI protections.

| Advisory | Affected package | Fixed version | Why the project cannot upgrade yet | Remove the exception when |
|---|---|---:|---|---|
| `PYSEC-2026-2266` | `pydicom 2.4.5` | `3.0.2` | `pylinac==3.43.2` declares `pydicom<3`; this is a clinical QA dependency and its upgrade requires the documented verification plan. | A compatible Pylinac release permits pydicom 3 **and** the required dependency-bump / ACR-QA verification is complete. |
| `PYSEC-2026-2132` | `click 8.1.8` | `8.3.3` | The current Semgrep release requires `click~=8.1.8`. | A Semgrep release resolves with Click 8.3.3 or later; upgrade Semgrep and remove this exception. |

## Monitoring and review

- Dependabot checks root Python requirement files every Monday at 03:00 UTC. It already has an open Pylinac update PR; review every Pylinac or Semgrep update PR against this table before merging.
- The `pip-audit` workflow runs weekly at 06:00 UTC and on requirement changes. The exceptions are intentionally explicit in the workflow so new findings still fail CI.
- Reassess these exceptions no later than **2026-10-14**, and immediately after a relevant Dependabot PR or upstream security release.
- Dependabot will create a version-update PR when its weekly check finds a qualifying direct-dependency release. To receive that PR and Dependabot security-alert notifications, the repository owner must watch this repository with **All Activity**, or use **Custom** watch settings with at least **Pull requests** and **Security alerts** enabled. As of this review, the authenticated account had no watch subscription for this repository; configure the Watch menu in GitHub and ensure watching notifications are enabled in account settings. Keep at least one Dependabot PR active (merge, close, or otherwise interact with it) within 90 days: GitHub can pause updates for inactive repositories.

## Required removal process

1. Follow [`dev-docs/plans/completed/DEPENDENCY_BUMP_VERIFICATION_PLAN.md`](../dev-docs/plans/completed/DEPENDENCY_BUMP_VERIFICATION_PLAN.md) for the Pylinac/pydicom path, including clinical QA regression checks.
2. Update the affected requirement and run `pip-audit` without the corresponding `--ignore-vuln` option.
3. Remove the matching workflow exception and this row in the same commit.
