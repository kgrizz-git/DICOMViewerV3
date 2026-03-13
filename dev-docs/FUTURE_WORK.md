# Future Work Items

This file tracks features that are planned but deferred from the current implementation phases.

## Slice Location Line Across Views

Draw a line on secondary views showing where the current slice plane intersects those views. Reuses Phase 1 geometry (`plane_plane_intersection` + `project_line_to_2d`). UI: enable/disable toggle in View menu; line color/style per view.

## Interactive Oblique Rotation

Allow real-time dragging of MPR planes (rotation handles, crosshairs). Requires: multi-resolution caching during drag, full resolution on release, or optimized resampling. Add to MPR dialog as "Interactive mode" checkbox.

## Measurements on MPR

Enable ROIs, annotations, and measurements on MPR subwindows. Requires: pixel-to-patient coordinate mapping for output plane geometry (not source dataset), ROI storage in patient space, and measurement tools adapted for resampled data.

## Fusion on MPR

Enable fusion overlays on MPR views (e.g. PET/CT on coronal MPR). Requires: fusing volumes in 3D before resampling to plane, or resampling each volume separately and fusing the 2D results. Enable fusion controls for MPR subwindows.