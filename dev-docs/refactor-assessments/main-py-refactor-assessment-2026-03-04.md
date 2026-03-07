# Refactor Assessment: src/main.py

**Document**: main-py-refactor-assessment-2026-03-04  
**Date**: 2026-03-04  
**Scope**: `src/main.py` only — ways to reduce line count safely and in a smart way.  
**Line count (current)**: 3,552 (Python threshold for concern: 600; project guideline: 500–1000).

---

## Purpose

This assessment focuses on **safe, incremental** refactors for `src/main.py` to bring its size down without breaking behavior. It does not change code; it documents opportunities, migration strategies, and rough impact so you can prioritize and implement in separate steps.

---

## Current Structure Summary

`DICOMViewerApp` is the top-level orchestrator. Initialization is already split into five ordered steps (`_init_core_managers`, `_init_main_window_and_layout`, `_init_controllers_and_tools`, `_init_view_widgets`, `_post_init_subwindows_and_handlers`). Metadata and ROI/measurement are already extracted into `MetadataController` and `ROIMeasurementController`.

**Largest contributors to line count:**

| Area | Approx. lines | Methods / notes |
|------|----------------|------------------|
| Per-subwindow manager creation | ~450 | `_initialize_subwindow_managers` (382–626), `_create_managers_for_subwindow` (627–832). **Heavy duplication** between the two. |
| Handler initialization | ~135 | `_initialize_handlers` (910–1043). Creates FileOperationsHandler, DialogCoordinator, MouseModeHandler, CinePlayer, KeyboardEventHandler. |
| Close/reset and file flow | ~230 | `_close_files` (1070–1171), `_clear_data`, `_on_app_about_to_quit`, `_reset_fusion_for_all_subwindows`, `_handle_load_first_slice`. |
| Signal wiring | ~90 | `_connect_signals` plus `_connect_layout_signals`, `_connect_file_signals`, etc. (1422–1513). Already split by feature; could be moved out of main.py. |
| Projection handlers | ~120 | `_on_projection_enabled_changed` (1854–1955), `_on_projection_type_changed`, `_on_projection_slice_count_changed`. |
| Customization / tag presets | ~200+ | `_on_export_customizations`, `_on_import_customizations`, `_on_export_tag_presets`, `_on_import_tag_presets`. Repeated pattern: path resolution → dialog → config I/O → message box. |
| Privacy/view toggles | ~100 | `_on_privacy_view_toggled` (2037–2081), `_refresh_overlays_after_privacy_change` (2097–2136). |
| UI assembly | ~75 | `_setup_ui` (1348–1421). |
| Many small methods | rest | Thin delegations to controllers/coordinators (good); a few medium-sized handlers. |

---

## Refactoring Opportunities

### 1. Deduplicate subwindow manager creation (single factory)

**Problem**: `_initialize_subwindow_managers` and `_create_managers_for_subwindow` both build the same set of managers (ROI, measurement, annotation, crosshair, overlay, view state, slice display, coordinators, fusion). The second method is missing CrosshairManager in one code path; otherwise the logic is duplicated (~245 + ~206 lines).

**Proposed structure**:
- Add a **single** helper that, given `(app, idx, subwindow)`, returns the `managers` dict (and optionally fills `subwindow_data[idx]`). For example:
  - `_build_managers_for_subwindow(self, idx: int, subwindow: SubWindowContainer) -> Dict` in `main.py`, **or**
  - Move creation into `SubwindowLifecycleController` as e.g. `create_managers_for_subwindow(app, idx, subwindow) -> dict`, with the controller calling back into app only for callbacks/lambdas that need app state.
- `_initialize_subwindow_managers` becomes: loop over subwindows, call the single builder, store in `subwindow_managers` / `subwindow_data`, then call `_connect_all_subwindow_transform_signals()`.
- `_create_managers_for_subwindow` becomes: call the same builder, store, and perform the few one-off steps (e.g. set pan mode, file path callback). No second copy of manager construction.

**Migration**:
1. Introduce the single builder; implement it by extracting the common logic from one of the two methods (prefer the more complete one, e.g. `_initialize_subwindow_managers` loop body).
2. Replace the loop in `_initialize_subwindow_managers` with calls to the builder.
3. Replace the body of `_create_managers_for_subwindow` with a call to the builder plus the one-off steps. Ensure CrosshairManager (and any other manager) is present in both code paths.
4. Run full test suite and manual smoke tests (open files, change layout, add ROI, etc.).

**Benefits**: Removes ~200+ lines of duplication, single place to fix bugs or add new per-subwindow managers.  
**Risks**: Medium — manager creation is critical; test layout changes and dynamic subwindow creation (e.g. 1x1 → 2x2) carefully.

