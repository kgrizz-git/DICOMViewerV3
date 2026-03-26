# MPR DICOM Save, Cine Video Export, and Angle Measurement – Implementation Plan

This document implements three related items from `dev-docs/TO_DO.md` (**Features (Near-Term)**):

1. **Save MPRs as DICOM** (P1)
2. **Export cine as MPG/GIF/AVI** (P1)
3. **Angle measurement** — two connected line segments with on-screen angle (P2; reuse measurement styling)

**Related context**

- Existing MPR pipeline: `src/core/mpr_builder.py` (`MprResult`), `src/core/mpr_volume.py`, `src/core/mpr_controller.py`, `src/core/mpr_cache.py` (NPZ cache is **not** a substitute for standards-based DICOM export).
- Broader MPR/oblique plan: [SLICE_SYNC_AND_MPR_PLAN.md](SLICE_SYNC_AND_MPR_PLAN.md) (ROIs/measurements on MPR are still deferred there; **this plan** assumes angle and linear measurements remain **disabled on MPR subwindows** unless product direction changes).
- Cine: `src/gui/cine_player.py`, `src/gui/cine_controls_widget.py`, wiring in `src/core/app_signal_wiring.py` and handlers in `src/main.py` (`_on_cine_frame_advance`, etc.).
- Linear measurements: `src/tools/measurement_tool.py`, config under measurement settings in `src/utils/config/` (`measurement_config.py`), integration in `src/core/slice_display_manager.py` and per-subwindow managers in `src/core/subwindow_lifecycle_controller.py`.

---

## 1. Save MPRs as DICOM

### Goal

Allow the user to **write the computed MPR stack** (the same slices shown in an MPR subwindow) to one or more **DICOM CT/MR-style** instances (or a secondary capture SOP Class if you choose to minimize modality claims — see decisions below) so other tools can ingest them.

### Prerequisites

- [ ] Confirm legal/clinical disclaimer: exported MPR series are **derived**; UIDs must be new; patient/study identifiers policy (copy vs anonymize) must match existing export/privacy rules.
- [ ] Inventory what metadata is already available on `MprResult` and the **source** series datasets (first slice or representative instance).

### Design decisions (resolve before coding)

| Topic | Options | Recommendation |
|-------|---------|----------------|
| **SOP Class** | Standard MR/CT Image Storage vs Secondary Capture | Prefer **same general image storage class as source** when modality and attributes are coherent; otherwise **Secondary Capture** (0028,0008) to avoid invalid MR/CT IOD claims. |
| **Frame of reference** | Copy source Frame of Reference UID vs new | **Copy** when geometry is traceable to source; ensures registration tools still relate stacks. |
| **Pixel data** | Raw (BitsAllocated/BitsStored) vs float pipeline | Write **consistent with source** where possible (e.g. apply rescale for display HU only if you also set slope/intercept consistently). Map `MprResult` float slices to output dtype using a documented window (min/max or percentile) or **store slope/intercept** from known rescale. |
| **Series description** | User suffix vs fixed prefix | Default description like `MPR <orientation> from <SeriesDescription>`; optional user suffix in save dialog. |
| **Multi-file API** | One file per slice vs multi-frame | **One file per slice** matches most stacks today and simplifies per-instance UIDs; multi-frame is a later optimization. |

### Implementation outline

1. **Entry point**  
   - Add **“Save MPR as DICOM…”** (or under **Export**) when the **focused subwindow is MPR mode** and a completed `MprResult` (or equivalent in-memory slices + `SliceStack`) is available.  
   - Mirror UX patterns from existing export dialogs (`src/gui/dialogs/export_dialog.py`, `src/core/export_manager.py`) for folder picker, progress, and errors.

