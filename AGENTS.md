---
description: 
alwaysApply: true
---

# Agent instructions – DICOM Viewer V3

**Last updated:** 2026-07-12

**Table of contents** for agents: operational facts here; architecture, module tree, and harness checks linked below (progressive disclosure per [harness engineering](https://openai.com/index/harness-engineering/)).

**Human contributors:** [`dev-docs/CONTRIBUTING.md`](dev-docs/CONTRIBUTING.md) · **Harness index:** [`dev-docs/HARNESS.md`](dev-docs/HARNESS.md)

## Virtual environment (venv)

**Always activate the project virtual environment before running tests or application code.**

The env folder may be named `venv`, `.venv`, `env`, or `virtualenv`. **`launch.bat`** picks the first that exists under the project root. Many setups use **`.venv`** next to `requirements.txt`.

On a typical Windows checkout (if search ignores hidden folders):

- PowerShell: `%USERPROFILE%\...\DICOMViewerV3\.venv\Scripts\Activate.ps1`
- Python: `%USERPROFILE%\...\DICOMViewerV3\.venv\Scripts\python.exe`

- **Windows (cmd):** `<dir>\Scripts\activate`
- **Windows (PowerShell):** `.\.venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source .venv/bin/activate`

From project root, after activation:

- Run the app: `python src/main.py`
- Run tests: `python tests/run_tests.py` or `python -m pytest tests/ -v` (**`tests/README.md`**)
- Agent smoke: `python scripts/agent_smoke_harness.py`
- Harness docs check: `python scripts/check_repo_harness.py`
- Architecture boundaries: `python scripts/check_architecture_boundaries.py`

If no venv exists: `python -m venv .venv`, activate, `pip install -r requirements.txt`.

**Cine export:** `requirements.txt` pins **`imageio`** + **`imageio-ffmpeg`** (FFmpeg license obligations for frozen builds). **`IMAGEIO_FFMPEG_EXE`** can override the wheel binary. Prefer **`.mp4`** on Windows 11 Media Player over **`.mpg`** without the MPEG-2 extension.

## Repository map (read next)

| Topic | Location |
|-------|----------|
| Domains, dependency rules, where to edit | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| Full `src/` tree, controllers, signal wiring | [`dev-docs/SOURCE_LAYOUT.md`](dev-docs/SOURCE_LAYOUT.md) |
| Backlog | [`dev-docs/TO_DO.md`](dev-docs/TO_DO.md) |
| Maintenance / developer history | [`dev-docs/MAINTENANCE_LOG.md`](dev-docs/MAINTENANCE_LOG.md) |
| Plans (active / supporting / completed) | [`dev-docs/plans/`](dev-docs/plans/) |
| Developer doc index | [`dev-docs/README.md`](dev-docs/README.md) |
| UI design spec | [`DESIGN.md`](DESIGN.md) |
| Manual agent smoke steps | [`dev-docs/orchestration/AGENT_SMOKE.md`](dev-docs/orchestration/AGENT_SMOKE.md) |
| Multi-agent state | [`plans/orchestration-state.md`](plans/orchestration-state.md) |
| **Debug / diagnostic prints** | [`src/utils/debug_flags.py`](src/utils/debug_flags.py) — all `DEBUG_*` toggles (default `False`) |

## Conventions (short)

- **Layout:** `src/` (app), `tests/`, `user-docs/`, `dev-docs/` (plans, assessments).
- **Local study index:** `src/core/study_index/` — plan: [`LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md`](dev-docs/plans/supporting/LOCAL_STUDY_DATABASE_AND_INDEXING_PLAN.md).
- **Pylinac:** exact pin in `requirements.txt`; bump via [`DEPENDENCY_BUMP_VERIFICATION_PLAN.md`](dev-docs/plans/completed/DEPENDENCY_BUMP_VERIFICATION_PLAN.md) and [`PYLINAC_INTEGRATION_OVERVIEW.md`](dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md).
- **Version / changelog / SemVer:** bump [`src/version.py`](src/version.py) and keep **Current version** in [`CHANGELOG.md`](CHANGELOG.md) in sync; follow [`dev-docs/RELEASING.md`](dev-docs/RELEASING.md) for release cuts and [`dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md`](dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md) for version increments.
- **Tracking split / plan archive:** [`dev-docs/TO_DO.md`](dev-docs/TO_DO.md) is the active backlog, not a completion log. Remove fully completed items once captured in [`CHANGELOG.md`](CHANGELOG.md), [`dev-docs/MAINTENANCE_LOG.md`](dev-docs/MAINTENANCE_LOG.md), or a durable plan/investigation record. Move finished implementation plans to [`dev-docs/plans/completed/`](dev-docs/plans/completed/); keep only ongoing dependency/reference plans in [`dev-docs/plans/supporting/`](dev-docs/plans/supporting/). Use `CHANGELOG.md` for user-visible release changes and `MAINTENANCE_LOG.md` for CI, harness, static-analysis, dependency-verification, and repo-maintenance history.
- **Doc dates:** when editing a document that already has a `**Last updated:**` line, update the date if the edit changes policy, workflow, user-facing behavior, or canonical guidance. Do not bump dates for typo-only edits.
- **Privacy hooks:** `scripts/git_hook_privacy_checks.py` on staged `src/*.py` — [`SECURITY_TOOLS_CLI_GUIDE.md`](dev-docs/SECURITY_TOOLS_CLI_GUIDE.md).
- **Debug flags:** Before adding `print` tracing, read [`src/utils/debug_flags.py`](src/utils/debug_flags.py) and gate behind an existing or new `DEBUG_*` constant (default **`False`**). Each flag documents which modules it affects. Revert flags to **`False`** before commit — CI **debug-flags-check** fails on any `True`. Do not use `DEBUG_AGENT_LOG` in release builds (writes `debug-088dbc.log`).
- **Long-running commands:** use ~10 minute timeouts for full `pytest` or `pyright src/`.

## Multi-agent orchestration

Subagents (`/orchestrator`, `/planner`, `/coder`, …) use the **Task** tool. Default **`CHAIN_MODE` is `autonomous`:** primary agent chains **`Task(orchestrator)`** after each specialist until **complete** / **blocked** / **`needs_user`**, unless [`plans/orchestration-state.md`](plans/orchestration-state.md) sets **`## Chain mode`** to **`step`**. See **`.cursor/rules/orchestration-auto-chain.mdc`** and **`.claude/skills/team-orchestration-delegation/SKILL.md`**. Orchestrator must end with **`NEXT_TASK_TOOL:`** / **`NEXT_TASK_TOOL_SECOND:`**. **`medium`/`high`** risk: batch **`tester`** at slice end; UX changes → manual smoke in [`AGENT_SMOKE.md`](dev-docs/orchestration/AGENT_SMOKE.md). Run packet: [`dev-docs/orchestration/RUN_PACKET_TEMPLATE.md`](dev-docs/orchestration/RUN_PACKET_TEMPLATE.md).

## Verification before claiming done

| Check | Command |
|-------|---------|
| Tests | `python -m pytest tests/ -v` |
| User-docs links | `python scripts/check_user_docs_links.py` |
| Repo harness | `python scripts/check_repo_harness.py` |
| Architecture boundaries | `python scripts/check_architecture_boundaries.py` |
| Agent smoke | `python scripts/agent_smoke_harness.py` |

After editing `user-docs/` or `dev-docs/README.md`, run the link checker (CI: **User docs links**).

## CI (summary)

Workflows on **main** / **develop**: tests, Semgrep, Grype, debug flags, user-docs links, repo harness. **SonarCloud** Automatic Analysis scope: [`.sonarcloud.properties`](.sonarcloud.properties) (`src/` sources, `tests/` tests). Details: [`dev-docs/CONTRIBUTING.md`](dev-docs/CONTRIBUTING.md). Storage/CI review: [`GITHUB_ACTIONS_CI_CD_REVIEW_AND_STORAGE.md`](dev-docs/plans/supporting/GITHUB_ACTIONS_CI_CD_REVIEW_AND_STORAGE.md).

## View and display (agent-relevant defaults)

- **Image smoothing:** off by default; View menu + context menu; persisted.
- **Panes / navigator:** View menu + context menu; **N** toggles series navigator.
- **Multi-window:** 1×1 focused; 1×2 / 2×1 by row/column; double-click expand/revert; **Swap** in 2×2 only.
