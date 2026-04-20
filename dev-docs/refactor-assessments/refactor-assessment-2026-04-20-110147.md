# Refactor Assessment - 2026-04-20 11:01:47

## Assessment Date
- **Date**: 2026-04-20
- **Time**: 11:01:47
- **Assessor**: Auto (AI agent)

## Scope

Focused assessment of the **2 largest non-backup, non-dependency code files** in this repository, as requested:

1. `src/main.py`
2. `src/core/slice_display_manager.py`

No code changes were made during this assessment.

## Files Analyzed

### Summary Table

| File | Location | Line Count | Exceeds Python Threshold (600) | Status |
|------|----------|------------|----------------------------------|--------|
| `main.py` | `src/main.py` | 3617 | Yes | Analyzed |
| `slice_display_manager.py` | `src/core/slice_display_manager.py` | 1559 | Yes | Analyzed |

---

## Detailed Analysis

### File: `main.py`

**Location**: `src/main.py`  
**Line Count**: 3617  
**Exceeds Threshold**: Yes (Python guideline: 600)

#### Code Structure Inventory

- Module entry and global exception handling:
  - `exception_hook` (line 3928)
  - `main` (line 3945)
- Main class:
  - `class DICOMViewerApp(QObject)` (line 154)
  - ~230 methods, including:
    - initialization pipeline methods (`_init_core_managers`, `_init_main_window_and_layout`, `_init_view_widgets`, `_post_init_subwindows_and_handlers`)
    - MPR/synchronization handlers
    - file open/close/clear/study/series lifecycle methods
    - signal/slot handlers for view, ROI, measurements, overlays, cine, QA, export, and dialogs
    - UI event handlers and keyboard/mouse interaction methods

#### Logical Groupings

- **Composition root / app bootstrap**: initialization and manager wiring.
- **Subwindow and layout lifecycle**: per-pane manager construction, focus changes, layout swaps.
- **Data lifecycle**: open, merge, clear, close series/study, sync state.
- **Feature verticals**:
  - MPR/intensity projection
  - cine playback/export
  - overlay/privacy/slice-sync
  - ROI/measurement/annotation
  - QA flows
  - export flows
- **UI event adapters**: many `_on_*` methods forwarding to managers/facades.

#### Dependencies

- **Depends on** (high fan-in):
  - Qt UI stack (`PySide6.QtWidgets`, `PySide6.QtCore`, `PySide6.QtGui`)
  - core managers/controllers (`mpr_controller`, `subwindow_lifecycle_controller`, `file_series_loading_coordinator`, etc.)
  - GUI widgets/dialogs (`main_window`, dialogs, viewers, navigators)
  - tools/controllers (`ROI`, annotation, metadata, undo/redo)
  - feature facades (`projection_app_facade`, `qa_app_facade`, `export_app_facade`, `cine_app_facade`)
- **Depended upon by**:
  - tests (e.g. `tests/test_main_signals_view.py`)
  - signal wiring module (typing/duck-typing usage in `core/app_signal_wiring.py`)
  - app startup path (`if __name__ == "__main__": sys.exit(main())`)

#### Code Organization

- Strengths:
  - explicit initialization phases and documented order.
  - extensive feature extraction already underway (facades, controller modules, signal wiring module).
- Issues:
  - very high method count in a single class with mixed concerns.
  - many event handlers are thin adapters that still keep class surface large.
  - broad import footprint and high coupling make change impact harder to reason about.

#### Refactoring Opportunities

##### Opportunity 1: Extract dialog/menu action slots into cohesive action modules

**Proposed Structure**:
- New modules under `src/core/actions/` (or similarly named package):
  - `view_actions.py` (privacy, overlays, display toggles)
  - `export_actions.py` (export dialogs, screenshot/cine/export entry handlers)
  - `qa_actions.py` (QA open/run/result dialogs)
  - `annotation_actions.py` (annotation options, copy/paste, visibility toggles)
- Keep `DICOMViewerApp` methods as minimal compatibility wrappers (or direct wiring to action objects where safe).

**Migration Strategy**:
1. Move highest-cohesion `_open_*` and `_on_*` methods first (small batches).
2. Keep method names stable initially; wrappers delegate to action objects.
3. Switch signal wiring to call action object callables directly when coverage is in place.
4. Remove wrappers in a later pass if desired.

