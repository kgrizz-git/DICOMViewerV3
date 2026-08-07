# Tag Export UX Improvements

**Last updated:** 2026-08-07
**Status:** Draft plan — not yet executed

## Goal

Improve the Export DICOM Tags dialog with better UX: a top-level "Select All" checkbox for tags, studies collapsed by default at load, move the action from Tools to File, ensure presets save correctly under a search filter, display the count of selected tags, add a "Save" button to update the current preset, and auto-load the preset when selected from the dropdown.

## Current behavior (baseline)

Reference: `src/gui/dialogs/tag_export_dialog.py` (1415 lines)

- **Menu location:** `Tools > Export DICOM Tags...` (line 611, `main_window_menu_builder.py`).
- **Tag selection UI:** "Select All" / "Deselect All" push buttons only (no checkbox). `_toggle_all_tags` at line 679.
- **Studies tree:** Studies are expanded at load (`setExpanded(True)` at line 376, series at line 392). With many studies/instances, the dialog opens scrolled and noisy.
- **Preset save bug surface:** `_save_preset` (line 1154) calls `_update_selected_tags` which (line 919) collects **all checked tags regardless of visibility/filter state**. This is correct for the general case — but the user's mental model while a filter is active is "save what I see/checked." Since `_update_selected_tags` already ignores filter state, the existing code is *technically* correct; the risk is in the UI not communicating that clearly. **Verify** after changes.
- **No tag count label** visible to the user.
- **Preset load:** `_on_preset_selected` (line 1150) is a no-op `pass`; loading requires clicking the explicit "Load" button.
- **No "Save" (overwrite) button** — only "Save As..." which always prompts for a new name.

## Changes

### 1. Add a top "Select All" checkbox for the tag tree

**File:** `src/gui/dialogs/tag_export_dialog.py`

In `_create_tag_panel` (line 271), add a `QCheckBox` above the `tags_tree` (inside the tag panel, after the existing button row). Label: `"Select All"`. Use `setTristate(False)` so user clicks toggle Unchecked↔Checked only; `PartiallyChecked` is still reachable programmatically via `setCheckState(Qt.PartiallyChecked)` for the aggregate-state mirror (Qt does not emit user clicks that land on `PartiallyChecked` when tri-state is off, which is the desired behavior). Do **not** set `setTristate(True)` — that makes the user click cycle through `PartiallyChecked` (Unchecked → Partial → Checked → Unchecked), which combined with the "ignore PartiallyChecked on click" rule below makes the first click a visible no-op.

- Connect a **single** signal to a new `_on_select_all_tag_checkbox` handler. Use `clicked` for user-driven changes only; if programmatic state changes must also be handled (e.g., to re-derive aggregate state recursively and have the handler act on it), use `checkStateChanged` instead. **Do not wire both** `clicked` and a `stateChanged(int)` listener — a single user `click()` already emits both `clicked` and `checkStateChanged` (and the deprecated `stateChanged(int)`), so wiring more than one double-fires. Avoid the deprecated `stateChanged(int)` overload in PySide6.
- The handler sets the checkbox to `Checked` → call `_toggle_all_tags(True)`; `Unchecked` → `_toggle_all_tags(False)`. Ignore `PartiallyChecked` for click-driven state changes (with `setTristate(False)` the user cannot reach `PartiallyChecked` by clicking anyway).
- Add a method `_refresh_select_all_checkbox_state` that recomputes the aggregate state of all **visible exportable leaf-tag items** (defined precisely in the "Why visible leaves" paragraph below — **not** the same set as `_update_selected_tags`, which by design walks all checked tag-bearing nodes regardless of visibility; see `tag_export_dialog.py:919`) and sets the checkbox accordingly (without triggering its own signal loop — use `blockSignals`). Call it from `_on_tag_selection_changed`, `_toggle_all_tags`, `_load_preset`, and after `_filter_tags` (so the checkbox state tracks what the user currently sees). For displayed group/SQ/Item rows, keep recomputing ancestor tri-state (via `_update_ancestors_check_state`) so those headers reflect their visible descendants — but aggregate the **top checkbox** from visible exportable leaves, not from top-level groups.
- **Update `_toggle_all_tags`** so it selects or clears **only that same visible leaf-tag set** (not merely visible top-level groups / every visible descendant). After mutating leaf check states under `blockSignals`, recompute ancestor tri-state for displayed group/SQ/Item rows via `_update_ancestors_check_state`, then call `_update_selected_tags` / `_refresh_select_all_checkbox_state` / `_refresh_tag_count_label` as today. Hidden leaves must remain untouched so a filtered Select All cannot silently rewrite off-screen selections. Sequence/Item parent rows stay independently checkable for summary-column export; Select All does not force those parents on or off.
- **Critical — post-rebuild sync:** The tag tree is rebuilt by `_refresh_tag_tree()` / `_render_tag_tree()` when "Include Private Tags" or "Include sequences" is toggled, and on initial load (line 475, line 535). After any tree rebuild, the checkbox and count label MUST be refreshed. Add a call to `_refresh_select_all_checkbox_state()` and `_refresh_tag_count_label()` at the end of `_render_tag_tree()` (or wrap `_refresh_tag_tree` to call them). Without this, the checkbox/label go stale after toggling private-tags or sequences.
- **Filter-aware tri-state:** `_filter_tags()` (line 751) only hides/shows items; it does NOT recompute parent tri-state after visibility changes. Before reading aggregate state in `_refresh_select_all_checkbox_state`, walk affected ancestors and call `_update_ancestors_check_state` so that group check states reflect only visible descendants. Otherwise the top checkbox can show `Checked` when a group's checked descendants are all hidden.
- Keep the existing "Select All" / "Deselect All" push buttons (they remain useful for accessibility and power users). Both buttons must call the updated `_toggle_all_tags` so push-button and top-checkbox paths stay on the same visible-leaf set; then refresh via `_refresh_select_all_checkbox_state`.