**Evaluation**:
- **Ease of Implementation**: 3/5 — Straightforward extract, but two call sites and many lambdas/callbacks to pass correctly.
- **Safety**: 3/5 — High impact if wrong; mitigated by keeping logic identical and testing thoroughly.
- **Practicality**: 5/5 — One of the highest line-count wins and removes a major maintenance trap.
- **Recommendation**: 4/5 — Do early; unblocks cleaner lifecycle changes later.

**Overall Score**: 3.75/5 · **Priority: High**

---

### 2. Extract signal wiring to a dedicated module or class

**Problem**: `_connect_signals` and the `_connect_*` sub-methods (layout, file, dialog, undo/redo, cine, view, customization, subwindow, focused subwindow) live in `main.py` and tie the app to every signal source. They total ~90 lines of connection code; the rest of the “signal” area is layout/focus handlers.

**Proposed structure**:
- New module, e.g. `src/core/app_signal_wiring.py`, with a function or class that takes `app: DICOMViewerApp` and performs all `connect` calls. Optionally split by domain (e.g. `wire_layout_signals(app)`, `wire_file_signals(app)`) in the same module.
- `DICOMViewerApp._connect_signals()` becomes a single call, e.g. `wire_all_signals(self)` or `AppSignalWiring.wire(self)`.

**Migration**:
1. Add `app_signal_wiring.py`; move one `_connect_*` block from main.py into it (e.g. `_connect_layout_signals`) and call it from `_connect_signals`. Verify behavior.
2. Move remaining `_connect_*` bodies into the wiring module. Keep `_connect_signals()` in main.py as a thin dispatcher that calls the wiring API.
3. Optionally move layout/focus handlers that are only used by these connections (e.g. `_on_focused_subwindow_changed`, `_on_layout_changed`) into the wiring module or a small “layout focus” helper; if they need many app attributes, leaving them on the app is fine.

**Benefits**: Reduces main.py by ~80–100 lines; signal wiring is easier to find and test in isolation.  
**Risks**: Low if only connection code moves and handler implementations stay on the app.

**Evaluation**:
- **Ease of Implementation**: 4/5 — Mechanical move; clear boundary.
- **Safety**: 4/5 — No change to what is connected; only location of code.
- **Practicality**: 4/5 — Good maintainability win.
- **Recommendation**: 4/5 — Recommended.

**Overall Score**: 4.00/5 · **Priority: High**

---

### 3. Move customization and tag-preset handlers to a helper or coordinator

**Problem**: `_on_export_customizations`, `_on_import_customizations`, `_on_export_tag_presets`, `_on_import_tag_presets` follow the same pattern: resolve default path → file dialog → config I/O → success/failure message. They total 200+ lines and clutter main.py.

**Proposed structure**:
- Add a small helper module or class, e.g. `src/core/customization_handlers.py` or extend `DialogCoordinator` / a dedicated `CustomizationCoordinator`, that:
  - Takes `config_manager`, `main_window` (parent for dialogs), and any callbacks needed for “after import” (e.g. refresh overlay, theme, metadata column widths).
  - Exposes `export_customizations()`, `import_customizations()`, `export_tag_presets()`, `import_tag_presets()`.
- In main.py, keep only one-liner slots that call this helper (e.g. `_on_export_customizations` → `self._customization_handlers.export_customizations()`).

**Migration**:
1. Create the helper; implement one method (e.g. export customizations) and call it from main.py. Verify dialog, path, and message box behavior.
2. Move the other three methods; wire menu signals to the same thin slots.
3. Run tests and manual checks for import/export and tag presets.

**Benefits**: Removes ~150–200 lines from main.py; centralizes file-dialog and config-I/O patterns.  
**Risks**: Low; behavior is self-contained and easy to test.

**Evaluation**:
- **Ease of Implementation**: 4/5 — Clear extraction; “after import” callbacks need to be passed explicitly.
- **Safety**: 4/5 — Isolated; no change to core app lifecycle.
- **Practicality**: 4/5 — Good size reduction and clarity.
- **Recommendation**: 4/5 — Recommended.

**Overall Score**: 4.00/5 · **Priority: Medium–High**

---

### 4. Move projection handlers into SliceDisplayManager or a small projection handler

**Problem**: `_on_projection_enabled_changed` is long (~100 lines); `_on_projection_type_changed` and `_on_projection_slice_count_changed` are shorter. They all interact with slice display, rescaling, and UI state.

**Proposed structure**:
- **Option A**: Move the three handlers into `SliceDisplayManager` as public methods (e.g. `on_projection_enabled_changed(app, enabled)`), passing only what’s needed (e.g. app ref for status, config, or callbacks). Main.py then has thin slots that call the manager.
- **Option B**: Introduce a small `ProjectionEventHandler` in `core/` that holds a reference to `SliceDisplayManager`, `ViewStateManager`, and any other needed app attributes, and implements the three handlers. Main.py connects signals to this handler instead of to itself.

