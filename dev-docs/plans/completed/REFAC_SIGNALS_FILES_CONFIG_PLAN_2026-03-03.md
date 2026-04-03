## Refactor Plan – Signal Routing, File Operations Handler, and Config Manager

- **Date**: 2026-03-03
- **Source**: Refactor assessment `refactor-assessment-2026-03-03-160000.md` (Opportunities 1, 2, 3)
- **Target Files**:
  - `src/main.py` – `_connect_signals` method (~98 lines, lines 1417–1515)
  - `src/core/file_operations_handler.py` – 1687 lines, multiple open-file methods
  - `src/utils/config_manager.py` – 1248 lines, ~80 methods across ~10 feature domains
- **Goals**:
  1. **Split `_connect_signals` into grouped feature-area sub-methods** inside `DICOMViewerApp`.
  2. **Extract loading/progress infrastructure from `FileOperationsHandler`** into a dedicated `LoadingProgressManager` class, reducing the handler to its core open-file logic.
  3. **Split `ConfigManager` by feature domain** using mixin classes that ConfigManager inherits from, preserving the existing API entirely.
  4. **Write or extend automated tests** for changed modules.
  5. **Run the full test suite** and confirm all tests pass.

---

## Phase 0 – Planning and Scoping

- [x] Review this plan and confirm approach with user before starting.
- [x] Confirm exact line ranges for each signal group in `_connect_signals`.
- [x] Confirm which `FileOperationsHandler` methods share common infrastructure (progress dialog, animated loading, cancellation).
- [x] List all `ConfigManager` methods and assign each to a feature domain mixin.
- [x] Back up all files to be modified: `src/main.py`, `src/core/file_operations_handler.py`, `src/utils/config_manager.py`.

---

## Phase 1 – Split `_connect_signals` into Grouped Sub-methods

### Rationale

`_connect_signals` is a single 98-line method that connects signals across all feature areas (layout, file operations, dialogs, cine, privacy, theme, undo/redo, annotations, export). This makes it hard to find and maintain specific signal connections. Splitting it into named sub-methods grouped by feature area improves navigability with zero behavioral change.

### Phase 1.1 – Design

- [x] Identify signal groups and define sub-method names:
  - [x] `_connect_layout_signals()` – multi-window layout focus/layout-change, main window layout.
  - [x] `_connect_file_signals()` – open files/folder/recent, open from paths, close, app quit.
  - [x] `_connect_dialog_signals()` – settings, overlay settings, tag viewer, overlay config, annotation options, quick-start guide, fusion tech doc, tag export, histogram, ROI stats export, about-this-file, export/export-screenshots.
  - [x] `_connect_undo_redo_and_annotation_signals()` – undo/redo tag edits, annotation copy/paste.
  - [x] `_connect_cine_signals()` – cine controls widget (play, pause, stop, speed, loop, frame slider, loop bounds), cine player (frame advance, state change).
  - [x] `_connect_view_signals()` – privacy toggle, smooth-when-zoomed toggle, theme change.
  - [x] `_connect_customization_signals()` – export/import customizations, export/import tag presets.
  - [x] `_connect_subwindow_signals()` already exists; keep the existing call.
  - [x] `_connect_focused_subwindow_signals()` already exists; keep the existing call.
- [x] Confirm that `_connect_signals` becomes only a sequence of calls to these sub-methods.

### Phase 1.2 – Implementation

- [x] Back up `src/main.py` to `backups/main.py` (or timestamped) before editing.
- [x] Extract each signal group block into its private sub-method with a clear docstring.
- [x] Replace the full body of `_connect_signals` with ordered calls to each sub-method.
- [x] Verify no signals were accidentally omitted or duplicated.

### Phase 1.3 – Testing

- [x] Identify any existing signal-wiring tests.
- [x] Run full automated test suite; confirm no regressions: `python -m pytest tests/ -v`
- [x] Manual smoke tests:
  - [x] Open files via menu and drag-and-drop.
  - [x] Toggle privacy view, smoothing, and theme.
  - [x] Trigger cine play/pause/stop.
  - [x] Trigger undo/redo (tag edit and annotation).
  - [x] Open settings, overlay config, tag viewer, quick start guide.
  - [x] Change layout (1x1, 1x2, 2x1, 2x2).

---

## Phase 2 – Extract Loading Progress Infrastructure from `FileOperationsHandler`

### Rationale

`FileOperationsHandler` (1687 lines) contains four large open-file methods (`open_files`, `open_folder`, `open_recent_file`, `open_paths`) that all share the same animated-loading timer, progress dialog, and cancellation infrastructure. This shared infrastructure is about ~130 lines and is replicated in each method's setup/teardown. Extracting it into a dedicated `LoadingProgressManager` reduces coupling, makes each open-file method shorter, and makes the progress infrastructure independently testable.

### Phase 2.1 – Design

