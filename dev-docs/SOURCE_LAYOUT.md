# Source layout (`src/`)

**Last updated:** 2026-07-18  
**Purpose:** Detailed module tree, controller ownership, app bootstrap order, and Qt signal-wiring rules. Agents should read **[`ARCHITECTURE.md`](../ARCHITECTURE.md)** first for domains and dependency rules; use this file when you need file-level navigation.

---

## Module tree

```
src/
├── main.py                        # Application entry point and DICOMViewerApp orchestrator
├── metadata/                      # Metadata feature controllers
│   └── metadata_controller.py     # Owns MetadataPanel, TagEditHistoryManager, undo/redo, privacy for metadata
├── roi/                           # ROI / measurement feature controllers
│   └── roi_measurement_controller.py  # Owns ROIManager, MeasurementTool, AnnotationManager, panels
├── core/                          # Core processing, loading, and coordination logic
│   ├── actions/                     # Menu/dialog/view/customization actions: ``dialog_actions``, ``view_actions``, ``customization_actions``; ``dialog_action_handlers`` re-exports for façades/tests
│   ├── app_handler_bootstrap.py     # After subwindow managers exist: builds coordinators, ``FileOperationsHandler``, ``DialogCoordinator``, cine, keyboard, etc.; ``DICOMViewerApp._initialize_handlers`` delegates
│   ├── session_reset_controller.py  # Close-all / ROI clear / fusion reset / tag-union schedule / quit drain; ``main`` delegates ``_close_files``, ``_clear_data``, ``_on_app_about_to_quit``
│   ├── mpr_navigator_thumbnail.py   # MPR pixel-array helpers and series-navigator MPR thumbnail set/clear/floating (attached vs key ``-1`` detached); ``main`` keeps one-line slots for ``app_signal_wiring``
│   ├── layout_window_slot_controller.py  # Layout changed handlers, capture/restore, swap/expand 1×1, window-slot map refresh/popup; ``main`` delegates
│   ├── tag_export_union_host.py     # Tag-export union ``QThread`` worker, generation, merged map; ``tag_export_union_ready`` remains on ``DICOMViewerApp``
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
│   ├── cine_app_facade.py             # Cine player, frame slider, loop bounds; MPR-focused panes enable linear cine over ``n_slices``; ``app_signal_wiring`` connects slots to this facade (post-assessment Phase 8)
│   ├── main_app_key_event_filter.py   # Layout digit focus gating + key dispatch to ``KeyboardEventHandler`` (post-assessment Phase 9)
│   ├── slice_display_lut.py           # Window/level raw vs rescaled alignment helpers (used by SliceDisplayManager)
│   ├── slice_display_pixels.py        # Intensity projection → PIL pipeline (used by SliceDisplayManager)
│   ├── slice_window_level_resolver.py # Resolve effective W/L for a slice (dataset tags + user overrides)
│   ├── dicom_window_level.py          # DICOM window/level tag parsing and display-range math
│   ├── wl_preset_catalog.py           # Built-in and user W/L preset catalog (modality-aware labels)
│   ├── window_level_preset_handler.py # Context-menu W/L preset apply with raw/rescaled alignment (post-assessment Phase 7)
│   ├── slice_geometry.py              # Pure 3-D slice-plane/stack math (patient mm); shared by sync and location lines
│   ├── slice_sync_coordinator.py      # Linked-group anatomic slice sync across panes (off by default)
│   ├── slice_location_line_helper.py  # Pure geometry: plane intersections → 2-D line segments per target pane
│   ├── roi_export_service.py          # ROI/crosshair/measurement aggregation + TXT/CSV/XLSX writers (formula-safe cells)
│   ├── spreadsheet_safety.py          # Neutralize formula-like spreadsheet cell prefixes on export
│   ├── study_navigation_handlers.py   # Study/series navigation menu slots (delegated from main)
│   ├── direction_labels.py            # Patient LPS direction strings from ImageOrientationPatient (viewer edge labels; tests in tests/test_direction_labels.py)
│   ├── dicom_parser.py                # Dataset metadata: get_all_tags (iterall + optional export catalog merge)
│   ├── sr_sop_classes.py              # SR storage SOP class registry; ``is_structured_report_dataset``
│   ├── sr_document_tree.py            # Generic SR ``ContentSequence`` tree builder + JSON export helper
│   ├── sr_concept_identity.py         # SR coded-concept normalization (designator fold, LongCodeValue) for dose-event matching
│   ├── rdsr_dose_sr.py                # Radiation dose SR detection + CT summary walk; uses ``sr_concept_identity`` for concept codes
│   ├── rdsr_irradiation_events.py     # RDSR irradiation event rows (PS3.16 **113706** / **113819**); **DAP**/**Dose (RP)** + parallel **DAP units**/**Dose (RP) units** from ``MeasurementUnitsCodeSequence``; capped notes if units missing
│   ├── tag_export_catalog.py          # Curated standard tags for Export DICOM Tags picker; synthetic_tag_export_tree_entry for preset-only rows missing from the file union
│   ├── tag_export_union.py            # union_tags_across_datasets (merged tag map); separate from catalog to avoid a dicom_parser ↔ catalog import cycle for static analysis
│   └── tag_export_writer.py           # Tag export file writers: Excel, CSV, UTF-8 tab-separated text (shared row builder)
├── gui/                           # All Qt widgets, dialogs, layout; e.g. overlay_items_factory, series_navigator_view (thumbnails), series_navigator_model (labels/instance entries), main_window_*_builder (menus/toolbar); **`dialogs/tag_export_union_worker.py`** — tag-union merge thread (orchestrated by **`core/tag_export_union_host.py`** via **`DICOMViewerApp._schedule_tag_export_union_rebuild`** ); **`dialogs/structured_report_browser_dialog.py`** — modeless SR tree + dose events (optional **Hide empty columns**, on by default; CSV/XLSX still export all columns) + exports (**Tools → Structured Report…**)
│   ├── slice_location_line_manager.py   # Per-pane QGraphics line items for slice-location reference lines
│   ├── slice_location_line_coordinator.py  # App-level refresh across panes; reads ``SliceSyncConfigMixin`` visibility flags
│   ├── metadata_table_model.py    # Metadata panel tree delegate + tag filter/group/value helpers (Phase 5D; `metadata_panel.py` wires UI)
│   └── dialogs/
│       ├── slice_sync_dialog.py       # Manage linked sync groups (**View → Manage Sync Groups…**)
│       ├── export_roi_statistics_dialog.py  # **Tools → Export ROI Statistics** series picker + format options
│       └── mri_compare_result_dialog.py  # ACR MRI compare-results table + JSON/PDF actions; `qa_app_facade` wires callbacks (Phase 5E)
├── tools/                         # Interactive tools (ROI, measurement, annotation, crosshair)
│   └── roi_persistence.py         # Clipboard-oriented ROI dict serialization (Phase 5B; copy/paste schema)
└── utils/                         # Utilities (config, undo/redo, DICOM helpers, etc.)
    ├── undo_redo_tag_commands.py  # `TagEditCommand` for DICOM tag edits; imported at end of `undo_redo.py` for re-export (Phase 5E)
    ├── config_manager.py          # Thin facade: inherits all config mixins; owns __init__, _load_config, save_config, get, set
    ├── doc_urls.py                # GitHub base URL for in-app user-docs links (Help → Documentation, Quick Start); edit USER_DOCS_GITHUB_PREFIX for forks
    ├── debug_flags.py             # **Agent-relevant:** all DEBUG_* toggles for console tracing (default False); see AGENTS.md + HARNESS.md § Debugging
    └── config/                    # Feature-domain config mixin package
        ├── __init__.py
        ├── paths_config.py        # last_path, last_export_path, last_pylinac_output_path, recent_files, normalize_path
        ├── display_config.py      # theme, smooth_image_when_zoomed, privacy_view, scroll_wheel_mode
        ├── overlay_config.py      # overlay mode/visibility/font/tags + overlay_tags_detailed_extra (Detailed-only corner tags), get_all_modalities
        ├── layout_config.py       # multi_window_layout, view_slot_order
        ├── slice_sync_config.py   # slice_sync_enabled, linked groups, slice-location line visibility/width/mode
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

---

## Key controllers

| Controller | File | Owns / coordinates |
|---|---|---|
| `DICOMViewerApp` | `src/main.py` | Top-level orchestrator; delegates to all controllers below |
| `MetadataController` | `src/metadata/metadata_controller.py` | `MetadataPanel`, `TagEditHistoryManager`, undo/redo callbacks, privacy mode for metadata |
| `ROIMeasurementController` | `src/roi/roi_measurement_controller.py` | `ROIManager`, `MeasurementTool`, `AnnotationManager`, `ROIStatisticsPanel`, `ROIListPanel`; tracks active (focused-subwindow) managers via `update_focused_managers()` |
| `SubwindowLifecycleController` | `src/core/subwindow_lifecycle_controller.py` | Per-subwindow manager creation, focus changes, display updates |
| `PrivacyController` | `src/core/privacy_controller.py` | Privacy-mode propagation (metadata, overlay/crosshair managers, image viewers) and overlay refresh after privacy change; invoked from `core.actions.view_actions.on_privacy_view_toggled` via `DICOMViewerApp._on_privacy_view_toggled` |
| `SliceSyncCoordinator` | `src/core/slice_sync_coordinator.py` | Linked-group anatomic slice sync; geometry cache keyed by `(study_uid, series_uid)`; off by default |
| `SliceLocationLineCoordinator` | `src/gui/slice_location_line_coordinator.py` | Cross-pane slice-location reference lines; delegates segment math to `slice_location_line_helper` |

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
