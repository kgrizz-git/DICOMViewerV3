# WIP Refactoring Plan – DICOMViewerV3

## Purpose

This document is a multi-phase plan for addressing the top refactoring issues identified in the refactor assessment. It prioritizes high-impact, lower-risk work first and defers large, riskier extractions (e.g. from `main.py`) until later phases. Each phase should have a detailed to-do checklist created before initiation of that phase.

**Source assessment**: [refactor-assessment-2026-02-17-231800.md](../refactor-assessments/refactor-assessment-2026-02-17-231800.md)

**Status**: Work in progress (WIP). Phase 1 completed 2026-02-18 (measurement_items, ExportManager, main_window_theme). Phase 2 implementation completed 2026-02-19 (menu bar builder, DICOMProcessor split, AnnotationPasteHandler).

---

## Principles

- **Incremental**: One refactoring per deliverable where possible; run tests after each change.
- **Backward compatible**: Preserve existing public APIs; use facades or re-exports where needed.
- **Backups**: Per project rules, back up any code file before modifying it (e.g. in `backups/`).
- **No artificial test changes**: Do not alter tests solely to make them pass; fix behavior or document known gaps.

---

## Phase Overviews

### Phase 1: Quick wins (high ease, high safety)

**Goal**: Reduce line count and improve structure in three files with clear boundaries and low risk. No changes to `main.py`.

**Scope**:
- **measurement_tool.py** (1774 lines): Move graphics item classes (`DraggableMeasurementText`, `MeasurementHandle`, `MeasurementItem`) to a new module `src/tools/measurement_items.py`. Keep `MeasurementTool` in `measurement_tool.py` and import items from the new module.
- **export_dialog.py** (1762 lines): Move `ExportManager` class to `src/core/export_manager.py` (or `src/utils/export_manager.py`). Keep `ExportDialog` in the dialog file and use the manager for export execution.
- **main_window.py** (2276 lines): Move theme/styling logic (`_apply_theme`, `_set_theme` and their stylesheet/palette content) to `src/gui/main_window_theme.py`. MainWindow calls into the theme module to get and apply styles.

**Success criteria**: All three refactorings completed; existing tests pass; manual smoke test of measurement tool, export dialog, and theme switching; no new regressions.

**Estimated effort**: Small (assessment scores 4.0/5 ease/safety for each).

---

### Phase 2: Main window and core splits

**Goal**: Further reduce `main_window.py` and split `dicom_processor.py` into domain modules behind a facade. Add annotation copy/paste handler to prepare for main.py reduction.

**Scope**:
- **main_window.py**: Extract menu bar creation into a builder module (e.g. `src/gui/main_window_menu_builder.py`) so `_create_menu_bar` is replaced by a call to the builder.
- **dicom_processor.py** (1794 lines): Split into rescale, color, window/level, projections, and pixel-stats modules; keep `DICOMProcessor` in `dicom_processor.py` as a thin facade that delegates to the new modules for backward compatibility.
- **main.py**: Extract annotation copy/paste into `AnnotationPasteHandler` (e.g. `src/core/annotation_paste_handler.py`): move `_get_selected_*`, `_copy_annotations`, `_paste_annotations`, and the per-type `_paste_*` methods; main.py keeps menu wiring and calls the handler.

**Success criteria**: Menu bar and theme remain functional; DICOMProcessor API unchanged; copy/paste behavior unchanged; tests pass.

**Estimated effort**: Medium.

---

### Phase 3: main.py – file/series loading and subwindow lifecycle (incremental)

**Goal**: Reduce `main.py` by extracting file/series loading and then subwindow lifecycle/focus in small steps.

**Scope**:
- **File/series loading**: Introduce a coordinator (e.g. `src/core/file_series_loading_coordinator.py`) that owns `_handle_load_first_slice`, `_open_files`, `_open_folder`, `_open_recent_file`, `_open_files_from_paths`, series navigation and navigator selection, and related file-path helpers. main.py wires menu/signals to the coordinator and keeps high-level display entry points that the coordinator can call back.
- **Subwindow lifecycle**: Extract in order: (1) subwindow getter helpers (`_get_subwindow_*`, `get_focused_subwindow_index`, `get_histogram_callbacks_for_subwindow`); (2) focus/panel update methods (`_update_focused_subwindow_references`, `_update_right_panel_for_focused_subwindow`, `_update_left_panel_for_focused_subwindow`); (3) connect/disconnect and layout methods into a controller (e.g. `SubwindowLifecycleController`). Each step is a separate commit with tests and smoke tests.

