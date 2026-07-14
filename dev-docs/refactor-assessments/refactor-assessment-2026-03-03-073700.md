# Refactor Assessment - 2026-03-03 07:37:00

## Assessment Date
- **Date**: 2026-03-03
- **Time**: 07:37:00
- **Assessor**: GPT-5.1 AI Agent

## Files Analyzed

### Summary Table

| File | Location | Line Count | Exceeds Threshold | Status |
|------|----------|------------|-------------------|--------|
| main.py | `src/main.py` | 3375 | Yes (Python > 600) | Analyzed |

## Detailed Analysis

### File: main.py

**Location**: `src/main.py`  
**Line Count**: 3375  
**Exceeds Threshold**: Yes (Python guideline ~600 lines)

#### Code Structure Inventory

- `class DICOMViewerApp(QObject)` (roughly lines 98–3466): Central application class coordinating UI, configuration, DICOM loading/processing, ROI/annotation tools, multi-window layout, fusion, overlays, privacy mode, and event wiring.
  - `__init__`: Very large initializer that:
    - Creates and configures the Qt application and main window.
    - Instantiates many managers and widgets (`ConfigManager`, `DICOMLoader`, `DICOMOrganizer`, `DICOMProcessor`, `TagEditHistoryManager`, `UndoRedoManager`, `AnnotationClipboard`, `MetadataPanel`, `ROIManager`, `MeasurementTool`, `AnnotationManager`, `ROIStatisticsPanel`, `ROIListPanel`, `SeriesNavigator`, `CineControlsWidget`, `IntensityProjectionControlsWidget`, `FusionProcessor`, `FusionControlsWidget`, `OverlayManager`, etc.).
    - Sets up the multi-window layout (`MultiWindowLayout`) and focused subwindow state.
    - Initializes per-subwindow managers and lifecycle controller.
    - Initializes legacy "current_*" dataset fields for backward compatibility.
    - Calls `_initialize_handlers()`, `_connect_signals()`, and sets initial mouse/interaction modes.
  - `_initialize_subwindow_managers`: Creates and wires many per-subwindow manager/coordinator objects, handling lazy creation of subwindows and fallback behavior.
  - Numerous handler/utility methods (not exhaustively listed here due to size) likely cover:
    - File/open/import flows.
    - Series and slice navigation.
    - Multi-window layout changes (1x1, 1x2, 2x1, 2x2, swaps).
    - ROI creation, editing, statistics, and export.
    - Measurement tools and annotations.
    - Fusion controls, overlays, and privacy toggles.
    - Config persistence and UI state restoration.
- `def exception_hook(exctype, value, tb)` (near end of file): Global exception hook to log/report uncaught exceptions.
- `def main()` (end of file): Entry point creating the `DICOMViewerApp` instance and starting the Qt event loop.

#### Logical Groupings

- **Application bootstrap & configuration**
  - Qt application creation, application name/style.
  - `ConfigManager` initialization and retrieval of initial layout, overlay, smoothing, scroll-wheel mode, privacy view state.

- **Window/layout and subwindow management**
  - `MainWindow` creation and event filtering.
  - `MultiWindowLayout` setup, including initial layout and layout menu synchronization.
  - Focused subwindow tracking (`focused_subwindow_index`, `subwindow_data` dictionaries).
  - `_initialize_subwindow_managers` and related lifecycle logic to create per-subwindow managers and tie them to image viewers.

- **Metadata, privacy, and tag editing**
  - `MetadataPanel` setup, history manager wiring (`TagEditHistoryManager`), undo/redo callbacks, privacy mode propagation.

- **Image interaction tools and managers**
  - Window/level controls, zoom display, slice navigator, ROI manager, measurement tool, annotations, ROI statistics/list panels.
  - Central coordination of these tools per subwindow (e.g., view state, overlay coordinators).

