# Export Annotations, Resolution Options, and Screenshots – Implementation Plan

This document outlines the implementation plan for three related export improvements from `dev-docs/TO_DO.md` (lines 9–11): resolution-independent annotation sizing, replacing “apply current zoom” with explicit upscale options, and adding “Export Screenshots” for currently displayed subwindows.

**References:**  
- Current export flow: `src/gui/dialogs/export_dialog.py`, `src/core/export_manager.py`  
- Annotation options: `src/gui/dialogs/annotation_options_dialog.py`, `src/utils/config_manager.py`  
- Export overlay/ROI rendering: `ExportManager._render_overlays_and_rois()` in `export_manager.py`  
- Multi-subwindow: `src/core/subwindow_lifecycle_controller.py`, `main.py` (`image_viewer` = focused subwindow)

---

## 1. Overview of Changes

| Area | Current behavior | Target behavior |
|------|------------------|-----------------|
| **Annotation size in export** | ROI/measurement line and font sizes from config are scaled only by `zoom_factor` (current zoom when dialog opened). No resolution-independent mapping. | Use **formula-based sizing** from image dimensions: line thickness = (1/100)·(setting/2)·(width+height)/2; text size = (1/100)·(setting)·(width+height)/2 (with optional scale when magnification is used). Include **text and arrow annotations** in export and screenshots when user opts to include annotations. |
| **Resolution option** | Single checkbox: “Export at displayed resolution (apply current zoom)” – uses focused subwindow’s zoom for all exports. | **Remove** that option. **Add**: export at **native resolution** or **magnified 1.5×, 2×, or 4×**. Optional: “Enlarge line thickness and text size by the same factor” (yes/no). |
| **Screenshots** | Not available. | **New**: “Export Screenshots” – save currently displayed image(s) exactly as shown. **One file per selected subwindow.** User selects which visible subwindow(s) to include; when annotations are included, text and arrow annotations are included. Only the currently displayed frame per subwindow; annotations match on-screen appearance. |

---

## 2. Scope and Out-of-Scope

**In scope**

- PNG/JPG export (tree-based “Export Images” flow): annotation sizing, resolution/upscale UI and logic, removal of “apply current zoom.”
- New “Export Screenshots” flow: per-subwindow capture of current frame with optional annotations as displayed.

**Out of scope for this plan**

- DICOM export (no annotation/resolution UI changes).
- Changing how annotation options are stored in config (still integer line thickness and font sizes); only **interpretation** at export time becomes percent-based (and optionally scaled by upscale factor).
- **In scope:** Include **text and arrow annotations** in image export and in screenshots when the user opts to include annotations (see checklist 6.1 and 6.3).

---

## 3. Detailed Design

### 3.1 Annotation sizing: formula-based (TO_DO item 9)

**Goal:** Line thickness and text size in exported images are derived from image dimensions so that the same annotation settings produce consistent visual weight across resolutions.

**Formulas (when there is no image magnification):**

- **Line thickness in export (pixels):**  
  `line_thickness = (1/100) * (line_thickness_setting / 2) * (image_width + image_height) / 2`  
  i.e. `(setting/2) * (width + height) / 200`. Apply to ROI line thickness and measurement line thickness (each uses its own config setting).
- **Text size in export (pixels, used as font size):**  
  `text_size = (1/100) * (text_size_setting) * (image_width + image_height) / 2`  
  i.e. `setting * (width + height) / 200`. Apply to ROI font size, measurement font size, overlay (DICOM corner) font size, and text-annotation font size (each uses its own config setting).

Use the **final** export image dimensions (after any 1.5×/2×/4× upscale). When “Enlarge line thickness and text size by the same factor” is checked, multiply the resulting line thickness and text size values by the export scale factor.

**Implementation outline**

- Add helpers (e.g. in `export_manager` or a shared util):  
  - `export_line_thickness_pixels(setting: int, width: int, height: int, scale_factor: float = 1.0) -> int`  
    Returns `max(1, round((1/100) * (setting/2) * (width+height)/2 * scale_factor))`.  
  - `export_text_size_pixels(setting: int, width: int, height: int, scale_factor: float = 1.0) -> int`  
    Returns value clamped to a reasonable range (e.g. 8–72), from `(1/100) * setting * (width+height)/2 * scale_factor`.