**Benefits**:
- Reduces `main.py` by an estimated 500–1000 lines over phases.
- Improves readability of composition root vs. feature behavior.
- Lowers cognitive load when maintaining one feature area.

**Evaluation**:
- **Ease of Implementation**: 4/5 — many handlers are already thin and separable.
- **Safety**: 4/5 — wrapper-first strategy keeps behavior stable.
- **Practicality**: 5/5 — large maintainability gain for predictable effort.
- **Recommendation**: 5/5 — best first step for size reduction.
- **Overall Score**: 4.50/5

**Priority**: High

##### Opportunity 2: Introduce a focused `SubwindowStateService`

**Proposed Structure**:
- New module: `src/core/subwindow_state_service.py`
  - Encapsulate lookup helpers (`_get_subwindow_*`, focused index/state, assignment map, thumbnail support helpers).
  - Provide explicit typed API for `dataset`, `slice index`, `series UID`, and manager access.

**Migration Strategy**:
1. Move pure lookup/query methods with no UI side effects.
2. Replace direct dictionary/index access patterns in `main.py` with service methods.
3. Add focused tests around boundary conditions (invalid index, detached window, missing manager).

**Benefits**:
- Reduces repeated access patterns and defensive checks in `main.py`.
- Improves safety for subwindow-related operations.
- Makes downstream handler code shorter and less error-prone.

**Evaluation**:
- **Ease of Implementation**: 3/5
- **Safety**: 4/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 3.75/5

**Priority**: Medium

##### Opportunity 3: Formalize app façade boundaries and continue progressive extraction

**Proposed Structure**:
- Continue current pattern used by `projection_app_facade.py`, `qa_app_facade.py`, `export_app_facade.py`, and `cine_app_facade.py`.
- Add/expand:
  - `overlay_app_facade.py`
  - `roi_measurement_app_facade.py` (UI adapter layer, not replacing existing ROI controller)
  - `study_lifecycle_app_facade.py`

**Migration Strategy**:
1. Group by independent feature stream and extract method clusters.
2. Keep stable app-level API for signal wiring while internals delegate.
3. Monitor startup sequence and avoid cross-facade circular dependencies.

**Benefits**:
- Aligns with architecture already in progress.
- Sustained file-size reduction while preserving behavior.
- Better modular ownership and testability.

**Evaluation**:
- **Ease of Implementation**: 3/5
- **Safety**: 3/5
- **Practicality**: 5/5
- **Recommendation**: 4/5
- **Overall Score**: 3.75/5

**Priority**: Medium

---

### File: `slice_display_manager.py`

**Location**: `src/core/slice_display_manager.py`  
**Line Count**: 1559  
**Exceeds Threshold**: Yes (Python guideline: 600)

#### Code Structure Inventory

- Module helpers:
  - `_make_no_pixel_placeholder_pil` (line 49)
  - `_overlay_metadata_dataset_for_slice` (line 69)
- Main class:
  - `class SliceDisplayManager` (line 115)
  - 18 methods, with one very large central method:
    - `display_slice` begins at line 334 and spans most of file logic
    - additional methods include ROI/measurement/annotation display, slice change handling, and series navigation

#### Logical Groupings

- **Context and state preparation**: current context, rescale params, series identity.
- **Image/pixel path**: projection handling, no-pixel placeholder, image render path.
- **W/L and control synchronization**: presets, WC/WW, rescale conversions, UI controls update.
- **Overlay and annotation rendering**: corner metadata, ROIs, measurements, text/arrow annotations, PS/KO annotations.
- **Navigation behavior**: slice changes, series changes, keyboard navigation.

#### Dependencies

- **Depends on**:
  - `DICOMProcessor`, `DICOMParser`, `DICOMOrganizer`
  - `ImageViewer`, metadata panel, slice navigator, W/L controls
  - `ROIManager`, `MeasurementTool`, `AnnotationManager`, `OverlayManager`
  - slice utilities and debug flags
- **Depended upon by**:
  - `src/core/subwindow_manager_factory.py` (construction and use in per-subwindow manager graph)
  - indirectly by `main.py` through subwindow manager orchestration
  - behavior alignment references in viewer/navigation modules (comments and integration assumptions)

#### Code Organization

- Strengths:
  - clear high-level responsibility area (slice display pipeline).
  - good integration with existing manager ecosystem.
- Issues:
  - `display_slice` carries too many responsibilities and side effects.
  - hard to unit test isolated branches due to broad mutable state and UI calls intermixed with data logic.
  - some inline imports and exception-swallowing blocks reduce analyzability.

