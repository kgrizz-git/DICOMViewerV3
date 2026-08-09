# MainWindow Refactoring Plan

**Date:** 2026-08-09
**Status:** Draft (reviewed x2 + assessment)
**Target:** `src/gui/main_window.py` (1,777 lines, 75 methods)

## Interaction with POST_REVIEW_BUGFIXES_2026_08_08

No direct file overlap. The bugfix plan touches 10 coordinator/controller files;
this refactor touches `main_window.py` and creates new files. **Recommended order:**
land bugfix PR first (small, surgical, independent), then this refactor on a
separate branch. If done in the other order, the bugfix's `closeEvent` cleanup
and `MainWindowLayoutHelper` log fix still apply cleanly because they don't touch
the extracted paths.

Indirect coupling to be aware of:
- The refactor's overlay mixin restructures the signal-toggle methods that
  coordinators connect to (e.g., `privacy_view_toggled`, `scale_markers_toggled`).
  The mixin preserves the same `self.method()` API, so coordinator code is
  unaffected.
- The recent-files manager extracts `eventFilter`; the bugfix plan does not
  touch `eventFilter`, so no conflict.

## Problem

`MainWindow` is a god object: 1,777 lines managing ~15 unrelated concerns. Most methods
are small (5-10 lines), but the class accumulates state for toast messages, recent files,
fullscreen, theme, mouse mode, overlay options, series navigator, layout/splitter, and
the about dialog. This makes the file hard to navigate and risks merge conflicts.

## Refactoring Approach

Extract self-contained concerns into dedicated controllers/helpers. MainWindow keeps signal
declarations, `__init__`, and core layout. Each extracted module follows the existing
project pattern (e.g., `MainWindowStatusController` was already extracted this way).

**Import posture:** Each new module imports only stdlib, PySide6, sibling `gui/` modules,
and (for `ConfigManager` typing) `utils.config`/`config_manager`. No new `gui` → `main`
imports. No new entries in `dev-docs/architecture_boundary_baseline.txt`.

**Mixin typing note:** `MainWindowOverlayOptionsMixin` reads `self.<attr>` resolved at
runtime (e.g., `_privacy_action`, toolbar color actions, signals). Add
`if TYPE_CHECKING: from gui.main_window import MainWindow` with `self: MainWindow`
to keep static analysis useful, or add class-level annotations on the mixin with a
comment that they are satisfied by the host class.

## External contract checklist

These `MainWindow` attributes/methods are referenced from outside `main_window.py`
(via production code and `MagicMock` test stubs). All must remain reachable as
`self.<name>` on `MainWindow` after extraction:

- `show_toast_message` → `tests/test_series_navigation_controller.py`
- `set_fullscreen` → `tests/test_main_app_key_event_filter.py`
- `update_recent_menu` (public) → `file_operations_handler.py` (5×), `main_window_menu_builder.py`
- `get_current_mouse_mode` → `tests/core/test_subwindow_keyboard_focus_callbacks.py`
- `set_mouse_mode_checked`, `_on_mouse_mode_changed` → `tests/gui/test_mouse_mode_handler.py`
- `update_status`, `update_zoom_preset_status` → kept in MainWindow (status delegation)
- `_set_theme`, `_apply_theme` → kept in MainWindow
- `set_layout_mode` → kept in MainWindow
- `set_show_instances_separately_enabled`, `set_3d_view_actions_enabled` → overlay mixin must keep these
- `set_*_checked` family (overlay options) → overlay mixin must keep these, no renames
- Signals: `privacy_view_toggled`, `smooth_when_zoomed_toggled`, `layout_changed`,
  `open_file_requested`, `open_files_from_paths_requested`, `export_requested`

## Extractions