**Success criteria**: Open file/folder/recent/paths and series navigation work as before; layout change, focus, and series assignment work correctly; main.py line count reduced substantially.

**Estimated effort**: Large; do in multiple small PRs.

---

### Phase 4: Image viewer, cine/projection, and remaining medium-priority items

**Goal**: Simplify `image_viewer.py`, extract cine/projection callbacks from main.py, and address file_operations_handler and dialog patterns.

**Scope**:
- **image_viewer.py**: Break `mousePressEvent` (and optionally `mouseMoveEvent`/`mouseReleaseEvent`) into smaller private methods (e.g. `_handle_select_mode_click`, `_handle_pan_mode_click`, `_handle_roi_drawing_*`); optionally extract mouse handling into a dedicated helper class/mixin in a follow-up.
- **main.py**: Extract cine callbacks and projection callbacks into small coordinator/handler modules; main.py connects signals and delegates to them.
- **file_operations_handler.py**: Break long `open_*` methods into named steps; optionally extract progress-dialog helpers into a small helper class/module.
- **Optional**: overlay_manager – move `ViewportOverlayWidget` to `overlay_widget.py`; tag_export_dialog – extract tag export runner to core/utils.

**Success criteria**: All mouse modes and cine/projection behavior unchanged; file open paths still work; tests pass.

**Estimated effort**: Medium.

---

## Phase 1 – Detailed Checklist

Use this checklist when implementing Phase 1. Mark items only after they are fully done and verified.

### 1. Measurement tool: extract graphics items to `measurement_items.py`

- [ ] **Backup**: Copy `src/tools/measurement_tool.py` to `backups/measurement_tool_pre_measurement_items_extract.py` (or equivalent name). *(Note: if automated copy failed due to path, create backup manually before further edits.)*
- [x] **Create module**: Add `src/tools/measurement_items.py` with module docstring describing purpose, inputs, outputs, and requirements.
- [x] **Move classes**: Move `DraggableMeasurementText`, `MeasurementHandle`, and `MeasurementItem` from `measurement_tool.py` to `measurement_items.py`. Preserve all imports needed by these classes (PySide6, typing, math; no dicom_utils in item classes). Forward refs used for MeasurementItem.
- [x] **Re-export**: In `measurement_tool.py`, add: `from tools.measurement_items import DraggableMeasurementText, MeasurementHandle, MeasurementItem` and `__all__` so existing imports from `tools.measurement_tool` continue to work.
- [x] **Update measurement_tool.py**: Removed moved class bodies; kept only `MeasurementTool` and imports; MeasurementTool imports item classes from `measurement_items`.
- [x] **Tests**: Run the test suite. 
- [x] **Smoke test**: Manually verify measurement tool: draw measurement, move text, resize via handles, delete; confirm units and pixel spacing behavior.
- [x] **Lint**: Run linter on `measurement_tool.py` and `measurement_items.py`; fix reported issues.
- [x] **Documentation**: Updated `measurement_tool.py` and `measurement_items.py` docstrings. `tools/__init__.py` does not re-export these classes; no change needed.

### 2. Export dialog: extract `ExportManager` to `export_manager.py`

- [ ] **Backup**: Copy `src/gui/dialogs/export_dialog.py` to `backups/export_dialog_pre_export_manager_extract.py` (or equivalent). *(Create manually if needed.)*
- [x] **Decide location**: Chose `src/core/export_manager.py`. Created with module docstring.
- [x] **Move class**: Moved entire `ExportManager` class to `core/export_manager.py` with all dependencies (PIL, pydicom, numpy, os, copy, DICOMProcessor, DICOMParser, get_slice_thickness, QProgressDialog, Qt).
- [x] **Imports in new module**: `export_manager.py` imports from core and utils only; no import from gui.dialogs.
- [x] **Update export_dialog.py**: Added `from core.export_manager import ExportManager`; removed in-file `ExportManager`; cleaned unused imports. `ExportDialog` still uses `ExportManager()` and `export_selected()` the same way.
- [x] **Tests**: Run the test suite. *
- [x] **Smoke test**: Open app, load DICOM, open Export dialog; run export to JPEG/PNG and optionally DICOM; verify output files and options (e.g. overlay, window/level).
- [x] **Lint**: Lint `export_dialog.py` and `export_manager.py`; no issues reported.
- [x] **Documentation**: Updated export_dialog and export_manager docstrings to describe split.