**Why visible exportable leaves (precise definition):** A "leaf" in the export tree is a row whose `metadata_row_kind(tag_data) == "element"` (see `src/gui/metadata_table_model.py:104`) — i.e., neither an `"item"` parent nor a `"sequence"` parent. **Do not** define a leaf as "any item whose `UserRole` carries a tag string": `_build_export_tag_tree_item` (`tag_export_dialog.py:618`) sets `UserRole = tag_str` on **every** node including `"sequence"` and `"item"` parents, so that rule would aggregate SQ/Item intermediate nodes too. Tree items do **not** store `tag_data` on the item; resolve kind by looking up `tag_str = item.data(0, UserRole)` in the currently rendered union dict (`_tag_union_merged_full` or `_tag_union_merged_sequences`, whichever drove the last `_render_tag_tree`), then call `metadata_row_kind(tag_data)`. (Optional optimization: stash `row_kind` on the item at build time under a dedicated role such as `UserRole + 2` — do **not** overload `UserRole + 1`, which already stores large-sequence leaf counts.) **Visible** = `not item.isHidden()` (filter respects `_filter_tags`). The shared set used by both `_refresh_select_all_checkbox_state` and `_toggle_all_tags` is therefore: every reachable tree item where `metadata_row_kind(...) == "element"` AND `not item.isHidden()`. This is **deliberately narrower** than `_update_selected_tags` (which intentionally includes hidden and non-leaf nodes for export). Benefit: Select All / Deselect All and the top checkbox stay consistent under filters; a single visible unchecked leaf → top checkbox shows `PartiallyChecked`; hidden tags are never rewritten by Select All.

### 2. Studies collapsed at load

**File:** `src/gui/dialogs/tag_export_dialog.py`

In `_populate_series`:
- Line 376: change `study_item.setExpanded(True)` → `study_item.setExpanded(False)`.
- Line 392: change `series_item.setExpanded(True)` → `series_item.setExpanded(False)`.

This makes the initial dialog compact. Users expand the studies/series they care about. No behavioral change to selection or export — only the initial tree expansion state.

### 3. Move Export Tags from Tools to File menu

**File:** `src/gui/main_window_menu_builder.py`

- Remove lines 611–614 (the `tag_export_action` in the Tools menu).
- Add a new action in the File menu. Place it in the export group, after `save_mpr_dicom_action` (line 125) and before the separator at line 127. This groups it with the other export actions (Export, De-identify Export, Screenshots, Cine, Save MPR).
- Keep the shortcut `Ctrl+Shift+T` and the signal connection (`main_window.tag_export_requested.emit`).
- **No signal changes** — only the menu location changes. The signal `tag_export_requested` and its wiring in `app_signal_wiring.py:85` are untouched.

**Keyboard shortcuts dialog** (`src/gui/dialogs/keyboard_shortcuts_dialog.py`): update the section label at line 106 from `"DICOM Tags"` (still fine) — no change needed since the shortcut label is menu-agnostic.

