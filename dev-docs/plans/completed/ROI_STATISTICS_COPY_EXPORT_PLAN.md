# Copy and Export ROI Statistics – Implementation Plan

This document is an implementation plan for adding **Copy** and **Export** of ROI statistics, as specified in [TO_DO.md](../TO_DO.md) (lines 13–15).

**References:**
- Requirements: `dev-docs/TO_DO.md` (Copy + Export ROI Statistics)
- ROI statistics panel: `src/gui/roi_statistics_panel.py` (ROIStatisticsPanel, QTableWidget)
- ROI/crosshair data: `src/tools/roi_manager.py` (ROIManager, ROIItem, calculate_statistics), `src/tools/crosshair_manager.py` (CrosshairManager, CrosshairItem)
- Coordinator and right panel: `src/gui/roi_coordinator.py`, `src/main.py` (right panel tabs, roi_statistics_panel)
- Tools menu and context menu: `src/gui/main_window_menu_builder.py`, `src/gui/image_viewer.py` (context menu when right-click on image)
- Export patterns: `src/gui/dialogs/tag_export_dialog.py` (series selection, format, default filename with AccessionNumber), `src/gui/dialog_coordinator.py` (open_tag_export)
- Studies and subwindow managers: `src/main.py` (current_studies, subwindow_managers with roi_manager/crosshair_manager per subwindow)
- Patient coordinates: `src/utils/dicom_utils.py` (pixel_to_patient_coordinates), `src/gui/crosshair_coordinator.py` (patient coords appended to crosshair text)

---

## 1. Overview of Features

| Feature | Description |
|--------|-------------|
| **Copy** | User can select the ROI statistics in the right pane and copy them (Ctrl+C or right-click "Copy"). Copied content is the currently displayed statistics as text (statistic name and value, tab-separated, row per statistic), including units (e.g. HU) exactly as shown in the table. |
| **Export** | "Export ROI Statistics..." in **Tools** menu and in **image viewer context menu**. Opens a dialog to choose format (TXT, CSV, XLSX), select one or more series to export, and choose file path/name. Default filename: `{AccessionNumber} ROI stats` (or `{PatientID} ROI stats` if Accession is blank). Output is grouped by series → slice/frame → ROI/crosshair, with all stats for ellipse/rectangle ROIs and pixel + patient coordinates for crosshairs. |

---

## 2. Scope and Out-of-Scope

**In scope**
- **Copy:** Make ROI statistics table rows selectable and copyable (keyboard Ctrl+C and right-click context menu). Copy selected rows or full current stats to clipboard, including units as shown.
- **Export:** New "Export ROI Statistics..." action in Tools menu and in image viewer context menu. New dialog: format (TXT, CSV, XLSX), a "Use rescaled values (e.g. HU) if available" checkbox, multi-series selection (with ROI/crosshair counts shown), file path/name (default: Accession + " ROI stats" or Patient ID + " ROI stats"). Export logic aggregates ROI/crosshair data from all subwindow managers for selected series; recomputes ROI stats per slice (always fresh); includes crosshair pixel (x, y, z slice-index) and patient coordinates (always recomputed from raw coords, not parsed from display string).
- Documentation: Update Quick Start Guide and README/AGENTS if relevant; update TO_DO checklist when done.

**Out of scope**
- Changing how ROI or crosshair data are stored or keyed.
- Export of measurements or other annotations (only ROI statistics and crosshair coordinates).
- Changing default visibility of the ROI Statistics tab in the right panel.

---

## 3. Principles

- **Backups:** Per project rules, back up every code file before modifying it (in `backups/`). All files requiring modification are listed in checklist item E0.
- **No artificial test changes:** Do not alter tests solely to make them pass; fix behavior or document gaps.
- **Consistency:** Copy/Export behavior and wording should match existing patterns (e.g. Export DICOM Tags, tag viewer Copy).
- **Accessibility:** Dialogs and file pickers should appear in focus and on top per user rules. File pickers should not stay on top after another window is focused.

---

## 4. Current Behavior (Relevant Code)

