# Refactor Plan: Split main.py into Multiple Files

**Created:** 2026-08-07  
**Status:** Draft  
**Target:** `src/main.py` (2494 lines → 4 files ≤750 lines each)

## Summary

The `src/main.py` file is currently the largest in the codebase at 2494 lines and is grandfathered in the line complexity hook. This plan outlines a phased approach to split it into 4 files each under the 750-line threshold while maintaining functionality, test coverage, and docstring quality.

## Current State Analysis

### File Structure
- **Location:** `src/main.py`
- **Lines:** 2494 (grandfathered at 2494 in `scripts/line_complexity_grandfather.json`)
- **Components:**
  - Module docstring + imports (lines 1-260)
  - `DICOMViewerApp(QObject)` class (lines 261-2430) with **239 method definitions** (verified via `grep -cE "    def "`; the bulk are private `_`-prefixed methods)
  - Module-level functions: `exception_hook` (2431), `install_application_privacy_boundaries` (2454), `main` (2472)

### Method Groupings in DICOMViewerApp
The class contains methods that fall into logical categories. The counts below are **approximate/illustrative**; the authoritative, complete method→file mapping is generated in Phase 1 (see Phase 1, Task 5 / Appendix A) and replaces the `etc.` placeholders in later phases.

1. **Initialization (4 `_init_*`-prefixed + 2 setup methods):** `__init__`, `_init_core_managers`, `_init_main_window_and_layout`, `_init_view_widgets`, `_post_init_subwindows_and_handlers`, `_init_controllers_and_tools`, `_initialize_handlers`, `_setup_ui`, `_connect_signals` (note: only 4 methods carry the `_init_` prefix; the rest are setup/orchestration methods).
2. **Subwindow Management (25 methods):** `_build_managers_for_subwindow`, `_initialize_subwindow_managers`, `_get_subwindow_dataset`, `_get_subwindow_slice_index`, etc.
3. **MPR Navigation (15 methods):** `_update_mpr_navigator_thumbnail`, `_clear_mpr_navigator_thumbnail`, `_on_mpr_detached`, `_on_mpr_thumbnail_clicked`, etc.
4. **File Operations (10 methods):** `_open_files`, `_open_folder`, `_open_recent_file`, `_open_files_from_paths`, etc.
5. **UI Signal Handlers (30 methods):** `_on_focused_subwindow_changed`, `_on_layout_changed`, `_on_privacy_view_toggled`, etc.
6. **Tag Editing (8 methods):** `_update_tag_viewer`, `_on_tag_edited`, `_undo_tag_edit`, `_redo_tag_edit`, etc.
7. **ROI/Measurement (5 methods):** `_display_rois_for_subwindow`, `_update_roi_list`, `_keyboard_delete_roi`, etc.
8. **Display/Projection (10 methods):** `_display_slice`, `_redisplay_current_slice`, `_on_projection_enabled_changed`, etc.
9. **Privacy/Settings (15 methods):** `_on_privacy_view_toggled`, `_on_slice_sync_toggled`, `_open_settings`, etc.
10. **Layout Management (10 methods):** `_on_layout_change_requested`, `_on_expand_to_1x1_requested`, `_on_swap_view_requested`, etc.

### Existing Test Coverage
- `tests/test_main_privacy_lifecycle.py` - Privacy boundary lifecycle
- `tests/test_main_signals_view.py` - Signal wiring tests
- `tests/test_main_window_fullscreen.py` - Fullscreen behavior
- `tests/test_main_window_status_controller.py` - Status bar
- `tests/test_main_window_theme.py` - Theme application
- `tests/test_main_window_toast.py` - Toast notifications

## Hook Configuration & Complexity Measurement

### How complexity is measured
Complexity is measured by **Lizard** (`lizard>=1.23.0`, from `requirements-dev.txt`), invoked by the pre-commit hook `scripts/git_hook_line_complexity.py`. The hook analyzes each staged file for:
- **Line count:** `WARN_LINES = 600`, `BLOCK_LINES = 750` (file length)
- **Function cyclomatic complexity (CCN):** `BLOCK_CCN = 20` (per-function; any function exceeding CCN 20 blocks the commit)

