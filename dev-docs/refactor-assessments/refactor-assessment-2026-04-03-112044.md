# Refactor Assessment - 2026-04-03 11:20:44

## Assessment Date
- **Date**: 2026-04-03
- **Time**: 11:20:44
- **Assessor**: Cursor Agent (automated pass against template v2.0)

## Scope and Method
- Assessed project-owned `*.py` files under `src/`, `tests/`, and `scripts/` (relative to repo root).
- **Excluded** paths/names matching backup rules: `backup` / `backups` folders, filenames containing `backup`, `_BAK`, or `.bak` (case-insensitive).
- **Threshold**: Template language-specific guideline for **Python: 600 lines** (base template checklist uses 750; Python row recommends 600). Files **≥ 600 lines** are listed below.
- **No application code was modified** during this assessment; only this markdown file was created.
- Line counts include comments and blank lines (`sum` of physical lines, UTF-8 with replacement on decode errors).

## Files Analyzed

### Summary Table (Python files ≥ 600 lines)

| File | Location | Line Count | Exceeds 600 (Py) | Exceeds 750 | Status |
|------|----------|------------|------------------|-------------|--------|
| main.py | src/main.py | 4556 | Yes | Yes | Analyzed |
| image_viewer.py | src/gui/image_viewer.py | 3428 | Yes | Yes | Analyzed |
| slice_display_manager.py | src/core/slice_display_manager.py | 1602 | Yes | Yes | Analyzed |
| main_window.py | src/gui/main_window.py | 1584 | Yes | Yes | Analyzed |
| export_manager.py | src/core/export_manager.py | 1517 | Yes | Yes | Analyzed |
| overlay_manager.py | src/gui/overlay_manager.py | 1290 | Yes | Yes | Analyzed |
| series_navigator.py | src/gui/series_navigator.py | 1272 | Yes | Yes | Analyzed |
| annotation_manager.py | src/tools/annotation_manager.py | 1217 | Yes | Yes | Analyzed |
| roi_manager.py | src/tools/roi_manager.py | 1190 | Yes | Yes | Analyzed |
| fusion_controls_widget.py | src/gui/fusion_controls_widget.py | 1183 | Yes | Yes | Analyzed |
| mpr_controller.py | src/core/mpr_controller.py | 1149 | Yes | Yes | Analyzed |
| subwindow_lifecycle_controller.py | src/core/subwindow_lifecycle_controller.py | 1145 | Yes | Yes | Analyzed |
| file_series_loading_coordinator.py | src/core/file_series_loading_coordinator.py | 1120 | Yes | Yes | Analyzed |
| undo_redo.py | src/utils/undo_redo.py | 1113 | Yes | Yes | Analyzed |
| pylinac_runner.py | src/qa/pylinac_runner.py | 1112 | Yes | Yes | Analyzed |
| view_state_manager.py | src/core/view_state_manager.py | 1105 | Yes | Yes | Analyzed |
| fusion_coordinator.py | src/gui/fusion_coordinator.py | 1065 | Yes | Yes | Analyzed |
| roi_coordinator.py | src/gui/roi_coordinator.py | 1032 | Yes | Yes | Analyzed |
| tag_export_dialog.py | src/gui/dialogs/tag_export_dialog.py | 1017 | Yes | Yes | Analyzed |
| fusion_handler.py | src/core/fusion_handler.py | 918 | Yes | Yes | Analyzed |
| measurement_items.py | src/tools/measurement_items.py | 855 | Yes | Yes | Analyzed |
| dicom_loader.py | src/core/dicom_loader.py | 808 | Yes | Yes | Analyzed |
| arrow_annotation_tool.py | src/tools/arrow_annotation_tool.py | 792 | Yes | Yes | Analyzed |
| metadata_panel.py | src/gui/metadata_panel.py | 765 | Yes | Yes | Analyzed |
| text_annotation_tool.py | src/tools/text_annotation_tool.py | 747 | Yes | No | Analyzed |
| image_resampler.py | src/core/image_resampler.py | 747 | Yes | No | Analyzed |
| annotation_options_dialog.py | src/gui/dialogs/annotation_options_dialog.py | 723 | Yes | No | Analyzed |
| tag_viewer_dialog.py | src/gui/dialogs/tag_viewer_dialog.py | 721 | Yes | No | Analyzed |
| dicom_organizer.py | src/core/dicom_organizer.py | 698 | Yes | No | Analyzed |
| annotation_paste_handler.py | src/core/annotation_paste_handler.py | 684 | Yes | No | Analyzed |
| export_dialog.py | src/gui/dialogs/export_dialog.py | 666 | Yes | No | Analyzed |
| multi_window_layout.py | src/gui/multi_window_layout.py | 653 | Yes | No | Analyzed |
| roi_export_service.py | src/core/roi_export_service.py | 631 | Yes | No | Analyzed |
| mpr_builder.py | src/core/mpr_builder.py | 628 | Yes | No | Analyzed |
| measurement_tool.py | src/tools/measurement_tool.py | 601 | Yes | No | Analyzed |

