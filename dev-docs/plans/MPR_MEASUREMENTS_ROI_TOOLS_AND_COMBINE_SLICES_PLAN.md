# MPR Enhancements: ROI/Measurements + Slab Combine (MIP/MinIP/AIP) – Implementation Plan

This document consolidates two related items from `dev-docs/TO_DO.md`:

1. **Enable measurements + ROI tools on MPR subwindows** (including Window/Level ROIs).
2. **Combine slices on MPR** via slab modes (**MIP**, **MinIP**, **AIP**) with configurable slab thickness.

MPR (multi-planar reconstructions) currently renders resampled 2D slices in each subwindow, but the app temporarily disables ROI/measurement/annotation tools in MPR mode and the MPR builder outputs a single plane per navigator step. This plan extends the MPR pipeline so the displayed pixels can be used by ROI statistics/auto-WL and so the user can choose slab-combined rendering for MPR.

---
## Goals

### ROI/Measurement Tools on MPR
- [ ] Allow the user to draw and manage:
  - [ ] Ellipse ROIs and rectangle ROIs
  - [ ] Measurements (distance tool)
  - [ ] Window/Level ROIs (the “Window/Level ROI (W)” auto-WL interaction)
  - [ ] (Optional per scope decision) existing annotation types if they are already supported in non-MPR mode
- [ ] Ensure ROI statistics and measurement scaling use the **displayed MPR resampled pixel array** and **MPR output spacing** (not the synthetic overlay dataset).

### Combine Slices on MPR (Slab Projection)
- [ ] Add per-MPR-view options:
  - [ ] Slab mode: `None`, `MIP`, `MinIP`, `AIP`
  - [ ] Slab thickness in mm
- [ ] When enabled, each MPR navigator step displays the slab-combined 2D image for the plane at the current MPR slice index.
- [ ] ROI statistics and Window/Level ROI calculations operate on the **slab-combined pixels** currently displayed.

---
## Non-Goals (for this plan)

- No RTSTRUCT import/export or fully-fledged 3D ROI/contouring editing.
- No real-time interactive oblique rotation resampling while dragging (unless already implemented elsewhere).
- No guarantee of “pixel-perfect” geometric equivalence for all oblique acquisitions under all interpolation modes; the measurement/area semantics are defined in “Accuracy & Semantics” below.

---
## Current State (what we’re changing)

### MPR tool disabling
- `src/core/mpr_controller.py` explicitly disables ROI/measurement/annotation tools while a subwindow is in MPR mode via `_set_tools_enabled(..., enabled=False)`.
- `src/gui/image_viewer.py` context menu generation disables drawing modes when the image viewer has `_mpr_mode_override=True`, showing tooltips like: “ROIs and annotations are not available on MPR views.”

### ROI statistics pixel source mismatch
- `src/gui/roi_coordinator.py` computes ROI statistics using `dicom_processor.get_pixel_array(current_dataset)` and uses `get_pixel_spacing(current_dataset)`.
- In MPR mode, `src/core/mpr_controller.py` sets `app.current_dataset` to a *synthetic overlay dataset* (text/metadata only). That dataset is not kept in sync with the displayed resampled slice pixels.
- Therefore, without changes, ROI statistics and Window/Level-from-ROI would be computed from the wrong pixel data on MPR subwindows.

### Measurement scaling pixel spacing
- Distance measurement scaling currently comes from `MeasurementTool.set_pixel_spacing(...)`.
- For standard DICOM views, this is wired by `src/core/slice_display_manager.py`.
- MPR display bypasses the normal slice display path, so measurements on MPR either stay disabled or would have incorrect spacing unless we explicitly set spacing for MPR.

---
## Implementation Strategy (high level)

The work is organized into phases with clear dependencies.

1. **Slab combine in the MPR builder** so the displayed MPR slice is already “final” (and reusable by ROI stats/WL).
2. **Expose MPR output geometry to ROI/measurement coordinators** (pixel array + output spacing).
3. **Enable interactive tools in MPR mode** while preserving safe interaction defaults (pan/zoom remain functional).

