# Refactor Assessment - DICOMViewerV3
## 2026-02-17 23:18:00

## Assessment Date
- **Date**: 2026-02-17
- **Time**: 23:18:00
- **Assessor**: AI Agent (Cursor)

## Thresholds Applied
- **Base threshold**: 750 lines
- **Python-specific guideline**: 600 lines (template language-specific table)
- **Scope**: All source code in `src/`, `scripts/`, `tests/`; backup files and `backups/` folder excluded.

---

## Assessment Checklist

### Preparation
- [x] Create timestamped copy of this template
- [x] **Remember: Only edit the timestamped assessment file - do not modify any code files**
- [x] Identify all code files in codebase (root, `src/`, `scripts/`, `tests/`)
- [x] **Exclude backup files** (files with "backup", "_BAK", ".bak" in name or in backup folders)
- [x] Count lines for each file
- [x] Create list of files exceeding 750 lines

### Analysis (for each file exceeding 750 lines)
- [x] Document file path and line count
- [x] List main functions/classes in the file
- [x] Identify function groupings
- [x] Analyze dependencies (what it uses, what uses it)
- [x] Identify code organization patterns
- [x] Identify refactoring opportunities
- [x] Document proposed refactoring plan
- [x] Evaluate each refactoring suggestion (Ease, Safety, Practicality, Recommendation)
- [x] Calculate overall score for each suggestion
- [x] Prioritize recommendations

### Documentation
- [x] Create summary table of all files analyzed
- [x] Create prioritized list of refactoring recommendations
- [x] Document any files that are appropriately large (with justification)
- [x] Note any patterns or observations about the codebase structure

---

## Files Analyzed

### Summary Table

| File | Location | Line Count | Exceeds 750 | Exceeds 600 (Py) | Status |
|------|----------|------------|-------------|------------------|--------|
| main.py | src/main.py | 5853 | Yes | Yes | Analyzed |
| image_viewer.py | src/gui/image_viewer.py | 2465 | Yes | Yes | Analyzed |
| main_window.py | src/gui/main_window.py | 2276 | Yes | Yes | Analyzed |
| dicom_processor.py | src/core/dicom_processor.py | 1794 | Yes | Yes | Analyzed |
| measurement_tool.py | src/tools/measurement_tool.py | 1774 | Yes | Yes | Analyzed |
| export_dialog.py | src/gui/dialogs/export_dialog.py | 1762 | Yes | Yes | Analyzed |
| file_operations_handler.py | src/core/file_operations_handler.py | 1680 | Yes | Yes | Analyzed |
| slice_display_manager.py | src/core/slice_display_manager.py | 1321 | Yes | Yes | Analyzed |
| overlay_manager.py | src/gui/overlay_manager.py | 1310 | Yes | Yes | Analyzed |
| tag_export_dialog.py | src/gui/dialogs/tag_export_dialog.py | 1288 | Yes | Yes | Analyzed |
| config_manager.py | src/utils/config_manager.py | 1185 | Yes | Yes | Analyzed |
| annotation_manager.py | src/tools/annotation_manager.py | 1173 | Yes | Yes | Analyzed |
| fusion_controls_widget.py | src/gui/fusion_controls_widget.py | 1131 | Yes | Yes | Analyzed |
| roi_manager.py | src/tools/roi_manager.py | 1124 | Yes | Yes | Analyzed |
| view_state_manager.py | src/core/view_state_manager.py | 1080 | Yes | Yes | Analyzed |
| undo_redo.py | src/utils/undo_redo.py | 1060 | Yes | Yes | Analyzed |
| fusion_coordinator.py | src/gui/fusion_coordinator.py | 1016 | Yes | Yes | Analyzed |
| roi_coordinator.py | src/gui/roi_coordinator.py | 988 | Yes | Yes | Analyzed |
| series_navigator.py | src/gui/series_navigator.py | 875 | Yes | Yes | Analyzed |
| fusion_handler.py | src/core/fusion_handler.py | 875 | Yes | Yes | Analyzed |
| quick_start_guide_dialog.py | src/gui/dialogs/quick_start_guide_dialog.py | 823 | Yes | Yes | Analyzed |
| fusion_technical_doc_dialog.py | src/gui/dialogs/fusion_technical_doc_dialog.py | 811 | Yes | Yes | Analyzed |
| dicom_loader.py | src/core/dicom_loader.py | 747 | Yes | Yes | Analyzed |
| image_resampler.py | src/core/image_resampler.py | 737 | No | Yes | Not over 750 |
| create_appimage.sh | scripts/create_appimage.sh | 193 | No | N/A | Under threshold |

---

## Detailed Analysis

### File: main.py

**Location**: `src/main.py`  
**Line Count**: 5853  
**Exceeds Threshold**: Yes (by a large margin)