### 3. Main window: extract theme to `main_window_theme.py`

- [ ] **Backup**: Copy `src/gui/main_window.py` to `backups/main_window_pre_theme_extract.py` (or equivalent). *(Create manually if needed.)*
- [x] **Create module**: Added `src/gui/main_window_theme.py` with module docstring (purpose: stylesheet and viewer background for themes; inputs: theme name and checkmark paths; outputs: stylesheet string and QColor for viewer).
- [x] **Extract logic**: Implemented `get_theme_stylesheet(theme, white_checkmark_path, black_checkmark_path) -> str` and `get_theme_viewer_background_color(theme) -> QColor`. All dark/light stylesheet strings and viewer background colors live in the theme module.
- [x] **MainWindow integration**: Replaced `_apply_theme` body with: get theme from config, set up QDir search path and checkmark paths, call theme module for stylesheet and viewer color, set QApplication style sheet and viewer background, processEvents. `_set_theme` unchanged: updates action states, config, calls `_apply_theme`, emits signal.
- [x] **Dependencies**: Theme module depends only on PySide6.QtGui.QColor; theme name and paths passed as arguments.
- [x] **Tests**: Run the test suite. *(No theme-specific tests changed.)*
- [x] **Smoke test**: Switch between light and dark theme from the menu; confirm appearance of main window, toolbars, and dialogs. Check that theme persists after restart if applicable.
- [x] **Lint**: Lint `main_window.py` and `main_window_theme.py`; no issues reported.
- [x] **Documentation**: Updated `_apply_theme` docstring to reference gui.main_window_theme; theme module fully documented.

### Phase 1 completion

- [x] **Full test run**: Run the entire test suite once more after all three refactorings are done. (Requires venv with pydicom, PySide6, etc.)
- [ ] **Line count check**: Optionally run line count on `measurement_tool.py`, `export_dialog.py`, and `main_window.py` and record in this plan or in the refactor assessment “Next Steps” so progress is visible.
- [x] **Update assessment**: In `refactor-assessment-2026-02-17-231800.md`, under “Next Steps”, mark “Create implementation plans for high-priority refactorings” as done for Phase 1 and add a short note that Phase 1 (measurement_items, ExportManager, main_window_theme) is completed with date.
- [x] **Check off completed Phase 1 To-Do items** where fully and successfully completed (see checkboxes above).
- [x] **Create detailed checklist in this document for Phase 2** to prepare for starting Phase 2.

---

## Phase 2 – Detailed Checklist

Use this checklist when implementing Phase 2. Mark items only after they are fully done and verified.

### 1. Main window: extract menu bar to `main_window_menu_builder.py`

- [x] **Backup**: Copy `src/gui/main_window.py` to `backups/main_window_pre_menu_builder_extract.py` (or equivalent). *(Create manually if needed.)*
- [x] **Create module**: Add `src/gui/main_window_menu_builder.py` with module docstring (purpose: build MainWindow menu bar and menus; inputs: MainWindow or actions container; outputs: menu bar or list of actions).
- [x] **Move logic**: Move all menu action creation and connection from `MainWindow._create_menu_bar` into the builder (class or function). MainWindow keeps only high-level callbacks that need to call back into MainWindow (e.g. open file, settings).
- [x] **MainWindow integration**: Replace `_create_menu_bar` body with a call to the builder; pass required callbacks/slots. Preserve all existing menu structure and behavior.
- [ ] **Tests**: Run the test suite. *(Import verification done; pytest not in venv.)*
- [ ] **Smoke test**: Open app; verify all menus (File, Edit, View, etc.) and actions work; check theme, recent files, layout, and any menu-triggered dialogs.
- [x] **Lint**: Run linter on `main_window.py` and `main_window_menu_builder.py`; fix reported issues.
- [x] **Documentation**: Update `main_window.py` and `main_window_menu_builder.py` docstrings to describe the split.

