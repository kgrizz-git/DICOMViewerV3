# Refactor Plan: Split main.py into Multiple Files

**Created:** 2026-08-07  
**Last updated:** 2026-08-14
**Status:** Complete pending human commit (gate remediation done 2026-08-08)  
**Target:** `src/main.py` (~334 lines) + 5 mixin modules under `src/main_app_*.py` (each ≤750 lines; largest ~642)

> **Readiness (2026-08-08):** Strategy approved. Start with **Phase 0** (test safety net), then Phase 2 scaffolding, then extraction (Phases 3–5). Appendix A/B are populated. CCN reduction is a regression check only (zero methods currently ≥ 20). Phase numbering is 0, then 2–7 (Phase 1 unused).

## Progress ledger (2026-08-08 resume)

| Item | Status | Notes |
|------|--------|-------|
| Plan strategy + mixin rules (plain mixins, Signal on `DICOMViewerApp`, no mixin `__init__`) | **Done** | Commits `cc2a07c`, `c671910`, `1f6c223` + uncommitted plan polish |
| Appendix A (236-method ownership map) + Appendix B (CCN inventory) | **Done** | Extraction complete; `main.py` ~334 lines + 5 mixins |
| `interrogate>=1.7.0` in `requirements-dev.txt` + inventory entry | **Done** | Phase 2 Task 8 complete early |
| Phase 0 safety-net test suites | **Done** | 5 new suites + `tests/main_test_helpers.py`; 31 new tests (37 incl. existing 6 in acceptance cmd) |
| Phase 0 coverage/interrogate baseline numbers recorded | **Done** | Coverage **50%** un-omitted (`tmp/main-refactor/phase0_coverage_baseline.md`); interrogate **B = 98.8%** confirmed |
| Phase 2 empty mixins / `.coveragerc` omit / architecture boundaries / MRO test | **Done** | 5 `src/main_app_*.py` shells, `tests/test_main_mixin_composition.py`, `.coveragerc` omit, architecture checker |
| Phase 3 — InitializationMixin extraction (12 methods) | **Done** | `src/main_app_initialization.py` 517 lines; `main.py` 2097 lines; CCN max 12; 57/57 tests pass |
| Phase 4 — SubwindowManagementMixin + MPRNavigationMixin (53 methods) | **Done** | `src/main_app_subwindow_management.py` 642 lines; `main.py` 1604 lines; CCN max 9; 47/47 tests pass |
| Phase 5 — UIHandlersMixin + FileOperationsMixin + DisplayProjectionMixin + SettingsLayoutMixin + TagEditingMixin + ROIWorkflowMixin (164 methods) | **Done** | 3 mixin files populated; `main.py` 506 lines; CCN max 6; 79/79 Phase 0–5 tests pass |
| Phase 6–7 extraction + cleanup | **Done** | Imports pruned; grandfather regenerated; docs/changelog; **gate remediation** (PERF_LOG crash, basedpyright pragmas, ruff) |
| Gate remediation (post-review) | **Done** | C1 `_log_startup_perf`; basedpyright 0 via ImageViewer-style pragmas (not `self: DICOMViewerApp` — invalid under pyright); ruff 0; `StudiesNestedDict` consolidated; TO_DO coverage-omit lift |

**Resume point:** Human commit on `refactor/main-split` when ready.

### Typing deviation (recorded 2026-08-08)

Plan Composition model item 8 originally prescribed `self: DICOMViewerApp` on mixin methods. basedpyright rejects that (`Type of parameter "self" must be a supertype of its class "<Mixin>"`). The implementation matches existing `ImageViewerInputMixin` / `ImageViewerViewMixin` pragmas instead (`reportAttributeAccessIssue` / `reportArgumentType` / `reportUninitializedInstanceVariable`). There is **no** `TYPE_CHECKING` import of `main` from `main_app_*.py` (and therefore no `main ↔ main_app_*` import cycle).

**Accepted tradeoff (R1):** with untyped mixin `self` and `reportUnknown*=none` in `pyrightconfig.json`, `self.<app-attr>` typos in mixin bodies are no longer reported as basedpyright **errors** (they were on monolithic `DICOMViewerApp`). Mitigation: Phase 0 behavioral tests + move-only discipline; do not “fix” by adding a top-level `from main import DICOMViewerApp`.

**Composition model item 8 (superseded):** use `from __future__ import annotations` + the ImageViewer-style file pragma above; do **not** annotate `self: DICOMViewerApp` on plain mixins.

## Summary

The `src/main.py` file is currently the largest in the codebase at 2494 lines and is grandfathered in the line complexity hook. This plan outlines a phased approach to split it into `main.py` plus 5 mixin modules (6 files total), each under the 750-line threshold, while maintaining functionality, test coverage, and docstring quality.

## Current State Analysis

### File Structure
- **Location:** `src/main.py`
- **Lines:** 2494 (grandfathered at 2494 in `scripts/line_complexity_grandfather.json`)
- **Components:**
  - Module docstring + imports (lines 1-260)
  - `DICOMViewerApp(QObject)` class (lines 261-2430) with **236 method definitions** (AST class-body count; an earlier `grep -cE "    def "` of 239 counted nested defs). The bulk are private `_`-prefixed methods; ~211 are thin facades (≤2 statements) that already delegate into `core.*`
  - Module-level functions: `exception_hook` (2431), `install_application_privacy_boundaries` (2454), `main` (2472)

### Method Groupings in DICOMViewerApp
The class contains methods that fall into logical categories. The counts below are **approximate/illustrative**; the authoritative, complete method→file mapping is **Appendix A** (generated 2026-08-08). Refresh Appendix A if `src/main.py` changes before extraction.

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
- `files`: `path -> line_count` (pre-refactor had `src/main.py: 2494`; **removed** in Phase 6 regenerate because the file is now under `BLOCK_LINES`). New `main_app_*.py` files are also under 750 and do not need `files` grandfather entries.
- `functions`: `path::name -> CCN` (67 entries today; **zero** for `src/main.py`). A function is allowed only while its CCN is at or below the recorded cap; the hook **auto-ratchets the cap down** when a function improves, and **blocks** any growth past the recorded cap.

**Critical implication (updated 2026-08-08):** `src/main.py` currently has **no** grandfathered high-CCN functions, and a fresh `lizard --CCN 20 src/main.py` run shows **zero** methods at or above CCN 20 (max ≈ 14; see Appendix B). When methods move into newly staged `src/main_app_*.py` files, the hook will evaluate them — so the per-phase gate remains mandatory as a **regression check**. It is **not** a redesign backlog: do not invent CCN rewrites unless a move somehow pushes a function over 20 (e.g. after extracting helpers incorrectly). Phase 7 consolidates the verification.

Current grandfather status: `src/main.py` file entry = 2494; `functions` entries for `src/main.py` = 0.

### Coverage Strategy (CI `--cov-fail-under=80` trap)
`src/main.py` is excluded from coverage via `omit = src/main.py` in `.coveragerc`, and CI enforces `PYTHONPATH=src python -m pytest tests --cov=src --cov-fail-under=80` (`.github/workflows/ci.yml`). Today `src/main.py`'s business logic is only ~53% covered (mostly init paths). Extracting ~2,200 uncovered lines into `src/main_app_*.py` removes them from the omit rule, so they enter the coverage denominator and will very likely pull the repo average below 80%, **failing CI**.