#### Code Structure Inventory
- **DICOMViewerApp** (class, lines 95–5849): Single application class with ~170+ methods. Responsibilities include: app init, subwindow manager lifecycle, focused subwindow updates, fusion notification state, panel updates, ROI/measurement/annotation display, handler init, clear/close/reset, rescale params, tag viewer/undo/redo, ROI list, UI setup and signal connections, layout change handling, series assignment, signal connect/disconnect for subwindows, file open/folder/recent/paths, series navigation and navigator selection, slice display and redisplay, projection callbacks, settings/overlay/about dialogs, export/import customizations and tag presets, window/mouse/ROI/measurement/overlay/scroll/rescale/histogram/zoom/transform/viewport/pixel/arrow/window-level/overlay font/cine/visibility helpers, selection getters, copy/paste annotations (ROI, measurement, crosshair, text, arrow), event filter, layout shortcuts, run(), keyboard focus.
- **exception_hook** (function, lines 5850–5867): Top-level exception hook.
- **main()** (function, lines 5869–end): Entry point.

#### Logical Groupings
- **Subwindow lifecycle**: `_initialize_subwindow_managers`, `_create_managers_for_subwindow`, `_get_subwindow_*`, `get_focused_subwindow_index`, `get_histogram_callbacks_for_subwindow`, `_update_focused_subwindow_references`, `_update_right_panel_for_focused_subwindow`, `_update_left_panel_for_focused_subwindow`, `_display_rois_for_subwindow`, `_redisplay_subwindow_slice`, `_ensure_all_subwindows_have_managers`, `_connect_subwindow_signals`, `_connect_all_subwindow_*`, `_disconnect_focused_subwindow_signals`, `_connect_focused_subwindow_signals`, `_get_focused_subwindow`.
- **Handlers & setup**: `_initialize_handlers`, `_setup_ui`, `_connect_signals`, `_clear_data`, `_close_files`, `_reset_fusion_for_all_subwindows`.
- **File/series loading**: `_handle_load_first_slice`, `_open_files`, `_open_folder`, `_open_recent_file`, `_open_files_from_paths`, `_on_series_navigation_requested`, `_build_flat_series_list`, `_on_series_navigator_selected`, `_on_assign_series_from_context_menu`, `_assign_series_to_subwindow`.
- **Display/slice**: `_display_slice`, `_redisplay_current_slice`, `_display_rois_for_slice`, `_display_measurements_for_slice`, `_redisplay_subwindow_slice`.
- **Tags/undo**: `_get_rescale_params`, `_update_tag_viewer`, `_on_tag_edited`, `_undo_tag_edit`, `_redo_tag_edit`, `_update_undo_redo_state`, `_refresh_tag_ui`, `_on_undo_requested`, `_on_redo_requested`.
- **Dialogs/settings**: `_open_settings`, `_open_overlay_settings`, `_open_about_this_file`, `_open_tag_viewer`, `_open_overlay_config`, `_open_annotation_options`, `_open_quick_start_guide`, `_open_fusion_technical_doc`, `_open_tag_export`, `_open_export`, export/import customizations and tag presets, `_on_*_applied`.
- **Mouse/UI state**: `_set_mouse_mode_via_handler`, `_on_window_changed`, `_on_mouse_mode_changed`, `_set_mouse_mode`, `_set_roi_mode`, ROI/measurement/overlay/scroll/rescale/histogram/zoom/transform/viewport/pixel/arrow/window-level/overlay font callbacks, cine callbacks, visibility helpers.
- **Selection & copy/paste**: `_get_selected_rois`, `_get_selected_measurements`, `_get_selected_crosshairs`, `_get_selected_text_annotations`, `_get_selected_arrow_annotations`, `_copy_annotations`, `_paste_annotations`, `_paste_roi`, `_paste_measurement`, `_paste_crosshair`, `_paste_text_annotation`, `_paste_arrow_annotation`.
- **Layout**: `_on_focused_subwindow_changed`, `_on_layout_changed`, `_on_main_window_layout_changed`, `_capture_subwindow_view_states`, `_restore_subwindow_views`, `_on_layout_change_requested`, `_on_assign_series_requested`.
- **Misc**: `_update_roi_list`, `_update_series_navigator_highlighting`, `eventFilter`, `_is_widget_allowed_for_layout_shortcuts`, `run`, `_set_initial_keyboard_focus`, fusion notification helpers, file path helpers.

#### Dependencies
- **Depends on**: `gui.main_window`, `gui.dialogs.*` (file, settings, tag_viewer, overlay_config, annotation_options), `gui.image_viewer`, `gui.multi_window_layout`, `gui.sub_window_container`, `gui.metadata_panel`, `gui.window_level_controls`, `gui.roi_statistics_panel`, `gui.roi_list_panel`, `utils.undo_redo`, `gui.slice_navigator`, `gui.series_navigator`, `gui.zoom_display_widget`, `gui.cine_player`, `gui.cine_controls_widget`, `gui.intensity_projection_controls_widget`, `core.dicom_loader`, `core.dicom_organizer`, `core.dicom_parser`, `core.dicom_processor`, `core.tag_edit_history`, `utils.config_manager`, `utils.dicom_utils`, `tools.roi_manager`, `tools.measurement_tool`, `tools.crosshair_manager`, `tools.annotation_manager`, `tools.histogram_widget`, `gui.overlay_manager`, `utils.annotation_clipboard`, `core.view_state_manager`, `core.file_operations_handler`, `core.slice_display_manager`, `gui.roi_coordinator`, `gui.measurement_coordinator`, `gui.crosshair_coordinator`, `gui.overlay_coordinator`, `gui.dialog_coordinator`, `gui.mouse_mode_handler`, `gui.keyboard_event_handler`, `core.fusion_*`, `gui.fusion_*`, PySide6, pydicom.
- **Depended upon by**: Entry point only (e.g. `if __name__ == "__main__"`); no other modules import from `main`.

