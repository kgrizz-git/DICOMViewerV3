# Slice Location Line Across Views – Implementation Plan

**Status:** **Shipped and archived** (2026-04). Implementation lives in `src/core/slice_location_line_helper.py`, `src/gui/slice_location_line_manager.py`, `src/core/slice_location_line_coordinator.py`, config on `SliceSyncConfigMixin`, **View → Show Slice Location Lines** and the image **Show Slice Location Lines** submenu, plus **Overlay Settings** (line mode middle/begin–end and line width). See `CHANGELOG.md` for MPR/combine-slice integration and follow-up fixes. *Original plan items not built:* duplicate entry under **Slice & Sync** submenu only (lines live under **View**); per-subwindow-only visibility override; optional checkbox inside **Manage sync groups**; optional viewport legend.

This document describes the implementation plan for the **Slice Location Line Across Views** feature from `dev-docs/TO_DO.md`. It shows, in each view, the line where another view’s current slice plane intersects the current image plane, so users can see anatomic correspondence across linked windows.

The plan reuses the existing Phase 1 geometry from `dev-docs/plans/completed/SLICE_SYNC_AND_MPR_PLAN.md` (`plane_plane_intersection`, `project_line_to_2d`, `SlicePlane`, `SliceStack`) and aligns with slice sync linked groups where applicable.

---

## Overview

| Phase | Scope | Delivers |
|-------|--------|----------|
| **Phase 1** | Geometry and line computation | Reuse `slice_geometry`; optional helper for clipping and batch “lines for all other views” |
| **Phase 2** | Drawing and per-subwindow state | Scene line items, update on slice/layout change, clipping to image rect |
| **Phase 3** | UI and config | Master toggle, optional per-view toggle, colors/legend, View menu and config |
| **Phase 4** | Edge cases and polish | Parallel-plane handling, numerical stability, optional legend/tooltip |

**Recommended order**: Phase 1 → Phase 2 → Phase 3 → Phase 4. Phase 1 is mostly validation and thin helpers; Phases 2–3 deliver the visible feature.

**Dependencies**: Phase 1 geometry in `src/core/slice_geometry.py` is already implemented (`plane_plane_intersection`, `project_line_to_2d`). Slice sync (`SliceSyncCoordinator`, `slice_sync_config`) and `subwindow_data` / `subwindow_managers` are in place.

---

## Resolved Decisions

| Topic | Decision |
|-------|----------|
| **Scope of “other views”** | When the feature is on, show slice lines from **all other subwindows that have valid geometry** (optionally scoped to the same linked group when slice sync is used; see Phase 3). |
| **Drawing** | Use **scene-based** `QGraphicsLineItem`(s) in each subwindow’s scene so lines zoom/pan with the image. Do not use `ItemIgnoresTransformations`. |
| **Coordinates** | `project_line_to_2d` returns `(col1, row1, col2, row2)` in pixel coordinates. Clip segment to image rect `[0, cols] x [0, rows]` before creating the line item. Image item is at scene origin, so pixel coords = scene coords. |
| **Toggle** | Master toggle “Show slice location lines” (default off). Optional: per-subwindow “Show lines in this view” to reduce clutter when many windows are open. |
| **Styling** | Distinct color (or style) per source subwindow (e.g. Window 1 → cyan, Window 2 → magenta). Optional short legend or tooltip: “Cyan = Window 1 slice”. |
| **Sync coupling** | Feature can be used with or without slice sync. When sync is enabled, “other views” can be restricted to the same linked group to avoid clutter. |

---

## Current State and Overlap