**Total**: 35 files ≥ 600 lines. No `tests/` or `scripts/` files met the threshold in this pass.

---

## Detailed Analysis

### File: `src/main.py`

**Location**: `src/main.py`  
**Line Count**: 4556  
**Exceeds Threshold**: Yes (600 and 750)

#### Code Structure Inventory
- **`DICOMViewerApp` (`QObject`)**: single-application orchestrator from roughly lines 144–4518 (~4374 lines of class body).
- **~217** instance methods at standard indent (large surface area: init stages, subwindow plumbing, file/series lifecycle, display, dialogs, fusion, QA, slice sync, projection, export helpers, signal handlers).
- **Module level**: `exception_hook`, `main()` (startup).

#### Logical Groupings
- **Staged initialization**: `_init_core_managers`, `_init_main_window_and_layout`, `_init_controllers_and_tools`, `_init_view_widgets`, `_post_init_subwindows_and_handlers`.
- **Per-subwindow construction**: `_build_managers_for_subwindow`, `_create_managers_for_subwindow`, `_initialize_subwindow_managers`, getters for dataset/slice/MPR state.
- **Focus and layout**: `_update_focused_subwindow_references`, layout swap/expand, `_connect_focused_subwindow_signals`, panel updates.
- **File/series lifecycle**: open/close paths, `_clear_data`, study/series close, fusion reset.
- **Display pipeline**: `_display_slice`, `_redisplay_*`, ROI/measurement display hooks, projection-related slots.
- **Metadata / undo-redo**: tag editing, undo/redo delegation.
- **Feature areas still concentrated here**: intensity projection UI reactions, QA preflight/worker wiring, many `_open_*` dialog entry points, slice sync and slice location line toggles, export path resolution.

#### Dependencies
- **Depends on**: Most of `core/`, `gui/`, `tools/`, `metadata/`, `roi/`, `qa/` modules (see imports in file header, lines 52–134).
- **Depended upon by**: Application entry (`main()`); **lazy/type imports** in `core/app_signal_wiring.py` and `core/dialog_action_handlers.py` (`from main import DICOMViewerApp`).

#### Refactoring Opportunities

##### Opportunity 1: Vertical slices by feature façade (QA, projection, export orchestration)

**Proposed Structure**:
- New thin modules (or expand existing coordinators), e.g. `core/qa_app_facade.py`, `core/projection_app_facade.py`, `core/export_app_facade.py`, holding methods currently on `DICOMViewerApp` that only need `app` references + Qt parent.
- **`main.py` retains**: init ordering, ownership of managers, and delegation one-liners.

**Migration Strategy**: Move one feature cluster at a time; keep `DICOMViewerApp` as the single owner of widgets/workers; pass `self` or narrow protocols into facades; run full test suite after each move.

**Benefits**: Shrinks `main.py`, makes feature ownership grep-friendly, reduces merge contention on the hottest file.

**Evaluation**:
- **Ease of Implementation**: 2/5 — Many method bodies touch shared state; careful boundary drawing required.
- **Safety**: 2/5 — Regression risk in signal order and focus handling; needs manual QA + tests.
- **Practicality**: 5/5 — Very high long-term payoff for a 4.5k-line orchestrator.
- **Recommendation**: 5/5 — Aligns with modular controller pattern already documented in `AGENTS.md`.
- **Overall Score**: **3.50/5**

**Priority**: High (incremental)

##### Opportunity 2: Further thin `main` after facades — document-only “god class” acceptance

**Proposed Structure**: If facades extract ~800–1500 lines, remaining `DICOMViewerApp` may still be large but cohesive as **composition root** only.

**Evaluation**:
- **Ease**: 4/5 (documentation + module stubs).
- **Safety**: 5/5.
- **Practicality**: 3/5.
- **Recommendation**: 4/5.
- **Overall Score**: **4.00/5**