**Update user docs:** Check `user-docs/` for any screenshots or menu references that show "Export Tags" under Tools and update them.

### 4. Ensure tag export presets save correctly (especially when filtered)

**File:** `src/gui/dialogs/tag_export_dialog.py`

The existing `_save_preset` (line 1154) already calls `_update_selected_tags` (line 908), which iterates **all** checked items regardless of filter visibility (line 919 comment). This is the correct behavior: a preset should capture all explicitly-checked tags, not just the visible subset.

- **Add a clarifying comment** in `_update_selected_tags` reinforcing that filter state does not affect the collected tags (for future maintainers).
- **Add a test** that:
  1. Populates the tree with tags.
  2. Applies a search filter that hides some checked tags.
  3. Saves a preset.
  4. Asserts the saved preset contains all checked tags, including the hidden ones.
  5. Clears the filter, reloads the preset, and asserts the checked state is restored.

This guards against a regression where someone refactors `_update_selected_tags` to respect visibility.

### 5. Show total number of tags selected for export

**File:** `src/gui/dialogs/tag_export_dialog.py`

Add a `QLabel` near the tag tree (e.g., bottom of the tag panel or next to the "Export Tags..." button) that shows the selected-tag count with correct English pluralization.

- Initialize the label in `__init__` (around line 197).
- Update it from a new method `_refresh_tag_count_label` that reads `len(self.selected_tags)`.
- Call `_refresh_tag_count_label` from `_update_selected_tags` (at the end, line 925), and from `_load_preset` after `_update_selected_tags`, and from `_toggle_all_tags`, and from `_on_tag_selection_changed`.
- Label copy: `0` → `"No tags selected"`; `1` → `"1 tag selected"` (singular); `n > 1` → `"{n} tags selected"` (plural).
- Position: place it left-aligned in the tag panel bottom row, or as a status tip on the export button. Preferred: a dedicated label below the tree or above the export button row. Place it in the bottom button layout next to the export button: `"42 tags selected  |  Export Tags..."`.

### 6. Add "Save" button to update the current preset

**File:** `src/gui/dialogs/tag_export_dialog.py`

In `_create_tag_panel`, next to the existing "Save As..." button (around line 296), add a **"Save"** button.

- New method `_save_current_preset`:
  1. Reads the current `preset_combo.currentText()`.
  2. If it is `"(No preset)"` or empty — fall back to `_save_prompt` (which is `_save_preset`) so the user can name it. Optionally show a message: "No preset selected. Please select a preset first or use Save As..."
  3. Otherwise, call `self._update_selected_tags()` first (synchronize `self.selected_tags` with the live tree), then call `self.config_manager.save_tag_export_preset(current_name, self.selected_tags)` directly (overwrite, no prompt). **Rationale:** `self.selected_tags` is normally refreshed by `_on_tag_selection_changed` (line 879 calls `_update_selected_tags`), but `_toggle_all_tags` (line 681) and `_load_preset` (line 1238) mutate check state under `blockSignals(True)`, which suppresses `_on_tag_selection_changed`. Mirrors the existing `_save_preset` step at line 1162. Do **not** describe this as "flushing pending `itemChanged` events" — Qt direct connections are synchronous on the same thread and there are no pending events; the issue is `blockSignals` suppressing the refresh path.
  4. Shows `QMessageBox.information` "Preset '{name}' updated."
  5. Does NOT refresh the combo list or change selection (the preset name is unchanged; only its contents changed).
- Connect the "Save" button to `_save_current_preset`.
- Update the tooltip/statusTip to clarify: "Save As..." creates a new preset; "Save" overwrites the currently selected preset.

### 7. Auto-load preset on dropdown selection

**File:** `src/gui/dialogs/tag_export_dialog.py`

In `_on_preset_selected` (line 1150), replace the `pass` with:

```python
def _on_preset_selected(self, preset_name: str) -> None:
    """Auto-load the preset when selected from the dropdown."""
    if not preset_name or preset_name == _ITEM_NO_PRESET:
        return
    if not self.config_manager:
        return
    self._load_preset_by_name(preset_name)
```

Refactor `_load_preset` (line 1197) to extract the core logic into `_load_preset_by_name(preset_name: str)`:

- `_load_preset`: reads `preset_combo.currentText()`, validates it, then calls `_load_preset_by_name(name)`.
- `_load_preset_by_name`: contains the existing body of `_load_preset` (lines 1212–1263) — fetches preset tags, merges missing into active union, checks nodes, recomputes tri-state, applies filter, updates selection, refreshes count label.
- Both `_load_preset` and `_on_preset_selected` call `_load_preset_by_name`.
- Do **not** add a `_loading_preset` re-entrancy flag. `_load_preset_by_name` does not change `preset_combo` selection (it only reads `currentText()` on the manual Load path and is passed a name on the auto-load path), so there is no re-entrant `textActivated`/`currentTextChanged` path to guard. If a genuine re-entrant path is later identified (e.g., `_load_preset_by_name` starts calling `preset_combo.setCurrentIndex`), add an early-return guard and ensure the flag is cleared in a `finally` block — do not add an `assert` against the flag.

**Important — signal choice:** Disconnect `currentTextChanged` → `_on_preset_selected` and connect `preset_combo.textActivated` → `_on_preset_selected`. In Qt 6 / PySide6, `QComboBox.activated` carries only the **index**; the string form is the separate `textActivated(QString)` signal (the Qt 5 `activated(QString)` overload was removed in Qt 6). `textActivated` fires only on user selection (mouse/keyboard), not on `setCurrentIndex`, which is what we want for auto-load. Update line 284 accordingly.

**Important — no modal on auto-load:** `_load_preset()` currently shows `QMessageBox.information("Preset Loaded", ...)` (line 1262). Auto-load on dropdown selection must NOT show a modal on every pick. Solution: add a `show_feedback: bool = True` parameter to `_load_preset_by_name`. `_load_preset` (manual Load button) calls `_load_preset_by_name(name, show_feedback=True)`. `_on_preset_selected` (auto-load) calls `_load_preset_by_name(name, show_feedback=False)`.

## Files to modify

| File | Change |
|------|--------|
| `src/gui/dialogs/tag_export_dialog.py` | Add top "Select All" checkbox; collapse studies; add tag count label; add "Save" button; auto-load preset on `textActivated`; refactor `_load_preset` → `_load_preset_by_name(show_feedback)`; post-rebuild sync for checkbox+count; filter-aware tri-state recompute; clarifying comments |
| `src/gui/main_window_menu_builder.py` | Move `tag_export_action` from Tools menu to File menu (export group) |
| `src/gui/dialogs/keyboard_shortcuts_dialog.py` | No change (shortcut is menu-agnostic) — verify only |
| `user-docs/USER_GUIDE_EXPORT.md` | Update menu reference at line 69 from "Tools > Export Tags" to "File > Export Tags" |
| `tests/gui/test_tag_export_dialog_presets_slice.py` | Add tests for: select-all checkbox state sync; collapsed-at-load; preset save with filter; tag count; save-current-preset; auto-load on selection |

## Files NOT changed (verify only)

- `src/gui/main_window.py` — `tag_export_requested` signal unchanged.
- `src/gui/app_signal_wiring.py` — wiring unchanged.
- `src/gui/dialog_coordinator.py` — dialog construction unchanged.
- `src/gui/actions/dialog_actions.py` — action unchanged.
- `src/main.py` — `_open_tag_export` unchanged.
- `src/utils/config/tag_export_config.py` — preset storage logic unchanged (no schema change).

## Testing plan

### New tests (`tests/gui/test_tag_export_dialog_presets_slice.py` or new file)

