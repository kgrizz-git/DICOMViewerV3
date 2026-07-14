# Refactor Assessment - 2026-03-21 18:45:00

## Assessment Date
- **Date**: 2026-03-21
- **Time**: 18:45:00
- **Assessor**: GitHub Copilot (GPT-5.4)

## Scope and Method
- Assessed project-owned code files in root, `src/`, `tests/`, and `scripts/`.
- Excluded virtual environment files and backup files/folders per template rules.
- Used the template threshold for this pass: files exceeding **750 lines**.
- No code files were modified during this assessment.

## Files Analyzed

### Summary Table (Files Exceeding 750 Lines)

| File | Location | Line Count | Exceeds Threshold | Status |
|------|----------|------------|-------------------|--------|
| main.py | src/main.py | 3270 | Yes | Analyzed |
| image_viewer.py | src/gui/image_viewer.py | 3057 | Yes | Analyzed |
| file_operations_handler.py | src/core/file_operations_handler.py | 1686 | Yes | Analyzed |
| slice_display_manager.py | src/core/slice_display_manager.py | 1578 | Yes | Analyzed |
| overlay_manager.py | src/gui/overlay_manager.py | 1463 | Yes | Analyzed |
| export_manager.py | src/core/export_manager.py | 1455 | Yes | Analyzed |
| main_window.py | src/gui/main_window.py | 1430 | Yes | Analyzed |
| tag_export_dialog.py | src/gui/dialogs/tag_export_dialog.py | 1288 | Yes | Analyzed |
| series_navigator.py | src/gui/series_navigator.py | 1198 | Yes | Analyzed |
| annotation_manager.py | src/tools/annotation_manager.py | 1187 | Yes | Analyzed |
| roi_manager.py | src/tools/roi_manager.py | 1158 | Yes | Analyzed |
| fusion_controls_widget.py | src/gui/fusion_controls_widget.py | 1134 | Yes | Analyzed |
| view_state_manager.py | src/core/view_state_manager.py | 1097 | Yes | Analyzed |
| undo_redo.py | src/utils/undo_redo.py | 1074 | Yes | Analyzed |
| subwindow_lifecycle_controller.py | src/core/subwindow_lifecycle_controller.py | 1040 | Yes | Analyzed |
| fusion_coordinator.py | src/gui/fusion_coordinator.py | 1023 | Yes | Analyzed |
| file_series_loading_coordinator.py | src/core/file_series_loading_coordinator.py | 996 | Yes | Analyzed |
| roi_coordinator.py | src/gui/roi_coordinator.py | 988 | Yes | Analyzed |
| fusion_handler.py | src/core/fusion_handler.py | 892 | Yes | Analyzed |
| quick_start_guide_dialog.py | src/gui/dialogs/quick_start_guide_dialog.py | 835 | Yes | Analyzed |
| main_window_theme.py | src/gui/main_window_theme.py | 826 | Yes | Analyzed |
| fusion_technical_doc_dialog.py | src/gui/dialogs/fusion_technical_doc_dialog.py | 811 | Yes | Analyzed |
| mpr_controller.py | src/core/mpr_controller.py | 784 | Yes | Analyzed |
| dicom_loader.py | src/core/dicom_loader.py | 777 | Yes | Analyzed |

---

## Detailed Analysis

### File: `src/main.py`

**Location**: `src/main.py`  
**Line Count**: 3270  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Class: `DICOMViewerApp` (large orchestrator)
- Top-level methods: ~200
- Strong logical sections are already present via `_init_*`, `_connect_*`, and feature handlers.

#### Logical Groupings
- App bootstrap and staged initialization (`_init_core_managers`, `_init_main_window_and_layout`, etc.)
- Signal wiring and event orchestration (`_connect_signals` family)
- File lifecycle and loading (`_open_*`, `_close_*`, `_handle_load_first_slice`)
- Slice display and navigation (`_display_slice`, `_redisplay_current_slice`, navigator callbacks)
- Dialog opening and settings handlers

#### Dependencies
- **Depends on**: almost all core/gui/tools controllers and managers.
- **Depended upon by**: `run.py` / application entry path and runtime startup flow.

#### Refactoring Opportunities

##### Opportunity 1: Extract event wiring to a dedicated module (`core/app_signal_wiring.py` expansion)

