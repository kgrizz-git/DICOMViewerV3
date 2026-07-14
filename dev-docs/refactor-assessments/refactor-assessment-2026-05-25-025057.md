# Refactor Assessment - 2026-05-25 02:50:57

## Assessment Date
- **Date**: 2026-05-25
- **Time**: 02:50:57
- **Assessor**: Auto (AI agent)

## Scope

Full **top-10-by-line-count** assessment per [`refactor-assessment-template.md`](../templates-generalized/refactor-assessment-template.md). Analyzed only the ten largest non-backup Python files under `src/`, `scripts/`, and `tests/`. **No code changes** were made during this assessment.

**Python threshold used**: 600 lines (template guideline for Python).

## Files Analyzed

### Summary Table

| File | Location | Line Count | Exceeds Python Threshold (600) | Status |
|------|----------|------------|----------------------------------|--------|
| `main.py` | `src/main.py` | 3024 | Yes | Analyzed |
| `main_window.py` | `src/gui/main_window.py` | 1698 | Yes | Analyzed |
| `mpr_controller.py` | `src/core/mpr_controller.py` | 1693 | Yes | Analyzed |
| `slice_display_manager.py` | `src/core/slice_display_manager.py` | 1614 | Yes | Analyzed |
| `roi_manager.py` | `src/tools/roi_manager.py` | 1604 | Yes | Analyzed |
| `subwindow_lifecycle_controller.py` | `src/core/subwindow_lifecycle_controller.py` | 1552 | Yes | Analyzed |
| `image_viewer_view.py` | `src/gui/image_viewer_view.py` | 1399 | Yes | Analyzed |
| `overlay_manager.py` | `src/gui/overlay_manager.py` | 1257 | Yes | Analyzed |
| `pylinac_runner.py` | `src/qa/pylinac_runner.py` | 1247 | Yes | Analyzed |
| `view_state_manager.py` | `src/core/view_state_manager.py` | 1236 | Yes | Analyzed |

**Note**: 34 additional Python files in `src/` also exceed 600 lines; they are out of scope for this run.

---

## Detailed Analysis

### File: `main.py`

**Location**: `src/main.py`  
**Line Count**: 3024 (was 3617 in assessment 2026-04-20)  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- `class DICOMViewerApp(QObject)` (~line 171): **~231 methods**, single composition root
- Module helpers: `exception_hook`, `main`
- **88** import lines; heavy delegation to facades, controllers, and `core/actions/` (`dialog_actions`, `view_actions`, `customization_actions`)

#### Logical Groupings
- App bootstrap and `_init_*` pipeline
- Subwindow/layout lifecycle (partially in `layout_window_slot_controller`, `subwindow_lifecycle_controller`)
- File/study/series lifecycle and session reset
- Feature verticals: MPR, cine, fusion, overlays, ROI/measurements, QA, export, slice sync
- Thin `_on_*` / `_open_*` adapters (many now delegate to action modules)

#### Dependencies
- **Depends on**: PySide6, most `core/*` controllers/facades, `gui/*`, `tools/*`, `qa/*`, `core/app_signal_wiring.py`, `core/app_handler_bootstrap.py`
- **Depended upon by**: `tests/test_main_signals_view.py`, `tests/test_mpr_overlay_and_rescale.py` (import `main` module), startup entry point

#### Code Organization
- **Progress since 2026-04-20**: `src/core/actions/` extraction reduced file size ~593 lines; `app_signal_wiring`, session reset, and layout controllers already split
- **Remaining issues**: `DICOMViewerApp` still owns ~231 methods; high coupling surface; many handlers remain as one-liner wrappers

#### Refactoring Opportunities

##### Opportunity 1: Extract remaining signal/slot clusters into feature handler modules

**Proposed Structure**:
- New modules under `src/core/handlers/` (or extend `core/actions/`):
  - `fusion_handlers.py`, `slice_sync_handlers.py`, `study_navigation_handlers.py`
- `wire_all_signals` binds to handler callables; `DICOMViewerApp` keeps only state accessors

**Migration Strategy**: Move highest-cohesion `_on_*` groups in batches; keep method names on app as wrappers until wiring updated; regression via `tests/test_main_signals_view.py`.

**Benefits**: Estimated 400–800 line reduction; clearer ownership per feature stream.

**Evaluation**:
- **Ease**: 4/5 — pattern established by actions extraction
- **Safety**: 4/5 — wrapper-first migration
- **Practicality**: 5/5
- **Recommendation**: 5/5
- **Overall Score**: 4.50/5