**Migration**:
1. Choose Option A or B; implement one handler (e.g. `_on_projection_type_changed`) in the new place and wire it from main.py. Verify projection behavior.
2. Move the other two; ensure rescale/projection state and UI stay in sync.
3. Test projection on/off, type change, slice count change, and series change.

**Benefits**: Removes ~100–120 lines from main.py; projection logic lives next to slice display.  
**Risks**: Moderate — projection and rescaling are subtle; test with different series and layouts.

**Evaluation**:
- **Ease of Implementation**: 3/5 — Handlers depend on several app pieces; need a clear contract (callbacks or minimal app ref).
- **Safety**: 3/5 — Behavior must remain identical; regression tests for projection are important.
- **Practicality**: 3/5 — Solid improvement; slightly more involved than customization extraction.
- **Recommendation**: 3/5 — Consider after 1–3.

**Overall Score**: 3.00/5 · **Priority: Medium**

---

### 5. Centralize privacy/view toggle logic (PrivacyController or helper)

**Problem**: Privacy mode is applied in `_init_core_managers` (flag), then in `_init_view_widgets` (overlay_manager), and in per-subwindow overlay managers; toggling and overlay refresh are in `_on_privacy_view_toggled` and `_refresh_overlays_after_privacy_change`. Logic is scattered.

**Proposed structure**:
- A small `PrivacyController` or `privacy_helper` that:
  - Holds or receives: config_manager, metadata_controller, and a way to iterate subwindow overlay managers (and crosshair managers if needed).
  - Exposes: `set_privacy(enabled: bool)`, and optionally `refresh_overlays_after_privacy_change()`.
- Main.py: `_on_privacy_view_toggled` and `_refresh_overlays_after_privacy_change` become thin wrappers; initial application of privacy in init can call the same API.

**Benefits**: Removes ~50–80 lines from main.py and groups all privacy behavior in one place.  
**Risks**: Low–medium; privacy is user-visible — test metadata panel, overlay text, and crosshairs.

**Evaluation**:
- **Ease of Implementation**: 3/5 — Need to gather all “set privacy” and “refresh overlay” call sites.
- **Safety**: 3/5 — Must not miss any overlay or metadata panel update.
- **Practicality**: 3/5 — Moderate win; improves clarity.
- **Recommendation**: 3/5 — Consider after higher-impact items.

**Overall Score**: 3.00/5 · **Priority: Low–Medium**

---

### 6. Move _setup_ui into MainWindow or a layout helper

**Problem**: `_setup_ui` (~75 lines) only assembles panels, tabs, and the multi-window layout; it does not contain business logic. It could live on `MainWindow` (e.g. `main_window.setup_content(app)`) or in a small `MainWindowLayoutHelper` that receives the app and adds widgets to the main window’s panels.

**Proposed structure**:
- `MainWindow.setup_content(self, app)` or `setup_main_layout(main_window, app)` in `gui/` that:
  - Takes the main window and app (or the specific widgets: multi_window_layout, cine_controls_widget, metadata_panel, tab widgets, series_navigator, etc.).
  - Performs the same layout adds and the window-slot map callback wiring.
- Main.py: `_setup_ui()` becomes a single call to that method.

**Benefits**: Removes ~70 lines from main.py; layout assembly is co-located with the window.  
**Risks**: Low; purely structural.

**Evaluation**:
- **Ease of Implementation**: 4/5 — Straightforward move.
- **Safety**: 5/5 — No behavior change.
- **Practicality**: 3/5 — Moderate line reduction; improves separation.
- **Recommendation**: 3/5 — Optional, after 1–3.

**Overall Score**: 3.75/5 · **Priority: Low**

---

## Prioritized Summary

| Priority | Opportunity | Est. line reduction | Score |
|----------|-------------|---------------------|-------|
| High | 1. Single subwindow manager factory (dedupe) | ~200+ | 3.75 |
| High | 2. Extract signal wiring to module | ~80–100 | 4.00 |
| Medium–High | 3. Customization / tag-preset handlers | ~150–200 | 4.00 |
| Medium | 4. Projection handlers to SliceDisplayManager or handler | ~100–120 | 3.00 |
| Low–Medium | 5. Privacy controller / helper | ~50–80 | 3.00 |
| Low | 6. _setup_ui to MainWindow or layout helper | ~70 | 3.75 |

Doing **1 + 2 + 3** first is a smart order: biggest duplication fix, then wiring, then customization. That could remove on the order of **430–500 lines** from main.py with manageable risk. After that, main.py would still be large (~3000 lines) but with less duplication and clearer boundaries; 4–6 can follow in a second phase.

---

## Detailed Implementation Plan (Opportunities 1–3)

Execute in order. After each opportunity: backup (if not already done), implement, run tests, commit, then proceed. Do not implement the next opportunity until the current one is complete and verified.

---

### Phase 1: Opportunity 1 — Single subwindow manager factory

**Goal**: One place that builds the per-subwindow `managers` dict; remove duplication between `_initialize_subwindow_managers` and `_create_managers_for_subwindow`.