> **Reviewer note — STATUS: Mostly complete.** `src/core/app_signal_wiring.py` exists and `main.py._connect_signals()` already delegates directly to `wire_all_signals(self)`. A quick check of `src/main.py` shows only a few remaining local `connect()` calls, and they are narrow one-off cases (dialog-local wiring and lazy timer setup), not broad app-level signal registration. Reframe this item as **verification and cleanup of residual inline connections**, not a new extraction project.

**Proposed Structure**:
- `src/core/app_signal_wiring.py` (already exists)
  - Contains all `_wire_*` functions.
- Keep in `main.py`:
  - Lifecycle ordering and high-level orchestration.

**Evaluation**:
- **Ease of Implementation**: 3/5 - Many callsites but clear boundaries exist.
- **Safety**: 3/5 - Signal ordering risk; mitigated with targeted tests.
- **Practicality**: 5/5 - Large maintainability gain.
- **Recommendation**: 5/5 - High-value split (if not yet complete).
- **Overall Score**: 4.00/5

**Priority**: Verify complete and trim residual inline connections

##### Opportunity 2: Extract dialog/action command handlers

**Proposed Structure**:
- New module: `src/core/dialog_action_handlers.py`
  - `_open_*` dialog methods and related post-apply handlers.

**Evaluation**:
- **Ease**: 4/5
- **Safety**: 4/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 4.00/5

**Priority**: High

---

### File: `src/gui/image_viewer.py`

**Location**: `src/gui/image_viewer.py`  
**Line Count**: 3057  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Class: `ImageViewer`
- Methods: ~50 with several very large event handlers (`mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`, `set_image`).

#### Logical Groupings
- Rendering and image state
- Interaction modes and input handling
- Zoom/pan/transform and viewport events
- Pixel inspection and magnifier
- Drag/drop and keyboard behavior

#### Dependencies
- **Depends on**: Qt graphics stack, PIL, numpy, debug/config utilities.
- **Depended upon by**: display, lifecycle, and controller modules across app.

#### Refactoring Opportunities

##### Opportunity 1: Split interaction handling into dedicated handlers

**Proposed Structure**:
- `src/gui/image_viewer_interaction.py` (mouse/keyboard/wheel logic)
- `src/gui/image_viewer_rendering.py` (set_image, fit/zoom, transforms)
- Keep `ImageViewer` as facade and state holder.

**Evaluation**:
- **Ease**: 2/5 - Complex shared state between handlers.
- **Safety**: 2/5 - High UX regression risk if event ordering changes.
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 3.00/5

**Priority**: Medium

##### Opportunity 2: Extract magnifier/pixel-info subsystem

**Proposed Structure**:
- `src/gui/image_viewer_magnifier.py` for zoomed pixel sampling, hover text, and magnifier widget state.
- Keep `ImageViewer` responsible for dispatching mouse events and owning shared viewport state.

**Reviewer note**: This is a better first extraction than full input-handler splitting. It has clearer boundaries, lower regression risk, and reduces `ImageViewer` size without disturbing core pan/zoom behavior.

**Evaluation**:
- **Ease**: 4/5
- **Safety**: 4/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 4.00/5

**Priority**: High

---

### File: `src/core/file_operations_handler.py`

**Location**: `src/core/file_operations_handler.py`  
**Line Count**: 1686  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Class: `FileOperationsHandler`
- Methods: 17
- Contains repeated progress callback implementations and similar workflows for open-file/open-folder/open-recent/open-paths.

#### Logical Groupings
- File/folder selection orchestration
- Loading and progress reporting
- Merge/organize logic
- First-slice selection policy

#### Refactoring Opportunities

##### Opportunity 1: Extract shared load pipeline

**Proposed Structure**:
- `src/core/loading_pipeline.py`
  - Centralized open-source agnostic load path with strategy flags.
- Keep thin public entry methods in handler.

**Evaluation**:
- **Ease**: 4/5
- **Safety**: 4/5
- **Practicality**: 5/5
- **Recommendation**: 5/5
- **Overall Score**: 4.50/5

**Priority**: High

---

### File: `src/core/slice_display_manager.py`

**Location**: `src/core/slice_display_manager.py`  
**Line Count**: 1578  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Class: `SliceDisplayManager`
- Methods: 18
- Notably large `display_slice` and projection/rendering flow.

