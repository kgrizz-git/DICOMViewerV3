# Swap in All Layouts + 2×2 Window-Assignment Thumbnail – Implementation Plan

This plan covers two TO_DO items:

1. **Swap in all layouts with focus unchanged** – Make swap available in 1x1, 1x2, and 2x1 (not only 2x2), and ensure focus does not follow the swapped view; panels (ROI list/statistics, frame slider, tag browser) stay tied to the focused window and may need updates.
2. **2×2 thumbnail for window assignments** – Add a small 2×2 indicator so users can see which view is in which grid position even when not in 2x2 layout (placement options: far right of series navigator with separator, or only when opening the Swap context submenu).

**References:**
- TO_DO: `dev-docs/TO_DO.md` (lines 21–22)
- Existing plan: `dev-docs/plans/VIEW_SLOT_LAYOUT_AND_SWAP_PLAN.md`
- Layout/slot state: `src/gui/multi_window_layout.py` (`slot_to_view`, `swap_views`, `_arrange_subwindows`)
- Swap handler: `src/main.py` (`_on_swap_view_requested` – currently no-ops when not 2x2)
- Focus-driven panels: `src/core/subwindow_lifecycle_controller.py` (`update_right_panel_for_focused_subwindow`, `update_left_panel_for_focused_subwindow`)
- Context menu Swap: `src/gui/image_viewer.py` (Swap submenu, `swap_view_requested`)

---

## Part A: Swap in All Layouts, Focus Stays on Current Window

### A.1 Goal

- **Current:** Swap is only effective in 2x2; in 1x1/1x2/2x1 the handler returns without doing anything.
- **Target:**
  - Swap updates `slot_to_view` in **all** layouts (1x1, 1x2, 2x1, 2x2).
  - **Focus does not change** – it stays on the window that had focus (the “current” window). Content (ROI list/statistics, frame slider, tag browser, etc.) continues to reflect the focused view.
  - In 1x2/2x1, after a swap the visible panes are re-arranged so the same logical row/column (by slot) is shown, with the new slot-to-view mapping.
  - No code path may assume “focused view = first visible slot” or “slot 0 = focused”; all panel data must be keyed by **focused subwindow** (view index or container), not by layout position.

### A.2 Design

- **`swap_views(view_index_a, view_index_b)`**  
  - Already updates `slot_to_view` regardless of layout.  
  - Today it only calls `_arrange_subwindows("2x2")` when `current_layout == "2x2"`.  
  - **Change:** After updating `slot_to_view`, also call `_arrange_subwindows(self.current_layout)` when `current_layout` is `"1x2"` or `"2x1"`. For 1x1, no re-arrangement is needed (only one container is shown, and it is chosen by focused view index).

- **Focus:** Do **not** call `set_focused_subwindow` in the swap path. The handler already uses the menu-emitting view as source and does not change focus; keep it that way.

- **Panel content (ROI list, ROI statistics, frame slider, tag browser, etc.):**  
  - These are already driven by `get_focused_subwindow()` / `focused_subwindow_index` and updated in `update_right_panel_for_focused_subwindow` / `update_left_panel_for_focused_subwindow`.  
  - After swap we do **not** want to trigger a “focus changed” that would refresh from the wrong view. Since we are not changing focus, no extra “update panels” call is strictly required; the only risk is code that infers “current” from layout position (e.g. “first visible container”) instead of from focus. The plan therefore includes an **audit** to ensure every place that drives these panels uses the focused subwindow, not slot order.

### A.3 Implementation Tasks