#### Pre-work
- [x] Back up `src/main.py` to `backups/main.py` (or `backups/main_pre_subwindow_factory_YYYY-MM-DD.py`). Confirm backup exists and has content.
- [x] Run full test suite and record baseline (e.g. “all 90 tests pass”). Document any known flakiness.

#### Step 1.1: Add the single builder method
- [x] In `main.py`, add a new private method:  
  `_build_managers_for_subwindow(self, idx: int, subwindow: SubWindowContainer) -> Dict`
- [x] Implement it by copying the **loop body** from `_initialize_subwindow_managers` (the block that creates `managers` for one `(idx, subwindow)`). Use the version that includes **CrosshairManager** and **CrosshairCoordinator** so both code paths get the same set of managers.
- [x] Ensure all lambdas and callbacks use `idx` correctly (e.g. `lambda idx=idx: ...` where needed to avoid closure issues).
- [x] Do **not** yet remove or shorten `_initialize_subwindow_managers` or `_create_managers_for_subwindow`; only add the new method.
- [x] Run tests. Fix any issues (e.g. missing imports inside the new method if you moved any).

#### Step 1.2: Use the builder in _initialize_subwindow_managers
- [x] In `_initialize_subwindow_managers`, replace the inner loop body (that builds `managers` and fills `subwindow_data[idx]`) with:
  - Call `managers = self._build_managers_for_subwindow(idx, subwindow)`.
  - Store: `self.subwindow_managers[idx] = managers`.
  - Initialize: `self.subwindow_data[idx] = { 'current_dataset': None, 'current_slice_index': 0, 'current_series_uid': '', 'current_study_uid': '', 'current_datasets': [] }`.
- [x] Keep the rest of `_initialize_subwindow_managers` unchanged (scroll wheel mode, loop over subwindows, skip None subwindows, call `_connect_all_subwindow_transform_signals()` at the end).
- [x] Run full test suite. Manually: start app, open files, switch layouts (1x1, 2x2), add ROI, change slice. Confirm no regressions.
- [x] Commit (e.g. “refactor(main): use _build_managers_for_subwindow in _initialize_subwindow_managers”).

#### Step 1.3: Use the builder in _create_managers_for_subwindow
- [x] In `_create_managers_for_subwindow`, replace the entire manager-creation block with:
  - Call `managers = self._build_managers_for_subwindow(idx, subwindow)`.
  - Store: `self.subwindow_managers[idx] = managers`.
  - Initialize `self.subwindow_data[idx]` if `idx not in self.subwindow_data` (same dict as in Step 1.2).
  - Keep the one-off steps that are specific to “single subwindow” path: set scroll wheel mode, `set_smooth_when_zoomed_state`, set `image_viewer.get_file_path_callback`, set pan mode.
- [x] Ensure `_build_managers_for_subwindow` is used for **both** initial bulk creation and dynamic creation from `SubwindowLifecycleController`; confirm `SubwindowLifecycleController` still calls `app._create_managers_for_subwindow(idx, subwindow)` and that that method now delegates to the builder.
- [x] Run full test suite. Manually: open files, change layout from 2x2 to 1x1 and back, trigger creation of a new subwindow (e.g. 1x1 → 2x1), add ROI in each pane. Verify crosshair and overlay in both code paths.
- [x] Commit (e.g. “refactor(main): dedupe subwindow manager creation via _build_managers_for_subwindow”).

#### Step 1.4: Cleanup and final check
- [x] Remove any dead code or duplicated comments left in `_initialize_subwindow_managers` or `_create_managers_for_subwindow`.
- [x] Run tests again. Update changelog: note refactor (no user-facing behavior change). Bump version if per project policy (e.g. patch).
- [x] Mark Opportunity 1 complete in this document (optional checklist at end of plan).

---

### Phase 2: Opportunity 2 — Extract signal wiring to a dedicated module

**Goal**: Move all `_connect_*` logic from `main.py` into `src/core/app_signal_wiring.py`; `_connect_signals()` in main.py becomes a thin dispatcher.

#### Pre-work
- [x] Back up `src/main.py` to `backups/` (e.g. `main_pre_signal_wiring_YYYY-MM-DD.py`). Confirm backup.
- [x] Run tests; ensure baseline is green after Opportunity 1.

#### Step 2.1: Create wiring module and move first block
- [x] Create `src/core/app_signal_wiring.py` with module docstring (purpose: connect all Qt signals for DICOMViewerApp; takes `app` and wires layout, file, dialog, etc.).
- [x] Add a function, e.g. `wire_all_signals(app: "DICOMViewerApp") -> None`, that will eventually call all sub-functions. For now, implement only **layout** wiring:
  - Move the body of `_connect_layout_signals` from main.py into a function e.g. `_wire_layout_signals(app)` in the new module (connect `multi_window_layout.focused_subwindow_changed`, `layout_changed`; `main_window.layout_changed`).
  - In main.py, replace the body of `_connect_layout_signals` with a call to the new function (e.g. `from core.app_signal_wiring import wire_layout_signals` then `wire_layout_signals(self)`). Keep `_connect_signals()` calling `self._connect_layout_signals()` so call order is unchanged.