#### Logical Groupings
- Context/state setup
- Projection generation
- Base slice display
- ROI/measurement/annotation redraws
- Slice navigation handlers

#### Refactoring Opportunities

##### Opportunity 1: Extract projection service

**Proposed Structure**:
- `src/core/projection_display_service.py` for projection-specific image creation and state.

**Evaluation**:
- **Ease**: 3/5
- **Safety**: 3/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 3.50/5

**Priority**: Medium

##### Opportunity 2: Extract overlay/annotation dispatch methods

**Evaluation**:
- **Ease**: 4/5
- **Safety**: 4/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 4.00/5

**Priority**: High

---

### File: `src/gui/overlay_manager.py`

**Location**: `src/gui/overlay_manager.py`  
**Line Count**: 1463  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Classes: `ViewportOverlayWidget`, `OverlayManager`
- Methods: 33
- Mixes text-generation policy with graphics item lifecycle.

#### Refactoring Opportunities

##### Opportunity 1: Separate overlay text composition from rendering

**Proposed Structure**:
- `src/gui/overlay_text_builder.py` for modality/privacy/timing text logic.
- Keep `OverlayManager` for scene/widget rendering only.

**Evaluation**:
- **Ease**: 4/5
- **Safety**: 4/5
- **Practicality**: 5/5
- **Recommendation**: 5/5
- **Overall Score**: 4.50/5

**Priority**: High

---

### File: `src/core/export_manager.py`

**Location**: `src/core/export_manager.py`  
**Line Count**: 1455  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Class: `ExportManager`
- Methods: 15
- Mixes format routing, DICOM projection synthesis, filesystem naming, and overlay rendering.

#### Refactoring Opportunities

##### Opportunity 1: Split export orchestration vs per-format writers

**Proposed Structure**:
- `src/core/export_writers/image_export_writer.py`
- `src/core/export_writers/csv_export_writer.py`
- `src/core/export_writers/excel_export_writer.py`
- Keep `ExportManager` as orchestrator only.

**Evaluation**:
- **Ease**: 3/5
- **Safety**: 3/5
- **Practicality**: 5/5
- **Recommendation**: 5/5
- **Overall Score**: 4.00/5

**Priority**: High

---

### File: `src/gui/main_window.py`

**Location**: `src/gui/main_window.py`  
**Line Count**: 1430  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Class: `MainWindow`
- Methods: 55
- Contains menu/toolbar build, theming, pane toggles, drag/drop, status, and UI event filters.

#### Refactoring Opportunities

##### Opportunity 1: Move UI construction blocks to builders

**Proposed Structure**:
- Keep existing `main_window_menu_builder.py` and add:
  - `main_window_toolbar_builder.py`
  - `main_window_status_builder.py`

**Evaluation**:
- **Ease**: 4/5
- **Safety**: 4/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 4.00/5

**Priority**: High

---

### File: `src/gui/dialogs/tag_export_dialog.py`

**Location**: `src/gui/dialogs/tag_export_dialog.py`  
**Line Count**: 1288  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Class: `TagExportDialog`
- Methods: 26
- Mixes UI concerns, tag analysis logic, file writing, and preset CRUD.

#### Refactoring Opportunities

##### Opportunity 1: Extract data analysis and write backends

**Proposed Structure**:
- `src/core/tag_export_analysis_service.py`
- `src/core/tag_export_writer.py`
- Keep dialog for interaction and validation only.

**Evaluation**:
- **Ease**: 4/5
- **Safety**: 4/5
- **Practicality**: 5/5
- **Recommendation**: 5/5
- **Overall Score**: 4.50/5

**Priority**: High

---

### File: `src/gui/series_navigator.py`

**Location**: `src/gui/series_navigator.py`  
**Line Count**: 1198  
**Exceeds Threshold**: Yes

#### Code Structure Inventory
- Classes: `StudyDivider`, `StudyLabel`, `SeriesThumbnail`, `SeriesNavigator`
- Methods: 39
- Combines rendering widgets, drag/drop interaction, list orchestration, and thumbnail generation.

#### Refactoring Opportunities

##### Opportunity 1: Extract thumbnail generation/cache logic

**Proposed Structure**:
- `src/gui/series_thumbnail_service.py`
- Navigator keeps selection and dispatch logic.