- [x] **A.3.1** Back up `src/gui/multi_window_layout.py` and `src/main.py` per project rules.
- [x] **A.3.2** In `MultiWindowLayout.swap_views`: after updating `slot_to_view` and (if 2x2) calling `_arrange_subwindows("2x2")`, add: if `self.current_layout == "1x2"` or `self.current_layout == "2x1"`, call `self._arrange_subwindows(self.current_layout)` so the two visible cells reflect the new slot-to-view mapping. Leave 1x1 as-is (no re-arrange).
- [x] **A.3.3** In `main.py`, change `_on_swap_view_requested` so it **does not** return early when layout is not 2x2. Always call `multi_window_layout.swap_views(source_index, other_index)` when the sender is an ImageViewer with a valid `subwindow_index` (and other_index is valid). Optionally show a short status message when not in 2x2, e.g. “Slot order updated; switch to 2x2 to see positions,” to avoid confusion.
- [x] **A.3.4** **Audit “focus vs slot” usage:** Search for any code that uses “first visible” container, “slot 0,” or layout position to decide which subwindow’s data to show (ROI list, ROI statistics, slice navigator, metadata/tag panel, cine/frame slider). Ensure they all use `get_focused_subwindow()` or `focused_subwindow_index` (or equivalent from lifecycle controller). Document any findings and fix any misuse so that after a swap in 1x2/2x1 the panels still show the focused view’s data. **Done:** Audit completed; see **Appendix: Focus vs Slot Audit** below. No misuse found; no code changes required for the audit.
- [ ] **A.3.5** Manual testing: (1) In 2x2, swap two views – positions and data unchanged for focus. (2) In 1x2, focus one pane, open Swap from the other pane’s context menu and swap – slot_to_view updates, layout re-arranges, focus unchanged, ROI/slider/metadata still for the originally focused pane. (3) Same in 2x1. (4) In 1x1, perform a swap (e.g. swap current view with another); then switch to 2x2 and confirm the two views have swapped positions.

### A.4 Possible Difficulties and Error-Prone Areas

- **Re-arrangement in 1x2/2x1:** After swapping, `_arrange_subwindows("1x2")` or `_arrange_subwindows("2x1")` uses `_get_focused_slot()` and row/column logic. If `slot_to_view` is inconsistent or focus is ever wrong, the wrong two containers could be shown. Mitigation: keep existing logic; only add the re-arrange call; ensure no focus change in swap path.
- **Assumptions that “first visible = focused”:** Some code might assume the first widget in the layout is the focused one. After swap in 1x2/2x1, the focused view might be in the second visible cell. The audit (A.3.4) is there to catch this.
- **Context menu “Swap” visibility:** The Swap submenu is currently always shown (when `subwindow_index` is set). Making swap effective in all layouts does not require changing that; we only change the handler to perform the swap and re-arrange. Optionally, menu text could hint that in 1x1/1x2/2x1 the effect is “slot order for when you go to 2x2” (or similar) to set user expectations.

### A.5 Doability and Recommendation

- **Doability: High.** The change is localized: one extra branch in `swap_views` and removing the early return in `_on_swap_view_requested`, plus an audit and tests. No change to how focus or panel updates work, as long as the audit confirms everything is focus-based.
- **Recommendation:** Proceed. The behavior is clear and aligns with the existing slot-based design; the main risk is hidden assumptions about “first visible” which the audit addresses.

### A.6 Window-Based Focus Behavior for Swap

- **Problem:** After Part A’s initial implementation, `swap_views` correctly updated `slot_to_view` and re-arranged panes, but focus stayed on the same *view* (subwindow), not the same *window* (grid slot). If the user invoked Swap from a non-focused window, the ROI list, ROI statistics, frame slider, and metadata panels continued tracking the old focused view, not the content now visible in the originally focused window.
- **Desired behavior:** Treat **“window” as the grid slot (Window 1–4)**. When swapping, keep focus on the **same window/slot** that was focused before the swap, and after the swap re-point focus (and thus app-level refs) to whichever **view now occupies that slot**. Visually the focus highlight stays on the same pane; logically the focused view index may change.
- **Design:** In `MultiWindowLayout.swap_views`:
  - Before modifying `slot_to_view`, compute `focused_slot` by finding which slot currently contains the focused view (if any): from `focused_subwindow` → `focused_view_idx` → slot `s` with `slot_to_view[s] == focused_view_idx`.
  - Perform the existing slot swap (`slot_to_view[s_a]`, `slot_to_view[s_b]`) and persist to config.
  - Re-arrange visible panes based on `current_layout` (as in A.3.2): call `_arrange_subwindows("2x2" / "1x2" / "2x1")` as appropriate.
  - After re-arrange, if `focused_slot` is not `None`, get `new_view_index = slot_to_view[focused_slot]` and call `set_focused_subwindow(self.subwindows[new_view_index])` (if in range). This re-applies focus to the **window that was focused before**, now bound to the swapped-in view.
