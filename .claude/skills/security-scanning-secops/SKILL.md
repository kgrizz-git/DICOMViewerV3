---
name: security-scanning-secops
description: >Runs and interprets security tooling—semgrep, grype, GitHub Actions hygiene, trufflehog, gitleaks—and records timestamped assessments. Use for secops subagent work, dependency vulnerability review, or secret scanning.
---

# Security scanning (secops)

## When to use which tool

| Concern | Example tool | Notes |
|--------|----------------|-------|
| Static analysis / bug patterns | `semgrep` | Use project config if present (`.semgrep.yml`). |
| Container / SBOM CVEs | `grype` | Point at image or SBOM; summarize critical/high. |
| CI/CD misuse, dangerous patterns | Review `.github/workflows/` | Pin actions, least privilege, no plaintext secrets. |
| Repo secrets | `trufflehog`, `gitleaks` | Run read-only; redact findings in summaries. |
| Dependency advisories | `pip audit`, `npm audit`, OSV, vendor advisories | Cross-check with trusted upstream docs. |

Run only what is **installed or available** in the environment; if a tool is missing, say so and suggest install or CI addition—do not fabricate scan output.

## Outputs

- **Targeted review**: comment in orchestration thread with file paths and severities.
- **Full assessment**: write `security-assessment-YYYYMMDD-HHMM.md` (UTC or local, be consistent) with executive summary, findings by severity, reproduction commands, and remediation order. To determine where to create this file, check repo for any subfolder matching `security-assessments` or `safety-assessments` or `safety-scans` or `assessments`, in that order. If none found, create `assessments/` in the repo base.

## Venv

- Apply **`python-venv-dependencies`** when scans invoke Python-based CLIs.