Lizard is run via `lizard.analyze_file.analyze_source_code(...)`. To measure ad hoc:
```bash
lizard src/main.py                       # full CCN/length report for one file
lizard --CCN 20 src/main_app_*.py        # list only functions at/above CCN 20
python scripts/git_hook_line_complexity.py --all   # repo-wide line + CCN check
```

### Grandfather model (important for this refactor)
The allowlist `scripts/line_complexity_grandfather.json` has two maps:
- `files`: `path -> line_count` (currently `src/main.py: 2494`). Removing `src/main.py` here in Phase 5 means its new length is subject to `BLOCK_LINES = 750` — but the file is being *shrunk*, so this is fine.
- `functions`: `path::name -> CCN` (67 entries today; **zero** for `src/main.py`). A function is allowed only while its CCN is at or below the recorded cap; the hook **auto-ratchets the cap down** when a function improves, and **blocks** any growth past the recorded cap.

**Critical implication:** `src/main.py` currently has **no** grandfathered high-CCN functions. When methods are moved into the new mixin files, their CCN travels with them. Any moved method whose CCN exceeds 20 will **immediately block the commit** in the new file. Therefore complexity reduction cannot be deferred to a separate later effort — it must be done **as each method is extracted** (see Phase 6). This is why Phase 6 is part of this plan rather than a separate plan.

Current grandfather status: `src/main.py` file entry = 2494; `functions` entries for `src/main.py` = 0.

## Refactoring Strategy

### Approach: Mixin-Based Decomposition (plain mixins, single QObject base)

To avoid circular dependencies and maintain the single `DICOMViewerApp` class, we'll use Python mixins. **Critical constraint:** `DICOMViewerApp` already inherits `QObject` (`src/main.py:261`, and `src/main.py:326` calls `super().__init__()` as the first statement). PySide6 forbids two `QObject` bases, so the mixins must be **plain classes that do NOT inherit `QObject`** — matching the repo's existing mixin convention (`src/utils/config/display_config.py:24` `DisplayConfigMixin`, `paths_config.py`, `layout_config.py`, etc., which are plain `class XMixin:` and access shared state via `getattr(self, ...)`).

Composition model:

1. Keep `DICOMViewerApp` in `src/main.py` as the main class, with `QObject` as its **sole** Qt base.
2. Extract method groups into **plain mixin classes** (no `QObject` base) in separate files.
3. Compose via multiple inheritance: `class DICOMViewerApp(QObject, InitializationMixin, SubwindowManagementMixin, MPRNavigationMixin, UIHandlersMixin, FileOperationsMixin, DisplayProjectionMixin, SettingsLayoutMixin, TagEditingMixin, ROIWorkflowMixin):`. Python C3 linearization resolves bases **left-to-right, so earlier-listed bases take precedence** — i.e. a method defined in `InitializationMixin` overrides the same method in a later-listed mixin. Document this override precedence explicitly (Appendix A lists which mixin owns each method, so collisions are intentional/known).
4. Each mixin file stays under 750 lines. Because 4 files × 750 = 3000 leaves no margin for duplicated structure (imports, module docstrings, class declarations) and the mandated docstrings, target **5 mixin files + `main.py`** (see Target File Structure). If any single mixin still exceeds 750 after extraction, split it further (e.g. separate `TagEditingMixin` / `ROIWorkflowMixin`).
5. **`Signal` declarations cannot move to plain mixins.** PySide6 requires `Signal` instances to be class attributes on a `QObject` subclass. `src/main.py` declares exactly one (`tag_export_union_ready = Signal(int, object)` at line 269); it must remain on `DICOMViewerApp` in `src/main.py`. Mixins connect to / emit it via `self.tag_export_union_ready` but never declare it.
6. **Typing across mixins:** mixin methods reference `self.layout`, `self.study_cache`, etc. To satisfy Pyright without a runtime circular import, each mixin file uses `if TYPE_CHECKING:` to import `DICOMViewerApp` and annotates `self: "DICOMViewerApp"` on methods that touch shared state. Add `pyright src/` to the verification commands.
7. Shared/cross-mixin state is accessed through explicit accessor helpers (following `DisplayConfigMixin._config()`/`_save_config()`) where it reduces risk, but a full rewrite of every `self.attribute` into `self._get_attribute()` across all 239 methods is **out of scope** (see Risk Assessment, State/Cross-Mixin Dependencies). Methods may read `self.<attr>` directly as long as init ordering guarantees the attribute exists; accessor helpers are used only for the highest-churn shared state.

