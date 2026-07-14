# Plan: Window/Level preset menu — show C/W values

**Last updated:** 2026-05-31  
**Status:** Supporting — complete (2026-06-04)  
**Backlog:** [`dev-docs/TO_DO.md`](../../TO_DO.md) — Bugs / Correctness (P2)

---

## Goal and success criteria

Show **window center and width** alongside preset names in the **Window/Level Presets** menu (toolbar dropdown and image context menu), using values that match what the user would get if they applied the preset in the **current viewer mode** (raw vs rescaled).

**Success criteria:**

- Each preset action shows name **and** numeric C/W (not only in hover tooltip).
- Displayed C/W reflect **`use_rescaled_values`** on the focused pane when preset storage space differs (convert via slope/intercept when applicable).
- Unit suffix rules from [`WL_PRESET_DICOM_LABELS_AND_UNITS_PLAN.md`](WL_PRESET_DICOM_LABELS_AND_UNITS_PLAN.md) are preserved (no fake `HU`; meaningful units only).
- Menu labels stay readable at typical widths (truncate or compact format if needed).
- Tooltips remain useful (can show stored vs displayed values when they differ).
- Unit tests cover raw/rescaled conversion and label formatting; no regression in preset application.

---

## Context and links

### Related TO_DO / plans

| Item | Relationship |
|------|----------------|
| **[P2] W/L Presets menu — show values** (this plan) | Primary tracker |
| **[P2] W/L preset management UI** (done) | Built-in/custom presets, Manage dialog — [`wl_preset_catalog.py`](../../../src/core/wl_preset_catalog.py), [`wl_preset_menu.py`](../../../src/gui/wl_preset_menu.py) |
| **[P1] DICOM W/L preset labels/units** (done) | [`WL_PRESET_DICOM_LABELS_AND_UNITS_PLAN.md`](WL_PRESET_DICOM_LABELS_AND_UNITS_PLAN.md) — names and unit suffixes, not inline C/W |
| **[P1] PT/BQML W/L controls** | [`PT_WINDOW_LEVEL_CONTROLS_AND_QUICK_WL_PLAN.md`](PT_WINDOW_LEVEL_CONTROLS_AND_QUICK_WL_PLAN.md) — spinbox ranges; menu values must stay consistent with W/L controls |
| **[P1] Set min/max W/L from bit depth** | [`UX_IMPROVEMENTS_BATCH1_PLAN.md`](UX_IMPROVEMENTS_BATCH1_PLAN.md) — separate; menu display only |

### Current behavior

- [`format_preset_menu_label()`](../../../src/core/wl_preset_catalog.py) — **name + storage-space suffix only**; comment explicitly says full C/W go in tooltip.
- [`format_preset_tooltip()`](../../../src/core/wl_preset_catalog.py) — shows `Center X, Width Y` for **stored** preset values; notes viewer mode and conversion-on-apply but does **not** show converted numbers.
- [`populate_wl_preset_menu()`](../../../src/gui/wl_preset_menu.py) — builds toolbar and context-menu actions; receives `WLPresetMenuContext` with `use_rescaled`, `rescale_slope`, `rescale_intercept`.
- Context built in [`main.py`](../../../src/main.py) `_get_wl_preset_menu_context()` from `view_state_manager`.

Menus are rebuilt when opened (not live-updated while open). Toggling **Use rescaled values** should show updated C/W the **next** time the menu opens — verify no stale cache.

---

## Recommended label format

**Default (compact):**

`{name} — C {center}, W {width}{unit_suffix}`

Examples:

- `Lung — C 40, W 400 (HU)`
- `NORMAL — C 350, W 2000`
- `SUV 0-5 — C 2.5, W 5 (BQML)`
- `Brain T1 — C 500, W 1000 (raw)`

**When stored space ≠ viewer mode** and conversion applies, show **viewer-space** numbers in the menu line; tooltip can add one line: `Stored: C …, W … ({space})`.

**Formatting rules:**