- **`slice_geometry.py`**: `plane_plane_intersection(a, b)` returns `(point_on_line, direction)` or `None`. `project_line_to_2d(point, direction, plane)` returns `(col1, row1, col2, row2)` or `None`. Caller must clip to image extent.
- **`SliceSyncCoordinator`**: Has `_get_stack(idx)`, `_get_current_plane(idx)`-style logic (current slice’s `SlicePlane`). Slice location line logic can use the same app refs (`subwindow_data`, `subwindow_managers`) and same geometry cache or a dedicated cache.
- **Per-subwindow scene**: Each subwindow has its own `ImageViewer` and scene; overlay/crosshair/ROI items are per-scene. Slice line items will be per-subwindow scene, owned by a small manager or the overlay/slice-line component.
- **Overlay / crosshair**: Crosshairs use `QGraphicsLineItem` with `ItemIgnoresTransformations` for viewport-fixed size. Slice location lines should **not** ignore transformations so they stay fixed to anatomy when zooming/panning.

---

## Phase 1: Geometry and Line Computation

### Goal

Confirm existing geometry is sufficient and add a small, testable helper that, for a given “target” subwindow, returns zero or more 2D line segments (one per “source” subwindow) ready for drawing, with clipping applied.

### Prerequisites

- [x] `slice_geometry.plane_plane_intersection`, `project_line_to_2d` available and tested.
- [x] Read `SliceSyncCoordinator._get_stack` / `_get_current_plane` (or equivalent) to obtain current `SlicePlane` per subwindow without duplicating cache logic.

### Tasks

#### 1.1 Clip segment to image rectangle

**File**: `src/core/slice_geometry.py` (or a small helper in the same module / `slice_location_line_utils.py`).

- [x] Implement `clip_line_to_rect(col1, row1, col2, row2, width, height) -> Optional[Tuple[float, float, float, float]]`:
  - Input: segment `(col1, row1)`–`(col2, row2)` and image size `width` (columns), `height` (rows).
  - Use Cohen–Sutherland or parametric clipping to the rect `[0, width] x [0, height]`.
  - Return `(c1, r1, c2, r2)` if the segment intersects the rect, else `None`.
- [x] Add unit tests: segment fully inside, crossing one edge, crossing two edges, fully outside, degenerate (zero length).

#### 1.2 Batch “lines from other views” for one target

**File**: `src/core/slice_location_line_helper.py` (new) or extend `slice_sync_coordinator` with a read-only helper.

- [x] Define a function or small class that, given:
  - `target_subwindow_idx: int`
  - `subwindow_data: Dict`, `subwindow_managers` (or app reference),
  - Optional: `only_same_group: bool` and `groups: List[List[int]]`,
  - Optional: geometry cache `(study_uid, series_uid) -> SliceStack`,
  returns a list of **line descriptors** for the target view:
  - Each descriptor: `{ "source_idx": int, "col1", "row1", "col2", "row2" }` in target’s pixel coordinates.
  - For each other subwindow `s` that has valid `SlicePlane` for current slice and valid target `SlicePlane`:
    - Get source current plane `P_s`, target current plane `P_t`.
    - `line_3d = plane_plane_intersection(P_s, P_t)`; if `None`, skip (parallel/coincident).
    - `seg = project_line_to_2d(point, direction, P_t)`; if `None`, skip.
    - Clip `seg` to target image size; if no intersection, skip.
    - Append `{ "source_idx": s, "col1", "row1", "col2", "row2" }`.
  - Use existing stack/plane access (e.g. from `SliceSyncCoordinator` or a shared geometry cache) so we don’t duplicate cache logic.
- [x] Document behavior when target or source is MPR: use MPR stack’s plane when available (same as slice sync).
- [x] Unit tests (mock subwindow_data and stacks): two orthogonal planes give one line; parallel planes give no line; missing geometry gives no line.

### Potential problems

| Area | Risk | Recommendation |
|------|------|----------------|
| **Numerical stability** | Near-parallel planes or tiny segments after clipping | Rely on existing `plane_plane_intersection` (magnitude check) and `project_line_to_2d` (normal-dot check). If clipped segment length is very small (e.g. &lt; 1 pixel), optionally omit drawing. |
| **Cache reuse** | Duplicating `SliceStack` build per subwindow | Reuse `SliceSyncCoordinator._stack_cache` or a shared cache used by both sync and slice-line feature; avoid building stacks twice. |