**Priority**: High

##### Opportunity 2: `SubwindowStateService` for lookup/query helpers

**Proposed Structure**: `src/core/subwindow_state_service.py` — typed API for dataset, slice index, series UID, manager lookup per subwindow index.

**Evaluation**: Ease 3/5, Safety 4/5, Practicality 4/5, Recommendation 4/5 — **Overall 3.75/5**

**Priority**: Medium

##### Opportunity 3: Continue façade extraction (`overlay_app_facade`, `study_lifecycle_app_facade`)

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 5/5, Recommendation 4/5 — **Overall 3.75/5**

**Priority**: Medium

---

### File: `main_window.py`

**Location**: `src/gui/main_window.py`  
**Line Count**: 1698  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- `MainWindow(QMainWindow)`: **~68 methods**
- Helpers: `_get_resource_path`
- Menu/toolbar already delegated to `main_window_menu_builder.py`, `main_window_toolbar_builder.py`, theme to `main_window_theme.py`

#### Logical Groupings
- Widget construction (`_create_central_widget`, status bar, splitter)
- View/menu actions (privacy, smoothing, scale markers, mouse mode, font controls)
- About/disclaimer UI (`_show_about`, `_show_disclaimer`) — **125 lines** in `_show_about` alone
- Toast overlay (`show_toast_message` — **78 lines**)
- Recent-files menu, drag/drop, fullscreen chrome, layout mode, series navigator embedding

#### Dependencies
- **Depends on**: `ConfigManager`, menu/toolbar builders, `version`
- **Depended upon by**: `main.py`, `file_operations_handler.py`, `dialog_coordinator.py`, `view_state_manager.py`, `roi_coordinator.py`, `mouse_mode_handler.py`; inline import from `slice_display_manager.py` (TYPE_CHECKING/runtime guard pattern)

#### Refactoring Opportunities

##### Opportunity 1: Extract About/Disclaimer dialog builder

**Proposed Structure**: `src/gui/dialogs/about_dialog.py` — `show_about_dialog(parent, config) -> None`

**Benefits**: ~120 line reduction; isolates HTML/resource strings.

**Evaluation**: Ease 5/5, Safety 5/5, Practicality 4/5, Recommendation 4/5 — **Overall 4.50/5**

**Priority**: High

##### Opportunity 2: Extract toast overlay widget

**Proposed Structure**: `src/gui/toast_overlay.py` — reusable toast with fade/position logic; `MainWindow.show_toast_message` delegates.

**Evaluation**: Ease 4/5, Safety 4/5, Practicality 4/5, Recommendation 4/5 — **Overall 4.00/5**

**Priority**: High

##### Opportunity 3: Move view-toggle handlers to `main_window_view_actions.py`

**Proposed Structure**: Privacy/smoothing/scale/direction/slice-slider toggles as functions taking `MainWindow` protocol or callback bundle.

**Evaluation**: Ease 4/5, Safety 4/5, Practicality 3/5, Recommendation 3/5 — **Overall 3.50/5**

**Priority**: Medium

---

### File: `mpr_controller.py`

**Location**: `src/core/mpr_controller.py`  
**Line Count**: 1693  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Module helpers: `apply_mpr_stack_combine`, `seed_mpr_combine_state`, `_mpr_log`
- `MprController(QObject)`: **~30 methods**
- Largest methods: `_on_mpr_requested` (~200 lines), `display_mpr_slice` (~197), `_tear_down_mpr_at_subwindow` (~145), `_activate_mpr` (~122)

#### Logical Groupings
- MPR open/save dialog flows
- Worker lifecycle and cache
- Detach/relocate/floating MPR
- Slice display (`display_mpr_slice`) and W/L for MPR arrays
- Combine-stack state (shared helpers used by `mpr_navigator_thumbnail.py`)

#### Dependencies
- **Depends on**: app reference, MPR workers, image viewers, overlay builders, numpy/PIL paths
- **Depended upon by**: `main.py`, `mpr_navigator_thumbnail.py` (imports `apply_mpr_stack_combine`)

#### Refactoring Opportunities

##### Opportunity 1: Split MPR display pipeline from lifecycle controller

**Proposed Structure**:
- `src/core/mpr_display_pipeline.py` — `display_mpr_slice`, `_array_to_pil`, W/L helpers
- `MprController` orchestrates open/close/detach only

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 5/5, Recommendation 4/5 — **Overall 3.75/5**