#### Code Organization
- Single giant class with methods in rough thematic order but no physical separation. Repeated patterns: subwindow iteration, manager lookup by index, callback lambdas that close over `self`. Many one-off `_on_*` handlers that delegate to handlers/coordinators but still add glue and state.

#### Refactoring Opportunities

##### Opportunity 1: Extract subwindow lifecycle and focus into SubwindowLifecycleController (or similar)

**Proposed Structure**:
- New module: `src/core/subwindow_lifecycle_controller.py` (or `src/app/subwindow_controller.py`)
  - Move: `_initialize_subwindow_managers`, `_create_managers_for_subwindow`, `_get_subwindow_dataset`, `_get_subwindow_slice_index`, `_get_subwindow_slice_display_manager`, `_get_subwindow_study_uid`, `_get_subwindow_series_uid`, `get_focused_subwindow_index`, `get_histogram_callbacks_for_subwindow`, `_update_focused_subwindow_references`, `_update_right_panel_for_focused_subwindow`, `_update_left_panel_for_focused_subwindow`, `_display_rois_for_subwindow`, `_redisplay_subwindow_slice`, `_ensure_all_subwindows_have_managers`, `_connect_subwindow_signals`, `_connect_all_subwindow_transform_signals`, `_connect_all_subwindow_context_menu_signals`, `_disconnect_focused_subwindow_signals`, `_connect_focused_subwindow_signals`, `_get_focused_subwindow`, `_on_focused_subwindow_changed`, `_on_assign_series_requested`, `_assign_series_to_subwindow`, `_on_layout_change_requested`, `_capture_subwindow_view_states`, `_restore_subwindow_views`, `_on_layout_changed`, `_on_main_window_layout_changed`.
- DICOMViewerApp keeps: references to the controller, init, `_setup_ui`, `_connect_signals`, file/series loading, display entry points, dialogs, event handlers that call into controller where needed.

**Migration Strategy**:
1. Add new module; instantiate controller in `DICOMViewerApp.__init__` with required callbacks/references.
2. Move methods to controller (or facade methods that delegate). Update `main.py` to call controller.
3. Run tests and manual smoke tests for layout change, focus, series assignment, and multi-subwindow behavior.

**Benefits**:
- Reduces main.py by an estimated 1500–2500 lines. Clear single responsibility for subwindow/focus/layout.
- Improves testability of subwindow logic in isolation.
- Makes future multi-window features easier to reason about.

**Evaluation**:
- **Ease of Implementation**: 2/5 – Many methods close over `self` and reference `self.subwindow_managers`, `self.multi_window_layout`, etc.; careful parameterization or dependency injection required.
- **Safety**: 2/5 – High risk: touches focus, layout, and signal connections used everywhere; regressions in focus or display are likely if not tested thoroughly.
- **Practicality**: 4/5 – High benefit: main.py is the largest single file and this is the largest coherent block.
- **Recommendation**: 4/5 – Should be done; do in small steps (e.g. extract “get subwindow” helpers first, then focus updates, then signal connect/disconnect).
- **Overall Score**: 3.00/5

**Priority**: High (due to impact on maintainability; implement incrementally)

##### Opportunity 2: Extract file/series loading and first-slice display into a dedicated module

**Proposed Structure**:
- New module: `src/core/file_series_loading_coordinator.py` (or extend `FileOperationsHandler` with a “load first slice” coordinator that owns the callback logic)
  - Move: `_handle_load_first_slice`, `_open_files`, `_open_folder`, `_open_recent_file`, `_open_files_from_paths`, `_on_series_navigation_requested`, `_build_flat_series_list`, `_on_series_navigator_selected`, `_on_assign_series_from_context_menu`, and related file-path helpers (`_get_file_path_for_dataset`, `_on_show_file_from_series`, `_on_about_this_file_from_series`, `_get_current_slice_file_path`, `_update_about_this_file_dialog`).
- main.py keeps: wiring to this coordinator from menu/signals and high-level `_display_slice` / `_redisplay_current_slice` that the coordinator can call back into.

**Migration Strategy**:
1. Create coordinator that takes loader, organizer, dialog, config, and callbacks (clear_data, load_first_slice_callback, display_slice, update_status, etc.).
2. Move logic from main into coordinator; main’s menu/signals call coordinator methods.
3. Test open file/folder/recent/paths, series navigation, and “about this file” / “show file”.

**Benefits**:
- Reduces main.py by roughly 800–1200 lines. Clear boundary for “how files and series get loaded and first slice shown”.
- Easier to test loading and series selection without full UI.

**Evaluation**:
- **Ease of Implementation**: 3/5 – Callback surface is well-defined; some state (e.g. current_studies, subwindow_data) must be owned or passed clearly.
- **Safety**: 3/5 – Critical path; good test coverage and incremental move reduce risk.
- **Practicality**: 4/5 – Clear functional boundary; good payoff.
- **Recommendation**: 4/5 – Recommended; can be done after or in parallel with subwindow extraction.
- **Overall Score**: 3.50/5