- **ROIStatisticsPanel:** Uses `QTableWidget` with 2 columns ("Statistic", "Value") and 6 rows (Mean, Std Dev, Min, Max, Pixels, Area). `setEditTriggers(NoEditTriggers)`. No explicit selection mode set (default is single-item). `update_statistics()` / `clear_statistics()` update display; `current_statistics` holds the last stats dict; value cells already contain formatted text including units (e.g. `"45.32 HU"` or `"12.50 cm²"`). The title label shows the ROI identifier.
- **ROI data:** `ROIManager.rois` is `Dict[(study_uid, series_uid, instance_identifier), List[ROIItem]]`. Each subwindow has its own `roi_manager` in `subwindow_managers[idx]`. App-level `self.roi_manager` switches to the focused subwindow's manager. `ROIItem.shape_type` is `"ellipse"` or `"rectangle"`. `ROIItem.statistics` caches the last-computed stats dict (may be `None` if the ROI was never selected in the viewer, or stale if rescale settings changed). Stats are computed by `roi_manager.calculate_statistics(roi, pixel_array, rescale_slope, rescale_intercept, pixel_spacing)` → returns `{mean, std, min, max, count, area_pixels, area_mm2}`.
- **Crosshair data:** `CrosshairManager.crosshairs` keyed same as ROI manager. `CrosshairItem` stores `x_coord`, `y_coord`, `z_coord` (all 0-based slice array indices/pixel coordinates), and `pixel_value_str` (a human-readable display string that may already embed patient coords as a substring — do **not** parse this string for export). Patient coordinates are obtained fresh via `pixel_to_patient_coordinates(dataset, x_coord, y_coord, z_coord)`.
- **Series/studies:** `app.current_studies` is `{study_uid: {series_uid: [Dataset]}}`. Tag export uses this for series tree and default filename (AccessionNumber from first dataset). Export dialog receives `current_studies` from `dialog_coordinator`.
- **Default filename:** Tag export uses `f"{modality} DICOM Tag Export {accession}.xlsx"`. For ROI stats: `f"{accession} ROI stats.{ext}"`, falling back to `f"{patient_id} ROI stats.{ext}"` when AccessionNumber is blank, then `"ROI_stats.{ext}"` if both are blank.
- **Subwindow ROI uniqueness:** Each subwindow holds entirely separate `ROIItem` and `CrosshairItem` instances. Two subwindows displaying the same series each have their own manager and their own ROI objects — there is no shared object to deduplicate. All ROIs from all subwindows for a given (study, series, slice) key are distinct annotations placed by the user in different windows and should all be exported.
- **Rescale:** Rescale slope/intercept/type are per-subwindow (`view_state_manager.use_rescaled_values`). There is no single app-wide "use rescaled" flag, so the export dialog should offer an explicit checkbox rather than trying to infer the global setting.

---

## 5. Copy Feature – Design

### 5.1 Behavior
- User focuses the ROI Statistics panel (right pane, ROI Statistics tab).
- User selects one or more **rows** in the statistics table (each row = one statistic, e.g. "Mean | 45.32 HU").
- **Copy** (Ctrl+C or right-click → "Copy") copies selected rows to the system clipboard as plain text: each row as `{Statistic name}\t{Value}`, rows separated by newlines. This format pastes cleanly into Notepad, Excel, etc.
- If no rows are selected, copy the entire current table (all 6 stat rows) as formatted text, prepended with the ROI identifier line (from the title label, e.g. `ROI Statistics - ROI 1 (ellipse)`).
- If the panel is empty (no ROI selected), Copy silently does nothing (no error, no empty clipboard write).
- Values are copied exactly as displayed (already include units such as "HU", "cm²", "pixels").

### 5.2 Implementation Notes
- **ROIStatisticsPanel:** Change selection to `setSelectionBehavior(SelectRows)` and `setSelectionMode(ExtendedSelection)` so users naturally select whole Statistic+Value row pairs. Keep `NoEditTriggers`. Row selection is more ergonomic than cell selection for this 2-column table.
- **Copy source:** Use `item.text()` from the displayed table cells — this already contains formatted values with units. Do **not** re-read from `current_statistics` dict (which lacks units).
- **Context menu:** Add right-click context menu on `stats_table` with a single "Copy" action. Connect to a shared `_copy_stats_to_clipboard()` method on `ROIStatisticsPanel`.
- **Ctrl+C:** Override `keyPressEvent` on the panel (or install an event filter on the table) to intercept Ctrl+C and call the same `_copy_stats_to_clipboard()` method. This ensures it works whether the panel widget or the table widget has keyboard focus.
- **Clipboard:** Use `QApplication.clipboard().setText(text)` (see `tag_viewer_dialog.py` lines 601, 623 for existing clipboard usage pattern).
- **Build text:** Iterate `stats_table.selectedRanges()` to find selected rows; if empty, use all rows 0–5. For each row, get `stats_table.item(row, 0).text()` and `stats_table.item(row, 1).text()` and join with `\t`.

