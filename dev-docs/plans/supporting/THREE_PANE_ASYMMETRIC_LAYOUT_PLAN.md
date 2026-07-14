# Plan: Three-Pane Asymmetric Window Layouts

**Created:** 2026-05-31  
**TO_DO:** UX / Workflow — *One large window + two smaller (left/right or top/bottom); key **2** toggles 1×2 ↔ 2×1; key **3** cycles 3-window layouts.*

---

## Goal and success criteria

### Goal

Add **three visible panes** with asymmetric sizing:

1. **Large left + two stacked right** (primary reading pane left).
2. **Large right + two stacked left** (mirror).
3. **Large top + two side-by-side bottom**.
4. **Large bottom + two side-by-side top** (mirror).

Keyboard behavior per TO_DO:

- **2** — toggle **1×2** ↔ **2×1** (keep current behavior).
- **3** — **cycle** through the four 3-pane modes (not “2×1” as today).

### Success criteria

| Check | Pass |
|-------|------|
| Layout menu + context menu | User can select each 3-pane mode; checkmarks reflect active mode |
| Key **3** | Cycles 3-pane family only; does not break **4** → 2×2 |
| Key **2** | Still toggles 1×2 / 2×1 only |
| Four logical views | Still 4 subwindows (A–D); 3 visible, 1 hidden — hidden view retains series assignment |
| Focus | Click/focus works; navigator colors match slot map |
| Slot map widget | Mini-map shows 3 visible cells + 1 dimmed/hidden |
| Screenshot export | Composite respects 3-pane geometry (if export uses layout mode) |
| Swap (2×2) | Unchanged; 3-pane swap rules documented (likely: swap within visible triple only — v1) |

---

## Context and links

### Current architecture (verified)

| Component | Behavior |
|-----------|----------|
| `src/gui/multi_window_layout.py` | `LayoutMode = Literal["1x1", "1x2", "2x1", "2x2"]`; 4 `SubWindowContainer`s; `QGridLayout` placement in `_arrange_subwindows` |
| `src/gui/keyboard_event_handler.py` | Keys 1–4 → `change_layout_callback("1x1"…"2x2")`; key **3** = **2×1** today |
| `src/gui/image_viewer_context_menu.py` | Layout submenu: 1×1 (1), 1×2 (2), 2×1 (3), 2×2 (4) |
| `src/gui/main_window_menu_builder.py` | View → Layout menu, same four modes |
| `src/gui/window_slot_map_widget.py` | Paints 2×2 grid; dims slots not in `displayed_slots` for 1×1/1×2/2×1 |
| `src/gui/main_window.py` | `layout_changed` signal; `_on_layout_changed` syncs QAction checks |

**Not in scope of existing plans:** [WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md](WINDOW_LAYOUT_AND_NAVIGATION_POLISH_PLAN.md) covers 4-tile **within** a subwindow and fullscreen — not asymmetric 3-pane top-level layouts.

### Design constraint: keep four logical views

The app assumes **4** subwindows (`subwindow_managers` keys 0–3, `slot_to_view` length 4). Extending to 3 physical panes without dropping a view requires:

- One subwindow **hidden** but still addressable (series assignment, sync, cine).
- `slot_to_view` mapping unchanged in meaning: slot 0–3 → view index 0–3.

---

## Proposed layout modes

Extend `LayoutMode` with four strings (names tentative — pick stable API):

| Mode ID | Description | Grid (rows×cols) | Row/col spans |
|---------|-------------|------------------|---------------|
| `1+2R` | Large **left**, two right | 2×2 | Left: view A spans rows 0–1 col 0; right: B row0 col1, C row1 col1 |
| `2L+1` | Two left, large **right** | 2×2 | Right: view D spans rows 0–1 col 1; left: B row0 col0, C row1 col0 |
| `2T+1` | Large **top**, two bottom | 2×2 | Top: view A spans cols 0–1 row 0; bottom: B col0 row1, C col1 row1 |
| `1+2B` | Two top, large **bottom** | 2×2 | Bottom: view D spans cols 0–1 row 1; top: B col0 row0, C col1 row0 |

