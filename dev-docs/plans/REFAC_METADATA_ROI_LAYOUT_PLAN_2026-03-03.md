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

- [ ] Review `refactor-assessment-2026-03-03-073700.md` and confirm refactor priorities.
- [ ] Identify all metadata-related, ROI/measurement/annotation-related, and initialization-heavy sections inside `DICOMViewerApp` that will be in scope.
- [ ] Decide on final module locations/names (e.g. `metadata/metadata_controller.py`, `roi/roi_measurement_controller.py`, etc.) consistent with existing project structure.
- [ ] Document any external APIs (other modules) that currently depend directly on `DICOMViewerApp` internals that may need to call into the new controllers.

---

## Phase 1 – Extract `MetadataController`

### Phase 1.1 – Design

- [ ] Define responsibilities and public API of `MetadataController`:
  - [ ] Ownership of `MetadataPanel`, `TagEditHistoryManager`, and related undo/redo logic.
  - [ ] Handling of privacy mode for metadata display.
  - [ ] Methods for updating current dataset/study/series context.
- [ ] Decide on constructor dependencies (e.g. config manager, undo/redo manager, callbacks, logging).
- [ ] Sketch class/method signatures and interaction points with `DICOMViewerApp` (e.g. `update_current_dataset`, `set_privacy_mode`, `can_undo`, `undo_last_tag_edit`, etc.).

### Phase 1.2 – Implementation

- [ ] Create new module `metadata/metadata_controller.py` (exact path/name to be finalized in Phase 1.1).
- [ ] Move `MetadataPanel` and `TagEditHistoryManager` construction from `DICOMViewerApp.__init__` into `MetadataController`.
- [ ] Move and/or recreate metadata-specific undo/redo callbacks within `MetadataController`.
- [ ] Add methods to `MetadataController` for:
  - [ ] Setting the current dataset / study / series identifiers.
  - [ ] Toggling privacy mode and propagating to the metadata panel.
  - [ ] Querying undo/redo availability for UI components.
- [ ] Update `DICOMViewerApp` to:
  - [ ] Instantiate `MetadataController`.
  - [ ] Replace direct use of `metadata_panel`, `tag_edit_history`, and related fields with calls to `MetadataController`.

### Phase 1.3 – Testing

- [ ] Identify existing automated tests covering metadata/tag-edit behavior (if any).
- [ ] Design new tests for `MetadataController`:
  - [ ] Unit tests for undo/redo behavior and history management.
  - [ ] Tests for privacy mode toggling and its effect on metadata display.
  - [ ] Tests for updating current dataset context and ensuring UI reflects changes.
- [ ] Implement new unit tests (e.g. in `tests/metadata/` or similar).
- [ ] Run automated test suite (within venv):
  - [ ] `python tests/run_tests.py` or `python -m pytest tests/ -v`
- [ ] Perform manual smoke tests:
  - [ ] Open DICOM studies and verify metadata displays correctly.
  - [ ] Edit tags and confirm undo/redo works as expected.
  - [ ] Toggle privacy view and verify sensitive metadata is appropriately hidden/shown.

---

## Phase 2 – Extract `ROIMeasurementController`

### Phase 2.1 – Design

- [ ] Define responsibilities and public API of `ROIMeasurementController`:
  - [ ] Ownership and coordination of `ROIManager`, `MeasurementTool`, `AnnotationManager`, `AnnotationClipboard`, `AnnotationPasteHandler`.
  - [ ] Wiring and update flows for `ROIStatisticsPanel` and `ROIListPanel`.
  - [ ] Integration points with image viewers / layout for ROI display and interaction.
  - [ ] Hooks for privacy, overlays, and series/dataset changes.
- [ ] Decide constructor dependencies (e.g. config manager, overlay manager, access to current image viewers).
- [ ] Sketch method signatures for high-level operations (e.g. `add_roi`, `delete_roi`, `copy_roi`, `paste_roi`, `update_statistics`, `set_privacy_mode`, `on_new_series_loaded`).

### Phase 2.2 – Implementation

- [ ] Create new module `roi/roi_measurement_controller.py` (exact path/name to be finalized in Phase 2.1).
- [ ] Move construction and wiring of ROI/measurement/annotation components from `DICOMViewerApp` into `ROIMeasurementController`.
- [ ] Centralize ROI-related signal/slot connections (panel updates, list updates, etc.) in the new controller.
- [ ] Add methods in `ROIMeasurementController` to:
  - [ ] Reflect changes when the focused subwindow or associated image viewer changes.
  - [ ] Handle privacy/overlay updates relevant to ROI visualization.
  - [ ] Respond to series/dataset load/unload events.