**Priority**: Medium–High

##### Opportunity 2: Extract `_on_mpr_requested` / `_activate_mpr` into `mpr_activation.py`

**Benefits**: Shrinks controller; easier to test activation preconditions.

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 4/5, Recommendation 4/5 — **Overall 3.50/5**

**Priority**: Medium

##### Opportunity 3: Dedicated `mpr_teardown.py` for `_tear_down_mpr_at_subwindow`

**Evaluation**: Ease 4/5, Safety 3/5, Practicality 3/5, Recommendation 3/5 — **Overall 3.25/5**

**Priority**: Low–Medium

---

### File: `slice_display_manager.py`

**Location**: `src/core/slice_display_manager.py`  
**Line Count**: 1614 (was 1559 in 2026-04-20)  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Helpers: `_make_no_pixel_placeholder_pil`, `_overlay_metadata_dataset_for_slice`
- `SliceDisplayManager`: **27 methods**
- **Pipeline already staged** (implemented since 2026-04-20 plan):
  - `_resolve_window_level_for_series_transition` — **~301 lines** (largest remaining block)
  - `_render_base_image_pipeline` (~142)
  - `_sync_controls_and_metadata` (~120)
  - `_render_scene_overlays_annotations` (~127)
  - `display_slice` orchestrator (~138)

#### Dependencies
- **Depends on**: DICOM processor/parser/organizer, `ImageViewer`, W/L controls, `ROIManager`, `MeasurementTool`, `AnnotationManager`, `OverlayManager`
- **Depended upon by**: `subwindow_manager_factory.py`, app via subwindow managers

#### Refactoring Opportunities

##### Opportunity 1: Decompose `_resolve_window_level_for_series_transition` into sub-stages

**Proposed Structure**:
- `src/core/slice_window_level_resolver.py` with pure-ish steps: series transition detection, preset selection, rescale sync, user-W/L restore

**Benefits**: Addresses the main remaining complexity blob; improves testability of W/L edge cases.

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 5/5, Recommendation 5/5 — **Overall 4.00/5**

**Priority**: High

##### Opportunity 2: Extract overlay/annotation scene collaborators

**Proposed Structure**: `slice_overlay_renderer.py`, `slice_annotation_renderer.py` (as in 2026-04-20 assessment)

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 4/5, Recommendation 4/5 — **Overall 3.50/5**

**Priority**: Medium

##### Opportunity 3: `SliceDisplayContext` dataclass

**Evaluation**: Ease 3/5, Safety 4/5, Practicality 4/5, Recommendation 4/5 — **Overall 3.75/5**

**Priority**: Medium

---

### File: `roi_manager.py`

**Location**: `src/tools/roi_manager.py`  
**Line Count**: 1604  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- **6 classes** in one file:
  - `ROIGraphicsEllipseItem`, `ROIGraphicsRectItem` (~130 lines each)
  - `compute_resized_scene_rect_from_handle`, `apply_roi_scene_bounding_rect`, `roi_scene_bounding_rect`
  - `ROIResizeHandleItem`, `DraggableStatisticsOverlay`
  - `ROIItem` (~240 lines)
  - `ROIManager` (~940 lines from line 663)
- Largest `ROIManager` methods: `create_statistics_overlay` (~194), `calculate_statistics` (~127)

#### Dependencies
- **Depends on**: PySide6 graphics, numpy, `ConfigManager`
- **Depended upon by**: `subwindow_manager_factory`, `roi_coordinator`, `keyboard_event_handler`, `image_viewer_input`, `undo_redo`, `roi_list_panel`, `roi_measurement_controller`

#### Refactoring Opportunities

##### Opportunity 1: Split graphics primitives into `roi_graphics_items.py`

**Proposed Structure**: Move ellipse/rect items, resize handle, drag overlay, and scene-rect helpers.

**Benefits**: ~400 line reduction in `roi_manager.py`; aligns with `image_viewer` mixin split pattern.

**Evaluation**: Ease 4/5, Safety 4/5, Practicality 5/5, Recommendation 5/5 — **Overall 4.50/5**

**Priority**: High

##### Opportunity 2: Extract statistics engine to `roi_statistics.py`

**Proposed Structure**: `calculate_statistics`, `create_statistics_overlay`, overlay removal helpers.

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 4/5, Recommendation 4/5 — **Overall 3.50/5**

**Priority**: Medium

