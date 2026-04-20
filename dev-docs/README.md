# Developer documentation index

This folder is for **contributors, maintainers, and release engineering**. End-user guides live under **`user-docs/`** (start at [`USER_GUIDE.md`](../user-docs/USER_GUIDE.md)); repository orientation for everyone is in the root **[`README.md`](../README.md)**.

## Setup and workflow

| Document | Purpose |
|----------|---------|
| [`DEVELOPER_SETUP.md`](DEVELOPER_SETUP.md) | Environment setup, hooks, troubleshooting installs |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Human contributor playbook: hooks, CI, releases, pylinac bumps, licenses |
| [`CODE_DOCUMENTATION.md`](CODE_DOCUMENTATION.md) | Where major UI modules, dialogs, and bundled help files live |
| [`../AGENTS.md`](../AGENTS.md) | AI agents and quick ops: venv, `src/` map, orchestration, display options |

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

## Plans and tracking

| Location | Purpose |
|----------|---------|
| [`plans/`](plans/) | Active and archived implementation plans |
| [`plans/supporting/`](plans/supporting/) | Supporting and dependency plans |
| [`plans/completed/`](plans/completed/) | Completed plan records |
| [`TO_DO.md`](TO_DO.md) | Product and engineering backlog |
| [`implementation-plans.md`](implementation-plans.md) | Plan index / rollup (if maintained) |

## Reference and research (`info/`)

Deep dives on pylinac, DICOM behavior, GitHub Actions billing, fusion, SR, etc.: see **[`info/`](info/)** and follow filenames by topic.

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
| [`.github/workflows/user-docs-links.yml`](../.github/workflows/user-docs-links.yml) | CI job that runs the script on `main` / `develop` |

## Orchestration (optional)

| Document | Purpose |
|----------|---------|
| [`orchestration/RUN_PACKET_TEMPLATE.md`](orchestration/RUN_PACKET_TEMPLATE.md) | Multi-agent run packets |
| [Orchestration state](../plans/orchestration-state.md) | Repo-level `plans/orchestration-state.md` (if used in your workflow) |
