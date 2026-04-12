"""
Slice Location Line Helper

Computes 2-D line segments for the "slice location line across views" feature.
For a given target subwindow, returns the intersection lines from other views'
current slice planes, projected onto the target's image and clipped to the
image rectangle.

Two rendering modes are supported:
    "middle"    – (default) one line per source at the centre of the source
                  slice/slab plane.
    "begin_end" – two lines per source at the slab boundaries, offset by
                  ±(SliceThickness / 2) along the source plane's normal.
                  Falls back to "middle" for a given source when thickness
                  is unavailable.

Inputs:
    - Target subwindow index
    - App reference (subwindow_data, slice_sync_coordinator for geometry)
    - Optional: only_same_group, mode

Outputs:
    - List of segment descriptors:
        {
            "source_idx": int,   # used for colour
            "line_id":    str,   # unique key per line item
            "col1", "row1", "col2", "row2": float
        }

Requirements:
    - core.slice_geometry (SlicePlane, plane_plane_intersection,
                           project_line_to_2d, clip_line_to_rect)
    - SliceSyncCoordinator.get_current_plane / get_slice_thickness
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


def _make_offset_plane(plane: SlicePlane, offset_mm: float) -> SlicePlane:
    """
    Return a copy of *plane* with its origin shifted by *offset_mm* along the
    plane's unit normal vector.

    This creates a parallel plane representing one face of a slab.

    Args:
        plane:     Source SlicePlane (centre of slab).
        offset_mm: Signed shift in mm along plane.normal.

    Returns:
        New SlicePlane with shifted origin; same orientation and spacing.
    """
    shifted_origin = plane.origin + offset_mm * plane.normal
    return SlicePlane(
        origin=shifted_origin,
        row_cosine=plane.row_cosine,
        col_cosine=plane.col_cosine,
        row_spacing=plane.row_spacing,
        col_spacing=plane.col_spacing,
    )


def _compute_segment(
    source_plane: SlicePlane,
    target_plane: SlicePlane,
    width: float,
    height: float,
) -> Optional[Tuple[float, float, float, float]]:
    """
    Compute the clipped 2-D segment where *source_plane* intersects the
    *target_plane* image.

    Returns:
        (col1, row1, col2, row2) in target pixel coordinates, or None.
    """
    line_3d = plane_plane_intersection(source_plane, target_plane)
    if line_3d is None:
        return None

    point, direction = line_3d
    seg = project_line_to_2d(point, direction, target_plane)
    if seg is None:
        return None

    col1, row1, col2, row2 = seg
    clipped = clip_line_to_rect(col1, row1, col2, row2, width, height)
    if clipped is None:
        return None

    c1, r1, c2, r2 = clipped
    length = ((c2 - c1) ** 2 + (r2 - r1) ** 2) ** 0.5
    if length < _MIN_SEGMENT_LENGTH_PX:
        return None

    return (c1, r1, c2, r2)


def get_slice_location_line_segments(
    target_idx: int,
    app: Any,
    only_same_group: bool = False,
    other_indices: Optional[List[int]] = None,
    mode: str = "middle",
) -> List[Dict[str, Any]]:
    """
    Compute slice location line segments for a target subwindow.

    For each other subwindow (scoped by group if requested), computes the
    intersection of that source's current slice plane with the target's
    image and clips to the image rectangle.

    In "middle" mode (default): one segment per source at the centre plane.
    In "begin_end" mode: two segments per source at ±(SliceThickness/2) from
    the centre.  Falls back to a single centre segment when thickness is not
    available for that source.

    Args:
        target_idx:     Subwindow index (0–3) of the target view.
        app:            DICOMViewerApp instance.
        only_same_group: If True, only consider sources in the same linked
                         group as target_idx.
        other_indices:  If provided, use exactly these indices as sources.
        mode:           "middle" (default) or "begin_end".

    Returns:
        List of dicts with keys:
            source_idx – subwindow source index (used for colour).
            line_id    – unique key for this line item within the manager.
                         middle mode:    "middle:<source_idx>"
                         begin_end mode: "begin:<source_idx>" / "end:<source_idx>"
            col1, row1, col2, row2 – endpoint pixel coordinates in the target.
        Empty if no valid segments.
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
    all_indices = list(app.subwindow_data.keys() if hasattr(app, "subwindow_data") else [])
    if other_indices is not None:
        source_indices = [i for i in other_indices if i != target_idx]
    else:
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

    target_for_uid = _get_frame_of_reference_uid(app, target_idx)

    for source_idx in source_indices:
        source_for_uid = _get_frame_of_reference_uid(app, source_idx)
        if (
            target_for_uid is not None
            and source_for_uid is not None
            and target_for_uid != source_for_uid
        ):
            continue  # Different Frame of Reference: coordinates not comparable; skip

        source_plane = coordinator.get_current_plane(source_idx)
        if source_plane is None:
            continue

        source_thickness = _get_source_plane_thickness_mm(app, coordinator, source_idx)

        if mode == "begin_end":
            _append_begin_end_segments(
                segments,
                source_idx,
                source_plane,
                target_plane,
                width,
                height,
                source_thickness,
            )
        else:
            # Default: middle mode — single centre line.
            clipped = _compute_segment(source_plane, target_plane, width, height)
            if clipped is not None:
                c1, r1, c2, r2 = clipped
                segments.append({
                    "source_idx": source_idx,
                    "line_id": f"middle:{source_idx}",
                    "col1": c1,
                    "row1": r1,
                    "col2": c2,
                    "row2": r2,
                })

    return segments