### Target File Structure (5 mixin files + main.py)

1. **`src/main.py`** (~300 lines)
   - Module imports
   - `Signal` declaration(s) on `DICOMViewerApp` (`tag_export_union_ready`)
   - Module-level functions (`exception_hook`, `install_application_privacy_boundaries`, `main`)
   - `DICOMViewerApp` class skeleton with composition
   - Core attributes and initialization orchestration

2. **`src/main_app_initialization.py`** (~700 lines)
   - `InitializationMixin` - All `_init_*` / `_setup_*` / `_connect_*` / `_initialize_*` methods (init, core managers, main window/layout, view widgets, subwindow post-init, controllers/tools, handlers, UI setup, signal connections)

3. **`src/main_app_subwindow_management.py`** (~700 lines)
   - `SubwindowManagementMixin` - Subwindow lifecycle + dataset/slice accessor methods + subwindow manager registry
   - `MPRNavigationMixin` - MPR thumbnail and navigation methods

4. **`src/main_app_ui_and_files.py`** (~700 lines)
   - `UIHandlersMixin` - UI signal handlers (focus, layout-changed, privacy toggled, etc.)
   - `FileOperationsMixin` - File open/save/recent operations

5. **`src/main_app_display_settings.py`** (~700 lines)
   - `DisplayProjectionMixin` - Display and projection methods (`_display_slice`, `_redisplay_current_slice`, projection toggles)
   - `SettingsLayoutMixin` - Privacy/settings and layout management (`_on_privacy_view_toggled`, `_open_settings`, swap/expand, layout requests)

6. **`src/main_app_tag_roi.py`** (~700 lines)
   - `TagEditingMixin` - Tag viewer/edit/undo/redo (`_update_tag_viewer`, `_on_tag_edited`, `_undo_tag_edit`, `_redo_tag_edit`, tag-export union)
   - `ROIWorkflowMixin` - ROI/measurement display + list + keyboard delete (`_display_rois_for_subwindow`, `_update_roi_list`, `_keyboard_delete_roi`)

> Note: the original plan grouped Tag Editing, ROI/Measurement, and Layout Management in the category analysis but omitted them from the file structure. They are now assigned above (items 5-6). If any single file still risks > 750 lines after docstrings, split `TagEditingMixin` / `ROIWorkflowMixin` into their own files (6 mixins total).

## Phased Implementation Plan

### Phase 1: Preparation and Infrastructure
**Goal:** Set up infrastructure and validate approach

**Tasks:**
 1. Create empty mixin files with proper docstrings
 2. Add a temporary test (see below) to verify `DICOMViewerApp` instantiates and resolves methods through the composed MRO
 3. Run existing test suite to establish baseline
 4. Document the mixin composition pattern in ARCHITECTURE.md
 5. **Generate Appendix A**: run an `ast`/`grep` scan of `src/main.py` to produce the **complete, enumerated** method→file mapping (every one of the 239 methods, no `etc.`). This appendix supersedes the illustrative category lists and is the authoritative work item for Phases 2-4.
 6. **Update `scripts/check_architecture_boundaries.py`** to map `src/main_app_*.py` to the `"main"` domain (mirror the `src/main.py` branch in `importing_domain()` at line 76), so the new files are not flagged as unknown-domain. Re-run `python scripts/check_architecture_boundaries.py` to confirm clean.
 7. Add a `pyright src/` type-check pass to the verification set (mixin `self` typing via `TYPE_CHECKING`).

**Phase 1 temporary test must assert:**
- `DICOMViewerApp` is a subclass of `QObject` and of every mixin class.
- A representative method from each mixin resolves via `DICOMViewerApp`'s MRO (i.e., `hasattr(DICOMViewerApp, "<method>")`).
- `DICOMViewerApp.__init__` chains `super().__init__()` exactly once and reaches `QObject.__init__` (guards against a second `QObject` base or a broken MRO).

