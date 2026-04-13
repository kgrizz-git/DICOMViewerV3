---
description: 
alwaysApply: true
---

# Agent instructions – DICOM Viewer V3

Guidance for AI agents and developers working in this repository.

## Virtual environment (venv)

**Always activate the project virtual environment before running tests or application code.**

The env folder may be named `venv`, `.venv`, `env`, or `virtualenv`. **`launch.bat`** picks the first that exists under the project root in that order; many setups use **`venv`** or **`.venv`** (tools like `uv` often create `.venv`).

On this machine/repo, a common layout is **`<project-root>\.venv`** (next to `requirements.txt` and `src\`). Example PowerShell activation from the repo root: `.\.venv\Scripts\Activate.ps1`.

If workspace search/index ignores hidden virtualenv folders, use these explicit paths directly:
- PowerShell activate: `C:\Users\kevingrizzard\Desktop\My-Codes-Windows-Local\DICOMViewerV3\.venv\Scripts\Activate.ps1`
- Python interpreter: `C:\Users\kevingrizzard\Desktop\My-Codes-Windows-Local\DICOMViewerV3\.venv\Scripts\python.exe`

- **Windows (Command Prompt)** — replace `<dir>` with your env folder, e.g. `venv` or `.venv`:
  - `<dir>\Scripts\activate`
- **Windows (PowerShell):** `.\<dir>\Scripts\Activate.ps1` (e.g. `.\.venv\Scripts\Activate.ps1`)
- **macOS / Linux:** `source <dir>/bin/activate` (e.g. `source .venv/bin/activate`)

From project root, after activation:

- Run the app: `python src/main.py`
- Run tests: `python tests/run_tests.py` or `python -m pytest tests/ -v` (see **`tests/README.md`** for layout and options).

If no venv exists, create one, for example `python -m venv venv` or `python -m venv .venv`, activate it, then `pip install -r requirements.txt`.

Optional for contributors: `pip install -r requirements-dev.txt` adds local Python security scanners (semgrep, detect-secrets). Install TruffleHog v3 separately via `powershell -ExecutionPolicy Bypass -File .\scripts\install-trufflehog-v3.ps1 -AddToUserPath` so local scans align with CI's TruffleHog v3 action/binary line.

## Other conventions

- See `.cursor/rules` and user rules.  Before major refactors only, backup files before changing. Do not proceed with edits until the backup is verified (e.g. file exists and has content) or the user has been asked.
- **Multi-agent orchestration:** Subagents (`/orchestrator`, `/planner`, `/coder`, …) are invoked via the **Task** tool. **Default `CHAIN_MODE` is `autonomous`:** the **primary agent** chains **`Task(orchestrator)`** after **each** non-orchestrator specialist until **complete** / **blocked** / **`needs_user`** / guard limits, unless **`plans/orchestration-state.md`** sets **`## Chain mode`** to **`step`** or the user asks for single-step mode—see **`.cursor/rules/orchestration-auto-chain.mdc`** and **`.claude/skills/team-orchestration-delegation/SKILL.md`**. After **`Task(orchestrator)`**, also chain **`NEXT_TASK_TOOL`** when not `none`. The orchestrator must end with **`NEXT_TASK_TOOL:`** / **`NEXT_TASK_TOOL_SECOND:`** (see **`.claude/agents/orchestrator.md`**); parallel **`SECOND`** only when the skill’s checklist passes. **Run packet:** **`dev-docs/orchestration/RUN_PACKET_TEMPLATE.md`**.
- **Long-running commands (agents / automation):** When type-checking large trees (`pyright` on all of `src/`), running the full test suite, or similar heavy work, use a **conservative timeout on the order of 10 minutes** (e.g. 600000 ms where the tool measures wait time) so runs are not cut off on slower machines. Shorter limits remain fine for single-file checks or quick smoke steps.
- Project layout: `src/` (application), `tests/` (tests; run instructions in **`tests/README.md`**), `user-docs/` (user guide hub **`USER_GUIDE.md`**), `dev-docs/` (plans, assessments).
- **Pylinac (ACR QA)**: `requirements.txt` pins an exact **`pylinac`** version; that pin is the only upstream release **verified** with the viewer’s ACR CT / MRI integration. When bumping the pin, re-verify and update `dev-docs/info/PYLINAC_INTEGRATION_OVERVIEW.md` (**Verified pylinac package version**). Default Stage‑1 runs use **`src/qa/pylinac_extent_subclasses.py`** (**`ACRCTForViewer`** / **`ACRMRILargeForViewer`**) so origin indices may be **0 … N−1** (stock pylinac is stricter); JSON **`pylinac_analysis_profile`** records **`relaxed_image_extent`**. Users may enable **Vanilla pylinac** in the ACR CT/MRI options dialogs (persisted in **`qa_pylinac_config`**) to run stock **`ACRCT`** / **`ACRMRILarge`** instead.
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
│   ├── study_index/                 # Local encrypted study DB (SQLCipher MVP): store, service, port, study_date_format (UI DA↔US), background threads
│   ├── loading_progress_manager.py    # Animated loading dots, QProgressDialog, cancellation (used by FileOperationsHandler)
│   ├── privacy_controller.py          # Privacy-mode propagation and overlay refresh (called from main on privacy toggle)
│   ├── export_manager.py              # Export orchestration (paths, progress, slice/selection export)
│   ├── export_rendering.py            # Pillow projection, photometric handling, overlay/ROI rasterization for export
│   ├── fusion_handler_io.py           # Pure DICOM spatial reads + NumPy fusion helpers (no Qt); used by fusion_handler (Phase 5A)
│   ├── mpr_geometry.py                # Pure MPR output-grid math, standard LPS planes, stack positions; used by mpr_builder (Phase 5C)
│   ├── projection_app_facade.py       # Intensity projection / MPR combine UI handlers; DICOMViewerApp delegates slots here (Phase 4a)
│   ├── qa_app_facade.py               # ACR CT/MRI pylinac QA flows, workers, compare dialog, QA JSON export; DICOMViewerApp delegates (Phase 4b)
│   ├── export_app_facade.py           # Focused-series paths, save-as prompt, export/ROI-stats/screenshot entrypoints; DICOMViewerApp delegates (Phase 4c)
│   ├── subwindow_image_viewer_sync.py # Propagate privacy, slice sync, smoothing, scale/direction markers to all pane ImageViewers (used by main.py)
│   ├── subwindow_manager_factory.py # build_managers_for_subwindow(app, idx, subwindow) — per-pane ROI/measurement/overlay/slice/fusion graph (used by main.py)
│   ├── cine_app_facade.py             # Cine player, frame slider, loop bounds; ``app_signal_wiring`` connects slots to this facade (post-assessment Phase 8)
│   ├── window_level_preset_handler.py # Context-menu W/L preset apply with raw/rescaled alignment (post-assessment Phase 7)
│   ├── main_app_key_event_filter.py   # Layout digit focus gating + key dispatch to ``KeyboardEventHandler`` (post-assessment Phase 9)
│   ├── slice_display_lut.py           # Window/level raw vs rescaled alignment helpers (used by SliceDisplayManager)
│   ├── slice_display_pixels.py        # Intensity projection → PIL pipeline (used by SliceDisplayManager)
│   ├── direction_labels.py            # Patient LPS direction strings from ImageOrientationPatient (viewer edge labels; tests in tests/test_direction_labels.py)
│   ├── dicom_parser.py                # Dataset metadata: get_all_tags (iterall + optional export catalog merge)
│   ├── tag_export_catalog.py          # Curated standard tags for Export DICOM Tags picker; synthetic_tag_export_tree_entry for preset-only rows missing from the file union
│   ├── tag_export_union.py            # union_tags_across_datasets (merged tag map); separate from catalog to avoid a dicom_parser ↔ catalog import cycle for static analysis
│   └── tag_export_writer.py           # Tag export file writers: Excel, CSV, UTF-8 tab-separated text (shared row builder)
├── gui/                           # All Qt widgets, dialogs, layout; e.g. overlay_items_factory, series_navigator_view (thumbnails), series_navigator_model (labels/instance entries), main_window_*_builder (menus/toolbar); **`dialogs/tag_export_union_worker.py`** — background tag-union for Export DICOM Tags ( **`DICOMViewerApp._schedule_tag_export_union_rebuild`** )
│   ├── metadata_table_model.py    # Metadata panel tree delegate + tag filter/group/value helpers (Phase 5D; `metadata_panel.py` wires UI)
│   └── dialogs/mri_compare_result_dialog.py  # ACR MRI compare-results table + JSON/PDF actions; `qa_app_facade` wires callbacks (Phase 5E)
├── tools/                         # Interactive tools (ROI, measurement, annotation, crosshair)
│   └── roi_persistence.py         # Clipboard-oriented ROI dict serialization (Phase 5B; copy/paste schema)
└── utils/                         # Utilities (config, undo/redo, DICOM helpers, etc.)
    ├── undo_redo_tag_commands.py  # `TagEditCommand` for DICOM tag edits; imported at end of `undo_redo.py` for re-export (Phase 5E)
    ├── config_manager.py          # Thin facade: inherits all config mixins; owns __init__, _load_config, save_config, get, set
    ├── doc_urls.py                # GitHub base URL for in-app user-docs links (Help → Documentation, Quick Start); edit USER_DOCS_GITHUB_PREFIX for forks
    ├── debug_flags.py             # Central on/off switches for diagnostic prints (e.g. DEBUG_LAYOUT, DEBUG_LOADING, DEBUG_NAV, DEBUG_YBR)
    └── config/                    # Feature-domain config mixin package
        ├── __init__.py
        ├── paths_config.py        # last_path, last_export_path, last_pylinac_output_path, recent_files, normalize_path
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
        ├── app_config.py          # disclaimer_accepted
        ├── qa_pylinac_config.py   # persisted pylinac QA options (e.g. MRI LC method/threshold/sanity)
        └── study_index_config.py  # local study index DB path, auto-add on open, browser column order
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

**Rule**: signal connections live only in the `_connect_signals` family (implemented in `core/app_signal_wiring.py` via `wire_all_signals`). No `connect()` calls should be scattered across other `_init_*` helpers. The call order within `_connect_signals` is intentional: layout and file signals are wired before dialog signals so that subwindow/focus state is ready when dialogs are first triggered. **Exception:** annotation **Copy** / **Paste** menu signals connect to `AnnotationPasteHandler.copy_annotations` / `paste_annotations` on the app (same wiring module, not slots on `DICOMViewerApp`).

## GitHub Actions (CI)

- Workflows live under `.github/workflows/`. Use current **major tags** for first-party actions (`actions/checkout@v6`, `actions/upload-artifact@v7`, `github/codeql-action/*@v4`) so Dependabot can propose updates. Pin **third-party** actions to release tags when reproducibility matters (e.g. `trufflesecurity/trufflehog@v3.x.x` plus matching `version:` for the scanner image).
- **Storage / billing**: Artifact and cache usage accrues in **GB-hours**; free plans include a small **artifact** allowance (see GitHub’s current billing docs). Large multi-OS **`upload-artifact`** outputs and long **`retention-days`** can exhaust quota quickly—see `dev-docs/info/GITHUB_ACTIONS_STORAGE_AND_BILLING.md`. The **Build Executables** workflow uploads **`dist/`** (and the Linux AppImage) only — **not** PyInstaller’s **`build/`** folder (debug analysis locally). **`actions-cache-prune.yml`** (weekly + manual) deletes **stale** Actions **caches** on non-protected refs while keeping **default branch**, **`develop`**, and optional extra refs—see the same doc. **macOS PySide6 submodule excludes** are **off** by default; set **`PYINSTALLER_MACOS_SLIM=1`** locally or enable the optional **workflow_dispatch** slim job — see **`dev-docs/info/BUILDING_EXECUTABLES.md`** / **`dev-docs/info/PYINSTALLER_BUNDLE_SIZE_AND_BASELINES.md`**. **`tests/test_pyinstaller_exclude_audit.py`** guards excluded module names against **`src/`** and **`tests/`** imports.
- `actions/upload-artifact` v6+ and related actions may require **self-hosted runners ≥ 2.327.1** (Node 24); GitHub-hosted `ubuntu-latest` satisfies this.
- If `.github/dependabot.yml` lists `labels:`, those labels must exist on the repo (e.g. `dependencies`, `github-actions`) or Dependabot will warn on PRs.

## View and display options

- **Image Smoothing**: User-configurable option in the **View** menu and in the **image viewer context menu** (right-click on image). When enabled, the image uses smooth scaling when idle after zoom/pan; during zoom/pan it uses fast scaling for responsiveness. Default is **off** (no enhancement). Setting is persisted in config.
- **Show/Hide Left Pane and Right Pane**: Available in the **View** menu and in the **image viewer context menu** (right-click on image). Toggle hides the pane (width 0) or shows it at default 250 px; state is persisted with splitter sizes.
- **Show/Hide Series Navigator**: Available in the **View** menu, toolbar, key **N**, and the **image viewer context menu** (right-click on image). Toggles the series navigator bar at the bottom.
- **Multi-window layout**: 1x1 shows the **focused** view only. **1x2** shows the row (in the 2x2 grid) containing the focused window; **2x1** shows the column containing the focused window. Double-click on a pane (on image/background) expands it to 1x1; double-click again in 1x1 reverts to the last layout (or 2x2). **Swap** in the context menu (right-click → Swap) offers "Swap with Window 1/2/3/4" (grid positions); reorders view positions in 2x2 without moving data; swap is only active in 2x2.
