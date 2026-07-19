# Plan: Second Slice — Undo/Redo Annotation Command Complexity

**Last updated:** 2026-07-18
**Status:** Implemented
**Baseline:** post first-slice local analysis; scoped reporter **472** active
priority findings (360 CRITICAL, 112 MAJOR). `python:S3776` = 293 open;
`python:S1192` = 67 open.
**Post-fix analysis:** local scanner after Phase 1–2; scoped reporter
returned **464** active priority findings (352 CRITICAL, 112 MAJOR).
`python:S3776` open count 293 → 285; `undo_redo.py` S3776 = 0 for the four
targeted add/remove command classes.
**Predecessor:**
[`SONARQUBE_CRITICAL_CODE_SMELL_FIRST_SLICE_PLAN_20260718.md`](SONARQUBE_CRITICAL_CODE_SMELL_FIRST_SLICE_PLAN_20260718.md)

## Goal

Continue the CRITICAL cognitive-complexity cleanup in the same behavior domain
as the first slice: extract shared add/remove helpers for the remaining
annotation undo/redo commands in `src/utils/undo_redo.py`, without changing
product behavior.

This is intentionally one file / one domain (~8 `python:S3776` findings), not a
dashboard-clearing pass.

## Why this slice

| Option | Why not now / why now |
|--------|------------------------|
| Remaining `undo_redo.py` S3776 (Measurement / Text / Arrow / Crosshair) | **Chosen.** Same extraction pattern as `ROICommand`; high reuse; easy to characterize with Qt scene tests; ~8 CRITICAL findings. |
| `bundled_fonts.py` S1192 (16) | Still deferred: data-definition string table, not worth reshaping for duplicate-literal scoring. |
| `mpr_controller.py` / `fusion_coordinator.py` S3776 | Larger controller flows; need deeper characterization; do after undo/redo domain is quiet. |
| Mechanical MAJOR (`S125` / `S1066` / `S1172`) | Valuable later as a separate “low-risk MAJOR sweep” plan; do not mix with CRITICAL complexity refactors. |

## In-scope findings

Open `python:S3776` on these methods (line numbers from the post-first-slice
report; may shift slightly after edits):

| Class | Methods |
|-------|---------|
| `MeasurementCommand` | `execute()`, `undo()` |
| `TextAnnotationCommand` | `execute()`, `undo()` |
| `ArrowAnnotationCommand` | `execute()`, `undo()` |
| `CrosshairCommand` | `execute()`, `undo()` |

Expected Sonar delta if successful: about **−8 CRITICAL** (472 → ~464), with
`undo_redo.py` S3776 count dropping from 8 to 0 for these add/remove commands.
Geometry/edit/move commands in the same file are **out of scope** unless a
helper extraction accidentally clears them.

## Out of scope

- All `python:S1192` duplicate-string findings (including bundled fonts).
- Remaining S3776 outside these four command classes (MPR, fusion, ROI manager,
  loading, view-state, etc.).
- All MAJOR findings (`S125`, `S1066`, `S1172`, `S107`, …).
- Behavior changes to measurement text refresh, handle visibility, or
  crosshair text `mark_deleted()` semantics.
- New complexity CI gates or quality-profile changes.

## Phase 1 — Characterize contracts with tests first

Add `tests/test_undo_redo_annotation_commands.py` (mirror
`tests/test_undo_redo_roi_commands.py`).

For each of Measurement / Text / Arrow / Crosshair:

- [x] **add → undo:** item is registered under the composite key, present in
      the scene after execute, absent from both after undo; no duplicates on a
      second execute.
- [x] **remove → undo → redo:** item leaves the manager + scene on remove;
      undo restores membership and scene attachment; redo removes again.
- [x] **Measurement-specific:** text item is added/removed with the
      measurement; `hide_handles()` runs on remove paths when present; undo of
      remove refreshes distance or angle geometry when those methods exist.
- [x] **Crosshair-specific:** linked text item is removed with
      `mark_deleted()` when that method exists; undo of remove reattaches the
      text item when still present on the crosshair.

Use lightweight fakes / real Qt graphics items as appropriate; prefer real
`QGraphicsScene` with `@pytest.mark.qt`. Do not invent production APIs.

## Phase 2 — Extract helpers, keep dispatch explicit

Modify only `src/utils/undo_redo.py`. Follow the `ROICommand` pattern:

- [x] `MeasurementCommand`: `_add_measurement_to_manager_and_scene() -> bool`,
      `_remove_measurement_from_manager_and_scene()`, keep execute/undo as thin
      action dispatch. Preserve text-item attach/detach and handle hiding.
- [x] `TextAnnotationCommand`: `_add_annotation_…` / `_remove_annotation_…`;
      preserve `_is_new_annotation = False` and `on_editing_finished = None` on
      add paths.
- [x] `ArrowAnnotationCommand`: same add/remove helper split.
- [x] `CrosshairCommand`: same split; preserve text-item `mark_deleted()` on
      remove and text reattach on undo-remove.

Constraints:

- No public API changes.
- No shared base-class mega-refactor across command types in this slice
  (keep per-class private helpers; a later slice may generalize if still useful).
- Backup `src/utils/undo_redo.py` under gitignored `backups/` before edits;
  delete the backup after verification.

## Phase 3 — Verify and close out

- [x] Run focused tests:
      `python -m pytest tests/test_undo_redo_annotation_commands.py tests/test_undo_redo_roi_commands.py tests/test_roi_delete_resize_handles.py tests/gui/test_measurement_move_tracking.py -v`
- [x] Run `python scripts/agent_smoke_harness.py`,
      `python scripts/check_architecture_boundaries.py`, and
      `python scripts/check_repo_harness.py`.
- [x] Submit fresh analysis: `python scripts/run_local_sonarqube.py`, then
      `python scripts/report_local_sonarqube_issues.py --expected-revision "$(git rev-parse HEAD)"`.
      Confirm the eight targeted S3776 findings are closed; record the new
      total without treating the absolute count as a hard fail.
- [x] Update `dev-docs/MAINTENANCE_LOG.md`, a brief `CHANGELOG.md` Unreleased
      patch note (maintainability only), and point `dev-docs/TO_DO.md` at the
      next deferred domain.
- [x] Mark this plan Implemented and leave a follow-up backlog item for either
      (a) next S3776 domain or (b) a separate MAJOR mechanical sweep.

## Suggested follow-up slices (not this plan)

1. **Next CRITICAL domain:** one controller file with a modest S3776 cluster
   and existing tests — candidate order after this plan:
   `roi_coordinator.py` → `slice_display_manager.py` → `view_state_manager.py`
   (avoid `mpr_controller` / `fusion_coordinator` until smaller wins land).
2. **MAJOR mechanical sweep:** `S125` commented-code removal + `S1066`
   collapsible-if collapses in one package at a time (start with
   `src/gui/dialogs/` or a single controller).
3. **S1192 dialogs only:** `annotation_options_dialog.py` +
   `overlay_config_dialog.py` string constants (still skip `bundled_fonts.py`).