2. **Writer module**  
   - New module e.g. `src/core/mpr_dicom_export.py` (or under `src/utils/`) with a pure-ish function:  
     `write_mpr_series(output_dir, mpr_result, template_dataset, options) -> list[Path]`  
   - **UIDs**: new `StudyInstanceUID` only if policy requires; always new `SeriesInstanceUID`, new `SOPInstanceUID` per slice; consistent `SeriesNumber` / `InstanceNumber`.

3. **Metadata**  
   - **Copy** from template: patient/study level tags, referenced source series UID in private tag or `SourceImageSequence` (0018,2107), `ImageType` including `DERIVED\SECONDARY` as appropriate.  
   - **Set** per slice: `ImagePositionPatient`, `ImageOrientationPatient`, `PixelSpacing`, `SliceThickness`, `SpacingBetweenSlices` (if applicable) from `MprResult.slice_stack` and `output_spacing_mm` / `output_thickness_mm`.  
   - **Window/level**: optional preset tags from current viewer W/L or from min/max of slice.

4. **Verification**  
   - Round-trip: load written series in this app and in an external validator (dciodverify / dcmdump).  
   - Unit tests with a **minimal synthetic** `MprResult` or fixture slices (no PHI).

5. **Changelog / version**  
   - Document new behavior and any new optional dependency (none expected if using `pydicom` + NumPy only).

### Out of scope (initial pass)

- Sending to PACS / DIMSE  
- Lossless float32 MPR storage as DICOM float pixels (rare; most tools expect integer pixels + rescale)

---

## 2. Cine video export (MPG, GIF, AVI)

### Goal

From a **cine-capable** subwindow, export the **full loop** (respecting loop bounds and direction if applicable) to **MPG (MPEG)**, **GIF**, or **AVI**, at a user-chosen frame rate (default: effective cine FPS from `CinePlayer` / DICOM).

### Prerequisites

- [ ] Decide dependency strategy: **ffmpeg** subprocess (user must install) vs **Python wheels** (`imageio`, `imageio-ffmpeg`, `opencv-python`). Prefer minimal friction on Windows: e.g. `imageio` + `imageio-ffmpeg` bundles a binary — confirm license and size impact in `requirements.txt`.
- [ ] Privacy: same rules as screenshot export (optional burn-in vs clean pixels; respect privacy mode).

### Design decisions

| Topic | Recommendation |
|-------|----------------|
| **Resolution** | Native pixel matrix of the displayed image after standard LUT **or** explicit “as displayed” (if W/L and zoom must match UI, add a second mode later). |
| **Scope** | **Focused subwindow** first; multi-window batch can reuse export manager patterns later. |
| **Palette GIF** | Quantize to 256 colors; document quality tradeoff for medical grayscale. |
| **MPG vs MP4** | User asked for **MPG**; implement **MPEG-1/2** or **transport** as supported by chosen backend; if only MP4 is trivial, document mapping (e.g. “MPG via ffmpeg `-f mpeg`”). |

### Implementation outline

1. **UI**  
   - Cine toolbar or **Export** submenu: “Export cine as…” → format + path + FPS + loop/range (reuse loop start/end from `CineControlsWidget` if present).

2. **Frame capture**  
   - Drive playback **deterministically**: iterate frame indices `0 … N-1` (or loop range), calling the same path as `_on_cine_frame_advance` / `SliceNavigator.advance_to_frame` **without** relying on real-time `QTimer` for export (avoid dropped frames).  
   - After each advance, grab the **rendered** image: either `QImage` grab of the `ImageViewer` viewport or reuse the same pixmap/array used for PNG export (must match fusion/overlay options per product choice).

3. **Encode**  
   - Feed frames to encoder; **GIF**: variable delay per frame from FPS; **AVI/MPG**: fixed FPS.  
   - Run encoder in background `QThread` with cancel support (pattern from `LoadingProgressManager` / export).

4. **Tests**  
   - Smoke: 4-frame synthetic series → export to temp file → assert file exists and non-empty (skip heavy decode assertions in CI if needed).

### Risks