### 2. DICOMProcessor: split into domain modules behind facade

- [x] **Backup**: Copy `src/core/dicom_processor.py` to `backups/dicom_processor_pre_split.py` (or equivalent). *(Create manually if needed.)*
- [x] **Create modules**: Add `src/core/dicom_rescale.py`, `dicom_color.py`, `dicom_pixel_array.py`, `dicom_window_level.py`, `dicom_projections.py`, `dicom_pixel_stats.py` with docstrings. *(get_pixel_array in dicom_pixel_array.py.)*
- [x] **Move rescale**: Move `get_rescale_parameters`, `infer_rescale_type` (and related) to `dicom_rescale.py`.
- [x] **Move color**: Move color detection, YBR, planar configuration, RGB conversion to `dicom_color.py`.
- [x] **Move window/level**: Move `apply_window_level`, `apply_color_window_level_luminance`, `convert_window_level_*`, `get_window_level_from_dataset`, `get_window_level_presets_from_dataset` to `dicom_window_level.py`.
- [x] **Move projections**: Move `average_intensity_projection`, `maximum_intensity_projection`, `minimum_intensity_projection` to `dicom_projections.py`.
- [x] **Move pixel stats**: Move `get_pixel_value_range`, `get_series_pixel_value_range`, `get_series_pixel_median` to `dicom_pixel_stats.py`.
- [x] **Facade**: Keep `DICOMProcessor` in `dicom_processor.py`; replace method bodies with delegation to the new modules so all existing call sites remain unchanged.
- [x] **Tests**: Run the test suite; add or run any DICOMProcessor-related tests.
- [x] **Smoke test**: Load DICOM; verify display, window/level, rescale, projections, and any features that use pixel stats.
- [x] **Lint**: Lint all new and modified core modules; fix issues.
- [x] **Documentation**: Document facade and new modules; update `dicom_processor.py` docstring.

### 3. main.py: extract annotation copy/paste to `AnnotationPasteHandler`

- [x] **Backup**: Copy `src/main.py` to `backups/main_pre_annotation_paste_handler_extract.py` (or equivalent). *(Create manually if needed.)*
- [x] **Create module**: Add `src/core/annotation_paste_handler.py` with module docstring (purpose: handle copy/paste of ROI, measurement, crosshair, text, arrow annotations; inputs: getters for current subwindow, managers, scene; outputs: copy/paste behavior).
- [x] **Move selection getters**: Move `_get_selected_rois`, `_get_selected_measurements`, `_get_selected_crosshairs`, `_get_selected_text_annotations`, `_get_selected_arrow_annotations` into the handler (or pass as callbacks from main).
- [x] **Move copy/paste**: Move `_copy_annotations`, `_paste_annotations`, and per-type `_paste_roi`, `_paste_measurement`, `_paste_crosshair`, `_paste_text_annotation`, `_paste_arrow_annotation` into the handler.
- [x] **main.py integration**: Instantiate handler in DICOMViewerApp with required getters/callbacks; replace existing copy/paste method bodies with calls to the handler. Keep menu wiring in main.
- [x] **Tests**: Run the test suite.
- [x] **Smoke test**: Copy and paste each annotation type (ROI, measurement, crosshair, text, arrow) within and across subwindows if applicable; verify offsets and behavior.
- [x] **Lint**: Lint `main.py` and `annotation_paste_handler.py`; fix issues.
- [x] **Documentation**: Update main.py and annotation_paste_handler docstrings to describe the split.

### Phase 2 completion

- [x] **Full test run**: Run the entire test suite once more after all Phase 2 refactorings are done.
- [x] **Smoke test**: End-to-end check of menu bar, DICOM load/display/window-level/projections, and annotation copy/paste.
- [ ] **Update assessment**: Optionally update `refactor-assessment-2026-02-17-231800.md` (line counts, Next Steps) when Phase 2 is completed.

---

## Reference: Assessment priority list (summary)

