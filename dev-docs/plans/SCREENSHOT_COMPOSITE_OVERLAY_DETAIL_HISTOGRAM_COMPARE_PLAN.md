# Screenshot composite / full-window capture, overlay detail modes + Spacebar, and multi-series histogram — implementation plan

**Source:** `dev-docs/TO_DO.md` — P2 items (screenshot scope, overlay simple/detailed + Spacebar, histogram comparison).

**Related prior work:** `dev-docs/plans/completed/EXPORT_ANNOTATIONS_AND_SCREENSHOTS_PLAN.md` (per-viewport screenshot export); `dev-docs/plans/HISTOGRAM_PROJECTION_PIXEL_VALUES_PLAN.md` (projection pixels in histogram).

**Priority:** P2 (nice-to-have UX).

---

## 1. Executive summary

| Feature | Current state | Target |
|--------|----------------|--------|
| **Screenshots** | `ScreenshotExportDialog` saves **one file per selected subwindow** via `QWidget.grab()` on each `ImageViewer.viewport()` (`src/gui/dialogs/screenshot_export_dialog.py`). | Optional **single composite** image of the **multi-window image grid** (respecting current 1x1 / 1x2 / 2x1 / 2x2 layout and slot order). Optional **entire main window** capture (toolbar, left/right panes, status bar, etc., as currently shown). |
| **Overlay “simple / detailed” + Spacebar** | `OverlayManager` already supports **`mode`** `minimal` / `detailed` / `hidden`** with different default tag lists (`src/gui/overlay_manager.py`). `ConfigManager` exposes `get_overlay_mode` / `set_overlay_mode` (`src/utils/config/overlay_config.py`). **Spacebar** today cycles **`visibility_state` 0→1→2** (show all → hide corner text → hide corner + measurements/ROI text) via `OverlayManager.toggle_overlay_visibility()` and `overlay_coordinator.handle_toggle_overlay` — **not** `overlay_mode`. `OverlayConfigDialog` configures **per-corner / per-modality tags**, not an explicit “simple vs detailed preset” UX. | **Overlay configuration:** clearer **“detail level”** (simple = minimal field set, detailed = extended field set), including **optional extra tags** only in detailed mode (may extend existing per-modality maps or add named presets). **Spacebar:** cycle **`overlay_mode`** **minimal → detailed → hidden** (persist to config), aligned with TO_DO. **Product decision:** whether to **retain** the old `visibility_state` cycle on another shortcut/menu only, or drop it from Spacebar entirely. |
| **Histogram comparison** | `HistogramWidget` plots a **single** blue curve + fill (`src/tools/histogram_widget.py`). `HistogramDialog` drives one primary pixel source per update (`src/gui/dialogs/histogram_dialog.py`). | Allow **multiple distributions** on one axes (e.g. **current slice** + **pinned reference**, or **View 1 vs View 2**), each with a **distinct color**, shared bin edges / axis scaling where possible, legend, and **add / remove** controls (TO_DO suggests entry via histogram UI, e.g. a button). |

---

## 2. Screenshot export: composite grid and full application window

### 2.1 Goals

1. **Composite multi-view image:** When the user selects more than one subwindow (or selects “all visible views”), offer an output mode such as **“Single image (grid as shown)”** that produces **one raster** matching the on-screen **layout** of image viewports (including 1x2 / 2x1 / 2x2 geometry and **slot-to-view** order from `MultiWindowLayout` — `src/gui/multi_window_layout.py`).
2. **Full main window:** Optional **“Entire application window”** (or “Include chrome”) that captures **everything** in the main `QMainWindow` content as the user sees it: toolbars, dock widgets / splitters, navigators if visible, **excluding** modal dialogs on top (grab should run with dialog closed or use explicit geometry — see risks).

### 2.2 Technical approach

**Composite grid (recommended implementation path)**