def _append_begin_end_segments(
    segments: List[Dict[str, Any]],
    source_idx: int,
    source_plane: SlicePlane,
    target_plane: SlicePlane,
    width: float,
    height: float,
    thickness: Optional[float],
) -> None:
    """
    Append begin and end boundary segments for *source_idx* in begin_end mode.

    Uses the effective source thickness passed in by the caller. This is the
    slab thickness when Combine Slices / MPR slab combine is active, otherwise
    the nominal single-slice thickness. Falls back to a single centre-line
    segment when thickness is unavailable.

    The two line_id values used are:
        "begin:<source_idx>" → negative offset ("top" boundary)
        "end:<source_idx>"   → positive offset ("bottom" boundary)

    Args:
        segments:     Output list to append to.
        source_idx:   Source subwindow index (0–3).
        source_plane: SlicePlane for the source's current slice.
        target_plane: SlicePlane for the target's current slice.
        width:        Target image width in pixels.
        height:       Target image height in pixels.
        thickness:    Effective source slice/slab thickness in mm.
    """
    if thickness is None or thickness <= 0:
        # Fallback: single centre line (same as middle mode).
        clipped = _compute_segment(source_plane, target_plane, width, height)
        if clipped is not None:
            c1, r1, c2, r2 = clipped
            segments.append({
                "source_idx": source_idx,
                "line_id": f"middle:{source_idx}",
                "col1": c1,
                "row1": r1,
                "col2": c2,
                "row2": r2,
            })
        return

    half = thickness / 2.0

    # Begin boundary: shift origin by -half along normal.
    begin_plane = _make_offset_plane(source_plane, -half)
    clipped_begin = _compute_segment(begin_plane, target_plane, width, height)
    if clipped_begin is not None:
        c1, r1, c2, r2 = clipped_begin
        segments.append({
            "source_idx": source_idx,
            "line_id": f"begin:{source_idx}",
            "col1": c1,
            "row1": r1,
            "col2": c2,
            "row2": r2,
        })

    # End boundary: shift origin by +half along normal.
    end_plane = _make_offset_plane(source_plane, half)
    clipped_end = _compute_segment(end_plane, target_plane, width, height)
    if clipped_end is not None:
        c1, r1, c2, r2 = clipped_end
        segments.append({
            "source_idx": source_idx,
            "line_id": f"end:{source_idx}",
            "col1": c1,
            "row1": r1,
            "col2": c2,
            "row2": r2,
        })


def _get_source_plane_thickness_mm(
    app: Any,
    coordinator: Any,
    source_idx: int,
) -> Optional[float]:
    """
    Return the effective source thickness for slice location line rendering.

    For ordinary 2-D series this is the nominal slice thickness from the slice
    sync geometry cache. When Combine Slices is active, the effective slab
    thickness is ``slice_thickness * slice_count`` so begin/end mode reflects
    the displayed slab, not just the centre slice. The same rule applies to MPR
    runtime slab combine using ``mpr_combine_slice_count``.
    """
    get_slice_thickness = getattr(coordinator, "get_slice_thickness", None)
    if callable(get_slice_thickness):
        base_thickness = get_slice_thickness(source_idx)
    else:
        base_thickness = None
    if base_thickness is None or base_thickness <= 0:
        return base_thickness

    data = getattr(app, "subwindow_data", {}).get(source_idx, {})
    managers = getattr(app, "subwindow_managers", {}).get(source_idx, {})
    slice_display_manager = managers.get("slice_display_manager")

    if bool(data.get("is_mpr")):
        if bool(data.get("mpr_combine_enabled", False)):
            combine_count = max(1, int(data.get("mpr_combine_slice_count", 1) or 1))
            return base_thickness * combine_count
        return base_thickness

    if (
        slice_display_manager is not None
        and bool(getattr(slice_display_manager, "projection_enabled", False))
    ):
        projection_count = max(
            1,
            int(getattr(slice_display_manager, "projection_slice_count", 1) or 1),
        )
        return base_thickness * projection_count

    return base_thickness


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


def _get_frame_of_reference_uid(app: Any, idx: int) -> Optional[str]:
    """Return FrameOfReferenceUID for a subwindow's current series, or None."""
    data = getattr(app, "subwindow_data", {}).get(idx, {})
    if data.get("is_mpr") and data.get("mpr_result") is not None:
        mpr = data["mpr_result"]
        if hasattr(mpr, "source_volume") and mpr.source_volume is not None:
            src = getattr(mpr.source_volume, "source_datasets", None)
            if src and len(src) > 0:
                return getattr(src[0], "FrameOfReferenceUID", None)
        return None
    ds = data.get("current_dataset")
    if ds is None:
        return None
    return getattr(ds, "FrameOfReferenceUID", None)
