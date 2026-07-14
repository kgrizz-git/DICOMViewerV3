# AIP / MIP / MinIP Projection Export Plan

**Status:** Not started  
**Priority:** P1  
**TO_DO ref:** Features (Near-Term) — "Allow export of AIP, MIP, MinIP stack as DICOM or images."

---

## Goal

Allow users to export the current **intensity projection** (AIP, MIP, or MinIP) as:

1. A **single image** (PNG, JPG, or single-frame DICOM) — the current projection view.
2. A **multi-slice DICOM series** — projections computed at each slice position through the volume, producing a new derived series.

### Current state

- **Projection engine:** `src/core/dicom_projections.py` — `average_intensity_projection()`, `maximum_intensity_projection()`, `minimum_intensity_projection()` take a list of datasets and return float32 arrays.
- **Display pipeline:** `src/core/slice_display_pixels.py` → `create_slice_projection_pil_image()` builds a PIL image from a projection around the current slice with a configurable slab thickness.
- **UI controls:** `src/gui/intensity_projection_controls_widget.py` — enable toggle, type selector (AIP/MIP/MinIP), slab thickness (2/3/4/6/8 slices).
- **Export:** Current export (`ExportManager` / `export_rendering.py`) exports the base slice, not the projection. The existing PNG/JPG screenshot capture may incidentally capture the projected display but not as a clean pipeline.

---

## Phase 1 — Single-image projection export

### 1a. Export dialog integration

- [ ] In the Export dialog (`gui/dialogs/export_dialog.py`), when projection is active:
  - Add a **"Export projection view"** checkbox (default on when projection is active).
  - When checked, export uses the projection image instead of the raw slice.
  - Applies current W/L and (if implemented) LUT to the projection.
- [ ] Alternatively, add a dedicated **File → Export Projection…** entry when projection is active.

### 1b. PNG/JPG export

- [ ] Reuse `create_slice_projection_pil_image()` to generate the PIL image.
- [ ] Apply overlays (if the "include overlays" export option is on).
- [ ] Apply anonymization (if enabled — same as existing image export).
- [ ] Save with metadata (projection type, slab thickness, source series) in EXIF or filename.

### 1c. Single-frame DICOM export

- [ ] Create one DICOM instance with:
  - `ImageType` = `["DERIVED", "SECONDARY", "{AIP|MIP|MINIP}"]`.
  - `DerivationDescription` = e.g., "Maximum Intensity Projection (8 slices from slice 42)".
  - `DerivationCodeSequence` with CID 7203 codes for MIP/AIP/MinIP if applicable.
  - SOP Class: Secondary Capture.
  - Pixel Data: float32 → int16 with computed RescaleSlope/Intercept (same as MPR export).
  - Copy patient/study/series metadata from source; new SOPInstanceUID + SeriesInstanceUID.
  - Spatial metadata: use the center slice's IPP; note slab thickness in `SliceThickness`.
- [ ] Reuse patterns from `mpr_dicom_export.py` for pixel encoding and metadata.

### 1d. Tests

- [ ] `tests/test_projection_export.py`:
  - Export MIP as PNG — file exists, correct dimensions.
  - Export AIP as single DICOM — loads in pydicom, correct ImageType.
  - W/L applied correctly to exported projection.

---

## Phase 2 — Multi-slice projection series export

### 2a. Sliding-slab projection stack

- [ ] Compute projections at **every slice position** through the series:
  - For each slice index `i`, compute the projection over `[i, i + slab_thickness - 1]`.
  - Produces `N - slab_thickness + 1` output slices (or `N` with clamped slab at ends).
  - Reuse `average_intensity_projection()` / `maximum_intensity_projection()` / `minimum_intensity_projection()` from `dicom_projections.py`.
- [ ] Run in a background thread with progress (can be slow for large series).
- [ ] Cache results if the same projection type + slab thickness is requested again.

### 2b. Multi-file DICOM export

- [ ] Create a derived DICOM series (one file per projected slice):
  - `SeriesInstanceUID`: new (derived series).
  - `SeriesDescription`: e.g., "MIP (8-slice slab) from [original series description]".
  - Per-slice `ImagePositionPatient`: from the center of each slab.
  - Per-slice `SliceThickness`: slab thickness in mm.
  - `ImageType` = `["DERIVED", "SECONDARY", "{AIP|MIP|MINIP}"]`.
  - Pixel encoding: same int16 + RescaleSlope/Intercept approach as MPR export.
  - Global W/L hint from the projection value range.
- [ ] Output to a user-chosen folder (same as MPR DICOM export).
- [ ] Optional anonymization.

### 2c. Image stack export (PNG/JPG)

- [ ] Export all projection slices as numbered image files in a folder.
- [ ] Apply W/L; optional overlays and anonymization.

### 2d. Tests

- [ ] `tests/test_projection_series_export.py`:
  - 10-slice input, slab=3 → 8 output DICOM files.
  - Each DICOM has correct ImageType and spatial metadata.
  - Round-trip: re-load derived series in the viewer.

---

## Phase 3 — UI for series export

- [ ] **Export dialog:** When projection is active, add option:
  - "Export current projection view" (Phase 1).
  - "Export projection stack (all slices)" (Phase 2).
  - Slab thickness slider (inherit from projection controls or allow override).
- [ ] Progress dialog for multi-slice export.
- [ ] Output folder picker (default: alongside source data or last-used export folder).

---

## Phase 4 — Verification

- [ ] Manual QA: Load a CT chest series → enable MIP with 8-slice slab → export stack as DICOM → reload in viewer → verify MIP stack looks correct (vessels/bones should be more prominent than individual slices).
- [ ] Verify AIP stack produces the expected averaged appearance.
- [ ] Verify MinIP stack highlights low-density structures (air, fluid).
- [ ] Load exported DICOM in an external viewer (3D Slicer, Horos) → verify correct geometry and pixel values.
- [ ] Verify existing (non-projection) export is unaffected.

---

## Open questions

1. **Slab thickness for export:** Should the export always use the currently configured slab thickness, or should the user be able to override it in the export dialog? Recommend: inherit with option to override.
2. **Overlapping vs non-overlapping slabs:** The sliding-slab approach overlaps (slab at slice 0 = [0,7], slab at slice 1 = [1,8]). Should we also offer non-overlapping (slab at 0 = [0,7], next slab at 8 = [8,15])? This produces fewer output slices but loses detail. Recommend: overlapping by default, non-overlapping as an option.
3. **Memory:** Computing MIP across a 500-slice series with slab=8 produces 493 float32 arrays. Should be manageable (~500 MB for 512×512 series) but worth a memory check. The background thread should release each array after writing to disk.
4. **Interaction with LUTs:** If LUTs (from `LUTS_AND_COLORMAPS_PLAN.md`) are active, should the exported projection use the LUT? For DICOM: no (raw pixel data). For PNG/JPG: yes (matches display).

---

## Files likely touched

| File | Change |
|------|--------|
| `src/core/dicom_projections.py` | Possibly add batch/stack projection helper |
| `src/core/projection_export.py` | **New** — stack export logic |
| `src/gui/dialogs/export_dialog.py` | Projection export options |
| `src/core/export_manager.py` | Delegate to projection export |
| `src/core/mpr_dicom_export.py` | Reuse pixel encoding patterns |
| `src/core/export_rendering.py` | Single-image projection rendering |
| `tests/test_projection_export.py` | **New** |
| `tests/test_projection_series_export.py` | **New** |