**Priority**: Medium (supporting narrative for reviewers)

---

### File: `src/gui/image_viewer.py`

**Location**: `src/gui/image_viewer.py`  
**Line Count**: 3428  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- **`ImageViewer` (`QGraphicsView`)**: one class, **~64** methods at first indent — image display, interaction, zoom/pan, context menus, wheel handling, fusion/overlay hooks, and large event handlers.

#### Logical Groupings
- Viewport / scene setup and image pipeline (`set_image`, scaling, smoothing behavior).
- Mouse and keyboard interaction (press/move/release, wheel — often high line count).
- Context menu and window/level / navigation affordances.
- Bridge to external managers (ROI, crosshair, measurements) via signals or callbacks.

#### Dependencies
- **Depends on**: Qt graphics stack, DICOM/dataset helpers, multiple tool/manager types from constructor/callbacks.
- **Depended upon by**: Subwindow/container setup, coordinators, `main` wiring.

#### Refactoring Opportunities

##### Opportunity 1: Split interaction from rendering

**Proposed Structure**:
- `image_viewer_view.py` — scene, pixmap item, fit-to-window, resize.
- `image_viewer_input.py` or strategy objects — mouse/wheel/key routing.
- Optional: `image_viewer_context_menu.py` — menu build/actions.

**Benefits**: Easier unit testing of math (zoom constraints) vs. event routing; smaller diffs when changing UX.

**Evaluation**:
- **Ease**: 3/5
- **Safety**: 3/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: **3.50/5**

**Priority**: High

---

### File: `src/core/slice_display_manager.py`

**Line Count**: 1602 — **single primary class** `SliceDisplayManager` (slice display orchestration: LUT, window/level sync, update paths).

**Opportunity**: Extract **window/level** and **pixel pipeline** helpers into `slice_display_lut.py` / `slice_display_pixels.py`; keep scheduling and subwindow coupling in manager.

**Evaluation**: Ease 3, Safety 3, Practicality 4, Recommendation 4 → **Overall 3.50/5** — **Medium–High priority**

---

### File: `src/gui/main_window.py`

**Line Count**: 1584 — `MainWindow` + `_get_resource_path`; menus, toolbars, actions, layout chrome.

**Opportunity**: Move **menu/toolbar construction** into `main_window_menus.py` / `main_window_actions.py` (already partially split elsewhere — verify `main_window_layout_helper`); centralize action registration table.

**Evaluation**: Ease 4, Safety 4, Practicality 4, Recommendation 4 → **Overall 4.00/5** — **High priority (low risk)**

---

### File: `src/core/export_manager.py`

**Line Count**: 1517 — module helpers (`_get_bundled_font_path`, `_load_font_with_fallback`) + **`ExportManager`** with large `export_selected`, `export_slice`, projection builders, overlay ROI rendering.

**Opportunity**: Split **Pillow rasterization / projection** (`_create_projection_*`, `_render_overlays_and_rois`) into `export_rendering.py`; keep path selection and public API on `ExportManager`.

**Evaluation**: Ease 3, Safety 3, Practicality 5, Recommendation 5 → **Overall 4.00/5** — **High priority**

---

### File: `src/gui/overlay_manager.py`

**Line Count**: 1290 — `ViewportOverlayWidget` + **`OverlayManager`**; `create_overlay_items` and widget overlay paths are long.

**Opportunity**: Move **DICOM tag → text layout** mapping and **graphics item factory** to `overlay_items_factory.py`; keep `OverlayManager` as coordinator/policy.

**Evaluation**: Ease 3, Safety 4, Practicality 4, Recommendation 4 → **Overall 3.75/5** — **Medium–High priority**

---

### Cluster: Navigators, tools, and coordinators (≈ 1000–1300 lines each)