---

## 6. Export Feature – Design

### 6.1 Menu and Context
- **Tools menu:** Add action "Export ROI Statistics..." after the existing "Histogram..." action. Connect to a new main window signal `export_roi_statistics_requested`. In `main.py`, connect this signal to a handler that calls `dialog_coordinator.open_export_roi_statistics(...)`. Always show the menu item; guard in the handler (show a message if no studies are loaded, matching how tag export is handled in `dialog_coordinator`).
- **Image viewer context menu:** In `image_viewer.py`, add a new signal `export_roi_statistics_requested = Signal()` to `ImageViewer`. In the image context menu (right-click on image, not on ROI), add "Export ROI Statistics..." in the same section as "Annotation Options". In `main.py`, connect this `ImageViewer` signal to the same handler as above. This is consistent with how other viewer signals (e.g. `histogram_requested`) are wired.

### 6.2 Export Dialog (`export_roi_statistics_dialog.py`)
- **Title:** "Export ROI Statistics"
- **Series selection panel (left):** Tree widget with study → series hierarchy, mirroring TagExportDialog. Show all loaded series from `current_studies`. Each series item includes a suffix showing the annotation count, e.g. `Series 3: Ax T1  (2 ROIs, 1 crosshair)` — series with no annotations still appear but the suffix is omitted or shows `(0)`. Multi-select with "Select All" / "Deselect All" buttons.
- **Options panel (right):**
  - **Format:** Radio buttons or combo: TXT, CSV, XLSX.
  - **Rescale:** Checkbox "Use rescaled values (e.g. HU) if available" — checked by default when any loaded series has rescale parameters (slope/intercept). When checked, `DICOMProcessor.get_rescale_parameters(dataset)` values are used in `calculate_statistics`; when unchecked, raw pixel values are exported.
  - **File path:** Line edit (editable) + "Browse…" button (opens `QFileDialog.getSaveFileName`). File dialog and dialog window are raised and focused per user rules; they do not stay on top.
- **Default filename (computed once dialog opens, updated if format radio changes):** From the first selected series' first dataset: use `AccessionNumber` if non-empty, else `PatientID`, else `"ROI_stats"`. Append `" ROI stats"`. Append extension from current format selection (`.txt`, `.csv`, `.xlsx`). Sanitize: strip or replace characters not valid in filenames (`/ \ : * ? " < > |`). When the user changes format, update only the extension in the file path field automatically.
- **Buttons:** "Export" and "Cancel". "Export" validates that at least one series is selected and a file path is set, then calls the export service; closes on success. On error, shows a clear error dialog and keeps the export dialog open so the user can fix the path and retry.

### 6.3 Export Data Structure (Hierarchy)

Output at all three format levels follows this hierarchy:

1. **Series** – Header: `Series {SeriesNumber}: {SeriesDescription}` (from `getattr(dataset, 'SeriesNumber', '')` and `getattr(dataset, 'SeriesDescription', '')`).
2. **Slice/Frame** – Header: `Slice Index: {z}` (where `z` is the 0-based slice array index, labelled explicitly as "Slice Index (0-based)" to distinguish it from DICOM `InstanceNumber`). Only slices that have at least one ROI or crosshair are included in TXT and XLSX output; empty slices are silently skipped for readability. (In CSV, empty slices produce no rows — also clean by default.)
3. **ROI or Crosshair** – Numbered within each slice, separately for ROIs and crosshairs:
   - **Ellipse/Rectangle ROI:** Heading e.g. `Ellipse ROI 1`, `Rectangle ROI 2`. Data rows: Mean, Std Dev, Min, Max, Pixels (count), Area (pixels), Area (mm²). Include rescale unit suffix (e.g. "HU") on value rows when rescaled export is selected.
   - **Crosshair:** Heading e.g. `Crosshair 1`. Data rows: Pixel X (column), Pixel Y (row), Slice Index (z, 0-based), Pixel Value (from `pixel_value_str` — the raw value portion only, not the embedded patient coord string), Patient X (mm), Patient Y (mm), Patient Z (mm). Patient coordinates are computed fresh via `pixel_to_patient_coordinates(dataset, x_coord, y_coord, z_coord)`; if the function returns `None` (missing DICOM spatial metadata), mark as "N/A".