- [x] Run tests. Manually: change layout, change focus; confirm layout and focus still work.
- [x] Commit (e.g. “refactor(signals): add app_signal_wiring, move layout signals”).

#### Step 2.2: Move remaining _connect_* bodies
- [x] In `app_signal_wiring.py`, add functions (or a single class with static methods) for: file, dialog, undo/redo+annotation, cine, view, customization. Move each corresponding block from main.py into the new module. Each function receives `app` and performs the same `app.xxx.connect(app._on_yyy)` (or equivalent) calls. Handlers remain methods on `DICOMViewerApp`; only the **connection** code moves.
- [x] In main.py, replace each `_connect_*` method body with a single call to the wiring module (e.g. `wire_file_signals(self)`). Preserve the order of calls in `_connect_signals()` (layout → file → dialog → undo/redo → cine → view → customization → subwindow → focused subwindow).
- [x] Add wiring for subwindow and focused-subwindow: move the logic that calls `_subwindow_lifecycle_controller.connect_subwindow_signals()` and `connect_focused_subwindow_signals()` into the wiring module (e.g. `wire_subwindow_signals(app)`, `wire_focused_subwindow_signals(app)`), or keep those two as one-liners in main.py that call the controller — either way, the **call** to them can be from the wiring module’s `wire_all_signals(app)` so that main.py’s `_connect_signals` is just one line: `wire_all_signals(self)`.
- [x] Run full test suite. Manually: open/close files, open dialogs (settings, overlay, tag viewer, export), cine, privacy toggle, layout/focus, subwindow-specific actions. Confirm all signals still fire correctly.
- [x] Commit (e.g. “refactor(signals): move all app signal wiring to app_signal_wiring.py”).

#### Step 2.3: Thin out main.py _connect_signals
- [x] Simplify `_connect_signals()` to a single call: `wire_all_signals(self)`. Remove the now-redundant `_connect_layout_signals`, `_connect_file_signals`, etc. from main.py (their bodies are in the wiring module; the dispatcher can be removed so that `_connect_signals` only invokes `wire_all_signals(self)`).
- [x] Run tests again. Update changelog; bump version if needed. Mark Opportunity 2 complete.

---

### Phase 3: Opportunity 3 — Customization and tag-preset handlers

**Goal**: Move `_on_export_customizations`, `_on_import_customizations`, `_on_export_tag_presets`, `_on_import_tag_presets` into a helper (e.g. `src/core/customization_handlers.py`); main.py keeps only thin slots that call the helper.

#### Pre-work
- [x] Back up `src/main.py` to `backups/` (e.g. `main_pre_customization_handlers_YYYY-MM-DD.py`). Confirm backup.
- [x] Run tests; ensure baseline is green after Opportunity 2.

#### Step 3.1: Create helper and move export customizations
- [x] Create `src/core/customization_handlers.py` with a class or set of functions that will handle export/import customizations and export/import tag presets. The helper needs: `config_manager`, `main_window` (parent for dialogs), and for import customizations: callbacks for “after import” (e.g. refresh overlay, apply theme, update metadata panel column widths, annotation options). Design the constructor or function signature so main.py can pass these in.
- [x] Implement `export_customizations()` in the helper: resolve default path (last export path or cwd), file save dialog, `config_manager.export_customizations(file_path)`, update last export path, show success/failure message. Match current behavior of `_on_export_customizations` exactly.
- [x] In main.py, replace the body of `_on_export_customizations` with a call to the helper (e.g. `self._customization_handlers.export_customizations()`). Create the helper in `_initialize_handlers` (or earlier if it has no dependency on handlers) and store as `self._customization_handlers`.
- [x] Run tests. Manually: Export Customizations, choose path, confirm file is created and message shown. Commit (e.g. “refactor(main): extract export customizations to customization_handlers”).

#### Step 3.2: Move import customizations
- [x] Implement `import_customizations()` in the helper: resolve path, file open dialog, `config_manager.import_customizations(file_path)`. On success: apply overlay font size/color, call “overlay config applied” callback, call “annotation options applied” callback, apply theme, update metadata panel column widths, show success message. On failure: show failure message. Pass in the necessary callbacks from main.py (e.g. `overlay_coordinator.handle_overlay_config_applied`, a method that triggers `_on_annotation_options_applied`, `main_window._set_theme`, and metadata panel column width update).
- [x] In main.py, replace the body of `_on_import_customizations` with a call to the helper’s `import_customizations()`.
- [x] Run tests. Manually: Import Customizations from a known-good export file; confirm overlay, theme, metadata columns, and annotations update. Commit.

