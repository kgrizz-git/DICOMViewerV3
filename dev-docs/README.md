# Developer documentation index

**Last updated:** 2026-07-14

This folder is for **contributors, maintainers, and release engineering**. End-user guides live under **`user-docs/`** (start at [`USER_GUIDE.md`](../user-docs/USER_GUIDE.md)); repository orientation for everyone is in the root **[`README.md`](../README.md)**.

For docs that already have a `**Last updated:**` line, update the date when an edit changes policy, workflow, user-facing behavior, or canonical guidance. Do not bump dates for typo-only edits. Completed plans, one-off investigations, changelogs, and dated maintenance-log entries usually do not need separate date churn.

## Setup and workflow

| Document | Purpose |
|----------|---------|
| [`DEVELOPER_SETUP.md`](DEVELOPER_SETUP.md) | Environment setup, hooks, troubleshooting installs |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Human contributor playbook: hooks, CI, releases, pylinac bumps, licenses |
| [`CODE_DOCUMENTATION.md`](CODE_DOCUMENTATION.md) | Where major UI modules, dialogs, and bundled help files live |
| [`../AGENTS.md`](../AGENTS.md) | AI agents: venv, run/test, orchestration (short table of contents) |
| [`../ARCHITECTURE.md`](../ARCHITECTURE.md) | Domains, dependency rules, where to change code |
| [`SOURCE_LAYOUT.md`](SOURCE_LAYOUT.md) | Full `src/` tree, controllers, signal wiring |
| [`HARNESS.md`](HARNESS.md) | Agent harness layers, scripts, CI, smoke workflow |
| [`../src/utils/debug_flags.py`](../src/utils/debug_flags.py) | Central `DEBUG_*` toggles for console diagnostics (default off; CI enforces off before merge) |

## Releases and versioning

| Document | Purpose |
|----------|---------|
| [`RELEASING.md`](RELEASING.md) | Version bump, changelog, tags, in-app doc URL notes |
| [`info/SEMANTIC_VERSIONING_GUIDE.md`](info/SEMANTIC_VERSIONING_GUIDE.md) | SemVer rules for this project |
| [`info/BUILDING_EXECUTABLES.md`](info/BUILDING_EXECUTABLES.md) | Frozen builds, PyInstaller, artifacts |

## Security and compliance

| Document | Purpose |
|----------|---------|
| [`SECURITY_HARDENING_GUIDE.md`](SECURITY_HARDENING_GUIDE.md) | Security posture and hardening |
| [`SECURITY_TOOLS_CLI_GUIDE.md`](SECURITY_TOOLS_CLI_GUIDE.md) | Local scanners (semgrep, TruffleHog, etc.) |
| [`info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md`](info/BUNDLED_PACKAGES_AND_FONTS_LICENSES.md) | Dependency and font license inventory |
| [`info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md`](info/PYLIBJPEG_ALTERNATIVES_AND_DICOM_DECODER_STRATEGY.md) | `pylibjpeg-libjpeg` replacement options and decoder tradeoffs |

## Plans and tracking

| Location | Purpose |
|----------|---------|
| [`plans/`](plans/) | Active, supporting, and archived implementation plans |
| [`plans/supporting/`](plans/supporting/) | Ongoing dependency/reference plans that still support open backlog work |
| [`plans/completed/`](plans/completed/) | Completed implementation plan records; move finished plans here when closing their backlog items |
| [`TO_DO.md`](TO_DO.md) | Active product and engineering backlog |
| [`MAINTENANCE_LOG.md`](MAINTENANCE_LOG.md) | Developer-maintenance history: CI, harness, static analysis, dependency verification, repo hygiene |
| [`implementation-plans.md`](plans/completed/implementation-plans.md) | Plan index / rollup (if maintained) |

## Reference and research (`info/`)

Deep dives on pylinac, DICOM behavior, GitHub Actions billing, fusion, SR, etc.: see **[`info/`](info/)** and follow filenames by topic.

| Topic | Doc |
|-------|-----|
| GSPS, KO, Secondary Capture (read/export/app status) | [`info/DICOM_GSPS_KO_SECONDARY_CAPTURE.md`](info/DICOM_GSPS_KO_SECONDARY_CAPTURE.md) |
| KO/PR objects and embedded overlays | [`info/KO_PR_OVERLAYS_EXPLANATION.md`](info/KO_PR_OVERLAYS_EXPLANATION.md) |
| Competitive feature gaps (vs RadiAnt, Horos, OHIF, etc.) | [`info/DICOM_VIEWER_COMPETITIVE_FEATURE_GAP_ANALYSIS.md`](info/DICOM_VIEWER_COMPETITIVE_FEATURE_GAP_ANALYSIS.md) |
| Optional local PII/PHI text-detection models and Presidio integration | [`info/LOCAL_PHI_PII_DETECTION_MODEL_OPTIONS.md`](info/LOCAL_PHI_PII_DETECTION_MODEL_OPTIONS.md) |

## Assessments and templates

| Location | Purpose |
|----------|---------|
| [`doc-assessments/`](doc-assessments/) | Timestamped documentation assessments |
| [`templates-generalized/`](templates-generalized/) | Reusable templates (assessments, plans) |
| [`refactor-assessments/`](refactor-assessments/) | Refactor-focused assessments |

## Quality checks (documentation)

| Script / workflow | Purpose |
|-------------------|---------|
| [`../scripts/check_user_docs_links.py`](../scripts/check_user_docs_links.py) | Validates relative links in `user-docs/*.md` and `dev-docs/README.md` |
| [`../scripts/check_repo_harness.py`](../scripts/check_repo_harness.py) | Harness files, slim `AGENTS.md`, `TO_DO.md` freshness, plan paths, harness doc links |
| [`../scripts/check_architecture_boundaries.py`](../scripts/check_architecture_boundaries.py) | AST import-boundary guard against new high-risk layer violations (`architecture_boundary_baseline.txt` tracks current legacy edges) |
| [`../scripts/agent_smoke_harness.py`](../scripts/agent_smoke_harness.py) | Imports, version, committed DICOM fixture; optional `--qt-smoke` |
| [`.github/workflows/user-docs-links.yml`](../.github/workflows/user-docs-links.yml) | CI: user-docs links on `main` / `develop` |
| [`.github/workflows/repo-harness.yml`](../.github/workflows/repo-harness.yml) | CI: harness docs + architecture boundaries + agent smoke on `main` / `develop` |

## Orchestration (optional)

| Document | Purpose |
|----------|---------|
| [`orchestration/RUN_PACKET_TEMPLATE.md`](orchestration/RUN_PACKET_TEMPLATE.md) | Multi-agent run packets |
| [`orchestration/AGENT_SMOKE.md`](orchestration/AGENT_SMOKE.md) | Manual UI smoke checklist for agents |
| [Orchestration state](../plans/orchestration-state.md) | Repo-level `plans/orchestration-state.md` (if used in your workflow) |
