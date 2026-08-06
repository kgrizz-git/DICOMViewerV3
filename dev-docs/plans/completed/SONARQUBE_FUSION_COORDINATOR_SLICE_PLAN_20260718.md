# Plan: Fusion Coordinator Sonar S3776 First Slice

**Last updated:** 2026-07-18
**Status:** Implemented
**Baseline:** post ROI finish slice; scoped reporter **295** priority findings.
**Post-fix analysis:** scoped reporter **290** active priority findings.
Five targeted `fusion_coordinator` `S3776` cleared; three remaining deferred.
**Predecessor:** [ROI coordinator finish slice](SONARQUBE_ROI_COORDINATOR_FINISH_SLICE_PLAN_20260718.md)

## Goal

Clear five mid-size CRITICAL `python:S3776` findings in
`src/gui/fusion_coordinator.py` by extracting focused private helpers,
preserving fusion enable / UI sync / resampling-status / auto-detect behavior.

## In-scope findings (`python:S3776`)

| Method | Status |
|--------|--------|
| `handle_fusion_enabled_changed` | Cleared |
| `_update_base_display` | Cleared |
| `sync_ui_from_handler_state` | Cleared |
| `_update_resampling_status` | Cleared |
| `_auto_detect_fusion_candidates` | Cleared |

Expected Sonar delta: about **−5 CRITICAL** (295 → ~290). Achieved: **290**.

## Out of scope (finish slice later)

| Method | Why deferred |
|--------|--------------|
| `_finish_overlay_series_load` | Largest remaining |
| `get_fused_image` | Display-path; separate tests |
| `_update_spatial_alignment` | Large; already has dedicated tests |

## Implementation checklist

- [x] Add characterization tests for the five methods
- [x] Extract helpers; preserve behavior
- [x] Verify focused tests, fresh Sonar; update docs; mark Implemented