The plan adopts a **hybrid** (do both):
- **Option A — keep the debt quarantined:** extend the `.coveragerc` `omit` list with `src/main_app_*.py` so the extracted files are not counted until deliberately opted in. This prevents a CI regression on day one and is the safe default.
- **Option B — pay it down later:** expand safety-net tests over time so `src/main_app_*.py` can eventually be removed from `omit` without dropping below 80%. This is **not** a Phase 0 hard gate (un-omitting ~2.4k lines of mostly-uncovered facade code today would make Phase 0 unbounded).

**Decision recorded:** Apply Option A at Phase 2 (add the omit) so CI stays green during incremental extraction. Phase 0 records a coverage *baseline* (temporary un-omit for measurement only, then restore the omit — do not require `--cov-fail-under=80` to pass while un-omitted). Lifting the omit is a **follow-up backlog item** after the refactor lands; do not leave the new files uncounted permanently.

## Refactoring Strategy

### Approach: Mixin-Based Decomposition (plain mixins, single QObject base)

To avoid circular dependencies and maintain the single `DICOMViewerApp` class, we'll use Python mixins. **Critical constraint:** `DICOMViewerApp` already inherits `QObject` (`src/main.py:261`, and `src/main.py:326` calls `super().__init__()` as the first statement). PySide6 forbids two `QObject` bases, so the mixins must be **plain classes that do NOT inherit `QObject`** — matching the repo's existing mixin convention (`src/utils/config/display_config.py:24` `DisplayConfigMixin`, `paths_config.py`, `layout_config.py`, etc., which are plain `class XMixin:` and access shared state via `getattr(self, ...)`).

Composition model:

1. Keep `DICOMViewerApp` in `src/main.py` as the main class, with `QObject` as its **sole** Qt base.
2. Extract method groups into **plain mixin classes** (no `QObject` base) in separate files.
 3. Compose via multiple inheritance: `class DICOMViewerApp(QObject, InitializationMixin, SubwindowManagementMixin, MPRNavigationMixin, UIHandlersMixin, FileOperationsMixin, DisplayProjectionMixin, SettingsLayoutMixin, TagEditingMixin, ROIWorkflowMixin):`. Python C3 linearization resolves bases **left-to-right, so earlier-listed bases take precedence** — i.e. a method defined in `InitializationMixin` overrides the same method in a later-listed mixin. Relying on implicit shadowing is a maintenance hazard, so **method-name collisions across mixins are prohibited** (enforced by a Phase 2 test, see below). Each method must have exactly one owning mixin; Appendix A is the authoritative ownership map.
 4. Each mixin file stays under 750 lines. Because 4 files × 750 = 3000 leaves no margin for duplicated structure (imports, module docstrings, class declarations) and the mandated docstrings, target **5 mixin files + `main.py`** (see Target File Structure). If any single mixin still exceeds 750 after extraction, split it further (e.g. separate `TagEditingMixin` / `ROIWorkflowMixin` into their own files → 6 mixins + `main.py` = 7 files). Plan for up to 7 files if docstrings push a heavy mixin over budget.
 5. **`Signal` declarations cannot move to plain mixins.** PySide6 requires `Signal` instances to be class attributes on a `QObject` subclass. `src/main.py` declares exactly one (`tag_export_union_ready = Signal(int, object)` at line 269); it must remain on `DICOMViewerApp` in `src/main.py`. Mixins connect to / emit it via `self.tag_export_union_ready` but never declare it.
 6. **Mixins MUST NOT define `__init__`.** PySide6's `QObject` does not cooperatively call `super().__init__()`; a mixin `__init__` would be skipped or break the chain. All initialization happens in `DICOMViewerApp.__init__` via the explicit named setup methods (`_init_*`, `_setup_*`, `_connect_*`, `_initialize_*`), which call directly into the mixin methods. No mixin owns object construction.
 8. **Typing across mixins (superseded 2026-08-08):** each new mixin file starts with `from __future__ import annotations` and uses the ImageViewer-style file pragma (`reportAttributeAccessIssue` / `reportArgumentType` / `reportUninitializedInstanceVariable`). Do **not** annotate `self: DICOMViewerApp` (basedpyright Liskov self-type error) and do **not** `TYPE_CHECKING`-import `main` (unnecessary cycle). See “Typing deviation” in the Progress ledger. Type-check via `python scripts/check_basedpyright_errors.py`.
9. Shared/cross-mixin state is accessed through explicit accessor helpers (following `DisplayConfigMixin._config()`/`_save_config()`) where it reduces risk, but a full rewrite of every `self.attribute` into `self._get_attribute()` across all 236 methods is **out of scope** (see Risk Assessment, State/Cross-Mixin Dependencies). Methods may read `self.<attr>` directly as long as init ordering guarantees the attribute exists; accessor helpers are used only for the highest-churn shared state.


### Facade reality (important)

`src/main.py` is already mostly a **thin orchestration facade**: ~211 of 236 methods are ≤2 statements and many docstrings say `Body in core.*` (e.g. `_connect_signals` → `wire_all_signals`, handlers via `core.app_handler_bootstrap`). This split is primarily about **file length / ownership**, not rewriting business logic. Phase 0 should pin facade delegation and a small wiring smoke set — not re-test all of `core.app_signal_wiring` from inside `main.py`.

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

### Phase 0: Test Safety Net (prerequisite — do before any extraction)
**Goal:** Establish automated confidence that the refactor does not break `DICOMViewerApp` orchestration, because the existing `tests/test_main_*.py` suite covers only ~initialization + 2 signal slots (per `test_coverage_assessment_20260808_004301.md`, `src/main.py` is omitted from `.coveragerc` and achieves only ~53% line coverage when measured, almost entirely init paths). Passing the current suite gives near-zero confidence that signal wiring, delegation signatures, or subwindow focus sync survive the move.

**Context / harness:** `DICOMViewerApp()` is already instantiable in tests via `@pytest.mark.qt` + the `qapp` fixture (`tests/conftest.py`); `tests/test_main_signals_view.py` already verifies two slots (`privacy_view_toggled`, `smooth_when_zoomed_toggled`). New tests follow that pattern — instantiate `main_module.DICOMViewerApp()`, emit signals, assert delegated state/method calls. No GUI launch required for most; use a fixture that builds the app with lightweight/mock managers where a full real manager tree is heavy.