**Priority**: High

##### Opportunity 3: Extract annotation copy/paste into AnnotationPasteHandler (or integrate into existing clipboard/coordinator)

**Proposed Structure**:
- New module: `src/core/annotation_paste_handler.py` or extend `utils/annotation_clipboard` with a handler class that owns paste logic.
  - Move: `_get_selected_rois`, `_get_selected_measurements`, `_get_selected_crosshairs`, `_get_selected_text_annotations`, `_get_selected_arrow_annotations`, `_copy_annotations`, `_paste_annotations`, `_paste_roi`, `_paste_measurement`, `_paste_crosshair`, `_paste_text_annotation`, `_paste_arrow_annotation`.
- main.py: keeps only menu wiring and calls into this handler.

**Migration Strategy**:
1. Add handler that receives getters for current subwindow, managers, and scene; implement copy/paste and per-type paste methods.
2. Move selection getters and paste implementations from main; replace with handler calls.
3. Test copy/paste for each annotation type and across subwindows if applicable.

**Benefits**:
- Removes ~600+ lines from main. Single place for paste rules and offsets.
- Improves testability of paste behavior.

**Evaluation**:
- **Ease of Implementation**: 3/5 – Self-contained block; depends on manager interfaces and scene.
- **Safety**: 4/5 – Isolated feature; lower risk if tests cover paste scenarios.
- **Practicality**: 4/5 – Clear boundary, good benefit.
- **Recommendation**: 4/5 – Recommended.
- **Overall Score**: 3.75/5

**Priority**: High

##### Opportunity 4: Extract cine and projection callbacks into small coordinator modules

**Proposed Structure**:
- `src/app/cine_coordinator.py`: `_update_cine_player_context`, `_on_cine_frame_advance`, `_on_cine_playback_state_changed`, `_on_cine_play`, `_on_cine_pause`, `_on_cine_stop`, `_on_cine_speed_changed`, `_on_cine_loop_toggled`, `_get_cine_loop_state`, `_on_cine_loop_start_set`, `_on_cine_loop_end_set`, `_on_cine_loop_bounds_cleared`, `_on_frame_slider_changed`.
- `src/app/projection_callback_handler.py`: `_on_projection_enabled_changed`, `_on_projection_type_changed`, `_on_projection_slice_count_changed`.
- main.py: connects signals to these coordinators; coordinators call back into main or managers for slice/display updates.

**Benefits**:
- Removes ~200–300 lines from main; clearer separation for cine vs projection.

**Evaluation**:
- **Ease of Implementation**: 4/5 – Small, cohesive blocks.
- **Safety**: 4/5 – Isolated; cine and projection already use callbacks.
- **Practicality**: 3/5 – Moderate benefit.
- **Recommendation**: 3/5 – Consider when touching main.py for other refactors.
- **Overall Score**: 3.75/5

**Priority**: Medium

---

### File: image_viewer.py

**Location**: `src/gui/image_viewer.py`  
**Line Count**: 2465  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- **ImageViewer** (class, lines 34–2465): One class. Methods: `__init__`, `set_background_color`, `_apply_inversion`, `invert_image`, `set_image`, `fit_to_view`, `zoom_in`/`zoom_out`, `reset_zoom`, `set_zoom`, `set_scroll_wheel_mode`, `set_rescale_toggle_state`, `set_cine_controls_enabled`, `set_privacy_view_state`, `wheelEvent`, `set_mouse_mode`, `set_roi_drawing_mode`, `mousePressEvent` (very long), `_toggle_statistic`, `mouseMoveEvent`, `mouseReleaseEvent`, `_on_show_file_requested`, `viewportEvent`, `keyPressEvent`, `set_window_level_for_drag`, `_check_transform_changed`, `_on_scrollbar_changed`, `get_viewport_center_scene`, `set_pixel_info_callbacks`, `_update_pixel_info`, `_extract_image_region`, `_get_pixel_value_at_coords`, `resizeEvent`, `dragEnterEvent`, `dragMoveEvent`, `dropEvent`. Many signals defined at class level.

#### Logical Groupings
- **Image and view**: `set_image`, `_apply_inversion`, `invert_image`, `fit_to_view`, zoom methods, `set_zoom`, `set_window_level_for_drag`, `resizeEvent`, `_check_transform_changed`, `_on_scrollbar_changed`, `get_viewport_center_scene`.
- **Mouse/key/scroll**: `set_mouse_mode`, `set_roi_drawing_mode`, `wheelEvent`, `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`, `keyPressEvent`, `viewportEvent`.
- **Pixel info and magnifier**: `set_pixel_info_callbacks`, `_update_pixel_info`, `_extract_image_region`, `_get_pixel_value_at_coords`.
- **Drag/drop**: `dragEnterEvent`, `dragMoveEvent`, `dropEvent`.
- **State/config**: `set_background_color`, `set_scroll_wheel_mode`, `set_rescale_toggle_state`, `set_cine_controls_enabled`, `set_privacy_view_state`, `_on_show_file_requested`, `_toggle_statistic`.