- **Effect:** The content seen in the previously focused window changes according to the swap, and all focus-driven UI (ROI list, ROI statistics, frame slider, metadata panel, About This File, cine context) updates to the newly focused view in that same window. If focus was on a view not involved in the swap, `focused_slot` still points to the same slot and `new_view_index` equals the original view index, so focus remains effectively unchanged.
- **Notes / edge cases:**
  - If there is no focused subwindow (should be rare after initialization), `focused_slot` is `None` and no focus re-application occurs; behavior falls back to simple slot swap.
  - In 1x1 layout, `slot_to_view` still updates for future layouts, but visible content is controlled by the focused view index, so swap mainly affects how views will appear when returning to multi-window layouts; the focus re-application logic is effectively a no-op there.

---

## Part B: 2×2 Thumbnail for Window Assignments

### B.1 Goal

Provide a way to see which view (A/B/C/D or 1–4) is in which grid position (Window 1–4) when not in 2x2 layout, so that “Swap with Window k” is easier to interpret.

Two placement options from TO_DO:

- **Option 1:** A very small 2×2 thumbnail **far right of the series navigator**, separated from series/studies by a separator (e.g. vertical line or space). Always visible when the navigator is visible.
- **Option 2:** Show the 2×2 indicator **only when the user opens the Swap submenu** (e.g. as a small popover or inline widget near the menu, or as part of the context menu).

### B.2 Design Options

| Approach | Pros | Cons |
|----------|------|------|
| **Option 1 – Right of navigator** | Always visible when navigator is on; consistent place; no extra click. | Uses horizontal space; must work when navigator is hidden (hide thumbnail too or show elsewhere); small 2×2 might be hard to read if too small. |
| **Option 2 – Only when Swap opened** | No permanent UI change; only relevant when user is about to swap. | Not visible until user opens Swap; may need a custom menu/popover to embed the 2×2; more one-off UI code. |

**Recommendation:** Prefer **Option 1** for clarity and discoverability, with a **fallback to Option 2** if space or layout constraints become an issue. Option 2 can be implemented as a small dialog/popover triggered when the Swap submenu is opened, showing “Window 1–4” and which view (A/B/C/D) is in each.

### B.3 Design Details (Option 1 – Thumbnail right of navigator)

- **Widget:** New small widget, e.g. `WindowSlotMapWidget` or `ViewSlotThumbnailWidget`, that:
  - Displays a fixed 2×2 grid (four cells).
  - Each cell is labeled by **slot** (Window 1–4) and shows which **view** is in that slot (e.g. “A”, “B”, “C”, “D” or “1”–“4” for view index). Optionally, the focused view could be highlighted (e.g. border or background).
  - Gets `slot_to_view` from the layout (callback or signal) and updates when layout or swap changes.
- **Placement:** The series navigator is currently added to the central widget’s main layout (bottom). To put the thumbnail “far right of navigator”:
  - Introduce a **container** for the bottom bar: e.g. `QWidget` with `QHBoxLayout`: `[ series_navigator (stretch) | separator (line or fixed-width space) | WindowSlotMapWidget ]`.
  - The main window (or the code that calls `set_series_navigator`) would add this container to the layout instead of adding the navigator alone; the navigator and the new widget go inside the container. When the navigator is hidden, hide the whole bottom bar (current behavior) or hide only the navigator and keep the thumbnail visible – product choice; recommend hiding both for simplicity.
- **Size:** “Very small” – e.g. four small cells (e.g. 20–30 px per cell), total ~60–80 px width so it doesn’t dominate the bar.
- **Updates:** Connect to `layout_changed` and to a new signal or callback when `slot_to_view` changes (e.g. after `swap_views`). If the layout doesn’t expose a signal, the widget can take a `get_slot_to_view` callback and refresh when it receives a central “slot map updated” signal or when the navigator/layout is shown.

### B.4 Design Details (Option 2 – Only when Swap opened)

- When the user opens the **Swap** submenu (e.g. on `aboutToShow` or when building the menu), show a small **popover or tooltip** next to the menu (or above/below it) that displays the 2×2 map (Window 1–4 → view A/B/C/D). Alternative: add a non-clickable “legend” row or widget inside the Swap submenu (e.g. at the top of the submenu) showing the same 2×2. Qt’s standard QMenu may not support custom widgets in all styles; a small popover is more reliable.
- Dismiss when the menu closes or when the user clicks elsewhere.