**Hidden view:** The fourth view not placed in the grid stays in `subwindows[]` but `hide()` — default mapping:

| Mode | Visible views (example slot_to_view) | Hidden |
|------|--------------------------------------|--------|
| `1+2R` | slot0 large, slot1 top-right, slot2 bottom-right | slot3 |
| `2L+1` | slot1 top-left, slot2 bottom-left, slot3 large | slot0 |
| `2T+1` | slot0 top, slot1 bottom-left, slot2 bottom-right | slot3 |
| `1+2B` | slot0 top-left, slot1 top-right, slot2 large bottom | slot3 |

Exact slot↔view mapping should follow **focused slot** rules used in 1×2/2×1 (focused pane must remain visible). Document chosen convention in code comments.

Use `QGridLayout.addWidget(widget, row, col, rowSpan, colSpan)` — already used for 1×1 single cell.

### Keyboard

- **`_cycle_three_pane_layout()`** in app or `MultiWindowLayout`: order e.g. `1+2R` → `2L+1` → `2T+1` → `1+2B` → wrap.
- If current mode is 1×1/1×2/2×1/2×2, first press of **3** enters `1+2R` (or last-used 3-pane from config).
- **2** unchanged: toggle 1×2 ↔ 2×1 only (when in 2-pane family); if in 3-pane, TO_DO says “2 switches between 1x2 and 2x1” — **interpretation:** leaving 3-pane to 2-pane on **2** is reasonable; document in UX.

**Clarification for implementer:** When user presses **2** from a 3-pane mode, switch to **1×2** or **2×1** based on last 2-pane choice (persist in config).

### Persistence

- Save `layout_mode` in config (existing key if any) — new enum values must not break old configs (unknown → `1x1`).

---

## Touch points (file checklist)

| File | Change |
|------|--------|
| `multi_window_layout.py` | Extend `LayoutMode`, `_get_num_subwindows`, `_arrange_subwindows`, `_get_first_visible_container`, `get_visible_view_indices`, early-return in `set_layout` |
| `keyboard_event_handler.py` | Key 3 → cycle 3-pane; key 2 → toggle 1×2/2×1 |
| `main_window_menu_builder.py` | Layout submenu entries + shortcuts hint |
| `image_viewer_context_menu.py` | Layout submenu; renumber hints (3 = cycle 3-pane, 4 = 2×2) |
| `window_slot_map_widget.py` | `_compute_displayed_slots` for 3-pane geometries |
| `main_window.py` | `_on_layout_changed` checkable actions for new modes |
| `src/utils/config/layout_config.py` | Extend `LayoutMode` literal + `get/set_multi_window_layout` validation (unknown → `1x1`) |
| `src/gui/dialogs/screenshot_export_dialog.py` / composite builder | Map new modes to tile rectangles (if layout-aware export exists) |
| `tests/test_multi_window_layout.py` | **New** — grid positions and visible count (file does not exist yet) |

---

## Implementation phases

### Phase 0 — UX spec sign-off

- [x] (T0) Confirm slot assignment table and **2** key behavior when exiting 3-pane — **locked 2026-06-04 (user approved parallel run):** use slot table in **Proposed layout modes**; hidden pane retains series assignment; **2** from 3-pane → last-used **1×2** or **2×1** (persist in config); **3** cycle order **`1+2R` → `2L+1` → `2T+1` → `1+2B`**; first **3** from 1×1/2×2 enters **`1+2R`** (or last 3-pane from config when added).

### Phase 1 — Core layout engine