- In `_render_overlays_and_rois`, **stop** scaling ROI/measurement line thickness and font sizes by `zoom_factor` only. Instead use the formulas above with the current export image `width` and `height` and the optional `scale_factor` when “enlarge by same factor” is true.
- Overlay (DICOM corner) font: use the same text-size formula with the overlay font-size setting.
- **Text and arrow annotations:** When “include overlays and ROIs” (annotations) is selected, also render **text annotations** and **arrow annotations** onto the export image, using the same line-thickness formula for arrow stroke and the same text-size formula for text annotation font (from config text annotation font size). Add the necessary data lookups (per study/series/slice and scene) and drawing in `_render_overlays_and_rois` or a dedicated helper.

---

### 3.2 Replace “apply current zoom” with upscale options (TO_DO item 10)

**Goal:** Remove the “Export at displayed resolution (apply current zoom)” checkbox and replace it with explicit, predictable resolution choices.

**New UI (Export dialog, PNG/JPG only)**

- **Resolution:**  
  - **Native resolution** (no upscale).  
  - **1.5×**, **2×**, **4×** (magnification of the image dimensions).
- **Checkbox:** “Enlarge line thickness and text size by the same factor” (only visible when 1.5× / 2× / 4× is selected).  
  - If checked: after computing annotation sizes from the percent-based rule, multiply line thickness and font sizes by the selected factor (1.5, 2, or 4).  
  - If unchecked: annotation sizes are purely percent-based (no extra scaling by factor).

**Backend**

- Remove `export_at_display_resolution`, `current_zoom`, and `initial_fit_zoom` from the export API where they are used only for this behavior.
- Add parameters, e.g.:  
  `export_scale: Literal[1.0, 1.5, 2.0, 4.0]` and `scale_annotations_with_image: bool`.
- In `export_slice` (and batch export):
  - Build the base image at native resolution.
  - If `export_scale > 1.0`, resize image by that factor (same as current zoom-based resize, but with a fixed value).
  - When rendering overlays/ROIs, compute annotation sizes from the percent-based rule using the **final** image dimensions; if `scale_annotations_with_image` is true, multiply those sizes by `export_scale`.

**Scale limits (performance / memory)**

To avoid excessive memory use and slow exports when scaling large images, **disable** high scale factors when the **output** would exceed a maximum dimension:

- **Suggested cap:** Maximum dimension of the exported image ≤ **4096** pixels. (Keeps per-image memory reasonable; 4096×4096×4 bytes ≈ 67 MB. Adjust to 8192 if needed for high-end workflows.)
- **4× scaling:** Disable when `max(image_width, image_height) > 1024` (since 4× would give 4096). So 4× is only offered for images with both dimensions ≤ 1024.
- **2× scaling:** Disable when `max(image_width, image_height) > 2048` (since 2× would give 4096). So 2× is only offered when the larger side is ≤ 2048.
- **1.5× scaling:** Disable when `max(image_width, image_height) > 2730` (2730×1.5 ≈ 4096). 

**Implementation:** The export dialog does not know image dimensions until the user has selected studies/series/slices. Two approaches: (a) **Dynamic:** When the user changes selection, recompute the **maximum** native dimension across all selected slices and enable/disable 2× and 4× in the resolution combo (or show them grayed with a tooltip: “Not available for selected images (max dimension would exceed 4096)”). (b) **Per-slice:** Apply the limit at export time: for each slice, if the chosen scale would exceed 4096 on the long side, either cap the scale for that slice (e.g. use 2× instead of 4×) or skip scaling for that slice and export at native. Recommend **(a)** so the user sees up front which options are valid; if selection is mixed (some small, some large), use the **largest** max dimension in the selection to decide which scale options to offer (conservative: one large image disables 4×/2× for the whole batch).

**Files to touch**

