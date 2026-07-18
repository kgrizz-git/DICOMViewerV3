# Architecture — DICOM Viewer V3

**Last updated:** 2026-07-18  
**Audience:** Engineers and AI agents. This is the top-level map; file-level detail lives in **[`dev-docs/SOURCE_LAYOUT.md`](dev-docs/SOURCE_LAYOUT.md)**.

---

## Product shape

Desktop **PySide6** DICOM viewer: multi-pane layouts, series navigator, MPR, fusion, ROI/measurement/annotation tools, structured reports, local encrypted study index, pylinac QA, and export pipelines. Entry point: **`src/main.py`** (`DICOMViewerApp`).

---

## Domains and packages

| Domain | Primary location | Responsibility |
|--------|------------------|----------------|
| **App shell** | `src/main.py`, `src/core/app_handler_bootstrap.py`, `src/core/app_signal_wiring.py` | Lifecycle, handler wiring, global signals |
| **GUI / chrome** | `src/gui/` | Main window, menus, toolbar, dialogs, themes (`DESIGN.md`) |
| **View / display** | `src/core/slice_display_*.py`, `src/gui/image_viewer*.py`, `src/core/subwindow_*` | Pixels, W/L, overlays, multi-window layout |
| **Window / level** | `dicom_window_level.py`, `slice_display_lut.py`, `wl_preset_catalog.py`, `window_level_preset_handler.py` | Raw vs rescaled W/L alignment, preset catalog, context-menu apply |
| **Slice sync / reference lines** | `slice_geometry.py`, `slice_sync_coordinator.py`, `slice_location_line_*` | Anatomic linked-pane sync; cross-view slice-location reference lines |
| **Loading / organize** | `src/core/loading_*`, DICOM organizer, `FileOperationsHandler` | Open folder/files, navigator population |
| **MPR** | `src/core/mpr_*.py`, `mpr_controller.py`, `mpr_geometry.py` | Volume build, reslice, detached navigator thumbnail |
| **Fusion** | `src/core/fusion_*`, `fusion_handler_io.py` | 2D/3D registration display |
| **ROI / tools** | `src/roi/`, `src/tools/`, `src/gui/roi_*` | ROIs, measurements, annotations, crosshair |
| **Metadata / tags** | `src/metadata/`, `dicom_parser.py`, tag export union/catalog | Panel, tag viewer, export presets |
| **Structured report** | `src/core/sr_*.py`, `rdsr_*.py`, `gui/dialogs/structured_report_*` | SR detection, dose events, browser |
| **Study index** | `src/core/study_index/` | SQLCipher + FTS5 local index |
| **QA (pylinac)** | `src/qa/`, `qa_app_facade.py` | ACR CT/MRI workflows |
| **Export / cine** | `export_*`, `cine_*`, `roi_export_service.py`, `spreadsheet_safety.py` | Static images, video, MPR DICOM save, ROI statistics export (TXT/CSV/XLSX) |
| **Config / utils** | `src/utils/config/`, `config_manager.py` | Persisted preferences by feature mixin |

---

## Dependency rules (enforced by convention)

Agents should respect these edges when adding imports or new modules:

```
utils/          →  (stdlib, third-party only; no gui/, no main)
core/           →  utils/, other core/; NOT gui/ (keep Qt out of pure modules)
gui/            →  core/, utils/, roi/, metadata/, tools/
roi/, metadata/ →  core/, utils/, gui/ (widgets), tools/
main.py         →  all domains; thin delegation preferred (facades)
```

| Rule | Rationale |
|------|-----------|
| **No `gui` → `main` imports** | Avoid circular app shell |
| **Pure I/O in `*_io.py` / `*_geometry.py`** | Testable without Qt (fusion, MPR math) |
| **Facades for menu slots** | `*_app_facade.py` keeps `main.py` small |
| **Signal wiring only in `app_signal_wiring.py`** | Single place to audit connections |
| **Config via `ConfigManager` mixins** | One persistence path per feature domain |

Custom structural linting has an incremental guard: **`scripts/check_architecture_boundaries.py`** blocks new high-risk import edges while allowing the current legacy baseline in **`dev-docs/architecture_boundary_baseline.txt`**. Remove baseline entries as modules are refactored toward this map.

---

## Where to change what

| Task | Start here |
|------|------------|
| New menu action / shortcut | `src/core/actions/`, `src/gui/main_window_menu_builder.py`, then `app_signal_wiring.py` |
| File open / folder load | `FileOperationsHandler`, loading pipeline, `DICOMOrganizer` |
| Navigator / thumbnails | `src/gui/series_navigator_*` |
| Overlay text / Spacebar cycle | `overlay_config`, `KeyboardEventHandler`, `OverlayManager` |
| MPR behavior | `src/core/mpr_controller.py`, `mpr_navigator_thumbnail.py` |
| Slice sync / linked groups | `slice_sync_coordinator.py`, `utils/config/slice_sync_config.py`, `gui/dialogs/slice_sync_dialog.py` |
| Slice location reference lines | `slice_location_line_helper.py`, `gui/slice_location_line_coordinator.py`, `gui/slice_location_line_manager.py` |
| ROI statistics export | `roi_export_service.py`, `gui/dialogs/export_roi_statistics_dialog.py` |
| Window/level presets | `wl_preset_catalog.py`, `window_level_preset_handler.py`, `dicom_window_level.py` |
| Privacy / PHI display | `privacy_controller.py`, `view_actions.on_privacy_view_toggled` |
| Study index search | `src/core/study_index/`, `study_index_search_dialog.py` |
| SR / RDSR | `rdsr_dose_sr.py`, `structured_report_browser_dialog.py` |
| Pylinac QA | `qa_app_facade.py`, `src/qa/` |
| User-visible defaults | `src/utils/config/*.py`, `config_manager.default_config` |
| Version / release | `src/version.py`, `CHANGELOG.md`, `dev-docs/RELEASING.md` |

---

## Repository knowledge map (progressive disclosure)

| Need | Document |
|------|----------|
| Agent quick ops (venv, test, CI) | [`AGENTS.md`](AGENTS.md) |
| Harness tooling & smoke | [`dev-docs/HARNESS.md`](dev-docs/HARNESS.md) |
| Module tree & signal wiring | [`dev-docs/SOURCE_LAYOUT.md`](dev-docs/SOURCE_LAYOUT.md) |
| Backlog | [`dev-docs/TO_DO.md`](dev-docs/TO_DO.md) |
| Implementation plans | [`dev-docs/plans/`](dev-docs/plans/) |
| Design / UX tokens | [`DESIGN.md`](DESIGN.md) |
| Human contributor workflow | [`dev-docs/CONTRIBUTING.md`](dev-docs/CONTRIBUTING.md) |
| Developer doc index | [`dev-docs/README.md`](dev-docs/README.md) |
| End-user docs | [`user-docs/USER_GUIDE.md`](user-docs/USER_GUIDE.md) |

---

## Quality and verification

| Gate | Command / location |
|------|-------------------|
| Unit tests | `python -m pytest tests/ -v` (activate `.venv` first) |
| User-docs links | `python scripts/check_user_docs_links.py` |
| Repo harness | `python scripts/check_repo_harness.py` |
| Architecture boundaries | `python scripts/check_architecture_boundaries.py` |
| Agent smoke (imports + fixture) | `python scripts/agent_smoke_harness.py` |
| Type check | `pyright src/` (see `dev-docs/TO_DO.md` maintenance notes) |
| Security (local/CI) | Semgrep, Grype workflows; see `CONTRIBUTING.md` |