**Evaluation**:
- **Ease**: 4/5
- **Safety**: 4/5
- **Practicality**: 4/5
- **Recommendation**: 4/5
- **Overall Score**: 4.00/5

**Priority**: High

---

### Condensed Assessments (Remaining >750 LOC Files)

| File | Primary Refactor Opportunity | Ease | Safety | Practicality | Recommendation | Overall | Priority |
|------|------------------------------|------|--------|--------------|----------------|---------|----------|
| src/tools/annotation_manager.py | Split RT/Overlay parsing from scene item creation | 3 | 3 | 4 | 4 | 3.50 | Medium |
| src/tools/roi_manager.py | Separate ROI model/statistics from QGraphics item behaviors | 3 | 3 | 5 | 5 | 4.00 | High |
| src/gui/fusion_controls_widget.py | Extract status formatting + unit conversion helper | 4 | 4 | 4 | 4 | 4.00 | High |
| src/core/view_state_manager.py | Split WL state machine from zoom/transform tracking | 3 | 3 | 4 | 4 | 3.50 | Medium |
| src/utils/undo_redo.py | Partition command classes by domain module | 4 | 4 | 5 | 5 | 4.50 | High |
| src/core/subwindow_lifecycle_controller.py | Extract signal wiring from viewport/layout operations | 3 | 3 | 4 | 4 | 3.50 | Medium |
| src/gui/fusion_coordinator.py | Extract candidate detection/alignment status flow | 4 | 4 | 4 | 4 | 4.00 | High |
| src/core/file_series_loading_coordinator.py | Merge duplicate open-path wrappers + isolate assignment policy | 4 | 4 | 4 | 4 | 4.00 | High |
| src/gui/roi_coordinator.py | Extract ROI statistics/update pipeline | 4 | 4 | 4 | 4 | 4.00 | High |
| src/core/fusion_handler.py | Move spatial metadata extraction to utility/service module | 3 | 3 | 4 | 4 | 3.50 | Medium |
| src/gui/dialogs/quick_start_guide_dialog.py | Move long help-content HTML/text payload to resource file | 5 | 5 | 5 | 5 | 5.00 | High |
| src/gui/main_window_theme.py | Externalize stylesheet fragments into themed resource files | 5 | 5 | 5 | 5 | 5.00 | High |
| src/gui/dialogs/fusion_technical_doc_dialog.py | Move large technical document text to resource file | 5 | 5 | 5 | 5 | 5.00 | High |
| src/core/mpr_controller.py | Split async build flow from view activation/presentation logic | 3 | 3 | 4 | 4 | 3.50 | Medium |
| src/core/dicom_loader.py | Separate path filtering, validation, and load execution pipeline | 4 | 4 | 4 | 4 | 4.00 | High |

> **Reviewer note — `src/utils/undo_redo.py` expanded detail (Score: 4.50)**: This file contains 15 classes. `Command` (ABC), `UndoRedoManager`, and `CompositeCommand` form the core infrastructure and should stay in `undo_redo.py`. The remaining 12 concrete command classes partition cleanly into domain groups:
> - `src/utils/commands/roi_commands.py` — `ROICommand`, `ROIMoveCommand`
> - `src/utils/commands/measurement_commands.py` — `MeasurementCommand`, `MeasurementMoveCommand`
> - `src/utils/commands/annotation_commands.py` — `TextAnnotationCommand`, `ArrowAnnotationCommand`, `TextAnnotationEditCommand`, `TextAnnotationMoveCommand`, `ArrowAnnotationMoveCommand`
> - `src/utils/commands/crosshair_commands.py` — `CrosshairCommand`, `CrosshairMoveCommand`
> - `src/utils/commands/tag_commands.py` — `TagEditCommand`
>
> Import compatibility during transition: re-export all command classes from `undo_redo.py` via `from .commands.roi_commands import *` etc., so existing import sites require no changes. Keep the command modules together under `src/utils/commands/` to avoid scattering undo/redo infrastructure across feature packages.

---

## Prioritized Recommendations