---

## Phase 2: Drawing and Per-Subwindow State

### Goal

For each subwindow, maintain a set of `QGraphicsLineItem`(s) representing slice location lines from other views. Update them when slice indices change, when layout/subwindow content changes, or when the master toggle (or per-view toggle) changes.

### Prerequisites

- [x] Phase 1 helper available: given target index and app state, get list of `{ source_idx, col1, row1, col2, row2 }`.
- [x] Clear ownership: which component owns the line items (e.g. a new `SliceLocationLineManager` per subwindow, or one coordinator that holds per-subwindow lists of items).

### Tasks

#### 2.1 SliceLocationLineManager (per subwindow)

**File**: `src/gui/slice_location_line_manager.py` (new) or under `src/core/` if preferred.

- [x] Class `SliceLocationLineManager`:
  - Holds reference to one subwindow’s **scene** and **image size** (cols, rows) for clipping.
  - Holds a list (or dict keyed by source_idx) of `QGraphicsLineItem` objects.
  - Method `update_lines(segments: List[Dict])`: segments are `{ "source_idx", "col1", "row1", "col2", "row2" }`.
    - Remove or clear existing line items that are no longer needed.
    - For each segment, create or reuse a `QGraphicsLineItem(col1, row1, col2, row2)` in **scene coordinates** (pixel coords = scene coords when image at origin).
    - Set pen: color by source_idx (from a small palette), line width 1–2 px, cosmetic or not; do **not** set `ItemIgnoresTransformations` so the line zooms with the image.
    - Set Z-value so lines sit above the image but below overlays/crosshairs (e.g. z = 100).
    - Add items to the scene.
  - Method `clear()`: remove all line items from the scene and clear the list.
  - Optional: `set_visible(visible: bool)` to show/hide the group without recomputing.
- [x] Ensure line items do not accept hover/click (set `ItemIsSelectable`/`ItemIsFocusable` to false) so they don’t steal mouse events from the image.

#### 2.2 Coordinator or app-level update trigger

**File**: `src/core/slice_location_line_coordinator.py` (new) or integrate into `SliceSyncCoordinator` as an optional second responsibility.

- [x] A **SliceLocationLineCoordinator** (or equivalent) that:
  - Holds references to app, and to per-subwindow `SliceLocationLineManager` instances (created when subwindows are created; cleared when a subwindow is destroyed or reset).
  - Knows master toggle “show slice location lines” (from config or caller).
  - Optional: per-subwindow “show lines in this view” (default True when master is on).
  - Method `refresh_all()`: for each subwindow that has an image and slice line visibility on, call Phase 1 helper to get segments for that target; call that subwindow’s `SliceLocationLineManager.update_lines(segments)`.
  - Method `refresh_for_subwindow(target_idx: int)`: refresh only one target (e.g. after slice change in that subwindow).
- [x] When to call refresh:
  - After any subwindow’s **slice index** changes (same signal that drives slice sync or display update).
  - When **master toggle** or **per-view toggle** changes.
  - When **layout** or **subwindow content** changes (e.g. series loaded/closed, subwindow closed) so that “other views” or geometry changes.
- [x] Ensure refresh is not called in a reentrant way (e.g. guard with a flag if refresh triggers slice change; normally it should not).

#### 2.3 Wiring into app and lifecycle