### B.5 Implementation Tasks (Option 1)

- [ ] **B.5.1** Back up `src/gui/main_window.py` and any new files.
- [ ] **B.5.2** Create `WindowSlotMapWidget` (or similar) in `src/gui/` (new file). It should:
  - Take a callback `get_slot_to_view() -> List[int]` and optionally `get_focused_view_index() -> int`.
  - Draw a 2×2 grid with labels (e.g. “1:A”, “2:B”, … meaning Window 1 shows View A). Highlight the cell for the focused view if desired.
  - Expose a method `refresh()` and connect it to layout/slot changes (see B.5.4).
- [ ] **B.5.3** In `MainWindow.set_series_navigator`: instead of `main_layout.addWidget(navigator_widget)`, create a container widget with an `QHBoxLayout`, add `navigator_widget` with stretch 1, add a thin vertical separator (e.g. `QFrame` with `StyledPanel` or `VLine`), add the new `WindowSlotMapWidget` with fixed maximum width. Add the container to the main layout. Store a reference to the slot map widget so it can be passed the callback and updated. When the navigator is toggled visible/hidden, show/hide the same container so the thumbnail is shown/hidden with the navigator (or define different behavior and document it).
- [ ] **B.5.4** In `main.py` (or wherever the main window and layout are wired): pass `multi_window_layout.get_slot_to_view` (or a wrapper) and `get_focused_subwindow_index` to the slot map widget; connect `multi_window_layout.layout_changed` and a new signal/callback from `swap_views` (e.g. `slot_to_view_changed`) to the widget’s `refresh()`. If adding a signal from `MultiWindowLayout` for “slot_to_view changed,” add it and emit it at the end of `swap_views` and when restoring from config.
- [ ] **B.5.5** Theming: ensure the small 2×2 widget respects theme (background, text color) so it doesn’t look out of place in light/dark mode.
- [ ] **B.5.6** Manual testing: toggle navigator, swap in 2x2 and in 1x2, change layout; confirm the thumbnail always shows the current slot_to_view and (if implemented) focused highlight.

### B.6 Implementation Tasks (Option 2 – minimal)

- [ ] **B.6.1** Add a “Slot map” or “Window positions” small popover/dialog that shows the 2×2 (Window 1–4 → View A/B/C/D). Trigger it when the Swap submenu is about to be shown (e.g. from ImageViewer context menu code, or from a custom menu that wraps the Swap actions). Show it near the menu; dismiss on menu close or click outside.
- [ ] **B.6.2** Alternatively, add a non-interactive label or tiny grid inside the Swap submenu (if the Qt style supports it) so the user sees the map without a separate window.

### B.7 Possible Difficulties and Error-Prone Areas

- **Layout hierarchy:** The series navigator is added in `main_window.set_series_navigator`; changing that to a container + navigator + thumbnail requires touching the main window layout. If the central widget’s layout is built elsewhere, both places must stay in sync. Risk of the thumbnail appearing in the wrong place or not resizing correctly.
- **Visibility:** If the navigator is hidden by default, the thumbnail is hidden too (Option 1). Users who never show the navigator would never see the map unless we add an alternative (e.g. View menu “Show window slot map” that shows only the thumbnail, or Option 2).
- **Signals:** `MultiWindowLayout` does not currently emit when `slot_to_view` changes. Adding a `slot_to_view_changed` (or `slot_order_changed`) signal and emitting it from `swap_views` and from config restore ensures the thumbnail can refresh without polling.
- **Theme:** The new widget must use palette or theme-aware colors so it matches the rest of the UI.

### B.8 Doability and Recommendation

- **Doability: Medium.** Option 1 requires a new widget, a change to the main window’s bottom bar layout, and a new signal or refresh path. Option 2 is smaller in surface area but involves menu/popover timing and placement.
- **Recommendation:**  
  - If the goal is “see assignments at a glance”: implement **Option 1** and keep the thumbnail small so it doesn’t clutter the bar.  
  - If the goal is “see assignments only when swapping”: implement **Option 2** (popover when Swap submenu opens) to avoid any permanent layout change.  
  - A hybrid is possible: Option 1 by default, with a setting to hide the thumbnail and rely on Option 2 (show map when Swap is opened) for minimal UI.

