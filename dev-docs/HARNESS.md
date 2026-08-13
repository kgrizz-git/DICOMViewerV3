# Agent harness

**Last updated:** 2026-08-13
**Reference:** [OpenAI — Harness engineering](https://openai.com/index/harness-engineering/) (environment design, progressive disclosure, mechanical checks).

This project uses a **human-led, agent-assisted** workflow—not a fully agent-generated codebase. The harness below makes repository knowledge legible and verifiable for Cursor/Codex-style agents.

---

## Layer 1 — Table of contents (`AGENTS.md`)

[`AGENTS.md`](../AGENTS.md) stays short (~100 lines): venv, run/test, orchestration, links. **Do not** paste the full `src/` tree into `AGENTS.md`; use [`ARCHITECTURE.md`](../ARCHITECTURE.md) and [`SOURCE_LAYOUT.md`](SOURCE_LAYOUT.md).

---

## Layer 2 — Architecture map

| File | Role |
|------|------|
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Domains, dependency rules, “where to change what” |
| [`SOURCE_LAYOUT.md`](SOURCE_LAYOUT.md) | Full `src/` tree, controllers, init order, signal wiring |
| [`DESIGN.md`](../DESIGN.md) | UI tokens and interaction spec |
| [`dev-docs/README.md`](README.md) | Index of developer documentation |
| [`dev-docs/plans/`](plans/) | Active, supporting, and completed implementation plans |
| [`dev-docs/TO_DO.md`](TO_DO.md) | Active product/engineering backlog |
| [`dev-docs/MAINTENANCE_LOG.md`](MAINTENANCE_LOG.md) | Developer-maintenance history for CI, harness, repo hygiene, and similar work |

### Change routing and focused verification

Use [`ARCHITECTURE.md`](../ARCHITECTURE.md#where-to-change-what) to identify
the owning code first, then run the smallest relevant verification slice from
the canonical commands in [`tests/README.md`](../tests/README.md#focused-test-selection)
before the full suite. The table below is a navigation aid, not a replacement
for full regression after cross-cutting changes.

| Change area | Start with | Focused verification |
|---|---|---|
| Main-window actions, shortcuts, or signal wiring | `src/main.py`, `src/main_app_*.py`, `src/gui/main_window_menu_builder.py` | `tests/test_main_signal_wiring.py`, `tests/test_main_signals_view.py`, then the relevant manual smoke step |
| Loading, parsing, or decoder behavior | `FileOperationsHandler`, loading pipeline, `dicom_loader.py`, `dicom_pixel_array.py` | `tests/test_dicom_loader.py`, `tests/test_dicom_parser.py`; run decoder fixture smoke after decoder or frozen-build changes |
| Navigator, overlays, or keyboard handling | `src/gui/series_navigator_*`, `overlay_config`, `KeyboardEventHandler` | `tests/test_series_navigator_tooltips.py`, `tests/test_keyboard_overlay_shortcuts.py`; smoke Space on normal and MPR panes |
| MPR, geometry, or export | `src/core/mpr_controller.py`, `mpr_*` modules | `tests/test_mpr_core.py`, `tests/test_mpr_geometry.py`, `tests/test_mpr_overlay_and_rescale.py`, plus MPR manual smoke when UI-visible |
| Privacy display, storage, or output | `privacy_controller.py`, `src/utils/privacy/` | targeted `tests/test_privacy_*.py`, `tests/test_main_privacy_lifecycle.py`, and the required privacy hook lane |
| Study index, SR/RDSR, or QA/pylinac | `src/core/study_index/`, `rdsr_dose_sr.py`, `src/qa/` | corresponding `tests/test_study_index_*.py`, `tests/test_rdsr_*.py`, or `tests/test_pylinac_*.py`; use optional deep smoke when behavior is UI-visible |

### Search and indexing hygiene

- Use **ripgrep** (`rg`) for scoped repository search. It is a developer/agent
  workstation tool, not an application dependency; install it through platform
  package management (for example, `brew install ripgrep`), never this
  project's Python environment. If it is unavailable, use `find` plus the
  platform's available text-search tool.
- `.cursorindexingignore` excludes local data, runtime state, generated Python
  bytecode, local Codex state, and other non-source artifacts from Cursor
  indexing. Keep it aligned with `.cursorignore` when adding a new local-only
  root. These exclusions do not change application behavior or replace the
  repository's privacy gates.
- Add nested `AGENTS.md` guidance only where a subtree has durable rules that
  differ from the root guidance. Keep it narrowly scoped to invariants,
  entry points, and verification; do not duplicate the root architecture map.

### Agent-tool trial protocol

Before adopting an MCP server or output-compression hook, run a small,
non-gating trial on three to five representative tasks. Establish a no-tool
baseline, then enable one tool at a time. Record task completion, focused-test
result, elapsed time, and any lost traceback or source detail. Retain a tool
only when it preserves correctness and makes this repository's workflow
materially better. Keep a raw-output path for every output filter.

---

## Layer 3 — Mechanical checks (CI + local)

| Script | What it validates |
|--------|-------------------|
| [`scripts/check_user_docs_links.py`](../scripts/check_user_docs_links.py) | Relative links in `user-docs/` and `dev-docs/README.md` |
| [`scripts/check_repo_harness.py`](../scripts/check_repo_harness.py) | Harness files present, `AGENTS.md` not bloated, `TO_DO.md` freshness, plan paths in `TO_DO.md`, links in harness docs, required **user-docs** topic guides linked from `USER_GUIDE.md` hub |
| [`scripts/check_architecture_boundaries.py`](../scripts/check_architecture_boundaries.py) | AST import-boundary checks for the highest-risk edges in `ARCHITECTURE.md`; existing legacy edges are listed in [`architecture_boundary_baseline.txt`](architecture_boundary_baseline.txt) |
| [`scripts/agent_smoke_harness.py`](../scripts/agent_smoke_harness.py) | Python path, core imports, committed DICOM fixture read; optional Qt headless smoke |
| [`scripts/check_doc_feature_coverage.py`](../scripts/check_doc_feature_coverage.py) | Report-only: maps `QAction` labels in `src/` to mentions in `user-docs/` and lists candidate documentation gaps (heuristic; exit 0 unless `--fail-under RATIO`) |

**CI:** [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

**Pytest:** `tests/test_user_docs_links.py`, `tests/test_repo_harness.py`, `tests/test_architecture_boundaries.py`, `tests/test_agent_smoke_harness.py`, `tests/test_doc_feature_coverage.py`.

**Doc garden:** `python scripts/check_repo_harness.py --doc-garden` prints a non-blocking report for stale harness dates, open TO_DO count, and duplicate `[Unreleased]` changelog headings. Treat it as a triage aid, not a merge gate.

**Feature → doc coverage:** `python scripts/check_doc_feature_coverage.py` lists menu/`QAction` labels not yet mentioned anywhere under `user-docs/` — a heuristic worklist for the documentation audit (some labels are trivial or documented under different wording). Add `--show-covered` to see what is matched, or `--fail-under 0.5` to gate in CI.

**Tracking split / plan archive:** keep [`TO_DO.md`](TO_DO.md) limited to active and near-term backlog items. Remove fully completed rows after the outcome is captured in the right durable place: [`../CHANGELOG.md`](../CHANGELOG.md) for user-visible release changes, [`MAINTENANCE_LOG.md`](MAINTENANCE_LOG.md) for CI / harness / static-analysis / dependency-verification / repo-maintenance history, and `plans/completed/`, `plans/supporting/`, `info/`, or `bug-investigations/` for detailed implementation or investigation records. Move finished implementation plans to `plans/completed/`; leave plans in `plans/supporting/` only when they remain active as dependencies, reference material, or future-scope support for open backlog work.

**Doc dates:** keep `**Last updated:**` dates on living guidance documents when the edit changes policy, workflow, user-facing behavior, or canonical instructions. Do not bump dates for typo-only edits. Completed plans, one-off investigations, changelogs, and dated maintenance-log entries do not need separate date churn unless they already use a living-document date.

---

## Debugging (console traces)

All optional diagnostic **`print`** paths are gated by **`DEBUG_*`** constants in **[`src/utils/debug_flags.py`](../src/utils/debug_flags.py)** (not environment variables). Open that file first when investigating layout, loading, W/L, fusion, MPR, 3D volume, pylinac, or navigation issues — each flag lists the modules it affects.

- Set the relevant flag to **`True`** locally, reproduce, then set back to **`False`** before commit.
- CI workflow **debug-flags-check** (see [`.github/workflows/privacy-gates.yml`](../.github/workflows/privacy-gates.yml)) rejects any `DEBUG_*: bool = True` in that file.
- Human policy: [`CONTRIBUTING.md`](CONTRIBUTING.md) (debug flags section).

Agents: also listed in [`AGENTS.md`](../AGENTS.md) repository map and conventions.

---

## Layer 4 — Agent runtime smoke

For UI or integration validation after changes:

1. Activate venv: `.\.venv\Scripts\Activate.ps1` (Windows) or `source .venv/bin/activate`.
2. Run automated smoke: `python scripts/agent_smoke_harness.py --write-report`
3. Optional Qt import smoke: `python scripts/agent_smoke_harness.py --qt-smoke`
4. Launch app: `python src/main.py` or `launch.bat` → option 1.
5. Manual checklist: [`orchestration/AGENT_SMOKE.md`](orchestration/AGENT_SMOKE.md)
6. Full regression: `python -m pytest tests/ -v` (~40s on a many-core host;
   `pytest.ini` sets `-n auto`, so this parallelizes automatically. Add `-n 0`
   to force a serial run, which takes ~8m40s).

**Decoder fixture smoke** (after decoder or PyInstaller changes):

```bash
python src/main.py --decoder-fixture-smoke tests/fixtures/dicom_decoder
```

Frozen executables use the same flag. The runner decodes nine reviewed synthetic fixtures, checks pixel hashes, and (for the 12-bit JPEG Extended fixture) asserts the exact allowlisted GDCM native diagnostic on stderr. Output is JSON with handler versions only — no file paths or PHI. See also `scripts/report_gdcm_bundle_inventory.py` for release SBOM evidence.

Agents with browser MCP can drive the running app per project UX skills; logs and version come from `src/version.py` and test output.

---

## Layer 5 — Focused verification

Default to one agent and the verification commands above. For a materially
high-risk change, one focused independent review may be useful, but no
project-local planner/coder/tester/orchestrator role chain is required or
maintained.

Skill: [`.claude/skills/agent-smoke-harness/SKILL.md`](../.claude/skills/agent-smoke-harness/SKILL.md).

---

## Maintaining the harness

When you add a major domain or change bootstrap/signal rules:

1. Update [`ARCHITECTURE.md`](../ARCHITECTURE.md) (domains / where-to-change).
2. Update [`SOURCE_LAYOUT.md`](SOURCE_LAYOUT.md) if files or wiring moved.
3. Bump **Last updated** on edited harness docs when the edit changes policy, workflow, user-facing behavior, or canonical guidance; skip date churn for typo-only edits.
4. Run `python scripts/check_repo_harness.py` and `python scripts/check_architecture_boundaries.py`; fix new failures before merge.
5. When a baseline violation is intentionally refactored away, run `python scripts/check_architecture_boundaries.py --refresh-baseline` and review the removed line.

Future improvements (not required today): autonomous doc-gardening bot, per-worktree launch script with observability hooks.
