# Plan: Measurement Handle Drag Highlight Suppression

Last updated: 2026-05-31

## Goal and success criteria

When a user drags a distance measurement endpoint handle, the measurement should not draw the yellow selected/outlined styling during the drag. The endpoint remains draggable, the optional magnified handle-drag viewer still works, and selection/handles return to the normal selected state after release.

Success criteria:

- Dragging a distance measurement start or end handle does not show the yellow dashed selected line while the mouse button is down.
- The magnified viewer path does not show the unwanted yellow outline or endpoint marker during handle drag.
- Releasing the handle restores normal selected styling and visible handles.
- Whole-measurement selection, movement, delete, copy/paste, and text-label dragging are unchanged.

## Context and links

- Backlog item: `dev-docs/TO_DO.md` Bugs / Correctness, "Measurement handle drag - spurious highlight".
- Primary owner: `src/tools/measurement_items.py`.
- Related creator/manager: `src/tools/measurement_tool.py`.
- Current state observed from code:
  - `MeasurementHandle.mousePressEvent()` sets `_handle_drag_in_progress` and `_dragging_handle` on the parent `MeasurementItem`.
  - `MeasurementItem.paint()` always draws the yellow dashed selected line when `isSelected()` is true.
  - The paint path already skips endpoint crosshair markers for the handle being dragged, but does not suppress the selected-line overlay itself.
  - `MeasurementHandle.paint()` hides the active handle while dragging, so event routing depends on keeping the hidden handle alive in the scene.

## Task graph and gates

### Ordering

- T1 -> T2 -> T3 -> T4.
- T5 can run after T2 if the graphics behavior is covered by unit tests first.

### Verification gates

- Gate 1: A focused Qt graphics test demonstrates that selected styling is suppressed only during handle drag.
- Gate 2: Manual smoke confirms normal selected styling returns after release and the magnified viewer no longer shows the spurious highlight.

### File / area ownership

- `src/tools/measurement_items.py` -> coder.
- `tests/test_measurement_items.py` or a focused measurement graphics test file -> tester/coder.
- `dev-docs/orchestration/AGENT_SMOKE.md` optional manual note/checklist update -> tester, only if the manual smoke script needs a reusable step.

## Phases

### Phase 1 - Reproduce and pin the state transition

- [ ] (T1) Reproduce the issue with one distance measurement and both endpoint handles (owner: tester, parallel-safe: no, stream: none, after: none).
- [ ] (T2) Add a focused test or small test helper that exercises the selected measurement paint decision when `_handle_drag_in_progress` is true (owner: coder, parallel-safe: no, stream: none, after: T1).
- [ ] (T3) Confirm the test fails or documents the current selected-line behavior before implementation (owner: tester, parallel-safe: no, stream: none, after: T2).

### Phase 2 - Suppress selected styling only during handle drag

- [ ] (T4) Update `MeasurementItem.paint()` so the yellow dashed selected outline and endpoint markers are skipped while `_handle_drag_in_progress` is true, without clearing selection or hiding handles globally (owner: coder, parallel-safe: no, stream: none, after: T3).
- [ ] (T5) If the magnified viewer paints a separate measurement representation, route the same "active handle drag" state into that rendering path or confirm it already consumes the cleaned scene output (owner: coder, parallel-safe: no, stream: none, after: T4).
- [ ] (T6) Keep the active handle hidden-but-interactive behavior intact; do not remove the dragging handle from the scene during the drag (owner: coder, parallel-safe: no, stream: none, after: T4).

### Phase 3 - Regression coverage and UX verification

- [ ] (T7) Add or update tests for both start-handle and end-handle drag state transitions: selected before press, suppressed styling during drag, selected styling restored after release (owner: tester, parallel-safe: no, stream: none, after: T4).
- [ ] (T8) Manually verify distance measurement selection, endpoint dragging, text-label dragging, deletion, and copy/paste still behave normally (owner: tester, parallel-safe: no, stream: none, after: T7).
- [ ] (T9) Manually verify Shift+drag or any magnified-handle workflow does not display the yellow selected outline during the drag (owner: tester, parallel-safe: no, stream: none, after: T7).

## Risks and mitigations

- Risk: Clearing selection during drag would remove handles or break keyboard/delete behavior. Mitigation: suppress painting from `_handle_drag_in_progress`; do not call `setSelected(False)` for the parent measurement.
- Risk: Removing handles from the scene would break mouse move/release events. Mitigation: keep the current hidden-but-interactive active-handle pattern.
- Risk: Angle measurements use a separate implementation. Mitigation: this plan is scoped to distance measurement handles; inspect `src/tools/angle_measurement_items.py` only if the same bug is observed there.

## Modularity and file-size guardrails

Keep the implementation inside `MeasurementItem.paint()` or a tiny helper such as `_should_paint_selection_outline()`. Avoid broad measurement-tool refactors.

## Testing strategy

- Run `.\.venv\Scripts\python.exe -m pytest tests/test_measurement_items.py -q`.
- If a new focused test file is created, run it directly.
- Run the relevant ROI/measurement regression subset before marking the backlog item complete.
- Manual smoke: draw a measurement, select it, drag each endpoint with and without Shift, and confirm the magnifier plus main viewer suppress the yellow drag outline.

## Questions for user

None blocking. The intended behavior is already specific: no yellow selected/outlined styling while a handle is actively being dragged.

## Completion notes

**Done 2026-06-03.** Implemented in `src/tools/measurement_items.py`:

- Added a tiny helper `MeasurementItem._should_paint_selection_outline()` returning `isSelected() and not _handle_drag_in_progress`.
- `MeasurementItem.paint()` now gates the yellow dashed selected line **and** the endpoint crosshair markers on that helper, so all selected styling is suppressed only while a handle is actively dragged. Selection state and handles are untouched (no `setSelected(False)`, handles stay in scene), so styling returns to normal on release.
- **Magnified viewer (T5):** no separate measurement representation exists — the handle-drag magnifier renders via `QGraphicsScene.render()` (`image_viewer_view.py:_render_scene_region`, line ~1136), which calls each item's `paint()`. Suppressing the overlay in `paint()` therefore fixes the magnifier automatically. Confirmed by a render-based pixel test.
- Active handle stays hidden-but-interactive (`MeasurementHandle.paint()` early-return unchanged) (T6).

Tests added in `tests/test_measurement_items.py` (`TestHandleDragHighlightSuppression`):
- `test_paint_decision_tracks_drag_state` — helper is True when selected, False mid-drag for both start and end handles, True after release.
- `test_render_has_no_yellow_overlay_during_drag` — scene render (the magnifier's path) shows yellow pixels when selected, zero during a handle drag.

Tests run: `pytest tests/test_measurement_items.py tests/test_angle_measurement_geometry.py tests/test_roi_export_service_measurements.py -q` → 15 passed. Manual UI/magnifier smoke not performed in this environment (GPU/Parallels); the render-based test exercises the same `scene.render()` path the magnifier uses.