---

## Part C: Summary and Ordering

| Item | Doability | Suggested order |
|------|-----------|------------------|
| A – Swap in all layouts, focus unchanged | High | Do first; small code change + audit. |
| B – 2×2 thumbnail (Option 1 or 2) | Medium | Do after A; independent but benefits from a possible `slot_to_view_changed` signal added for A (e.g. for panel audit or future use). |

### Rethinking the Ideas

- **Swap in all layouts:** No need to rethink. It extends the existing slot model consistently and improves usability when users want to reorder slots without being in 2x2. The only subtlety is making sure all UI is focus-based, which the audit addresses.
- **2×2 thumbnail:**  
  - If the bar is already crowded, **Option 2** (show only when Swap is opened) is a good fallback and avoids layout churn.  
  - If you want constant visibility, **Option 1** is better. Consider making the thumbnail optional (e.g. config or View menu) so users can turn it off.

---

## File Change Summary

| File | Changes |
|------|---------|
| `src/gui/multi_window_layout.py` | In `swap_views`, after updating `slot_to_view`, call `_arrange_subwindows(self.current_layout)` for 1x2 and 2x1. Optionally add `slot_to_view_changed` signal and emit it from `swap_views` and config restore. |
| `src/main.py` | In `_on_swap_view_requested`, remove early return when layout != 2x2; always call `swap_views` when sender and indices are valid. Optionally show status message when not in 2x2. |
| `src/core/subwindow_lifecycle_controller.py` | No change unless audit finds panel logic that uses slot order; then switch to focus-based. |
| `src/gui/main_window.py` | (Option 1) In `set_series_navigator`, add bottom bar container with navigator + separator + `WindowSlotMapWidget`; add slot map widget reference; show/hide container with navigator. |
| **New:** `src/gui/window_slot_map_widget.py` (or similar) | 2×2 thumbnail widget with `get_slot_to_view` / `get_focused_view_index` callbacks and `refresh()`. |
| `src/gui/image_viewer.py` | (Option 2 only) When building Swap submenu, show popover or inline legend with 2×2 map. |
| Docs (README, AGENTS.md, TO_DO.md) | Document swap in all layouts and (if implemented) the 2×2 thumbnail placement and optional visibility. |

---

## Appendix: Focus vs Slot Audit (Task A.3.4)

**Date:** 2025-03-03  
**Scope:** All code that drives ROI list, ROI statistics, slice navigator, metadata/tag panel, cine/frame slider, or other “current subwindow” UI. Goal: confirm every such path uses the **focused** subwindow (view index or container), not “first visible” or “slot 0.”

### Summary

**Result: No misuse found.** All panel data is keyed by the focused subwindow. The only uses of index `0` or “first” subwindow are (1) initialization/fallback when no focus has been set yet, and (2) initial load of the first slice, which deliberately targets subwindow 0 and sets focus there. No code changes are required for the audit; swap-in-all-layouts can proceed without modifying panel logic.

---

### 1. Focus-based paths (correct)

| Location | What it does | How it uses focus |
|----------|----------------|-------------------|
| `subwindow_lifecycle_controller.update_focused_subwindow_references` | Sets app.view_state_manager, app.image_viewer, app.current_dataset, app.current_slice_index, etc. | Uses `get_focused_subwindow()` → `subwindows.index(focused_subwindow)` → `focused_idx`; all app references from `subwindow_managers[focused_idx]` and `subwindow_data[focused_idx]`. |
| `subwindow_lifecycle_controller.update_right_panel_for_focused_subwindow` | Right panel (zoom, W/L, projection, fusion) | Uses `app.image_viewer` and managers already set from focused subwindow. |
| `subwindow_lifecycle_controller.update_left_panel_for_focused_subwindow` | Left panel (metadata, cine context) | Uses `app.current_dataset` (synced to focused subwindow). |
| `main._on_slice_changed` | Slice navigator → update displayed slice | Uses `focused_subwindow_index`; updates `subwindow_data[focused_idx]` and `subwindow_managers[focused_idx]['slice_display_manager']`. |
| `main._update_roi_list` | ROI list panel | Uses `self.current_dataset` and `self.current_slice_index` (app-level refs synced to focused subwindow). |
| `main._update_series_navigator_highlighting` | Series navigator current series | Uses `focused_subwindow_index` and `subwindow_data[focused_idx]`. |
| `main._open_about_this_file` | About This File dataset/path | Uses `focused_subwindow_index` and `subwindow_data[focused_idx]`. |
| `main._on_frame_slider_changed` / cine | Frame slider and cine playback | Slice navigator is shared; slice changes are applied to focused subwindow in `_on_slice_changed`. Cine context uses `app.current_studies` / `current_series_uid` (focus-synced). |
| `dialog_coordinator.update_histogram_for_subwindow` | Histogram for a subwindow | Uses `get_focused_subwindow_index()` when `subwindow_index` is None. |
| `file_series_loading_coordinator` (series selection, assign, etc.) | Series assignment and load | Uses `get_focused_subwindow()` for “assign to focused”; `focused_subwindow_index` where a single target is needed. |
| `annotation_paste_handler` | Paste annotation | Uses `_get_focused_subwindow()`. |

