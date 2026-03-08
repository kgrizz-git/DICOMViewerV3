# Distance Measurement Positioning UX — Plan

**Goal:** Make it easier to position distance measurement endpoints: improve visibility of ends, reduce visual clutter while dragging a handle, and optionally magnify around the active end for precise placement.

**Related TO_DO:** dev-docs/TO_DO.md (line 46): *"Make it easier to position distance measurements - easier to see ends, hide handles while dragging - magnify around end when dragging handle (or maybe if shift+click and drag handle)"*.

**Date:** 2026-03-08  
**Status:** Plan

---

## 1. Current Behavior

- **Measurement structure:** Distance measurements are implemented as `MeasurementItem` (group) in `src/tools/measurement_items.py`, containing a line segment, `DraggableMeasurementText`, and two `MeasurementHandle` instances (start and end). Handles are separate scene items, not Qt-children of the group.
- **Handles:** `MeasurementHandle` is a small green ellipse (diameter 12 px in item coords, with `ItemIgnoresTransformations` so it stays a fixed size on screen). Handles are shown only when the measurement is selected (`show_handles()`), and hidden when deselected (`hide_handles()`). They are movable; dragging updates the measurement line and distance.
- **During handle drag:** `_handle_drag_in_progress` and `_dragging_handle` are set on the parent `MeasurementItem`. Handles remain visible throughout the drag, which can obscure the exact endpoint and make fine placement harder.
- **Magnifier:** The app has a separate "Magnifier" mouse mode (`MagnifierWidget`, `image_viewer._extract_image_region`) that shows a floating magnified region under the cursor. It is not used during measurement handle drag.

---

## 2. Desired Outcomes

| Outcome | Description |
|--------|-------------|
| **Easier to see ends** | Endpoints of the measurement line are clearly visible (e.g. small cross/circle at exact pixel, or stronger visual emphasis when selected). |
| **Hide handles while dragging** | While the user is dragging a handle, that handle (and optionally the other) is hidden so the line end and image are unobstructed. |
| **Optional magnify at handle** | When dragging a handle, show a magnified view centered on the current handle position so the user can place the end precisely. Option: make magnification conditional on modifier (e.g. Shift+drag) to avoid surprising users who prefer no overlay. |

---

## 3. Implementation Plan

### 3.1 Easier to see ends

**Option A — Endpoint markers on the line (recommended):**  
Draw a small visual at each endpoint when the measurement is selected (e.g. a 2–4 px cross or circle at `start_point` and `end_point`). This can be done in `MeasurementItem.paint()`: when selected, after drawing the dashed selection outline, draw two small shapes at the line endpoints in scene coordinates. Use the same color as the line or a high-contrast accent so the exact end is unambiguous even when handles are hidden.

**Option B — Larger or higher-contrast handles:**  
Increase handle size or add a thin outline so they are easier to see. This does not address “hide while dragging” and can still obscure the pixel under the center.

**Files:** `src/tools/measurement_items.py` — `MeasurementItem.paint()` (or a dedicated “endpoint decoration” step called from paint).

---

### 3.2 Hide handles while dragging

- In `MeasurementItem`, when a handle drag starts (`_handle_drag_in_progress = True`, `_dragging_handle` set), hide the handles for the duration of the drag:
  - Either call `hide_handles()` and then show them again on drag end (same as deselection path), or
  - Temporarily hide only the two handle items (e.g. `setVisible(False)`) without removing them from the scene, and show them again on release.
- Ensure `update_handle_positions()` does not re-show handles during drag; keep them hidden until `mouseReleaseEvent` on the handle clears `_handle_drag_in_progress` and `_dragging_handle`, then call `show_handles()` (or set visible True) so they reappear for the next interaction.

**Files:**  
- `src/tools/measurement_items.py`: `MeasurementHandle.mousePressEvent` (after setting drag flags, hide handles via parent), `MeasurementHandle.mouseReleaseEvent` (clear flags, show handles again). `MeasurementItem` may need a method like `hide_handles_during_drag()` / `show_handles_after_drag()` used only for this case, or reuse `hide_handles()`/`show_handles()` with care so that selection state is not confused (e.g. measurement stays selected; only visibility of handles toggles).

**Edge case:** If the user has multiple measurements selected, only the one whose handle is being dragged should hide/show its handles; others keep current behavior.

---

### 3.3 Magnify around end when dragging handle