- [ ] Update `DICOMViewerApp` to:
  - [ ] Instantiate `ROIMeasurementController` with required dependencies.
  - [ ] Delegate ROI/measurement/annotation operations to the controller instead of accessing low-level objects directly.

### Phase 2.3 – Testing

- [ ] Identify any existing automated tests that cover ROI, measurement, or annotation workflows.
- [ ] Design new tests for `ROIMeasurementController`:
  - [ ] Unit tests for ROI creation, modification, deletion, and copy/paste behavior.
  - [ ] Tests for statistics and list updates when ROIs change.
  - [ ] Tests for behavior when current dataset/series or focused subwindow changes.
- [ ] Implement new unit/integration tests (e.g. in `tests/roi/` or appropriate location).
- [ ] Run automated test suite (within venv):
  - [ ] `python tests/run_tests.py` or `python -m pytest tests/ -v`
- [ ] Perform manual smoke tests:
  - [ ] Create/edit/delete ROIs in different layouts (1x1, 1x2, 2x1, 2x2).
  - [ ] Verify ROI statistics panel and ROI list panel update correctly.
  - [ ] Test annotation copy/paste across subwindows/series where applicable.

---

## Phase 3 – Slim Down `DICOMViewerApp.__init__`

### Phase 3.1 – Design

- [ ] Identify logical initialization groups inside `DICOMViewerApp.__init__`:
  - [ ] Core managers (config, DICOM loader/organizer/processor, undo/redo, history).
  - [ ] View components (main window, multi-window layout, image viewers, panels/widgets).
  - [ ] Controllers (metadata controller, ROI controller, others).
  - [ ] Legacy state and compatibility fields.
  - [ ] Signal/handler wiring.
- [ ] Define a set of private helper methods (and/or further controllers where appropriate), such as:
  - [ ] `_init_core_managers()`
  - [ ] `_init_view_components()`
  - [ ] `_init_controllers()`
  - [ ] `_init_legacy_state()`
  - [ ] `_post_init_layout_and_interaction()`

### Phase 3.2 – Implementation

- [ ] Extract grouped sections of `__init__` into well-named private helper methods, without changing behavior.
- [ ] Ensure new `MetadataController` and `ROIMeasurementController` are constructed and wired via `_init_controllers()` or equivalent.
- [ ] Keep initialization order explicit and well-documented to avoid regressions (e.g. layout must exist before per-subwindow managers, controllers must be set up before signal wiring).
- [ ] Remove any now-redundant attributes or initialization code from `DICOMViewerApp` that has been delegated to controllers.

### Phase 3.3 – Testing

- [ ] Re-run full automated test suite (within venv):
  - [ ] `python tests/run_tests.py` or `python -m pytest tests/ -v`
- [ ] Perform end-to-end manual smoke tests:
  - [ ] Application startup/shutdown.
  - [ ] Loading DICOM data, navigating series/slices.
  - [ ] Metadata viewing and editing (including undo/redo and privacy).
  - [ ] ROI/measurement/annotation workflows across different layouts.
  - [ ] Any other high-traffic user flows (cine, overlays, fusion where affected).

---

## Phase 4 – Final Verification and New Refactor Assessment

### Phase 4.1 – Documentation and Cleanup

- [ ] Update any relevant developer documentation (e.g. `AGENTS.md`, related dev-doc plans) to describe the new controller structure and responsibilities.
- [ ] Ensure naming and module layout are consistent with existing conventions (`src/`, controller/manager patterns).
- [ ] Remove or update any comments that refer to old structures now handled by controllers.

### Phase 4.2 – New Refactor Assessment (Final Step)

- [ ] Run a new refactor assessment using `dev-docs/templates-generalized/refactor-assessment-template.md`:
  - [ ] Create a new timestamped assessment markdown file under `dev-docs/refactor-assessments/`.
  - [ ] Recompute file line counts and re-evaluate `src/main.py` and any new controller modules.
  - [ ] Document how the refactor changed file sizes, responsibilities, and coupling.
  - [ ] Record any new refactoring opportunities discovered as a result of this reorganization.