---
## Files to Be Touched (tracked)

- [ ] `src/gui/dialogs/mpr_dialog.py` (add slab combine controls in the dialog + request fields)
- [ ] `src/core/mpr_controller.py` (pass combine parameters into build/cache; enable ROI/measurement/WL tool activation in MPR)
- [ ] `src/core/mpr_builder.py` (implement slab combine in the MPR build worker)
- [ ] `src/core/mpr_cache.py` (include combine settings in the persistent cache key; bump cache format version)
- [ ] `src/gui/image_viewer.py` (adjust MPR tool gating so ROI/measurement/WL ROI drawing modes remain available)
- [ ] `src/gui/roi_coordinator.py` (switch ROI stats pixel source + pixel spacing when the viewer is in MPR mode)
- [ ] `src/core/slice_display_manager.py` (if using the existing non-MPR measurement wiring path; otherwise measurement spacing will be set directly by `mpr_controller.py`)

---
## Phase 0: Add MPR view state for slab combine

### 0.1 Extend `MprRequest` and `MprDialog`
- [ ] Update `src/gui/dialogs/mpr_dialog.py`:
  - [ ] Extend `MprRequest` dataclass with:
    - [ ] `combine_mode: str` (enum-like string: `none|mip|minip|aip`)
    - [ ] `slab_thickness_mm: float`
  - [ ] Add UI controls to the “Output Parameters” or a new “Slab Combine” group:
    - [ ] Mode dropdown (`None`, `MIP`, `MinIP`, `AIP`)
    - [ ] Thickness spinbox (mm)
    - [ ] Optional quick presets (thin/medium/thick) mapped to mm values

### 0.2 Persist combine settings in request → controller → builder
- [ ] Update `src/core/mpr_controller.py`:
  - [ ] When MPR is requested, pass `combine_mode` and `slab_thickness_mm` into:
    - [ ] cache key generation
    - [ ] `MprBuilder.create_worker(...)`
    - [ ] MprResult reconstruction on cache hit (see Phase 0.3)

### 0.3 Update persistent MPR cache key
- [ ] Update `src/core/mpr_cache.py`:
  - [ ] Include `combine_mode` and `slab_thickness_mm` in the cache key.
  - [ ] Bump `_MPR_CACHE_FORMAT_VERSION` to invalidate incompatible cache entries after schema/behavior changes.

---
## Phase 1: Implement slab combine in `MprBuilder`

### 1.1 Add parameters to builder worker
- [ ] Update `src/core/mpr_builder.py`:
  - [ ] Update `MprBuilderWorker.__init__` to accept:
    - [ ] `combine_mode: str`
    - [ ] `slab_thickness_mm: float`
  - [ ] Update `MprBuilder.create_worker(...)` signature to forward these.

### 1.2 Define slab combine semantics
Let:
- `output_thickness_mm` = the spacing between consecutive generated MPR planes
- `slab_thickness_mm` = user-configured slab thickness

For a requested output plane at index `i`, define the slab range as an integer window of neighboring planes:
- `n = max(1, round(slab_thickness_mm / output_thickness_mm))`
- Use a symmetric window around `i` (clamped to `[0, n_slices-1]`).

Then:
- `MIP`: per-pixel `max` across the slab window
- `MinIP`: per-pixel `min` across the slab window
- `AIP`: per-pixel `mean` across the slab window
- `None`: the original per-plane slice (current behavior)

#### Accuracy tradeoff note
This “window across already-resampled slices” approach is a practical MVP:
- It is consistent with orientation changes because it’s computed in the resampled MPR plane family.
- It is approximate vs. “full volume-space slab rendering” when interpolation and thickness don’t align perfectly with `output_thickness_mm`.

If later you want the more exact “compute slabs in volume space before final plane rendering” approach, it should still be able to reuse the same UI + state model. That future upgrade would add more sampling along the slab-normal axis and collapse in volume space.

### 1.3 Update `MprResult` (metadata for downstream consumers)
- [ ] Optionally extend `MprResult` with:
  - [ ] `combine_mode: str`
  - [ ] `slab_thickness_mm: float`