- Integers without decimals when whole; one decimal place otherwise (match existing tooltip style).
- Omit unit suffix when unknown/non-meaningful (same as labels plan).
- Long DICOM explanation names: keep full name; values after em dash; avoid menu overflow by Qt elision if needed (optional T5).

---

## Task graph and gates

### Ordering

- T1 (format helper) → T2 (wire menu) → T3 (tooltip alignment) → T4 (tests).
- T5 (menu refresh on rescaled toggle) after T2 if gap found.

### Verification gates

- **Gate 1:** Reviewer approves compact label format before UI change.
- **Gate 2:** `test_wl_preset_catalog.py` + any new cases green.
- **Gate 3:** Manual smoke — CT (HU), PT (BQML), toggle raw/rescaled, apply preset from menu.

### File ownership

| Area | Modules |
|------|---------|
| Label/tooltip formatting | `src/core/wl_preset_catalog.py` |
| Menu population | `src/gui/wl_preset_menu.py` |
| Context / rescaled state | `src/main.py`, `view_state_manager` |
| Tests | `tests/test_wl_preset_catalog.py` |

---

## Phases (checklist)

### Phase 1 — Display values in menu labels

- [x] (T1) Add `format_preset_display_values(preset, *, use_rescaled, rescale_slope, rescale_intercept) -> tuple[float, float]` (or reuse existing conversion helper if one exists) (owner: coder, parallel-safe: no, stream: none, after: none).
- [x] (T2) Extend `format_preset_menu_label()` to accept viewer context and append ` — C …, W …` using display values (owner: coder, parallel-safe: no, stream: none, after: T1).
- [x] (T3) Update `populate_wl_preset_menu()` to pass `use_rescaled` / slope / intercept into label formatter (owner: coder, parallel-safe: no, stream: none, after: T2).
- [x] (T4) Align `format_preset_tooltip()` so first line shows **display** C/W when viewer mode differs from stored space; keep stored line when conversion applies (owner: coder, parallel-safe: no, stream: none, after: T1).

### Phase 2 — Consistency and tests

- [x] (T5) Confirm toolbar dropdown and context menu both use updated labels; audit legacy `context_from_legacy_presets` path (owner: coder, parallel-safe: no, stream: none, after: T3). **Note:** both menus call `populate_wl_preset_menu()`; legacy path already carries `use_rescaled`/slope/intercept via `main._get_wl_preset_menu_context()`.
- [x] (T6) Unit tests: HU preset raw vs rescaled viewer; BQML preset; raw-space preset; DICOM named preset (owner: coder/tester, parallel-safe: no, stream: none, after: T4).
- [ ] (T7) Manual QA: open menu, toggle rescaled checkbox, reopen menu — values update (owner: tester, parallel-safe: no, stream: none, after: T5).

---

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Menu items too wide | Compact `C`/`W` abbreviations; Qt elide if needed |
| Double conversion on apply | Display-only conversion; do not change apply path |
| Mismatch with spinbox W/L | Use same conversion utilities as `view_state_manager` / W/L controls |
| Regression of done labels/units plan | Reuse `storage_space_label()`; extend tests from `test_wl_preset_catalog.py` |

---

## Testing strategy

- Extend `tests/test_wl_preset_catalog.py` for menu labels with C/W and mode conversion.
- Smoke: toolbar **Window/Level Presets** and image right-click preset submenu on CT + PT sample.

---

## Questions for user (non-blocking)

1. Prefer **`C 40, W 400`** or **`40 / 400`** in the menu?
2. Show converted values only, or always show both stored and display when they differ (menu vs tooltip split)?

**Default if unanswered:** compact ` — C {c}, W {w}{suffix}` in menu; stored values only in tooltip when conversion applies.

---

## Completion notes

**2026-06-04 (coder):** `format_preset_display_values`, extended `format_preset_menu_label` / `format_preset_tooltip`, `populate_wl_preset_menu` passes viewer context. Tests in `tests/test_wl_preset_catalog.py`. T7 manual smoke deferred to tester.
