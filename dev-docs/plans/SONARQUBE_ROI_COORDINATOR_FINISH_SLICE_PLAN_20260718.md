# Plan: ROI Coordinator Sonar S3776 Finish Slice

**Last updated:** 2026-07-18
**Status:** Implemented
**Baseline:** post MPR finish slice; scoped reporter **299** priority findings.
**Post-fix analysis:** scoped reporter **295** active priority findings.
`roi_coordinator` `python:S3776` → **0** (four remaining methods cleared).
**Predecessor:** [ROI coordinator stats slice](SONARQUBE_ROI_COORDINATOR_STATS_SLICE_PLAN_20260718.md)
  (stats-path `S3776` cleared; drawing/delete/selection deferred).

## Goal

Clear the four remaining CRITICAL `python:S3776` findings in
`src/gui/roi_coordinator.py` by extracting focused private helpers, preserving
ROI draw-finish, delete, delete-all, and scene-selection behavior.

## In-scope findings (`python:S3776`)

| Method | Status |
|--------|--------|
| `handle_roi_drawing_finished` | Cleared |
| `delete_all_rois_current_slice` | Cleared |
| `handle_roi_delete_requested` | Cleared |
| `handle_scene_selection_changed` | Cleared |

Expected Sonar delta: about **−4 CRITICAL** (299 → ~295). Achieved: **295**.

## Out of scope

- `fusion_coordinator` clusters (next domain)
- Behavior changes to undo semantics, auto-W/L, or ROI persistence

## Approach

1. Extend characterization coverage under `tests/gui/` for the four methods
   (auto-W/L success/error, normal draw + undo, delete with/without undo,
   delete-all composite, scene selection vs overlay-position refresh).
2. Extract private helpers until each orchestrator is under the Sonar threshold.
3. Focused tests + local Sonar rescan; update CHANGELOG / MAINTENANCE_LOG /
   TO_DO; mark Implemented.

## Suggested helper splits

- **`handle_roi_drawing_finished`:** resolve slice IDs; auto-W/L path;
  restore pan mode; normal undo-add + select/stats.
- **`handle_roi_delete_requested`:** prepare delete (handles/IDs); execute
  remove command or fallback; post-delete list/stats sync.
- **`delete_all_rois_current_slice`:** collect ROIs/crosshairs; build
  composite remove commands; fallback clear; refresh panels.
- **`handle_scene_selection_changed`:** sync selection to list/stats/handles;
  refresh overlay positions when deselected.

## Implementation checklist

- [x] Add/extend characterization tests for the four methods
- [x] Extract helpers; preserve behavior
- [x] Verify focused tests, fresh Sonar; update MAINTENANCE_LOG / CHANGELOG /
      TO_DO; mark Implemented
