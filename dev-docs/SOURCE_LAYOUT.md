# Source layout (`src/`)

**Last updated:** 2026-08-13
**Purpose:** Compact controller, bootstrap, and signal-wiring index. Agents should read **[`ARCHITECTURE.md`](../ARCHITECTURE.md)** first for domains and dependency rules, then open the on-demand [detailed module tree](info/SOURCE_LAYOUT_MODULE_TREE.md) only when file-level navigation is needed.

---

## Module navigation

| Need | Start with |
|---|---|
| App bootstrap, mixins, or signal ordering | This file’s [bootstrap](#dicomviewerapp__init__-order) and [signal-wiring](#signal-wiring-_connect_signals) sections |
| File-level ownership within a domain | [Detailed module tree](info/SOURCE_LAYOUT_MODULE_TREE.md) |
| Domain boundaries or a change-area entry point | [`ARCHITECTURE.md`](../ARCHITECTURE.md#where-to-change-what) |
| Local subtree invariants and focused tests | `src/core/AGENTS.md`, `src/gui/AGENTS.md`, or `src/qa/AGENTS.md` when working in that subtree |

---

## Key controllers

| Controller | File | Owns / coordinates |
|---|---|---|
| `DICOMViewerApp` | `src/main.py` + `src/main_app_*.py` mixins | Top-level orchestrator (plain mixin composition); delegates to all controllers below |
| `MetadataController` | `src/metadata/metadata_controller.py` | `MetadataPanel`, `TagEditHistoryManager`, undo/redo callbacks, privacy mode for metadata |
| `ROIMeasurementController` | `src/roi/roi_measurement_controller.py` | `ROIManager`, `MeasurementTool`, `AnnotationManager`, `ROIStatisticsPanel`, `ROIListPanel`; tracks active (focused-subwindow) managers via `update_focused_managers()` |
| `SubwindowLifecycleController` | `src/core/subwindow_lifecycle_controller.py` | Per-subwindow manager creation, focus changes, display updates |
| `PrivacyController` | `src/core/privacy_controller.py` | Privacy-mode propagation (metadata, overlay/crosshair managers, image viewers) and overlay refresh after privacy change; invoked from `core.actions.view_actions.on_privacy_view_toggled` via `DICOMViewerApp._on_privacy_view_toggled` |
| `SliceSyncCoordinator` | `src/core/slice_sync_coordinator.py` | Linked-group anatomic slice sync; geometry cache keyed by `(study_uid, series_uid)`; off by default |
| `SliceLocationLineCoordinator` | `src/gui/slice_location_line_coordinator.py` | Cross-pane slice-location reference lines; delegates segment math to `slice_location_line_helper` |
| `MainWindow` | `src/gui/main_window.py` + helpers below | Shell: signals, layout/splitter, theme, drag/drop; delegates toast/recent/fullscreen/overlay/status |
| `MainWindowToastController` | `src/gui/main_window_toast_controller.py` | Temporary toast/banner overlay (`show_toast_message` wrapper on `MainWindow`) |
| `MainWindowRecentFilesManager` | `src/gui/main_window_recent_files_manager.py` | Recent-files menu rebuild, context menu (owns `eventFilter` on `recent_menu`), edit-list dialog |
| `MainWindowFullscreenManager` | `src/gui/main_window_fullscreen_manager.py` | Fullscreen enter/exit, chrome snapshot/restore, `changeEvent` / `closeEvent` helpers |
| `MainWindowOverlayOptionsMixin` | `src/gui/main_window_overlay_options.py` | View/overlay toggles, check-state sync, font/color pickers (mixed into `MainWindow`) |
| `MainWindowStatusController` | `src/gui/main_window_status_controller.py` | Status-bar labels (file/study, zoom+W/L, pixel info) |
| `show_about` | `src/gui/dialogs/about_dialog.py` | About dialog HTML + `disclaimer://` link callback |

### Slice sync and location-line flow

1. **Config** — `SliceSyncConfigMixin` (`utils/config/slice_sync_config.py`) persists `slice_sync_enabled`, `slice_sync_groups`, and slice-location line visibility/style.
2. **Slice change** — `SliceSyncCoordinator.on_slice_changed(source_idx)` updates linked panes when sync is enabled; `SliceLocationLineCoordinator.refresh_all()` (or targeted refresh) runs regardless.
3. **Geometry** — `slice_geometry.py` builds `SliceStack` / `SlicePlane` from DICOM IPP/IOP; `find_nearest_slice` enforces a half-thickness tolerance so non-overlapping stacks do not jump.
4. **UI** — **View → Manage Sync Groups…** (`slice_sync_dialog.py`); **View → Show Slice Location Lines** toggles the coordinator via config.

Tests: `tests/core/test_slice_sync_coordinator_unit.py`, `tests/core/test_slice_geometry.py`, `tests/core/test_slice_location_line_helper_logic.py`, `tests/utils/test_slice_sync_config.py`.

---

## `DICOMViewerApp.__init__` order

The constructor delegates to five helpers in strict order (each step depends on the previous):

1. `_init_core_managers()` – Qt app, DICOM managers, history, undo/redo, config, privacy state.
2. `_init_main_window_and_layout()` – `MainWindow`, `FileDialog`, `MultiWindowLayout`, theme.
3. `_init_controllers_and_tools()` – `MetadataController`, `ROIMeasurementController`.
4. `_init_view_widgets()` – navigators, cine, fusion, overlays, scroll-wheel mode.
5. `_post_init_subwindows_and_handlers()` – UI assembly, per-subwindow managers, handlers, signals, pan mode.

---

## Signal wiring (`_connect_signals`)

All Qt signal connections for `DICOMViewerApp` are wired in a single call to `_connect_signals()` (invoked from `_post_init_subwindows_and_handlers`). That method delegates to focused sub-methods in `core/app_signal_wiring.py` via `wire_all_signals`:

| Sub-method | Responsibility |
|---|---|
| `_connect_layout_signals()` | Multi-window layout and main-window layout-change signals |
| `_connect_file_signals()` | File open/close and application-quit signals |
| `_connect_dialog_signals()` | Dialog/panel open signals (settings, overlays, export, etc.) |
| `_connect_undo_redo_and_annotation_signals()` | Undo/redo stack and annotation signals |
| `_connect_cine_signals()` | Cine playback control signals |
| `_connect_view_signals()` | View-mode, privacy, smoothing, and scroll-wheel signals |
| `_connect_customization_signals()` | Theme/customization applied signals |
| `_connect_subwindow_signals()` | Per-subwindow signals (files dropped, etc.) |
| `_connect_focused_subwindow_signals()` | Focused-subwindow state change signals |

**Rule:** signal connections live only in the `_connect_signals` family. No `connect()` calls in other `_init_*` helpers. Order is intentional: layout and file signals before dialog signals. **Exception:** annotation **Copy** / **Paste** menu signals connect to `AnnotationPasteHandler` on the app (same wiring module).