- [x] (T1) Extend `LayoutMode` type and validation in `set_layout` (owner: coder, parallel-safe: no, stream: none, after: T0).
- [x] (T2) Implement `_arrange_subwindows` branches for four 3-pane modes with row/col spans (owner: coder, parallel-safe: no, stream: none, after: T1).
- [x] (T3) Update `_compute_displayed_slots` / focus helpers so focused view stays visible (owner: coder, parallel-safe: no, stream: none, after: T2).
- [x] (T4) Unit tests: each mode shows exactly 3 widgets in grid, correct spans (owner: coder, parallel-safe: yes, stream: none, after: T2).

### Phase 2 — UI and shortcuts

- [x] (T5) Menu + context menu entries; update accelerator labels “(3)” on 3-pane cycle vs “(4)” on 2×2 (owner: coder, parallel-safe: no, stream: none, after: T2).
- [x] (T6) `keyboard_event_handler`: key 3 cycle, key 2 toggle; persist last 2-pane/3-pane in config (owner: coder, parallel-safe: no, stream: none, after: T5).
- [x] (T7) `window_slot_map_widget` paint: three active cells + one ghosted (owner: coder, parallel-safe: no, stream: none, after: T3).

### Phase 3 — Integration and regression

- [ ] (T8) Series drag-drop to hidden pane still works via slot map click or swap (owner: tester, parallel-safe: no, stream: none, after: T6).
- [x] (T9) Screenshot / window-slot export if applicable (owner: coder, parallel-safe: no, stream: none, after: T2).
- [ ] (T10) Manual smoke all modes + swap in 2×2 unchanged; `CHANGELOG.md` minor feature note (owner: tester, parallel-safe: no, stream: none, after: T8).

---

## Task graph and gates

- **T0 → T1 → T2 → T3/T4 → T5 → T6 → T7 → T8–T10**
- **Gate G1:** Layout unit tests pass.
- **Gate G2:** Manual 4-mode cycle via key 3 without focus loss on assigned series.

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Hidden pane “loses” series | Navigator still shows assignment; optional badge “hidden pane D” |
| Splitter unequal sizes | Qt stretch factors 2:1 on grid rows/cols; tune in `_arrange_subwindows` |
| MPR / fusion per-pane | No change — still per subwindow index |
| Shortcut conflict with text edit | Same guard as layout keys 1–4 (`is_any_text_annotation_editing`) |

---

## Modularity

- Prefer one function `_arrange_three_pane(mode, grid, ...)` to avoid 4× copy-paste in `_arrange_subwindows`.
- Keep `multi_window_layout.py` under ~750 lines or extract `layout_arrangement.py` if needed.

---

## Testing strategy

```text
.\.venv\Scripts\python.exe -m pytest tests/test_multi_window_layout.py -v
python scripts/agent_smoke_harness.py
```

Manual: cycle **3**, drag series to each visible pane, verify hidden pane retains assignment when re-entering 2×2.

---

## UX / UI

Defer visual polish (splitter grab handles, exact 60/40 split) to [UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md](UX_ASSESSMENT_REMEDIATION_AND_DESIGN_SYSTEM_PLAN.md) if needed; v1 uses grid stretch only.

---

## Questions for user

1. **Hidden fourth pane:** Acceptable to keep view D loaded but hidden, or must all four be visible in navigator only?
2. **Key 2 from 3-pane:** Switch to 1×2/2×1 immediately, or ignore until user picks 1×2/2×1 from menu?
3. **Default 3-pane cycle order:** OK with `1+2R` → `2L+1` → `2T+1` → `1+2B`?

---

## Completion notes

**Reviewer 2026-06-04 (LP-A):** Phases 0–2 + T9 verified vs code; Gate **G1** closed (`tests/test_multi_window_layout.py` **10** green). **G2** / **T8** / **T10** remain manual (tester suggested smoke: keys 2/3/4, hidden-pane assignment). **Follow-ups (non-blocking):** context-menu layout checkmarks not synced on open (View → Layout OK); slot map highlights 3 active cells but hidden cell not explicitly dimmed; 3-pane swap out of v1 scope per coder.
