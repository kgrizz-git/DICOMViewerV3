# UX Improvements – Batch 1 Implementation Plan

**Created:** 2026-03-21  
**Covers TO_DO items (UX/Workflow section, lines 45–50):**

1. [Make window map thumbnail interactive](#1-window-map-thumbnail-interactive)
2. [Make toolbar contents / ordering customizable](#2-toolbar-customization)
3. [Add alternative window/level interaction](#3-alternative-windowlevel-interaction)
4. [Set min/max W/L from pixel bit depth](#4-minmax-windowlevel-from-bit-depth)
5. [Add overlay configuration to image right-click context menu](#5-overlay-configuration-in-right-click-context-menu)
6. [Reduce default line thicknesses and annotation font sizes](#6-reduce-default-line-thicknesses-and-font-sizes)

---

## Overall notes / cross-cutting concerns

- Items **3, 4, 5** are self-contained with minimal side-effects and are the easiest to land.
- Items **1 and 6** are also low-risk but require careful state wiring (item 1) and awareness of
  persisted user configs (item 6).
- Item **2** (toolbar customization) is substantially more complex than the others and should be
  treated as a separate workstream.
- Items **3 and 4** both touch `image_viewer.py` → `view_state_manager.py` and can conflict
  if worked on in parallel; sequence them or use separate branches.
- Item **5** overlaps lightly with item **3**: if you add a context-menu W/L action, put it in
  the same context-menu edit pass as item 5 to avoid two separate context-menu editing touches.

---

## 1. Window Map Thumbnail Interactive

**Priority:** P2  
**Key files:**
- [src/gui/window_slot_map_widget.py](../src/gui/window_slot_map_widget.py) — `WindowSlotMapWidget`, `_DraggableWindowSlotMapContainer`, `WindowSlotMapPopupDialog`
- [src/main.py](../src/main.py) — `_on_focused_subwindow_changed`, `_on_layout_changed`, `set_window_slot_map_callbacks`
- [src/gui/main_window.py](../src/gui/main_window.py) — `set_window_slot_map_callbacks`

### What already exists

`WindowSlotMapWidget` is a pure paint widget (80 × 80 px grid of 4 cells). It already draws thumbnails, the focused-slot border, and colored dots. When shown in the popup via `_DraggableWindowSlotMapContainer`, it has `WA_TransparentForMouseEvents = True` so clicks fall through to the draggable container. The inline bar version (inside the navigator bar) receives events normally.

### Goal

Clicking a cell in either the inline or popup variant should:
1. Focus the corresponding view (update `multi_window_layout.focused_subwindow`).
2. Keep the current layout unchanged.
3. If the layout is 1×2 / 2×1 and the clicked slot is not currently revealed, reveal the corresponding row/column within that same layout rather than switching layouts.

### Steps

#### 1a. Add a `cell_clicked` signal to `WindowSlotMapWidget`

```python
from PySide6.QtCore import Signal
cell_clicked = Signal(int)  # slot index 0–3
```

#### 1b. Add `mousePressEvent` to `WindowSlotMapWidget`

Compute which cell (0–3) was clicked from `event.position()`, then emit `cell_clicked`. Use the same geometry math already present in `paintEvent`:

```python
def mousePressEvent(self, event):
    if event.button() != Qt.MouseButton.LeftButton:
        return super().mousePressEvent(event)
    rect = self.rect().adjusted(1, 1, -1, -1)
    side = min(rect.width(), rect.height())
    if side <= 0:
        return
    cell_side = side // 2
    ox = rect.left() + (rect.width() - side) // 2
    oy = rect.top() + (rect.height() - side) // 2
    p = event.position().toPoint()
    col = (p.x() - ox) // cell_side
    row = (p.y() - oy) // cell_side
    if 0 <= col <= 1 and 0 <= row <= 1:
        slot = row * 2 + col
        self.cell_clicked.emit(slot)
    super().mousePressEvent(event)
```

#### 1c. Expose a `focus_slot_callback` on `WindowSlotMapWidget`

Add an optional callable attribute `focus_slot_callback: Optional[Callable[[int], None]] = None` and connect it from `cell_clicked`:

```python
def _on_cell_clicked(self, slot: int) -> None:
    if self.focus_slot_callback:
        self.focus_slot_callback(slot)
```

Wire `cell_clicked.connect(self._on_cell_clicked)` in `__init__`.

#### 1d. Fix the popup: remove `WA_TransparentForMouseEvents` from the embedded widget in `_DraggableWindowSlotMapContainer`

The `WA_TransparentForMouseEvents` flag causes clicks to fall through. Instead, let the map widget receive events, and prevent the container's drag logic from interfering: only start a container drag when the press lands **outside** the map widget's rect, or use a dedicated drag handle area (the `_LayoutMapTopBar` already serves this purpose).

#### 1e. Wire in `main.py`

After `set_window_slot_map_callbacks(...)`, also set:

```python
def _focus_slot(slot: int) -> None:
    slot_to_view = self.multi_window_layout.get_slot_to_view()
    view_idx = slot_to_view[slot] if slot < len(slot_to_view) else slot
    subwindows = self.multi_window_layout.get_all_subwindows()
    if view_idx < len(subwindows) and subwindows[view_idx]:
        mode = self.multi_window_layout.get_layout_mode()
        self.multi_window_layout.set_focused_subwindow(subwindows[view_idx])
        # Keep the current layout. Focus change should drive which row/column is revealed
        # in 1x2 / 2x1 layouts via the normal layout/focus refresh path.

widget.focus_slot_callback = _focus_slot
# Also wire popup widget if present
```

Also set the same callback on the popup widget (`_window_slot_map_widget_popup`).

### Risks / complications

- The popup's drag-vs-click conflict: single click on the map area should focus, but a drag on the same area currently moves the popup. Resolved by using `_LayoutMapTopBar` as the exclusive drag handle and forwarding click events through to the map widget.
- `set_focused_subwindow` must trigger the normal focus-change path; verify `_on_focused_subwindow_changed` runs and that 1×2 / 2×1 layouts reveal the newly focused row/column without a layout mode change.
- The inline bar map widget is smaller (80 px total → 39 px cells), so hit targets are small but adequate.

---

## 2. Toolbar Customization

**Priority:** P2  
**Key files:**
- [src/gui/main_window.py](../src/gui/main_window.py) — `_create_toolbar()`, all `self.mouse_mode_*_action` attributes
- [src/utils/config/](../src/utils/config/) — new mixin needed for toolbar layout
- [src/gui/dialogs/](../src/gui/dialogs/) — new `toolbar_config_dialog.py`
- [src/gui/main_window_menu_builder.py](../src/gui/main_window_menu_builder.py) — if a menu entry is needed

### Complexity and risk: HIGH

This is the most involved item in the batch. The toolbar has ~20 actions and widgets hardcoded in a single `_create_toolbar()` method, and many actions are referenced by name throughout `main_window.py` and signal-wiring code. A full drag-and-drop toolbar editor (like Qt's built-in `QMainWindow` toolbar drag) is possible but requires significant scaffolding.

### Recommended approach: per-section visibility plus per-section ordering

**Phase 1 – Toggle visibility of toolbar groups:**

- Define a list of toolbar "sections" (each = a named group of related actions).
- Add a "Customize Toolbar…" entry to the **View** menu (and optionally the toolbar right-click context menu).
- Open a dialog with checkboxes for each section.
- Persist visibility state in config (new `toolbar_config.py` mixin under `src/utils/config/`).
- On startup and after dialog `OK`, call a `_apply_toolbar_config()` method that calls `action.setVisible(visible)` for each action in each section.

Example sections: `Mouse Mode Tools`, `Privacy`, `View Controls`, `Series Navigation`, `Overlay Font`, `Scroll Wheel`.

**Section ordering:**
- Store section order as a list in config.
- Rebuild the toolbar from a stable section-definition list in the configured order.
- Keep the existing `QAction` objects on `MainWindow`; only re-add them in different section order.
- Do not support per-action ordering. Per-section ordering is sufficient and materially simpler.

### Steps

1. Create `src/utils/config/toolbar_config.py` mixin with `get_toolbar_section_visible(name)` / `set_toolbar_section_visible(name, visible)`.
2. Add mixin to `ConfigManager`.
3. Add `get_toolbar_section_order()` / `set_toolbar_section_order(order)` to the same mixin.
4. Refactor `_create_toolbar()` so it builds from a section-definition structure, for example `list[ToolbarSection]`, where each section contains its title and the existing actions/widgets that belong to it.
5. Add `_rebuild_toolbar_from_config()` that re-adds sections in the configured order and hides sections marked invisible.
6. Wrap non-`QAction` toolbar items (`QLabel`, spacer widget, `QComboBox`) in `QWidgetAction` or an equivalent reusable section item so they can participate in section rebuilds.
7. Create `src/gui/dialogs/toolbar_config_dialog.py` with checkboxes for visibility and a simple move-up / move-down UI for section ordering; emit a `toolbar_config_changed` signal.
8. Wire in `main_window_menu_builder.py`.

### Risks / complications

- `mouseModeActions` list in `set_mouse_mode_checked()` / `update_toolbar_buttons()` iterates over `all_actions`. If actions are hidden (not removed), they still work with keyboard shortcuts and signals — this is fine.
- The spacer `QWidget` and `QLabel` widgets (not `QAction`s) cannot be treated like ordinary actions; section rebuilds need a consistent wrapper model, likely `QWidgetAction`.
- If the user hides all mode buttons, the app still needs to handle mode changes via keyboard shortcuts.
- Section ordering is tractable; per-action ordering is intentionally out of scope.

---

## 3. Alternative Window/Level Interaction

**Priority:** P1  
**Key files:**
- [src/gui/image_viewer.py](../src/gui/image_viewer.py) — `mousePressEvent`, `mouseMoveEvent`, `mouseReleaseEvent`
- [src/core/view_state_manager.py](../src/core/view_state_manager.py) — `handle_window_level_drag`, `handle_right_mouse_press_for_drag`
- [src/utils/config/display_config.py](../src/utils/config/display_config.py) — if a config option is needed

### Current state

Right-mouse-drag for window/level is already implemented and working:
- `right_mouse_press_for_drag` signal → `handle_right_mouse_press_for_drag()`
- `window_level_drag_changed` signal → `handle_window_level_drag(center_delta, width_delta)`
- Context menu only shows if drag distance < 5 px

So the "alternative" may refer to **middle-mouse drag** or **W + left-drag modifier** for users who want left-button pan to coexist with easy W/L adjustment in a different mode.

### Recommendation

Do **not** add a second mouse gesture by default. The current right-click-and-drag window/level behavior already satisfies the core interaction need. This item should first be validated as a documentation / discoverability issue rather than a missing capability.

### Steps

1. Verify the current right-drag W/L behavior is reliable in the main use cases and document it in the user guide / quick start if missing.
2. Decide whether this TO_DO item should be reworded from "add alternative interaction" to "make existing W/L drag more discoverable".
3. Only if testing shows the current interaction is insufficient, evaluate a modifier-based alternative such as `W + drag`; avoid adding middle-click as a default recommendation.

### Risk: overlap with item 5

If item 3 remains a documentation-only change, this conflict largely disappears. If a future alternate gesture is added, batch it with the same `image_viewer.py` input-handling edit pass as item 5 or item 4.

### Risks / complications

- The main risk here is unnecessary complexity: adding another gesture can create discoverability gains for some users while making input handling harder to reason about.
- If a second gesture is ever added later, validate platform conflicts and avoid duplicating fragile drag-init logic.

---

## 4. Min/Max Window/Level from Bit Depth

**Priority:** P1  
**Key files:**
- [src/core/dicom_pixel_stats.py](../src/core/dicom_pixel_stats.py) — pixel range utilities
- [src/core/dicom_window_level.py](../src/core/dicom_window_level.py) — `get_window_level_from_dataset`
- [src/core/view_state_manager.py](../src/core/view_state_manager.py) — `set_series_pixel_range`, `get_series_pixel_range`
- [src/core/slice_display_manager.py](../src/core/slice_display_manager.py) — where `set_series_pixel_range` is called
- [src/gui/window_level_controls.py](../src/gui/window_level_controls.py) — (likely) W/L spinboxes / slider
- Possibly [src/gui/image_viewer.py](../src/gui/image_viewer.py) — context menu entry for "Full Range"

### Goal

"Set min/max W/L using min/max pixel value possible (raw or rescaled) based on bit depth" should mean using the **full theoretical representable range**, then converting that range into rescaled units when `use_rescaled_values` is enabled.

This is distinct from the observed series range already available via `get_series_pixel_range()`.

### New utility: `get_bit_depth_pixel_range(dataset)`

Add to `dicom_pixel_stats.py` (or `dicom_window_level.py`):

```python
def get_bit_depth_pixel_range(dataset) -> tuple[Optional[float], Optional[float]]:
    """Return theoretical (min, max) based on BitsAllocated/BitsStored/PixelRepresentation."""
    try:
        bits_stored = int(getattr(dataset, 'BitsStored', 0)) or int(getattr(dataset, 'BitsAllocated', 16))
        signed = int(getattr(dataset, 'PixelRepresentation', 0)) == 1
        if signed:
            lo = -(2 ** (bits_stored - 1))
            hi = 2 ** (bits_stored - 1) - 1
        else:
            lo = 0
            hi = 2 ** bits_stored - 1
        return float(lo), float(hi)
    except Exception:
        return None, None
```

If rescale is active, convert the raw theoretical range into rescaled units using slope/intercept. Width should use the magnitude of the slope so it remains positive.

Example:

```python
raw_lo, raw_hi = get_bit_depth_pixel_range(dataset)
if use_rescaled_values and raw_lo is not None and raw_hi is not None:
    slope = float(rescale_slope) if rescale_slope is not None else 1.0
    intercept = float(rescale_intercept) if rescale_intercept is not None else 0.0
    rescaled_lo = raw_lo * slope + intercept
    rescaled_hi = raw_hi * slope + intercept
    lo = min(rescaled_lo, rescaled_hi)
    hi = max(rescaled_lo, rescaled_hi)
```

Store this in `ViewStateManager` alongside `series_pixel_min/max`.

### UX: where to expose "Full Range"

**Option A – Context menu** ("Set Full Bit-Depth Range" action under a W/L submenu in the image viewer context menu). This is consistent with how W/L presets are already exposed.

**Option B – Button in the W/L controls widget** ("Min/Max" button next to the reset button).

Both options can coexist. Option A is lower effort; Option B is more discoverable.

### Steps

1. Add `get_bit_depth_pixel_range(dataset)` to `dicom_pixel_stats.py`.
2. In `SliceDisplayManager._display_slice()` (where `set_series_pixel_range` is called), also compute and store the theoretical full-range values in `ViewStateManager` — add `set_bit_depth_pixel_range` / `get_bit_depth_pixel_range` to `ViewStateManager`.
3. Add a `set_full_bit_depth_wl_callback` on `ImageViewer` (similar to `get_window_level_presets_callback`).
4. Add context menu entry "Set Full Range (Bit Depth)" that calls the callback.
5. In the callback / handler, update `WindowLevelControls.set_ranges(...)` first so the theoretical values are inside the current allowed range, then apply `window_center = (lo + hi) / 2` and `window_width = hi - lo`.
6. Update `ViewStateManager.handle_window_changed()` so that setting a custom W/L clears the "preset" highlight.

### Overlaps / conflicts

- Any context menu edit here should be batched with item 5.
- `rescale_slope / intercept` handling is part of the core definition of the feature, not an optional add-on.

### Risks / complications

- `BitsStored` vs `BitsAllocated`: some DICOM files don't set `BitsStored`; fall back to `BitsAllocated`.
- Negative rescale slopes must be handled by sorting the converted endpoints and deriving width from `hi - lo` after conversion.
- `WindowLevelControls` will clamp values unless its ranges are widened first; the implementation must update control ranges before setting the theoretical full-range W/L values.
- The bit-depth range calculation is arithmetic only and should not create a performance concern.

---

## 5. Overlay Configuration in Right-Click Context Menu

**Priority:** P1  
**Key files:**
- [src/gui/image_viewer.py](../src/gui/image_viewer.py) — context menu build block (~line 1930+)
- [src/gui/dialogs/overlay_config_dialog.py](../src/gui/dialogs/overlay_config_dialog.py) — `OverlayConfigDialog`
- [src/gui/dialogs/overlay_settings_dialog.py](../src/gui/dialogs/overlay_settings_dialog.py) — `OverlaySettingsDialog`
- [src/core/subwindow_lifecycle_controller.py](../src/core/subwindow_lifecycle_controller.py) — where focused-subwindow `ImageViewer` signals are wired
- [src/gui/main_window_menu_builder.py](../src/gui/main_window_menu_builder.py) — existing menu entries for overlay dialogs

### Current state

- "Toggle Overlay (Spacebar)" is already in the context menu.
- Full overlay config dialogs exist (`OverlayConfigDialog`, `OverlaySettingsDialog`) but are only accessible from the View/Overlay menu, not the right-click context menu.
- `MainWindow` already exposes `overlay_config_requested` and `overlay_settings_requested`; the image-viewer context menu needs its own equivalent entry-point signals or a direct callback path.

### Goal

Add an "Overlay Configuration…" submenu (or direct entry) to the existing context menu, providing quick access to:
- Overlay mode toggle (minimal / detailed / hidden) — radio actions
- "Overlay Settings…" (font, color)
- "Configure Overlay Tags…" (per-modality tag assignment)

### New signals needed on `ImageViewer`

```python
overlay_settings_requested = Signal()   # → open OverlaySettingsDialog
overlay_config_requested = Signal()     # → open OverlayConfigDialog (tag config)
```

(Check whether these already exist; if so, reuse them.)

### Steps

1. Add the two signals to `ImageViewer` if not already present.
2. In the context menu build block (after the existing "Toggle Overlay" action), add:
   ```python
   overlay_menu = context_menu.addMenu("Overlay Configuration")
   overlay_settings_action = overlay_menu.addAction("Overlay Settings…")
   overlay_settings_action.triggered.connect(self.overlay_settings_requested.emit)
   overlay_config_action = overlay_menu.addAction("Configure Overlay Tags…")
   overlay_config_action.triggered.connect(self.overlay_config_requested.emit)
   ```
3. Wire `image_viewer.overlay_settings_requested` → `app._open_overlay_settings()` in the focused-subwindow wiring path, following the same pattern as other `ImageViewer` dialog-open signals such as `annotation_options_requested`.
4. Wire `image_viewer.overlay_config_requested` → `app._open_overlay_config()` similarly.
5. Verify that the existing View menu entries remain working (no double-connection issue).

### Risks / complications

- Low risk overall. The dialogs already exist and work; this just adds new entry points.
- Ensure the dialog is opened parented to `self.main_window` (same as existing entries), not to the `ImageViewer` widget, to avoid the dialog disappearing when the image viewer loses focus.
- Overlap with item 3/4: if all three context menu changes (items 3, 4, 5) are batched, keep the context menu structure consistent — put W/L actions in a "Window/Level" submenu for cleanliness.

---

## 6. Reduce Default Line Thicknesses and Font Sizes

**Priority:** P2  
**Status:** Implemented (defaults + shipped `default_config` merge values); see verification below.  
**Key files:**
- [src/utils/config/roi_config.py](../src/utils/config/roi_config.py) — `get_roi_line_thickness` / `get_roi_font_size` **fallback** defaults when keys are absent from merged config
- [src/utils/config/measurement_config.py](../src/utils/config/measurement_config.py) — measurement line / font **fallback** defaults
- [src/utils/config_manager.py](../src/utils/config_manager.py) — `default_config` dict used when creating a **new** config file and when merging loaded JSON over defaults (keys present in `default_config` seed first-time values)
- [src/utils/config/annotation_config.py](../src/utils/config/annotation_config.py) — `get_text_annotation_font_size` (default 12, already at target; no change)
- Tests: [tests/config/test_roi_config.py](../tests/config/test_roi_config.py), [tests/config/test_measurement_config.py](../tests/config/test_measurement_config.py)

### Proposed default changes

| Setting | Previous default | Target default | Where updated |
|---|---|---|---|
| ROI line thickness | 6 | 3 | `roi_config.py` `.get(..., 3)` + `default_config["roi_line_thickness"]` |
| ROI font size | 14 | 12 | `roi_config.py` `.get(..., 12)` + `default_config["roi_font_size"]` |
| Measurement line thickness | 6 | 3 | `measurement_config.py` + `default_config` |
| Measurement font size | 14 | 12 | `measurement_config.py` + `default_config` |
| Text annotation font size | 12 | 12 | (unchanged) |

### Implementation detail (read this before changing defaults again)

1. **Mixin fallbacks** (`roi_config.py`, `measurement_config.py`): `dict.get("key", default)` applies when the key is missing from `self.config` after `_load_config()` merge.
2. **Seeded defaults** (`config_manager.py` → `default_config`): ensures **brand-new** installs get 3/12 even if merge logic evolves; keeps documentation aligned with actual first-run JSON.
3. **Existing users:** If `roi_line_thickness` / `roi_font_size` (or measurement equivalents) are already persisted from an older run, **this change does not overwrite them**. Users can adjust values in **Annotation Options** or clear those keys in their config JSON if they want the new shipped defaults without losing other preferences.

### Verification checklist

- [ ] Delete or rename `%APPDATA%\DICOMViewerV3\dicom_viewer_config.json` (Windows) or start on a clean profile; confirm Annotation Options show **12** / **3** for ROI and measurement spinboxes.
- [ ] Draw a new rectangle ROI and a distance measurement; confirm thinner stroke and smaller label at default zoom.
- [ ] Run `pytest tests/config/test_roi_config.py tests/config/test_measurement_config.py -q`.

### Risks / complications

- Very low risk to the code itself.
- May surprise long-term users if they reset to defaults expecting the old thick lines.
- ROI/measurement tools read settings at creation/update time via `ConfigManager`; no scene refactor required.

---

## Suggested implementation order

For minimal conflict and good incremental delivery:

1. **Item 6** — Smallest change, no regressions, quick win. Verify visually.
2. **Item 5** — Low risk, purely additive to context menu.
3. **Item 4** — Implement separately; it touches W/L ranges, state, and context menu.
4. **Item 1** — Moderate effort; isolate to `window_slot_map_widget.py` and `main.py` wiring.
5. **Item 2** — Treat as a separate feature workstream; design and implement independently.
6. **Item 3** — Reassess after documentation / discoverability review; it may not require code changes.