- **Fusion, overlays, and visualization controls**
  - Fusion processing and control widgets.
  - Overlay manager configuration (font size, color, visible elements, privacy mode).
  - Smoothing/scroll-wheel behavior and pan/zoom interaction setup across subwindows.

- **DICOM loading, organizing, processing, navigation**
  - `DICOMLoader`, `DICOMOrganizer`, `DICOMProcessor`, `SeriesNavigator`.
  - Current dataset/study/series tracking fields for backward compatibility.

- **Event wiring and handlers**
  - `_initialize_handlers()` and `_connect_signals()` tying together:
    - Menu actions.
    - Toolbar buttons.
    - Keyboard shortcuts.
    - Interactions between the viewer, metadata panel, ROI/statistics, fusion controls, and overlays.

- **Error handling and entry point**
  - `exception_hook` and `main()` for process-level lifecycle.

#### Dependencies

- **Depends on** (incomplete but representative):
  - `config.config_manager.ConfigManager` (configuration and preferences).
  - DICOM-related modules: `DICOMLoader`, `DICOMOrganizer`, `DICOMProcessor`, likely residing under `core/` or similar.
  - GUI modules: `MainWindow`, `ImageViewer`, `MultiWindowLayout`, `MetadataPanel`, `WindowLevelControls`, `ZoomDisplayWidget`, `SliceNavigator`, `ROIStatisticsPanel`, `ROIListPanel`, `CineControlsWidget`, `IntensityProjectionControlsWidget`, etc.
  - ROI/annotation tooling: `ROIManager`, `MeasurementTool`, `AnnotationManager`, `AnnotationClipboard`, `AnnotationPasteHandler`.
  - Layout and lifecycle: `SubwindowLifecycleController`, various coordinator/manager classes (view state, overlays, crosshair, measurement/ROI coordinators).
  - Fusion: `FusionHandler` (per-subwindow), `FusionProcessor`, `FusionControlsWidget`, `FusionCoordinator`.
  - Qt/PySide6 types (`QApplication`, `QObject`, `QStyleFactory`, signals/slots).

- **Depended upon by**:
  - `main()` function in the same file, and any external scripts that import and invoke this entry point.
  - Other modules may reference `DICOMViewerApp` directly for integration or testing, although the primary usage is as the main GUI entry point.

The result is **very tight coupling**: the central app class knows about almost all major components, constructs them directly, and often wires their interactions. Most other modules are leaf dependencies; they rarely depend on each other directly and instead communicate through this monolithic orchestrator.

#### Code Organization

- The file is structured around a **single giant class** with many responsibilities and a large initializer, followed by a small number of module-level functions.
- There are logical sections (managers/controls initialization, subwindow manager initialization, handler initialization, signal wiring, legacy state, etc.), but they all live inside the same class and file, which:
  - Makes navigation difficult.
  - Mixes concerns such as configuration, layout, ROI/statistics, fusion, overlays, and event wiring.
  - Increases the cognitive load required to understand or change any one behavior.
- Some responsibilities (e.g., ROI handling, layout handling, metadata/privacy) appear cohesive enough to become their own controller modules but are currently implemented as methods/attributes on `DICOMViewerApp`.

#### Refactoring Opportunities

##### Opportunity 1: Extract layout and subwindow management into a dedicated controller module

**Brief Description**:  
Move multi-window layout logic, subwindow lifecycle handling, focused subwindow tracking, and per-subwindow manager orchestration out of `DICOMViewerApp` into a dedicated controller module (e.g., `layout/subwindow_controller.py`).

**Proposed Structure**:
- New module: `src/layout/subwindow_controller.py` (or similar)
  - New class: `SubwindowLayoutController`
    - Responsible for:
      - Initializing `MultiWindowLayout`.
      - Managing layout modes (1x1, 1x2, 2x1, 2x2) and swaps.
      - Tracking focused subwindow index and subwindow data dictionaries.
      - Initializing and managing per-subwindow managers (ROI, measurement, overlays, crosshair, etc.).
      - Ensuring privacy and smoothing states are propagated to all subwindows.
  - Public API: methods such as `initialize_layout(config_manager)`, `set_layout_mode(mode)`, `get_focused_subwindow()`, `for_each_subwindow(callback)`, `update_privacy_mode(enabled)`, etc.
