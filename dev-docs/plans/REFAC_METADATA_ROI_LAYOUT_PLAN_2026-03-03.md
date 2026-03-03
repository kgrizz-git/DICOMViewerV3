## Refactor Plan – Metadata, ROI/Measurement, and `DICOMViewerApp` Initialization

- **Date**: 2026-03-03  
- **Target Files**: Primarily `src/main.py` (plus new controller modules)  
- **Goals**:
  - **Extract metadata/privacy and tag-edit history into `MetadataController`**.
  - **Extract ROI, measurement, and annotation coordination into `ROIMeasurementController`**.
  - **Slim down `DICOMViewerApp.__init__` via structured helper methods and controller usage**.
  - **Finish by running a new refactor assessment using the refactor-assessment template.**

---

## Phase 0 – Planning and Scoping

- [x] Review `refactor-assessment-2026-03-03-073700.md` and confirm refactor priorities.
- [x] Identify all metadata-related, ROI/measurement/annotation-related, and initialization-heavy sections inside `DICOMViewerApp` that will be in scope.
- [x] Decide on final module locations/names (e.g. `metadata/metadata_controller.py`, `roi/roi_measurement_controller.py`, etc.) consistent with existing project structure.
- [x] Document any external APIs (other modules) that currently depend directly on `DICOMViewerApp` internals that may need to call into the new controllers.

---

## Phase 1 – Extract `MetadataController`

### Phase 1.1 – Design

- [x] Define responsibilities and public API of `MetadataController`:
  - [x] Ownership of `MetadataPanel`, `TagEditHistoryManager`, and related undo/redo logic.
  - [x] Handling of privacy mode for metadata display.
  - [x] Methods for updating current dataset/study/series context.
- [x] Decide on constructor dependencies (e.g. config manager, undo/redo manager, callbacks, logging).
- [x] Sketch class/method signatures and interaction points with `DICOMViewerApp` (e.g. `update_current_dataset`, `set_privacy_mode`, `can_undo`, `undo_last_tag_edit`, etc.).

### Phase 1.2 – Implementation

- [x] Create new module `metadata/metadata_controller.py` (exact path/name to be finalized in Phase 1.1).
- [x] Move `MetadataPanel` and `TagEditHistoryManager` construction from `DICOMViewerApp.__init__` into `MetadataController`.
- [x] Move and/or recreate metadata-specific undo/redo callbacks within `MetadataController`.
- [x] Add methods to `MetadataController` for:
  - [x] Setting the current dataset / study / series identifiers.
  - [x] Toggling privacy mode and propagating to the metadata panel.
  - [x] Querying undo/redo availability for UI components.
- [x] Update `DICOMViewerApp` to:
  - [x] Instantiate `MetadataController`.
  - [x] Replace direct use of `metadata_panel`, `tag_edit_history`, and related fields with calls to `MetadataController`.

### Phase 1.3 – Testing

- [x] Identify existing automated tests covering metadata/tag-edit behavior (if any).
- [x] Design new tests for `MetadataController`:
  - [x] Unit tests for undo/redo behavior and history management.
  - [x] Tests for privacy mode toggling and its effect on metadata display.
  - [x] Tests for updating current dataset context and ensuring UI reflects changes.
- [x] Implement new unit tests (e.g. in `tests/metadata/` or similar).
- [x] Run automated test suite (within venv):
  - [x] `python tests/run_tests.py` or `python -m pytest tests/ -v`
- [ ] Perform manual smoke tests:
  - [ ] Open DICOM studies and verify metadata displays correctly.
  - [ ] Edit tags and confirm undo/redo works as expected.
  - [ ] Toggle privacy view and verify sensitive metadata is appropriately hidden/shown.

---

## Phase 2 – Extract `ROIMeasurementController`

### Phase 2.1 – Design

- [x] Define responsibilities and public API of `ROIMeasurementController`:
  - [x] Ownership and coordination of `ROIManager`, `MeasurementTool`, `AnnotationManager`, `AnnotationClipboard`, `AnnotationPasteHandler`.
  - [x] Wiring and update flows for `ROIStatisticsPanel` and `ROIListPanel`.
  - [x] Integration points with image viewers / layout for ROI display and interaction.
  - [x] Hooks for privacy, overlays, and series/dataset changes.
- [x] Decide constructor dependencies (e.g. config manager, overlay manager, access to current image viewers).
- [x] Sketch method signatures for high-level operations (e.g. `add_roi`, `delete_roi`, `copy_roi`, `paste_roi`, `update_statistics`, `set_privacy_mode`, `on_new_series_loaded`).

### Phase 2.2 – Implementation

