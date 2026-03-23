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

## Stream A: Export + Loading UX + Default Style

### TO_DO items

- Reduce default ROI/measurement line thickness and font sizes
- Duplicate-skip toast center/opacity
- Large-file warning threshold update
- PNG/JPG anonymization + embedded WL default

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

### TO_DO items

- Navigator tooltips (privacy-aware)
- Multi-frame instance navigation follow-up audit (`current_slice_index` usage)
- Left/right keys for instance switching when show-instances-separately is enabled

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

### TO_DO items

- Scale markers (ruler ticks)
- Direction labels (A/P/L/R/S/I)
- Overlay configuration in right-click context menu

### File ownership

- `src/gui/scale_ruler_widget.py` (new)
- `src/utils/dicom_utils.py`
- `src/gui/overlay_manager.py`
- `src/gui/dialogs/overlay_config_dialog.py`
- `src/gui/dialogs/overlay_settings_dialog.py`

### Notes

- If context-menu wiring requires `src/gui/image_viewer.py`, coordinate with Stream D or sequence work after D.

## Stream D: Viewer Interaction/Transform Core

### TO_DO items

- Window/level discoverability/interaction updates
- Min/max W/L from bit depth
- W/L remembered per series
- Flip/rotate image
- Slice/frame edge slider bars
- Image drift hardening/follow-up

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

### TO_DO items

- Window map thumbnail interactive
- Toolbar customization
- View fullscreen command and shortcut
- Optional slice-position line display option (if implemented through layout/overlay config path)

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