- `src/gui/dialogs/export_dialog.py`: Remove display-resolution checkbox. Add resolution combo (Native / 1.5× / 2× / 4×) and “Enlarge line thickness and text size by the same factor” checkbox. **Enable/disable 4× and 2× based on selected items’ max dimension (e.g. 4× only if max ≤ 1024, 2× only if max ≤ 2048).** Pass new parameters to `ExportManager`.
- `src/core/export_manager.py`: Replace `export_at_display_resolution`/`current_zoom`/`initial_fit_zoom` with `export_scale` and `scale_annotations_with_image`. Use percent-based annotation sizing and optional scale factor.
- `src/gui/dialog_coordinator.py`: `open_export()` no longer needs `current_zoom` or `initial_fit_zoom` for resolution; remove or keep only if still used for something else (e.g. overlay font legacy path).
- `main.py`: `_open_export()` – stop passing `current_zoom` and `initial_fit_zoom` (unless required elsewhere).

---

### 3.3 Export Screenshots (TO_DO item 11)

**Goal:** A separate action “Export Screenshots” that saves the **currently displayed** image(s) exactly as they appear. **One file per selected subwindow.** When the user opts to include annotations, text and arrow annotations are included in the capture.

**Behavior**

- **Source:** Only the currently displayed frame in each selected subwindow (no study/series/slice tree).
- **Output:** One file per selected subwindow (e.g. `screenshot_view1.png`, `screenshot_view2.png`). No combined/grid option.
- **Appearance:** Pixel-accurate to what is on screen (zoom, pan, window/level, overlays, ROIs, measurements, and when enabled, text and arrow annotations). Line thickness and text size match the viewer because the image is captured from the view.
- **Selection:** User selects which of the currently visible subwindows to include (e.g. checkboxes “View 1”, “View 2”, “View 3”, “View 4”). Only subwindows that have an image loaded are eligible. Option to “Include annotations” (overlays, ROIs, measurements, text and arrow annotations) so the capture matches the current display; when unchecked, capture can be image-only or still include annotations depending on product decision (recommend: when “Include annotations” is checked, capture includes everything drawn on the view, including text and arrows).

**Implementation outline**

- **Entry point:** New menu item (e.g. File → Export Screenshots or Export → Screenshots). Separate from the existing “Export Images” dialog.
- **Dialog:**  
  - List of visible subwindows (e.g. “View 1”, “View 2”, …) with checkboxes.  
  - **One file per subwindow:** save each selected view to its own file (e.g. `screenshot_view1.png`).  
  - Checkbox: “Include annotations” (overlays, ROIs, measurements, text and arrow annotations). When checked, the capture must include all of these (they are part of the scene/viewport).  
  - Output directory and optional filename prefix.  
  - Format: PNG (and optionally JPG).
- **Capture:**  
  - For each selected subwindow, get its `QGraphicsView` (image viewer).  
  - Use `QWidget.grab()` on the viewport (or the view) to get exactly what’s on screen so that overlays, ROIs, measurements, and text/arrow annotations are included in the pixel capture.  
  - If annotations are drawn in a separate layer, ensure the grabbed widget includes that layer (or use `QGraphicsScene.render()` if needed so text and arrow annotations are present).
- **File naming:** e.g. `{prefix}view{index}.png` or `{prefix}{index}.png`. One file per selected subwindow.
- **No DICOM:** Screenshots are raster only (PNG/JPG).

**Edge cases**

- Subwindow has no image: hide or disable that option in the list.
- Layout 1×1 vs 2×2 vs others: “Export Screenshots” always exports “current frame” per view; layout only affects which views exist, not the capture method.
- High DPI / device pixel ratio: use a resolution-independent capture (e.g. `grab()` already accounts for device pixels) so the saved image matches what the user sees.

---

## 4. Ambiguities and Decisions to Resolve

- **Annotation formulas:** Resolved. Line thickness = (1/100)·(setting/2)·(width+height)/2; text size = (1/100)·(setting)·(width+height)/2 (see §3.1). Overlay (DICOM corner) font uses the same text-size formula with the overlay font-size setting.
- **Text and arrow annotations:** In scope. When the user opts to include annotations, image export must render text and arrow annotations (using the same formulas); screenshots include them by capturing the view (they are part of the scene when “Include annotations” is checked).
- **Backward compatibility:** Removing “apply current zoom” changes behavior for users who relied on it. Document in release notes and, if desired, add a short note in the Export dialog (e.g. “Use 1.5× / 2× / 4× for higher resolution export”).
- **Screenshots:** One file per selected subwindow (no combined image option).

