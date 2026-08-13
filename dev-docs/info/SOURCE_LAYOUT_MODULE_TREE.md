# Detailed source module tree

**Last updated:** 2026-08-13
**Purpose:** On-demand file-level navigation. Read [`../SOURCE_LAYOUT.md`](../SOURCE_LAYOUT.md) first for bootstrap and signal-wiring rules, then read only the relevant domain below.

## Application shell

| Path | Responsibility |
|---|---|
| `src/main.py` | `DICOMViewerApp` Qt shell, signals, run/event filter |
| `src/main_app_initialization.py` | Core-manager through post-init orchestration |
| `src/main_app_subwindow_management.py` | Pane layout, subwindows, MPR navigation |
| `src/main_app_ui_and_files.py` | Menus, dialogs, file/series loading |
| `src/main_app_display_settings.py` | Overlays, projection, display settings |
| `src/main_app_tag_roi.py` | Tag edit/export and ROI workflows |

## Core processing and coordination

| Area | Key paths |
|---|---|
| Action/signal infrastructure | `core/actions/`, `core/app_handler_bootstrap.py`, `core/app_signal_wiring.py`, `core/session_reset_controller.py` |
| Loading/decoding | `dicom_loader_file.py`, `dicom_loader.py`, `dicom_pixel_array.py`, `decoder_capabilities.py`, `decoder_fixture_*.py`, `loading_progress_manager.py` |
| Display/window level | `slice_display_*.py`, `slice_window_level_resolver.py`, `dicom_window_level.py`, `wl_preset_catalog.py`, `window_level_preset_handler.py` |
| MPR/slice coordination | `mpr_controller.py`, `mpr_geometry.py`, `mpr_navigator_thumbnail.py`, `slice_geometry.py`, `slice_sync_coordinator.py`, `slice_location_line_helper.py` |
| Per-pane lifecycle | `subwindow_lifecycle_controller.py`, `subwindow_manager_factory.py`, `subwindow_image_viewer_sync.py`, `layout_window_slot_controller.py` |
| Export/tags | `export_manager.py`, `export_rendering.py`, `export_app_facade.py`, `tag_export_*.py`, `roi_export_*.py`, `spreadsheet_safety.py` |
| Privacy | `privacy_controller.py`; shared privacy helpers remain in `utils/privacy/` |
| Study index/SR | `study_index/`, `study_navigation_handlers.py`, `sr_*.py`, `rdsr_*.py` |
| QA/cine/projection | `qa_app_facade.py`, `cine_app_facade.py`, `projection_app_facade.py` |

## Qt interface and feature controllers

| Area | Key paths |
|---|---|
| Main window | `gui/main_window.py`, `main_window_*_builder.py`, `main_window_*_controller.py` |
| Loading/navigator | `file_series_*`, `series_navigator_*`, `slice_navigator.py` |
| Overlay/crosshair | `overlay_*`, `crosshair_*`, `slice_location_line_manager.py`, `slice_location_line_coordinator.py` |
| Dialogs | `gui/dialogs/`; inspect the named dialog before changing its action/controller path |
| Metadata and ROI controllers | `metadata/metadata_controller.py`, `roi/roi_measurement_controller.py` |
| Tools | `tools/` for ROI, measurement, annotation, crosshair, and clipboard persistence |

## QA and shared utilities

| Area | Key paths |
|---|---|
| Pylinac/medical physics | `src/qa/`; app entry points in `core/qa_app_facade.py` |
| Config persistence | `utils/config_manager.py`, `utils/config/` feature mixins |
| Diagnostics | `utils/debug_flags.py` (all flags default to `False`) |
| User-doc links | `utils/doc_urls.py` |
| Undo/redo | `utils/undo_redo.py`, `utils/undo_redo_tag_commands.py` |

## Search examples

```bash
rg --files src/core
rg "wire_all_signals|_connect_.*signals" src
rg "class .*Controller|def .*export" src/core src/gui
```

Use the focused verification map in [`../HARNESS.md`](../HARNESS.md#change-routing-and-focused-verification) after locating the relevant owner.