- [ ] This is useful for debugging, overlay labeling, and QA reporting.

---
## Phase 2: Enable ROI/Measurement tools on MPR subwindows

### 2.1 Allow tool activation in MPR mode
- [ ] Update `src/core/mpr_controller.py`:
  - [ ] Change `_set_tools_enabled(idx, enabled=False)` logic so that MPR no longer “hard disables” tools.
  - [ ] Keep a safe default mouse mode:
    - [ ] default mouse mode on entering MPR: `pan`
    - [ ] but allow tool modes in the context menu/toolbars (ROI/measurement/WL ROI)
- [ ] Update `src/gui/image_viewer.py`:
  - [ ] Adjust the “Drawing/annotation modes are disabled in MPR mode” gate so the disabled list matches the new intended scope.
  - [ ] Ensure Window/Level ROI mode (`auto_window_level`) is not disabled when we’re implementing Window/Level ROIs on MPR.

### Acceptance criterion
- [ ] After creating an MPR view, the user can select:
  - [ ] `Ellipse ROI`, `Rectangle ROI`, `Measure`, and `Window/Level ROI (W)`
  - [ ] and draw them on the MPR view without UI dead-ends.

### 2.2 Ensure ROI statistics use the displayed MPR pixels
This is the most important correctness requirement.

- [ ] Update `src/gui/roi_coordinator.py`:
  - [ ] Add MPR detection logic:
    - [ ] Use existing `image_viewer.is_mpr_view_callback` (already present in `ImageViewer`) or a new callback exposed from `MprController`.
  - [ ] When in MPR mode:
    - [ ] Replace `_get_pixel_array_for_statistics()`’s fallback path from:
      - [ ] `dicom_processor.get_pixel_array(current_dataset)`
      - [ ] to:
      - [ ] the currently displayed MPR slice array (and slab-combined slice if Phase 1 is enabled).
    - [ ] Replace `pixel_spacing = get_pixel_spacing(current_dataset)` with:
      - [ ] `pixel_spacing = (output_spacing_row_mm, output_spacing_col_mm)` from `MprResult.output_spacing_mm`.

#### Decide how projection settings interact with slab combine
Current non-MPR ROI stats can use slice “projection” (MIP/MinIP/AIP over neighboring DICOM slices).
For MPR, we now have slab combine inside the MPR rendering itself.

Recommended rule (MVP clarity):
- [ ] In MPR mode, treat the existing “projection” toggles in the app as:
  - [ ] disabled/ignored for ROI stats
  - [ ] because slab combine already provides the intended behavior and avoids confusing “two different projection concepts”.

### 2.3 Ensure measurement tool has correct pixel spacing
- [ ] Update `src/core/mpr_controller.py` to set MeasurementTool spacing when showing slices:
  - [ ] After `display_mpr_slice` updates the image, set:
    - [ ] `measurement_tool.set_pixel_spacing(result.output_spacing_mm)`
  - [ ] The per-slice logic should be stable because output spacing is constant for a given MPR build.

Alternatively (and more robust):
- [ ] Set pixel spacing once in `_activate_mpr(...)` and update it when MPR is rebuilt/cleared.

### 2.4 ROI + Measurement geometry semantics (what the numbers mean)
Define explicit semantics to avoid misleading users:

- Distance measurement on MPR:
  - Compute distance in the **output plane** coordinate system (mm), using MPR output pixel spacing.
  - For oblique planes, this corresponds to the physical distance along the plane axes (the same assumptions DICOM makes about in-plane pixel spacing).
  - Implementation option:
    - current tool computes distance using 2D dx/dy scaled by row/col spacing
    - future enhancement can compute 3D distance by projecting endpoints into patient space using `SlicePlane` geometry

- ROI area calculation:
  - Use `output_spacing_mm` for area in mm².
  - Current ROI manager computes area based on pixel mask and `pixel_spacing` product; this remains consistent with “output plane” semantics.