**Tasks (add these suites; each pins current behavior so the refactor is observable):**
1. **Signal-to-slot wiring smoke tests** — extend `tests/test_main_signals_view.py` (or add `tests/test_main_signal_wiring.py`) with a **representative** set of slots that `DICOMViewerApp` exposes and that `_connect_signals()` reaches via `wire_all_signals(self)` (full connect matrix lives in `core.app_signal_wiring`, not in `main.py`). Emit each chosen UI signal and assert the target `DICOMViewerApp` slot is invoked / state updates. Goal: catch silent breakage of the facade entry points during the move — not re-own wiring coverage for `core`.
2. **Subwindow focus & multi-pane lifecycle tests** — test `_on_focused_subwindow_changed()` and assert `DICOMViewerApp` active pointers (`image_viewer`, `view_state_manager`, `slice_display_manager`, etc.) update correctly; cover `_update_focused_subwindow_references()`, `_redisplay_subwindow_slice()`, `_clear_subwindow()`, `_close_series()`, `_close_study()`.
3. **Facade / action delegation tests** — unit-test `DICOMViewerApp` facade delegation methods, asserting parameters are forwarded with correct types/names to `_export_app_facade`, `_qa_app_facade`, `_mpr_controller` (use mocks for the underlying objects).
4. **Event filter / shortcut dispatch tests** — test `DICOMViewerApp.eventFilter` with synthetic `QKeyEvent`s for ROI deletion and layout hotkeys.
5. **Tag export union background-thread tests** — test `get_tag_export_union_snapshot` / `_drain_tag_export_union_worker` with a fixture to ensure no deadlock/thread leak.
6. **Coverage baseline (measurement only):** temporarily remove `src/main.py` from the `.coveragerc` omit list, capture the coverage number, then **restore the omit**. Do **not** require `--cov-fail-under=80` to pass while un-omitted (Option A remains the CI strategy through extraction).
7. Record the pre-refactor `interrogate` docstring baseline (B) (`interrogate` is already pinned in `requirements-dev.txt` and registered in `security/security-tool-inventory.json`) and the `src/main.py` coverage baseline from Task 6.

**Acceptance:** New suites pass against the **current** (un-refactored) `src/main.py`. They are the regression oracle for Phases 1-7 — if any later phase breaks wiring/delegation, these fail.

**Tests to Run:**
```bash
python -m pytest tests/test_main_signals_view.py tests/test_main_privacy_lifecycle.py tests/test_main_signal_wiring.py -v
python -m pytest tests/ -k "main or subwindow or signal or facade or eventfilter or tag_export" -v
```

### Phase numbering note
There is **no Phase 1**. Historical numbering proceeds **0 → 2 → 3 → 4 → 5 → 6 → 7**. Do not skip Phase 0.

### Phase 2: Preparation and Infrastructure
**Goal:** Set up infrastructure and validate approach

**Tasks:**
 1. Create empty mixin files with proper docstrings
 2. Add a temporary test (see below) to verify `DICOMViewerApp` instantiates and resolves methods through the composed MRO
 3. Run existing test suite to establish baseline
 4. Document the mixin composition pattern in ARCHITECTURE.md
 5. **Confirm Appendix A**: Appendix A is already populated (236 methods, 2026-08-08). Re-run the `ast`/`lizard` scan only if `src/main.py` changed since generation; keep the appendix as the authoritative work item for Phases 3–5.
  6. **Update `scripts/check_architecture_boundaries.py`** so `src/main_app_*.py` is treated as the `"main"` domain. The script resolves domain in **two** places that must both be updated:
     - `importing_domain()` (line 76): add a branch normalizing `main_app_*.py` → `"main"` (same as `main.py`).
     - `top_level_package()` (line 55): for `src.main_app_X` imports, return `"main"` instead of `"main_app_X"`, so that `violation_reason()` still blocks illegal imports *into* the main domain (e.g. a `gui` module importing `src.main_app_initialization` must be flagged, the same as importing `src.main`).
     Re-run `python scripts/check_architecture_boundaries.py` to confirm clean.
  7. Add a type-check pass via `python scripts/check_basedpyright_errors.py` (the repo pins **basedpyright**, not raw `pyright`) to the verification set (mixin files use ImageViewer-style file pragmas per Typing deviation — not `TYPE_CHECKING` / `self: DICOMViewerApp`).
  8. **`interrogate` inventory — DONE:** `interrogate>=1.7.0` is already in `requirements-dev.txt` and registered in `security/security-tool-inventory.json`. Skip re-adding; only verify `python scripts/check_security_tool_inventory.py` still passes if those files are touched.
 9. **Decide and apply the coverage strategy** (see *Coverage Strategy* below) so the new mixin files do not drop the repo below `--cov-fail-under=80`.
 10. **Confirm Appendix B:** already populated — zero methods CCN ≥ 20. Re-measure only if `src/main.py` changed.
 11. **Apply Option A (quarantine):** add `src/main_app_*.py` to the `omit` list in `.coveragerc` (alongside `src/main.py`) so the extracted files are not counted in coverage until deliberately opted in. This keeps CI green during the incremental extraction. Re-run `python -m pytest tests --cov=src --cov-fail-under=80` to confirm it still passes.

**Phase 2 temporary test must assert:**
- `DICOMViewerApp` is a subclass of `QObject` and of every mixin class.
- A representative method from each mixin resolves via `DICOMViewerApp`'s MRO (i.e., `hasattr(DICOMViewerApp, "<method>")`).
- `DICOMViewerApp.__init__` chains `super().__init__()` exactly once and reaches `QObject.__init__` (guards against a second `QObject` base or a broken MRO).
- **No mixin defines `__init__`** (each mixin class has no `__init__` attribute).
- **Zero method-name collisions across mixins:** collect `dir()` of every mixin class (excluding `object`/`QObject` dunder methods) and assert the intersection of user-defined method names is empty. This enforces Composition model item 3 (no implicit shadowing).

**Tests to Run:**
```bash
python -m pytest tests/test_main_privacy_lifecycle.py -v
python -m pytest tests/test_main_signals_view.py -v
python -m pytest tests/ -k "main" -v
```

**Risks:**
- Mixin composition order matters for MRO: **earlier-listed bases take precedence** (C3 left-to-right); `QObject` must remain the **primary/first base** of `DICOMViewerApp` (PySide6 requires the `QObject` subclass to be listed first — it is the *first* base, not the last/terminal one).
- A second `QObject` base (if a mixin wrongly subclasses `QObject`) raises `TypeError` at class definition time.
- `Signal` declarations placed on a plain mixin fail at class-definition time (PySide6 requires them on the `QObject` subclass).
- Fragile base class: methods reach across mixins via `self`, so init ordering and shared-attribute contracts matter.
 - basedpyright may report `self.<app-attr>` typos less strictly on mixin files when using ImageViewer-style file pragmas (see Typing deviation); mitigation is Phase 0 behavioral tests + move-only discipline, not `TYPE_CHECKING` or `self: DICOMViewerApp`.
 - `scripts/check_architecture_boundaries.py` maps only `src/main.py` to domain `"main"`; new `src/main_app_*.py` files resolve to domain `""` and will be reported as unknown-domain violations unless updated in both `importing_domain()` and `top_level_package()` (see Task 6).

**Mitigation:**
- Mixins are **plain classes** (no `QObject` base); only `DICOMViewerApp(QObject, ...)` names `QObject`. Document the exact base list and override precedence (earlier base wins).
- Keep `Signal` declarations on `DICOMViewerApp` in `src/main.py` (see Composition model item 5).
- Mixins MUST NOT define `__init__`; all init goes through `DICOMViewerApp.__init__` calling named setup methods (Composition model item 6).
- Prohibit method-name collisions across mixins; enforce with the Phase 2 collision test (Composition model item 3).
- Shared state goes through explicit accessor helpers (mirror `DisplayConfigMixin._config()`) where it reduces risk; otherwise rely on documented init ordering.
- Add the MRO/initialization/collision tests above.
- Each mixin file uses `from __future__ import annotations` + ImageViewer-style file pragma (`reportAttributeAccessIssue` / `reportArgumentType` / `reportUninitializedInstanceVariable`); include `python scripts/check_basedpyright_errors.py` in verification (see Typing deviation).
- Phase 2 Task 6 updates `scripts/check_architecture_boundaries.py` in both `importing_domain()` and `top_level_package()` so `main_app_*` is the `"main"` domain.