- Remaining in `DICOMViewerApp`:
  - High-level orchestration and coordination between layout controller, DICOM/session management, ROI/statistics, metadata panel, and fusion.
  - Application bootstrap and main window creation.

**Migration Strategy**:
1. Identify all attributes and methods on `DICOMViewerApp` that relate primarily to layout and subwindow management (e.g., `multi_window_layout`, `subwindow_managers`, `focused_subwindow_index`, `subwindow_data`, `_initialize_subwindow_managers`, focused-subwindow reference updates, etc.).
2. Create `SubwindowLayoutController` that takes minimal, explicit dependencies (e.g., `MainWindow`, `ConfigManager`) and internally manages `MultiWindowLayout` and per-subwindow managers.
3. Move layout/subwindow-specific logic into `SubwindowLayoutController`, adjusting references to use controller methods instead of direct attribute access.
4. Update `DICOMViewerApp.__init__` to:
   - Instantiate `SubwindowLayoutController`.
   - Delegate layout-related calls (e.g., layout initialization, pan mode setup, privacy/smoothing propagation) to it.
5. Update handler/slot methods and other modules to call into `SubwindowLayoutController` where they previously manipulated `multi_window_layout` or subwindow managers directly.
6. Run existing tests and perform manual smoke testing (layout changes, pane swaps, ROI interactions in different layouts) to verify behavior.

**Benefits**:
- Significantly reduces the size and complexity of `DICOMViewerApp`.
- Improves separation of concerns: window layout logic is isolated from DICOM/session/ROI logic.
- Makes layout behavior easier to test in isolation (unit tests for controller without spinning up the full app).
- Provides a clearer public API for layout-related operations, reducing accidental tight coupling.

**Evaluation**:
- **Ease of Implementation**: 3/5 – Moderate; requires careful extraction but logic is conceptually grouped and not inherently algorithmically complex.
- **Safety**: 3/5 – Medium risk; layout and subwindow management affect many user workflows and must be tested across layouts.
- **Practicality**: 4/5 – Good benefit-to-effort ratio; layout complexity is a major contributor to class bloat.
- **Recommendation**: 4/5 – Recommended as an early refactor to make future changes safer.
- **Overall Score**: 3.50/5

**Priority**: High

##### Opportunity 2: Extract ROI, measurement, and annotation coordination into a separate controller

**Brief Description**:  
Group ROI, measurement, annotation, and ROI statistics/list logic into a dedicated controller (e.g., `roi/roi_measurement_controller.py`) instead of having these responsibilities scattered across `DICOMViewerApp`.

**Proposed Structure**:
- New module: `src/roi/roi_measurement_controller.py`
  - New class: `ROIMeasurementController`
    - Owns:
      - `ROIManager`, `MeasurementTool`, `AnnotationManager`, `AnnotationClipboard`, `AnnotationPasteHandler`.
      - `ROIStatisticsPanel`, `ROIListPanel` wiring.
      - Connections between ROI changes and statistics/list updates.
      - Privacy and overlay integration for ROI display where appropriate.
  - Public API: high-level methods like `add_roi(...)`, `delete_roi(...)`, `copy_roi(...)`, `paste_roi(...)`, `update_statistics()`, `set_privacy_mode(enabled)`, etc.
- Remaining in `DICOMViewerApp`:
  - High-level coordination (e.g., when new series is loaded, inform the ROI controller; when layout changes, pass relevant image viewers).