**Tests to Run:**
```bash
python -m pytest tests/test_main_privacy_lifecycle.py -v
python -m pytest tests/test_main_signals_view.py -v
python -m pytest tests/ -k "main" -v
```

**Risks:**
- Mixin composition order matters for MRO: **earlier-listed bases take precedence** (C3 left-to-right); `QObject` must remain the terminal base of `DICOMViewerApp`.
- A second `QObject` base (if a mixin wrongly subclasses `QObject`) raises `TypeError` at class definition time.
- `Signal` declarations placed on a plain mixin fail at class-definition time (PySide6 requires them on the `QObject` subclass).
- Fragile base class: methods reach across mixins via `self`, so init ordering and shared-attribute contracts matter.
- Pyright will flag `self.<app-attr>` as unbound in mixin files unless typed via `TYPE_CHECKING` + `self: "DICOMViewerApp"`.
- `scripts/check_architecture_boundaries.py` maps only `src/main.py` to domain `"main"`; new `src/main_app_*.py` files resolve to domain `""` and will be reported as unknown-domain violations.

**Mitigation:**
- Mixins are **plain classes** (no `QObject` base); only `DICOMViewerApp(QObject, ...)` names `QObject`. Document the exact base list and override precedence (earlier base wins).
- Keep `Signal` declarations on `DICOMViewerApp` in `src/main.py` (see Composition model item 5).
- Shared state goes through explicit accessor helpers (mirror `DisplayConfigMixin._config()`) where it reduces risk; otherwise rely on documented init ordering.
- Add the MRO/initialization test above; add a `super()`-chained `__init__` test that exercises all mixins.
- Add `if TYPE_CHECKING:` import of `DICOMViewerApp` and annotate `self: "DICOMViewerApp"` in mixin methods touching shared state; include `pyright src/` in verification.
- **Phase 1 must update `scripts/check_architecture_boundaries.py`** so `src/main_app_*.py` maps to the `"main"` domain (treat them like `main.py`), otherwise the architecture-boundary check fails on every new file.


### Phase 2: Extract Initialization Methods
**Goal:** Move all `_init_*` methods to InitializationMixin

**Tasks:**
1. Move `InitializationMixin` methods to `src/main_app_initialization.py`
2. Update `DICOMViewerApp` to inherit from `InitializationMixin`
3. Update imports in `src/main.py`
4. Add docstrings to all extracted methods
5. Run tests to verify functionality

**Methods to Move (authoritative list — cross-check against Appendix A):**
- `_init_core_managers`
- `_init_main_window_and_layout`
- `_init_view_widgets`
- `_post_init_subwindows_and_handlers`
- `_init_controllers_and_tools`
- `_initialize_handlers`
- `_setup_ui`
- `_connect_signals`
- (Plus any additional init/setup methods enumerated in Appendix A under "Initialization".)

**Tests to Run:**
```bash
python -m pytest tests/test_main_privacy_lifecycle.py -v
python -m pytest tests/test_main_signals_view.py -v
python -m pytest tests/test_main_window_theme.py -v
```

**Risks:**
- Initialization order dependencies (the `__init__` call sequence in `DICOMViewerApp` must be preserved exactly across mixins)
- Missing attribute references (a mixin method touches state set by another mixin)

**Mitigation:**
- Maintain initialization order in docstrings and in `DICOMViewerApp.__init__` call sequence.
- Shared state via explicit accessor helpers, not scattered `getattr`.
- Add assertions for required attributes at the start of init methods.

### Phase 3: Extract Subwindow Management Methods
**Goal:** Move subwindow and MPR methods to SubwindowManagementMixin + MPRNavigationMixin

**Tasks:**
1. Create `SubwindowManagementMixin` and `MPRNavigationMixin` (plain classes, no `QObject`)
2. Move methods enumerated in Appendix A for "Subwindow Management" and "MPR Navigation" to the respective mixins
3. Update `DICOMViewerApp` inheritance
4. Add comprehensive docstrings
5. Update grandfather list if needed (`--generate-grandfather` after moving)

