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

- [ ] Define `LoadingProgressManager` class in `src/core/loading_progress_manager.py`:
  - [ ] Owns: `_loading_timer`, `_loading_base_message`, `_loading_dot_state`, `_progress_dialog`, `_progress_event_filter`, `_user_cancelled`.
  - [ ] Methods:
    - [ ] `start_animated_loading(base_message: str, update_callback: Callable) -> None`
    - [ ] `stop_animated_loading() -> None`
    - [ ] `create_progress_dialog(parent, total_files: int, message: str) -> QProgressDialog`
    - [ ] `close_progress_dialog() -> None`
    - [ ] `on_cancel_loading() -> None`
    - [ ] `is_cancelled() -> bool`
    - [ ] `reset() -> None` – clear all state for next operation.
  - [ ] Constructor takes: `update_status_callback: Callable` (for "Loading…" status bar messages).
- [ ] Define how `FileOperationsHandler` uses `LoadingProgressManager`:
  - [ ] `FileOperationsHandler` creates one `LoadingProgressManager` instance in `__init__`.
  - [ ] All progress/animation calls in `open_files`, `open_folder`, `open_recent_file`, `open_paths` delegate to the manager.
- [ ] Confirm `ProgressDialogEventFilter` moves into `loading_progress_manager.py` as it belongs to the infrastructure.

### Phase 2.2 – Implementation

- [ ] Back up `src/core/file_operations_handler.py` to `backups/` before editing.
- [ ] Create `src/core/loading_progress_manager.py` with `LoadingProgressManager` and `ProgressDialogEventFilter`.
- [ ] Update `FileOperationsHandler.__init__` to instantiate `LoadingProgressManager` and remove the now-moved attributes.
- [ ] Replace all direct progress/animation calls in each open-file method with delegation to `self._loading_manager.*`.
- [ ] Verify `open_files`, `open_folder`, `open_recent_file`, `open_paths`, and `load_first_slice` all still compile and behave identically.

### Phase 2.3 – Testing

- [ ] Identify existing tests for file loading.
- [ ] Design new unit tests for `LoadingProgressManager`:
  - [ ] `start_animated_loading` starts the timer and sets base message.
  - [ ] `stop_animated_loading` clears the timer.
  - [ ] `on_cancel_loading` sets `is_cancelled()` to True.
  - [ ] `reset()` clears all state.
  - [ ] `create_progress_dialog` returns a `QProgressDialog`.
- [ ] Implement new tests in `tests/core/test_loading_progress_manager.py`.
- [ ] Run full automated test suite: `python -m pytest tests/ -v`
- [ ] Manual smoke tests:
  - [ ] Open single file(s) and observe loading animation and progress dialog.
  - [ ] Open a folder with many files and verify progress and cancellation work.
  - [ ] Open a recent file and observe correct loading behavior.
  - [ ] Cancel a load mid-way and confirm state resets cleanly.

---

## Phase 3 – Split `ConfigManager` by Feature Domain Using Mixins

### Rationale

`ConfigManager` (1248 lines) manages settings for every feature area in the application in a single class. While the API is simple (get/set pairs backed by a JSON dict), the file is large and adding new settings requires editing a single growing file. Splitting into feature-domain mixin classes means each area's settings are co-located, easier to find, and easier to test in isolation — without changing a single callsite.

### Phase 3.1 – Design

Identify the following feature-domain mixins and their methods:

- [ ] `PathsConfigMixin` (`src/utils/config/paths_config.py`):
  - `get_last_path`, `set_last_path`, `get_last_export_path`, `set_last_export_path`
  - `get_recent_files`, `add_recent_file`, `remove_recent_file`, `normalize_path`

- [ ] `DisplayConfigMixin` (`src/utils/config/display_config.py`):
  - `get_theme`, `set_theme`
  - `get_smooth_image_when_zoomed`, `set_smooth_image_when_zoomed`
  - `get_privacy_view`, `set_privacy_view`
  - `get_scroll_wheel_mode`, `set_scroll_wheel_mode`

- [ ] `OverlayConfigMixin` (`src/utils/config/overlay_config.py`):
  - `get_overlay_mode`, `set_overlay_mode`
  - `get_overlay_visibility_state`, `set_overlay_visibility_state`
  - `get_overlay_custom_fields`, `set_overlay_custom_fields`
  - `get_overlay_font_size`, `set_overlay_font_size`
  - `get_overlay_font_color`, `set_overlay_font_color`
  - `get_overlay_tags`, `set_overlay_tags`, `get_all_modalities`

- [ ] `LayoutConfigMixin` (`src/utils/config/layout_config.py`):
  - `get_multi_window_layout`, `set_multi_window_layout`
  - `get_view_slot_order`, `set_view_slot_order`

- [ ] `ROIConfigMixin` (`src/utils/config/roi_config.py`):
  - `get_roi_font_size`, `set_roi_font_size`
  - `get_roi_font_color`, `set_roi_font_color`
  - `get_roi_line_thickness`, `set_roi_line_thickness`
  - `get_roi_line_color`, `set_roi_line_color`
  - `get_roi_default_visible_statistics`, `set_roi_default_visible_statistics`

