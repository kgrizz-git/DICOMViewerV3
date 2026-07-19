# Plan: MPR Controller Sonar S3776 Slice

**Last updated:** 2026-07-18
**Status:** Implemented
**Baseline:** post S1192 finish; scoped reporter **308** priority findings.
**Post-fix analysis:** scoped reporter **303** active priority findings.
Five targeted `mpr_controller` `S3776` findings closed (9 → 4 remaining
out-of-scope methods in the same file).
**Predecessor:** S108/S1192 mechanical cleanup on `feat/sonar-dotenv-loading`.

## Goal

Reduce cognitive complexity on five CRITICAL methods in
`src/gui/mpr_controller.py` by extracting focused private helpers,
preserving MPR display/lifecycle behavior.

## In-scope findings (`python:S3776`)

| Method | Status |
|--------|--------|
| `display_mpr_slice` | Cleared |
| `_activate_mpr` | Cleared |
| `_tear_down_mpr_at_subwindow` | Cleared |
| `_install_mpr_payload_at_subwindow` | Cleared |
| `_build_overlay_dataset` | Cleared |

Expected Sonar delta: about **−5 CRITICAL** (308 → ~303). Achieved: **303**.

## Out of scope (remaining in file)

- `prompt_save_mpr_as_dicom`
- `attach_floating_mpr`
- `_on_mpr_requested`
- `_reset_window_level_for_mpr`
- `roi_manager` / `fusion_coordinator` (later slices)

## Implementation checklist

- [x] Add `tests/gui/test_mpr_controller_sonar_slice.py`
- [x] Extract helpers in the five methods; preserve behavior
- [x] Verify focused tests, fresh Sonar; update MAINTENANCE_LOG / CHANGELOG /
      TO_DO; mark Implemented
