# Detailed source module tree

**Last updated:** 2026-08-13
**Purpose:** On-demand file-level navigation. Paths in this document are repository-relative. Read [`../SOURCE_LAYOUT.md`](../SOURCE_LAYOUT.md) first for bootstrap and signal-wiring rules, then read only the relevant domain below.

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
| Action/signal infrastructure | `src/core/actions/`, `src/core/app_handler_bootstrap.py`, `src/core/app_signal_wiring.py`, `src/core/session_reset_controller.py` |
| Loading/decoding | `src/core/dicom_loader_file.py`, `src/core/dicom_loader.py`, `src/core/dicom_pixel_array.py`, `src/core/decoder_capabilities.py`, `src/core/decoder_fixture_*.py`, `src/core/loading_progress_manager.py` |
| Display/window level | `src/core/slice_display_*.py`, `src/core/slice_window_level_resolver.py`, `src/core/dicom_window_level.py`, `src/core/wl_preset_catalog.py`, `src/core/window_level_preset_handler.py` |
| MPR/slice coordination | `src/core/mpr_controller.py`, `src/core/mpr_geometry.py`, `src/core/mpr_navigator_thumbnail.py`, `src/core/slice_geometry.py`, `src/core/slice_sync_coordinator.py`, `src/core/slice_location_line_helper.py` |
| Per-pane lifecycle | `src/core/subwindow_lifecycle_controller.py`, `src/core/subwindow_manager_factory.py`, `src/core/subwindow_image_viewer_sync.py`, `src/core/layout_window_slot_controller.py` |
| Export/tags | `src/core/export_manager.py`, `src/core/export_rendering.py`, `src/core/export_app_facade.py`, `src/core/tag_export_*.py`, `src/core/roi_export_*.py`, `src/core/spreadsheet_safety.py` |
| Privacy | `src/core/privacy_controller.py`; shared privacy helpers remain in `src/utils/privacy/` |
| Study index/SR | `src/core/study_index/`, `src/core/study_navigation_handlers.py`, `src/core/sr_*.py`, `src/core/rdsr_*.py` |
| QA/cine/projection | `src/core/qa_app_facade.py`, `src/core/cine_app_facade.py`, `src/core/projection_app_facade.py` |

## Qt interface and feature controllers

| Area | Key paths |
|---|---|
| Main window | `src/gui/main_window.py`, `src/gui/main_window_*_builder.py`, `src/gui/main_window_*_controller.py` |
| Loading/navigator | `src/gui/file_series_*`, `src/gui/series_navigator_*`, `src/gui/slice_navigator.py` |
| Overlay/crosshair | `src/gui/overlay_*`, `src/gui/crosshair_*`, `src/gui/slice_location_line_manager.py`, `src/gui/slice_location_line_coordinator.py` |
| Dialogs | `src/gui/dialogs/`; inspect the named dialog before changing its action/controller path |
| Metadata and ROI controllers | `src/metadata/metadata_controller.py`, `src/roi/roi_measurement_controller.py` |
| Tools | `src/tools/` for ROI, measurement, annotation, crosshair, and clipboard persistence |

## QA and shared utilities

| Area | Key paths |
|---|---|
| Pylinac/medical physics | `src/qa/`; app entry points in `src/core/qa_app_facade.py` |
| Config persistence | `src/utils/config_manager.py`, `src/utils/config/` feature mixins |
| Diagnostics | `src/utils/debug_flags.py` (all flags default to `False`) |
| User-doc links | `src/utils/doc_urls.py` |
| Undo/redo | `src/utils/undo_redo.py`, `src/utils/undo_redo_tag_commands.py` |

## Search examples

```bash
rg --files src/core
rg "wire_all_signals|_connect_.*signals" src
rg "class .*Controller|def .*export" src/core src/gui
```

Use the focused verification map in [`../HARNESS.md`](../HARNESS.md#change-routing-and-focused-verification) after locating the relevant owner.
