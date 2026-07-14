# MPR Rescale and Overlay/Combine Consistency Plan

This plan covers two `P0` items from `dev-docs/TO_DO.md`:

1. Base-series rescale consistency for MPR pixel values.
2. MPR overlay correctness for slice thickness and combine-slices labeling (including initial MIP/MinIP creation labeling).

## Scope and Goals

### 1) MPR Rescale Consistency

Goal: ensure MPR display values are transformed with the same rescale semantics as the source series (for both live builds and cache hits), and that this remains true when runtime MPR combine-slices is enabled.

### 2) MPR Overlay and Labeling Consistency

Goal: on MPR views, make overlay content represent the constructed MPR stack (not raw source-slice metadata) while preserving existing non-MPR overlay behavior:

- `SliceThickness` should show the constructed MPR thickness by default.
- When MPR combine-slices is active (from dialog defaults or right-pane controls), overlay should show combined range/type and combined thickness info analogous to regular projection overlays.
- If MPR is initially created with `MIP` or `MinIP`, the MPR banner/label should indicate that mode clearly.

---

## Current-State Findings (Code-Based)

- MPR display path is bypassed through `MprController.display_mpr_slice()` rather than `SliceDisplayManager.display_slice()`.
- In `MprController.display_mpr_slice()`, MPR combine is applied first (`apply_mpr_stack_combine`) and then rescale is applied via `MprResult.apply_rescale()`. This is directionally correct.
- `MprBuilder` captures source `RescaleSlope` and `RescaleIntercept` into `MprResult`; `MprCache` persists and reloads these fields.
- MPR overlay currently uses a synthetic dataset from `_build_overlay_dataset()`, but:
  - it does not currently stamp MPR-derived `SliceThickness`;
  - MPR overlay creation does not pass projection/combine metadata to `OverlayManager.create_overlay_items()` (regular series path does).
- Existing `overlay_text_builder.get_corner_text()` already supports projection labels/ranges and combined thickness display if the relevant projection arguments are passed.
- MPR banner is currently only `MPR - <Orientation>`, without combine-mode qualifier.

---

## ROI statistics on MPR (root cause, 2026-04-11)

**Symptom:** ROI mean/min/max on an MPR view did not match rescaled (e.g. HU) display values.

**Causes (both fixed in code):**

1. **Per-subwindow vs focused `ViewStateManager`:** Each subwindow has its own `view_state_manager`, but `ROICoordinator` used `DICOMViewerApp._get_rescale_params()`, which read **only** the **focused** window’s rescale slope/intercept/`use_rescaled_values`. Statistics for a **non-focused** MPR pane (or any mismatch) could apply the wrong rescale flags to the pixel buffer from `get_mpr_pixel_array()`.

2. **Double application when focused:** `_get_subwindow_mpr_pixel_array()` already returns **display-space** pixels (it applies `MprResult.apply_rescale` when that subwindow’s `use_rescaled_values` is true). `ROIManager.calculate_statistics()` was **also** given slope/intercept when `use_rescaled` was true → **double rescale** on focused MPR, or inconsistent pairing with (1).

**Fix:** Wire `get_rescale_params` to `_get_subwindow_rescale_params(idx)` (same subwindow index as the coordinator). For MPR views, **never** pass slope/intercept into `calculate_statistics` (buffer is already display-ready). **HU labels:** broaden `infer_rescale_type` for CT (any slope+intercept → `HU` unless `RescaleType` is set); MPR W/L reset passes **unit** into `set_window_level`.

---

## Implementation Plan

## 1. Rescale Consistency for MPR Pixel Values

### 1.1 Harden and document invariants

- [x] Add/confirm explicit inline comments in `MprController.display_mpr_slice()` describing required order:
  1) combine raw planes,
  2) apply rescale,
  3) apply W/L for rendering.
- [x] Add a defensive log branch (debug-only) when exactly one of slope/intercept is present (unexpected partial rescale metadata). (`MprBuilderWorker._get_rescale_params`, gated by `DEBUG_MPR`.)
- [x] Verify no alternate MPR display path bypasses `result.apply_rescale()` (e.g., helper/export/histogram callbacks).

### 1.2 Ensure cache parity

- [x] Verify cache-hit reconstruction path (`_on_mpr_requested()` cache branch) preserves `rescale_slope` and `rescale_intercept` already stored in `meta`.
- [x] Add a targeted unit test that saves/loads an MPR result through `MprCache` and asserts `MprResult.apply_rescale()` behavior remains numerically identical pre/post cache.

### 1.3 Add regression tests for combine + rescale interaction

- [x] Add test case where source slices contain known raw values with non-trivial slope/intercept.
- [x] Assert for MPR display math equivalence:
  - expected = `rescale(combine(raw stack))`,
  - actual from controller helper path (or extracted pure function path if introduced).
- [x] Cover at least `aip` and one extremum mode (`mip` or `minip`) to prevent mode-specific regressions.

---

## 2. MPR Overlay SliceThickness and Combine Labeling

### 2.1 Stamp MPR-derived thickness into overlay dataset

- [x] Update `MprController._build_overlay_dataset()` to set/overwrite synthetic dataset thickness fields from `MprResult.output_thickness_mm`:
  - `SliceThickness`,
  - and optionally `SpacingBetweenSlices` (if used elsewhere in overlays).