---

## 5. Potential Problems and Risks

- **Performance:** Export at 4× with “enlarge annotations” and many slices could be memory- and CPU-heavy. **Add scale limits:** disable 4× when image max dimension > 1024, disable 2× when > 2048 (cap output at 4096). See §3.2 “Scale limits.” Use progress feedback for multi-slice export.
- **Font availability:** Export already uses a list of font paths for PIL; percent-based font sizes may produce larger or smaller point sizes. Keep min/max bounds (e.g. 8–72 pt) to avoid broken layouts.
- **Screenshot and overlays:** If overlays are drawn in a separate layer (e.g. on top of the viewport), `grab()` should include them. If they are drawn inside the scene, `QGraphicsScene.render()` might be needed to include them; verify with the current overlay implementation.
- **Order of implementation:** Implementing 3.1 (percent-based sizing) and 3.2 (upscale options) together is recommended so that the export pipeline has a single, consistent resolution and annotation model. Screenshots (3.3) can be implemented after or in parallel, as they use a different code path.

---

## 6. Checklist (to-do items)

Use this checklist when implementing; mark items complete only when done and verified.

### 6.1 Annotation sizing and rendering (formula-based + text/arrow)

- [x] Document the formulas in code: line thickness = (1/100)·(setting/2)·(width+height)/2; text size = (1/100)·(setting)·(width+height)/2 (no magnification). With magnification and “enlarge by same factor,” multiply results by export scale.
- [x] Add helpers in `export_manager` (or shared util): `export_line_thickness_pixels(setting, width, height, scale_factor)` and `export_text_size_pixels(setting, width, height, scale_factor)` implementing the formulas with min/max clamping where needed.
- [x] In `_render_overlays_and_rois`, replace zoom-based scaling of ROI line thickness and ROI font size with the new formula-based helpers.
- [x] In `_render_overlays_and_rois`, replace zoom-based scaling of measurement line thickness and measurement font size with the new formula-based helpers.
- [x] In `_render_overlays_and_rois`, convert overlay (DICOM corner) font size to the text-size formula (overlay font setting) and remove dependence on `initial_fit_zoom` / zoom ratio.
- [x] **Text annotations in export:** When “include overlays and ROIs” is selected, look up text annotations for the slice (study/series/slice and scene), draw them on the export image using the text-size formula for font size (config text annotation font size) and config text annotation color; use the same coordinate scaling as ROIs/measurements.
- [x] **Arrow annotations in export:** When “include overlays and ROIs” is selected, look up arrow annotations for the slice, draw them on the export image using the line-thickness formula (e.g. use measurement or a dedicated arrow line-thickness config if present) and config color; use the same coordinate scaling as ROIs/measurements.
- [ ] Add unit tests or export tests that verify annotation pixel sizes follow the formulas (e.g. double image size → line/font sizes scale as specified).

### 6.2 Replace “apply current zoom” with upscale options

- [x] In `export_dialog.py`, remove the “Export at displayed resolution (apply current zoom)” checkbox.
- [x] In `export_dialog.py`, add resolution control: Native, 1.5×, 2×, 4× (combo or radio).
- [x] In `export_dialog.py`, add checkbox “Enlarge line thickness and text size by the same factor” (shown only when 1.5×/2×/4× is selected).
- [x] **Scale limits:** When selection changes, compute max native dimension across selected items. Disable 4× when max dimension > 1024; disable 2× when max dimension > 2048 (output cap 4096). Optionally show tooltip on disabled options (e.g. “Not available: selected images would exceed 4096 px”). Keep 1.5× available for all sizes unless profiling shows need to limit (e.g. when max > 2730).
- [x] In `export_manager.py`, replace `export_at_display_resolution` and `current_zoom`/`initial_fit_zoom` (for resolution) with parameters `export_scale` (1.0, 1.5, 2.0, 4.0) and `scale_annotations_with_image` (bool).
- [x] In `export_slice` / `export_selected`, apply image resize by `export_scale` when > 1.0, and when rendering annotations apply the “enlarge by factor” option.
- [x] Update `dialog_coordinator.open_export()` and `main._open_export()` to stop passing `current_zoom` and `initial_fit_zoom` (or only pass them if still needed for another purpose).
- [ ] Update quick-start guide / README / tooltips that mention “apply current zoom” to describe the new resolution options.
- [ ] Test: export at native and at 1.5×/2×/4× with and without “enlarge annotations” and verify image size and annotation proportions.