**Migration Strategy**:
1. Identify all ROI/measurement/annotation related attributes in `DICOMViewerApp.__init__` and related methods.
2. Move construction and wiring of these components into `ROIMeasurementController`, giving it any required references (e.g., current image viewers, config manager, overlay manager).
3. Replace direct attribute usage in handlers with calls to `ROIMeasurementController` methods.
4. Ensure `ROIMeasurementController` exposes enough API surface to support existing workflows (ROI creation, edit, copy/paste, statistics export, etc.).
5. Test ROI-related workflows end-to-end (creation/editing, stats updates, list interactions, copy/paste, deletion).

**Benefits**:
- Concentrates ROI logic and dependencies in a single, cohesive module.
- Reduces clutter in `DICOMViewerApp` and improves readability.
- Makes ROI behavior easier to reason about and to test.
- Helps avoid layout or DICOM lifecycle changes accidentally impacting ROI behavior.

**Evaluation**:
- **Ease of Implementation**: 3/5 – Similar to Opportunity 1; structural refactor but not algorithmically complex.
- **Safety**: 3/5 – Moderate risk because ROI features are user-facing and must remain stable.
- **Practicality**: 4/5 – Good payoff in terms of modularity and maintainability.
- **Recommendation**: 4/5 – Recommended for medium-term refactoring after or alongside layout extraction.
- **Overall Score**: 3.50/5

**Priority**: Medium–High

##### Opportunity 3: Separate metadata/privacy and tag-edit history management into its own controller

**Brief Description**:  
Extract `MetadataPanel`, `TagEditHistoryManager`, undo/redo callbacks, and privacy state wiring into a dedicated `MetadataController` module.

**Proposed Structure**:
- New module: `src/metadata/metadata_controller.py`
  - New class: `MetadataController`
    - Manages:
      - `MetadataPanel` creation and configuration.
      - Linkage between the metadata panel and `TagEditHistoryManager`.
      - Undo/redo callbacks and availability checks.
      - Privacy mode updates for metadata display.
    - Interacts with current dataset/study/series identifiers without needing full app context.
- Remaining in `DICOMViewerApp`:
  - High-level calls such as "a new dataset has been loaded; update metadata controller" and "global privacy mode changed; notify metadata controller."

**Migration Strategy**:
1. Move metadata panel and history manager initialization into `MetadataController`.
2. Recreate the undo/redo callbacks and privacy wiring within that controller.
3. Provide minimal API methods (e.g., `set_current_dataset(dataset)`, `set_privacy_mode(enabled)`, `undo_last_tag_edit()`, `redo_last_tag_edit()`) that `DICOMViewerApp` can call.
4. Verify that all places in `DICOMViewerApp` that previously touched metadata/history now go through the controller.

**Benefits**:
- Isolates a clearly defined concern (metadata + history + privacy for tags).
- Reduces the number of responsibilities on `DICOMViewerApp`.
- Makes metadata behavior easier to reason about and change.

**Evaluation**:
- **Ease of Implementation**: 4/5 – Smaller, well-defined surface area compared to layout and ROI refactors.
- **Safety**: 4/5 – Lower risk; can be validated via focused tests and simple manual workflows.
- **Practicality**: 4/5 – High payoff with relatively small effort.
- **Recommendation**: 5/5 – Highly recommended as an early refactor to chip away at `DICOMViewerApp` complexity.
- **Overall Score**: 4.25/5

**Priority**: High

##### Opportunity 4: Slim down `__init__` and centralize handler/signal initialization

**Brief Description**:  
Refactor `DICOMViewerApp.__init__` so that it delegates initialization to a small number of clearly named helper methods or separate modules, reducing the length and complexity of the constructor.

**Proposed Structure**:
- Within `src/main.py` initially:
  - Helper methods such as `_init_core_managers()`, `_init_view_components()`, `_init_controllers()`, `_init_state()`, `_post_init_layout_and_privacy()`.