##### Opportunity 3: Keep `ROIItem` + `ROIManager` as core (~900 lines) until further domain split

**Justification**: Manager coordinates scene, undo, and panels — splitting further needs clear boundary with `roi_measurement_controller`.

**Evaluation**: Ease 2/5, Safety 2/5, Practicality 3/5, Recommendation 2/5 — **Overall 2.25/5**

**Priority**: Low (defer)

---

### File: `subwindow_lifecycle_controller.py`

**Location**: `src/core/subwindow_lifecycle_controller.py`  
**Line Count**: 1552  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- `SubwindowLifecycleController`: **37 methods**
- Signal wiring dominates file size:
  - `connect_subwindow_signals` (~245 lines)
  - `connect_focused_subwindow_signals` (~231 lines)
  - `disconnect_focused_subwindow_signals` (~176 lines)
- Focus/panel updates: `update_focused_subwindow_references` (~101), `update_right_panel_for_focused_subwindow` (~84)

#### Dependencies
- **Depends on**: app, per-subwindow managers, Qt signals
- **Depended upon by**: `main.py` (primary orchestration)

#### Refactoring Opportunities

##### Opportunity 1: Move signal wiring tables to `subwindow_signal_wiring.py`

**Proposed Structure**: Declarative connect/disconnect functions per signal group; controller calls wiring module.

**Benefits**: ~650 lines moved; wiring becomes data-driven and grep-friendly.

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 5/5, Recommendation 5/5 — **Overall 4.00/5**

**Priority**: High

##### Opportunity 2: Extract panel sync helpers (`focused_panel_sync.py`)

**Evaluation**: Ease 4/5, Safety 4/5, Practicality 4/5, Recommendation 4/5 — **Overall 4.00/5**

**Priority**: High

##### Opportunity 3: Typed subwindow accessor object (overlap with `SubwindowStateService` in `main.py`)

**Evaluation**: Ease 3/5, Safety 4/5, Practicality 4/5, Recommendation 3/5 — **Overall 3.50/5**

**Priority**: Medium

---

### File: `image_viewer_view.py`

**Location**: `src/gui/image_viewer_view.py`  
**Line Count**: 1399  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- `ImageViewerViewMixin`: **47 methods** (mixed into `ImageViewer` via multiple inheritance)
- Largest: `set_image` (~231 lines), `_get_pixel_value_at_coords` (~135), `_draw_scale_markers` (~86), `_draw_direction_labels` (~66)

#### Dependencies
- **Depends on**: PIL, Qt graphics, smoothing config, dataset metadata for overlays on viewport
- **Depended upon by**: `gui/image_viewer.py` (mixin), tests referencing viewer behavior

#### Refactoring Opportunities

##### Opportunity 1: Split viewport decoration from image compositing

**Proposed Structure**:
- `image_viewer_viewport_decorations.py` — scale markers, direction labels, `drawForeground`
- `image_viewer_image_pipeline.py` — `set_image`, inversion, smoothing application

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 5/5, Recommendation 4/5 — **Overall 3.75/5**

**Priority**: Medium–High

##### Opportunity 2: Extract magnifier/pixel-probe helpers

**Proposed Structure**: `image_viewer_magnifier.py` for handle-drag magnifier and `_get_pixel_value_at_coords`

**Evaluation**: Ease 4/5, Safety 4/5, Practicality 4/5, Recommendation 4/5 — **Overall 4.00/5**

**Priority**: Medium

---

### File: `overlay_manager.py`

**Location**: `src/gui/overlay_manager.py`  
**Line Count**: 1257  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- `ViewportOverlayWidget(QWidget)` (~255 lines) — corner labels, MPR banner
- `OverlayManager` (~950 lines)
- `create_overlay_items` (~243 lines), `_create_widget_overlays` (~97 lines)

#### Dependencies
- **Depends on**: `DICOMParser`, Qt graphics/scene, config modes
- **Depended upon by**: `subwindow_manager_factory`, `keyboard_event_handler`, `slice_display_manager`, `overlay_coordinator`

#### Refactoring Opportunities

##### Opportunity 1: Move `ViewportOverlayWidget` to `viewport_overlay_widget.py`

**Evaluation**: Ease 5/5, Safety 5/5, Practicality 4/5, Recommendation 4/5 — **Overall 4.50/5**

**Priority**: High

##### Opportunity 2: Split scene overlay creation from widget overlay path