### Phase 3: Extract Initialization Methods
**Goal:** Move all `_init_*` methods to InitializationMixin

**Tasks:**
1. Move `InitializationMixin` methods to `src/main_app_initialization.py`
2. Update `DICOMViewerApp` to inherit from `InitializationMixin`
3. Update imports in `src/main.py`
4. Add docstrings to all extracted methods
5. Run tests to verify functionality
6. **CCN regression gate (mandatory, blocking):** after moving methods, run `lizard --CCN 20 src/main_app_initialization.py`. Appendix B shows these methods are currently ≤ 20; if any exceed 20 after the move (or after extracting helpers), reduce before the phase commit. Do **not** invent redesigns for already-compliant methods. The pre-commit hook blocks CCN > 20 on newly staged files.

**Methods to Move:** see Appendix A section `src/main_app_initialization.py` — `InitializationMixin` (complete enumerated list).

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

### Phase 4: Extract Subwindow Management Methods
**Goal:** Move subwindow and MPR methods to SubwindowManagementMixin + MPRNavigationMixin

**Tasks:**
1. Create `SubwindowManagementMixin` and `MPRNavigationMixin` (plain classes, no `QObject`)
2. Move methods enumerated in Appendix A for "Subwindow Management" and "MPR Navigation" to the respective mixins
3. Update `DICOMViewerApp` inheritance
4. Add comprehensive docstrings
5. Update grandfather list if needed (`--generate-grandfather` after moving)
6. **CCN regression gate (mandatory, blocking):** after moving methods, run `lizard --CCN 20 src/main_app_subwindow_management.py`. Reduce only if CCN > 20 appears; otherwise proceed.

**Methods to Move:** see Appendix A sections `SubwindowManagementMixin` and `MPRNavigationMixin` (complete enumerated lists).

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

### Phase 5: Extract UI Handler Methods
**Goal:** Move UI signal handlers, file operations, display, and settings to their mixins

**Tasks:**
1. Create mixin classes for UI handlers, file operations, display, and settings
2. Move identified methods to appropriate mixins
3. Update `DICOMViewerApp` inheritance
4. Add docstrings following project conventions
5. Verify all signal connections still work
6. **CCN regression gate (mandatory, blocking):** after moving methods, run `lizard --CCN 20 src/main_app_ui_and_files.py src/main_app_display_settings.py src/main_app_tag_roi.py`. Reduce only if CCN > 20 appears; otherwise proceed.

**Methods to Move:** see Appendix A sections for `UIHandlersMixin`, `FileOperationsMixin`, `DisplayProjectionMixin`, `SettingsLayoutMixin`, `TagEditingMixin`, and `ROIWorkflowMixin` (complete enumerated lists).

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

### Phase 6: Final Cleanup and Validation
**Goal:** Complete refactoring and ensure all requirements met

**Tasks:**
1. Verify all files are under 750 lines (plan for 7 files if any mixin overflows).
2. Refresh the grandfather baseline with `python scripts/git_hook_line_complexity.py --all --generate-grandfather` (this **regenerates** the JSON from the current worktree, so do **not** hand-edit/remove the `src/main.py` entry first — the regenerated list will reflect the now-smaller `main.py` and the new mixin files automatically).
3. **Validate the grandfather diff:** run `git diff scripts/line_complexity_grandfather.json` and confirm **NO new entries appear under the `functions` map** for the mixin files. `--generate-grandfather` silently records any remaining CCN>20 function; if such an entry appears, return to Phase 7 and reduce it rather than shipping the grandfather entry.
4. Run full test suite
5. Update documentation
6. Verify docstring coverage (see Success Criterion 4 heuristic below)
7. Run privacy gate: `python scripts/git_hook_privacy_checks.py --staged` (moving 200+ methods touches many dialog/debug/logging paths)
8. Run debug-flags check (any `DEBUG_*` left `True` fails CI; gate new tracing behind `src/utils/debug_flags.py`)
9. Run the agent smoke harness (mandated by AGENTS.md before claiming done): `python scripts/agent_smoke_harness.py` — splitting the app root risks breaking startup/signal wiring, so this is a hard gate.

**Tests to Run:**
```bash
python -m pytest tests/ -v
python scripts/git_hook_line_complexity.py --all
python scripts/check_repo_harness.py
python scripts/check_architecture_boundaries.py
python scripts/check_basedpyright_errors.py
python scripts/git_hook_privacy_checks.py --staged
python scripts/agent_smoke_harness.py
python scripts/check_user_docs_links.py
```

**Documentation Updates:**
- Update `ARCHITECTURE.md` with new file structure
- Update `dev-docs/SOURCE_LAYOUT.md` if needed
- Add refactoring notes to `CHANGELOG.md`
- Update `dev-docs/MAINTENANCE_LOG.md`

### Phase 7: Final CCN Validation & Baseline (reduction done inline in Phases 3-5)

**Goal:** Confirm every function in the new mixin files is `CCN <= 20` and that no `functions` grandfather entries were needed. CCN **reduction is performed inline during each extraction phase** (see the mandatory CCN gate added to Phases 3, 4, and 5) — it is NOT deferred here. A developer who skipped the inline gate would be hard-blocked by the `git_hook_line_complexity.py` pre-commit hook at the Phase 3/4/5 commit, so this phase is the consolidated verification, not the place reduction first happens.

**Why this is necessary:** Newly staged `src/main_app_*.py` files are evaluated by the pre-commit hook. Appendix B shows current methods are already ≤ 20, so this phase is a **final regression sweep**, not the place where a large CCN redesign first happens. Still required: confirm no function crept over 20 during extraction and that `--generate-grandfather` did not silently add `functions` entries.

**Tasks:**
1. **Inventory (Appendix B, 2026-08-08):** zero methods at/above CCN 20. No reduction backlog; Phases 3–5 only needed the regression gate.
2. **Final CCN sweep:** run `lizard --CCN 20 src/main_app_*.py src/main.py`. Any function still > 20 means an inline-gate step was missed — return to that phase and reduce it (micro-commits + dedicated regression test) rather than grandfathering it.
3. **Verify no new grandfather entries were required:** after Phase 6's `--generate-grandfather`, confirm the `functions` map contains no `src/main_app_*.py` entries. If any remain, that indicates an unreduced function — fix it rather than ship the grandfather entry.
4. **Add/extend tests** for any extracted helper so behavior is pinned (ties to Coverage Targets baseline).

**Measurement commands:**
```bash
lizard --CCN 20 src/main_app_*.py src/main.py   # final sweep of all new + remaining files
python scripts/git_hook_line_complexity.py --all   # full repo gate (line + CCN)
```

**Acceptance:** Every function in `src/main_app_*.py` and `src/main.py` has `CCN <= 20` (no `functions` grandfather entries for the new files).

**Risks:**
- A missed inline-gate step leaves a >20 function for this phase to catch — mitigate with the per-phase `lizard` gate already embedded in Phases 3-5.
- Some methods may need structural redesign — flag these in Appendix B with a note and tackle in a focused sub-PR if they block.