**Methods to Move (authoritative list — see Appendix A; replace the `etc.` below):**
- Subwindow: `_build_managers_for_subwindow`, `_initialize_subwindow_managers`, `_get_subwindow_dataset`, `_get_subwindow_slice_index`, … (full set in Appendix A)
- MPR: `_update_mpr_navigator_thumbnail`, `_clear_mpr_navigator_thumbnail`, `_on_mpr_detached`, `_on_mpr_thumbnail_clicked`, … (full set in Appendix A)

**Tests to Run:**
```bash
python -m pytest tests/ -k "subwindow or mpr" -v
python -m pytest tests/test_main_signals_view.py -v
```

**Risks:**
- Tight coupling between subwindow and MPR methods
- Shared state access across the two mixins

**Mitigation:**
- Keep related methods together; if coupling is high, merge into one mixin rather than forcing a split.
- Use explicit accessor helpers for shared state.
- Add integration tests that exercise subwindow + MPR together.

### Phase 4: Extract UI Handler Methods
**Goal:** Move UI signal handlers, file operations, display, and settings to their mixins

**Tasks:**
1. Create mixin classes for UI handlers, file operations, display, and settings
2. Move identified methods to appropriate mixins
3. Update `DICOMViewerApp` inheritance
4. Add docstrings following project conventions
5. Verify all signal connections still work

**Methods to Move (authoritative list — see Appendix A; replace the `etc.` below):**
- UI Handlers: `_on_focused_subwindow_changed`, `_on_layout_changed`, … (full set in Appendix A)
- File Operations: `_open_files`, `_open_folder`, … (full set in Appendix A)
- Display: `_display_slice`, `_redisplay_current_slice`, … (full set in Appendix A)
- Settings: `_on_privacy_view_toggled`, `_open_settings`, … (full set in Appendix A)

**Tests to Run:**
```bash
python -m pytest tests/test_main_privacy_lifecycle.py -v
python -m pytest tests/test_main_signals_view.py -v
python -m pytest tests/test_main_window_fullscreen.py -v
python -m pytest tests/test_main_window_toast.py -v
```

**Risks:**
- Signal wiring complexity
- Event handler ordering

**Mitigation:**
- Document signal connections
- Add signal wiring verification tests
- Use explicit connection in initialization

### Phase 5: Final Cleanup and Validation
**Goal:** Complete refactoring and ensure all requirements met

**Tasks:**
1. Verify all files are under 750 lines
2. Refresh the grandfather baseline with `python scripts/git_hook_line_complexity.py --all --generate-grandfather` (this **regenerates** the JSON from the current worktree, so do **not** hand-edit/remove the `src/main.py` entry first — the regenerated list will reflect the now-smaller `main.py` and the new mixin files automatically).
3. Confirm no new `functions` grandfather entries were needed for the mixin files (any CCN>20 function must have been reduced in Phase 6, not grandfathered)
4. Run full test suite
5. Update documentation
6. Verify docstring coverage against the baseline
7. Run privacy gate: `python scripts/git_hook_privacy_checks.py --staged` (moving 200+ methods touches many dialog/debug/logging paths)
8. Run debug-flags check (any `DEBUG_*` left `True` fails CI; gate new tracing behind `src/utils/debug_flags.py`)

**Tests to Run:**
```bash
python -m pytest tests/ -v
python scripts/git_hook_line_complexity.py --all
python scripts/check_repo_harness.py
python scripts/check_architecture_boundaries.py
python scripts/git_hook_privacy_checks.py --staged
python scripts/check_user_docs_links.py
```

**Documentation Updates:**
- Update `ARCHITECTURE.md` with new file structure
- Update `dev-docs/SOURCE_LAYOUT.md` if needed
- Add refactoring notes to `CHANGELOG.md`
- Update `dev-docs/MAINTENANCE_LOG.md`

### Phase 6: Reduce Cyclomatic Complexity of Extracted Functions (Lizard CCN)