### 2.5 (Recommended follow-up) World-space persistence and cross-plane editing
The `dev-docs/FUTURE_WORK_DETAIL_NOTES.md` guidance suggests:
- [ ] Store measurements and ROIs in patient/world space
- [ ] Render them into each MPR view via transform projection

This plan includes an MVP path that makes features work with correct displayed pixels and scaling.

Then a follow-up (separate plan) can:
- [ ] refactor ROI/measurement storage into a world-space data model
- [ ] support projecting/editing the same ROI across multiple MPR planes with clear ownership/conflict rules

---
## Phase 3: UI/UX polish & QA integration

### 3.1 MPR banner labeling
- [ ] Update the overlay banner from `MPR - <Orientation>` to optionally include slab mode:
  - [ ] `MPR - Coronal (MIP, 6mm slab)` when combine is active.

### 3.2 ROI list / statistics panel consistency
- [ ] Ensure ROI list panel and statistics panel update when:
  - [ ] MPR slice index changes
  - [ ] MPR combine mode changes (new build)
  - [ ] focus shifts between MPR and non-MPR subwindows

Recommended behavior:
- [ ] ROI selection is scoped to the focused subwindow (same as existing non-MPR ROI behavior).

### 3.3 Testing and validation plan

#### Unit tests (non-Qt)
- [ ] Slab combine correctness:
  - [ ] Given a synthetic volume (or synthetic slice arrays), verify:
    - [ ] `MIP` uses max
    - [ ] `MinIP` uses min
    - [ ] `AIP` uses mean
  - [ ] Verify clamping at boundaries when the slab window extends outside `[0, n_slices-1]`.

#### Integration tests (app logic / lightweight)
- [ ] ROI stats pixel source:
  - [ ] On an MPR view, draw an ROI and confirm the displayed stats correspond to the displayed resampled pixels (not the synthetic overlay dataset).
- [ ] Window/Level ROI:
  - [ ] Use a known region with distinct min/max values:
    - [ ] verify W/L controls update to match ROI stats.

#### Manual QA checklist
- [ ] Create MPR view and confirm:
  - [ ] ROI ellipse drawing works and the ROI list populates.
  - [ ] ROI statistics overlay appears and changes as you scroll MPR slices.
  - [ ] Measurement tool reports mm values (and changes with output spacing if you rebuild MPR with different spacing).
  - [ ] Window/Level ROI updates W/L controls and deletes the temporary ROI as expected.
- [ ] Toggle combine mode (None/MIP/MinIP/AIP) and verify:
  - [ ] MPR display updates per navigator step.
  - [ ] ROI statistics and auto-WL reflect combined output pixels.

---
## Risks & Mitigations

- Performance:
  - ROI move events can recompute stats frequently.
  - Mitigation: debounce ROI stats recomputation; reuse the already-displayed in-memory MPR slice arrays.

- Cache invalidation errors:
  - Combine parameters must be included in cache keys.
  - Mitigation: bump cache format version and include `combine_mode/slab_thickness_mm` in key + metadata.

- Coordinate mapping mismatch:
  - Current ROI manager assumes scene-to-pixel mapping is effectively 1:1.
  - Mitigation: verify scene bounds for MPR slices (scaled display) still map correctly; if not, implement a proper mapping layer in ROI manager or in ROI coordinator.

- Measurement semantics confusion:
  - Users may expect measurements in original acquisition space.
  - Mitigation: explicitly label/understand that measurements are in the MPR output plane coordinate system.

---
## Deliverables / Completion Checklist

- [ ] MPR dialog supports slab combine controls (`None|MIP|MinIP|AIP`) and slab thickness.
- [ ] MprBuilder applies slab combine so the displayed slice arrays are already combined.
- [ ] MPR cache keys include slab combine parameters and old caches are invalidated safely.
- [ ] MPR mode no longer hard-disables ROI/measurement/WL ROI tool activation.
- [ ] ROI statistics on MPR use the displayed MPR slice arrays and use MPR output pixel spacing.
- [ ] MeasurementTool uses MPR output pixel spacing on MPR subwindows.
- [ ] QA confirms ROI stats + auto-WL match the displayed MPR pixels for all slab modes.