### 6.3 Export Screenshots (one file per subwindow; include text/arrow when annotations opted)

- [x] Add menu entry (e.g. File → Export Screenshots) and wire to a new handler.
- [x] Create dialog: select which subwindow(s) to include (checkboxes), output directory, filename prefix, format (PNG/JPG), and “Include annotations” checkbox. **One file per selected subwindow** (no combined image).
- [x] Implement capture: for each selected subwindow with an image, grab the viewport (or render the scene) to a QImage and save as a separate file (e.g. `{prefix}_view{index}.png`).
- [x] Ensure overlays, ROIs, measurements, **text annotations**, and **arrow annotations** are included in the capture when “Include annotations” is checked (verify drawing is on the same viewport/scene so grab includes them; if not, use scene render or composite layer).
- [x] Handle subwindows with no image (disable or hide in the list).
- [x] File naming: one file per subwindow (e.g. prefix + view index + extension); document in UI.
- [ ] Update documentation (README, quick-start, AGENTS.md if needed) for “Export Screenshots.”

### 6.4 Cleanup and docs

- [x] Remove or deprecate any export code paths that only existed for “apply current zoom” (e.g. passing `current_zoom`/`initial_fit_zoom` through the chain).
- [ ] Update `TO_DO.md`: mark the three sub-items (9, 10, 11) as addressed once image export and screenshots include text/arrow when annotations are opted.
- [ ] Add a short “Export” section in dev-docs or user docs describing resolution options, formula-based annotation sizing, inclusion of text/arrow in annotations, and the difference between “Export Images” (tree-based, resolution options) and “Export Screenshots” (one file per subwindow, current display only).

---

## 7. Summary

- **Annotation sizing:** Use **formula-based** sizing with no magnification: line thickness = (1/100)·(setting/2)·(width+height)/2; text size = (1/100)·(setting)·(width+height)/2. When export scale is used and “enlarge by same factor” is checked, multiply these by the scale factor. Implement in `_render_overlays_and_rois` for ROI, measurement, and overlay text; add **text and arrow annotations** to export when user opts to include annotations.
- **Resolution:** Remove “apply current zoom”; add **Native / 1.5× / 2× / 4×** and optional “Enlarge line thickness and text size by the same factor.”
- **Screenshots:** New **Export Screenshots** flow: **one file per selected subwindow**; when “Include annotations” is checked, capture includes overlays, ROIs, measurements, **text annotations**, and **arrow annotations** as displayed.

Implementing 6.1 and 6.2 together keeps the export pipeline consistent; 6.3 can follow or be done in parallel.

---

## 8. How annotations are currently stored (current behavior)

This section documents how ROIs and other annotations are keyed and why export only includes annotations from the **currently focused subwindow**.

### 8.1 Per-subwindow managers

- The application uses **one set of annotation managers per subwindow** (not a single global set).
- For each subwindow (index 0–3), `_initialize_subwindow_managers()` in `main.py` creates:
  - **ROIManager** – stores ROIs keyed by `(study_uid, series_uid, instance_identifier)` where `instance_identifier` is the slice index (array position) for that series.
  - **MeasurementTool** – stores measurements under `(study_uid, series_uid, slice_index)`.
  - **TextAnnotationTool** – stores text annotations per `(study_uid, series_uid, slice_index)`.
  - **ArrowAnnotationTool** – stores arrow annotations per `(study_uid, series_uid, slice_index)`.