**Proposed Structure**: `overlay_scene_builder.py`, `overlay_widget_builder.py`

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 4/5, Recommendation 4/5 — **Overall 3.50/5**

**Priority**: Medium

---

### File: `pylinac_runner.py`

**Location**: `src/qa/pylinac_runner.py`  
**Line Count**: 1247  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- **17 module-level functions** (no classes)
- Domains mixed in one file:
  - PDF notes/assembly (`build_mri_*`, `assemble_mri_compare_pdf`) — ~300+ lines
  - ACR CT analysis (`run_acr_ct_analysis`) — ~147 lines
  - ACR MRI large (`run_acr_mri_large_analysis`, `run_acr_mri_large_batch`) — ~370 lines
  - Analyzer builders and diagnostics

#### Dependencies
- **Depends on**: pylinac (lazy in places), `qa.analysis_types`, PDF tooling
- **Depended upon by**: `qa_app_facade`, `qa.worker`

#### Refactoring Opportunities

##### Opportunity 1: Split by modality/package

**Proposed Structure**:
- `src/qa/pylinac_acr_ct.py`
- `src/qa/pylinac_acr_mri.py`
- `src/qa/pylinac_mri_pdf.py`
- `pylinac_runner.py` re-exports public API for backward compatibility

**Evaluation**: Ease 4/5, Safety 4/5, Practicality 5/5, Recommendation 5/5 — **Overall 4.50/5**

**Priority**: High

##### Opportunity 2: Shared `_jsonable` / result helpers in `qa_result_utils.py`

**Evaluation**: Ease 5/5, Safety 5/5, Practicality 3/5, Recommendation 3/5 — **Overall 4.00/5**

**Priority**: Medium

---

### File: `view_state_manager.py`

**Location**: `src/core/view_state_manager.py`  
**Line Count**: 1236  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- `ViewStateManager`: **35 methods**
- Large methods: `store_initial_view_state` (~124), `reset_view` (~231), `handle_window_changed` (~130), `handle_rescale_toggle` (~100), orientation save/restore blocks

#### Dependencies
- **Depends on**: image viewer, W/L controls, series navigator, callbacks to redisplay slice
- **Depended upon by**: `subwindow_manager_factory` (per-subwindow instance)

#### Refactoring Opportunities

##### Opportunity 1: Extract window/level state machine to `view_window_level_state.py`

**Proposed Structure**: User W/L cache, preset application, drag handling, rescale toggle.

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 4/5, Recommendation 4/5 — **Overall 3.50/5**

**Priority**: Medium

##### Opportunity 2: Extract zoom/viewport fit logic to `view_transform_state.py`

**Covers**: `store_initial_view_state`, `reset_view`, viewport resize handlers.

**Evaluation**: Ease 3/5, Safety 3/5, Practicality 4/5, Recommendation 4/5 — **Overall 3.50/5**

**Priority**: Medium

##### Opportunity 3: Series inversion + orientation persistence module

**Evaluation**: Ease 4/5, Safety 4/5, Practicality 3/5, Recommendation 3/5 — **Overall 3.50/5**

**Priority**: Medium

---

## Prioritized Recommendations

### High Priority (Overall Score ≥ 4.0)

| # | Opportunity | File | Score |
|---|-------------|------|-------|
| 1 | Extract remaining handler clusters from `DICOMViewerApp` | `main.py` | 4.50 |
| 2 | Split ROI graphics items to `roi_graphics_items.py` | `roi_manager.py` | 4.50 |
| 3 | Split `pylinac_runner` by modality/PDF | `pylinac_runner.py` | 4.50 |
| 4 | Extract About dialog | `main_window.py` | 4.50 |
| 5 | Move `ViewportOverlayWidget` to own module | `overlay_manager.py` | 4.50 |
| 6 | Extract subwindow signal wiring module | `subwindow_lifecycle_controller.py` | 4.00 |
| 7 | Extract focused panel sync helpers | `subwindow_lifecycle_controller.py` | 4.00 |
| 8 | Decompose `_resolve_window_level_for_series_transition` | `slice_display_manager.py` | 4.00 |
| 9 | Extract toast overlay | `main_window.py` | 4.00 |
| 10 | Extract magnifier/pixel-probe helpers | `image_viewer_view.py` | 4.00 |

### Medium Priority (Overall Score 3.0–3.9)

