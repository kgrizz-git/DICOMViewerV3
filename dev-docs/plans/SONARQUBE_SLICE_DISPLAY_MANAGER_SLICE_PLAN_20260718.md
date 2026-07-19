# Plan: Slice Display Manager Sonar Slice

**Last updated:** 2026-07-18
**Status:** Implemented
**Baseline:** post ROI-coordinator stats slice; scoped reporter **461**
active priority findings (349 CRITICAL, 112 MAJOR). `python:S3776` = 282.
**Post-fix analysis:** scoped reporter **454** active priority findings
(344 CRITICAL, 110 MAJOR). `python:S3776` 282 → 277; five targeted
`slice_display_manager` findings closed (two incidental MAJOR also cleared).
**Predecessor:**
[`SONARQUBE_ROI_COORDINATOR_STATS_SLICE_PLAN_20260718.md`](SONARQUBE_ROI_COORDINATOR_STATS_SLICE_PLAN_20260718.md)

## Goal

Reduce cognitive complexity on the remaining CRITICAL methods in
`src/gui/slice_display_manager.py` by extracting focused private helpers,
preserving public APIs and user-visible display / ROI / series-navigation
behavior.

## In-scope findings (`python:S3776`)

| Method | Approx line |
|--------|-------------|
| `_render_base_image_pipeline` | 466 |
| `_sync_controls_and_metadata` | 609 |
| `_render_scene_overlays_annotations` | 730 |
| `display_rois_for_slice` | 1004 |
| `handle_series_navigation` | 1216 |

Expected Sonar delta: about **−5 CRITICAL** (461 → ~456). Achieved: **454**
(−7 priority; −5 `S3776` plus −2 incidental MAJOR).

## Out of scope

- Remaining MAJOR smells in this file (`S107`, `S1066`, `S125`)
- `view_state_manager.py`, MPR/fusion controllers, loading pipeline
- Behavior changes to W/L, fusion, projection, overlays, or series sort order

## Implementation checklist

- [x] Add `tests/gui/test_slice_display_manager_sonar_slice.py` (pipeline, ROI,
      series-nav contracts)
- [x] Extract helpers in the five S3776 methods; preserve behavior
- [x] Verify focused tests, smoke, harness, fresh Sonar report; update
      MAINTENANCE_LOG / CHANGELOG / TO_DO; mark Implemented