- [x] Define `LoadingProgressManager` class in `src/core/loading_progress_manager.py`:
  - [x] Owns: `_loading_timer`, `_loading_base_message`, `_loading_dot_state`, `_progress_dialog`, `_progress_event_filter`, `_user_cancelled`.
  - [x] Methods:
    - [x] `start_animated_loading(base_message: str) -> None`
    - [x] `stop_animated_loading() -> None`
    - [x] `create_progress_dialog(parent, total_files: int, message: str) -> QProgressDialog`
    - [x] `close_progress_dialog() -> None`
    - [x] `on_cancel_loading() -> None`
    - [x] `is_cancelled() -> bool`
    - [x] `was_dialog_cancelled() -> bool` (added: reflects dialog Cancel-button state)
    - [x] `get_dialog() -> Optional[QProgressDialog]` (added: dialog accessor for callbacks)
    - [x] `reset() -> None` – clear all state for next operation.
  - [x] Constructor takes: `update_status_callback: Callable` and `cancel_loader_callback: Optional[Callable]`.
- [x] Define how `FileOperationsHandler` uses `LoadingProgressManager`:
  - [x] `FileOperationsHandler` creates one `LoadingProgressManager` instance in `__init__`.
  - [x] All progress/animation calls in `open_files`, `open_folder`, `open_recent_file`, `open_paths` delegate to the manager.
- [x] Confirm `ProgressDialogEventFilter` moves into `loading_progress_manager.py` as it belongs to the infrastructure.

### Phase 2.2 – Implementation

- [x] Back up `src/core/file_operations_handler.py` to `backups/` before editing. (backup existed: `backups/file_operations_handler_2026-03-03.py`)
- [x] Create `src/core/loading_progress_manager.py` with `LoadingProgressManager` and `ProgressDialogEventFilter`.
- [x] Update `FileOperationsHandler.__init__` to instantiate `LoadingProgressManager` and remove the now-moved attributes.
- [x] Replace all direct progress/animation calls in each open-file method with delegation to `self._loading_manager.*`.
- [x] Verify `open_files`, `open_folder`, `open_recent_file`, `open_paths`, and `load_first_slice` all still compile and behave identically. (92 existing tests still pass)

### Phase 2.3 – Testing

- [x] Identify existing tests for file loading. (none existed; 92 unrelated tests confirmed passing)
- [x] Design new unit tests for `LoadingProgressManager`:
  - [x] `start_animated_loading` starts the timer and sets base message.
  - [x] `stop_animated_loading` clears the timer.
  - [x] `on_cancel_loading` sets `is_cancelled()` to True.
  - [x] `reset()` clears all state.
  - [x] `create_progress_dialog` returns a `QProgressDialog`.
- [x] Implement new tests in `tests/core/test_loading_progress_manager.py`. (27 tests, all passing)
- [x] Run full automated test suite: `python -m pytest tests/ -v` (119 tests pass)
- [x] Manual smoke tests:
  - [x] Open single file(s) and observe loading animation and progress dialog.
  - [x] Open a folder with many files and verify progress and cancellation work.
  - [x] Open a recent file and observe correct loading behavior.
  - [x] Cancel a load mid-way and confirm state resets cleanly.

---

## Phase 3 – Split `ConfigManager` by Feature Domain Using Mixins

### Rationale

`ConfigManager` (1248 lines) manages settings for every feature area in the application in a single class. While the API is simple (get/set pairs backed by a JSON dict), the file is large and adding new settings requires editing a single growing file. Splitting into feature-domain mixin classes means each area's settings are co-located, easier to find, and easier to test in isolation — without changing a single callsite.

### Phase 3.1 – Design

Identify the following feature-domain mixins and their methods:

- [x] `PathsConfigMixin` (`src/utils/config/paths_config.py`):
  - `get_last_path`, `set_last_path`, `get_last_export_path`, `set_last_export_path`
  - `get_recent_files`, `add_recent_file`, `remove_recent_file`, `normalize_path`

- [x] `DisplayConfigMixin` (`src/utils/config/display_config.py`):
  - `get_theme`, `set_theme`
  - `get_smooth_image_when_zoomed`, `set_smooth_image_when_zoomed`
  - `get_privacy_view`, `set_privacy_view`
  - `get_scroll_wheel_mode`, `set_scroll_wheel_mode`

- [x] `OverlayConfigMixin` (`src/utils/config/overlay_config.py`):
  - `get_overlay_mode`, `set_overlay_mode`
  - `get_overlay_visibility_state`, `set_overlay_visibility_state`
  - `get_overlay_custom_fields`, `set_overlay_custom_fields`
  - `get_overlay_font_size`, `set_overlay_font_size`
  - `get_overlay_font_color`, `set_overlay_font_color`
  - `get_overlay_tags`, `set_overlay_tags`, `get_all_modalities`

- [x] `LayoutConfigMixin` (`src/utils/config/layout_config.py`):
  - `get_multi_window_layout`, `set_multi_window_layout`
  - `get_view_slot_order`, `set_view_slot_order`