**Mitigation:**
- **Micro-commits (recap of the per-phase rule):** reduce CCN in the smallest safe steps — extract one helper, add/run its dedicated regression test, commit, then move to the next method. Never batch a large CCN rewrite with the file move.
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
- **Establish the current test-coverage number before starting** (run `python -m pytest tests/ -v` with coverage, or `scripts/new_code_coverage.py`; the Sonar baseline `sonar-main-measures.json` / `coverage.xml` can be referenced). Success Criterion 2 is measurable against this baseline.
- **Docstring coverage — measured with `interrogate`:** Already pinned (`interrogate>=1.7.0` in `requirements-dev.txt`) and inventory-registered. Smoke-tested on `src/main.py` at **~98.8%** coverage. Use it as the CI-able metric for Success Criterion 4.
   - **Baseline (Phase 2):** capture `python -m interrogate src/main.py --fail-under 0` before refactoring and record the percentage as the baseline `B`.
  - **Per-phase gate:** run `python -m interrogate src/main_app_*.py src/main.py -f <B>` after each phase; the command fails if coverage drops below `B`, so regressions are caught immediately.
  - **Recommended flags:** `--ignore-init-method` (the `DICOMViewerApp.__init__` docstring is not the point) and `-e <other-paths>` to scope to the refactored files. Magic/`__` methods are not counted by default for coverage of the bodies, but public mixin methods should all carry docstrings.
  - **Success Criterion 4** becomes: post-refactor `interrogate` percentage `>= B` (no regression). Track the number in Appendix A if desired, but the tool output is authoritative.
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
   - Mitigation: Mixins are plain classes (no `QObject`); `QObject` is the **primary/first base** of `DICOMViewerApp(QObject, ...)` — PySide6 requires it listed first; document the exact base list and that earlier base wins; add the MRO/initialization test from Phase 2

2. **Circular Dependencies**
   - Risk: Mixins depend on each other
   - Impact: Import errors or runtime failures
   - Mitigation: Careful dependency analysis, import lazy loading

3. **Signal Wiring Breakage**
   - Risk: Extracted methods break signal connections
   - Impact: UI not responding to events
   - Mitigation: Signal wiring verification tests, integration tests; keep `Signal` declarations on `DICOMViewerApp` (PySide6 requires `Signal` on a `QObject` subclass)

4. **CCN Regression After Extraction**
   - Risk: Newly staged `main_app_*.py` files are CCN-checked; a move/helper extract that pushes any function > 20 blocks the commit (`BLOCK_CCN=20`). Current baseline is clean (Appendix B).
   - Impact: Hook blocks the commit until CCN is fixed
   - Mitigation: Per-phase `lizard --CCN 20` regression gate; fix only regressions; never grandfather new `functions` entries to pass the hook.

5. **State / Cross-Mixin Dependencies at Scale**
   - Risk: The plan references `DisplayConfigMixin`'s accessor-helper pattern. Refactoring every `self.<attr>` across 236 methods into `self._get_<attr>()` helpers is large, undocumented scope creep and risks behavior change.
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

All refactoring happens on a **dedicated feature branch**; `main` stays untouched until Phase 6 validation passes. If critical issues arise:

1. **Phase Rollback:** Revert individual phases using git (each phase is its own commit/PR)
2. **Complete Rollback:** Delete branch and return to main
3. **Data Safety:** No data migration involved, code-only change
4. **Branch Protection:** Keep main branch clean until validation complete (including the inline CCN reduction across Phases 3-5 and the Phase 7 final validation)

## Success Criteria

1. All files under 750 lines (up to 7 files if needed)
2. All tests passing (existing `tests/test_main_*.py` suite + new helper tests)
3. **No new `functions` grandfather entries for the mixin files** — every function `CCN <= 20` (Phase 7 complete, verified via `git diff` on the grandfather JSON)
4. Docstring coverage maintained or improved — measured automatically with `interrogate` (percentage `>=` the Phase 2 baseline `B`); the gate fails if coverage drops below `B`
5. No startup/orchestration regression — `python scripts/agent_smoke_harness.py` passes (no separate perf benchmark required for this facade split)
6. Documentation updated (ARCHITECTURE.md, SOURCE_LAYOUT.md, CHANGELOG.md, MAINTENANCE_LOG.md)
7. CI checks passing (line complexity, function CCN, architecture boundaries, basedpyright, privacy gate, agent smoke harness, user-docs links)

## Verification Commands

### After Each Phase
```bash
# Verify tests
python -m pytest tests/test_main_privacy_lifecycle.py -v
python -m pytest tests/test_main_signals_view.py -v

# Verify line counts + function CCN
python scripts/git_hook_line_complexity.py --all

# Verify architecture (after Phase 2 boundary update)
python scripts/check_architecture_boundaries.py

# Verify mixin typing (basedpyright; ImageViewer-style pragmas per Typing deviation)
python scripts/check_basedpyright_errors.py

# Verify docstring coverage (must stay >= baseline B)
python -m interrogate src/main_app_*.py src/main.py --ignore-init-method -f <B>
```

### Final Verification
```bash
# Full test suite
python -m pytest tests/ -v

# All hook checks
python scripts/git_hook_line_complexity.py --all
python scripts/check_repo_harness.py
python scripts/check_architecture_boundaries.py
python scripts/check_basedpyright_errors.py

# Docstring coverage (must stay >= baseline B)
python -m interrogate src/main_app_*.py src/main.py --ignore-init-method -f <B>

# Privacy gate (mandated before commit)
python scripts/git_hook_privacy_checks.py --staged

# Agent smoke harness (mandated before claiming done — guards app startup/signal wiring)
python scripts/agent_smoke_harness.py

# Documentation links
python scripts/check_user_docs_links.py
```

## Next Steps

1. ~~Review and approve this plan~~ (ready for Phase 0 as of 2026-08-08)
2. ~~**Complete Phase 0** (test safety net)~~ — **Done** 2026-08-08
3. ~~Phase 2 scaffolding (empty mixins, coverage omit, architecture boundaries)~~ — **Done** 2026-08-08
4. ~~Extraction Phases 3–5 using Appendix A; Phase 6 cleanup; Phase 7 CCN regression sweep~~ — **Done** 2026-08-08
5. Human commit on `refactor/main-split` when ready (see Progress ledger resume point)
6. ~~Update `ARCHITECTURE.md` / `SOURCE_LAYOUT.md` during Phase 6~~ — **Done** 2026-08-08 (Phase 6)
7. Create/update tracking note in `dev-docs/TO_DO.md` if desired (optional post-merge)

### Recorded baselines (fill during Phase 0)

| Metric | Value | Captured |
|--------|------:|----------|
| `interrogate` baseline **B** (`python -m interrogate src/main.py --ignore-init-method`) | **98.8%** | 2026-08-08 (pre-extraction) |
| `src/main.py` line coverage when temporarily un-omitted | **50%** | 2026-08-08 (Phase 0 Task 6; all `test_main_*` suites) |

## References