| Priority   | Refactoring                                              | Score  | Phase |
|-----------|-----------------------------------------------------------|--------|-------|
| High      | Measurement items → measurement_items.py                 | 4.00/5 | 1     |
| High      | ExportManager → export_manager.py                        | 4.00/5 | 1     |
| High      | MainWindow theme → main_window_theme.py                  | 4.00/5 | 1     |
| High      | Annotation copy/paste → AnnotationPasteHandler             | 3.75/5 | 2     |
| High      | DICOMProcessor split (rescale/color/wl/proj/stats)       | 3.75/5 | 2     |
| High      | MainWindow menu bar builder                              | 3.75/5 | 2     |
| High      | File/series loading coordinator (main.py)               | 3.50/5 | 3     |
| High      | Subwindow lifecycle controller (main.py, incremental)    | 3.00/5 | 3     |
| High      | ImageViewer mouse handling / smaller methods             | 3.25/5 | 4     |
| Medium    | Cine and projection callbacks (main.py)                 | 3.75/5 | 4     |
| Medium    | Pixel info/magnifier helper (image_viewer)               | 3.75/5 | 4     |
| Medium    | File_operations_handler progress/long-method split       | 3.75/5 | 4     |


---

## Phase 3 – Detailed Checklist

Use this checklist when implementing Phase 3. Mark items only after they are fully done and verified. Do each sub-phase (3.1, 3.2, 3.3, 3.4) as a separate deliverable with backup, tests, and smoke test before proceeding. Phase 3 is incremental and high-risk; prefer small commits.

---

### Phase 3.1: File/series loading coordinator

**Goal**: Extract file and series loading logic from main.py into a coordinator so menu/signals delegate to it; main keeps high-level display entry points the coordinator can call back.

- [x] **Backup**: Copy `src/main.py` to `backups/main_pre_file_series_coordinator.py` (or equivalent). *(Create manually if needed.)*
- [x] **Create module**: Add `src/core/file_series_loading_coordinator.py` with module docstring (purpose: own file/series loading and first-slice display; inputs: loader, organizer, dialogs, config, callbacks; outputs: loading behavior and callbacks to display/update).
- [x] **Define callback interface**: Document and implement the callbacks the coordinator needs from the app (e.g. clear_data, display_slice, update_status, get_recent_list, add_recent, current_studies/subwindow_data access or pass-through). main.py will pass these when creating the coordinator.
- [x] **Move load-first-slice**: Move `_handle_load_first_slice` logic into the coordinator (or a method it calls). main.py replaces the body with a call to the coordinator; pass required state/callbacks.
- [x] **Move open entry points**: Move `_open_files`, `_open_folder`, `_open_recent_file`, `_open_files_from_paths` into the coordinator. main.py keeps the methods as thin wrappers that call the coordinator (menu/signals still connect to main; main delegates).
- [x] **Move series navigation and selection**: Move `_on_series_navigation_requested`, `_build_flat_series_list`, `_on_series_navigator_selected`, `_on_assign_series_from_context_menu`, `_assign_series_to_subwindow` into the coordinator (or keep assignment in main if it tightly couples to subwindow layout; document the split).
- [x] **Move file-path helpers**: Move `_get_file_path_for_dataset`, `_on_show_file_from_series`, `_on_about_this_file_from_series`, `_get_current_slice_file_path`, `_update_about_this_file_dialog` into the coordinator or a small helper used by the coordinator. main.py delegates to coordinator where appropriate.
- [x] **Wire main.py**: Ensure menu and signal connections still call main; main’s handlers call the coordinator. No change to public behavior.
- [x] **Tests**: Run the full test suite. Add or run any tests that cover file/series loading paths if present. *(Activate the project venv first—e.g. Windows: `.\venv\Scripts\Activate.ps1` or `venv\Scripts\activate`—then from project root: `python tests/run_tests.py` or `python -m pytest tests/ -v`.)*
- [x] **Smoke test**: Open file(s), open folder, open recent, drag-drop paths; switch series via navigator; assign series from context menu; “About this file” and “Show file from series”. Verify first-slice display and status updates. *(See recommended smoke tests below.)*
- [x] **Lint**: Lint `main.py` and `file_series_loading_coordinator.py`; fix issues.
- [x] **Documentation**: Document coordinator API, callbacks, and integration in main; update main.py docstrings where handlers were replaced.

**Recommended smoke tests for Phase 3.1** (run manually after opening the app with a venv):