- [x] **Creation**: When subwindow managers are created in `subwindow_lifecycle_controller` (or equivalent), create a `SliceLocationLineManager` for that subwindow and register it with the coordinator. Store in `subwindow_managers[idx]['slice_location_line_manager']` or in a dedicated dict on the coordinator.
- [x] **Slice change**: From the same place that calls `SliceSyncCoordinator.on_slice_changed(source_idx)`, after that (or regardless of sync), call coordinator’s refresh: e.g. `refresh_all()` or `refresh_for_subwindow(source_idx)` plus refresh for all other subwindows that might show a line from `source_idx`. Simplest: `refresh_all()` on every slice change (bounded by number of subwindows).
- [x] **Display update**: When a subwindow’s image is set or its slice display is updated, ensure that subwindow’s slice line manager gets refreshed so lines use the correct current plane and image size.
- [x] **Cleanup**: When a subwindow is closed or its content is cleared, call `SliceLocationLineManager.clear()` and remove the manager from the coordinator.

### Potential problems

| Area | Risk | Recommendation |
|------|------|----------------|
| **Performance** | Refreshing all views on every slice change | Only recompute segments for subwindows that are visible and have the feature on; consider debouncing rapid scroll. |
| **Z-order** | Lines behind overlays or crosshairs | Set Z-value below overlay/crosshair items (e.g. overlay at 150+, crosshair 160+, slice lines 100). |
| **Image size** | Image size for clipping comes from displayed pixmap or DICOM | Use the same dimensions as the image item (e.g. `image_item.boundingRect().width/height` or current dataset rows/columns). |

---

## Phase 3: UI and Config

### Goal

Expose a master toggle and optional per-view toggle, and persist the setting(s). Optionally scope “other views” to the same linked group when slice sync is enabled.

### Prerequisites

- [x] Phase 2 in place: coordinator and managers update line items when toggles or data change.

### Tasks

#### 3.1 Config

**File**: `src/utils/config/slice_sync_config.py` (extend) or `display_config.py`.

- [x] Add config key `slice_location_lines_visible: bool` (default `False`).
- [x] Add getter/setter: `get_slice_location_lines_visible()`, `set_slice_location_lines_visible(bool)`.
  - When this is toggled, coordinator applies visibility and calls `refresh_all()` if turning on.
- [x] Optional: `slice_location_lines_same_group_only: bool` (default `True` when slice sync is enabled, else N/A or `False`). When True, only subwindows in the same linked group as the target show their slice line on the target.

#### 3.2 View menu and context menu

- [x] Add menu item under **View**: “Show slice location lines” (checkable). Tied to `slice_location_lines_visible`. When toggled, update config and call coordinator `refresh_all()`.
- [ ] Optional: In the **Slice Sync** submenu, add “Show slice location lines” as a sibling or sub-item so it’s discoverable with sync. *(Not implemented: feature is under **View → Show Slice Location Lines** next to **Slice & Sync**.)*
- [ ] Optional: In the **image viewer context menu** (right-click on image), add “Show slice location lines” for the current view only (per-view override: show lines in this view on/off). If implemented, store per-view override in subwindow data or a small dict keyed by subwindow index. *(Not implemented: context menu exposes the same global toggles as the View menu.)*

#### 3.3 Slice Sync dialog (optional)

- [ ] In **Manage sync groups** dialog, optional checkbox “Show slice location lines for this group” or rely on the single global toggle. *(Not implemented; global + same-group-only suffice.)*

### Potential problems

| Area | Risk | Recommendation |
|------|------|----------------|
| **Discoverability** | Users don’t find the feature | Place under View and optionally under Slice Sync submenu; mention in docs/TO_DO follow-up. |

---

## Phase 4: Edge Cases and Polish

### Goal

Handle parallel/coincident planes, numerical jitter, and optional legend/tooltip so the feature is robust and understandable.

### Tasks

#### 4.1 Parallel or coincident planes

- [x] Already handled by `plane_plane_intersection` returning `None`. No extra UI message when a line is not drawn for one pair; only draw when we have a valid segment.

#### 4.2 Numerical stability and jitter

- [x] If a segment’s length (in pixel space) is below a small threshold (e.g. 2 pixels), optionally skip drawing that segment to avoid flickering dots.
- [x] Use the same geometry cache as slice sync so stack/plane construction is consistent and not recomputed on every scroll; avoid floating-point variance between sync and line drawing.

