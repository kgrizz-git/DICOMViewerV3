# Plan: MPR Controller Sonar S3776 Finish Slice

**Last updated:** 2026-07-18
**Status:** Implemented
**Baseline:** post first MPR slice; scoped reporter **303** priority findings.
**Post-fix analysis:** scoped reporter **299** active priority findings.
`mpr_controller` `python:S3776` → **0** (four remaining methods cleared).
**Predecessor:** [MPR controller slice](SONARQUBE_MPR_CONTROLLER_SLICE_PLAN_20260718.md)
  (five methods cleared; four remaining in-file).

## Goal

Clear the four remaining CRITICAL `python:S3776` findings in
`src/gui/mpr_controller.py` by extracting focused private helpers, preserving
MPR request / save / attach / W-L behavior.

## In-scope findings (`python:S3776`)

| Method | Status |
|--------|--------|
| `prompt_save_mpr_as_dicom` | Cleared |
| `attach_floating_mpr` | Cleared |
| `_on_mpr_requested` | Cleared |
| `_reset_window_level_for_mpr` | Cleared |

Expected Sonar delta: about **−4 CRITICAL** (303 → ~299). Achieved: **299**.

## Out of scope

- `roi_manager` / `fusion_coordinator` clusters (next domains)
- Behavior changes to dialogs, cache keys, or W/L defaults

## Approach

Same pattern as the first MPR slice:

1. Extend `tests/gui/test_mpr_controller_sonar_slice.py` with characterization
   coverage for the four methods (early exits, cache hit path, attach success /
   restore, W/L focused vs unfocused).
2. Extract private helpers until each orchestrator is under the Sonar threshold.
3. Focused tests + local Sonar rescan; update CHANGELOG / MAINTENANCE_LOG /
   TO_DO; mark Implemented.

## Suggested helper splits

- **`prompt_save_mpr_as_dicom`:** validate focused MPR + resolve template;
  pick output folder; run export with progress / messaging.
- **`attach_floating_mpr`:** focus destination; backup/clear existing MPR;
  install-or-restore with warning.
- **`_on_mpr_requested`:** cancel prior worker; resolve orientation groups /
  SliceLocation fallback; build volume; try cache; start worker + wire
  progress / finished / error.
- **`_reset_window_level_for_mpr`:** resolve rescale params; sync pane
  view-state / viewer toggle; apply W/L + optional toolbar sync when focused.

## Implementation checklist

- [x] Extend `tests/gui/test_mpr_controller_sonar_slice.py`
- [x] Extract helpers in the four methods; preserve behavior
- [x] Verify focused tests, fresh Sonar; update MAINTENANCE_LOG / CHANGELOG /
      TO_DO; mark Implemented
