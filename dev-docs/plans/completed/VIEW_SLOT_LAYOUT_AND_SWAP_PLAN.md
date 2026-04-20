# View/Slot Layout and Swap – Implementation Plan

This document is a multi-phase implementation plan for making layout switching focus-aware, allowing swap of view positions, double-click to expand a subwindow to 1x1, and adding a "Swap" option to the right-click context menu.

**References:**
- Requirements: `dev-docs/TO_DO.md` (lines 20–22: choose which subwindows to expand/show; swap; magnify any to 1x1; use focused as first when switching to 1x2/2x1; double-click to expand)
- Layout manager: `src/gui/multi_window_layout.py` (MultiWindowLayout, set_layout, _arrange_subwindows)
- Subwindow container: `src/gui/sub_window_container.py` (SubWindowContainer, focus, event filter)
- Image viewer context menu: `src/gui/image_viewer.py` (Layout submenu, right-click menu around lines 1676–1793)
- App state: `src/main.py` (focused_subwindow_index, subwindow_data, subwindow_managers keyed by index)
- Lifecycle: `src/core/subwindow_lifecycle_controller.py` (on_layout_changed, on_layout_change_requested)

---

## 1. Overview of Changes

| Area | Current behavior | Target behavior |
|------|------------------|-----------------|
| **1x1 layout** | Always shows subwindow 0. | Shows the **currently focused** view’s container only. |
| **1x2 / 2x1 layout** | Always shows subwindows 0 and 1 in fixed order. | Shows the **focused window** and the **following window by grid position**: 1x2 = the row containing focus (slots 0,1 or 2,3); 2x1 = the column containing focus (slots 0,2 or 1,3). |
| **2x2 layout** | Always shows subwindows 0–3 in fixed grid positions. | Shows all four; **slot order** configurable via swap (which view is in which grid cell). Default order [0,1,2,3]. |
| **Double-click** | No special behavior. | Double-click on a subwindow sets focus and switches to **1x1** (expand that pane); when already in 1x1, double-click reverts to **last used layout** (or 2x2 if none). |
| **Context menu** | Layout submenu: 1x1, 1x2, 2x1, 2x2. | Add **Swap** submenu: "Swap with Window 1/2/3/4" (by grid position: 1=top-left, 2=top-right, 3=bottom-left, 4=bottom-right). Exclude current window. Only in 2x2. |
| **Data** | subwindow_data[idx], subwindow_managers[idx] by index. | Unchanged; data remains keyed by view index. Swapping only repositions widgets, not data. |

---

## 2. Scope and Out-of-Scope

**In scope**
- MultiWindowLayout: slot-to-view mapping for 2x2; focus-based choice of which container(s) to show for 1x1 and 1x2/2x1; `swap_views(i, j)`; double-click handling (signal or delegation).
- SubWindowContainer and/or ImageViewer: double-click to request “expand to 1x1” (set focus + set layout 1x1).
- ImageViewer context menu: add “Swap” submenu with “Swap with View A/B/C/D”, emitting or triggering swap; need view index available when building menu (e.g. set on ImageViewer by app).
- main.py / subwindow_lifecycle_controller: connect new signals (expand requested, swap requested); ensure focused index is correct when layout changes.
- Persistence: optional persistence of slot order for 2x2 (config key); can be Phase 2 or later.
- Documentation: README, AGENTS.md, Quick Start Guide, and TO_DO.md checklist updates.

**Out of scope**
- Changing how subwindow_data or subwindow_managers are keyed (always by view index 0–3).
- Adding more than 4 views or changing the 1x1/1x2/2x1/2x2 grid structure.
- Changing ROI/annotation storage or keying.

---

## 3. Principles

- **Backups:** Per project rules, back up any code file before modifying it (e.g. in `backups/`).
- **No artificial test changes:** Do not alter tests solely to make them pass; fix behavior or document gaps.
- **Data integrity:** Swap and layout changes only reposition widgets; view index and all associated data (slice, ROIs, overlays) stay with the same container/view.
- **Focus consistency:** When switching to 1x1 or 1x2/2x1, use the current focused subwindow index to decide which view(s) to show; after layout change, focus remains on the same logical view.

