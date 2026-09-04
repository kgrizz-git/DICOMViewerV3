# Plan: Raise Test Coverage (local SonarQube baseline)

**Last updated:** 2026-08-03  
**Status:** Active — Phases 1–4 complete; Phase 5 partial + deferred-dialog/high-miss slices; local Sonar remeasured (+7–8 pp line vs baseline). Hardened
with explicit agent rules + recipes so a less-capable model can execute safely.  
**Branch:** `test/coverage-boost` (at `origin/main`)  
**Source analysis:** `2026-08-01T03:04:41+0000`, revision
`85366265af53ed23f1a79c6f2fc251c31c87be60`  
**Dashboard:** `http://localhost:9000/dashboard?id=dicom-viewer-v3`

---

## ⛔ RULES FOR THE IMPLEMENTING AGENT — READ THIS FIRST

This section is authoritative. If anything below in the plan seems to conflict
with these rules, **these rules win.** Do exactly what is written; do not
improvise around it. If you cannot follow a rule, **stop and leave a note in
"Progress notes"** instead of working around it.

### Hard rules — NEVER do these

1. **NEVER edit files under `src/` — this branch is strictly tests-only.**
   Do not edit `src/` to make a test pass, to make a line "coverable," to
   "extract a pure helper," or to fix a bug you notice. The only files you may
   create or edit are under `tests/` (plus this plan's Progress notes). If a real
   product bug blocks a test, write the test as
   `@pytest.mark.xfail(reason="...", strict=False)` and record it in Progress
   notes — do **not** patch `src/`. **Extractions/refactors are explicitly
   forbidden on this branch** and require separate owner approval on a separate
   branch; wherever later phases mention "extract helpers," cover the code
   through its existing public API / events instead. (This overrides Phase 5 and
   the Non-goals note.)
2. **NEVER weaken, delete, `skip`, or `xfail` an *existing* test** to get green.
   Existing tests must keep passing untouched.
3. **NEVER assert something just to raise the number.** Every test must assert a
   real, meaningful outcome (a returned value, a widget field, a signal, a saved
   file's contents via a mock). A test with no `assert` (or only
   `assert dlg is not None`) is not acceptable.
4. **NEVER put real patient data in a test.** No real DICOM, no PHI/PII, no real
   file paths from a scanner. Use only existing fixtures under `tests/` or
   synthetic data you build in-test. See
   [`PHI_PII_REPOSITORY_GUARDRAILS.md`](../PHI_PII_REPOSITORY_GUARDRAILS.md).
5. **NEVER commit with a personal email, and NEVER change git config.** Commits
   must use the GitHub noreply author already configured on this machine:
   `216068303+kgrizz-git@users.noreply.github.com`. Checkpoint commits on
   `test/coverage-boost` are allowed after each module passes the Definition of
   Done (owner-approved 2026-07-31). **Do not `git push`** unless the owner asks.
6. **NEVER boot the full `MainWindow`** to test a single dialog or tool.
   Construct the one class under test with mocks/fakes for its dependencies.

### Always do these

7. **Mirror an existing test file.** Copy the structure of a real neighbor —
   e.g. [`tests/gui/test_annotation_options_dialog.py`](../../tests/gui/test_annotation_options_dialog.py)
   or [`tests/gui/test_overlay_config_dialog.py`](../../tests/gui/test_overlay_config_dialog.py).
   Use the same imports, the `qapp` fixture, and the `@pytest.mark.qt` marker.
8. **One new test file per source module.** Name it
   `tests/gui/test_<module>.py` (or `tests/<pkg>/test_<module>.py` matching the
   source package). Do not append to unrelated existing files. Even where a
   later phase says "extend existing X tests," create a **new** file
   `tests/<pkg>/test_<module>_<slice>.py` rather than editing the existing one.
9. **Run your new tests and confirm they pass before committing** (see Recipes).
10. **Do one module per commit.** Small, reviewable commits. Do not batch ten
    modules into one PR.
11. **If you get stuck on a module after a reasonable attempt, SKIP IT.** Add a
    line to Progress notes ("skipped X: reason") and move to the next module.
    Never force a module through by breaking rules 1–4.

### Ground truth about this repo's test setup (verified)

- Tests import from the package root, e.g. `from gui.dialogs.foo import FooDialog`
  (`tests/conftest.py` puts `src/` on `sys.path` automatically — do **not** add
  `sys.path` hacks).
- The Qt fixture is **`qapp`** (session-scoped, defined in `tests/conftest.py`).
  **There is no `qtbot`/`pytest-qt`** — anywhere this plan said "qtbot", use
  `qapp`. Get widgets/signals from the object you constructed, not from `qtbot`.
- Qt tests must run headless: set env `QT_QPA_PLATFORM=offscreen`.
- Mark every Qt-touching test with `@pytest.mark.qt`.

### Copy-paste recipes (run from repo root)

```bash
# 0. ALWAYS activate the venv first (per AGENTS.md). Usually .venv:
source .venv/bin/activate

# 1. Run ONE new test file (headless Qt), verbose:
QT_QPA_PLATFORM=offscreen python -m pytest tests/gui/test_<module>.py -v

# 2. Run the whole suite before committing (must stay green; ~3 min):
QT_QPA_PLATFORM=offscreen python -m pytest tests -q

# 3. Lint your new test files (must be clean):
ruff check tests/gui/test_<module>.py

# 4. Confirm no PHI / privacy-gate violations in what you added:
python scripts/check_no_phi_artifacts.py

# 5. Re-measure coverage — this is HEAVY; run once per PHASE (or every ~5
#    modules), NOT after every module. Steps 1–4 run after every module.
python scripts/run_local_sonarqube.py --with-coverage
```

**Interactive widgets (mouse/drag/key handlers):** the skeleton below covers
construct-and-assert dialogs. For widgets that need synthesized input events
(`QMouseEvent` / `QKeyEvent`) — e.g. `transfer_function_editor_widget.py`,
`histogram_widget.py` — mirror an existing example that already does this:
[`tests/gui/test_series_navigator_view.py`](../../tests/gui/test_series_navigator_view.py)
or [`tests/gui/test_image_viewer_context_menu.py`](../../tests/gui/test_image_viewer_context_menu.py).
Do not invent an event-injection pattern; copy one of those.

### Copy-paste test skeleton (adapt names; keep the shape)

```python
"""Tests for <ModuleName>: <what behavior these tests characterize>."""

from __future__ import annotations

import pytest

from gui.dialogs.<module> import <DialogClass>


@pytest.mark.qt
def test_<behavior_being_verified>(qapp) -> None:
    dlg = <DialogClass>(<mocked deps>)      # construct with fakes, not MainWindow
    # exercise ONE behavior:
    result = dlg.some_method()
    # assert a REAL outcome (value / widget field / call on a mock):
    assert result == <expected>
```

> A test file that only constructs the object and asserts it is not `None`
> raises coverage but is **rejected** by rule 3. Assert observable behavior.

---

## Goal

Raise meaningful line and branch coverage on `src/` with focused, maintainable
tests. Prefer **easy, high-yield** modules first, then **high-risk / low-coverage**
logic (load, export, tools). Do not chase entrypoint/`main.py` UI wiring until
the cheaper slices are done.

This plan is coverage-first. Sonar code-smell remediation (`S3776`, etc.) stays
on the existing Sonar slice backlog unless a coverage test naturally
characterizes a method before extraction.

## Baseline (this revision)

| Metric | Value |
|--------|------:|
| Sonar **coverage** (line+branch blend) | **56.6%** |
| Sonar **line coverage** | **60.5%** |
| Sonar **branch coverage** | **44.7%** |
| Uncovered lines / lines to cover | 20,223 / 51,193 |
| Uncovered conditions / conditions to cover | 9,114 / 16,478 |
| pytest-cov `coverage.xml` line rate | **61.7%** (30,970 / 50,197) |
| pytest-cov branch rate | **44.7%** (7,364 / 16,478) |
| Open issues | 1 BUG, 0 VULN, 308 CODE_SMELL (243 in scoped reporter) |
| Suite | 3,275 passed, 19 skipped |

**Coverage.xml vs Sonar gap:** Sonar reports `src/main.py` at **0% / 996
uncovered lines**; that file is **absent from** `.sonar-local/coverage.xml`
because pytest never imports the entrypoint. Treating `main.py` as a late-phase
or exclusion decision (see Phase 0) avoids a false “largest file” priority.

### Package picture (from coverage.xml)

| Area | Approx. line cov | Uncovered lines (order of) | Notes |
|------|-----------------:|---------------------------:|-------|
| `src/gui/dialogs/` | ~44% | ~4,900 | Largest easy pool; many dialogs &lt;25% |
| `src/tools/` | ~42% | ~2,200 | Interaction-heavy but unit-testable with fakes |
| `src/gui/` (non-dialog) | ~57% | large | Controllers/viewers; harder |
| `src/core/` | ~81% | ~2,300 | Already strong; remaining gaps are high value |
| `src/qa/` | ~69% | ~400 | ACR MRI / PDF helpers thin |
| `src/utils/` | ~78%+ | smaller | Keep opportunistically |

### Working targets (proposed)

| Milestone | Sonar line cov | Notes |
|-----------|---------------:|-------|
| M1 — dialog/widget smoke | ~63–65% | Phases 1–2 |
| M2 — tools + export paths | ~66–68% | Phase 3 |
| M3 — core remaining + selected GUI | ~70% | Phase 4; stretch |
| Branch cov | +3–5 pts each milestone | Assert error/edge branches, not only happy paths |

Re-measure after each phase with:

```bash
python scripts/run_local_sonarqube.py --with-coverage
python scripts/report_local_sonarqube_issues.py \
  --expected-revision "$(git rev-parse HEAD)"
```

---

## Phase 0 — Guardrails and measurement hygiene

- [ ] Keep tests PHI-safe: no real DICOM/PII; use existing fixtures / synthetic
      datasets only ([`PHI_PII_REPOSITORY_GUARDRAILS.md`](../PHI_PII_REPOSITORY_GUARDRAILS.md)).
- [ ] Prefer thin Qt dialogs constructed with the `qapp` fixture + mocks over
      full `MainWindow` boots (there is **no** `qtbot` in this repo — see Rules).
- [ ] **`src/main.py` policy — default: option B (tests-only), but expect
      little.** The entrypoint reads 0% because pytest never imports it.
      **Do not `import main` under pytest** — that pulls in `MainWindow` and the
      full heavy stack. The only cheap tests-only seam is the **module-level
      early-exit** for the decoder-fixture flags (`--decoder-fixture-smoke` /
      `--decoder-fixture-child`, near the top of `main.py`), best exercised with
      a **subprocess** call, not a direct import. This will **not** clear
      Sonar's ~996 uncovered `main.py` lines — so when scoring milestones,
      mentally set `main.py` aside entirely. **Do NOT do option A here**
      (excluding `**/main.py` edits `tools/sonarqube/sonar-project.properties`,
      forbidden on this tests-only branch — Rule 1); option A is a **separate
      chore PR** if the owner wants it.
- [ ] After each merged slice on this branch, refresh local Sonar with
      `--with-coverage` and record line/branch % in this plan’s progress notes.

---

## Per-module Definition of Done (apply to EVERY checklist item below)

Before ticking a box or committing a module, all of these must be true:

- [ ] New file `tests/<pkg>/test_<module>.py` or
      `tests/<pkg>/test_<module>_<slice>.py` exists and mirrors a neighbor.
- [ ] Every test asserts a real outcome (rule 3) — no bare construction tests.
- [ ] No `src/` file was modified (rule 1). `git diff --name-only` shows only
      `tests/` (and this plan).
- [ ] `QT_QPA_PLATFORM=offscreen python -m pytest tests/<pkg>/test_<module>.py -v`
      passes.
- [ ] `QT_QPA_PLATFORM=offscreen python -m pytest tests -q` still fully passes
      (no existing test regressed).
- [ ] `ruff check tests/<pkg>/test_<module>.py` is clean.
- [ ] `python scripts/check_no_phi_artifacts.py` passes.
- [ ] Committed alone, with the noreply author email (rule 5).

---

## Phase 1 — Easiest wins (small / near-zero dialogs & widgets)

**Why first:** low coupling, fast to write, large relative gain per hour.  
**Expected yield:** on the order of **~800–1,200** newly covered lines if smoke
tests hit construct → populate → accept/reject / key handlers.

- [x] `src/gui/dialogs/keyboard_shortcuts_dialog.py` — **0%**, ~39 lines  
- [x] `src/gui/transfer_function_editor_widget.py` — **0%**, ~118 lines  
- [x] `src/gui/dialogs/about_this_file_dialog.py` — ~8%, ~108 miss  
- [x] `src/gui/dialogs/mri_compare_result_dialog.py` — ~8%, ~73 miss  
- [x] `src/gui/dialogs/disclaimer_dialog.py` — ~16%, ~63 miss  
- [x] `src/gui/dialogs/quick_window_level_dialog.py` — ~11%, ~48 miss  
- [x] `src/gui/dialogs/mpr_orientation_choice_dialog.py` — ~21%, ~31 miss  
- [x] `src/gui/dialogs/mpr_dicom_save_dialog.py` — ~22%, ~25 miss  
- [x] `src/gui/dialogs/study_index_passphrase_warning_dialog.py` — ~22%, ~36 miss  
- [x] `src/gui/dialogs/ct_batch_result_dialog.py` — ~14%, ~63 miss  
- [x] `src/gui/dialogs/acr_ct_qa_dialog.py` — ~12%, ~59 miss  
- [x] `src/gui/overlay_items_factory.py` — ~12%, ~29 miss (pure-ish factory)

**Test style:** one focused file per dialog/widget under `tests/gui/` (or
`tests/gui/dialogs/` if that package is introduced), mirroring existing
patterns such as `tests/gui/test_overlay_config_dialog.py` /
`test_annotation_options_dialog.py`.

**Done when:** each listed module is ≥60% line coverage **or** remaining
uncovered lines are documented as Qt paint/layout-only dead ends.

---

## Phase 2 — Most needed among easy/medium dialogs (export, privacy, settings)

**Why next:** still mostly dialog-shaped, but closer to user-facing export and
privacy surfaces where regressions hurt more.

Priority order (need × remaining miss):

- [x] `export_roi_statistics_dialog.py` (~9%, ~258 miss) — ties to ROI export
      services already well tested; wire dialog → facade with fakes  
- [x] `deep_anonymizer_export_dialog.py` (~10%, ~199 miss) — privacy-adjacent  
- [x] `edit_recent_list_dialog.py` (~9%, ~227 miss)  
- [x] `overlay_settings_dialog.py` (~8%, ~284 miss) — display defaults  
- [x] `screenshot_export_dialog.py` (~16%, ~338 miss)  
- [x] `cine_export_dialog.py` (~18%, ~76 miss)  
- [x] `file_dialog.py` (~13%, ~90 miss)  
- [x] `slice_sync_dialog.py` (~15%, ~82 miss)  
- [x] `wl_preset_manager_dialog.py` (~12%, ~130 miss)  
- [x] `histogram_dialog.py` (~14%, ~190 miss) — reuse
      `histogram_frequency` unit seams where possible  
- [x] `tag_edit_dialog.py` (~10%, ~123 miss)  
- [x] `radiation_dose_report_dialog.py` (~24%, ~75 miss)

**Defer within dialogs (harder / huge):** full `export_dialog.py`,
`structured_report_browser_dialog.py`, `study_index_search_dialog.py`,
`tag_export_dialog.py`, `fusion_technical_doc_dialog.py`,
`quick_start_guide_dialog.py` — cover via their existing public API only (no
`src/` extraction on this branch, Rule 1); if still below 40% after M1–M2,
either skip and note them or accept documentation-only dialogs as low priority.

**Done when:** Phase 2 list average ≥50% line coverage; export/privacy dialogs
have at least one cancel path and one successful-accept path with mocked I/O.

---

## Phase 3 — High-need tools & coordinators (behavior risk)

**Why:** measurement/ROI/crosshair bugs are user-visible; coverage is weak
(~12–35% on several large modules).

- [x] `src/tools/crosshair_manager.py` (~13%, ~225 miss)  
- [x] `src/tools/histogram_widget.py` (~14%, ~118 miss)  
- [x] `src/tools/text_annotation_tool.py` (~26%, ~208 miss)  
- [x] `src/tools/arrow_annotation_tool.py` (~45%, ~217 miss)  
- [x] `src/tools/angle_measurement_items.py` (~39%, ~214 miss)  
- [x] `src/tools/measurement_tool.py` (~12%, ~371 miss) — slice by public API;
      do not boil the ocean in one PR  
- [x] `src/tools/roi_manager.py` (~35%, ~331 miss) — add a **new**
      `tests/tools/test_roi_manager_<slice>.py` (do not edit existing ROI tests, Rule 8)  
- [x] Coordinators with low cov: `text_annotation_coordinator`,
      `crosshair_coordinator`, `arrow_annotation_coordinator`,
      `slice_location_line_coordinator`
- [ ] `layout_window_slot_controller` — **skipped** (needs `DICOMViewerApp` /
      `MainWindow`; Rule 6/11). See Progress notes.

**Done when:** each touched tool module gains ≥15 absolute percentage points
or clears its top public methods’ happy + one error path.

---

## Phase 4 — Most needed core gaps (already “green” packages, still risky)

Core is ~81% overall; remaining holes are still worth targeted tests:

- [x] `src/core/fusion_handler.py` (~30%, ~195 miss) — fusion match / FOV edges
      (pair with existing coverage-hint tests)  
- [x] `src/core/dicom_loader.py` (~35%, ~193 miss) — remaining branches beyond
      sonar-slice helpers  
- [x] `src/core/subwindow_lifecycle_controller.py` (~41%, ~304 miss)  
- [x] `src/qa/pylinac_acr_mri.py` / `pylinac_mri_pdf.py` — mock pylinac results;
      no real patient PDFs in-repo  
- [x] Opportunistic deferred dialogs/widgets: `structured_report_browser_dialog`, `export_dialog`,
      `tag_export` presets, `fusion_controls_widget`, `overlay_manager`, `window_slot_map_widget`,
      `export_rendering` / `export_manager` helpers, `series_navigator` behavior slice
- [ ] Opportunistic: `sr_document_tree`, `mpr_cache` / `mpr_volume` branches (existing coverage strong)

**Done when:** fusion_handler and dicom_loader ≥55% line coverage; lifecycle
controller has create/destroy/error characterization.

---

## Phase 5 — Hard GUI (largest misses; last)

Defer until Phases 1–4 pay off. These dominate uncovered-line rankings but need
heavier fixtures.

> **Tests-only reminder (Rule 1):** the "Approach" column below predates the
> tests-only rule. **Do NOT extract helpers or otherwise edit `src/`.** Cover
> these modules through their existing public methods and synthesized events
> only. If a module is genuinely untestable without a refactor, **skip it** and
> note it in Progress notes for a future owner-approved refactor branch.

| File | ~cov | ~miss | Approach (tests-only) |
|------|-----:|------:|----------|
| `image_viewer_input.py` | 16% | 551 | Drive existing public event handlers with synthesized `QMouseEvent`s; do **not** extract helpers |
| `qa_app_facade.py` | 16% | 454 | Facade method tests with fake QA workers |
| `main_window.py` | 56% | 425 | Only menu/action handlers with mocks; no full boot marathon |
| `series_navigator.py` | 26% | 393 | **Partial:** `test_series_navigator_behavior_slice.py` (privacy/list/MPR/keys) |
| `image_viewer_view.py` | 40% | 384 | View-state seams only |
| `annotation_paste_handler.py` | 24% | 333 | Clipboard fake + paste/undo |
| `mpr_controller.py` | 61% | 359 | Add tests only for its public methods; **ignore any `src/` extraction items** in older sonar-slice plans (Rule 1) |

**Explicitly out of scope for unit coverage:** full interactive drag/WL/cine
loops; rely on [`AGENT_SMOKE`](../orchestration/AGENT_SMOKE.md) for those.

---

## Suggested implementation order (first PRs on `test/coverage-boost`)

1. **PR-A (easiest):** Phase 1 keyboard / about / disclaimer / MPR choice /
   passphrase warning / transfer-function widget smoke.  
2. **PR-B (needed + still easy):** Phase 2 ROI-stats export, deep anonymizer
   export, edit-recent, overlay settings (mocked persistence).  
3. **PR-C (needed tools):** crosshair_manager + histogram_widget + one
   annotation tool.  
4. **PR-D (needed core):** fusion_handler FOV/match branches + dicom_loader
   remaining error paths.  
5. Reassess Sonar %; only then schedule Phase 5 slices.

## Non-goals

- Raising coverage by excluding large swaths of `src/` without documentation.
- **Editing production code at all on this branch** (see Rule 1). Extractions /
  refactors — even ones that would reduce complexity — belong on a separate,
  owner-approved branch, not here.
- Changing failing tests to force green (per project test rules).
- Uploading coverage or analysis outside the local SonarQube / approved
  main-only Cloud workflow.

## Progress notes

**Known deferred (do NOT fix on this branch — tests-only, Rule 1):**
- Open Sonar bug `python:S1226` (MINOR) in
  `src/gui/file_series_first_slice_load.py` (~L255): parameter `managers_0`
  reassigned without using its initial value. Belongs on a separate `src/` fix
  branch, not this coverage branch.

| Date | Revision | Sonar cov / line / branch | Notes |
|------|----------|---------------------------|-------|
| 2026-07-31 | `8536626` | 56.6% / 60.5% / 44.7% | Baseline on `test/coverage-boost` |
| 2026-08-01 | `f4fd55a` | (pending re-measure) | Phase 1 complete: 12 modules, 42 new tests; full suite 3317 passed |
| 2026-08-01 | `041389d` | (pending re-measure) | Phase 2 complete: 12 dialog modules; cancel+accept paths with mocks |
| 2026-08-01 | `31b9c87` | (pending re-measure) | Phase 3 tools+coordinators; skipped layout_window_slot_controller (needs app/MainWindow) |
| 2026-08-01 | (phase4) | (pending re-measure) | Phase 4 fusion/loader/lifecycle/MRI PDF+missing pylinac helpers |
| 2026-08-01 | HEAD | (pending re-measure) | Phase 3 Critical Rule-3 fixes; Phase 5 slices for qa_app_facade + annotation_paste; skipped layout_window_slot_controller, image_viewer_input, main_window, etc. |
| 2026-08-01 | `ccee720`/`60b478d` | — | Review fixes: TF paint asserts; remove dose export tautology |
| 2026-08-01 | post-final-review | (pending re-measure) | Addressed Important findings: lifecycle focused-index assert; split layout_window_slot_controller checklist; arrow scene/visibility; histogram Slice label; export browse-cancel no-I/O paths. Full suite 3415 passed at `b9576df`. Sonar re-measure still pending. |
| 2026-08-01 | `1f29082` | pytest-cov 63% (34,018 / 53,860) | Full re-measure: 3,418 passed, 19 skipped. Reaching 70% needs at least 3,684 additional covered statements before branch coverage; continue with high-yield behavior slices rather than superficial assertions. |
| 2026-08-02 | `2e4e689` | **64.0% / 68.5% / 50.3%** | Local Sonar `--with-coverage` after Phase5+deferred slices (window_slot_map, overlay_manager, SR browser, series_navigator, fusion_controls, export_dialog, export_rendering helpers, tag_export presets, export_manager). Baseline was 56.6/60.5/44.7 (+7.4 / +8.0 / +5.6 pp). Suite 3459+ passed. |
