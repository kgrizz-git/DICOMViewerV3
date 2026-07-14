# Parallel Workstream Ownership Plan

Last updated: 2026-03-23
Owner: DICOM Viewer V3
Status: Draft execution guide for parallel implementation

## Goal

Define conflict-minimized workstreams by assigning each stream an explicit file ownership boundary.

## How to use this plan

1. Pick one stream per engineer.
2. Treat the listed files as owned by that stream for the duration of the sprint.
3. If a task needs a file owned by another stream, either:
   - move the task to that stream, or
   - split the task into a preparatory part and a follow-up part.

## Conflict hot spots (avoid concurrent edits)

- `src/gui/image_viewer.py`
- `src/core/view_state_manager.py`
- `src/main.py`
- `src/gui/main_window.py`
- `src/gui/main_window_menu_builder.py`
- `src/gui/series_navigator.py`

## Active assignments (placeholders)

Use these as temporary placeholders until owners and branches are assigned.

| Stream | Placeholder owner | Placeholder branch | Status |
|---|---|---|---|
| A | `TBD` | `tbd/stream-a` | `not started` |
| B | `TBD` | `tbd/stream-b` | `not started` |
| C | `TBD` | `tbd/stream-c` | `not started` |
| D | `TBD` | `tbd/stream-d` | `not started` |
| E | `TBD` | `tbd/stream-e` | `not started` |

## Stream A: Export + Loading UX + Default Style

### Placeholder assignment

- Owner: `TBD`
- Branch: `tbd/stream-a`
- Status: `not started`

### TO_DO items

- [Reduce default ROI/measurement line thickness and font sizes](../TO_DO.md#L51)
- [Duplicate-skip toast center/opacity](../TO_DO.md#L62)
- [Large-file warning threshold update](../TO_DO.md#L63)
- [PNG/JPG anonymization + embedded WL default](../TO_DO.md#L68)

### File ownership

- `src/utils/config/roi_config.py`
- `src/utils/config/measurement_config.py`
- `src/core/file_operations_handler.py`
- `src/core/file_series_loading_coordinator.py`
- `src/gui/main_window.py`
- Export-flow files touched by export privacy/WL default implementation

### Notes

- `src/gui/main_window.py` is shared risk with other streams; schedule main-window changes in a short merge window.

## Stream B: Navigator + Multi-frame Navigation

### Placeholder assignment

- Owner: `TBD`
- Branch: `tbd/stream-b`
- Status: `not started`

### TO_DO items

- [Navigator tooltips (privacy-aware)](../TO_DO.md#L61)
- [Multi-frame instance navigation follow-up audit (`current_slice_index` usage)](../TO_DO.md#L52)
- [Left/right keys for instance switching when show-instances-separately is enabled](../TO_DO.md#L67)

### File ownership

- `src/gui/series_navigator.py`
- `src/core/dicom_organizer.py`
- `src/core/multiframe_handler.py`
- `src/gui/overlay_manager.py`
- `src/utils/config/display_config.py`
- Related navigation routing files for focused-subwindow key handling

### Notes

- Do not run this stream in parallel with another stream editing `src/gui/series_navigator.py`.

## Stream C: Viewer UX Additive Overlays (non-transform)

### Placeholder assignment

- Owner: `TBD`
- Branch: `tbd/stream-c`
- Status: `not started`

### TO_DO items

- [Scale markers (ruler ticks)](../TO_DO.md#L57)
- [Direction labels (A/P/L/R/S/I)](../TO_DO.md#L58)
- [Overlay configuration in right-click context menu](../TO_DO.md#L50)

### File ownership

- `src/gui/scale_ruler_widget.py` (new)
- `src/utils/dicom_utils.py`
- `src/gui/overlay_manager.py`
- `src/gui/dialogs/overlay_config_dialog.py`
- `src/gui/dialogs/overlay_settings_dialog.py`

### Notes

- If context-menu wiring requires `src/gui/image_viewer.py`, coordinate with Stream D or sequence work after D.

## Stream D: Viewer Interaction/Transform Core

### Placeholder assignment

- Owner: `TBD`
- Branch: `tbd/stream-d`
- Status: `not started`

### TO_DO items

- [Window/level discoverability/interaction updates](../TO_DO.md#L48)
- [Min/max W/L from bit depth](../TO_DO.md#L49)
- [W/L remembered per series](../TO_DO.md#L56)
- [Flip/rotate image](../TO_DO.md#L59)
- [Slice/frame edge slider bars](../TO_DO.md#L60)
- [Image drift hardening/follow-up](../TO_DO.md#L31)

### File ownership

- `src/gui/image_viewer.py`
- `src/core/view_state_manager.py`
- `src/core/slice_display_manager.py`
- `src/core/dicom_pixel_stats.py`
- `src/core/dicom_window_level.py`
- `src/gui/window_level_controls.py`
- `src/gui/edge_reveal_slider_overlay.py` (new)

### Notes

- This stream owns the highest-conflict files; no parallel edits from other streams.

## Stream E: Layout/Window-Map/Fullscreen/Toolbar

### Placeholder assignment

- Owner: `TBD`
- Branch: `tbd/stream-e`
- Status: `not started`

### TO_DO items

- [Window map thumbnail interactive](../TO_DO.md#L46)
- [Toolbar customization](../TO_DO.md#L47)
- [View fullscreen command and shortcut](../TO_DO.md#L65)
- [Slice-position line display option](../TO_DO.md#L66)

### File ownership

- `src/gui/window_slot_map_widget.py`
- `src/gui/main_window.py`
- `src/gui/main_window_menu_builder.py`
- `src/main.py`
- `src/utils/config_manager.py`
- `src/utils/config/` mixins for layout/toolbar/fullscreen state

### Notes

- Because this stream touches app wiring (`src/main.py`), avoid running with another stream that modifies app-level signal plumbing.

## Recommended staffing pattern

For three parallel engineers:

1. Engineer 1: Stream A
2. Engineer 2: Stream B
3. Engineer 3: Stream D

Queue Streams C and E behind D and B respectively to reduce merge churn in shared viewer and menu files.

## PR and merge guardrails

1. One stream per branch.
2. PR title prefix with stream id: `[Stream-A]`, `[Stream-B]`, etc.
3. Any PR touching another stream's owned file must be marked `cross-stream`.
4. Rebase and rerun smoke tests before merge.
5. Merge order for lowest risk:
   1. Stream A
   2. Stream B
   3. Stream D
   4. Stream C
   5. Stream E