| # | Opportunity | File | Score |
|---|-------------|------|-------|
| 1 | `SubwindowStateService` | `main.py` | 3.75 |
| 2 | Continue façade extraction | `main.py` | 3.75 |
| 3 | MPR display pipeline split | `mpr_controller.py` | 3.75 |
| 4 | `SliceDisplayContext` dataclass | `slice_display_manager.py` | 3.75 |
| 5 | Viewport decoration vs image pipeline split | `image_viewer_view.py` | 3.75 |
| 6 | ROI statistics module | `roi_manager.py` | 3.50 |
| 7 | Overlay scene/widget builders | `overlay_manager.py` | 3.50 |
| 8 | View W/L state machine split | `view_state_manager.py` | 3.50 |
| 9 | View transform state split | `view_state_manager.py` | 3.50 |
| 10 | MPR activation module | `mpr_controller.py` | 3.50 |

### Low Priority (Overall Score < 3.0)

| # | Opportunity | File | Score |
|---|-------------|------|-------|
| 1 | Further split `ROIManager` core before controller boundaries clarified | `roi_manager.py` | 2.25 |

---

## Files Appropriately Large

None of the top 10 are justified to remain at current size without further decomposition. Closest case:

- **`main.py` as composition root**: May remain the largest file after refactor, but target **<1500 lines** with handlers/facades carrying feature logic (currently 3024).

---

## Observations and Patterns

1. **Prior refactor work is paying off**: `main.py` −593 lines since 2026-04-20; `slice_display_manager.display_slice` is now a staged pipeline; menu/toolbar/theme already extracted from `MainWindow`.
2. **New bottleneck**: `_resolve_window_level_for_series_transition` (~301 lines) replaced monolithic `display_slice` as the primary complexity hotspot in slice display.
3. **Signal wiring anti-pattern**: `subwindow_lifecycle_controller.py` and `main.py` still concentrate hundreds of lines of `connect()` calls — high-value, medium-risk extractions.
4. **Mixin pattern**: `image_viewer_view.py` follows successful `image_viewer_input.py` split; same approach applies to viewport decorations and `set_image`.
5. **QA module**: `pylinac_runner.py` is a clear package-split candidate (function-only, weak coupling between CT vs MRI vs PDF).
6. **Architecture guardrails**: `scripts/check_architecture_boundaries.py` forbids `gui` → `main` imports; new modules should use facades, signals, or injected callbacks.
7. **Performance plan overlap**: [`PERFORMANCE_DEEP_DIVE_PLAN.md`](../plans/supporting/PERFORMANCE_DEEP_DIVE_PLAN.md) targets hot paths in `mpr_controller`, `slice_display_manager`, and loaders — refactor splits can align with perf work (e.g. isolate `display_mpr_slice` for profiling).

---

## Assessment Checklist

### Preparation

- [x] Create timestamped copy of this template
- [x] **Remember: Only edit the timestamped assessment file - do not modify any code files**
- [x] Identify all code files in codebase (root, `src/`, `lib/`, `utils/`, `scripts/`, etc.)
- [x] **Exclude backup files** (files with "backup", "_BAK", ".bak" in name or in backup folders)
- [x] Count lines for each file
- [x] Create list of files exceeding 750 lines (focused on top 10 Python ≥600)

### Analysis

For each file exceeding threshold (top 10):

- [x] Document file path and line count
- [x] List all functions in the file (summary / largest methods)
- [x] Identify function groupings
- [x] Analyze dependencies (what it uses, what uses it)
- [x] Identify code organization patterns
- [x] Identify refactoring opportunities
- [x] Document proposed refactoring plan
- [x] Evaluate each refactoring suggestion (Ease, Safety, Practicality, Recommendation)
- [x] Calculate overall score for each suggestion
- [x] Prioritize recommendations

### Documentation

- [x] Create summary table of all files analyzed
- [x] Create prioritized list of refactoring recommendations
- [x] Document any files that are appropriately large (with justification)
- [x] Note any patterns or observations about the codebase structure

---

## Next Steps

- [ ] Review prioritized recommendations with user/team
- [ ] Create implementation plan(s) for selected high-priority items (suggest: `roi_graphics_items` split + `pylinac_runner` package split as low-risk first wins)
- [ ] Schedule refactoring work incrementally with `tests/smoke/test_refactor_regression.py` and targeted suites after each phase
- [ ] Re-run assessment after major extractions or quarterly

---

*Master template unchanged: [`dev-docs/templates-generalized/refactor-assessment-template.md`](../templates-generalized/refactor-assessment-template.md)*