### High Priority (Overall Score >= 4.0)
1. Break out common loading pipeline from `src/core/file_operations_handler.py` (Score: 4.50/5)
2. Separate text composition from rendering in `src/gui/overlay_manager.py` (Score: 4.50/5)
3. Split writer backends from `src/core/export_manager.py` orchestration (Score: 4.00/5)
4. Split tag analysis/writers from `src/gui/dialogs/tag_export_dialog.py` (Score: 4.50/5)
5. Partition command classes in `src/utils/undo_redo.py` by domain (Score: 4.50/5)
6. Externalize content-heavy dialogs/themes (`quick_start_guide_dialog.py`, `fusion_technical_doc_dialog.py`, `main_window_theme.py`) (Score: 5.00/5)
7. Continue decomposition of `src/main.py` by moving dialog command handlers; treat signal wiring as verify/cleanup work rather than a major pending split (Score: 4.00/5)

### Medium Priority (Overall Score 3.0-3.9)
1. Split interaction internals in `src/gui/image_viewer.py` (Score: 3.00/5)
2. Extract projection and annotation dispatch from `src/core/slice_display_manager.py` (Score: 3.50/5 to 4.00/5 depending on slice)
3. Separate MPR controller operational phases in `src/core/mpr_controller.py` (Score: 3.50/5)
4. Isolate lifecycle signal/viewport responsibilities in `src/core/subwindow_lifecycle_controller.py` (Score: 3.50/5)

### Low Priority (Overall Score < 3.0)
- None identified in this pass.

---

## Files Appropriate for Immediate Extraction (Fast Path)

> **Reviewer note**: The three files below were listed in an earlier draft of this section as "potentially acceptable in current form." That framing contradicts their 5.00/5 recommendation scores. They are retained here under a corrected heading: these are **not** deferred — they are the best place to start. The work is self-contained, low-risk, and builds the resource-file pattern that the theme and larger dialogs will later share.

The following files exceed 750 lines primarily because of embedded content payloads (stylesheets, HTML help text, technical documentation) rather than branching logic. Extracting the payload to `.qss`, `.html`, or `.md` resource files is low-risk, can be validated visually in isolation, and reduces the Python files to near-threshold or below:

- **`src/gui/main_window_theme.py`** (826 lines): large stylesheet payload; extract to `resources/themes/*.qss`.
- **`src/gui/dialogs/quick_start_guide_dialog.py`** (835 lines): help-content HTML/text; extract to `resources/help/quick_start_guide.html`.
- **`src/gui/dialogs/fusion_technical_doc_dialog.py`** (811 lines): embedded technical documentation; extract to `resources/help/fusion_technical_doc.html`.

Each extraction can be done independently in ~1–2 hours with zero impact on other modules.

---

## Implementation Plans

> The plans below are ordered for execution: Fast Path first (nearly zero risk), then Refactors 1–3 in any order (each is independent). Each plan provides enough detail to start immediately without additional design work.

---

### Fast Path: Resource Extraction (do first)

**Goal**: Reduce `main_window_theme.py`, `quick_start_guide_dialog.py`, and `fusion_technical_doc_dialog.py` below the 750-line threshold by externalizing embedded content to files under `resources/`.

#### A. `src/gui/main_window_theme.py` → `resources/themes/`

- [ ] Create `resources/themes/` directory
- [ ] Extract the dark-theme QSS string from `get_theme_stylesheet()` (lines ~43–381) to `resources/themes/dark.qss`
- [ ] Extract the light-theme QSS string (lines ~432–825) to `resources/themes/light.qss`
- [ ] Update `get_theme_stylesheet()` to load from file via `pathlib.Path(__file__).parent.parent.parent / "resources" / "themes" / f"{theme}.qss"` and apply `check_image_path` substitution before returning
- [ ] Verify both themes render correctly; run tests

#### B. `src/gui/dialogs/quick_start_guide_dialog.py` → `resources/help/`

- [ ] Create `resources/help/` directory
- [ ] Extract the help HTML/text payload to `resources/help/quick_start_guide.html`
- [ ] Update the dialog to load the file and pass to the widget (`QTextBrowser.setHtml()` or equivalent)
- [ ] Verify dialog content renders correctly; run tests

#### C. `src/gui/dialogs/fusion_technical_doc_dialog.py` → `resources/help/`

- [ ] Extract the technical documentation text to `resources/help/fusion_technical_doc.html`
- [ ] Update the dialog to load from file
- [ ] Verify dialog content renders correctly; run tests

---

### Refactor 1: `src/core/file_operations_handler.py` — Extract Shared Load Pipeline

