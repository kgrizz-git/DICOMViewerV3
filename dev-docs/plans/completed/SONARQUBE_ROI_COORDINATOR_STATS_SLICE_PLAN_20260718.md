# Plan: ROI Coordinator Statistics-Path Sonar Slice

**Last updated:** 2026-07-18
**Status:** Implemented
**Baseline:** post undo/redo annotation-command slice; scoped reporter **464**
active priority findings (352 CRITICAL, 112 MAJOR).
**Post-fix analysis:** scoped reporter **461** active priority findings
(349 CRITICAL, 112 MAJOR). `python:S3776` 285 → 282; three targeted
`roi_coordinator` stats-path findings closed.
**Predecessor:**
[`SONARQUBE_UNDO_REDO_ANNOTATION_COMMANDS_SLICE_PLAN_20260718.md`](SONARQUBE_UNDO_REDO_ANNOTATION_COMMANDS_SLICE_PLAN_20260718.md)

## Goal

Reduce cognitive complexity on the shared ROI statistics path in
`src/gui/roi_coordinator.py` by extracting helpers and removing dead debug-only
code, without changing stats / projection / MPR behavior.

## In-scope findings (`python:S3776`)

| Method | Approx line |
|--------|-------------|
| `_get_pixel_array_for_statistics` | 141 |
| `update_roi_statistics` | 757 |
| `update_roi_statistics_overlays` | 918 |

Expected Sonar delta: about **−3 CRITICAL** (464 → ~461). Achieved: **461**.

## Out of scope

- Other `roi_coordinator` S3776 (drawing finish, delete-all, scene selection)
- `slice_display_manager` / `view_state_manager` / MPR / fusion controllers
- MAJOR-only sweeps, `S1192`, bundled fonts

## Implementation checklist

- [x] Add `tests/gui/test_roi_coordinator_statistics.py` (MPR, projection on/off,
      fallbacks, foreign ROI skip, overlay rebuild)
- [x] Extract `_resolve_projection_enabled`, `_build_projection_array_for_statistics`,
      `_roi_belongs_to_manager`, `_stats_spacing_and_rescale_params`,
      `_roi_identifier_for_slice`; strip dead `__closure__` debug / commented prints
- [x] Verify focused tests, smoke, harness, fresh Sonar report; update
      MAINTENANCE_LOG / CHANGELOG / TO_DO; mark Implemented
