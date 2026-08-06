# Plan: Sonar MAJOR Mechanical Sweep (S125 / S1066 / S1172)

**Last updated:** 2026-07-18
**Status:** Implemented
**Baseline:** post slice-display-manager slice; scoped reporter **454**
active priority findings (344 CRITICAL, 110 MAJOR).
**Post-fix analysis:** scoped reporter **408** active priority findings
(343 CRITICAL, 65 MAJOR). Targeted rules cleared: `S125` 24 → 0,
`S1066` 23 → 0, `S1172` 17 → 0.
**Predecessor:**
[`SONARQUBE_SLICE_DISPLAY_MANAGER_SLICE_PLAN_20260718.md`](SONARQUBE_SLICE_DISPLAY_MANAGER_SLICE_PLAN_20260718.md)

## Goal

Mechanically remediate open MAJOR `python:S125`, `python:S1066`, and
`python:S1172` findings without changing product behavior or mixing in
CRITICAL complexity refactors.

## Finding inventory (baseline → achieved)

| Rule | Baseline | After |
|------|----------|-------|
| `S125` | 24 | 0 |
| `S1066` | 23 | 0 |
| `S1172` | 17 | 0 |
| **Priority total** | **454** | **408** (−46) |

## Approach completed

### Pass 1 — S125 + S1066

- Removed commented-out debug/print blocks flagged by Sonar; kept live
  `DEBUG_*`-gated prints and genuine documentation comments.
- Collapsed nested sole-statement `if` nests into combined conditions.
- Rephrased a few documentation comments that Sonar misread as commented
  code (assignment-like trailing comments).

### Pass 2 — S1172

- Removed unused parameters from private helpers and updated call sites /
  tests (`format_final_status`, `_try_navigate_multiframe_instance`,
  `_dataset_idx_to_sorted_pos`, `_init_new_series_state`,
  `_compute_pixel_range_wl`).
- For public / Qt / API-compatible unused params: kept the public name and
  marked intentional retention with `_ = param` (or underscore rename only
  for positional Qt slots such as `_slice_index` / `_zoom_level`).
- No deferred public-arity cases.

## Out of scope (unchanged)

- CRITICAL `S3776` complexity work
- Other MAJOR rules still open (`S108`, `S107`, …)
- Behavior changes

## Implementation checklist

- [x] Point `TO_DO.md` at this plan as the active Sonar slice
- [x] Pass 1: clear all open `S125` and `S1066` locations
- [x] Pass 2: clear or gate each `S1172` per the signature rule
- [x] Verify focused tests, smoke, harness, fresh Sonar; update
      `MAINTENANCE_LOG` / `CHANGELOG` / `TO_DO`; mark Implemented