- **Series key:** The app uses `get_composite_series_key(dataset)` (SeriesInstanceUID + SeriesNumber when present) so that the same series is consistently keyed across subwindows.
- **Slice key:** Slice is the array index into the series' list of datasets (0, 1, 2, …), set when that subwindow displays a slice via `slice_display_manager` / `set_current_slice`.

### 8.2 Focus and what export receives

- When the user changes focus (clicks another subwindow), `_on_focused_subwindow_changed` runs and the **app's** references (`app.roi_manager`, `app.measurement_tool`, `app.text_annotation_tool`, `app.arrow_annotation_tool`) are updated to **that subwindow's** managers (see `subwindow_lifecycle_controller.on_focused_subwindow_changed`).
- The Export dialog is opened with **only the currently focused subwindow's** `roi_manager`, `overlay_manager`, `measurement_tool`, `text_annotation_tool`, and `arrow_annotation_tool` (passed from `main._open_export()`).
- Therefore, when "Include overlays and ROIs" is checked, **only annotations stored in the focused subwindow's managers** are available. Any slice that was never displayed (and annotated) in that subwindow has no ROIs/measurements/text/arrows in the managers passed to export, so those slices export **without** annotations.

### 8.3 Summary

| Item | Storage | Key | Available to export |
|------|--------|-----|----------------------|
| ROIs | Per subwindow (each has its own ROIManager) | (study_uid, series_uid, slice_index) | Only from **focused** subwindow's manager |
| Measurements | Per subwindow (MeasurementTool) | (study_uid, series_uid, slice_index) | Only from focused subwindow |
| Text annotations | Per subwindow (TextAnnotationTool) | (study_uid, series_uid, slice_index) | Only from focused subwindow |
| Arrow annotations | Per subwindow (ArrowAnnotationTool) | (study_uid, series_uid, slice_index) | Only from focused subwindow |

So annotations are **not** currently stored in a single global store keyed by series/slice; they are stored per subwindow and only the focused subwindow's data is used for export.

---

## 9. Global annotation store: export annotations for all selected slices

**Goal:** When the user checks "Include overlays and ROIs," annotations should be exported for **all** selected slices, not only those from the currently focused subwindow. Annotations should be tracked **per series and slice** and persist even when that slice is not currently loaded in any subwindow, so they can be recalled when the user returns to that slice and can be exported regardless of focus.

### 9.1 Target behavior

- **Single logical store per annotation type** keyed by `(study_uid, series_uid, slice_index)` (using `get_composite_series_key` for series_uid).
- When any subwindow displays a slice, it **reads** annotations from this store for that (study, series, slice). When the user draws/edits/deletes ROIs, measurements, or text/arrow annotations, the app **writes** to this store.
- When exporting with "Include overlays and ROIs," the export path receives (or queries) this **global** store so that every selected slice gets its annotations from the same store, regardless of which subwindow is focused or which subwindow last displayed that slice.
- Annotations persist when switching subwindows or loading different series; when the user later loads that series/slice again (in any subwindow), the annotations reappear.

### 9.2 Implementation options

**Option A – Single global managers (recommended)**  
- One **ROIManager**, one **MeasurementTool**, one **TextAnnotationTool**, one **ArrowAnnotationTool** for the whole application.
- All subwindows use these same instances. When a subwindow displays a slice, it calls `set_current_slice(study_uid, series_uid, slice_index)` on these tools and displays the items returned for that key (e.g. `get_rois_for_slice`). Drawing/editing updates the same managers.
- Export receives these same single managers; every selected slice's annotations are found by (study_uid, series_uid, slice_index).
- **Pros:** Simple model; export "include annotations for all" works by default. **Cons:** Requires refactor so that per-subwindow managers are removed and all coordinators use the global managers with the correct (study, series, slice) context per subwindow.