### 6.4 Export Logic (Aggregation and Computation)

**Inputs:** Selected series `[(study_uid, series_uid), ...]`, format, file path, use-rescale flag, from app: `current_studies`, `subwindow_managers`, `DICOMProcessor`.

**Aggregation (per slice):** For each selected `(study_uid, series_uid)`, get `series_datasets = current_studies[study_uid][series_uid]`. For each slice index `z` in `range(len(series_datasets))`, collect:
- All `ROIItem` objects from every `subwindow_managers[idx]['roi_manager'].rois.get((study_uid, series_uid, z), [])` across all subwindow indices.
- All `CrosshairItem` objects from every `subwindow_managers[idx]['crosshair_manager'].crosshairs.get((study_uid, series_uid, z), [])` across all subwindow indices.

Because each subwindow has entirely separate `ROIItem`/`CrosshairItem` instances (different Python objects, never shared), collecting from all subwindows requires no deduplication — every item is a unique user-placed annotation.

**ROI stats computation:** For each `ROIItem`:
- Do **not** use `roi.statistics` (the cached value). It may be `None` (never selected in viewer) or stale (rescale settings may have changed since it was last computed).
- Always recompute: `dataset = series_datasets[z]`, `pixel_array = DICOMProcessor.get_pixel_array(dataset)`, `pixel_spacing = get_pixel_spacing(dataset)`. If use-rescale is checked: `rescale_slope, rescale_intercept, rescale_type = DICOMProcessor.get_rescale_parameters(dataset)`, else `rescale_slope = rescale_intercept = rescale_type = None`.
- Call any ROIManager instance's `calculate_statistics(roi, pixel_array, rescale_slope, rescale_intercept, pixel_spacing)` — the method only uses its arguments, not manager-level state. Calling it on `subwindow_managers[0]['roi_manager']` or any valid manager instance is fine.

**Crosshair coords:** For each `CrosshairItem`, use `item.x_coord`, `item.y_coord`, `item.z_coord` (raw integers). Do **not** parse `item.pixel_value_str` for coordinates — this string is a human-readable display string that embeds patient coords as a substring in varying formats. Always call `pixel_to_patient_coordinates(series_datasets[z], item.x_coord, item.y_coord, item.z_coord)` fresh.

**Output format details:**
- **TXT:** Section headers (series, then slice, then ROI/crosshair) separated by blank lines and dashes. Key–value lines indented. Example:
  ```
  ============================================================
  Series 3: Ax T1
  ============================================================
    Slice Index (0-based): 5
    ----------------------------------------
    Ellipse ROI 1
      Mean:     45.32 HU
      Std Dev:   8.14 HU
      ...
    Crosshair 1
      Pixel X:   120
      Pixel Y:    85
      ...
  ```
- **CSV:** One data row per ROI summary or per crosshair. Columns (blanks where not applicable):
  `Study UID, Series Number, Series Description, Slice Index (0-based), ROI Type, ROI Index, Mean, Std Dev, Min, Max, Pixels, Area (pixels), Area (mm²), Rescale Unit, Pixel X, Pixel Y, Pixel Z, Pixel Value, Patient X (mm), Patient Y (mm), Patient Z (mm)`.
  ROI rows fill stat columns and leave coordinate/pixel value columns blank. Crosshair rows fill coordinate/pixel value columns and leave stat columns blank.
- **XLSX:** One sheet per study (sheet named after `StudyDescription`, max 31 chars, sanitized). Within each sheet: bold merged-cell headers for each series, indented slice headers, bold ROI/crosshair headings, data rows. Use bold formatting for headers, matching `tag_export_dialog.py` style.