- [ ] `MeasurementConfigMixin` (`src/utils/config/measurement_config.py`):
  - `get_measurement_font_size`, `set_measurement_font_size`
  - `get_measurement_font_color`, `set_measurement_font_color`
  - `get_measurement_line_thickness`, `set_measurement_line_thickness`
  - `get_measurement_line_color`, `set_measurement_line_color`

- [ ] `AnnotationConfigMixin` (`src/utils/config/annotation_config.py`):
  - `get_text_annotation_color`, `set_text_annotation_color`
  - `get_text_annotation_font_size`, `set_text_annotation_font_size`
  - `get_arrow_annotation_color`, `set_arrow_annotation_color`
  - `get_arrow_annotation_size`, `set_arrow_annotation_size`

- [ ] `CineConfigMixin` (`src/utils/config/cine_config.py`):
  - `get_cine_default_speed`, `set_cine_default_speed`
  - `get_cine_default_loop`, `set_cine_default_loop`

- [ ] `MetadataUIConfigMixin` (`src/utils/config/metadata_ui_config.py`):
  - `get_metadata_panel_column_widths`, `set_metadata_panel_column_widths`
  - `get_metadata_panel_column_order`, `set_metadata_panel_column_order`

- [ ] `TagExportConfigMixin` (`src/utils/config/tag_export_config.py`):
  - `get_tag_export_presets`, `save_tag_export_preset`, `delete_tag_export_preset`
  - `export_tag_export_presets`, `import_tag_export_presets`

- [ ] `CustomizationsConfigMixin` (`src/utils/config/customizations_config.py`):
  - `export_customizations`, `import_customizations`

- [ ] `AppConfigMixin` (`src/utils/config/app_config.py`):
  - `get_disclaimer_accepted`, `set_disclaimer_accepted`

- [ ] **`ConfigManager` in `src/utils/config_manager.py` becomes a thin facade**:
  - Inherits from all mixins in a clear, documented order.
  - Retains only `__init__`, `_load_config`, `save_config`, `get`, and `set`.
  - All callers continue to use `config_manager.get_roi_font_size()` etc. without any changes.

- [ ] Create `src/utils/config/__init__.py` to make `config/` a package.
- [ ] Decide whether mixin base class should be a `ConfigMixinBase` that each mixin inherits from (to type-annotate access to `self._config` and `save_config`).

### Phase 3.2 – Implementation

- [ ] Back up `src/utils/config_manager.py` to `backups/` before editing.
- [ ] Create `src/utils/config/` package with `__init__.py`.
- [ ] Create each mixin file, moving the appropriate methods from `config_manager.py` into it.
  - [ ] Each mixin method accesses `self._config` and `self.save_config()` exactly as in the original (these are provided by `ConfigManager.__init__` and the base class).
- [ ] Update `ConfigManager` to inherit from all mixins and remove moved methods.
- [ ] Verify `ConfigManager`'s public API is unchanged by running a full import check.

### Phase 3.3 – Testing

- [ ] Identify existing config manager tests.
- [ ] Design new unit tests for each mixin, verifiable without a full `ConfigManager`:
  - [ ] Each mixin's get/set pair: default value returned when key absent; persisted value returned after set.
  - [ ] Recent files: add, retrieve, remove; deduplication; max-length enforcement.
  - [ ] Overlay tags: get for known modality; get for unknown modality returns default.
  - [ ] Tag export presets: save, retrieve, delete.
- [ ] Implement new tests in `tests/config/test_<mixin_name>.py` for each mixin.
- [ ] Run full automated test suite: `python -m pytest tests/ -v`
- [ ] Manual smoke tests:
  - [ ] Launch app; verify all settings load correctly.
  - [ ] Change theme, overlay settings, ROI/measurement colors via the Settings dialog and confirm they persist after restart.

---

## Phase 4 – Final Verification and New Refactor Assessment

### Phase 4.1 – Documentation

- [ ] Update `AGENTS.md` to reflect:
  - [ ] `src/utils/config/` package structure (list all mixin files).
  - [ ] `LoadingProgressManager` class location.
  - [ ] `_connect_signals` sub-method naming convention.
- [ ] Ensure no references to old single-file structure remain in inline comments.

### Phase 4.2 – New Refactor Assessment (Final Step)

- [ ] Run a new refactor assessment using `dev-docs/templates-generalized/refactor-assessment-template.md`:
  - [ ] Create a new timestamped file under `dev-docs/refactor-assessments/`.
  - [ ] Recompute file line counts for `src/main.py`, `src/core/file_operations_handler.py`, `src/utils/config_manager.py`, and all new files.
  - [ ] Document how the refactoring changed sizes, responsibilities, and coupling.
  - [ ] Record any new refactoring opportunities discovered.