#### Refactoring Opportunities

##### Opportunity 1: Split `display_slice` into a deterministic pipeline with private stages

**Proposed Structure**:
- Keep public `display_slice`, but orchestrate private stage methods such as:
  - `_resolve_dataset_for_slice_context`
  - `_prepare_view_state_for_dataset`
  - `_render_base_image_and_apply_window_level`
  - `_sync_controls_and_metadata`
  - `_render_overlays_and_annotations`

**Migration Strategy**:
1. Extract pure/preparation steps first (no scene writes).
2. Extract render/sync steps as separate methods with narrow inputs.
3. Keep behavior order exactly unchanged during first pass.
4. Add targeted tests around branch behavior (new series vs same series, no pixel data, projection on/off).

**Benefits**:
- Major readability and testability improvement.
- Lower risk for future behavioral changes in one stage.
- Keeps runtime efficiency unchanged (method extraction only).

**Evaluation**:
- **Ease of Implementation**: 4/5
- **Safety**: 4/5
- **Practicality**: 5/5
- **Recommendation**: 5/5
- **Overall Score**: 4.50/5

**Priority**: High

##### Opportunity 2: Extract annotation and overlay scene-application into collaborator modules

**Proposed Structure**:
- New module candidates:
  - `src/core/slice_overlay_renderer.py`
  - `src/core/slice_annotation_renderer.py`
- `SliceDisplayManager` delegates scene mutation operations to these collaborators.

**Migration Strategy**:
1. Move the annotation-manager scene block first (currently large try/except section).
2. Move overlay dataset selection and corner overlay update path.
3. Keep same callbacks/contracts to avoid breaking `main.py` flow.

**Benefits**:
- Better separation between image pipeline and scene decoration.
- Easier debugging of overlays vs pixel rendering.
- Enables focused tests and potential reuse for MPR-specific paths.

**Evaluation**:
- **Ease of Implementation**: 3/5
- **Safety**: 3/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 3.50/5

**Priority**: Medium

##### Opportunity 3: Introduce typed context object for current-study/current-series/slice state

**Proposed Structure**:
- New dataclass (e.g., `SliceDisplayContext`) containing:
  - `current_studies`, `current_study_uid`, `current_series_uid`, `current_slice_index`, `dataset`
- Methods accept/return this context rather than many parallel parameters.

**Migration Strategy**:
1. Add dataclass and adapt internal private methods first.
2. Keep external public method signatures stable in initial pass.
3. Expand use gradually where manager interactions benefit from explicit context.

**Benefits**:
- Reduces parameter drift and mismatched state bugs.
- Easier to reason about and mock in tests.
- Improves static type quality and code navigation.

**Evaluation**:
- **Ease of Implementation**: 3/5
- **Safety**: 4/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 3.75/5

**Priority**: Medium

---

## Prioritized Recommendations

### High Priority (Overall Score ≥ 4.0)

1. Split `SliceDisplayManager.display_slice` into staged private pipeline methods — **4.50/5**
2. Extract dialog/menu action slot clusters from `DICOMViewerApp` into cohesive action modules — **4.50/5**

### Medium Priority (Overall Score 3.0–3.9)

1. Introduce `SubwindowStateService` for `main.py` subwindow queries/state access — **3.75/5**
2. Continue façade-based extraction from `main.py` by feature stream — **3.75/5**
3. Add typed `SliceDisplayContext` object in `slice_display_manager.py` — **3.75/5**
4. Extract overlay/annotation scene rendering collaborators from `SliceDisplayManager` — **3.50/5**

### Low Priority (Overall Score < 3.0)

No low-priority items identified in this focused two-file assessment.

---

## Observations and Patterns

- Refactoring is already in progress in this repository (facades, wiring modules, manager factory extraction).  
- The largest remaining gains come from **reducing orchestration surface area in `main.py`** and **decomposing `display_slice` in `slice_display_manager.py`**.
- Most proposed changes can be done incrementally with low regression risk if wrapper-first migration is used.

## Next Steps

- [ ] Review prioritized recommendations with user/team
- [ ] Create implementation plan for high-priority item #1 (`display_slice` staged extraction)
- [ ] Create implementation plan for high-priority item #2 (`main.py` action module extraction)
- [ ] Execute refactors incrementally with focused regression tests after each phase