### 6.5 Dependencies
- **openpyxl** for XLSX (already in project for tag export).
- **csv** (standard library) for CSV.
- `DICOMProcessor.get_pixel_array`, `DICOMProcessor.get_rescale_parameters`.
- `get_pixel_spacing` from `utils.dicom_utils`.
- `pixel_to_patient_coordinates` from `utils.dicom_utils`.

### 6.6 Edge Cases
- **No studies loaded:** Keep "Export ROI Statistics..." always visible in the Tools menu. Guard in the handler: if `current_studies` is empty, show an informational message (matching `dialog_coordinator.open_tag_export` pattern) and do not open the export dialog.
- **No ROIs/crosshairs for selected series:** TXT/XLSX output contains only the series header (with a note "No annotations"). CSV produces no data rows. Do not treat this as an error.
- **Multiple subwindows, same series:** Aggregate all ROIs/crosshairs from all subwindow managers — each is a distinct user-placed annotation. No deduplication needed (see section 6.4).
- **AccessionNumber and PatientID both empty:** Default filename falls back to `"ROI_stats.{ext}"`.
- **Missing DICOM spatial metadata (no patient coords for crosshair):** Mark patient coordinate columns as "N/A" in all formats.
- **Write error (permissions, disk full):** Show a clear error dialog; keep the export dialog open so the user can change the path and retry.
- **Very large exports:** No pagination; export all selected slices and ROIs. Add a progress dialog later if performance becomes an issue.

---

## 7. File and Signal Changes (Summary)

| Location | Change |
|----------|--------|
| `src/gui/roi_statistics_panel.py` | Enable row selection on stats table (`SelectRows`, `ExtendedSelection`); add right-click context menu "Copy"; override `keyPressEvent` (or event filter) for Ctrl+C; implement `_copy_stats_to_clipboard()` using `item.text()` from table cells. |
| `src/gui/main_window.py` | New signal `export_roi_statistics_requested`. |
| `src/gui/main_window_menu_builder.py` | Add "Export ROI Statistics..." under Tools menu after Histogram; connect to `export_roi_statistics_requested`. |
| `src/gui/image_viewer.py` | Add signal `export_roi_statistics_requested = Signal()` to `ImageViewer`; add "Export ROI Statistics..." to image context menu; emit signal when triggered. |
| `src/main.py` | Connect both `main_window.export_roi_statistics_requested` and each `image_viewer.export_roi_statistics_requested` to a handler that calls `dialog_coordinator.open_export_roi_statistics(...)`, passing `current_studies`, `subwindow_managers`, config. |
| `src/gui/dialog_coordinator.py` | New method `open_export_roi_statistics(current_studies, subwindow_managers, config_manager)`: guard on empty studies, then instantiate and show `ExportROIStatisticsDialog`. |
| **New:** `src/gui/dialogs/export_roi_statistics_dialog.py` | Dialog UI: series tree (with annotation counts), format choice, rescale checkbox, file path + Browse, Export/Cancel. Implements or calls export logic. Default filename from first selected series (Accession or Patient ID) + " ROI stats". Updates extension automatically when format changes. |
| **New:** `src/core/roi_export_service.py` | Aggregation + computation + file-writing logic (TXT, CSV, XLSX). Keeps dialog thin and export logic testable. |

---

## 8. To-Do Checklist

Use this checklist when implementing; mark items complete only after they are fully done and verified.

### Preparation (all features)
- [ ] **E0** Back up all files that will be modified before beginning any edits:
  - `src/gui/roi_statistics_panel.py`
  - `src/gui/main_window.py`
  - `src/gui/main_window_menu_builder.py`
  - `src/gui/image_viewer.py`
  - `src/main.py`
  - `src/gui/dialog_coordinator.py`