#### Step 3.3: Move export and import tag presets
- [x] Implement `export_tag_presets()` in the helper: get presets via `config_manager.get_tag_export_presets()`; if empty, show “No Tag Presets” message and return. Otherwise resolve path, file save dialog, `config_manager.export_tag_export_presets(file_path)`, update last export path, show success/failure message.
- [x] Implement `import_tag_presets()` in the helper: resolve path, file open dialog, `config_manager.import_tag_export_presets(file_path)`; show success/failure message. If you have UI that must refresh after import (e.g. tag export dialog), pass a callback and call it after successful import.
- [x] In main.py, replace the bodies of `_on_export_tag_presets` and `_on_import_tag_presets` with calls to the helper.
- [x] Run full test suite. Manually: export/import customizations and export/import tag presets. Confirm dialogs, paths, and messages match previous behavior.
- [x] Commit (e.g. “refactor(main): extract customization and tag-preset handlers to customization_handlers”). Update changelog; mark Opportunity 3 complete.

---

### Post–Phase 3: Verification

- [x] Run full test suite (with timeout if applicable). All tests must pass.
- [x] Manual smoke test: start app, open files, switch layouts and focus, open/close dialogs, export/import customizations and tag presets, toggle privacy, use cine and projection. No regressions.
- [x] Re-run line count on `src/main.py`. Expect a reduction on the order of 430–500 lines from the start of the plan. Record the new line count in this document or in a follow-up note. **Post–1–3 count: 3,024 lines** (reduced from 3,552; –528 lines).

---

## Evaluation Step for Opportunities 4–6

After Opportunities 1–3 are fully implemented and committed, perform a short evaluation before implementing 4, 5, or 6.

### Objectives
- Decide whether to implement opportunities 4 (projection handlers), 5 (privacy controller), and 6 (_setup_ui) and in what order, if at all.
- Base the decision on: current main.py line count, remaining pain points, test coverage, and available time.

### Steps

1. **Re-measure and document**
   - Run line count on `src/main.py` (excluding backups). Record the value.
   - Note how much was reduced by 1–3 (e.g. “reduced from ~3552 to ~3050”).

2. **Re-read the assessment for 4–6**
   - Opportunity 4 (projection): ~100–120 lines; moderate risk; improves cohesion with SliceDisplayManager.
   - Opportunity 5 (privacy): ~50–80 lines; low–medium risk; centralizes privacy logic.
   - Opportunity 6 (_setup_ui): ~70 lines; low risk; moves layout assembly to MainWindow or helper.

3. **Decide**
   - If main.py is still above your target (e.g. 1000 lines), consider implementing 4, 5, and 6 in order of priority (4 → 5 → 6) or by risk (6 → 5 → 4 if you prefer the safest first).
   - If main.py is at or below target, you may defer 4–6 or do only one (e.g. 6 for clarity) as a follow-up.
   - If you have projection or privacy bugs in the backlog, favor 4 or 5 to get logic into a single place.

4. **Document the decision**
   - In this file (below) or in a short follow-up note (e.g. “Evaluation 4–6, YYYY-MM-DD”):
     - Record: “Post–1–3 main.py line count: N.”
     - Record: “Decision: [Implement 4 / 5 / 6 in order X] or [Defer 4–6] or [Implement only N].”
     - Optionally: “Rationale: …”

5. **If implementing 4–6**
   - For each chosen opportunity, follow the same discipline: backup main.py, implement incrementally, run tests and manual checks, commit, then proceed. Use the “Migration” and “Proposed structure” text in the assessment (sections 4, 5, 6) as the implementation guide. Add a short “Phase 4 / 5 / 6” plan in this document if you want a step-by-step checklist similar to 1–3.

---

## Evaluation Step Result (2026-03-04)

- **Post–1–3 main.py line count**: 3,024 lines.
- **Reduction from start**: ~528 lines (from 3,552).
- **Decision**: Implement Opportunity 6 first (lowest risk, purely structural), then Opportunity 5 (privacy controller, low–medium risk). Opportunity 4 (projection handlers) deferred; no projection bugs in backlog and the remaining wins from 5 and 6 alone are meaningful.
- **Order**: Phase 6 → Phase 5.

---

## Detailed Implementation Plan (Opportunities 5–6)

Execute in order. After each phase: backup, implement, run tests, commit, then proceed.

---

### Phase 6: Opportunity 6 — Move _setup_ui to a layout helper

**Goal**: Extract the body of `_setup_ui` (~73 lines) from `main.py` into a standalone helper function in `src/gui/main_window_layout_helper.py`. `_setup_ui` in main.py becomes a single call to that function. No behavior change.

**What the function receives**: `main_window`, and the widgets it places — `multi_window_layout`, `cine_controls_widget`, `metadata_panel`, `window_level_controls`, `zoom_display_widget`, `roi_list_panel`, `roi_statistics_panel`, `intensity_projection_controls_widget`, `fusion_controls_widget`, `series_navigator`, plus the callbacks needed for the window-slot map wiring (`get_slot_to_view`, `get_layout_mode`, `get_focused_view_index`, `get_thumbnail_for_view`).