### 1. Extract `_show_about` to a standalone dialog builder
**File:** `src/gui/dialogs/about_dialog.py` (add to existing dialogs directory)
**Lines removed from MainWindow:** ~125 (L802-926)
**Methods moved:** `_show_about`, `_on_about_disclaimer_clicked`
**Interface:** `show_about(parent, config_manager, on_disclaimer: Callable[[], None] | None = None)`.
MainWindow calls `show_about(self, self.config_manager, on_disclaimer=self._show_disclaimer)`.
The disclaimer callback handles the `disclaimer://` anchor click. `_show_disclaimer`
stays in MainWindow (it's also called from `main_window_menu_builder.py:700`).
**Risk:** Low — pure dialog construction, disclaimer callback wired explicitly.

### 2. `MainWindowToastController` — toast messages
**File:** `src/gui/main_window_toast_controller.py`
**Lines removed from MainWindow:** ~80 (L371-448)
**State moved:** `_toast_label`, `_toast_effect`, `_toast_timer`, `_toast_animation`
**Methods moved:** `show_toast_message`
**Interface:** Controller takes `parent QWidget` in constructor. MainWindow calls
`self._toast.show(message, ...)` instead of `self.show_toast_message(...)`.
**Risk:** Low — fully self-contained, no signal wiring.

### 3. Consolidate mouse-mode action mapping (in-place)
**File:** `src/gui/main_window.py` (in-place refactor)
**Lines affected:** ~160 gross, ~130 net (L928-1088)
**Problem:** `_on_mouse_mode_changed`, `set_mouse_mode_checked`, and
`get_current_mouse_mode` contain three near-identical 12-branch if/elif chains
mapping mode strings ↔ QAction attributes.
**Fix:** Add a `_mouse_mode_action_map: dict[str, QAction]` built once in
`__init__` (after toolbar is built). A reverse `_mouse_mode_action_reverse:
dict[QAction, str]` for `get_current_mouse_mode`. All three methods use the
maps instead of if/elif. Add a unit test asserting
`map[reverse_map[mode]] == mode` for all 12 modes.
**Risk:** Low — pure mechanical dedup, no behavioral change.

### 4. `MainWindowRecentFilesManager` — recent file menu + context menu
**File:** `src/gui/main_window_recent_files_manager.py`
**Lines removed from MainWindow:** ~145 (L1167-1311)
**State moved:** `recent_menu` reference
**Methods moved:** `_update_recent_menu`, `_remove_recent_file`, `_move_recent_file`,
`_open_edit_recent_list_dialog`
**Preferred eventFilter approach:** Manager installs its own eventFilter on the
`recent_menu` QMenu in its constructor (replacing the current
`main_window.recent_menu.installEventFilter(main_window)` from
`main_window_menu_builder.py:88`). MainWindow's `eventFilter` override is then
**removed entirely** — the entire body only serves the recent-menu context menu.
**Public wrapper:** MainWindow keeps a thin `update_recent_menu()` that delegates
to `self._recent_files.update()` for backward compatibility (called 5× from
`file_operations_handler.py`, 1× from `main_window_menu_builder.py`).
**Risk:** Low-Medium with Phase 0 test `test_main_window_recent_files.py`;
Medium without.

### 5. `MainWindowFullscreenManager` — fullscreen enter/exit/chrome
**File:** `src/gui/main_window_fullscreen_manager.py`
**Lines removed from MainWindow:** ~150 (L1497-1604 + fullscreen branch of L1739-1777)
**State moved:** `_fullscreen_snapshot`, `_fullscreen_transitioning`
**Methods moved:** `_take_fullscreen_snapshot`, `_apply_fullscreen_chrome_hidden`,
`_restore_fullscreen_chrome`, `set_fullscreen`, fullscreen branch of `changeEvent`
**Interface:** Controller takes `parent` (the QMainWindow). Exposes
`enter_fullscreen()`, `exit_fullscreen()`, `is_fullscreen -> bool`,
`handle_change_event(event) -> bool` (returns True if consumed),
`restore_on_close()`.
**Must ship together:** Extraction #5 + `closeEvent` update + `changeEvent` update.
`handle_change_event` must return `False` for non-fullscreen `WindowStateChange`
events so `MainWindow.changeEvent` can fall through to `super().changeEvent(event)`.
**Risk:** Medium with Phase 0 test extension; Medium-High without.

### 6. Extract overlay + view-option helpers to a mixin
**File:** `src/gui/main_window_overlay_options.py` (mixin class)
**Lines removed from MainWindow:** ~230 (L590-785 + L1099-1145)
**Methods moved:**
- Toggle handlers: `_on_privacy_toggled`, `_on_privacy_view_toggled`,
  `_on_smooth_when_zoomed_toggled`, `_on_scale_markers_toggled`,
  `_on_direction_labels_toggled`, `_on_show_instances_separately_toggled`
- Check-state sync: `set_smooth_when_zoomed_checked`, `set_scale_markers_checked`,
  `set_direction_labels_checked`, `set_slice_slider_checked`,
  `set_slice_slider_placement_checked`, `set_slice_slider_direction_checked`,
  `set_show_instances_separately_checked`, `set_show_instances_separately_enabled`,
  `set_3d_view_actions_enabled`
- Slice location lines: `set_slice_location_lines_*` (4 methods)
- Privacy UI: `_update_privacy_action`, `_update_privacy_mode_button` (alias)
- Font/color pickers: `_on_font_size_decrease`, `_on_font_size_increase`,
  `adjust_overlay_font_size`, `_on_font_color_picker`,
  `_on_scale_markers_color_picker`, `_on_direction_labels_color_picker`
**Interface:** `MainWindowOverlayOptionsMixin` mixed into `MainWindow`.
Each method accesses `self.config_manager` and signals on `self`.
**Do not rename** any of these methods — they are contract-surface for collaborators.
**Risk:** Low — all methods follow the same pattern (blockSignals, set checked,
emit signal). Mixin keeps them callable as `self.method()` with no API change.

## What stays in MainWindow

- Signal declarations (~80 lines) — canonical, must stay visible
- Class-level QAction/QWidget attribute declarations (~90 lines) — reference inventory
- `__init__` (~50 lines) — orchestration
- `_create_central_widget` (~73 lines) — layout construction
- `_apply_theme` / `_set_theme` (~65 lines) — tightly coupled to config + stylesheet
- `_on_splitter_moved` / `_toggle_left_pane` / `_toggle_right_pane` (~70 lines)
- `set_series_navigator` / `toggle_series_navigator` (~70 lines)
- `set_window_slot_map_*` (~30 lines)
- `dragEnterEvent` / `dropEvent` (~60 lines)
- `_on_layout_changed` / `set_layout_mode` (~40 lines)
- `_show_disclaimer` (~4 lines) — also called from menu builder
- `closeEvent` (~30 lines, delegates fullscreen restore to manager)
- `changeEvent` (~15 lines, delegates fullscreen branch to manager)
- Status bar delegation (~30 lines) — already thin
- `update_recent_menu` (~5 lines, thin delegate to recent-files manager)
- No `eventFilter` override (removed after extraction #4)

**Estimated final MainWindow:** ~1,050-1,100 lines (down from 1,777)
Net removals: 125 + 80 + 130 + 145 + 150 + 230 = ~860 lines.

## Documentation updates (in same PR)

1. `dev-docs/SOURCE_LAYOUT.md` — add new modules to `src/gui/` tree + controllers table
2. `dev-docs/MAINTENANCE_LOG.md` — record the refactor entry
3. `CHANGELOG.md` — add "Internal: split MainWindow for maintainability" if release
   cut is after this lands; otherwise MAINTENANCE_LOG is sufficient
4. Move this plan to `dev-docs/plans/completed/` when done

## Phase 0 — characterization tests

Add these **before** extraction #1 on a separate commit. They test current behavior;
once green, they become the regression net for the whole batch. Use the shared
`tests/conftest.py` `qapp` fixture (not a local one), `@pytest.mark.qt`,
`QT_QPA_PLATFORM=offscreen`.

### 1. `tests/test_main_window_about_dialog.py`
Open `MainWindow`, call `_show_about()`, assert:
- Dialog `windowTitle` is `"About DICOM Viewer V3"`
- Dialog is visible
- Body contains version string (from `src/version.py`) and `disclaimer://` anchor
- Disclaimer link callback fires with `force_show=True` (monkeypatch
  `DisclaimerDialog.show_disclaimer`)

### 2. `tests/test_main_window_recent_files.py`
Use a temp `ConfigManager` with 3 recent entries. Assert:
- `_update_recent_menu()` builds N actions matching config order
- `update_recent_menu()` (public wrapper) has same effect
- Right-click context menu offers "Remove" + "Move up/down"
- Invoking them updates config + re-renders
- `_open_edit_recent_list_dialog()` opens the dialog (assert visible + cancel)

### 3. `tests/test_main_window_mouse_mode_map.py`
For each of 12 mode strings, assert:
- `set_mouse_mode_checked(mode)` makes exactly one QAction checked
- `get_current_mouse_mode()` returns that mode
- After extraction: `reverse_map[action] == mode ↔ map[mode] == action` for all 12

### 4. Extend `tests/test_main_window_fullscreen.py`
Add two cases:
- (a) Enter fullscreen, send `closeEvent` while in fullscreen; assert snapshot cleared
- (b) Fullscreen exit restores chrome (splitter sizes, navigator, toolbar)

### 5. `tests/test_main_window_overlay_options.py`
For each of the 6 toggles + slice_location_lines_*:
- `set_*_checked(b)` flips the action's checked state
- Signal `*_toggled` is emitted with new value
- `blockSignals(True)` path does NOT emit
 Font: `adjust_overlay_font_size(+1)` then `(-1)` returns to original.
Also test `set_3d_view_actions_enabled(enabled, tooltip)`: assert it enables/disables the action and sets the tooltip.

### 6. (Optional) `tests/test_main_window_overlay_options_contract.py`
Non-Qt contract test: `hasattr(MainWindow, "privacy_view_toggled")` and all
method names from the external contract checklist.

## Extraction order

1. `_show_about` → about dialog (standalone, disclaimer callback)
2. Toast controller (self-contained, no signal wiring)
3. Mouse-mode action map (in-place; includes `get_current_mouse_mode`)
4. Recent files manager (manager installs own eventFilter; MainWindow's removed)
5. Fullscreen manager + `closeEvent` + `changeEvent` (must ship together)
6. Overlay options mixin (largest, but mechanical; includes font/color pickers)

Each extraction is a separate commit on this branch so each can be reverted independently.

## Verification

After Phase 0:
1. `python -m pytest tests/ -v` — full suite (baseline green)

After each extraction:
1. `python -m pytest tests/ -v` — full suite (regression signal)
2. `python scripts/check_architecture_boundaries.py` — no new violations
3. `python scripts/agent_smoke_harness.py` — import + fixture check
4. Manual: open app, verify theme toggle, privacy toggle, mouse mode switching,
   recent files menu (including right-click context menu), fullscreen enter/exit,
   toast messages, about dialog (including disclaimer link), drag/drop a folder