1. **Discovery:** From the dialog (or coordinator), obtain references already available to `ScreenshotExportDialog`: the list of **subwindow containers** in **visual order** for the current layout. If order is not trivial from the list index alone, add a small API on `MultiWindowLayout` (or pass `multi_window_layout` into the dialog) such as `visible_subwindows_in_layout_order() -> List[SubWindowContainer]` that mirrors how the grid is built for the active `LayoutMode`.
2. **Capture:** For each visible cell, `grab()` the same target as today — **`image_viewer.viewport()`** — to keep **WYSIWYG** (zoom, W/L, overlays). Avoid grabbing the whole `SubWindowContainer` if it adds chrome not shown in “image-only” composite; TO_DO asks for **multi-window view**, which matches **viewport** composition.
3. **Stitch:** After all grabs, compute a **target canvas** size:
   - **2x2:** `max(row0 widths) + max(row1 widths)` is wrong; use **per-cell width/height** from each grab and place in a **2×2 grid** with optional **uniform cell size** (either crop to min common size or pad with margin — **product choice**; min-padding is simplest).
   - **1x2 / 2x1:** horizontal or vertical concatenation with a configurable **gap** (e.g. 2 px divider line for clarity).
4. **Encode:** Save as PNG/JPG like single files; filename e.g. `{prefix}_grid.{ext}` when composite is selected alongside or instead of per-view files.
5. **UI:** In `ScreenshotExportDialog`, add a **radio group** or **combo**:
   - **“Separate file per view”** (current default).
   - **“Single composite image (layout as shown)”** — enabled when ≥2 selected views **or** when layout shows multiple cells (only export **selected** cells that are part of the grid).
   - **“Entire main window”** — **disables** per-view check logic or ignores them and captures `main_window.grab()` (or `winId()` + platform-specific if needed; Qt `QWidget.grab()` is usually sufficient on Windows).

**Full window capture**

- Pass **`parent`** (already `main_window`) or explicit **`QMainWindow`** into the dialog; on export, call **`self.parent().grab()`** after **`self.hide()`** + `QApplication.processEvents()` so the **save dialog is not in the shot** (same pattern as many screen-capture tools). Restore dialog visibility after grab.
- **Privacy:** If privacy mode redacts metadata in panes, the grab naturally includes that; document behavior.

### 2.3 Files to touch (expected)

| File | Change |
|------|--------|
| `src/gui/dialogs/screenshot_export_dialog.py` | UI for output mode; composite stitch; optional `main_window.grab()` path; overwrite checks for new filenames. |
| `src/core/export_app_facade.py` / `src/gui/dialog_coordinator.py` | Pass **`MultiWindowLayout`** or layout-order callback if the dialog cannot infer order from `subwindows` list alone. |
| `src/gui/multi_window_layout.py` (optional) | **`visible_ordered_subwindows()`** helper for deterministic grid placement. |
| `user-docs/USER_GUIDE.md` (when shipping) | Document new export modes. |

### 2.4 Risks and test notes

- **HiDPI:** `grab()` returns device pixels; document that composite resolution equals sum of viewport sizes (can be large).
- **Empty cells:** In 2x2 with only two panes loaded, composite should **only include selected cells** with images; do not leave huge black holes unless intentional.
- **Performance:** Stitching four 4K viewports → allocate `QImage` once and `painter.drawPixmap` into cells; avoid intermediate full-size copies if possible.

### 2.5 Verification

- Manual: 2x2 with different series, export composite → geometry matches screen.
- Manual: Full window with left pane hidden → capture reflects hidden splitter state.
- Optional automated: pure Qt offscreen test with small fixed-size viewports (if test harness exists for widgets).

---

## 3. Overlay: “simple / detailed” in config + Spacebar cycles modes

### 3.1 Current architecture (facts)

- **`OverlayManager.mode`:** `"minimal"` | `"detailed"` | `"hidden"` — controls **which tag list** drives corner text via `get_corner_text` / `overlay_text_builder` (`src/gui/overlay_text_builder.py`).
- **`OverlayManager.visibility_state`:** `0` | `1` | `2` — **independent** layer used by **`toggle_overlay_visibility()`** for Spacebar / context menu “Toggle Overlay”.
- **`should_show_text_overlays()`** returns `mode != "hidden"` **and** `visibility_state == 0` — so **hidden mode** and **visibility_state != 0** both suppress corner overlays; this interaction must be redesigned if Spacebar only cycles `mode`.

### 3.2 Target UX (from TO_DO)