**Why a free function rather than `MainWindow.setup_content(app)`**: Avoids giving `MainWindow` a dependency on `DICOMViewerApp`; all necessary widgets are explicit parameters, keeping the helper independently testable.

#### Pre-work
- [x] Back up `src/main.py` to `backups/main_pre_setup_ui_YYYY-MM-DD.py`. Confirm backup.

#### Step 6.1: Create the helper and move _setup_ui body
- [x] Create `src/gui/main_window_layout_helper.py` with module docstring (purpose: assemble the main-window panel layout; called once from `DICOMViewerApp._setup_ui`).
- [x] Add a single public function:  
  ```python
  def setup_main_window_content(
      main_window,
      multi_window_layout,
      cine_controls_widget,
      metadata_panel,
      window_level_controls,
      zoom_display_widget,
      roi_list_panel,
      roi_statistics_panel,
      intensity_projection_controls_widget,
      fusion_controls_widget,
      series_navigator,
      *,
      get_slot_to_view,
      get_layout_mode,
      get_focused_view_index,
      get_thumbnail_for_view,
  ) -> None:
  ```
- [x] Copy the full body of `_setup_ui` (center panel, left panel, right panel with two tabs, series navigator, window-slot map callbacks and visibility) into this function, replacing `self.xxx` with the corresponding parameter names. The `QVBoxLayout`, `QTabWidget`, and `QWidget` imports should be local inside the function (matching the current pattern in `_setup_ui`).
- [x] Do **not** yet change `main.py`; only add the new file.
- [x] Verify the new file has no syntax or lint errors (`python -m py_compile src/gui/main_window_layout_helper.py`).

#### Step 6.2: Thin out _setup_ui in main.py
- [x] In `main.py`, add the import:  
  `from gui.main_window_layout_helper import setup_main_window_content`
- [x] Replace the body of `_setup_ui` with a single call:
  ```python
  def _setup_ui(self) -> None:
      """Assemble main-window panel layout. Implemented in gui.main_window_layout_helper."""
      setup_main_window_content(
          self.main_window,
          self.multi_window_layout,
          self.cine_controls_widget,
          self.metadata_panel,
          self.window_level_controls,
          self.zoom_display_widget,
          self.roi_list_panel,
          self.roi_statistics_panel,
          self.intensity_projection_controls_widget,
          self.fusion_controls_widget,
          self.series_navigator,
          get_slot_to_view=self.multi_window_layout.get_slot_to_view,
          get_layout_mode=self.multi_window_layout.get_layout_mode,
          get_focused_view_index=self.get_focused_subwindow_index,
          get_thumbnail_for_view=self._get_thumbnail_for_view,
      )
  ```
- [x] Run full test suite. Manually: start app, open a file, confirm panels (left/center/right), cine controls, metadata panel, tabs (Window/Zoom/ROI and Combine/Fuse), series navigator, and window-slot map thumbnail all display correctly. Confirm layout switch (1x1, 2x2).
- [x] Update changelog. Commit (e.g. `refactor(main): move _setup_ui body to main_window_layout_helper`). Mark Opportunity 6 complete.

---

### Phase 5: Opportunity 5 — Privacy controller

**Goal**: Extract `_on_privacy_view_toggled` and `_refresh_overlays_after_privacy_change` from `main.py` into `src/core/privacy_controller.py`. main.py keeps thin slots that delegate to the controller. `self.privacy_view_enabled` stays on `DICOMViewerApp` as the authoritative boolean (it is read in many places).

**What the controller receives**:
- `config_manager` — to persist and load the privacy flag.
- `metadata_controller` — to call `set_privacy_mode(enabled)`.
- `overlay_manager` — the shared (focused) overlay manager.
- `get_subwindow_managers` — a callable returning the `subwindow_managers` dict (so the controller stays up-to-date without holding a stale reference).
- `get_all_subwindows` — a callable (e.g. `multi_window_layout.get_all_subwindows`).
- `get_focused_subwindow_index` — callable returning the current focused index.

**What the controller exposes**:
- `apply_privacy(enabled: bool)` — full propagation: metadata_controller, shared overlay_manager, all per-subwindow overlay/crosshair managers, all image-viewer states; then calls `refresh_overlays()`.
- `refresh_overlays()` — loops all subwindows with loaded data and calls `slice_display_manager.display_slice(...)` (falling back to `create_overlay_items` on exception), using `update_metadata=(idx == get_focused_subwindow_index())`.

In `main.py`:
- `_on_privacy_view_toggled(enabled)` → sets `self.privacy_view_enabled = enabled` then calls `self._privacy_controller.apply_privacy(enabled)`.
- `_refresh_overlays_after_privacy_change()` → calls `self._privacy_controller.refresh_overlays()`.