### Copy
- [x] **C1** In `roi_statistics_panel.py`, set `setSelectionBehavior(SelectRows)` and `setSelectionMode(ExtendedSelection)` on `stats_table`. Keep `NoEditTriggers`. Confirm rows are visually selectable.
- [x] **C2** Implement `_copy_stats_to_clipboard(self)` on `ROIStatisticsPanel`: collect selected rows via `stats_table.selectedRanges()`; if none selected and `current_statistics` is not None, use all 6 rows (prepend ROI identifier line from title label); if panel is empty, return without writing to clipboard. Build text as `"{col0}\t{col1}\n"` per row using `item.text()` (preserves displayed units). Write to `QApplication.clipboard().setText(text)`.
- [x] **C3** Add right-click context menu on `stats_table` with a single "Copy" action connected to `_copy_stats_to_clipboard()`.
- [x] **C4** Override `keyPressEvent` on `ROIStatisticsPanel` (or install an event filter on `stats_table`) to intercept `QKeySequence.Copy` (Ctrl+C / Cmd+C) and call `_copy_stats_to_clipboard()`.
- [ ] **C5** Verify: select one row → copy → paste in text editor shows correct tab-separated line. Select multiple rows → same. No selection → copy entire table including ROI identifier. Empty panel → nothing copied, no error.

### Export – Preparation and entry points
- [x] **E1** Add `export_roi_statistics_requested = Signal()` to `MainWindow` in `main_window.py`.
- [x] **E2** In `main_window_menu_builder.py`, add Tools menu action "Export ROI Statistics..." after Histogram; connect to `main_window.export_roi_statistics_requested`.
- [x] **E3** In `image_viewer.py`, add `export_roi_statistics_requested = Signal()` to `ImageViewer`; add "Export ROI Statistics..." to the image context menu (in the section near Annotation Options); connect the menu action to emit `self.export_roi_statistics_requested`.
- [x] **E4** In `main.py`, in the subwindow setup, connect each `image_viewer.export_roi_statistics_requested` to the export handler. Also connect `main_window.export_roi_statistics_requested` to the same handler. The handler should call `dialog_coordinator.open_export_roi_statistics(current_studies, subwindow_managers, config_manager)`. (Image viewer connections are in `subwindow_lifecycle_controller.connect_all_subwindow_context_menu_signals`.)

### Export – Dialog
- [x] **E5** Create `src/gui/dialogs/export_roi_statistics_dialog.py` with `ExportROIStatisticsDialog(QDialog)`. UI: left panel = series tree (study → series, multi-select, "Select All" / "Deselect All" buttons; suffix each series with annotation count, e.g. `(2 ROIs, 1 crosshair)`, by scanning all subwindow managers). Right panel = format selection (TXT / CSV / XLSX radio or combo), rescale checkbox "Use rescaled values (e.g. HU) if available" (default checked if any dataset has rescale params), file path line edit + "Browse…" button. Bottom = "Export" and "Cancel". Set `setModal(True)`. Raise and activate on open.
- [x] **E6** Default filename: from first selected series' first dataset, use `AccessionNumber` if non-empty, else `PatientID`, else `"ROI_stats"`; append `" ROI stats"` when a series is selected; append format extension. Sanitize (strip `/ \ : * ? " < > |`). When format selection changes, update only the extension portion of the file path field automatically.
- [x] **E7** Add `open_export_roi_statistics(self, current_studies, subwindow_managers, config_manager)` to `dialog_coordinator.py`. Guard: if `not current_studies`, show "Please load DICOM files before exporting ROI statistics." and return. Otherwise instantiate and exec `ExportROIStatisticsDialog`.

### Export – Aggregation, computation, and service
- [x] **E8** Create `src/core/roi_export_service.py` with a function `collect_roi_data(selected_series, current_studies, subwindow_managers)` that returns a structured representation: for each `(study_uid, series_uid)`, for each slice index `z` with at least one ROI or crosshair, lists of `ROIItem` and `CrosshairItem` objects. Collects from all subwindow manager roi/crosshair dicts using the key `(study_uid, series_uid, z)`. No deduplication (each object is a distinct annotation). Selected series with no annotations are included with empty slice list.
- [x] **E9** In `roi_export_service.py`, implement `compute_roi_statistics(roi_item, dataset, use_rescale)`: always recomputes from pixel array (never uses `roi_item.statistics` cache, which may be `None` or stale); calls `DICOMProcessor.get_pixel_array(dataset)`, `get_pixel_spacing(dataset)`, and if `use_rescale` is True calls `DICOMProcessor.get_rescale_parameters(dataset)` for slope/intercept; then calls `any_roi_manager_instance.calculate_statistics(roi, pixel_array, ...)`. Note in comments that `calculate_statistics` does not use manager-level state.
- [x] **E10** In `roi_export_service.py`, implement crosshair data extraction: for each `CrosshairItem`, use `item.x_coord`, `item.y_coord`, `item.z_coord` (raw integers — 0-based slice index; label as such in output). Call `pixel_to_patient_coordinates(dataset, x_coord, y_coord, z_coord)` fresh; if it returns `None` (missing spatial metadata), use `None` → output as "N/A". **Do not parse `item.pixel_value_str`** for coordinates.

