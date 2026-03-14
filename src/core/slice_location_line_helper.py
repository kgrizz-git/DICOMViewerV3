"""
Slice Location Line Helper

Computes 2-D line segments for the "slice location line across views" feature.
For a given target subwindow, returns the intersection lines from other views'
current slice planes, projected onto the target's image and clipped to the
image rectangle.

Inputs:
    - Target subwindow index
    - App reference (subwindow_data, slice_sync_coordinator for geometry)
    - Optional: only_same_group, groups (to scope sources to linked group)

Outputs:
    - List of segment descriptors: { "source_idx", "col1", "row1", "col2", "row2 }

Requirements:
    - core.slice_geometry (plane_plane_intersection, project_line_to_2d, clip_line_to_rect)
    - SliceSyncCoordinator.get_current_plane
"""

from typing import Any, Dict, List, Optional, Tuple

from core.slice_geometry import (
    SlicePlane,
    clip_line_to_rect,
    plane_plane_intersection,
    project_line_to_2d,
)

# Minimum segment length in pixels to avoid flickering dots.
_MIN_SEGMENT_LENGTH_PX = 2.0


def get_slice_location_line_segments(
    target_idx: int,
    app: Any,
    only_same_group: bool = False,
    other_indices: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Compute slice location line segments for a target subwindow.

    For each other subwindow in the same group (or all others if not scoped),
    computes the intersection of that source's current slice plane with the
    target's current slice plane, projects the 3-D line to the target's 2-D
    pixel coordinates, and clips to the image rectangle.

    Args:
        target_idx: Subwindow index (0–3) of the target view.
        app: DICOMViewerApp instance with subwindow_data, subwindow_managers,
             and _slice_sync_coordinator.
        only_same_group: If True, only consider sources in the same linked
                         group as target_idx. Requires app._slice_sync_coordinator
                         and config_manager.get_slice_sync_groups().
        other_indices: If provided, use only these indices as sources; else
                       use all subwindows except target_idx (optionally filtered
                       by group).

    Returns:
        List of dicts: { "source_idx": int, "col1", "row1", "col2", "row2 }
        in target's pixel coordinates. Empty if no valid segments.
    """
    segments: List[Dict[str, Any]] = []

    coordinator = getattr(app, "_slice_sync_coordinator", None)
    if coordinator is None:
        return segments

    target_plane = coordinator.get_current_plane(target_idx)
    if target_plane is None:
        return segments

    # Get target image dimensions (cols, rows).
    width, height = _get_image_size(app, target_idx)
    if width is None or height is None or width <= 0 or height <= 0:
        return segments

    # Determine source indices.
    if other_indices is not None:
        source_indices = [i for i in other_indices if i != target_idx]
    else:
        all_indices = list(app.subwindow_data.keys() if hasattr(app, "subwindow_data") else [])
        if only_same_group and hasattr(app, "config_manager"):
            groups = app.config_manager.get_slice_sync_groups()
            target_group = None
            for g in groups:
                if target_idx in g:
                    target_group = g
                    break
            if target_group is not None:
                source_indices = [i for i in target_group if i != target_idx]
            else:
                source_indices = [i for i in all_indices if i != target_idx]
        else:
            source_indices = [i for i in all_indices if i != target_idx]

    for source_idx in source_indices:
        source_plane = coordinator.get_current_plane(source_idx)
        if source_plane is None:
            continue

        line_3d = plane_plane_intersection(source_plane, target_plane)
        if line_3d is None:
            continue

        point, direction = line_3d
        seg = project_line_to_2d(point, direction, target_plane)
        if seg is None:
            continue

        col1, row1, col2, row2 = seg
        clipped = clip_line_to_rect(col1, row1, col2, row2, width, height)
        if clipped is None:
            continue

        c1, r1, c2, r2 = clipped
        length = ((c2 - c1) ** 2 + (r2 - r1) ** 2) ** 0.5
        if length < _MIN_SEGMENT_LENGTH_PX:
            continue

        segments.append({
            "source_idx": source_idx,
            "col1": c1,
            "row1": r1,
            "col2": c2,
            "row2": r2,
        })

    return segments


def _get_image_size(app: Any, idx: int) -> Tuple[Optional[float], Optional[float]]:
    """
    Return (width, height) in pixels for the image in subwindow idx.

    For DICOM: uses Rows and Columns from current_dataset.
    For MPR: uses shape of first slice in mpr_result.
    """
    data = getattr(app, "subwindow_data", {}).get(idx, {})
    if data.get("is_mpr") and data.get("mpr_result") is not None:
        mpr = data["mpr_result"]
        if mpr.slices:
            arr = mpr.slices[0]
            if arr.ndim >= 2:
                return (float(arr.shape[1]), float(arr.shape[0]))
        return (None, None)

    ds = data.get("current_dataset")
    if ds is None:
        return (None, None)

    try:
        rows = int(ds.Rows)
        cols = int(ds.Columns)
        return (float(cols), float(rows))
    except (AttributeError, TypeError, ValueError):
        return (None, None)