**Target**: `src/core/loading_pipeline.py` | **Score**: 4.50/5

**Problem**: `open_files()`, `open_folder()`, `open_recent_file()`, and `open_paths()` each reproduce the same progress-reporting → DICOM loading → organizing → status-bar update pipeline, duplicating roughly 300 lines across four nearly-identical bodies.

- [ ] Identify the shared inner pipeline across all four `open_*` methods: progress dialog setup and cancellation, DICOM loader call, merge/organize through DICOM organizer, `_format_final_status()` / `_batch_counts_from_merge_result()` call, and return of `(studies, skipped_files)`
- [ ] Create `src/core/loading_pipeline.py`; move `_format_source_name()`, `_format_final_status()`, `_batch_counts_from_merge_result()`, and the shared pipeline body into a single `run_load_pipeline(paths, loader, organizer, progress_manager, ...) -> tuple[dict, dict]` function
- [ ] Rewrite each `open_*` method in `FileOperationsHandler` to perform its source-specific path selection (file dialog, folder dialog, recent path string, raw paths list), then call `run_load_pipeline()`
- [ ] Run full test suite; confirm all file-open paths exercise the new pipeline
- [ ] Validate: `file_operations_handler.py` should drop from 1686 to ~600–800 lines

---

### Refactor 2: `src/gui/overlay_manager.py` — Separate Text Composition

**Target**: `src/gui/overlay_text_builder.py` | **Score**: 4.50/5

**Problem**: `OverlayManager` composes DICOM tag text *and* manages Qt scene items *and* owns privacy/mode state. The text-composition methods have no Qt graphics dependency and are testable pure functions.

- [ ] Identify the composition boundary — the three methods with no Qt graphics dependency:
  - `get_overlay_text()` (line 464), `_get_modality()` (line 499), `_get_corner_text()` (line 514)
- [ ] Create `src/gui/overlay_text_builder.py`; move those three as module-level functions (drop `self`); accept `privacy_mode`, `mode`, `custom_fields`, `total_slices`, and `config_manager` as explicit arguments
- [ ] Update `OverlayManager` to import and delegate: `overlay_text_builder.get_overlay_text(...)`; remove the moved methods from the class
- [ ] Verify overlay text is visually correct for all four corners across different modalities after the change (load CT, MR, and PT series)
- [ ] Confirm privacy-mode blanking still works
- [ ] Run tests

---

### Refactor 3: `src/gui/dialogs/tag_export_dialog.py` — Extract Analysis and Write Backends

**Targets**: `src/core/tag_export_analysis_service.py`, `src/core/tag_export_writer.py` | **Score**: 4.50/5

**Problem**: `TagExportDialog` contains tag analysis logic, Excel/CSV file writing, filename generation, and all UI in one class. The analysis and writer code has no Qt dependency beyond a QDialog parent for error messages.

**`src/core/tag_export_analysis_service.py`**:
- [ ] Move `_analyze_tag_variations()` (line 621) as `analyze_tag_variations(studies, selected_series, selected_tags) -> dict`
- [ ] Keep `_show_variation_analysis_dialog()` (line 685) in the dialog — it creates Qt widgets

**`src/core/tag_export_writer.py`**:
- [ ] Move `_generate_default_filename()` (line 792) as `generate_default_filename(selected_series) -> str`
- [ ] Move `_write_excel_file()` (line 806) as `write_excel_file(file_path, variation_analysis, selected_tags) -> None`
- [ ] Move `_write_csv_files()` (line 932) as `write_csv_files(base_file_path, variation_analysis, selected_tags) -> list[Path]`

**In `TagExportDialog`**:
- [ ] Update `_export_to_excel()` (line 537) to call through to the new service and writer modules
- [ ] Remove moved methods; verify Excel and CSV export paths still work end-to-end
- [ ] Run tests
- [ ] Validate: `tag_export_dialog.py` from 1288 → ~800–900 lines; each new module ~200–300 lines

---

### Refactor 4: `src/main.py` — Extract Logic-Bearing Dialog Handlers

**Target**: `src/core/dialog_action_handlers.py` | Companion cleanup: `src/core/app_signal_wiring.py` | **Score**: 4.00/5

**Background**: `main.py` has 18 `_open_*` methods. Thirteen are already 1–3 line stubs delegating to `dialog_coordinator` or `_file_series_coordinator`. Five contain meaningful pre-delegation logic:

| Method | Line | Lines of logic | What it does before delegating |
|--------|------|----------------|-------------------------------|
| `_open_about_this_file()` | 1998 | ~20 | Reads `focused_subwindow_index`, builds `current_dataset` + `file_path` from `subwindow_data` |
| `_open_slice_sync_dialog()` | 2066 | ~13 | Creates `SliceSyncDialog` directly; contains the **line-2071 residual `connect()`** flagged in Opportunity 1 |
| `_open_overlay_config()` | 2163 | ~17 | Extracts and validates modality string from `current_dataset` against a valid-modalities list |
| `_open_quick_window_level()` | 2184 | ~23 | Reads `view_state_manager` + `window_level_controls`; creates `QuickWindowLevelDialog` inline |
| `_open_export()` | 2223 | ~34 | Aggregates state from 6+ managers (`view_state_manager`, `slice_display_manager`, `subwindow_managers`, `roi_manager`, `overlay_manager`, `measurement_tool`) |

**Step 1 — Move logic-bearing handlers (~90-line net saving; do this first):**

- [ ] Create `src/core/dialog_action_handlers.py`
- [ ] Move `_open_about_this_file()`, `_open_slice_sync_dialog()`, `_open_overlay_config()`, `_open_quick_window_level()`, and `_open_export()` as module-level functions; rename `self` → `app` throughout; move their local imports into the new module
- [ ] Replace each method body in `main.py` with a one-liner: `dialog_action_handlers.open_X(self)`
- [ ] Note: moving `_open_slice_sync_dialog` naturally resolves the line-2071 residual `connect()`; mark Opportunity 1 residual as cleared after this step
- [ ] Run tests; confirm all five dialogs open correctly

**Step 2 — Eliminate thin stub wrappers (~40 additional lines; do after Step 1 is stable):**

- [ ] For each 1-liner stub that purely delegates to `self.dialog_coordinator.*` (9 methods: `_open_settings`, `_open_overlay_settings`, `_open_tag_viewer`, `_open_annotation_options`, `_open_quick_start_guide`, `_open_fusion_technical_doc`, `_open_tag_export`, `_open_export_roi_statistics`, `_open_export_screenshots`): in `app_signal_wiring.py` rewire the signal directly to `self.dialog_coordinator.open_*`, then delete the stub from `main.py`
- [ ] For the 4 file-open stubs (`_open_files`, `_open_folder`, `_open_recent_file`, `_open_files_from_paths`): rewire signals directly to `self._file_series_coordinator.*`
- [ ] Run full test suite; validate no broken signal connections
- [ ] Expected net reduction: `main.py` from 3270 → ~3130 lines after both steps

---

## Observations and Patterns

- The codebase has strong domain segmentation (`core`, `gui`, `tools`), but several files are still acting as both orchestrator and implementation.
- Repeated patterns exist in file-loading workflows and callback scaffolding that can be centralized.
- Long GUI/dialog files often combine content payload + behavior; moving payloads to resource files gives immediate wins with low risk.
- Existing controller architecture is good foundation for incremental extraction without API breaks.

## Next Steps

- [ ] **Verify `app_signal_wiring.py` completion**: Confirm `main.py._connect_signals()` fully delegates to `wire_all_signals()` with no stray `connect()` calls in `_init_*` helpers. If complete, mark main.py Opportunity 1 as done and update `main.py`'s line count.
- [ ] **Quick Wins first** — extract the three content-heavy files to resource files (see "Files Appropriate for Immediate Extraction" above). Each is self-contained, can be verified visually, and establishes the resource-file pattern for future theme work.
- [ ] Review this prioritized list and select 1-3 high-priority targets for implementation phase.
- [ ] Create dedicated implementation plans per selected target with sequence and test checkpoints.
- [ ] Execute refactors incrementally (one module split at a time), validating after each step.
- [ ] Re-run this assessment after implementation to measure size/coupling reduction.

> **Scoring methodology note**: The "Recommendation" dimension (1–5) contributes to the Overall Score alongside Ease, Safety, and Practicality, but it is somewhat circular since the Overall Score itself drives the final recommendation. In future assessments, consider replacing "Recommendation" with "Impact" (business/maintainability value) to give the fourth dimension independent meaning.