#### Dependencies
- **Depends on**: PySide6 (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QWidget, QMenu, QApplication, Qt, QRectF, Signal, QPointF, QTimer, QEvent, QPixmap, QImage, QWheelEvent, QKeyEvent, QMouseEvent, QPainter, QColor, QTransform, QDragEnterEvent, QDropEvent), PIL, numpy. Inline imports from `gui.sub_window_container`, `tools.measurement_tool`, `tools.text_annotation_tool`, `tools.arrow_annotation_tool`.
- **Depended upon by**: main.py (DICOMViewerApp), sub_window_container, and any code that embeds ImageViewer.

#### Code Organization
- Single large widget class. `mousePressEvent` is extremely long (hundreds of lines) with repeated type checks and mode branching; similar patterns appear in `mouseMoveEvent` and `mouseReleaseEvent`.

#### Refactoring Opportunities

##### Opportunity 1: Extract mouse event handling into a MouseEventHandler or mixin

**Proposed Structure**:
- New module: `src/gui/image_viewer_mouse_handler.py` (or mixin in same package).
  - Move: Logic from `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent` into a helper that receives (event, scene, image_item, mode, callbacks for ROI/measurement/annotation detection and signals). ImageViewer delegates to this helper.
- Alternative: Keep handlers in ImageViewer but extract **branch logic** into small methods (e.g. `_handle_select_mode_click`, `_handle_pan_mode_click`, `_handle_roi_drawing_move`) to shrink each event method.

**Migration Strategy**:
1. Add helper class or mixin with same inputs as current code (scene, transform, mode, callbacks). Move branches stepwise; replace in ImageViewer with delegation.
2. Test all mouse modes: pan, zoom, select, ROI, measure, text/arrow annotation, crosshair, magnifier, auto window/level.

**Benefits**:
- Shrinks image_viewer.py by hundreds of lines and makes mouse behavior testable in isolation.
- Reduces duplication of item-type checks.

**Evaluation**:
- **Ease of Implementation**: 2/5 – Tight coupling to scene items, callbacks, and signals; many branches.
- **Safety**: 3/5 – Mouse behavior is critical; needs thorough UI testing.
- **Practicality**: 4/5 – Large file and repeated patterns justify the effort.
- **Recommendation**: 4/5 – Recommended; consider first extracting small “handler” methods inside the same file to reduce risk.
- **Overall Score**: 3.25/5

**Priority**: High

##### Opportunity 2: Extract pixel value and magnifier logic into a small helper module

**Proposed Structure**:
- New module: `src/gui/pixel_info_helper.py` (or `image_viewer_pixel_info.py`).
  - Move: `_update_pixel_info`, `_extract_image_region`, `_get_pixel_value_at_coords` (and any dataset/slice callbacks usage) into a class or functions that take scene, callbacks, and event/scene position. ImageViewer keeps `set_pixel_info_callbacks` and calls the helper.

**Benefits**:
- Removes ~200 lines from image_viewer; isolates pixel-value and magnifier logic for testing.

**Evaluation**:
- **Ease of Implementation**: 4/5 – Clear inputs/outputs.
- **Safety**: 4/5 – Isolated; magnifier and status bar tests can validate.
- **Practicality**: 3/5 – Moderate benefit.
- **Recommendation**: 3/5 – Consider when refactoring image_viewer.
- **Overall Score**: 3.75/5

**Priority**: Medium

---

### File: main_window.py

**Location**: `src/gui/main_window.py`  
**Line Count**: 2276  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- **_get_resource_path** (function, lines 44–71): Resource path helper.
- **MainWindow** (class, lines 73–end): Methods include `__init__`, `_create_menu_bar`, `_create_toolbar`, `_create_status_bar`, `_create_central_widget`, `_apply_theme`, `_set_theme`, `_on_privacy_view_toggled`, `_on_privacy_mode_button_clicked`, `_update_privacy_mode_button`, `_show_disclaimer`, `_on_about_disclaimer_clicked`, `_show_about`, `_on_mouse_mode_changed`, `get_current_mouse_mode`, `set_mouse_mode_checked`, `_on_scroll_wheel_mode_combo_changed`, font size/color and rescale handlers, series nav, `_update_recent_menu`, `eventFilter`, `_remove_recent_file`, `update_recent_menu`, `_open_edit_recent_list_dialog`, `_on_splitter_moved`, `update_status`, `update_zoom_preset_status`, `update_undo_redo_state`, `set_series_navigator`, `toggle_series_navigator`, `dragEnterEvent`, `dropEvent`, `_on_layout_changed`, `set_layout_mode`, `closeEvent`. `_create_menu_bar` and `_apply_theme`/`_set_theme` are very long (menu bar: many actions; theme: large style blocks).

#### Logical Groupings
- **Menu/toolbar/status**: `_create_menu_bar`, `_create_toolbar`, `_create_status_bar`, `_create_central_widget`.
- **Theme**: `_apply_theme`, `_set_theme`.
- **Privacy/about**: `_on_privacy_view_toggled`, `_on_privacy_mode_button_clicked`, `_update_privacy_mode_button`, `_show_disclaimer`, `_on_about_disclaimer_clicked`, `_show_about`.
- **Mouse/UI state**: `_on_mouse_mode_changed`, `get_current_mouse_mode`, `set_mouse_mode_checked`, `_on_scroll_wheel_mode_combo_changed`, font/rescale handlers, series nav buttons.
- **Recent/layout**: `_update_recent_menu`, `_remove_recent_file`, `update_recent_menu`, `_open_edit_recent_list_dialog`, `_on_splitter_moved`, `_on_layout_changed`, `set_layout_mode`.
- **Status/series**: `update_status`, `update_zoom_preset_status`, `update_undo_redo_state`, `set_series_navigator`, `toggle_series_navigator`.
- **Events**: `eventFilter`, `dragEnterEvent`, `dropEvent`, `closeEvent`.