- Longer term:
  - As other controllers (`SubwindowLayoutController`, `ROIMeasurementController`, `MetadataController`, etc.) are introduced, `__init__` mostly becomes:
    - "Instantiate controllers" + "wire high-level interactions" + "start application."

**Migration Strategy**:
1. Identify logical clusters of initialization steps and group them into private helper methods.
2. Ensure helpers are side-effect free outside of assigning to instance attributes.
3. Gradually replace long inline initialization with calls to these helpers.
4. Once controllers/modules are introduced (from other opportunities), move entire helpers into those modules.

**Benefits**:
- Immediately improves readability and navigability of `__init__`.
- Provides clearer hooks for further extraction into modules without changing behavior.
- Lowers the risk of accidental regressions when adding new initialization logic.

**Evaluation**:
- **Ease of Implementation**: 4/5 – Mechanically straightforward.
- **Safety**: 4/5 – Low risk if changes are limited to grouping existing statements.
- **Practicality**: 4/5 – Meaningful quality-of-life improvement for developers working with this file.
- **Recommendation**: 4/5 – Recommended as a short-term clean-up even before larger extractions.
- **Overall Score**: 4.00/5

**Priority**: High

## Prioritized Recommendations

### High Priority (Overall Score ≥ 4.0)
1. **Extract metadata/privacy and tag-edit history into `MetadataController`** – Score: 4.25/5  
   - **File**: `src/main.py`  
   - **Justification**: Well-bounded responsibility with smaller surface area; good first step to break down `DICOMViewerApp` with lower risk and high clarity.

2. **Slim down `DICOMViewerApp.__init__` via structured helper methods (and future controllers)** – Score: 4.00/5  
   - **File**: `src/main.py`  
   - **Justification**: Improves readability and maintainability immediately and prepares the file for more ambitious extractions.

### Medium Priority (Overall Score 3.0–3.9)
1. **Extract layout and subwindow management into `SubwindowLayoutController`** – Score: 3.50/5  
   - **File**: `src/main.py`  
   - **Justification**: Large, impactful refactor that will substantially reduce complexity but touches many workflows; best tackled after initial high-priority cleanups.

2. **Extract ROI, measurement, and annotation coordination into `ROIMeasurementController`** – Score: 3.50/5  
   - **File**: `src/main.py`  
   - **Justification**: Strong structural improvement with moderate risk; suggested once metadata/layout refactors establish a clear pattern for controllers.

### Low Priority (Overall Score < 3.0)
- None identified at this stage for `src/main.py`. Future assessments may identify additional, lower-priority refactors once major responsibilities have been modularized.

## Files Appropriately Large

- None specifically justified as "appropriately large" yet. At present, `src/main.py` is **not** considered appropriately large given its breadth of responsibilities; it is the primary target for refactoring.

## Observations and Patterns

- The project appears to follow a **controller/manager-heavy architecture**, but many controllers/managers are constructed and orchestrated in a single central class, rather than being organized into smaller, dedicated orchestration modules.
- The `DICOMViewerApp` class acts as a "god object," coordinating many concerns that could be handled by specialized controllers (layout, ROI, metadata, fusion, overlays, etc.).
- Introducing a **set of focused controllers** with clear APIs would:
  - Reduce the size and complexity of `src/main.py`.
  - Improve testability of individual features.
  - Make it easier to reason about and evolve specific aspects of the viewer (layout, ROI, metadata, fusion) independently.
- A follow-up refactor assessment is recommended after the first wave of controller extractions to reassess file sizes and identify remaining hotspots.

## Next Steps

- [ ] Review prioritized recommendations with user/team.
- [ ] Decide ordering and scope for the first implementation wave (e.g., `MetadataController` + `__init__` cleanup).
- [ ] Create detailed implementation plans for high-priority refactorings (possibly as separate dev-docs plans).
- [ ] Schedule and execute refactorings with appropriate unit/manual testing.
- [ ] Run a new refactor assessment after major refactors to update findings.