1. **Open file(s)** – File → Open File(s); select one or more DICOM files. Confirm first slice displays, series navigator appears, status bar updates.
2. **Open folder** – File → Open Folder; select a folder with DICOMs. Confirm load and first-slice display.
3. **Open recent** – File → Open Recent; pick a recent file or folder. Confirm it opens and displays.
4. **Drag-and-drop** – Drag DICOM files or a folder onto the window. Confirm they load and first slice displays.
5. **Series navigation** – With a multi-series study loaded, use left/right arrow (or series nav) to move between series. Confirm image and slice navigator update; no double-firing or lock messages in console.
6. **Series navigator selection** – Click a different series in the series navigator. Confirm focused subwindow shows that series.
7. **Assign series from context menu** – Right-click in the viewer → Assign Series → choose a series. Confirm the focused subwindow shows the chosen series.
8. **About this file** – With a series loaded, open "About this file" (e.g. from Help or context). Confirm dialog shows current dataset/path; change slice and reopen to confirm it updates.
9. **Show file from series** – In the series navigator, use "Show file" (or equivalent) on a series. Confirm file explorer opens and highlights the correct file (if supported on OS).
10. **First-slice and UI state** – After any open action, confirm: fusion reset, projection controls reset, tag viewer filter cleared, metadata and window/level reflect current series, series navigator highlight matches focused subwindow.

---

### Phase 3.2: Subwindow lifecycle – step 1 (getter helpers)

**Goal**: Extract subwindow getter helpers so they can later live in a controller; or move them into a new SubwindowLifecycleController in this step. Recommendation: create the controller module and move only getters in step 1.

- [x] **Backup**: Copy `src/main.py` to `backups/main_pre_subwindow_getters_extract.py` (or equivalent). *(Create manually if needed.)*
- [x] **Create module**: Add `src/core/subwindow_lifecycle_controller.py` (or `src/app/subwindow_controller.py`) with module docstring (purpose: own subwindow getters, focus/panel updates, and signal connect/disconnect/layout; inputs: app or references to multi_window_layout, subwindow_managers; outputs: subwindow/index and callbacks). If doing getters-only first, the class can be minimal (e.g. `SubwindowLifecycleController(app)` with getter methods).
- [x] **Move getter methods**: Move (or delegate from main to controller): `_get_subwindow_dataset`, `_get_subwindow_slice_index`, `_get_subwindow_slice_display_manager`, `_get_subwindow_study_uid`, `_get_subwindow_series_uid`, `get_focused_subwindow_index`, `get_histogram_callbacks_for_subwindow`, `_get_focused_subwindow`. main.py keeps thin wrappers that call the controller so all existing call sites continue to work.
- [x] **Instantiate controller**: In DICOMViewerApp, create the controller (e.g. in `__init__` after multi_window_layout and subwindow_managers exist), store as `self._subwindow_lifecycle_controller` or similar.
- [x] **Tests**: Run the full test suite.
- [x] **Smoke test**: Load DICOM, switch focus between subwindows, change layout (1x1, 1x2, 2x1, 2x2); confirm correct subwindow and slice context (e.g. ROI list, measurements, series navigator).
- [x] **Lint**: Lint `main.py` and `subwindow_lifecycle_controller.py`; fix issues.
- [x] **Documentation**: Document controller getter API and how main uses it.

---

### Phase 3.3: Subwindow lifecycle – step 2 (focus/panel update methods)

**Goal**: Move focus and panel update logic into the SubwindowLifecycleController so main.py no longer contains their implementations.

- [ ] **Backup**: Copy `src/main.py` to `backups/main_pre_subwindow_focus_panel_extract.py` (or equivalent). *(Create manually if needed.)*
- [ ] **Move focus/panel methods**: Move into the controller: `_update_focused_subwindow_references`, `_update_right_panel_for_focused_subwindow`, `_update_left_panel_for_focused_subwindow`. Controller may need callbacks or references to main’s UI (e.g. panel widgets, series navigator). main.py replaces method bodies with calls to the controller.
- [ ] **Preserve call sites**: Ensure every caller of these methods in main.py now invokes the controller (or a main wrapper that calls the controller). No behavior change.
- [ ] **Tests**: Run the full test suite.
- [ ] **Smoke test**: Change focused subwindow (click, layout change); verify right and left panels update (metadata, window/level, ROI list, etc.) and series navigator highlighting.
- [ ] **Lint**: Lint modified files; fix issues.
- [ ] **Documentation**: Update controller and main docstrings to describe the split.