---

### 2. Uses of index 0 or “first” subwindow

| Location | Code | Verdict |
|----------|------|--------|
| **main.py `__init__`** (after layout ready) | If `roi_coordinator is None`: use `subwindow_managers[0]`, `subwindows[0].image_viewer` for app references. | **Acceptable.** Runs only before any focus has been set (or in a broken state). After swap we do not clear `roi_coordinator`, so this path does not run during normal operation. Optional future improvement: if a “recovery” path ever re-runs this logic, use `get_focused_subwindow()` instead of 0. |
| **main.py `_initialize_handlers`** | Same fallback: if `roi_coordinator is None`, use `subwindow_managers[0]` and `subwindows[0]`. | **Acceptable.** Same as above; initialization only. |
| **file_series_loading_coordinator** (initial load, e.g. first slice) | Sets `app.multi_window_layout.set_focused_subwindow(subwindow_0)` and `app.focused_subwindow_index = 0`; then uses `managers_0 = app.subwindow_managers[0]`, `subwindow_data[focused_idx]` with `focused_idx = 0`. | **By design.** Initial load targets subwindow 0 and sets focus there. Not a “panel shows wrong view” case; no change needed for swap. |
| **multi_window_layout._get_first_visible_container** | Returns the container in the “first” visible slot for the given layout (slot-based for 1x2/2x1/2x2). | **Correct.** Used only when **setting** focus because there is no focus or the focused container is not visible (`set_layout` → “Set focus to first visible slot if no focus or focused container not visible”). After swap we do not change focus, so this is not invoked. It correctly returns the first visible slot’s container for that layout. |
| **multi_window_layout.set_layout** | Calls `_get_first_visible_container` only when `focused_subwindow is None or not focused_subwindow.isVisible()`. | After swap we only call `_arrange_subwindows`; we do not call `set_layout`, so focus is not reset. |

---

### 3. Data flow check

- **ROI list / ROI statistics:** Updated via `update_right_panel_for_focused_subwindow` (focus-based) and by `_update_roi_list` (uses `app.current_dataset` / `app.current_slice_index`, which are synced from focused subwindow). Per-subwindow ROI coordinators call `roi_list_panel.update_roi_list(...)` with their own study/series/instance; the **active** panel state is the one from the focused subwindow’s coordinator because app references point to that subwindow’s managers.
- **Slice navigator:** Shared widget; its `current_slice_index` and `total_slices` are updated when focus changes (in `update_focused_subwindow_references`) and when the user changes slice (`_on_slice_changed`), both of which use the focused subwindow. So the slider and slice position always reflect the focused view.
- **Metadata panel / tag browser:** Use `app.current_dataset` and related app-level refs, which are set from `subwindow_data[focused_idx]` in `update_focused_subwindow_references`.
- **Cine / frame slider:** Cine context and frame position come from the slice navigator and focused subwindow’s series/slice; no slot-based assumption.

---

### 4. Conclusion

All panel and navigator behavior is driven by the focused subwindow. No code assumes “first visible = focused” or “slot 0 = current” for ongoing UI updates. The only index-0 uses are initialization fallback and initial load targeting subwindow 0. **No fixes required for the audit;** implementing swap in all layouts (without changing focus) is safe from a panel-consistency perspective.

---

*End of plan.*