- `scripts/git_hook_line_complexity.py` - Line count and complexity (Lizard CCN) thresholds
- `scripts/line_complexity_grandfather.json` - Current grandfather list (`files` + `functions` maps)
- `requirements-dev.txt` (lizard>=1.23.0) - Complexity measurement dependency
- `src/utils/config/display_config.py` - Reference plain-mixin pattern (`DisplayConfigMixin`)
- `ARCHITECTURE.md` - Architecture boundaries and conventions
- `dev-docs/SOURCE_LAYOUT.md` - Source code layout documentation
- `tests/test_main_*.py` - Existing test coverage
- `tests/test_main_signals_view.py` - Signal-wiring test pattern (extend in Phase 0)
- `tests/conftest.py` - `qapp` fixture + `qt` marker for instantiating `DICOMViewerApp()`
- `tmp/test_coverage_assessment_20260808_004301.md` - Coverage analysis driving Phase 0 (the safety net)
- `src/utils/debug_flags.py` - Gate for any new debug tracing
- `requirements-dev.txt` (`interrogate>=1.7.0`) - Docstring coverage measurement
- `security/security-tool-inventory.json` - Tool inventory; `interrogate` entry required when added to `requirements-dev.txt` (see Phase 2 Task 8)
- `.coveragerc` / `.github/workflows/ci.yml` (`--cov-fail-under=80`) - Coverage trap addressed by the Coverage Strategy section
- `scripts/check_security_tool_inventory.py` - CI check that fails if a tool is in `requirements-dev.txt` but missing from the inventory
- `tmp/refactor_plan_assessment_20260808_010833.md` - Latest plan assessment (CI coverage trap, MRO terminology, security inventory, CCN sequencing)

## Appendix A — Complete Method→File Mapping (generated 2026-08-08)

Authoritative map of all **236** `DICOMViewerApp` methods (AST class-body count; an earlier `grep -cE "    def "` of 239 included nested defs). Generated from `src/main.py` via `ast` + `lizard` CCN. Each method has exactly one owning mixin; name collisions across mixins are prohibited.

### Line-budget estimate (method spans + overhead)

| File | Methods | Method lines | Est. total | Under 750? |
|------|--------:|-------------:|-----------:|:----------:|
| `src/main.py` | 8 | 135 | ~395 | yes |
| `src/main_app_initialization.py` | 12 | 413 | ~493 | yes |
| `src/main_app_subwindow_management.py` | 53 | 493 | ~573 | yes |
| `src/main_app_ui_and_files.py` | 91 | 473 | ~553 | yes |
| `src/main_app_display_settings.py` | 33 | 112 | ~192 | yes |
| `src/main_app_tag_roi.py` | 40 | 273 | ~353 | yes |

### Ownership notes

- `__init__`, `_log_startup_perf`, `run`, `eventFilter`, keyboard-focus / privacy-warn helpers, quit handler, and the single-shot timer helper stay on `DICOMViewerApp` in `src/main.py`.
- `tag_export_union_ready = Signal(...)` stays as a class attribute on `DICOMViewerApp`.
- Module-level `exception_hook`, `install_application_privacy_boundaries`, `main` stay in `src/main.py`.
- QA / MRI-compare facade methods are assigned to `UIHandlersMixin` (no separate QA mixin).
- Most methods are thin facades (`Body in core.*`); extraction is primarily a move, not a rewrite.
- All estimated file totals are under 750; keep the 6th-mixin escape hatch only if docstrings/imports push a file over.
- Refresh this appendix if `src/main.py` gains/loses methods before extraction starts.


### `src/main.py` — `DICOMViewerApp` (8 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 139–197 | `__init__` | 1 |
| 199–212 | `_log_startup_perf` | 2 |
| 214–216 | `_on_app_about_to_quit` | 1 |
| 218–233 | `_restart_single_shot_timer` | 2 |
| 235–240 | `eventFilter` | 2 |
| 242–266 | `run` | 2 |
| 268–271 | `_set_initial_keyboard_focus` | 2 |
| 273–280 | `_warn_if_privacy_off` | 2 |

### `src/main_app_initialization.py` — `InitializationMixin` (12 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 359–407 | `_init_core_managers` | 2 |
| 409–443 | `_init_main_window_and_layout` | 1 |
| 445–496 | `_init_view_widgets` | 1 |
| 498–618 | `_post_init_subwindows_and_handlers` | 12 |
| 620–654 | `_init_controllers_and_tools` | 1 |
| 663–684 | `_initialize_subwindow_managers` | 5 |
| 990–992 | `_initialize_handlers` | 1 |
| 1306–1328 | `_setup_ui` | 1 |
| 1330–1393 | `_connect_signals` | 2 |
| 1441–1443 | `_connect_all_subwindow_transform_signals` | 1 |
| 1445–1447 | `_connect_all_subwindow_context_menu_signals` | 1 |
| 1492–1494 | `_connect_focused_subwindow_signals` | 1 |

### `src/main_app_subwindow_management.py` — `SubwindowManagementMixin` (41 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 656–661 | `_build_managers_for_subwindow` | 1 |
| 686–716 | `_create_managers_for_subwindow` | 3 |
| 718–743 | `_refresh_slice_sync_group_indicators` | 7 |
| 745–747 | `_get_subwindow_dataset` | 1 |
| 749–751 | `_get_subwindow_slice_index` | 1 |
| 753–755 | `_get_subwindow_slice_display_manager` | 1 |
| 863–923 | `_sync_navigation_slider_for_subwindow` | 14 |
| 925–927 | `_get_subwindow_study_uid` | 1 |
| 929–931 | `_get_subwindow_series_uid` | 1 |
| 933–935 | `get_focused_subwindow_index` | 1 |
| 937–939 | `get_histogram_callbacks_for_subwindow` | 1 |
| 941–949 | `_update_focused_subwindow_references` | 3 |
| 951–961 | `has_shown_fusion_notification` | 1 |
| 963–971 | `mark_fusion_notification_shown` | 2 |
| 973–975 | `_update_right_panel_for_focused_subwindow` | 1 |
| 977–979 | `_update_left_panel_for_focused_subwindow` | 1 |
| 985–988 | `_redisplay_subwindow_slice` | 1 |
| 1019–1021 | `_clear_data` | 1 |
| 1023–1025 | `_close_files` | 1 |
| 1035–1050 | `_get_subwindow_assignments` | 1 |
| 1052–1074 | `_reset_fusion_handler_for_subwindow` | 5 |
| 1076–1087 | `_clear_subwindow` | 1 |
| 1089–1097 | `_reset_focused_subwindow_state_after_close` | 1 |
| 1099–1106 | `_on_clear_subwindow_content_requested` | 1 |
| 1108–1119 | `_close_series` | 1 |
| 1121–1132 | `_close_study` | 1 |
| 1134–1146 | `_reset_fusion_for_all_subwindows` | 2 |
| 1148–1155 | `_handle_load_first_slice` | 1 |
| 1157–1164 | `_get_rescale_params` | 1 |
| 1166–1182 | `_get_subwindow_rescale_params` | 2 |
| 1399–1407 | `_on_focused_subwindow_changed` | 2 |
| 1429–1431 | `_capture_subwindow_view_states` | 1 |
| 1433–1435 | `_restore_subwindow_views` | 1 |
| 1437–1439 | `_ensure_all_subwindows_have_managers` | 1 |
| 1484–1486 | `_assign_series_to_subwindow` | 1 |
| 1488–1490 | `_disconnect_focused_subwindow_signals` | 1 |
| 1994–1996 | `_refresh_overlay_all_subwindows` | 1 |
| 2221–2229 | `_update_histogram_for_focused_subwindow` | 2 |
| 2231–2234 | `_do_update_histogram_for_focused_subwindow` | 2 |
| 2354–2356 | `_get_focused_subwindow` | 1 |
| 2358–2381 | `_get_thumbnail_for_view` | 9 |