- [x] Keep patient/study/series identifiers unchanged to avoid breaking existing overlay/tag behavior.
- [x] Confirm this value is used whenever projection/combine is disabled in MPR mode.

### 2.2 Feed MPR combine context into overlay pipeline

- [x] In `MprController.display_mpr_slice()`, compute MPR combine overlay context (mirroring regular projection logic):
  - enabled flag,
  - start/end stack indices for current slab window,
  - combined thickness estimate (`sum` or `count * output_thickness_mm`, with edge-aware count).
- [x] Pass these fields to `overlay_manager.create_overlay_items(...)` via existing projection args:
  - `projection_enabled`,
  - `projection_start_slice`,
  - `projection_end_slice`,
  - `projection_total_thickness`,
  - `projection_type`.
- [x] Reuse current label vocabulary from `overlay_text_builder` (`AIP`/`MIP`/`MinIP`) to keep UI terminology consistent.

### 2.3 Confirm no regression for non-MPR overlays

- [x] Ensure changes are confined to MPR display path and do not alter `SliceDisplayManager.display_slice()` overlay semantics for regular series.
- [x] QWidget vs QGraphics: both branches call `get_corner_text` with the same projection kwargs (`overlay_manager.py`); class docstring documents the contract. Automated: `tests/test_mpr_overlay_and_rescale.py` (`test_overlay_corner_text_mip_minip_vocabulary_matches_widget_graphics_contract`). Full visual parity in both overlay modes remains a manual check.

---

## 3. MPR Banner Labeling for Initial MIP/MinIP

### 3.1 Banner content model

- [x] Add a helper in `MprController` to build banner text from:
  - orientation label (`Axial/Coronal/Sagittal/...`),
  - active combine mode if enabled.
- [x] For initial dialog-created MPR where `combine_mode in {"mip", "minip"}` and slab thickness > 0:
  - label as `MPR - <Orientation> (MIP)` or `MPR - <Orientation> (MinIP)`.
- [x] For `aip`, decide whether to label explicitly:
  - recommended: include `(AIP)` only when combine is enabled to match “combined view” semantics.

### 3.2 Keep banner live with right-pane changes

- [x] Ensure banner refreshes whenever MPR combine mode/enabled state changes through:
  - `_on_projection_enabled_changed`,
  - `_on_projection_type_changed`,
  - `_on_projection_slice_count_changed` (no mode text change, but triggers redraw consistency).
- [x] Verify clearing MPR still resets banner (`set_mpr_banner(None)`).

---

## 4. Validation and QA Checklist

### 4.1 Automated tests

- [x] Extend `tests/test_mpr_core.py` with:
  - rescale-preservation checks,
  - cache round-trip rescale parity,
  - combine+rescale numerical checks.
- [x] Add/extend overlay text tests (new file if needed, e.g. `tests/gui/test_overlay_text_builder.py`) for:
  - MPR-style `SliceThickness` display,
  - projection label/range formatting for MPR context.
- **Note:** Corner/projection strings live in `tests/test_mpr_overlay_and_rescale.py` (`get_corner_text`). CT HU inference: `tests/test_dicom_rescale.py`.

### 4.2 Manual QA scenarios

- [x] Build MPR from CT-like source (non-identity rescale), compare expected HU-like values via histogram/pixel probe path.
- [x] Toggle MPR combine enabled/disabled and switch `AIP/MIP/MinIP`; verify overlay and banner updates immediately.
- [x] Verify edge slices (start/end of MPR stack) show correct slab range and combined thickness.
- [x] Verify clearing MPR and creating a new MPR from another series keeps behavior correct.

### 4.3 Regression checks

- [x] Run focused tests:
  - `python -m pytest tests/test_mpr_core.py -v`
  - any overlay-focused tests added.
- [ ] Run existing smoke subset relevant to display/overlays if available.

---

## Files Expected to Be Touched

Primary implementation files:

- `src/core/mpr_controller.py`
- `src/gui/overlay_text_builder.py` (likely no functional change needed, but may need formatting/precision tweaks)
- `src/gui/overlay_manager.py` (only if MPR-specific argument plumbing/helper changes are needed)
- `src/main.py` (only if banner refresh or MPR combine signal handling requires small wiring updates)

Potential support files:

- `src/core/mpr_cache.py` (only if metadata handling needs hardening comments/validation)

Tests:

- `tests/test_mpr_core.py`
- `tests/gui/test_overlay_text_builder.py` (new, if added)

Documentation:

- `dev-docs/TO_DO.md` (linking done in this task)
- `dev-docs/plans/completed/MPR_RESCALE_AND_OVERLAY_COMBINE_PLAN.md` (this file)

---

## Sequencing Recommendation

1. Implement MPR overlay dataset + projection context plumbing in `MprController` first.
2. Implement banner text helper + live update hooks.
3. Add/expand tests for rescale + combine and overlay text formatting.
4. Run focused regression checks and then wider smoke checks.

---

## Semantic Versioning / Changelog Impact

This plan and TODO-link update is documentation-only, so it is expected to be a patch-level, non-functional documentation change until code implementation begins.
