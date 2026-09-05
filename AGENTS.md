---
description: 
alwaysApply: true
---

# Agent instructions – DICOM Viewer V3

**Last updated:** 2026-08-31

**Table of contents** for agents: operational facts here; architecture, module tree, and harness checks linked below (progressive disclosure per [harness engineering](https://openai.com/index/harness-engineering/)).

**Human contributors:** [`dev-docs/CONTRIBUTING.md`](dev-docs/CONTRIBUTING.md) · **Harness index:** [`dev-docs/HARNESS.md`](dev-docs/HARNESS.md)

## Local dashboard access

If a read-only check of a local dashboard or loopback service fails inside the
sandbox, retry the same narrow command once with `require_escalated` before
reporting the service unavailable. When the project uses an ignored `.env` for
credentials, load it only within that command; never echo or otherwise expose
its values.

## Virtual environment (venv)

**Always activate the project virtual environment before running tests or application code.**

The env folder may be named `.venv`, `venv`, `env`, or `virtualenv`. **`launch.bat`** and **`launch.command`** pick the first that exists under the project root (Windows: `Scripts\python.exe`; macOS/Linux: `bin/python`), in that order. If none exist, they create **`.venv`**. They use that interpreter for `pip install` and `run.py` (not bare `python` after `activate`). If the env is incomplete, **Run** installs requirements first. Prefer **`.venv`** next to `requirements.txt`.

On a typical Windows checkout (if search ignores hidden folders):

- PowerShell: `%USERPROFILE%\...\DICOMViewerV3\.venv\Scripts\Activate.ps1`
- Python: `%USERPROFILE%\...\DICOMViewerV3\.venv\Scripts\python.exe`

- **Windows (cmd):** `<dir>\Scripts\activate`
- **Windows (PowerShell):** `.\.venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source .venv/bin/activate`

From project root, after activation:

- Run the app: `python src/main.py`
- Run tests: `python tests/run_tests.py` or `python -m pytest tests/ -v` (**`tests/README.md`**). `pytest.ini` sets `-n auto`, so runs are parallel; add `-n 0` for serial/single-test iteration. Never construct a `QCoreApplication` in a test — depend on the session `qapp` fixture.
- **basedpyright vs PySide6:** CI installs fresh deps (`PySide6>=6.11.1` may resolve 6.11.2+). If local basedpyright suddenly reports many `QTreeWidgetItem | None` errors after `pip install -r requirements-dev.txt`, upgrade PySide6 to match CI and re-run `python scripts/check_basedpyright_errors.py` (tree code uses `gui.qt_tree_widget_utils.iter_tree_children`).
- Agent smoke: `python scripts/agent_smoke_harness.py`
- Harness docs check: `python scripts/check_repo_harness.py`
- Architecture boundaries: `python scripts/check_architecture_boundaries.py`

If no venv exists: `python -m venv .venv`, activate, `pip install -r requirements.txt`.

## Native VTK tests in the agent sandbox

VTK's macOS wheel has no EGL/OSMesa fallback here, so `vtkRenderWindow` can segfault at `vtkGenericRenderWindowInteractor.Initialize()`.
Retry the narrow test once with `require_escalated` (native graphics); do not skip it or blame xdist. See [`dev-docs/info/TESTING_GUIDANCE.md`](dev-docs/info/TESTING_GUIDANCE.md#vtk-rendering-on-macos).

**Cine export:** `requirements.txt` pins **`imageio`** + **`imageio-ffmpeg`** (FFmpeg license obligations for frozen builds). **`IMAGEIO_FFMPEG_EXE`** can override the wheel binary. Prefer **`.mp4`** on Windows 11 Media Player over **`.mpg`** without the MPEG-2 extension.

## Repository map (read next)

| Topic | Location |
|-------|----------|
| Domains, dependency rules, where to edit | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Source navigation, controllers, signal wiring | [`dev-docs/SOURCE_LAYOUT.md`](dev-docs/SOURCE_LAYOUT.md) |
| Backlog | [`dev-docs/TO_DO.md`](dev-docs/TO_DO.md) |
| Maintenance / developer history | [`dev-docs/MAINTENANCE_LOG.md`](dev-docs/MAINTENANCE_LOG.md) |
| Plans (active / supporting / completed) | [`dev-docs/plans/`](dev-docs/plans/) |
| Developer doc index | [`dev-docs/README.md`](dev-docs/README.md) |
| UI design spec | [`DESIGN.md`](DESIGN.md) |
| Test-writing tiers (unit, Qt/PySide6, pylinac) | [`dev-docs/info/TESTING_GUIDANCE.md`](dev-docs/info/TESTING_GUIDANCE.md) |
| Manual agent smoke steps | [`dev-docs/orchestration/AGENT_SMOKE.md`](dev-docs/orchestration/AGENT_SMOKE.md) |
| **Debug / diagnostic prints** | [`src/utils/debug_flags.py`](src/utils/debug_flags.py) — all `DEBUG_*` toggles (default `False`) |

## Repository navigation

Use `rg` for scoped text and file searches (for example, `rg --files src` or
`rg "symbol_name" src tests`). It is a workstation tool, not an application
dependency; never add it to this project's Python environment. If unavailable,
use `find` and the platform's available text-search tool rather than assuming
`rg` exists.

## Conventions (short)

- **Layout:** `src/` (app), `tests/`, `user-docs/`, `dev-docs/` (plans, assessments).
- **Local study index:** `src/core/study_index/` — plan: [`LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`](dev-docs/plans/supporting/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md).
- **Pylinac:** exact pin in `requirements.txt`; bump via [`DEPENDENCY_BUMP_VERIFICATION_PLAN.md`](dev-docs/plans/completed/DEPENDENCY_BUMP_VERIFICATION_PLAN.md) and [`PYLINAC_INTEGRATION_OVERVIEW.md`](dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md).
- **Known dependency advisories:** [`security/pip-audit-exceptions.md`](security/pip-audit-exceptions.md) records the two temporary `pip-audit` exceptions, their review triggers, and the required removal criteria. Do not add or broaden an exception without explicit review.
- **Version / changelog / SemVer:** bump [`src/version.py`](src/version.py) and keep **Current version** in [`CHANGELOG.md`](CHANGELOG.md) in sync; follow [`dev-docs/RELEASING.md`](dev-docs/RELEASING.md) for release cuts and [`dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md`](dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md) for version increments.
- **Tracking split / plan archive:** [`dev-docs/TO_DO.md`](dev-docs/TO_DO.md) is the active backlog, not a completion log. Remove fully completed items once captured in [`CHANGELOG.md`](CHANGELOG.md), [`dev-docs/MAINTENANCE_LOG.md`](dev-docs/MAINTENANCE_LOG.md), or a durable plan/investigation record. Move finished implementation plans to [`dev-docs/plans/completed/`](dev-docs/plans/completed/); keep only ongoing dependency/reference plans in [`dev-docs/plans/supporting/`](dev-docs/plans/supporting/). When a plan is merged but manual smoke remains, archive the plan and track the smoke in **Manual Smoke Checks** in `TO_DO.md` (one umbrella pointer in **Next up**). Use `CHANGELOG.md` for user-visible release changes and `MAINTENANCE_LOG.md` for CI, harness, static-analysis, dependency-verification, and repo-maintenance history.
- **Doc dates:** when editing a document that already has a `**Last updated:**` line, update the date if the edit changes policy, workflow, user-facing behavior, or canonical guidance. Do not bump dates for typo-only edits.
- **PHI / PII guardrails:** Before adding studies, DICOM, spreadsheets, screenshots, archives, document packages, or binary assets, read [`PHI_PII_REPOSITORY_GUARDRAILS.md`](dev-docs/PHI_PII_REPOSITORY_GUARDRAILS.md). The blocking artifact gate is `scripts/check_no_phi_artifacts.py`; its reviewed-asset manifest is `security/approved-media-sha256.json`. **Hounddog is local-only, non-blocking, and disconnected from accounts, repository integrations, uploads, and CI until the user explicitly changes that policy.**
- **Tool inventory:** Before adding, replacing, or upgrading a privacy/security/analysis tool or model, update [`security/security-tool-inventory.json`](security/security-tool-inventory.json) and run `python scripts/check_security_tool_inventory.py`.
- **Protected local data roots:** Never stage files under `data/` (except `.gitkeep`), `test-DICOM-data/`, `sample-DICOM-gitignored/`, `decoder-spike-artifacts/`, `resources/screenshots-ignored/`, `logs/`, `.sonar-local/`, `.phi-tools/`, `tmp/`, or `backups/`. Do not remove their privacy-critical `.gitignore` rules. The staged artifact gate blocks both actions even when `git add -f` is used. Relevant staged fixture/data, raster-media, and DICOM changes automatically invoke the available local advisory PhiScan/OCR/Presidio/DICOM wrappers; a `main` push invokes local-only Hounddog after blocking gates pass. Never treat an advisory clean result as permission to update the reviewed-asset manifest without the required human review.
- **Scratch output:** Write throwaway agent scratch (debug dumps, temp captures, intermediate logs, generated fixtures meant to be discarded) under the repo `tmp/` folder, **not** the OS `/tmp`. `tmp/` is gitignored and exempt from the PHI/artifact gate, so it stays inside the repo checkout and is cleaned with normal housekeeping. Never stage anything from `tmp/`.
- **Privacy checks:** run `scripts/git_hook_privacy_checks.py --staged` before
  committing output/logging/dialog/debug changes, `--all` for the complete
  advisory debt inventory, and `--all --critical` before push. Before
  adding data/media/DICOM, run the artifact gate plus the relevant isolated
  `scripts/privacy_tool_review.py` lane. Hounddog remains local-only,
  no-account/no-SCM, advisory. Scanner `SKIP` is not a pass. Never paste matched
  values into chat, commits, issues, or reports — see
  [`SECURITY_TOOLS_CLI_GUIDE.md`](dev-docs/SECURITY_TOOLS_CLI_GUIDE.md).
- **Debug flags:** Before adding `print` tracing, read [`src/utils/debug_flags.py`](src/utils/debug_flags.py) and gate behind an existing or new `DEBUG_*` constant (default **`False`**). Each flag documents which modules it affects. Revert flags to **`False`** before commit — CI **debug-flags-check** fails on any `True`. Do not use `DEBUG_AGENT_LOG` in release builds (writes `debug-088dbc.log`).
- **Long-running commands:** use ~10 minute timeouts for full `pytest` or `pyright src/`. Whole-repository pre-push privacy, PHI, secret, and type-analysis gates may take several minutes with little or no output; treat them as running until their completion status is known, give a progress update, and wait/poll rather than inferring failure.
- **Git hooks:** Never use `--no-verify`, disable or edit a hook to skip checks, or use an equivalent workaround for any commit, push, or verification gate unless the user gives explicit, specific approval to bypass that exact gate after its risk has been explained. A general request to commit, push, update a PR, or finish work is not approval. Git hooks (line complexity, PHI checks, ruff linting, etc.) are important quality gates. If hooks fail, fix the underlying issues or report the blocker rather than bypassing them.

## Optional delegation

Use worktrees and subagents for isolated or parallel work; archive or remove
them when the task is done. For a high-risk privacy, security, persistence, or
release change, prefer one focused independent review and one full test-suite
run at the end of the completed batch.

## Verification before claiming done

| Check | Command |
|-------|---------|
| Tests | `python -m pytest tests/ -v` |
| User-docs links | `python scripts/check_user_docs_links.py` |
| Repo harness | `python scripts/check_repo_harness.py` |
| Architecture boundaries | `python scripts/check_architecture_boundaries.py` |
| Agent smoke | `python scripts/agent_smoke_harness.py` |

After editing `user-docs/` or `dev-docs/README.md`, run the link checker (CI: **User docs links**). For user-visible changes, contract docstrings, and release assessments, follow [`DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md`](dev-docs/plans/DOCUMENTATION_WORKFLOW_AND_FRESHNESS_PLAN.md).

## CI (summary)

Workflows on **main** / **develop**: tests, Semgrep, Grype, debug flags, user-docs links, repo harness, SonarQube Cloud. The approved SonarQube Cloud scan imports pytest coverage (`coverage.xml`, `src/` paths only) via an internal CI artifact; coverage goes to no other external service. Preview new-code coverage locally with `scripts/new_code_coverage.py`. Details: [`dev-docs/CONTRIBUTING.md`](dev-docs/CONTRIBUTING.md). Storage/CI review: [`GITHUB_ACTIONS_CI_CD_REVIEW_AND_STORAGE.md`](dev-docs/plans/supporting/GITHUB_ACTIONS_CI_CD_REVIEW_AND_STORAGE.md).

## View and display (agent-relevant defaults)

- **Image smoothing:** on by default for new or missing configs; View menu + context menu; persisted. During zoom/pan the image uses fast scaling, then smooths after a short idle delay.
- **Panes / navigator:** View menu + context menu; **N** toggles series navigator.
- **Multi-window:** 1×1 focused; 1×2 / 2×1 by row/column; double-click expand/revert; **Swap** in 2×2 only.