### `src/main_app_subwindow_management.py` — `MPRNavigationMixin` (12 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 757–759 | `_get_subwindow_mpr_pixel_array` | 1 |
| 761–763 | `_get_subwindow_mpr_thumbnail_pixel_array` | 1 |
| 765–776 | `_update_mpr_navigator_thumbnail` | 1 |
| 778–787 | `_clear_mpr_navigator_thumbnail` | 1 |
| 789–796 | `_update_floating_mpr_navigator_thumbnail` | 1 |
| 798–800 | `_on_mpr_detached` | 1 |
| 802–820 | `_on_mpr_thumbnail_clicked` | 5 |
| 822–834 | `_on_mpr_assign_requested` | 2 |
| 836–844 | `_on_mpr_clear_from_navigator_thumbnail` | 4 |
| 846–848 | `_sync_intensity_projection_widget_from_mpr_data` | 1 |
| 850–861 | `_get_subwindow_mpr_output_pixel_spacing` | 4 |
| 1790–1792 | `_on_save_mpr_as_dicom` | 1 |

### `src/main_app_ui_and_files.py` — `UIHandlersMixin` (56 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 1184–1186 | `_set_mouse_mode_via_handler` | 1 |
| 1274–1285 | `_on_undo_requested` | 6 |
| 1288–1299 | `_on_redo_requested` | 6 |
| 1417–1419 | `_update_3d_view_action_state` | 1 |
| 1465–1467 | `_on_window_slot_map_cell_clicked` | 1 |
| 1469–1471 | `_on_window_slot_map_popup_requested` | 1 |
| 1473–1482 | `_on_assign_series_requested` | 3 |
| 1512–1517 | `_on_series_navigation_requested` | 1 |
| 1531–1533 | `_on_assign_series_from_context_menu` | 1 |
| 1571–1602 | `_on_study_index_after_load` | 4 |
| 1620–1622 | `_on_show_file_from_series` | 1 |
| 1652–1654 | `_on_slice_location_lines_toggled` | 1 |
| 1656–1658 | `_on_slice_location_lines_same_group_only_toggled` | 1 |
| 1660–1662 | `_on_slice_location_lines_focused_only_toggled` | 1 |
| 1664–1666 | `_on_slice_location_lines_mode_toggled` | 1 |
| 1676–1678 | `_on_orientation_flip_h` | 1 |
| 1680–1682 | `_on_orientation_flip_v` | 1 |
| 1684–1686 | `_on_orientation_rotate_cw` | 1 |
| 1688–1690 | `_on_orientation_rotate_ccw` | 1 |
| 1692–1694 | `_on_orientation_rotate_180` | 1 |
| 1696–1698 | `_on_orientation_reset` | 1 |
| 1700–1702 | `_on_scale_markers_toggled` | 1 |
| 1704–1706 | `_on_direction_labels_toggled` | 1 |
| 1708–1710 | `_on_slice_slider_toggled` | 1 |
| 1712–1714 | `_on_slice_slider_placement_changed` | 1 |
| 1716–1718 | `_on_slice_slider_direction_changed` | 1 |
| 1720–1722 | `_on_scale_markers_color_changed` | 1 |
| 1724–1726 | `_on_direction_labels_color_changed` | 1 |
| 1728–1730 | `_on_show_instances_separately_toggled` | 1 |
| 1756–1760 | `_on_keyboard_shortcuts_requested` | 1 |
| 1837–1848 | `_qa_build_preflight_warnings` | 1 |
| 1850–1852 | `_qa_user_confirms_preflight` | 1 |
| 1854–1856 | `_show_qa_result_dialog` | 1 |
| 1858–1865 | `_export_qa_json` | 1 |
| 1867–1885 | `_qa_offer_extent_retry` | 1 |
| 1887–1907 | `_start_qa_worker` | 1 |
| 1925–1935 | `_start_mri_batch_worker` | 1 |
| 1937–1939 | `_note_mri_compare_dialog_closed` | 1 |
| 1945–1952 | `_show_mri_compare_result_dialog` | 1 |
| 1954–1960 | `_export_mri_compare_json` | 1 |
| 1966–1968 | `_on_export_customizations` | 1 |
| 1970–1972 | `_on_import_customizations` | 1 |
| 1998–2000 | `_on_annotation_options_applied` | 1 |
| 2006–2014 | `_on_window_changed` | 1 |
| 2016–2023 | `_on_mouse_mode_changed` | 1 |
| 2025–2032 | `_set_mouse_mode` | 1 |
| 2151–2163 | `_on_scroll_wheel_mode_changed` | 3 |
| 2165–2172 | `_on_context_menu_mouse_mode_changed` | 1 |
| 2174–2181 | `_on_context_menu_scroll_wheel_mode_changed` | 1 |
| 2183–2185 | `_on_rescale_toggle_changed` | 1 |
| 2236–2238 | `_on_reset_all_views` | 1 |
| 2244–2246 | `_on_transform_changed` | 1 |
| 2248–2250 | `_on_viewport_resizing` | 1 |
| 2252–2254 | `_on_viewport_resized` | 1 |
| 2256–2258 | `_on_pixel_info_changed` | 1 |
| 2260–2267 | `_on_arrow_key_pressed` | 1 |

### `src/main_app_ui_and_files.py` — `FileOperationsMixin` (35 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 1395–1397 | `_open_wl_preset_manager` | 1 |
| 1496–1498 | `_open_files` | 1 |
| 1500–1502 | `_open_folder` | 1 |
| 1504–1506 | `_open_recent_file` | 1 |
| 1508–1510 | `_open_files_from_paths` | 1 |
| 1519–1521 | `_build_flat_series_list` | 1 |
| 1567–1569 | `_open_settings` | 1 |
| 1604–1606 | `_open_study_index_search` | 1 |
| 1608–1610 | `_open_overlay_settings` | 1 |
| 1612–1614 | `_open_about_this_file` | 1 |
| 1616–1618 | `_get_file_path_for_dataset` | 1 |
| 1624–1626 | `_on_about_this_file_from_series` | 1 |
| 1628–1630 | `_get_current_slice_file_path` | 1 |
| 1632–1634 | `_update_about_this_file_dialog` | 1 |
| 1644–1646 | `_open_slice_sync_dialog` | 1 |
| 1740–1742 | `_open_overlay_config` | 1 |
| 1744–1746 | `_open_annotation_options` | 1 |
| 1748–1750 | `_open_quick_window_level` | 1 |
| 1752–1754 | `_open_quick_start_guide` | 1 |
| 1762–1764 | `_open_user_documentation_in_browser` | 1 |
| 1766–1768 | `_open_fusion_technical_doc` | 1 |
| 1778–1780 | `_open_export` | 1 |
| 1782–1784 | `_open_deep_anonymizer_export` | 1 |
| 1786–1788 | `_open_export_screenshots` | 1 |
| 1794–1799 | `_open_structured_report_browser` | 1 |
| 1801–1808 | `_on_export_cine_video` | 1 |
| 1810–1819 | `_resolve_focused_series_ordered_paths` | 1 |
| 1821–1835 | `_prompt_save_path` | 1 |
| 1909–1911 | `_open_acr_ct_phantom_analysis` | 1 |
| 1913–1915 | `_open_acr_ct_batch_analysis` | 1 |
| 1917–1919 | `_open_acr_mri_phantom_analysis` | 1 |
| 1921–1923 | `_open_nuclear_qc_analysis` | 1 |
| 1941–1943 | `_open_path_in_system_viewer` | 1 |
| 2269–2273 | `_on_right_mouse_press_for_drag` | 1 |
| 2275–2283 | `_on_window_level_drag_changed` | 1 |