#### Dependencies
- **Depends on**: PySide6, `utils.config_manager`, resource paths, and various dialogs/widgets for menu actions.
- **Depended upon by**: main.py (DICOMViewerApp creates and uses MainWindow).

#### Code Organization
- One main window class; menu and toolbar built in a few very long methods; theme styling is a large block.

#### Refactoring Opportunities

##### Opportunity 1: Extract menu bar creation into MainWindowMenuBuilder (or similar)

**Proposed Structure**:
- New module: `src/gui/main_window_menu_builder.py`.
  - Class or function that takes MainWindow (or actions container) and builds menu bar and menus; returns menu bar or list of actions. MainWindow calls it from `_create_menu_bar`.
- Move: All menu action creation and connection from `_create_menu_bar` into the builder. MainWindow keeps only high-level actions that need to call back into MainWindow (e.g. open file, settings).

**Benefits**:
- Cuts main_window.py by an estimated 200–400 lines. Menu structure becomes easier to change and test.

**Evaluation**:
- **Ease of Implementation**: 3/5 – Many actions are connected to MainWindow or app; builder can accept signal slots or callbacks.
- **Safety**: 4/5 – Purely structural; behavior unchanged if connections preserved.
- **Practicality**: 4/5 – High line count in one method.
- **Recommendation**: 4/5 – Recommended.
- **Overall Score**: 3.75/5

**Priority**: High

##### Opportunity 2: Extract theme/styling into MainWindowTheme (or styles module)

**Proposed Structure**:
- New module: `src/gui/main_window_theme.py` (or `styles/main_window_styles.py`).
  - Move: `_apply_theme` and `_set_theme` implementation (stylesheet strings and palette logic) into a theme class or module that returns stylesheet and palette for a given theme name. MainWindow calls it and applies result.

**Benefits**:
- Removes a large block from main_window; centralizes styling for reuse and tweaks.

**Evaluation**:
- **Ease of Implementation**: 4/5 – Styling is mostly data.
- **Safety**: 4/5 – Visual only; regression test with a few themes.
- **Practicality**: 4/5 – Clear boundary.
- **Recommendation**: 4/5 – Recommended.
- **Overall Score**: 4.00/5

**Priority**: High

---

### File: dicom_processor.py

**Location**: `src/core/dicom_processor.py`  
**Line Count**: 1794  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- **DICOMProcessor** (class): Static or class methods for rescale parameters, color detection, RGB conversion, planar configuration, `get_pixel_array`, window/level (apply and convert), presets, `dataset_to_image`, intensity projections (average, max, min), pixel value range and median. Many pure functions of dataset/array.

#### Logical Groupings
- **Rescale**: `get_rescale_parameters`, `infer_rescale_type`.
- **Color**: `is_color_image`, `_is_already_rgb`, `convert_ybr_to_rgb`, `detect_and_fix_rgb_channel_order`, `_convert_ybr_to_rgb_2d`, `_handle_planar_configuration`.
- **Pixel array**: `get_pixel_array`.
- **Window/level**: `apply_window_level`, `apply_color_window_level_luminance`, `convert_window_level_*`, `get_window_level_from_dataset`, `get_window_level_presets_from_dataset`.
- **Image**: `dataset_to_image`.
- **Projections**: `average_intensity_projection`, `maximum_intensity_projection`, `minimum_intensity_projection`.
- **Stats**: `get_pixel_value_range`, `get_series_pixel_value_range`, `get_series_pixel_median`.

#### Dependencies
- **Depends on**: pydicom, numpy, PIL (or similar). Core only.
- **Depended upon by**: main.py, slice_display_manager, and any code that converts DICOM to displayable images or needs rescale/window-level.

#### Refactoring Opportunities

##### Opportunity 1: Split into smaller modules by domain

**Proposed Structure**:
- `src/core/dicom_rescale.py`: rescale parameters and infer logic.
- `src/core/dicom_color.py`: color detection, YBR, planar configuration, RGB fixes.
- `src/core/dicom_window_level.py`: window/level apply, convert, get from dataset, presets.
- `src/core/dicom_image.py`: `get_pixel_array`, `dataset_to_image` (or keep in processor as facade).
- `src/core/dicom_projections.py`: AIP, MIP, MinIP.
- `src/core/dicom_pixel_stats.py`: pixel value range and median.
- `DICOMProcessor` in `dicom_processor.py` becomes a thin facade that delegates to these modules for backward compatibility.

**Benefits**:
- Each file ~200–400 lines; easier to test and locate logic.

**Evaluation**:
- **Ease of Implementation**: 3/5 – Clear boundaries; facade keeps existing API.
- **Safety**: 4/5 – Facade preserves call sites; internal tests per module.
- **Practicality**: 4/5 – High value for a core component.
- **Recommendation**: 4/5 – Recommended.
- **Overall Score**: 3.75/5