---

## 4. Design Summary

- **View index (0–3):** Unchanged. Each `subwindows[i]` is the container for view `i`. Data and managers stay keyed by `i`.
- **Slot (grid position):** For 2x2, the four grid cells are slots 0–3 (e.g. (0,0), (0,1), (1,0), (1,1)). `slot_to_view: List[int]` of length 4 means “slot s shows view slot_to_view[s]”. Default `[0, 1, 2, 3]`. Arrangement uses `addWidget(subwindows[slot_to_view[s]], row, col, ...)`.
- **1x1:** Show exactly the container for the focused view: `subwindows[focused_index]`. If no focus, fall back to 0 and set focus to it.
- **1x2 / 2x1 (slot-based):** Show the **focused window** and the **following window by grid position**, not by view index. **Window 1–4** are fixed grid positions: 1=top-left (slot 0), 2=top-right (slot 1), 3=bottom-left (slot 2), 4=bottom-right (slot 3). Find `focused_slot` such that `slot_to_view[focused_slot] == focused_index`. Then: **1x2** = show the row containing focus: slots `row*2` and `row*2+1` where `row = focused_slot // 2` (so either slots 0,1 or 2,3). **2x1** = show the column containing focus: slots `col` and `col+2` where `col = focused_slot % 2` (so either slots 0,2 or 1,3). Order: first slot then second (left→right for 1x2, top→bottom for 2x1).
- **2x2:** Show all four; order by `slot_to_view`. Swap view i and j: find slots s_i, s_j where `slot_to_view[s_i]==i` and `slot_to_view[s_j]==j`, then swap `slot_to_view[s_i]` and `slot_to_view[s_j]`, then re-call `_arrange_subwindows("2x2")`.
- **Double-click:** In the subwindow that received the double-click, set that container as focused, then set layout to 1x1. Only treat double-click as “expand to 1x1” when the click is on the **image or view area with no interactive item under the cursor** (e.g. not on a text annotation, ROI, measurement, arrow, crosshair). Double-click on a text annotation or other item that has its own double-click behavior (e.g. inline edit) must pass through to the view/scene. “Empty/background” here means *no such interactive item*; it does **not** mean outside the displayed image — double-click on the image pixels (when not on an annotation) should expand. **When already in 1x1,** double-click should **revert to the last used layout** (the layout that was active before switching to 1x1); if none is stored in memory, revert to 2x2.
- **Context menu Swap:** Right-click on a subwindow shows “Swap” submenu with “Swap with View A”, “Swap with View B”, … **Window-numbering (Phase 7):** Use "Swap with Window 1/2/3/4" (1=top-left, 2=top-right, 3=bottom-left, 4=bottom-right); other_view = slot_to_view[k-1]. Exclude the current window's slot. When user picks “Swap with View X”, call `multi_window_layout.swap_views(source_view_index, X)` where **source_view_index** is the view that showed the menu (the emitting ImageViewer’s `subwindow_index`), not necessarily the focused view. Swap is only meaningful in 2x2; when layout is not 2x2, the handler should **no-op** (optionally show a short status message like “Swap is only available in 2x2 layout”). Do not auto-switch to 2x2 and then swap.

---

## 5. Phase Overviews and Checklists

---

### Phase 1: Slot-to-view state and focus-based arrangement in MultiWindowLayout

**Goal:** Add `slot_to_view` for 2x2 and change `_arrange_subwindows` so 1x1 shows focused view only, 1x2/2x1 show focused + next, and 2x2 uses `slot_to_view`. No UI yet.

**Tasks:**