- [x] Create new module `roi/roi_measurement_controller.py` (exact path/name to be finalized in Phase 2.1).
- [x] Move construction and wiring of ROI/measurement/annotation components from `DICOMViewerApp` into `ROIMeasurementController`.
- [x] Centralize ROI-related signal/slot connections (panel updates, list updates, etc.) in the new controller.
- [x] Add methods in `ROIMeasurementController` to:
  - [x] Reflect changes when the focused subwindow or associated image viewer changes.
  - [x] Handle privacy/overlay updates relevant to ROI visualization.
  - [x] Respond to series/dataset load/unload events.
- [x] Update `DICOMViewerApp` to:
  - [x] Instantiate `ROIMeasurementController` with required dependencies.
  - [x] Delegate ROI/measurement/annotation operations to the controller instead of accessing low-level objects directly.

### Phase 2.3 – Testing

- [x] Identify any existing automated tests that cover ROI, measurement, or annotation workflows.
- [x] Design new tests for `ROIMeasurementController`:
  - [x] Unit tests for ROI creation, modification, deletion, and copy/paste behavior.
  - [x] Tests for statistics and list updates when ROIs change.
  - [x] Tests for behavior when current dataset/series or focused subwindow changes.
- [x] Implement new unit/integration tests (e.g. in `tests/roi/` or appropriate location).
- [x] Run automated test suite (within venv):
  - [x] `python tests/run_tests.py` or `python -m pytest tests/ -v`
- [ ] Perform manual smoke tests:
  - [ ] Create/edit/delete ROIs in different layouts (1x1, 1x2, 2x1, 2x2).
  - [ ] Verify ROI statistics panel and ROI list panel update correctly.
  - [ ] Test annotation copy/paste across subwindows/series where applicable.

---

## Phase 3 – Slim Down `DICOMViewerApp.__init__`

### Phase 3.1 – Design

- [x] Identify logical initialization groups inside `DICOMViewerApp.__init__`:
  - [x] Core managers (config, DICOM loader/organizer/processor, undo/redo, history).
  - [x] View components (main window, multi-window layout, image viewers, panels/widgets).
  - [x] Controllers (metadata controller, ROI controller, others).
  - [x] Legacy state and compatibility fields.
  - [x] Signal/handler wiring.
- [x] Define a set of private helper methods (and/or further controllers where appropriate), such as:
  - [x] `_init_core_managers()`
  - [x] `_init_view_components()` (implemented as `_init_main_window_and_layout()`)
  - [x] `_init_controllers()` (implemented as `_init_controllers_and_tools()`)
  - [x] `_init_legacy_state()` (covered inside `_post_init_subwindows_and_handlers()`)
  - [x] `_post_init_layout_and_interaction()` (implemented as `_post_init_subwindows_and_handlers()`)

### Phase 3.2 – Implementation

- [x] Extract grouped sections of `__init__` into well-named private helper methods, without changing behavior.
- [x] Ensure new `MetadataController` and `ROIMeasurementController` are constructed and wired via `_init_controllers()` or equivalent.
- [x] Keep initialization order explicit and well-documented to avoid regressions (e.g. layout must exist before per-subwindow managers, controllers must be set up before signal wiring).
- [x] Remove any now-redundant attributes or initialization code from `DICOMViewerApp` that has been delegated to controllers.

### Phase 3.3 – Testing

- [x] Re-run full automated test suite (within venv):
  - [x] `python tests/run_tests.py` or `python -m pytest tests/ -v`
- [ ] Perform end-to-end manual smoke tests (to be done by user):
  - [ ] Application startup/shutdown.
  - [ ] Loading DICOM data, navigating series/slices.
  - [ ] Metadata viewing and editing (including undo/redo and privacy).
  - [ ] ROI/measurement/annotation workflows across different layouts.
  - [ ] Any other high-traffic user flows (cine, overlays, fusion where affected).

---

## Phase 4 – Final Verification and New Refactor Assessment

### Phase 4.1 – Documentation and Cleanup

- [x] Update any relevant developer documentation (e.g. `AGENTS.md`, related dev-doc plans) to describe the new controller structure and responsibilities.
- [x] Ensure naming and module layout are consistent with existing conventions (`src/`, controller/manager patterns).
- [x] Remove or update any comments that refer to old structures now handled by controllers.

### Phase 4.2 – New Refactor Assessment (Final Step)

- [x] Run a new refactor assessment using `dev-docs/templates-generalized/refactor-assessment-template.md`:
  - [x] Create a new timestamped assessment markdown file under `dev-docs/refactor-assessments/`.
  - [x] Recompute file line counts and re-evaluate `src/main.py` and any new controller modules.
  - [x] Document how the refactor changed file sizes, responsibilities, and coupling.
  - [x] Record any new refactoring opportunities discovered as a result of this reorganization.