### Export – Output format and writing
- [x] **E11** Implement TXT writer in `roi_export_service.py`: per hierarchy (series header → slice header → ROI/crosshair heading → indented key–value lines). Separate sections with blank lines and dashes. Skip slices with no annotations. Label z as `Slice Index (0-based): {z}`. Include rescale unit (e.g. "HU") in ROI value lines when use-rescale is True.
- [x] **E12** Implement CSV writer: one row per ROI or per crosshair. Columns: `Study UID, Series Number, Series Description, Slice Index (0-based), ROI Type, ROI Index, Mean, Std Dev, Min, Max, Pixels, Area (pixels), Area (mm²), Rescale Unit, Pixel X, Pixel Y, Pixel Z, Pixel Value, Patient X (mm), Patient Y (mm), Patient Z (mm)`. ROI rows leave coordinate columns blank; crosshair rows leave stat columns blank. Write header row first.
- [x] **E13** Implement XLSX writer using openpyxl: one sheet per study (name from `StudyDescription`, max 31 chars, sanitized). Bold merged-cell series header rows; indented slice header rows; bold ROI/crosshair sub-headers; data rows. Skip slices with no annotations. Follow bold/merge style of `tag_export_dialog.py`.

### Export – Edge cases and polish
- [x] **E14** Verify edge case: no ROIs/crosshairs for selected series → TXT/XLSX contain series header with note "No annotations"; CSV produces header row only. No error raised.
- [x] **E15** Verify edge case: write error (e.g. read-only path) → show error dialog with message; keep export dialog open so user can change path and retry.
- [x] **E16** After successful export, optionally show brief success message (or status in dialog) and close. Save the export directory to `config_manager` last-export-path (or a new dedicated key `last_roi_stats_export_path`) so Browse defaults to the same folder next time.

### Documentation and TO_DO
- [x] **D1** Update Quick Start Guide (`quick_start_guide_dialog.py`) to mention "Export ROI Statistics..." under Tools menu. Update README or AGENTS.md if those documents list Tools menu features.
- [x] **D2** When both Copy and Export are implemented and verified, update `dev-docs/TO_DO.md` and mark the Copy and Export ROI Statistics items complete.

---

## 9. Testing Suggestions

- **Copy:** Select one row, multiple rows, no selection (should copy all), empty panel (should copy nothing). Trigger via right-click context menu and Ctrl+C. Paste into Notepad and into Excel and verify tab-separated format and correct units.
- **Export – basic:** Load a study; add ellipse, rectangle, and crosshair ROIs on several slices of one series. Export to TXT, CSV, and XLSX. Verify hierarchy (series → slice → ROI), correct stat values, correct units when rescale is checked vs. unchecked, crosshair coordinates present, patient coords or "N/A" as appropriate.
- **Export – multi-series:** Select multiple series. Verify all series appear in output. Verify annotation counts shown in series tree match actual output.
- **Export – multi-subwindow:** Open two subwindows with the same series, draw ROIs in each. Export and confirm ROIs from both subwindows appear.
- **Export – defaults:** Test default filename with AccessionNumber present, with it absent (PatientID), and with both absent (fallback). Verify extension updates when format changes.
- **Export – empty series:** Select a series with no ROIs. Verify graceful output (series header only or no data rows) and no crash.
- **Export – write error:** Point to a read-only path. Verify clear error message and dialog stays open.

---

## 10. Estimated Effort

| Area | Effort |
|------|--------|
| Copy (row selection + context menu + Ctrl+C) | Small |
| Export dialog UI + series annotation counts + default filename | Small–Medium |
| Export aggregation + ROI stats recomputation service | Medium |
| Export TXT/CSV/XLSX writing | Medium |
| Menu and context wiring + edge cases + docs | Small |
| **Total** | **Medium** |