- [x] **1.1** Back up `src/gui/multi_window_layout.py` to `backups/` (or project backup location).
- [x] **1.2** In `MultiWindowLayout.__init__`, add `self.slot_to_view: List[int] = [0, 1, 2, 3]` (slot index → view index for 2x2).
- [x] **1.3** Add helper `_get_focused_view_index(self) -> int`: if `self.focused_subwindow` is in `self.subwindows`, return its index; else return 0.
- [x] **1.4** In `_arrange_subwindows`:
  - For **1x1:** Show only `subwindows[_get_focused_view_index()]` in the single cell (row 0, col 0). If no subwindows, no-op.
  - For **1x2:** Let `f = _get_focused_view_index()`, `n = (f + 1) % 4`. Show `subwindows[f]` at (0,0) and `subwindows[n]` at (0,1). Ensure both exist (create subwindows if needed already handled above).
  - For **2x1:** Same f and n; show `subwindows[f]` at (0,0) and `subwindows[n]` at (1,0).
  - For **2x2:** For slot s in 0..3, map to (row, col) as (s//2, s%2); add `subwindows[slot_to_view[s]]` at that (row, col).
- [x] **1.5** In `set_layout`, after creating/showing subwindows, when setting “focus to first subwindow if no focus”, set focus to the container that is now in the first visible slot, using the same mapping as in `_arrange_subwindows`: for 1x1 use `subwindows[_get_focused_view_index()]`; for 1x2/2x1 use `subwindows[f]` (focused); for 2x2 use `subwindows[slot_to_view[0]]`.
- [x] **1.6** Ensure `set_layout` is not skipped when only the focused view changes (e.g. user was in 2x2, clicked pane 2, then pressed 1 for 1x1 — pane 2 should become the single visible one). Change the early return to: **skip** only when `self.current_layout == layout_mode` **and** `(layout_mode != "1x1" and len(self.subwindows) >= num_subwindows)` — i.e. for 1x1 never skip; for other modes skip only when layout is unchanged and we already have enough subwindows.
- [x] **1.7** Run the application; test 1x1 (should show focused pane), 1x2/2x1 (focused + next), 2x2 (all four). Change focus then switch to 1x1 and confirm the correct pane is shown.

**Success criteria:** 1x1 shows focused view only; 1x2/2x1 show focused and next in order; 2x2 shows all four in default order. No new UI yet.

---

### Phase 2: Swap views in 2x2 and optional persistence

**Goal:** Implement `swap_views(i, j)` in MultiWindowLayout and re-arrange 2x2. Optionally persist slot order in config.

**Tasks:**

- [x] **2.1** In `MultiWindowLayout`, add `def swap_views(self, view_index_a: int, view_index_b: int) -> None`. Validate 0 <= view_index_a, view_index_b < 4 and view_index_a != view_index_b. Find slot s_a such that `slot_to_view[s_a] == view_index_a`, and s_b such that `slot_to_view[s_b] == view_index_b`. Swap: `slot_to_view[s_a], slot_to_view[s_b] = slot_to_view[s_b], slot_to_view[s_a]`. If current layout is 2x2, call `_arrange_subwindows("2x2")`.
- [x] **2.2** (Optional) Add config key e.g. `view_slot_order` (list of 4 ints) in config_manager; save in `set_multi_window_layout` or on swap; restore in MultiWindowLayout when loading layout. If omitted, use [0,1,2,3]. Can be deferred to a later phase.
- [x] **2.3** Manually test: switch to 2x2, call `swap_views(0, 2)` from Python or a temporary button; confirm positions of views 0 and 2 are swapped and data (slice, ROIs) unchanged.

**Success criteria:** swap_views(i, j) correctly swaps grid positions of two views in 2x2; data remains with the same view index.

---

### Phase 3: Double-click to expand subwindow to 1x1

**Goal:** Double-click on a subwindow sets focus to that container and switches layout to 1x1.

**Tasks:**

- [x] **3.1** Back up `src/gui/sub_window_container.py` (and if needed `src/gui/image_viewer.py`).
- [x] **3.2** Add signal on SubWindowContainer or ImageViewer: e.g. `expand_to_1x1_requested = Signal()` (no args; the source is the container that emitted). Option A: emit from SubWindowContainer when double-click is detected. Option B: emit from ImageViewer and have main/layout determine which container (focused or the one under cursor). Prefer Option A: SubWindowContainer already has an event filter on image_viewer; add handling for `QEvent.Type.MouseButtonDblClick` — set focus to this container (set_focused(True)) and emit `expand_to_1x1_requested.emit()`.
- [x] **3.3** In main.py (or subwindow_lifecycle_controller): connect `expand_to_1x1_requested` from each SubWindowContainer to a handler that (1) sets focused subwindow to the sender container (if not already), (2) calls `main_window` or `multi_window_layout` to set layout to "1x1". Connect in the same place other per-subwindow signals are connected (e.g. `SubwindowLifecycleController.connect_subwindow_signals()`): iterate `get_all_subwindows()` and for each container connect `container.expand_to_1x1_requested` to the handler. Avoid duplicate connections (e.g. disconnect before connecting if reconnecting when layout changes).
- [x] **3.4** Ensure double-click does not block other actions (e.g. text annotation inline edit). Handle double-click in the container’s event filter only when the click is on **image or view area with no interactive item under the cursor** (map to scene and check `scene.itemAt(...)`): if the item is the background or the image and not a text annotation, ROI, measurement, arrow, or crosshair, treat as expand-to-1x1 and return True to consume the event; otherwise return False so the view/scene can handle it (e.g. text annotation double-click to edit). “Empty/background” means *no such interactive item* — it does **not** mean outside the displayed image; double-click on the image pixels (when not on an annotation) should expand.
- [x] **3.5** Test: in 2x2 or 1x2/2x1, double-click on a subwindow; that pane should become the only visible one (1x1) and retain its slice/ROIs.

**Success criteria:** Double-click on any visible subwindow expands it to 1x1 (focus + set_layout("1x1")).

---

### Phase 4: Swap in right-click context menu

**Goal:** Add “Swap” submenu to the image viewer right-click context menu with “Swap with View A/B/C/D”, excluding current view; only enable in 2x2 (or show in all layouts but only have effect in 2x2).

**Tasks:**

- [x] **4.1** Back up `src/gui/image_viewer.py`.
- [x] **4.2** ImageViewer must know its “view index” (0–3) to build the Swap menu. Add optional attribute `self.subwindow_index: Optional[int] = None` on ImageViewer, with a setter e.g. `set_subwindow_index(self, idx: int)`. The app (main or subwindow_lifecycle_controller) must set this when creating/connecting subwindows so each ImageViewer has the correct index.
- [x] **4.3** Add signal on ImageViewer: `swap_view_requested = Signal(int)` (argument = other view index). When user chooses “Swap with View B”, emit `swap_view_requested.emit(1)` (B=1).
- [x] **4.4** In the image viewer context menu (where Layout submenu is built), add a “Swap” submenu after or before Layout:
  - If `self.subwindow_index is None`, omit the Swap submenu or disable it.
  - Otherwise, add submenu “Swap” with actions “Swap with View A” (0), “Swap with View B” (1), “Swap with View C” (2), “Swap with View D” (3). Disable or hide the action for the current view (`self.subwindow_index`). Always show Swap when `subwindow_index` is set; in the app handler, if layout is not 2x2, **no-op** (optionally show a short status message like “Swap is only available in 2x2 layout”). Do not auto-switch to 2x2 and then swap.
- [x] **4.5** Connect each ImageViewer’s `swap_view_requested` to a handler in main (or lifecycle controller). Handler receives `other_index`. The **source** view for swap must be the **view that showed the menu** (the emitting ImageViewer’s `subwindow_index`), not `focused_subwindow_index`, because right-click does not change focus. Resolve source from the sender: e.g. find the container whose `image_viewer is sender`, then get that container’s index via `get_all_subwindows().index(container)`, or use the emitting ImageViewer’s `subwindow_index` if set. Call `app.multi_window_layout.swap_views(source_index, other_index)`.
- [x] **4.6** Ensure subwindow_index is set for all ImageViewers when subwindows exist. In the same place other per-subwindow setup runs (e.g. `connect_subwindow_signals()` in subwindow_lifecycle_controller), use `for idx, container in enumerate(app.multi_window_layout.get_all_subwindows()): container.image_viewer.set_subwindow_index(idx)`.
- [x] **4.7** Test: in 2x2, right-click on a pane → Swap → “Swap with View C”; views should swap positions. Verify slice and ROIs stay with the same logical view.

**Success criteria:** Context menu has “Swap” submenu with “Swap with View A/B/C/D”; choosing one swaps positions in 2x2; data preserved.

---

### Phase 5: Edge cases and focus/layout sync

**Goal:** Handle edge cases: focus when a visible subwindow is hidden (e.g. switch from 2x2 to 1x1); ensure menu and layout state stay in sync.

**Tasks:**

- [ ] **5.1** When switching from 2x2 or 1x2/2x1 to 1x1, the focused view might already be the one to show; ensure focus is set on the single visible container so app.focused_subwindow_index and layout.focused_subwindow stay correct.
- [ ] **5.2** When switching to 1x2/2x1, focused and next are shown; ensure focus remains on the “focused” container (first slot).
- [ ] **5.3** If layout is 1x1 and user requests 1x2 via menu/key, ensure the two visible panes are focused and next (already implemented in Phase 1).
- [ ] **5.4** Verify that after swap in 2x2, focus and right-panel data (ROI list, statistics) still reflect the focused view, not the slot position.
- [x] **5.5** **Double-click in 1x1:** When the user is already in 1x1 layout and double-clicks on the visible pane (on image/background), revert to the **last used layout** before 1x1 (e.g. 2x2, 1x2, or 2x1). Store the previous layout when switching to 1x1 (e.g. in MultiWindowLayout or app state). If no previous layout is in memory (e.g. app just started in 1x1), revert to 2x2.
- [x] **5.6** **Resize when switching from 2x2 to 1x2/2x1:** Sometimes when changing layout from 2x2 to 2x1 or 1x2, an unfocused window does not resize appropriately. Investigate (e.g. which container fails to resize, timing of show/layout activation). Consider adding temporary debugging (e.g. log container sizes before/after `_arrange_subwindows`, or force `updateGeometry()` / `adjustSize()` on visible subwindows after arrangement) to reproduce and fix.

**Success criteria:** No focus/sync bugs when changing layout or after swap; double-click in 1x1 restores previous layout; 1x2/2x1 resize is reliable.

---

### Phase 6: Documentation updates

**Goal:** Update user-facing and developer-facing documentation.

**Tasks:**

- [x] **6.1** **README.md:** Under features or usage, add a short note that layout can be switched with 1–4 keys and from the Layout menu; that the single pane in 1x1 is the focused pane; that double-click on a pane expands it to 1x1; and that in 2x2 you can swap view positions via right-click → Swap.
- [x] **6.2** **AGENTS.md:** In “View and display options” or a new bullet, mention that 1x1 shows the focused view, 1x2/2x1 show focused + next, and that Swap in the context menu reorders view positions in 2x2 without moving data.
- [x] **6.3** **Quick Start Guide** (`src/gui/dialogs/quick_start_guide_dialog.py` or equivalent): Add a line under layout section: double-click a pane to expand it to full view; right-click → Swap to exchange positions of two views in 2x2 layout.
- [x] **6.4** **TO_DO.md:** Check off or update the items for “Make it possible to choose which subwindows to expand/show…” and the sub-item “double-clicking on a subwindow expand it to 1x1”. Add a brief “Done” note or move to a “Completed” section if that’s the project’s convention.

**Success criteria:** Docs accurately describe the new behavior and any constraints.

---

### Phase 7: Window-numbering (Swap by grid position) and slot-based 1x2/2x1

**Goal:** (1) Swap menu uses "Swap with Window 1/2/3/4" where 1–4 are fixed grid positions (top-left, top-right, bottom-left, bottom-right), not view identity. (2) When switching to 1x2 or 2x1, show the focused window and the following window **by grid position** (row or column in 2x2), not by view index.

**Tasks:**

- [x] **7.1** **Window 1–4 definition:** Document and implement fixed mapping: Window 1 = slot 0 (top-left), Window 2 = slot 1 (top-right), Window 3 = slot 2 (bottom-left), Window 4 = slot 3 (bottom-right). These refer to **positions** in the 2x2 grid; which view is in which position is given by `slot_to_view`.
- [x] **7.2** **Swap menu relabel:** Change context menu from "Swap with View A/B/C/D" to "Swap with Window 1", "Swap with Window 2", "Swap with Window 3", "Swap with Window 4". For each k in 1..4, the action swaps with the view currently in slot (k-1): call `swap_views(source_view_index, slot_to_view[k-1])`. Disable the action for the slot that contains the current view (find s where `slot_to_view[s] == subwindow_index`; disable "Swap with Window (s+1)"). Building the menu requires current `slot_to_view`: add a callback on ImageViewer (e.g. `get_slot_to_view_callback`) set by app to return `layout.get_slot_to_view()` or equivalent, or pass slot_to_view when building the Swap submenu.
- [x] **7.3** **Slot-based 1x2/2x1 in MultiWindowLayout:** Add helper `_get_focused_slot(self) -> int`: find slot s such that `slot_to_view[s] == _get_focused_view_index()`; if not found return 0. In `_arrange_subwindows`: for **1x2**, let `row = _get_focused_slot() // 2`; show `subwindows[slot_to_view[row*2]]` at (0,0) and `subwindows[slot_to_view[row*2+1]]` at (0,1). For **2x1**, let `col = _get_focused_slot() % 2`; show `subwindows[slot_to_view[col]]` at (0,0) and `subwindows[slot_to_view[col+2]]` at (1,0). Update `_get_first_visible_container("1x2")` to return `subwindows[slot_to_view[row*2]]` and for "2x1" return `subwindows[slot_to_view[col]]` (using same row/col from focused slot).
- [x] **7.4** **Edge cases:** (a) When `slot_to_view` is default [0,1,2,3], focused_slot equals focused_index; 1x2 shows views (row*2, row*2+1), 2x1 shows (col, col+2) — same as current for default. (b) When slot_to_view is permuted (e.g. after swaps), 1x2 shows the **row** containing the focused window; 2x1 shows the **column** containing the focused window. (c) If for any reason focused view is not in slot_to_view (should not happen), _get_focused_slot fallback 0 is correct. (d) Swap menu when not in 2x2: still build from current slot_to_view; handler no-ops if layout != "2x2". (e) Ensure set_layout focus fallback for 1x2/2x1 uses the same row/col logic so the "first" visible container is the one in the first slot of that row or column.
- [x] **7.5** **Documentation:** Update README, AGENTS, Quick Start to say "Swap with Window 1/2/3/4" and that 1x2 shows the row containing the focused window, 2x1 shows the column containing the focused window.
- [ ] **7.6** **Testing:** Verify 2x2 with swaps: Swap menu shows Window 1–4; choosing Window k swaps with view in that slot. Verify 1x2/2x1: after swapping in 2x2, switch to 1x2 — the two panes are the row containing focus (same row in 2x2); switch to 2x1 — the two panes are the column containing focus.

**Success criteria:** Swap menu is by window position (1–4); 1x2 and 2x1 show focused window and adjacent window by grid position (row or column).

---

## 6. File Change Summary

| File | Changes |
|------|---------|
| `src/gui/multi_window_layout.py` | slot_to_view; _get_focused_view_index(); _arrange_subwindows; swap_views. Phase 7: _get_focused_slot(); 1x2/2x1 slot-based (row/column); _get_first_visible_container for 1x2/2x1 by slot. |
| `src/gui/sub_window_container.py` | Double-click in event filter → set focus + emit expand_to_1x1_requested. |
| `src/gui/image_viewer.py` | subwindow_index attribute + setter; swap_view_requested signal; context menu “Swap” submenu. |
| `src/main.py` | Connect expand_to_1x1_requested → set focus + set_layout("1x1"); connect swap_view_requested → swap_views; set subwindow_index on each image_viewer when subwindows exist. |
| `src/core/subwindow_lifecycle_controller.py` | If expand/swap connections are done here instead of main, add same connections and set_subwindow_index in connect path. |
| `src/utils/config_manager.py` | (Optional) get/set view_slot_order for 2x2 persistence. |
| `README.md`, `AGENTS.md`, Quick Start, `TO_DO.md` | Documentation updates per Phase 6. |

---

## 7. Testing Checklist (manual)

- [ ] 1x1: Switch to 1x1; click another pane (in 2x2), then switch to 1x1 again — the clicked pane should be the one shown.
- [ ] 1x2/2x1: With default slot order, focus view 2, switch to 1x2 — row containing view 2 (views 2,3) appears. Phase 7: after swaps in 2x2, 1x2 shows the row (in 2x2) containing focused window; 2x1 shows the column containing focused window.
- [ ] 2x2: All four views visible; swap view 0 and 2 — positions swap; slice and ROIs unchanged.
- [ ] Double-click: In 2x2, double-click view 1 — layout becomes 1x1 with view 1 only.
- [ ] Double-click in 1x1: From 2x2 go to 1x1 (e.g. double-click a pane), then double-click again — layout reverts to 2x2; from 1x2 go to 1x1, then double-click — reverts to 1x2. If app starts in 1x1 and user double-clicks, revert to 2x2.
- [ ] Context menu Swap: Right-click in 2x2 → Swap → Swap with Window 2 (or 1/3/4); verify swap and data integrity. Phase 7: labels are "Window 1/2/3/4" by grid position.
- [ ] Focus after layout change: After 1x1 or swap, right panel and series navigator reflect the focused view.
- [ ] Resize 2x2→1x2/2x1: Switch from 2x2 to 1x2 or 2x1; both visible panes should resize correctly (no stuck/collapsed unfocused window).

---

## 8. Review: Clarifications and Recommended Improvements

*This section was added after double-checking the plan against the codebase. Implementers should apply these clarifications and consider the recommendations.*

### 8.1 Required clarifications (incorporated into phases above)

1. **Phase 4.5 – Swap source index**  
   Incorporated in Design Summary and task 4.5: use the **emitting ImageViewer’s `subwindow_index`** as the source for swap (the view that showed the menu), not `focused_subwindow_index`.

2. **Phase 3.4 – Double-click “empty/background”**  
   Incorporated in Design Summary and task 3.4. **Definition:** “Empty/background” means the **image or view area with no interactive scene item under the cursor** — i.e. not on a text annotation, ROI, measurement, arrow, or crosshair. It does **not** mean outside the displayed image; double-click on the image pixels (when not on an annotation) should expand to 1x1. Double-click on a text annotation or other item that has its own double-click behavior (e.g. inline edit) must pass through (return False) so the view/scene can handle it.

3. **Phase 4.6 – Where to set `subwindow_index`**  
   Incorporated in task 4.6: use `for idx, container in enumerate(app.multi_window_layout.get_all_subwindows()): container.image_viewer.set_subwindow_index(idx)` in the same place as other per-subwindow setup (e.g. `connect_subwindow_signals()`).

4. **Phase 3.3 – Connecting `expand_to_1x1_requested`**  
   Incorporated in task 3.3: connect in `connect_subwindow_signals()`, iterate `get_all_subwindows()`, and avoid duplicate connections when the method is called again on layout change.

### 8.2 Recommended improvements (incorporated into phases above)

1. **Phase 1.6 – Early return:** Explicit condition in task 1.6: skip when `current_layout == layout_mode` and `(layout_mode != "1x1" and len(self.subwindows) >= num_subwindows)`.
2. **Phase 4 – Swap when not in 2x2:** Design Summary and task 4.4: no-op when not 2x2 (optional status message); do not auto-switch to 2x2.
3. **Phase 1.5 – Focus fallback:** Task 1.5 now states the exact mapping: 1x1 → `subwindows[_get_focused_view_index()]`, 1x2/2x1 → `subwindows[f]`, 2x2 → `subwindows[slot_to_view[0]]`.
4. **Backup location:** `backups/` at project root — unchanged.
5. **TO_DO.md and Quick Start:** References correct — unchanged.

### 8.3 Codebase alignment verified

- **multi_window_layout.py:** Has `subwindows`, `focused_subwindow`, `_arrange_subwindows`, `set_layout` with the early return `if self.current_layout == layout_mode and len(self.subwindows) > 0`. No `slot_to_view` yet; `get_subwindow(index)` and `get_all_subwindows()` exist and return the list of containers.
- **sub_window_container.py:** Has event filter on `image_viewer`, `MouseButtonPress` handling for focus, `context_menu_requested` on right-click; no double-click handling yet. Adding `MouseButtonDblClick` and `expand_to_1x1_requested` here is consistent.
- **image_viewer.py:** Context menu with Layout submenu is built in `mouseReleaseEvent` (right-button, ~lines 1676–1748). Adding Swap submenu and `subwindow_index` / `swap_view_requested` here is correct.
- **main.py / subwindow_lifecycle_controller:** `focused_subwindow_index` is kept in sync via `on_focused_subwindow_changed` → `update_focused_subwindow_references()` (index from `subwindows.index(focused_subwindow)`). Per-subwindow signals are connected in `connect_subwindow_signals()` by iterating `get_all_subwindows()`. Plan’s wiring (expand, swap, set_subwindow_index) fits this pattern.

---

## 9. Window-numbering and slot-based 1x2/2x1 (Phase 7 – code flow and edge cases)

*Design for Phase 7: Swap by "Window 1–4" (grid position) and 1x2/2x1 by slot (row/column).*

### 9.1 Window 1–4 semantics

- **Window k** (k = 1,2,3,4) = grid cell in 2x2: 1=top-left (slot 0), 2=top-right (slot 1), 3=bottom-left (slot 2), 4=bottom-right (slot 3). View in Window k = `slot_to_view[k-1]`. "Swap with Window 2" = swap with view currently in top-right.

### 9.2 Swap menu – code flow

- Menu needs current `slot_to_view` (callback, e.g. `get_slot_to_view_callback` → `layout.slot_to_view`). For k in 1..4 add "Swap with Window k"; disable when `slot_to_view[k-1] == subwindow_index`. Emit `swap_view_requested.emit(slot_to_view[k-1])`. Handler unchanged: `swap_views(source_index, other_index)`.

### 9.3 1x2/2x1 – slot-based code flow

- Add `_get_focused_slot()`: s where `slot_to_view[s] == _get_focused_view_index()`; else 0. **1x2:** `row = focused_slot // 2`; show `slot_to_view[row*2]`, `slot_to_view[row*2+1]`. **2x1:** `col = focused_slot % 2`; show `slot_to_view[col]`, `slot_to_view[col+2]`. Update `_get_first_visible_container("1x2")` and `("2x1")` to use same row/col.

### 9.4 Edge cases

- Default slot_to_view [0,1,2,3]: focused_slot = focused_index; behavior matches current. Permuted slot_to_view: 1x2 shows row containing focus, 2x1 shows column. Swap menu when not 2x2: build from slot_to_view; handler no-ops.

---

*End of plan.*