**Priority**: High

---

### File: measurement_tool.py

**Location**: `src/tools/measurement_tool.py`  
**Line Count**: 1774  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- **DraggableMeasurementText** (class, ~lines 30–128): Text item for measurement display.
- **MeasurementHandle** (class, ~129–364): Handle for resizing/editing.
- **MeasurementItem** (class, ~365–1270): Main measurement graphic (line + text + handles).
- **MeasurementTool** (class, ~1271–end): Tool that creates/manages measurement items.

#### Logical Groupings
- **Graphics items**: DraggableMeasurementText, MeasurementHandle, MeasurementItem (one group).
- **Tool**: MeasurementTool.

#### Refactoring Opportunities

##### Opportunity 1: Move graphics item classes to a separate module

**Proposed Structure**:
- New module: `src/tools/measurement_items.py` (or `measurement_graphics.py`).
  - Move: `DraggableMeasurementText`, `MeasurementHandle`, `MeasurementItem`.
- `measurement_tool.py`: Keep only `MeasurementTool`, import item classes from `measurement_items`.

**Benefits**:
- Reduces measurement_tool.py by ~900 lines. Clear split between “drawable items” and “tool logic”.
- Reuse of item classes in tests or other tools.

**Evaluation**:
- **Ease of Implementation**: 4/5 – Clear class boundaries; MeasurementTool already references these types.
- **Safety**: 4/5 – Import path change; update tests and any other imports.
- **Practicality**: 4/5 – Good benefit.
- **Recommendation**: 4/5 – Recommended.
- **Overall Score**: 4.00/5

**Priority**: High

---

### File: export_dialog.py

**Location**: `src/gui/dialogs/export_dialog.py`  
**Line Count**: 1762  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- **ExportDialog** (class, ~41–577): Dialog UI for export options.
- **ExportManager** (class, ~578–end): Performs export (file types, options, progress). Likely contains most of the line count.

#### Logical Groupings
- **Dialog**: ExportDialog (UI, validation, user choices).
- **Manager**: ExportManager (export logic, formats, I/O).

#### Refactoring Opportunities

##### Opportunity 1: Move ExportManager to a separate module

**Proposed Structure**:
- New module: `src/core/export_manager.py` (or `src/utils/export_manager.py`).
  - Move: `ExportManager` class.
- `export_dialog.py`: Keep `ExportDialog`, import and use `ExportManager`. Dialog focuses on UI and passing options to manager.

**Benefits**:
- Shrinks export_dialog.py significantly; export logic can be tested without UI.
- Reuse of ExportManager from scripts or other dialogs.

**Evaluation**:
- **Ease of Implementation**: 4/5 – Clear class boundary.
- **Safety**: 4/5 – Dialog only needs to instantiate and call manager.
- **Practicality**: 4/5 – High benefit.
- **Recommendation**: 4/5 – Recommended.
- **Overall Score**: 4.00/5

**Priority**: High

---

### File: file_operations_handler.py

**Location**: `src/core/file_operations_handler.py`  
**Line Count**: 1680  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- **ProgressDialogEventFilter** (small class).
- **FileOperationsHandler** (class): `open_files`, `open_folder`, `open_recent_file`, `open_paths`, `load_first_slice`; helpers for progress dialog, large-file check, formatting. Methods `open_*` and `open_paths` are long (lots of steps).

#### Refactoring Opportunities

##### Opportunity 1: Extract progress and path-list handling into helpers

**Proposed Structure**:
- Same file or `src/core/file_operations_progress.py`: Extract `_create_progress_dialog`, `_start_animated_loading`, `_stop_animated_loading`, `_on_cancel_loading`, `_close_progress_dialog`, `_check_large_files`, `_format_source_name`, `_format_final_status` into a small `LoadingProgressHelper` or keep as private methods but split `open_paths`/`open_folder` into smaller methods (e.g. `_load_studies_from_paths`, `_show_progress_while_loading`).
- Focus on breaking the long `open_*` methods into named steps for readability and unit-testing of discrete steps.

**Benefits**:
- Improves readability and testability without necessarily moving to a new file; optional new module for progress if reused elsewhere.

**Evaluation**:
- **Ease of Implementation**: 4/5 – Internal refactor.
- **Safety**: 3/5 – Core loading path; tests required.
- **Practicality**: 4/5 – Worth doing.
- **Recommendation**: 4/5 – Recommended.
- **Overall Score**: 3.75/5

**Priority**: Medium

---

### Remaining Files Over 750 Lines (Brief)

