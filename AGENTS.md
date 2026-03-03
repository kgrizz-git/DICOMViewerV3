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

## Source module structure (`src/`)

```
src/
├── main.py                        # Application entry point and DICOMViewerApp orchestrator
├── metadata/                      # Metadata feature controllers
│   └── metadata_controller.py     # Owns MetadataPanel, TagEditHistoryManager, undo/redo, privacy for metadata
├── roi/                           # ROI / measurement feature controllers
│   └── roi_measurement_controller.py  # Owns ROIManager, MeasurementTool, AnnotationManager, panels
├── core/                          # Core processing, loading, and coordination logic
├── gui/                           # All Qt widgets, dialogs, and layout components
├── tools/                         # Interactive tools (ROI, measurement, annotation, crosshair)
└── utils/                         # Utilities (config, undo/redo, DICOM helpers, etc.)
```

### Key controller responsibilities

| Controller | File | Owns / coordinates |
|---|---|---|
| `DICOMViewerApp` | `src/main.py` | Top-level orchestrator; delegates to all controllers below |
| `MetadataController` | `src/metadata/metadata_controller.py` | `MetadataPanel`, `TagEditHistoryManager`, undo/redo callbacks, privacy mode for metadata |
| `ROIMeasurementController` | `src/roi/roi_measurement_controller.py` | `ROIManager`, `MeasurementTool`, `AnnotationManager`, `ROIStatisticsPanel`, `ROIListPanel`; tracks active (focused-subwindow) managers via `update_focused_managers()` |
| `SubwindowLifecycleController` | `src/core/subwindow_lifecycle_controller.py` | Per-subwindow manager creation, focus changes, display updates |

### `DICOMViewerApp.__init__` initialization order

The constructor delegates to five helpers in strict order (each step depends on the previous):

1. `_init_core_managers()` – Qt app, DICOM managers, history, undo/redo, config, privacy state.
2. `_init_main_window_and_layout()` – `MainWindow`, `FileDialog`, `MultiWindowLayout`, theme.
3. `_init_controllers_and_tools()` – `MetadataController`, `ROIMeasurementController`.
4. `_init_view_widgets()` – navigators, cine, fusion, overlays, scroll-wheel mode.
5. `_post_init_subwindows_and_handlers()` – UI assembly, per-subwindow managers, handlers, signals, pan mode.

## View and display options

- **Image Smoothing**: User-configurable option in the **View** menu and in the **image viewer context menu** (right-click on image). When enabled, the image uses smooth scaling when idle after zoom/pan; during zoom/pan it uses fast scaling for responsiveness. Default is **off** (no enhancement). Setting is persisted in config.
- **Multi-window layout**: 1x1 shows the **focused** view only. **1x2** shows the row (in the 2x2 grid) containing the focused window; **2x1** shows the column containing the focused window. Double-click on a pane (on image/background) expands it to 1x1; double-click again in 1x1 reverts to the last layout (or 2x2). **Swap** in the context menu (right-click → Swap) offers "Swap with Window 1/2/3/4" (grid positions); reorders view positions in 2x2 without moving data; swap is only active in 2x2.