**Goal:** Bring every function in the new mixin files to `CCN <= 20` (and ideally lower), so the refactor lands **without** adding any `functions` grandfather entries.

**Why this is necessary (clarifying the "zero grandfathered functions" premise):** `src/main.py` currently has **zero** entries in the `functions` grandfather map, yet `lizard` shows many of its methods already exceed CCN 20 (e.g. `_post_init_subwindows_and_handlers` CCN≈76, `__init__`≈59, `_init_view_widgets`≈52, `_sync_navigation_slider_for_subwindow`≈50, `_init_core_managers`≈28). They are not blocking today only because the pre-commit hook checks **staged** files and `src/main.py` is already committed and rarely re-staged — so its function CCN is effectively never re-evaluated. When these methods move into newly created (and thus newly staged) `src/main_app_*.py` files, the hook evaluates them for the first time and **blocks any function > 20**. So the work goes from *un-checked* to *checked*, and Phase 6 is required — not redundant. (Verified via `lizard --CCN 20 src/main.py`.)

**Why not a separate plan:** Folding it in keeps the PR self-contained and prevents "extract now, reduce later" drift where high-CCN functions get quietly grandfathered. If the team prefers a dedicated follow-up, the output of Step 1 below (the CCN inventory) is the ready-made backlog for that plan.

**Tasks:**
1. **Inventory (do this right after Phase 1):** run `lizard --CCN 20 src/main.py` to list every method already at/above CCN 20. Record each (`path::name`, current CCN) in Appendix B. This is the reduction backlog.
2. **During Phases 2-4:** as each method is moved, re-measure it in its new file (`lizard --CCN 20 src/main_app_*.py`). If `CCN > 20`, reduce it *before* committing that phase:
   - Extract private helpers (nested `if`/`for` bodies → small methods).
   - Replace nested conditionals with early `return`/guard clauses.
   - Replace long `if/elif` chains with dispatch dicts or polymorphism.
   - Move validation/parsing into dedicated helpers.
   - Avoid introducing `print` tracing; gate any new debug output behind `src/utils/debug_flags.py`.
3. **Verify no new grandfather entries were required:** after Phase 5's `--generate-grandfather`, confirm the `functions` map contains no `src/main_app_*.py` entries. If any remain, that indicates an unreduced function — fix it rather than ship the grandfather entry.
4. **Add/extend tests** for any extracted helper so behavior is pinned (ties to Coverage Targets baseline).

**Measurement commands:**
```bash
lizard --CCN 20 src/main.py                 # baseline inventory of high-CCN methods
lizard --CCN 20 src/main_app_*.py           # per-phase check on the new files
python scripts/git_hook_line_complexity.py --all   # full repo gate (line + CCN)
```

**Acceptance:** Every function in `src/main_app_*.py` and `src/main.py` has `CCN <= 20` (no `functions` grandfather entries for the new files). Functions that were already > 20 in `main.py` are reduced, not grandfathered.

**Risks:**
- Over-refactoring changes behavior — mitigate with the per-phase test runs and targeted new tests on extracted helpers.
- Some methods may need structural redesign (not just mechanical extraction) — flag these in Appendix B with a note and tackle in a focused sub-PR if they block.

**Mitigation:**
- Keep CCN reduction mechanical and test-backed; run the test suite after each reduction.
- Use `lizard` diffs (before/after) to confirm CCN dropped and no logic was lost.

## Docstring Requirements

### Standards
- Follow the **existing** project docstring convention. The repo uses NumPy/Sphinx-style sections (see `src/utils/config/display_config.py` and `src/main.py:262`), e.g. `Returns:` without an `Args:` header block. **Do not impose Google-style** (the example template below is now NumPy-style to match). Keep docstrings consistent with the surrounding codebase so review/consistency checks pass.
- Document all parameters, returns, and raises
- Include usage examples only where they are verified (do not assert "asynchronous" behavior unless confirmed)
- Document initialization order for init methods