| File | Note |
|------|------|
| `series_navigator.py` | Split model vs. view; consider separate delegate/widget for row rendering. |
| `annotation_manager.py` / `roi_manager.py` | Large state machines; extract persistence/serialization vs. interaction. |
| `fusion_controls_widget.py` | Split panel sections (blending, colormap, registration hints) into sub-widgets. |
| `mpr_controller.py` / `file_series_loading_coordinator.py` / `subwindow_lifecycle_controller.py` | Already “controller” named — extract pure functions for dataset keys and transition tables. |
| `view_state_manager.py` | Snapshot/restore helpers may move to `view_state_serializers.py`. |
| `undo_redo.py` | If many command classes inline, move command types per domain file. |
| `fusion_coordinator.py` / `roi_coordinator.py` | Delegate repeated “focused subwindow” boilerplate to small helper. |
| `tag_export_dialog.py` | Wizard steps or tab content widgets in separate modules. |
| `fusion_handler.py` | Split I/O vs. policy vs. VTK/numpy pipeline if mixed. |
| `measurement_items.py` / `arrow_annotation_tool.py` / `text_annotation_tool.py` | Graphics item subclasses → group by `items/` subpackage. |
| `dicom_loader.py` / `image_resampler.py` / `dicom_organizer.py` | Keep loading vs. sorting vs. resampling boundaries strict. |
| `metadata_panel.py` | Table model + delegate in separate file. |
| `pylinac_runner.py` | Isolate vendor integration vs. UI callback glue (if any leaks in). |
| `annotation_paste_handler.py` / `export_dialog.py` / `multi_window_layout.py` / `roi_export_service.py` / `mpr_builder.py` / `measurement_tool.py` | Borderline 600–750; refactor when touching for features; extract pure helpers first. |

---

## Prioritized Recommendations

### High priority (overall ≥ 3.75 or outsized impact)
1. **`src/main.py`** — Incremental feature façades (QA, projection, export glue) and continued delegation to existing coordinators. **~3.5–4.0** depending on slice chosen.
2. **`src/gui/image_viewer.py`** — Split input vs. rendering vs. menus. **~3.5**
3. **`src/gui/main_window.py`** — Menu/toolbar/action modules. **~4.0**
4. **`src/core/export_manager.py`** — Rendering/projection submodule. **~4.0**

### Medium priority
5. **`slice_display_manager.py`**, **`overlay_manager.py`**, **`series_navigator.py`**, **`tag_export_dialog.py`**, **`fusion_controls_widget.py`** — Cohesion splits as above (**~3.5–3.75**).

### Lower priority (touch when editing)
- Files **600–750 lines**: prefer extract-on-change unless a module is actively growing.

---

## Files Appropriately Large (with caveats)

- **`main.py`**: May remain the **composition root** after façade extraction; document that “size is acceptable if methods are thin delegates.”
- **`undo_redo.py`** / **`pylinac_runner.py`**: Domain-heavy; acceptable if classes are already grouped with clear headers — still watch for new features landing inline.

---

## Observations and Patterns

- **Orchestration is centralized** in `main.py` (~4.5k lines) while **`AGENTS.md` already describes** extracted controllers and `app_signal_wiring` — further wins come from **feature-specific facades**, not another monolithic split.
- **Single large Qt classes** (`ImageViewer`, `SliceDisplayManager`, `ExportManager`) dominate line counts; splitting **event handlers** vs. **pure logic** yields the best testability.
- **Previous assessment** (`refactor-assessment-2026-03-21-184500.md`) referenced **`file_operations_handler.py`** at >750 lines; it **does not appear** in the current ≥600-line set — suggests recent shrink or path changes; good sign for incremental refactors.
- **No `tests/`** files ≥600 lines — test suite modules stay manageable.

---

## Assessment Checklist (this run)

### Preparation
- [x] Create timestamped copy → `dev-docs/refactor-assessments/refactor-assessment-2026-04-03-112044.md`
- [x] No code files modified
- [x] Scanned `src/` (`tests/`, `scripts/` included in sweep; none ≥600)
- [x] Excluded backup paths/names
- [x] Line counts recorded
- [x] List of files ≥600 lines

### Analysis
- [x] Summary table for all qualifying files
- [x] Deep dive on top structural hotspots (`main.py`, `image_viewer.py`, and next-tier modules)
- [x] Cluster notes for remaining large files
- [x] Scores and priorities for primary opportunities

### Documentation
- [x] Summary table
- [x] Prioritized recommendations
- [x] “Appropriately large” caveats
- [x] Cross-cutting observations

---

## Next Steps

- [ ] Review prioritized recommendations and pick **one vertical slice** (e.g. export rendering or main-window menus) for implementation phase.
- [ ] After refactors, re-run line-count scan and update a new timestamped assessment.
- [ ] If new recurring patterns appear (e.g. “focused subwindow boilerplate”), consider adding a criterion to the master template `dev-docs/templates-generalized/refactor-assessment-template.md` (template itself unchanged in this pass).
