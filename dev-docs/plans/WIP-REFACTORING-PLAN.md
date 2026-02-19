# WIP Refactoring Plan – DICOMViewerV3

## Purpose

This document is a multi-phase plan for addressing the top refactoring issues identified in the refactor assessment. It prioritizes high-impact, lower-risk work first and defers large, riskier extractions (e.g. from `main.py`) until later phases.

**Source assessment**: [refactor-assessment-2026-02-17-231800.md](../refactor-assessments/refactor-assessment-2026-02-17-231800.md)

**Status**: Work in progress (WIP). Only the timestamped assessment file and this plan exist; no refactoring implementation has been started.

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

- [ ] **Backup**: Copy `src/tools/measurement_tool.py` to `backups/measurement_tool_pre_measurement_items_extract.py` (or equivalent name).
- [ ] **Create module**: Add `src/tools/measurement_items.py` with module docstring describing purpose, inputs, outputs, and requirements.
- [ ] **Move classes**: Move `DraggableMeasurementText`, `MeasurementHandle`, and `MeasurementItem` from `measurement_tool.py` to `measurement_items.py`. Preserve all imports needed by these classes (PySide6, typing, numpy, math, `utils.dicom_utils` for `format_distance`/`get_pixel_spacing`). Resolve any circular dependency (e.g. forward refs to `MeasurementItem` in `DraggableMeasurementText` – use string annotation or import inside method if needed).
- [ ] **Re-export**: In `measurement_tool.py`, add: `from tools.measurement_items import DraggableMeasurementText, MeasurementHandle, MeasurementItem` so that existing imports from `tools.measurement_tool` (e.g. in main.py, image_viewer.py, keyboard_event_handler.py, measurement_coordinator.py) continue to work without changing those files.
- [ ] **Update measurement_tool.py**: Remove the moved class bodies; keep only `MeasurementTool` and any imports it needs. Ensure `MeasurementTool` imports the item classes from `measurement_items`.
- [ ] **Tests**: Run the test suite. Fix any import or test failures; do not change test assertions to force pass without understanding the failure.
- [ ] **Smoke test**: Manually verify measurement tool: draw measurement, move text, resize via handles, delete; confirm units and pixel spacing behavior.
- [ ] **Lint**: Run linter on `measurement_tool.py` and `measurement_items.py`; fix reported issues.
- [ ] **Documentation**: Update `measurement_tool.py` and `measurement_items.py` docstrings/top comments if the split changes how the modules are used. Update `tools/__init__.py` if the package re-exports these classes.

### 2. Export dialog: extract `ExportManager` to `export_manager.py`

- [ ] **Backup**: Copy `src/gui/dialogs/export_dialog.py` to `backups/export_dialog_pre_export_manager_extract.py` (or equivalent).
- [ ] **Decide location**: Choose `src/core/export_manager.py` or `src/utils/export_manager.py` (assessment suggests core or utils). Create that file with a module docstring.
- [ ] **Move class**: Move the entire `ExportManager` class (from line 578 to end of class in export_dialog.py) to the new module. Move with it any imports that only `ExportManager` needs (e.g. PIL, pydicom, numpy, os, DICOMProcessor, DICOMParser, dicom_utils). Leave in export_dialog.py only what `ExportDialog` needs.
- [ ] **Imports in new module**: Ensure `export_manager.py` imports `DICOMProcessor`, `DICOMParser`, and any other dependencies used by `ExportManager`. Avoid importing from `gui.dialogs.export_dialog` to prevent circular imports.
- [ ] **Update export_dialog.py**: Add `from core.export_manager import ExportManager` (or `from utils.export_manager import ExportManager`). Remove the in-file `ExportManager` class definition. Confirm `ExportDialog` still instantiates and uses `ExportManager` the same way.
- [ ] **Tests**: Run the test suite. If there are export-related tests, run them; fix failures without artificially changing expectations.
- [ ] **Smoke test**: Open app, load DICOM, open Export dialog; run export to JPEG/PNG and optionally DICOM; verify output files and options (e.g. overlay, window/level).
- [ ] **Lint**: Lint `export_dialog.py` and `export_manager.py`; fix issues.
- [ ] **Documentation**: Update top-level docstrings and any README/AGENTS that refer to export implementation location.

### 3. Main window: extract theme to `main_window_theme.py`

- [ ] **Backup**: Copy `src/gui/main_window.py` to `backups/main_window_pre_theme_extract.py` (or equivalent).
- [ ] **Create module**: Add `src/gui/main_window_theme.py` with module docstring (purpose: provide stylesheet and palette for MainWindow themes; inputs: theme name; outputs: stylesheet string and/or QPalette).
- [ ] **Extract logic**: Move the implementation of `_apply_theme` and `_set_theme` into the new module. Options: (A) a function `get_theme_stylesheet(theme: str) -> str` and `get_theme_palette(theme: str)` (or `apply_theme_to_app(theme: str, app)` if application-wide), or (B) a small class `MainWindowTheme` with methods that return stylesheet and palette for a given theme. Ensure all style strings and palette logic live in the theme module; no theme logic remains in MainWindow except a call to the theme module.
- [ ] **MainWindow integration**: In `main_window.py`, replace the body of `_apply_theme` with a call to the theme module (e.g. get stylesheet and palette, then `self.setStyleSheet(...)` and `self.setPalette(...)` or equivalent). Replace `_set_theme` body with: optionally update config, then call the same theme application (so one code path applies theme).
- [ ] **Dependencies**: Theme module should depend only on Qt (and optionally config if theme choice is read from there). Prefer passing theme name as argument rather than theme module importing MainWindow or config.
- [ ] **Tests**: Run the test suite. No existing tests may assume theme implementation lives in MainWindow; fix any failures properly.
- [ ] **Smoke test**: Switch between light and dark theme from the menu; confirm appearance of main window, toolbars, and dialogs. Check that theme persists after restart if applicable.
- [ ] **Lint**: Lint `main_window.py` and `main_window_theme.py`; fix issues.
- [ ] **Documentation**: Update MainWindow docstring if it described theme implementation; document the new theme module in any dev-docs that reference UI styling.

### Phase 1 completion

- [ ] **Full test run**: Run the entire test suite once more after all three refactorings are done.
- [ ] **Line count check**: Optionally run line count on `measurement_tool.py`, `export_dialog.py`, and `main_window.py` and record in this plan or in the refactor assessment “Next Steps” so progress is visible.
- [ ] **Update assessment**: In `refactor-assessment-2026-02-17-231800.md`, under “Next Steps”, mark “Create implementation plans for high-priority refactorings” as done for Phase 1 and add a short note that Phase 1 (measurement_items, ExportManager, main_window_theme) is completed with date.

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

## Document history

- **Created**: 2026-02-17 (from refactor assessment 2026-02-17-231800).
- **Updated**: (none yet).