### Coverage Targets
- The vast majority of `DICOMViewerApp` methods are private (`_`-prefixed), so "100% public-method coverage" is nearly meaningless. Frame targets around the **existing** `tests/test_main_*.py` baseline instead.
- **Establish the current coverage number before starting** (run `python -m pytest tests/ -v` with coverage, or `scripts/new_code_coverage.py`; the Sonar baseline `sonar-main-measures.json` / `coverage.xml` can be referenced). Success Criterion 4 ("maintained or improved") is only measurable against this baseline.
- **Docstring coverage baseline:** there is no dedicated docstring-coverage tool in the repo; measure against the existing `src/main.py` docstring density (manual review + the existing test/docstring conventions). Track "docstrings added per extracted method" rather than a percentage.
- Document composition pattern in class docstrings
- Document MRO implications

### Example Docstring Template (NumPy/Sphinx style, matching repo)
```python
def _update_mpr_navigator_thumbnail(self, idx: int) -> None:
    """Update the MPR navigator thumbnail for a specific subwindow.

    This method retrieves the current MPR pixel array for the specified
    subwindow and updates the corresponding thumbnail in the navigator.
    The thumbnail is used to provide a visual preview of the MPR view.

    Parameters
    ----------
    idx : int
        The subwindow index (0-based) to update the thumbnail for.

    Raises
    ------
    IndexError
        If idx is not a valid subwindow index.
    RuntimeError
        If the MPR processor is not available for the subwindow.

    Notes
    -----
    This method is called automatically when the MPR view changes.
    (Verify whether thumbnail generation is synchronous or asynchronous
    before asserting timing behavior in the real docstring.)
    """
```

## Risk Assessment

### High Risks
1. **Mixin Composition Order / Second QObject Base**
   - Risk: Wrong MRO (e.g. assuming later-listed mixins win when Python C3 gives **earlier-listed bases precedence**), or a mixin wrongly subclassing `QObject`, causes `TypeError` at class-definition time or incorrect method resolution
   - Impact: Import failure or incorrect behavior
   - Mitigation: Mixins are plain classes (no `QObject`); `QObject` is the terminal base of `DICOMViewerApp(QObject, ...)`; document the exact base list and that earlier base wins; add the MRO/initialization test from Phase 1

2. **Circular Dependencies**
   - Risk: Mixins depend on each other
   - Impact: Import errors or runtime failures
   - Mitigation: Careful dependency analysis, import lazy loading

3. **Signal Wiring Breakage**
   - Risk: Extracted methods break signal connections
   - Impact: UI not responding to events
   - Mitigation: Signal wiring verification tests, integration tests; keep `Signal` declarations on `DICOMViewerApp` (PySide6 requires `Signal` on a `QObject` subclass)

4. **High-CCN Functions Block the Commit After Extraction**
   - Risk: `src/main.py` has many methods already > CCN 20, but they are not blocked today because the pre-commit hook only checks **staged** files and `main.py` is already committed. Moving them into newly staged `main_app_*.py` files makes them checked for the first time; any function > CCN 20 then blocks the commit (Lizard, `BLOCK_CCN=20`)
   - Impact: CI/hook blocks the PR; stalled refactor
   - Mitigation: Reduce CCN during extraction (Phase 6); never grandfather a function just to pass the hook. Measure with `lizard --CCN 20 src/main_app_*.py` after each phase.

5. **State / Cross-Mixin Dependencies at Scale**
   - Risk: The plan references `DisplayConfigMixin`'s accessor-helper pattern. Refactoring every `self.<attr>` across 239 methods into `self._get_<attr>()` helpers is large, undocumented scope creep and risks behavior change.
   - Impact: Schedule blowout or silent breakage if done inconsistently.
   - Mitigation: Do **not** rewrite all attribute access. Keep direct `self.<attr>` reads where init ordering guarantees the attribute exists; add accessor helpers only for the highest-churn shared state. Document the init order contract instead of forcing uniform accessors.

### Medium Risks
1. **Attribute Access During Refactoring**
   - Risk: Methods reference attributes not yet initialized
   - Impact: AttributeError during initialization
   - Mitigation: Type hints, assertions, careful ordering

2. **Test Coverage Gaps**
   - Risk: Existing tests don't cover extracted methods
   - Impact: Refactoring introduces bugs
   - Mitigation: Add new tests for extracted methods