- **Overlay configuration:** Users can configure something like **“simple view”** and **“detailed view”** — additional tags in detailed view (maps cleanly to **minimal vs detailed field lists**, possibly per modality, aligned with `OverlayConfigDialog` + config storage).
- **Spacebar:** Cycles **simple → detailed → hidden** (i.e. **`overlay_mode`** cycle), not the legacy three **visibility** states — **unless** product retains both behaviors.

### 3.3 Recommended design decisions (for planner / UX sign-off)

1. **Spacebar primary behavior:** Cycle **`config_manager` / `OverlayManager` `overlay_mode`:** `minimal` → `detailed` → `hidden` → `minimal`. Persist with **`set_overlay_mode`** after each press so all panes reload consistently (broadcast to **all** `OverlayManager` instances if the app uses one per subwindow — verify in `subwindow_manager_factory` / lifecycle).
2. **Legacy visibility cycle:** Either:
   - **(A)** Remove from Spacebar; expose **“Hide corner overlays”** / **“Hide all annotation text”** only in **View** menu or context menu, still using `visibility_state`; or
   - **(B)** Keep **Shift+Space** for old `visibility_state` cycle; document in Help.
3. **Unify gating:** Refactor `should_show_text_overlays()` so **`hidden` mode** is the single source of “no corner DICOM overlay,” and **`visibility_state`** is deprecated or only used for secondary “dim” states — avoids contradictory combinations.

### 3.4 Config / dialog work

- **`OverlayConfigDialog`:** Add a section **“Default detail level (minimal vs detailed)”** with:
  - Short explanation: **Minimal** = fewer lines; **Detailed** = extra tags (list driven by same lists as `OverlayManager.minimal_fields` / `detailed_fields` or **per-modality overrides** from config).
  - Optional: **“Tags only in detailed mode”** multi-select that **writes** into **detailed** field list only (minimal unchanged), stored in existing overlay tag maps if the schema already splits by corner/modality — extend schema only if necessary.
- **Startup / load:** Ensure `OverlayManager.set_mode(config.get_overlay_mode())` runs when subwindows are created and when config is imported from **customizations** (`src/utils/config/customizations_config.py` already snapshots `overlay.mode` — confirm key name matches).

### 3.5 Code touchpoints (expected)

| Area | Files |
|------|--------|
| Spacebar | `src/gui/keyboard_event_handler.py` — call new **`cycle_overlay_detail_mode()`** on app/coordinator instead of `handle_toggle_overlay` **or** branch inside coordinator. |
| Coordinator | `src/gui/overlay_coordinator.py` — implement cycle + refresh all affected viewers; consider **all subwindows**, not only focused. |
| Overlay manager | `src/gui/overlay_manager.py` — align `set_mode` with config; document interaction with `visibility_state`. |
| Context menu | `src/gui/image_viewer_context_menu.py` — update label from “Toggle Overlay (Spacebar)” to **“Cycle overlay detail (Spacebar)”** or similar. |
| Docs | Keyboard section in user guide; `AGENTS.md` only if behavior conventions change materially. |

### 3.6 Tests

- Unit: cycling order and persistence of `overlay_mode`.
- Integration (optional): one Qt test that simulates Spacebar and asserts overlay text item count or mock parser output lines differ between minimal and detailed.

---

## 4. Histogram: multiple distributions for comparison

### 4.1 Goals

- Plot **≥2 histogram curves** on the same axes with **distinct colors** and a **legend**.
- Typical sources: **(a)** “Pin” current distribution and compare after changing W/L or slice; **(b)** compare **focused view** vs **another subwindow**; **(c)** ROI vs whole image (ROI path may already exist via `set_roi_mask` — extend to **multiple** masks/series).
- Entry point per TO_DO: **histogram dialog** — e.g. buttons **“Add comparison (current)”**, **“Clear comparisons”**.

### 4.2 Data model

Define a small immutable structure (dataclass or typed dict):

- **`label: str`** (e.g. “Slice 42”, “View 2”, “Pinned @ 10:32”)
- **`pixels: np.ndarray`** (1D float or int, already masked if ROI)
- **`color: str | tuple`** (matplotlib color)
- **`linestyle`** optional for accessibility (color-blind: vary dash + color)

**Primary series** remains the live-updating histogram from the current callbacks (`HistogramDialog.update_histogram`). **Secondary series** are stored in a **`List[HistogramSeries]`** on the dialog, max **N** (e.g. 4–6) for performance.