### `src/main_app_display_settings.py` — `DisplayProjectionMixin` (18 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 1535–1537 | `_display_slice` | 1 |
| 1539–1541 | `_redisplay_current_slice` | 1 |
| 1551–1557 | `_on_projection_enabled_changed` | 1 |
| 1559–1561 | `_on_projection_type_changed` | 1 |
| 1563–1565 | `_on_projection_slice_count_changed` | 1 |
| 1668–1670 | `_on_smooth_when_zoomed_toggled` | 1 |
| 1732–1734 | `_refresh_overlays_after_privacy_change` | 1 |
| 1982–1984 | `_sync_all_overlay_managers_from_config` | 1 |
| 1986–1988 | `_cycle_overlay_detail_mode` | 1 |
| 1990–1992 | `_on_overlay_config_applied` | 1 |
| 2204–2212 | `_schedule_histogram_wl_only` | 2 |
| 2214–2219 | `_do_update_histogram_wl_only` | 2 |
| 2240–2242 | `_on_zoom_changed` | 1 |
| 2285–2287 | `_on_window_level_preset_selected` | 1 |
| 2289–2291 | `_update_zoom_preset_status_bar` | 1 |
| 2293–2295 | `_on_overlay_font_size_changed` | 1 |
| 2297–2299 | `_on_overlay_font_color_changed` | 1 |
| 2314–2316 | `_on_slice_changed` | 1 |

### `src/main_app_display_settings.py` — `SettingsLayoutMixin` (15 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 1409–1411 | `_update_series_navigator_highlighting` | 1 |
| 1413–1415 | `_refresh_series_navigator_state` | 1 |
| 1421–1423 | `_on_layout_changed` | 1 |
| 1425–1427 | `_on_main_window_layout_changed` | 1 |
| 1449–1451 | `_on_layout_change_requested` | 1 |
| 1453–1455 | `_on_expand_to_1x1_requested` | 1 |
| 1457–1459 | `_on_swap_view_requested` | 1 |
| 1461–1463 | `_refresh_window_slot_map_widgets` | 1 |
| 1523–1525 | `_on_series_navigator_selected` | 1 |
| 1527–1529 | `_on_series_navigator_instance_selected` | 1 |
| 1636–1638 | `_on_privacy_view_toggled` | 1 |
| 1640–1642 | `_on_slice_sync_toggled` | 1 |
| 1648–1650 | `_on_slice_sync_groups_changed` | 1 |
| 1962–1964 | `_apply_imported_customizations` | 1 |
| 2002–2004 | `_on_settings_applied` | 1 |

### `src/main_app_tag_roi.py` — `TagEditingMixin` (13 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 1003–1005 | `get_tag_export_union_snapshot` | 1 |
| 1007–1013 | `_drain_tag_export_union_worker` | 1 |
| 1015–1017 | `_schedule_tag_export_union_rebuild` | 1 |
| 1188–1190 | `_update_tag_viewer` | 1 |
| 1192–1214 | `_on_tag_edited` | 3 |
| 1216–1229 | `_undo_tag_edit` | 4 |
| 1231–1244 | `_redo_tag_edit` | 4 |
| 1246–1252 | `_update_undo_redo_state` | 3 |
| 1254–1272 | `_refresh_tag_ui` | 6 |
| 1736–1738 | `_open_tag_viewer` | 1 |
| 1770–1772 | `_open_tag_export` | 1 |
| 1974–1976 | `_on_export_tag_presets` | 1 |
| 1978–1980 | `_on_import_tag_presets` | 1 |

### `src/main_app_tag_roi.py` — `ROIWorkflowMixin` (27 methods)

| Lines | Method | CCN |
|------:|--------|----:|
| 981–983 | `_display_rois_for_subwindow` | 1 |
| 994–1001 | `_keyboard_delete_roi` | 4 |
| 1302–1304 | `_update_roi_list` | 1 |
| 1543–1545 | `_display_rois_for_slice` | 1 |
| 1547–1549 | `_display_measurements_for_slice` | 1 |
| 1774–1776 | `_open_export_roi_statistics` | 1 |
| 2034–2041 | `_set_roi_mode` | 1 |
| 2043–2050 | `_on_roi_drawing_started` | 1 |
| 2052–2059 | `_on_roi_drawing_updated` | 1 |
| 2061–2063 | `_on_roi_drawing_finished` | 1 |
| 2065–2072 | `_on_roi_clicked` | 1 |
| 2074–2076 | `_on_image_clicked_no_roi` | 1 |
| 2078–2085 | `_on_measurement_started` | 1 |
| 2087–2094 | `_on_measurement_updated` | 1 |
| 2096–2098 | `_on_measurement_finished` | 1 |
| 2100–2107 | `_on_measurement_delete_requested` | 1 |
| 2109–2113 | `_on_clear_measurements_requested` | 1 |
| 2115–2122 | `_on_roi_selected` | 1 |
| 2124–2131 | `_on_roi_delete_requested` | 1 |
| 2133–2140 | `_on_roi_deleted` | 1 |
| 2142–2149 | `_delete_all_rois_current_slice` | 3 |
| 2301–2303 | `_on_scene_selection_changed` | 1 |
| 2305–2312 | `_update_roi_statistics` | 1 |
| 2318–2325 | `_hide_measurement_labels` | 1 |
| 2327–2334 | `_hide_roi_labels` | 1 |
| 2336–2343 | `_hide_measurement_graphics` | 1 |
| 2345–2352 | `_hide_roi_graphics` | 1 |

## Appendix B — High-CCN Function Inventory (Lizard, 2026-08-08)

Command: `lizard --CCN 20 src/main.py`

**Result:** No thresholds exceeded. **Zero** `DICOMViewerApp` methods have CCN ≥ 20 (max observed class-method CCN = **14**). Average CCN ≈ 1.5 — consistent with `main.py` already being a thin facade over `core.*` modules.

| Method | CCN | Action |
|--------|----:|--------|
| _(none)_ | — | No reduction backlog. Per-phase gate remains: after each move, re-run `lizard --CCN 20` on the target file and keep CCN ≤ 20 (do not grandfather new `functions` entries). |

**Implication for Phases 3–5 / 7:** CCN reduction is **not** a major workstream. Treat the per-phase CCN gate as a **regression check**, not a redesign mandate. Earlier draft numbers (e.g. `_post_init_subwindows_and_handlers≈76`) were stale and are superseded by this inventory.