#### 4.3 Colors and legend

- [x] Define a small palette of distinct colors (e.g. cyan, magenta, green, orange) for source subwindow indices 0, 1, 2, 3. Map `source_idx` to color consistently.
- [ ] Optional: Draw a small legend on the viewport (e.g. “W1”, “W2”) with the same colors, or show tooltip on hover over the line (“Slice plane from Window 2”). If implemented, use viewport overlay or non-interactive QGraphicsTextItem at a fixed corner with `ItemIgnoresTransformations` so legend doesn’t zoom. *(Not implemented.)*

#### 4.4 MPR and non-DICOM views

- [x] MPR subwindows have a `SliceStack` (from `MprBuilder`); use it for both “current plane” and as a valid “source” or “target” for intersection. Same as slice sync: MPR participates in slice location lines.
- [x] Subwindows with no geometry (e.g. no `ImagePositionPatient`/`ImageOrientationPatient`) do not contribute a line and do not receive lines from others; already handled by returning no segment from the helper.

### Potential problems

| Area | Risk | Recommendation |
|------|------|----------------|
| **Clutter** | Many windows → many lines | Per-view toggle “Show lines in this view” and/or “same group only” reduce lines. |
| **Color blindness** | Palette not distinguishable | Use distinct colors and optional line style (e.g. dashed for one source); document in user docs. |

---

## File and Module Sketch

```
src/
  core/
    slice_geometry.py              # Existing: add clip_line_to_rect (or 1.1 in new helper file)
    slice_location_line_helper.py  # New (Phase 1.2): compute segments for target from other views
  gui/
    slice_location_line_manager.py # New (Phase 2.1): per-subwindow QGraphicsLineItem list, update_lines/clear
  core/
    slice_location_line_coordinator.py # New (Phase 2.2): app-level refresh, toggle, lifecycle
  utils/
    config/
      slice_sync_config.py         # Extend (Phase 3.1): slice_location_lines_visible, optional same_group_only

tests/
  test_slice_geometry.py           # Add tests for clip_line_to_rect (Phase 1.1)
  test_slice_location_line_helper.py # New: test segment computation (Phase 1.2)
```

---

## Integration Points (Summary)

| Trigger | Action |
|--------|--------|
| Subwindow slice index changes | Call coordinator `refresh_all()` (or refresh that subwindow + others that show its line). |
| Master toggle “Show slice location lines” | Update config; coordinator applies visibility and `refresh_all()`. |
| Subwindow closed / content cleared | Coordinator clears that subwindow’s manager and removes from list. |
| New subwindow / series loaded | Create manager for that subwindow; on next refresh, lines appear if toggle is on. |
| Slice sync group change | If “same group only” is used, refresh_all() so line set respects new groups. |

---

## Changelog and Versioning

- **Feature**: New optional visualization (off by default). **Minor version bump** recommended (e.g. 3.x.0).
- **Changelog**: “Added optional slice location lines: show the intersection of other views’ slice planes on the current image. Toggle in View menu; works with or without slice sync.”

---

## References

- `dev-docs/TO_DO.md` — “Slice Location Line Across Views” (suggestions, concerns, notes).
- `dev-docs/plans/completed/SLICE_SYNC_AND_MPR_PLAN.md` — Phase 1 geometry, Phase 2 sync, resolved decisions, file sketch.
- `src/core/slice_geometry.py` — `plane_plane_intersection`, `project_line_to_2d`, `SlicePlane`, `SliceStack`.
- `src/core/slice_sync_coordinator.py` — `_get_stack`, geometry cache, `on_slice_changed`.
- `src/gui/overlay_manager.py` — ViewportOverlayWidget, scene vs viewport; crosshair/measurement use `QGraphicsLineItem`.
- `src/utils/config/slice_sync_config.py` — slice_sync_enabled, slice_sync_groups.