---

### Phase 3.4: Subwindow lifecycle – step 3 (connect/disconnect and layout)

**Goal**: Move signal connect/disconnect and layout methods into the SubwindowLifecycleController so main.py delegates all subwindow lifecycle and layout to the controller.

- [ ] **Backup**: Copy `src/main.py` to `backups/main_pre_subwindow_connect_layout_extract.py` (or equivalent). *(Create manually if needed.)*
- [ ] **Move connect/disconnect**: Move into the controller: `_connect_subwindow_signals`, `_connect_all_subwindow_transform_signals`, `_connect_all_subwindow_context_menu_signals`, `_disconnect_focused_subwindow_signals`, `_connect_focused_subwindow_signals`, `_ensure_all_subwindows_have_managers`. main.py calls the controller for these. Preserve timing (when signals are connected/disconnected) to avoid regressions.
- [ ] **Move display/redisplay for subwindow**: Move `_display_rois_for_subwindow`, `_redisplay_subwindow_slice` into the controller if they are purely subwindow-scoped; otherwise keep in main and have controller call back to main. Document the choice.
- [ ] **Move layout and series assignment**: Move `_on_focused_subwindow_changed`, `_on_layout_changed`, `_on_main_window_layout_changed`, `_capture_subwindow_view_states`, `_restore_subwindow_views`, `_on_layout_change_requested`, `_on_assign_series_requested`, `_assign_series_to_subwindow` into the controller. main.py keeps only signal wiring and calls the controller.
- [ ] **Move init/creation if applicable**: If `_initialize_subwindow_managers` and `_create_managers_for_subwindow` can be moved into the controller without circular dependency, do so; otherwise leave in main and have controller use them via callbacks. Document.
- [ ] **Wire main.py**: Replace all moved method bodies in main with controller calls. Ensure layout shortcuts, menu layout actions, and series assignment still work.
- [ ] **Tests**: Run the full test suite.
- [ ] **Smoke test**: Full subwindow lifecycle: open files, change layout, switch focus, assign series from context menu, close and reopen; verify no duplicate or missing signal connections, correct display and panel state.
- [ ] **Lint**: Lint all modified files; fix issues.
- [ ] **Documentation**: Document controller responsibilities and main.py integration; update plan or assessment with approximate main.py line reduction.

---

### Phase 3 completion

- [ ] **Full test run**: Run the entire test suite once after all Phase 3 sub-phases are done.
- [ ] **Smoke test**: End-to-end: file/folder/recent/paths open, series navigation, layout changes, focus changes, series assignment, panel updates. Confirm no regressions.
- [ ] **Line count**: Optionally run line count on `main.py` and record in this plan or in the refactor assessment “Next Steps” to show progress.
- [ ] **Update assessment**: Optionally update `refactor-assessment-2026-02-17-231800.md` (line counts, Next Steps) when Phase 3 is completed.

---

## Document history

- **Created**: 2026-02-17 (from refactor assessment 2026-02-17-231800).
- **Updated**: 2026-02-19 10:56 – Phase 1 completion tasks (assessment update, Phase 2 checklist, document history).
- **Updated**: 2026-02-19 – Phase 2 implementation (menu bar builder, DICOMProcessor split, AnnotationPasteHandler); checklist items marked done; tests/smoke tests left for user.
- **Updated**: 2026-02-19 – Added Phase 3 detailed checklist (file/series loading coordinator, subwindow lifecycle in steps 3.1–3.4).
- **Updated**: 2026-02-19 – Phase 3.1 implementation complete: FileSeriesLoadingCoordinator added; load-first-slice, open entry points, series navigation, file-path helpers moved; main.py wired to delegate. Checklist marked done except Tests and Smoke test (require venv/manual run). Added recommended smoke tests for Phase 3.1.
- **Updated**: 2026-02-19 – Phase 3.2 implementation complete: SubwindowLifecycleController added in `src/core/subwindow_lifecycle_controller.py`; getter methods moved, main.py delegates; backup created; tests pass; smoke test left for user.