### 4.3 Binning and axis alignment (important)

- **Shared bins:** When adding a comparison, recompute **global** `x_min` / `x_max` across **primary + all pinned** datasets (respecting rescale flag) and pass to **`HistogramWidget`** so all `np.histogram` calls use **`range=(x_min, x_max)`** and identical **`bins=256`**.
- **Y-axis:** Use **max count across all series** (or per-series max then global max) for linear scale; for log scale, use the same floor logic as today for each series before taking max.
- **Window/level box:** Keep drawing **one** box for the **live** window (primary); optionally ghost a second box for pinned W/L — **defer** unless explicitly requested.

### 4.4 `HistogramWidget` API change

Current: `set_pixel_array` drives a single histogram.

**Preferred approach:**

- Add **`set_comparison_series(series_list: Optional[List[Tuple[np.ndarray, str, str]]])`** or pass combined structure.
- Refactor **`_update_histogram`** to:
  1. Clear axes.
  2. For each series: `hist, bins = np.histogram(pixels, bins=256, range=rng)` (same `rng`).
  3. `plot` / `fill_between` with **alpha** (e.g. 0.25 fill) per color.
  4. Draw W/L overlay once.
  5. `legend()`.

Backward compatibility: if comparison list empty, behavior matches current single-series plot.

### 4.5 Dialog UI (`HistogramDialog`)

- **“Add current as comparison”** — snapshots current `pixel_array` (after rescale / projection logic) + default label from slice index / view suffix (`title_suffix`).
- **“Remove all comparisons”**.
- **List widget** of pinned series with **remove** per row (optional v2).
- **Color assignment:** rotate a fixed palette (e.g. tab10: blue primary, orange, green, red, …).

### 4.6 Performance

- Pinning stores **1D arrays**; avoid pinning **full 2D** slices twice — flatten once when adding.
- Large series: optional **subsample** (e.g. max 2e6 samples random) for histogram only — document in tooltip if implemented.

### 4.7 Files to touch (expected)

| File | Change |
|------|--------|
| `src/tools/histogram_widget.py` | Multi-series plot; shared bin range; legend; font scaling still runs. |
| `src/gui/dialogs/histogram_dialog.py` | State for pinned series; buttons; pass series into widget; clear on series change / new study (hook from coordinator if needed). |
| `src/gui/dialog_coordinator.py` | Optional: reset pins when closing study — avoid stale memory. |

### 4.8 Tests

- **Unit:** Given two known small arrays and fixed bins, assert two peaks appear and legend has two entries (matplotlib `axes.get_legend_handles_labels()` or image comparison optional).
- **Manual:** Pin, change slice, confirm primary moves and pinned stays fixed.

---

## 5. Phasing and dependencies

| Phase | Deliverable | Depends on |
|-------|-------------|------------|
| **H1** | Histogram multi-series (widget + dialog + tests) | None (orthogonal). |
| **H2** | Screenshot composite + full window | None; may reuse layout helper. |
| **H3** | Overlay Spacebar + config UX | UX sign-off on legacy `visibility_state` vs shortcut; may touch multiple subwindows’ overlay refresh. |

**Risk tier:** Medium for **H3** (behavior change for long-time users); low–medium for **H1**/**H2**.

---

## 6. Open questions (resolve before coding)

1. **Screenshots:** Should composite mode **replace** per-file export or always be an **additional** optional output when multiple views are selected?
2. **Overlays:** Should **`hidden`** hide **only** DICOM corner text, or also **MPR / fusion banners**? Align with `should_show_text_overlays` call sites in `overlay_manager.py`.
3. **Histogram:** Maximum number of simultaneous curves? Subsample policy for huge volumes?

---

## 7. References (code)

- Screenshot dialog: `src/gui/dialogs/screenshot_export_dialog.py`
- Multi-window layout: `src/gui/multi_window_layout.py`
- Overlay modes and visibility: `src/gui/overlay_manager.py`, `src/gui/overlay_coordinator.py`, `src/utils/config/overlay_config.py`
- Histogram: `src/gui/dialogs/histogram_dialog.py`, `src/tools/histogram_widget.py`
- Prior screenshot plan: `dev-docs/plans/completed/EXPORT_ANNOTATIONS_AND_SCREENSHOTS_PLAN.md`
