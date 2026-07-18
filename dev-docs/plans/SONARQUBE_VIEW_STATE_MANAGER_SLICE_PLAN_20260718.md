# Plan: View State Manager Sonar Slice

**Last updated:** 2026-07-18
**Status:** Implemented
**Baseline:** post MAJOR mechanical sweep; scoped reporter **408**
active priority findings (343 CRITICAL, 65 MAJOR).
**Post-fix analysis:** scoped reporter **399** active priority findings
(338 CRITICAL, 61 MAJOR). Five targeted `view_state_manager` `S3776`
findings closed.
**Predecessor:**
[`SONARQUBE_MAJOR_MECHANICAL_SWEEP_PLAN_20260718.md`](SONARQUBE_MAJOR_MECHANICAL_SWEEP_PLAN_20260718.md)

## Goal

Reduce cognitive complexity on five CRITICAL methods in
`src/gui/view_state_manager.py` by extracting focused private helpers,
preserving W/L, zoom, rescale, and viewport behavior.

## In-scope findings (`python:S3776`)

| Method | Approx line |
|--------|-------------|
| `store_initial_view_state` | 263 |
| `reset_view` | 379 |
| `handle_window_changed` | 598 |
| `handle_rescale_toggle` | 703 |
| `handle_viewport_resized` | 873 |

Expected Sonar delta: about **−5 CRITICAL** (408 → ~403). Achieved: **399**
(−9 priority; −5 CRITICAL plus incidental MAJOR cleanup).

## Out of scope

- Remaining MAJOR in this file (`S108`, `S1871`)
- MPR / fusion / loading controllers
- Behavior changes to W/L, presets, rescale, or fit-on-resize

## Implementation checklist

- [x] Add `tests/gui/test_view_state_manager_sonar_slice.py`
- [x] Extract helpers in the five methods; preserve behavior
- [x] Verify focused tests, smoke, harness, fresh Sonar; update
      MAINTENANCE_LOG / CHANGELOG / TO_DO; mark Implemented