- [x] `ROIConfigMixin` (`src/utils/config/roi_config.py`):
  - `get_roi_font_size`, `set_roi_font_size`
  - `get_roi_font_color`, `set_roi_font_color`
  - `get_roi_line_thickness`, `set_roi_line_thickness`
  - `get_roi_line_color`, `set_roi_line_color`
  - `get_roi_default_visible_statistics`, `set_roi_default_visible_statistics`

- [x] `MeasurementConfigMixin` (`src/utils/config/measurement_config.py`):
  - `get_measurement_font_size`, `set_measurement_font_size`
  - `get_measurement_font_color`, `set_measurement_font_color`
  - `get_measurement_line_thickness`, `set_measurement_line_thickness`
  - `get_measurement_line_color`, `set_measurement_line_color`

- [x] `AnnotationConfigMixin` (`src/utils/config/annotation_config.py`):
  - `get_text_annotation_color`, `set_text_annotation_color`
  - `get_text_annotation_font_size`, `set_text_annotation_font_size`
  - `get_arrow_annotation_color`, `set_arrow_annotation_color`
  - `get_arrow_annotation_size`, `set_arrow_annotation_size`

- [x] `CineConfigMixin` (`src/utils/config/cine_config.py`):
  - `get_cine_default_speed`, `set_cine_default_speed`
  - `get_cine_default_loop`, `set_cine_default_loop`

- [x] `MetadataUIConfigMixin` (`src/utils/config/metadata_ui_config.py`):
  - `get_metadata_panel_column_widths`, `set_metadata_panel_column_widths`
  - `get_metadata_panel_column_order`, `set_metadata_panel_column_order`

- [x] `TagExportConfigMixin` (`src/utils/config/tag_export_config.py`):
  - `get_tag_export_presets`, `save_tag_export_preset`, `delete_tag_export_preset`
  - `export_tag_export_presets`, `import_tag_export_presets`

- [x] `CustomizationsConfigMixin` (`src/utils/config/customizations_config.py`):
  - `export_customizations`, `import_customizations`

- [x] `AppConfigMixin` (`src/utils/config/app_config.py`):
  - `get_disclaimer_accepted`, `set_disclaimer_accepted`

- [x] **`ConfigManager` in `src/utils/config_manager.py` becomes a thin facade**:
  - Inherits from all mixins in a clear, documented order.
  - Retains only `__init__`, `_load_config`, `save_config`, `get`, and `set`.
  - All callers continue to use `config_manager.get_roi_font_size()` etc. without any changes.

- [x] Create `src/utils/config/__init__.py` to make `config/` a package.
- [x] No `ConfigMixinBase` needed: mixins rely on `self.config` and `self.save_config()` provided by `ConfigManager.__init__` via Python's MRO; documented in each mixin's docstring.

### Phase 3.2 – Implementation

- [x] Back up `src/utils/config_manager.py` to `backups/` before editing. (backup: `backups/config_manager_pre_mixin_split.py`)
- [x] Create `src/utils/config/` package with `__init__.py`.
- [x] Create each mixin file, moving the appropriate methods from `config_manager.py` into it.
  - [x] Each mixin method accesses `self.config` and `self.save_config()` exactly as in the original.
- [x] Update `ConfigManager` to inherit from all mixins and remove moved methods.
- [x] Verify `ConfigManager`'s public API is unchanged by running a full import check. (119 existing tests pass)

### Phase 3.3 – Testing

- [x] Identify existing config manager tests. (`tests/test_config_manager_smooth_zoomed.py` – still passing)
- [x] Design new unit tests for each mixin, verifiable without a full `ConfigManager`:
  - [x] Each mixin's get/set pair: default value returned when key absent; persisted value returned after set.
  - [x] Recent files: add, retrieve, remove; deduplication; max-length enforcement.
  - [x] Overlay tags: get for known modality; get for unknown modality returns default.
  - [x] Tag export presets: save, retrieve, delete.
- [x] Implement new tests in `tests/config/test_<mixin_name>.py` for each mixin. (114 new tests across 8 mixin test files)
- [x] Run full automated test suite: `python -m pytest tests/ -v` (233 total tests pass)
- [x] Manual smoke tests:
  - [x] Launch app; verify all settings load correctly.
  - [x] Change theme, overlay settings, ROI/measurement colors via the Settings dialog and confirm they persist after restart.

---

## Phase 4 – Final Verification

### Phase 4.1 – Documentation

- [x] Update `AGENTS.md` to reflect:
  - [x] `src/utils/config/` package structure (list all mixin files). *(already present from Phase 3)*
  - [x] `LoadingProgressManager` class location. *(already present from Phase 2)*
  - [x] `_connect_signals` sub-method naming convention. *(added: table of sub-methods + wiring rule)*
- [x] Ensure no references to old single-file structure remain in inline comments. *(confirmed: none found)*

### Phase 4.2 – New Refactor Assessment

- [N/A] Skipped — no new assessment needed at this time.