- **Performance**: large matrices × many frames → memory; stream frames to encoder when possible.  
- **IP/licensing**: confirm codec libraries are OK for distribution in packaged executables.

---

## 3. Angle measurement tool

### Goal

**Three-click** interaction:

1. First click: vertex / hinge point (start of both arms, per product choice — see below).  
2. Second click: first arm endpoint.  
3. Third click: second arm endpoint.  
Display **two line segments** and the **interior angle** (and optionally the **supplementary** angle) with **same color / line thickness / font** as linear measurements.

### Interaction semantics (pick one and document in UI strings)

**Option A (typical “angle at point A”)**  

- Click 1 = **vertex**, click 2 = one ray point, click 3 = other ray point.  
- Angle = angle between vectors **(2−1)** and **(3−1)**.

**Option B (elbow from TO_DO wording)**  

- Click 1 → 2 = first segment; click 3 extends from **vertex at 2** — actually matches “line extends, second click drops point, third segment from there” = polyline **P1–P2–P3**, measure angle at **P2** between segments **P1–P2** and **P2–P3**.

The TO_DO text matches **Option B** (vertices P1–P2–P3 with angle at **P2**). Implement **Option B** unless UX review prefers vertex-first.

### Implementation outline

1. **Data model**  
   - Extend `MeasurementItem` or add `AngleMeasurementItem` in `measurement_tool.py` storing three scene coordinates + computed angle in degrees.  
   - Persistence: extend serialization used for copy/paste and session restore (`annotation_paste_handler.py`, any JSON/session code) with a **versioned** type discriminator.

2. **Painting**  
   - Two `QGraphicsLineItem` (or path) + text item for `θ = xx.x°`; reuse measurement font and pen from config via existing helpers.

3. **State machine**  
   - Idle → after tool activate: `waiting_p1` → `waiting_p2` → `waiting_p3` → commit → idle.  
   - Esc cancels; right-click behavior matches linear measurement tool.

4. **Wiring**  
   - Toolbar / menu: “Angle” next to distance measurement.  
   - Disable on MPR subwindows if linear measurements remain disabled (consistent with [SLICE_SYNC_AND_MPR_PLAN.md](SLICE_SYNC_AND_MPR_PLAN.md)).

5. **Export / screenshots**  
   - Include angle graphics in PNG/JPG export paths where linear measurements are drawn (`export_manager.py`).

6. **Tests**  
   - Pure geometry: known points → expected angle (0°, 90°, 180°).  
   - Optional: Qt graphics test for hit regions if you add dragging handles later (out of scope unless requested).

### Out of scope (initial pass)

- Oblique 3-D angle in patient space (use **in-plane** image coordinates unless pixel spacing is applied consistently for “true” angle — document as **in-plane angle** using **row/column** directions).

---

## Suggested implementation order

1. **Angle measurement** — localized to `measurement_tool` + export + config; lowest integration risk.  
2. **MPR DICOM save** — new writer + dialog; depends on stable `MprResult` access from `MprController`.  
3. **Cine video export** — dependency and packaging decisions; heaviest QA.

---

## Checklist (high level)

### MPR DICOM save

- [ ] Dialog + eligibility (MPR focused subwindow only)
- [ ] `mpr_dicom_export` writer with UIDs and geometry tags
- [ ] Privacy / anonymization alignment
- [ ] Tests + manual round-trip validation
- [ ] `CHANGELOG.md` + version bump per release rules

### Cine export

- [ ] Encoder dependency chosen and documented (`README` / `AGENTS.md` if install steps change)
- [ ] Off-timer frame iteration + capture
- [ ] GIF / AVI / MPG paths
- [ ] Progress + cancel
- [ ] Tests (minimal) + `CHANGELOG.md`

### Angle measurement

- [ ] Three-click tool + visuals + config reuse
- [ ] Export + paste/copy compatibility
- [ ] Tests for geometry math
- [ ] `CHANGELOG.md`