**Option A — Always magnify during handle drag:**  
While a measurement handle is being dragged, show a magnifier (e.g. reuse `MagnifierWidget`) centered on the current handle position in scene coordinates.  
- **Who drives the magnifier:** The image viewer already has `_extract_image_region()` and `magnifier_widget`. The measurement layer (handles) does not have a reference to the image viewer. So either:  
  - **Coordinate via MeasurementCoordinator / main:** When a handle drag starts, the coordinator (or app) is notified; it tells the active image viewer “show handle-drag magnifier at scene pos (x,y)”. On each handle move, update position; on release, hide. The viewer would need an API such as `show_handle_drag_magnifier(scene_pos)` / `update_handle_drag_magnifier(scene_pos)` / `hide_handle_drag_magnifier()`, and the measurement side must emit signals or callbacks (e.g. from `MeasurementHandle` / `MeasurementItem` up to the coordinator).  
  - **Or:** The scene/view forwards “handle drag” state and handle scene position to the viewer (e.g. via a signal from measurement tool or coordinator).  
- **Reuse existing magnifier:** Use the same `MagnifierWidget` and `_extract_image_region(center_x, center_y, size, zoom_factor)`. During handle-drag mode, center the magnifier on the handle’s scene position. Position the widget (e.g. offset from the handle so it doesn’t cover the point) and update on each move. Use a distinct flag (e.g. `magnifier_mode == "handle_drag"`) so it doesn’t conflict with the normal magnifier mouse mode.

**Option B — Magnify only with Shift+drag (recommended for first iteration):**  
Same as Option A, but show the magnifier only when the user starts the handle drag with Shift held (or holds Shift during drag). This keeps the default behavior lightweight and gives power users a way to get magnification when they need it.  
- In `MeasurementHandle.mousePressEvent`, record whether `event.modifiers() & Qt.KeyboardModifier.ShiftModifier`. Pass this to whoever controls the magnifier (e.g. “show handle-drag magnifier only if shift”).  
- Alternatively, show the magnifier on first move if Shift is pressed, so that “click handle then hold Shift and drag” also works.

**Files:**  
- `src/tools/measurement_items.py`: `MeasurementHandle` — in press/move/release, emit signals or call a callback with (scene_pos, is_drag_active, shift_held).  
- `src/gui/measurement_coordinator.py`: Subscribe to handle-drag state/position; call into image viewer or emit app-level signal for “show/update/hide handle-drag magnifier”.  
- `src/gui/image_viewer.py`: Add handle-drag magnifier API (show/update/hide at scene position), reusing `_extract_image_region` and `MagnifierWidget` (or a second widget to avoid conflicting with cursor magnifier).  
- Optional: `src/main.py` or wherever the image viewer and measurement coordinator are wired, connect coordinator to viewer for handle-drag magnifier.

**Positioning:** Place the magnifier window at a fixed offset from the handle (e.g. top-right of the handle) so the magnified center is on the endpoint and the widget does not cover it. Use the same region size/zoom as the existing magnifier or slightly smaller for a less intrusive overlay.

---

## 4. Suggested Order of Work

1. **Hide handles while dragging** — Small, clear UX win; no new UI or magnifier wiring.  
2. **Easier to see ends** — Endpoint markers in `MeasurementItem.paint()` so the line ends remain visible when handles are hidden.  
3. **Magnify around end** — Add handle-drag → coordinator → viewer wiring and optional (e.g. Shift+drag) magnifier; reuse `_extract_image_region` and `MagnifierWidget`.

---

## 5. Testing

- **Hide handles:** Select a measurement, drag one handle; the handles disappear during drag and reappear on release. The line and endpoint remain visible; distance and position update correctly.  
- **Endpoint markers:** With measurement selected, two small endpoint indicators are visible at the line ends; they are still visible during handle drag when handles are hidden.  
- **Magnifier (if implemented):** With Shift+drag (or always-on) handle drag, a magnifier appears at/near the handle and updates with movement; it hides on release. No conflict with normal Magnifier mode (cursor-based).  
- **Regression:** Deselecting measurement still hides handles; creating a new measurement and moving text/line behave as before; undo/redo of measurement moves still work.

---

## 6. Summary

| Item | Approach |
|------|----------|
| Easier to see ends | Draw small endpoint markers (cross/circle) in `MeasurementItem.paint()` when selected. |
| Hide handles while dragging | In handle press, set drag flags and hide handles; in handle release, clear flags and show handles again. |
| Magnify at handle | Reuse `MagnifierWidget` and `_extract_image_region`; coordinator/viewer API for “show/update/hide at scene pos”; optional modifier (Shift) to trigger. |

Implementing in order: (1) hide handles during drag, (2) endpoint markers, (3) handle-drag magnifier (with Shift modifier option) keeps each step reviewable and avoids scope creep.