#### Pre-work
- [x] Back up `src/main.py` to `backups/main_pre_privacy_controller_YYYY-MM-DD.py`. Confirm backup.
- [x] Run full test suite; confirm all tests pass (baseline after Phase 6).

#### Step 5.1: Create PrivacyController and implement apply_privacy
- [x] Create `src/core/privacy_controller.py` with module docstring (purpose: owns privacy-mode propagation; called from `DICOMViewerApp._on_privacy_view_toggled`).
- [x] Implement `PrivacyController.__init__` accepting `config_manager`, `metadata_controller`, `overlay_manager`, `get_subwindow_managers`, `get_all_subwindows`, `get_focused_subwindow_index`.
- [x] Implement `apply_privacy(self, enabled: bool) -> None`:
  - Call `self._metadata_controller.set_privacy_mode(enabled)` (guard with `hasattr` check as in current code).
  - Call `self._overlay_manager.set_privacy_mode(enabled)` (guard).
  - Iterate `self._get_subwindow_managers()` items; for each manager dict set `overlay_manager.set_privacy_mode(enabled)` and `crosshair_manager.set_privacy_mode(enabled)` (guard each).
  - Iterate `self._get_all_subwindows()`; for each non-None subwindow call `subwindow.image_viewer.set_privacy_view_state(enabled)`.
  - Call `self.refresh_overlays()`.
- [x] Do **not** yet change `main.py`. Run `python -m py_compile src/core/privacy_controller.py`.

#### Step 5.2: Implement refresh_overlays
- [x] Implement `refresh_overlays(self) -> None` in `PrivacyController`: copy the full logic of `_refresh_overlays_after_privacy_change` from `main.py` — enumerate all subwindows, skip those without loaded data, call `slice_display_manager.display_slice(...)` with `update_metadata=(idx == self._get_focused_subwindow_index())`, fall back to `create_overlay_items` on exception (using a local `DICOMParser` import inside the method, matching the current `from core.dicom_parser import DICOMParser` inline import).
- [x] Run `python -m py_compile src/core/privacy_controller.py`. No lint errors.

#### Step 5.3: Wire PrivacyController in main.py
- [x] In `main.py`, add import: `from core.privacy_controller import PrivacyController`.
- [x] In `_initialize_handlers` (after `dialog_coordinator` is created, when `overlay_manager`, `metadata_controller`, `multi_window_layout` are available), instantiate:
  ```python
  self._privacy_controller = PrivacyController(
      config_manager=self.config_manager,
      metadata_controller=self.metadata_controller,
      overlay_manager=self.overlay_manager,
      get_subwindow_managers=lambda: self.subwindow_managers,
      get_all_subwindows=self.multi_window_layout.get_all_subwindows,
      get_focused_subwindow_index=self.get_focused_subwindow_index,
  )
  ```
- [x] Replace the body of `_on_privacy_view_toggled` with:
  ```python
  self.privacy_view_enabled = enabled
  self._privacy_controller.apply_privacy(enabled)
  ```
- [x] Replace the body of `_refresh_overlays_after_privacy_change` with:
  ```python
  self._privacy_controller.refresh_overlays()
  ```
- [x] Run full test suite. Manually: toggle privacy mode (enable and disable); confirm overlay text hides/shows patient tags, metadata panel hides/shows patient fields, crosshairs remain fully visible in both modes, all four panes update when in 2x2 layout. Re-enable and re-disable to confirm no state residue.
- [x] Update changelog. Commit (e.g. `refactor(main): extract privacy propagation to PrivacyController`). Mark Opportunity 5 complete.

---

### Post–Phase 5–6: Verification

- [ ] Run full test suite. All tests must pass.
- [ ] Manual smoke test: start app, open files in multiple panes; toggle privacy on/off; export/import customizations; switch layouts; use cine; check all four tabs in right panel; verify window-slot map thumbnail.
- [ ] Re-run line count on `src/main.py`. Record here: **Post–5–6 count: ___**.
- [ ] Review `src/main.py` against opportunities 4 (projection) and any new candidates. Document decision on opportunity 4 or defer.

---

## Safety and process notes

- **No code changes in this assessment** — only this document was added.
- **Back up** `src/main.py` (e.g. to `backups/`) before implementing any refactor (per project rules).
- **Run the full test suite** after each extraction; fix any failing tests before moving on.
- **One refactor at a time** — implement, test, commit, then proceed.
- **Changelog / versioning**: Treat extractions as refactors; patch or minor bump per semantic versioning once behavior is unchanged and tests pass.

---

## References

- Existing refactor assessments in this folder (e.g. `refactor-assessment-2026-03-03-160000.md`) for prior main.py and SignalRouter/PrivacyController ideas.
- `AGENTS.md` for initialization order and controller responsibilities.
- Project rule: keep files under 500–1000 lines where possible; main.py is the primary outlier.