- **slice_display_manager.py** (1321): Single class. Consider extracting slice-to-image pipeline steps or view-state helpers into smaller modules if the class grows further.
- **overlay_manager.py** (1310): ViewportOverlayWidget + OverlayManager. Consider moving ViewportOverlayWidget to `overlay_widget.py` to separate drawing from manager logic.
- **tag_export_dialog.py** (1288): Dialog + export logic. Same pattern as export_dialog: consider extracting “tag export runner” to a core/util module.
- **config_manager.py** (1185): Many get/set for settings. Consider grouping into domain-specific config objects (e.g. overlay config, window config) to shrink file or split by domain.
- **annotation_manager.py** (1173): Single class. Consider extracting ROI persistence or serialization if present.
- **fusion_controls_widget.py** (1131): Large widget. Consider splitting into sub-widgets (e.g. fusion type, blend, visibility).
- **roi_manager.py** (1124), **view_state_manager.py** (1080), **undo_redo.py** (1060), **fusion_coordinator.py** (1016), **roi_coordinator.py** (988): Single-class modules; refactor when touching for features (extract helpers or sub-domains).
- **series_navigator.py** (875), **fusion_handler.py** (875): Medium size; refactor if adding features.
- **quick_start_guide_dialog.py** (823), **fusion_technical_doc_dialog.py** (811): Content-heavy; consider moving static content to resources/markdown.
- **dicom_loader.py** (747): Just over threshold; monitor or extract “loading strategy” if it grows.

---

## Prioritized Recommendations

### High Priority (Overall Score ≥ 4.0 or high impact)
1. **Extract MeasurementTool graphics items to measurement_items.py** – Score: 4.00/5  
   - File: measurement_tool.py  
   - Clear boundary; reduces file by ~900 lines; low risk.

2. **Extract ExportManager from export_dialog.py** – Score: 4.00/5  
   - File: export_dialog.py  
   - Same pattern; improves testability and separation.

3. **Extract MainWindow theme to main_window_theme.py** – Score: 4.00/5  
   - File: main_window.py  
   - Easy, safe, and improves maintainability of styling.

4. **Extract annotation copy/paste from main.py into AnnotationPasteHandler** – Score: 3.75/5  
   - File: main.py  
   - Large, self-contained block; good payoff.

5. **Split DICOMProcessor into rescale/color/window_level/projections/stats modules** – Score: 3.75/5  
   - File: dicom_processor.py  
   - Core logic; facade keeps API stable.

6. **Extract MainWindow menu bar builder** – Score: 3.75/5  
   - File: main_window.py  
   - Shrinks long method and clarifies structure.

7. **Extract file/series loading coordinator from main.py** – Score: 3.50/5  
   - File: main.py  
   - High impact; do incrementally.

8. **Extract subwindow lifecycle/focus from main.py** – Score: 3.00/5  
   - File: main.py  
   - Highest line reduction; do in small steps (e.g. getters first, then focus, then signals).

9. **Extract image_viewer mouse handling (or at least break mousePressEvent into smaller methods)** – Score: 3.25/5  
   - File: image_viewer.py  
   - Improves readability and testability of the largest GUI widget.

### Medium Priority (Overall Score 3.0–3.9)
1. **Extract cine and projection callbacks from main.py** – Score: 3.75/5  
2. **Extract pixel info/magnifier helper from image_viewer.py** – Score: 3.75/5  
3. **File_operations_handler: break long open_* methods into smaller steps / progress helper** – Score: 3.75/5  
4. **overlay_manager: move ViewportOverlayWidget to overlay_widget.py** – Suggested  
5. **tag_export_dialog: extract tag export runner** – Suggested  

### Low Priority (Overall Score < 3.0 or lower impact)
- **config_manager / annotation_manager / fusion_controls_widget / roi_manager / coordinators**: Refactor when adding features or when file size grows further.
- **quick_start_guide_dialog / fusion_technical_doc_dialog**: Move static content to resources if desired; lower code-impact.

---

## Files Appropriately Large

None are designated “appropriately large” with no refactoring recommended. All files over 750 lines have at least one refactoring opportunity documented above. The following are lower priority rather than “leave as-is”:

- **dicom_loader.py** (747): Slightly over 750-line guideline; keep as-is unless it grows.
- **create_appimage.sh** (193): Under 500–600 shell threshold; no action.

---

## Observations and Patterns

1. **main.py** is the dominant problem: one 5800+ line class with many responsibilities. The template’s 600-line Python guideline and 750-line base threshold both flag it. Breaking it by feature (subwindow, file/series, annotations, cine, projection) will have the largest impact.
2. **GUI widgets** (image_viewer, main_window) carry large event and UI-building code; extracting event handlers and UI builders (menu, toolbar, theme) improves readability and testability.
3. **Core modules** (dicom_processor, file_operations_handler) are single-class with long methods; splitting by domain or extracting helpers keeps them under control.
4. **Dialogs** that both show UI and perform heavy work (export_dialog, tag_export_dialog) benefit from moving “worker” logic into a separate manager/runner module.
5. **Coordinator** modules (fusion_coordinator, roi_coordinator, etc.) are already separated; they sit in the 900–1100 line range and can be refined when touched.
6. **Backup files** were correctly excluded; only `src/`, `scripts/`, and `tests/` were analyzed.

---

## Next Steps

- [ ] Review prioritized recommendations with team/user
- [x] Choose 2–3 high-priority items for the first implementation phase (e.g. measurement_items extraction, ExportManager extraction, main_window_theme extraction)
- [x] Create implementation plans and tests for chosen refactorings *(Phase 1 completed 2026-02-18: measurement_items, ExportManager, main_window_theme.)*
- [ ] Schedule refactoring work in small increments; re-run this assessment after major refactors
- [ ] Update this assessment file when refactorings are completed (line counts and status)