3. **Documentation Drift**
   - Risk: Docs not updated to match new structure
   - Impact: Confusion for future developers
   - Mitigation: Documentation verification in CI

### Low Risks
1. **Performance Impact**
   - Risk: Mixin composition adds overhead
   - Impact: Negligible (mixin composition is static)
   - Mitigation: Performance benchmarking

2. **Grandfather List Management**
   - Risk: Forget to update grandfather list
   - Impact: CI failures
   - Mitigation: Automated hook checks

## Rollback Plan

All refactoring happens on a **dedicated feature branch**; `main` stays untouched until Phase 5 validation passes. If critical issues arise:

1. **Phase Rollback:** Revert individual phases using git (each phase is its own commit/PR)
2. **Complete Rollback:** Delete branch and return to main
3. **Data Safety:** No data migration involved, code-only change
4. **Branch Protection:** Keep main branch clean until validation complete (including Phase 6 CCN reduction)

## Success Criteria

1. All files under 750 lines
2. All tests passing (existing `tests/test_main_*.py` suite + new helper tests)
3. **No new `functions` grandfather entries for the mixin files** — every function `CCN <= 20` (Phase 6 complete)
4. Docstring coverage maintained or improved against the measured baseline
5. No performance regression
6. Documentation updated (ARCHITECTURE.md, SOURCE_LAYOUT.md, CHANGELOG.md, MAINTENANCE_LOG.md)
7. CI checks passing (line complexity, function CCN, architecture boundaries, privacy gate, user-docs links)

## Verification Commands

### After Each Phase
```bash
# Verify tests
python -m pytest tests/test_main_privacy_lifecycle.py -v
python -m pytest tests/test_main_signals_view.py -v

# Verify line counts + function CCN
python scripts/git_hook_line_complexity.py --all

# Verify architecture (after Phase 1 boundary update)
python scripts/check_architecture_boundaries.py

# Verify mixin typing (TYPE_CHECKING self: DICOMViewerApp)
pyright src/
```

### Final Verification
```bash
# Full test suite
python -m pytest tests/ -v

# All hook checks
python scripts/git_hook_line_complexity.py --all
python scripts/check_repo_harness.py
python scripts/check_architecture_boundaries.py
pyright src/

# Documentation links
python scripts/check_user_docs_links.py
```

## Next Steps

1. Review and approve this plan
2. Begin Phase 1 implementation
3. Create tracking issue in project backlog
4. Update AGENTS.md with refactoring progress

## References

- `scripts/git_hook_line_complexity.py` - Line count and complexity (Lizard CCN) thresholds
- `scripts/line_complexity_grandfather.json` - Current grandfather list (`files` + `functions` maps)
- `requirements-dev.txt` (lizard>=1.23.0) - Complexity measurement dependency
- `src/utils/config/display_config.py` - Reference plain-mixin pattern (`DisplayConfigMixin`)
- `ARCHITECTURE.md` - Architecture boundaries and conventions
- `dev-docs/SOURCE_LAYOUT.md` - Source code layout documentation
- `tests/test_main_*.py` - Existing test coverage
- `src/utils/debug_flags.py` - Gate for any new debug tracing

## Appendix A — Complete Method→File Mapping (generated in Phase 1)

To be populated by an `ast`/`grep` scan of `src/main.py` listing **all 239 methods** with: method name, current line range, target mixin file, and target mixin class. This is the authoritative work item for Phases 2-4 and replaces every `etc.` placeholder above. Suggested generation:

```bash
# enumerate methods with line numbers
grep -nE "^    def " src/main.py
# or with ast for robustness
python - <<'EOF'
import ast
src = open("src/main.py").read()
tree = ast.parse(src)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.col_offset == 4:
        print(node.lineno, node.name)
EOF
```

## Appendix B — High-CCN Function Inventory (Lizard, populated in Phase 6 Step 1)

Run `lizard --CCN 20 src/main.py` and record each method that already exceeds the block threshold, with its current CCN. This is the reduction backlog for Phase 6. Example row format: `src/main.py::<method>  CCN=<n>  -> target CCN<=20`.

(No entries yet — generated during implementation.)