**Option B – Aggregate lookup for export only** *(implemented)*  
- Keep per-subwindow managers as they are.
- For export only: when building overlay/ROI/measurement/text/arrow data for a slice, **aggregate** from all subwindow managers: e.g. for (study_uid, series_uid, slice_index), call `get_rois_for_slice` on each subwindow's roi_manager and merge (or take the first non-empty). Pass either a single "aggregate" provider into the export dialog or have the export manager accept a list of managers and try each until it gets data for that slice.
- **Pros:** Smaller change, no refactor of display/drawing. **Cons:** Annotations are still tied to "which subwindow had this slice displayed"; if no subwindow ever displayed that slice with annotations, there is nothing to export. Does not fully meet "keep track per series/slice even when not loaded."
- **Implementation:** `main._open_export()` builds a list of per-subwindow dicts (roi_manager, measurement_tool, text_annotation_tool, arrow_annotation_tool) and passes it to the Export dialog. `ExportManager._render_overlays_and_rois()` accepts optional `subwindow_annotation_managers`; when provided, it aggregates ROIs, measurements, text items, and arrow items from all subwindows for the current (study_uid, series_uid, slice_index) and draws them. Options A and C remain available to explore if Option B is not satisfactory.

**Option C – Global store with per-subwindow display cache**  
- Introduce a global store (e.g. one ROIManager, one MeasurementTool, etc., or a dedicated AnnotationStore) keyed by (study_uid, series_uid, slice_index). Per-subwindow managers become thin wrappers that read/write this store and only hold "current slice" context and scene items for display.
- Export reads from the global store. Display and drawing logic are updated to go through this store.
- **Pros:** Clear separation; persistence and export semantics are central. **Cons:** Larger refactor than Option A; similar scope to Option A.

Recommendation: **Option A** (single global managers) for a clear, consistent model and straightforward export-for-all behavior. If the codebase already wires everything through a "focused" subwindow's managers, the change is to stop creating per-subwindow ROI/measurement/annotation tools and instead use one set of tools and pass the correct (study_uid, series_uid, slice_index) per subwindow when displaying or editing.

### 9.3 Checklist (global annotation store and export for all)

- [x] **Option B – Export path:** Pass a list of per-subwindow annotation managers into the Export dialog; `export_slice` / `_render_overlays_and_rois` aggregate ROIs, measurements, text annotations, and arrow annotations from all subwindows for each (study_uid, series_uid, slice_index) when "Include overlays and ROIs" is checked.
- [ ] **Design (Option A/C):** If Option B is not satisfactory, decide Option A or C and document where the single global store (or aggregate) lives and how subwindows get (study_uid, series_uid, slice_index) when displaying/editing.
- [ ] **ROIs (Option A/C):** For a single store, ensure ROIs are stored and retrieved by (study_uid, series_uid, slice_index); when a subwindow displays a slice, show ROIs from that store; when the user draws/edits, update that store. *(Option B uses per-subwindow stores and aggregates at export only.)*
- [ ] **Measurements (Option A/C):** Same as ROIs for a single store. *(Option B: aggregated at export.)*
- [ ] **Text annotations (Option A/C):** Same as ROIs/measurements for a single store. *(Option B: aggregated at export.)*
- [ ] **Arrow annotations (Option A/C):** Same as text annotations. *(Option B: aggregated at export.)*
- [ ] **Persistence when not loaded:** Ensure that once annotations are stored for a (study, series, slice), they remain in the store when the user switches subwindows or loads another series; when the user later loads that series/slice again (in any subwindow), annotations are shown and can be exported. *(Option B does not add persistence; annotations remain per subwindow.)*
- [ ] **Tests:** Add or update tests that export multiple slices from different series/subwindows and verify annotations appear on all slices when "Include overlays and ROIs" is checked (and that they are keyed by series/slice, not by subwindow).

---

## 10. Export dialog: window/level label clarification

- [x] In the Export dialog, change the first window/level radio label from "Use current viewer window/level" to **"Use currently focused sub-window window/level"** and append in parentheses which subwindow and the current window/level values, e.g. **(sub-window 1 - 44/486)** (center/width). This makes it explicit that the option applies only to the focused sub-window and shows the values that will be applied.
- Implementation: Pass `focused_subwindow_index` (0-based) and `current_window_center`, `current_window_width` into the dialog; set the radio text to e.g. "Use currently focused sub-window window/level (sub-window N - C/W)" when values are available; otherwise keep a shorter label and disable the option.