1. **`test_top_select_all_checkbox_reflects_state`**: Check some (not all) tags → checkbox shows `PartiallyChecked`. Check all → `Checked`. Uncheck all → `Unchecked`.
2. **`test_top_select_all_checkbox_toggles`**: Click the checkbox (checked) → all visible tags checked. Click again (unchecked) → all unchecked.
3. **`test_top_select_all_respects_filter`**: Apply a filter hiding some tags. Click top "Select All" → only visible tags checked. Clear filter → state is partial.
4. **`test_studies_collapsed_at_load`**: After `_populate_series`, assert all study items `isExpanded() == False` and series items `isExpanded() == False`.
5. **`test_preset_save_includes_hidden_checked_tags`**: Check several tags, apply a filter hiding some, save preset, reload, assert all originally-checked tags are present and checked.
6. **`test_tag_count_label_updates`**: Initially "No tags selected". Check one tag → "1 tag selected" (singular). Uncheck → "No tags selected". Check two or more → "{n} tags selected" (plural).
7. **`test_save_current_preset_overwrites`**: Save preset "X" with tags [a, b]. Change selection to [c, d]. Click "Save" (with "X" selected). Reload "X". Assert preset "X" now contains exactly [c, d] — i.e., Save **replaces** the preset contents with the current selection (overwrite, not merge).
8. **`test_save_current_preset_no_selection_falls_back`**: With "(No preset)" selected, click "Save" → falls back to "Save As..." prompt.
9. **`test_auto_load_preset_on_text_activated`**: Select preset from combo via the **`textActivated`** signal — `QComboBox.activated` only carries the `int` index in Qt 6 (the `activated(QString)` overload was removed in Qt 6 in favor of `textActivated`, which carries the string). Emit or spy on `textActivated` when verifying `_on_preset_selected`, asserting `selected_tags` matches the preset without clicking "Load". Executable assertion that auto-load is wired to the right signal: emit `activated(index)` separately and assert `selected_tags` is unchanged (i.e., auto-load is **not** driven by the index-int `activated`).
10. **`test_programmatic_combo_change_no_auto_load`**: Call `preset_combo.setCurrentIndex(...)` → assert auto-load does NOT fire (because `textActivated` is not fired by programmatic index changes).
11. **`test_checkbox_count_reset_after_rebuild`**: Toggle "Include Private Tags" or "Include sequences" (which triggers `_render_tag_tree`). Assert the top checkbox state and count label still reflect the current tree state correctly (not stale).
12. **`test_menu_export_tags_in_file_menu`**: Verify `main_window_menu_builder.py` has the export tags action in the File menu (not Tools). Lightweight test checking the action's parent menu or text.

### Existing tests to verify still pass

- `tests/gui/test_tag_export_dialog_presets_slice.py` — `test_construct_populates_series_and_tags`, `test_toggle_all_series_and_tags`, `test_filter_tags_hides_non_matches`, `test_load_presets_list_runs`.
- `tests/test_tag_export_dialog_sequences_checkbox.py` — sequences checkbox unaffected.
- `tests/test_tag_export_sequence_picker.py` — nested selection unaffected.
- `tests/test_tag_export_sequences_flag.py` — output correctness unaffected.
- `tests/test_tag_export_controller.py`, `tests/test_tag_export_writer.py`, `tests/test_tag_export_catalog.py` — unchanged.
- `tests/config/test_tag_export_config.py` — preset storage unaffected.
- `tests/core/test_customization_handlers.py` — import/export unaffected.

### Repository verification gate (required before claiming done)

Run all of the following from the project virtual environment (`source .venv/bin/activate` on macOS/Linux; `.venv\Scripts\activate` on Windows), per [`AGENTS.md`](../../../AGENTS.md):

| Check | Command |
|-------|---------|
| Python tests | `python -m pytest tests/ -v` |
| User-docs links | `python scripts/check_user_docs_links.py` |
| Repo harness | `python scripts/check_repo_harness.py` |
| Architecture boundaries | `python scripts/check_architecture_boundaries.py` |
| Agent smoke | `python scripts/agent_smoke_harness.py` |

Use approximately **10-minute timeouts** for full `pytest` and `pyright src/` runs. New tests added by this plan must pass on the venv interpreter before the plan is marked complete.

## Doc updates

- Add a section in the user docs (`user-docs/`) describing the new "Select All" checkbox, tag count, and Save/Save As distinction. Screenshots if applicable.
- Update any "Tools > Export Tags" menu references to "File > Export Tags".
- Update `CHANGELOG.md`: add a new section under either `## [Unreleased]` or a new version heading (`## [x.y.z]`) describing the dialog UX changes above. When adding a new version heading, **synchronize "Current version" near the top of `CHANGELOG.md` with `__version__` in [`src/version.py`](../../../src/version.py)** (per [`AGENTS.md`](../../../AGENTS.md) "Version / changelog / SemVer").

## Risk assessment

- **Low risk:** Menu relocation (pure UI, signal unchanged).
- **Low risk:** Studies collapsed at load (cosmetic, no selection logic change).
- **Medium risk:** Top "Select All" checkbox — must correctly respect filter visibility to avoid accidentally selecting hundreds of hidden tags. Mitigated by tests 3 and 5 above.
- **Medium risk:** Auto-load on `textActivated` — must not fire on programmatic changes. Mitigated by using `textActivated` (not `currentTextChanged`) and test 10.
- **Low risk:** Save button — purely additive; existing "Save As..." unchanged.
- **Low risk:** Tag count label — purely additive display.

## Out of scope

- Changing preset storage format or schema.
- Adding a "Select All" for the series tree (the existing push buttons are sufficient).
- Changing the export logic, writers, or controller.
- Changing the preset import/export file menu actions.
