# Agent instructions – DICOM Viewer V3

Guidance for AI agents and developers working in this repository.

## Virtual environment (venv)

**Always activate the venv in the `venv` directory before running tests or application code.**

- **Windows (Command Prompt):** `venv\Scripts\activate`
- **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
- **macOS / Linux:** `source venv/bin/activate`

From project root, after activation:

- Run the app: `python src/main.py`
- Run tests: `python tests/run_tests.py` or `python -m pytest tests/ -v`

If no venv exists, create one: `python -m venv venv`, activate it, then `pip install -r requirements.txt`.

## Other conventions

- See `.cursor/rules` and user rules for backup-before-modify, testing, and commit guidelines.
- Project layout: `src/` (application), `tests/` (tests), `dev-docs/` (plans, assessments).
- **Versioning**: Application version is defined in a single place, `src/version.py` (`__version__`). Use semantic versioning; release steps are in `dev-docs/RELEASING.md`, with full rules in `dev-docs/info/SEMANTIC_VERSIONING_GUIDE.md`.

## Source module structure (`src/`)

```
src/
├── main.py                        # Application entry point and DICOMViewerApp orchestrator
├── metadata/                      # Metadata feature controllers
│   └── metadata_controller.py     # Owns MetadataPanel, TagEditHistoryManager, undo/redo, privacy for metadata
├── roi/                           # ROI / measurement feature controllers
│   └── roi_measurement_controller.py  # Owns ROIManager, MeasurementTool, AnnotationManager, panels
├── core/                          # Core processing, loading, and coordination logic
│   ├── loading_progress_manager.py    # Animated loading dots, QProgressDialog, cancellation (used by FileOperationsHandler)
│   └── privacy_controller.py          # Privacy-mode propagation and overlay refresh (called from main on privacy toggle)
├── gui/                           # All Qt widgets, dialogs, and layout components
├── tools/                         # Interactive tools (ROI, measurement, annotation, crosshair)
└── utils/                         # Utilities (config, undo/redo, DICOM helpers, etc.)
    ├── config_manager.py          # Thin facade: inherits all config mixins; owns __init__, _load_config, save_config, get, set
    ├── debug_flags.py             # Central on/off switches for diagnostic print statements (DEBUG_LAYOUT, DEBUG_LOADING)
    └── config/                    # Feature-domain config mixin package
        ├── __init__.py
        ├── paths_config.py        # last_path, last_export_path, recent_files, normalize_path
        ├── display_config.py      # theme, smooth_image_when_zoomed, privacy_view, scroll_wheel_mode
        ├── overlay_config.py      # overlay mode/visibility/font/tags, get_all_modalities
        ├── layout_config.py       # multi_window_layout, view_slot_order
        ├── roi_config.py          # ROI font/line/default_visible_statistics
        ├── measurement_config.py  # measurement font/line
        ├── annotation_config.py   # text/arrow annotation appearance
        ├── cine_config.py         # cine speed/loop defaults
        ├── metadata_ui_config.py  # metadata panel column widths/order
        ├── tag_export_config.py   # tag export presets (CRUD + file I/O)
        ├── customizations_config.py  # bulk export/import of all visual settings
        └── app_config.py          # disclaimer_accepted
```

### Key controller responsibilities

| Controller | File | Owns / coordinates |
|---|---|---|
| `DICOMViewerApp` | `src/main.py` | Top-level orchestrator; delegates to all controllers below |
| `MetadataController` | `src/metadata/metadata_controller.py` | `MetadataPanel`, `TagEditHistoryManager`, undo/redo callbacks, privacy mode for metadata |
| `ROIMeasurementController` | `src/roi/roi_measurement_controller.py` | `ROIManager`, `MeasurementTool`, `AnnotationManager`, `ROIStatisticsPanel`, `ROIListPanel`; tracks active (focused-subwindow) managers via `update_focused_managers()` |
| `SubwindowLifecycleController` | `src/core/subwindow_lifecycle_controller.py` | Per-subwindow manager creation, focus changes, display updates |
| `PrivacyController` | `src/core/privacy_controller.py` | Privacy-mode propagation (metadata, overlay/crosshair managers, image viewers) and overlay refresh after privacy change; called from `DICOMViewerApp._on_privacy_view_toggled` |

### `DICOMViewerApp.__init__` initialization order

The constructor delegates to five helpers in strict order (each step depends on the previous):

1. `_init_core_managers()` – Qt app, DICOM managers, history, undo/redo, config, privacy state.
2. `_init_main_window_and_layout()` – `MainWindow`, `FileDialog`, `MultiWindowLayout`, theme.
3. `_init_controllers_and_tools()` – `MetadataController`, `ROIMeasurementController`.
4. `_init_view_widgets()` – navigators, cine, fusion, overlays, scroll-wheel mode.
5. `_post_init_subwindows_and_handlers()` – UI assembly, per-subwindow managers, handlers, signals, pan mode.

### Signal-wiring convention (`_connect_signals`)

All Qt signal connections for `DICOMViewerApp` are wired in a single call to `_connect_signals()` (invoked from `_post_init_subwindows_and_handlers`). That method delegates to a set of focused sub-methods, each responsible for one feature area:

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

**Rule**: signal connections live only in the `_connect_signals` family. No `connect()` calls should be scattered across other `_init_*` helpers. The call order within `_connect_signals` is intentional: layout and file signals are wired before dialog signals so that subwindow/focus state is ready when dialogs are first triggered.

## View and display options

- **Image Smoothing**: User-configurable option in the **View** menu and in the **image viewer context menu** (right-click on image). When enabled, the image uses smooth scaling when idle after zoom/pan; during zoom/pan it uses fast scaling for responsiveness. Default is **off** (no enhancement). Setting is persisted in config.
- **Show/Hide Left Pane and Right Pane**: Available in the **View** menu and in the **image viewer context menu** (right-click on image). Toggle hides the pane (width 0) or shows it at default 250 px; state is persisted with splitter sizes.
- **Show/Hide Series Navigator**: Available in the **View** menu, toolbar, key **N**, and the **image viewer context menu** (right-click on image). Toggles the series navigator bar at the bottom.
- **Multi-window layout**: 1x1 shows the **focused** view only. **1x2** shows the row (in the 2x2 grid) containing the focused window; **2x1** shows the column containing the focused window. Double-click on a pane (on image/background) expands it to 1x1; double-click again in 1x1 reverts to the last layout (or 2x2). **Swap** in the context menu (right-click → Swap) offers "Swap with Window 1/2/3/4" (grid positions); reorders view positions in 2x2 without moving data; swap is only active in 2x2.
