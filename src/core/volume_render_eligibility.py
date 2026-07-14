"""
3D volume render eligibility helpers (no Qt / no gui imports).

Used by toolbar enablement, context menus, and ``gui.volume_render_facade``.
"""

from __future__ import annotations

from typing import Any

from core.volume_renderer import vtk_available

# Minimum number of slices required for a meaningful 3D volume.
MIN_SLICES_FOR_VOLUME = 3

_TOOLTIP_ENABLED = "Open 3D Volume Render of current series"
_TOOLTIP_VTK_MISSING = "3D volume rendering requires the vtk package (pip install vtk)"


def get_datasets_for_subwindow(app: Any, idx: int) -> list[Any] | None:
    """Return the list of datasets loaded in subwindow *idx*, or None."""
    if idx < 0:
        return None
    data = app.subwindow_data.get(idx, {})
    datasets = data.get("datasets")
    if datasets and isinstance(datasets, list) and len(datasets) > 0:
        return datasets
    # Fallback: try current_studies lookup.
    study_uid = data.get("study_uid") or getattr(app, "current_study_uid", None)
    series_uid = data.get("series_uid") or getattr(app, "current_series_uid", None)
    if study_uid and series_uid:
        studies = getattr(app, "current_studies", {})
        if study_uid in studies and series_uid in studies[study_uid]:
            return studies[study_uid][series_uid]
    return None


def series_has_volume_geometry(datasets: list[Any]) -> bool:
    """Return True when enough slices have IOP + IPP for volume construction."""
    from utils.dicom_utils import get_image_orientation, get_image_position

    valid_count = 0
    for ds in datasets:
        if get_image_orientation(ds) is not None and get_image_position(ds) is not None:
            valid_count += 1
    return valid_count >= MIN_SLICES_FOR_VOLUME


def _is_multiframe_wrapper(ds: Any) -> bool:
    """Return True if *ds* is a FrameDatasetWrapper (multiframe frame)."""
    return hasattr(ds, '_original_dataset') and hasattr(ds, '_frame_index')


def classify_multiframe_for_3d(datasets: list[Any]) -> tuple[bool, str]:
    """Check if multiframe datasets can be used for 3D rendering.

    Returns ``(is_multiframe, warning_message)``.  *warning_message* is empty
    when datasets are not multiframe or when frames are clearly spatial.
    """
    if not datasets or not _is_multiframe_wrapper(datasets[0]):
        return False, ""

    from core.multiframe_handler import FrameType, classify_frame_type

    original = datasets[0]._original_dataset
    frame_type = classify_frame_type(original)

    if frame_type == FrameType.SPATIAL:
        return True, ""

    label = frame_type.value if frame_type != FrameType.UNKNOWN else "unknown"
    warning = (
        f"These frames appear to be {label} rather than spatial slices. "
        "The 3D reconstruction may not be anatomically meaningful."
    )
    return True, warning


def synthesize_frame_geometry(datasets: list[Any]) -> list[Any]:
    """Add synthesised IPP/IOP to frame datasets that lack spatial metadata.

    Uses ``SliceThickness`` or ``SpacingBetweenSlices`` if available, otherwise
    assumes 1.0 mm spacing.  Assumes axial orientation (standard IOP).
    Returns the datasets (modified in place).
    """
    if not datasets:
        return datasets

    from utils.dicom_utils import get_image_orientation, get_image_position

    # Check if datasets already have valid geometry — if so, return unchanged.
    valid = sum(
        1 for ds in datasets
        if get_image_orientation(ds) is not None and get_image_position(ds) is not None
    )
    if valid >= MIN_SLICES_FOR_VOLUME:
        return datasets

    # Determine slice spacing.
    spacing = None
    first = datasets[0]
    for attr in ('SliceThickness', 'SpacingBetweenSlices'):
        val = getattr(first, attr, None)
        if val is not None:
            try:
                spacing = float(val)
            except (TypeError, ValueError):
                pass
            if spacing is not None and spacing > 0:
                break
            spacing = None
    if spacing is None:
        spacing = 1.0

    # Standard axial IOP: row along X, column along Y.
    axial_iop = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]

    for i, ds in enumerate(datasets):
        if get_image_orientation(ds) is None:
            ds.ImageOrientationPatient = axial_iop
        if get_image_position(ds) is None:
            ds.ImagePositionPatient = [0.0, 0.0, float(i) * spacing]

    return datasets


def can_launch_3d_volume_render(
    app: Any,
    subwindow_idx: int | None = None,
) -> tuple[bool, str]:
    """
    Return whether 3D volume render can launch for *subwindow_idx* (or focused).

    The second tuple element is a short disabled-reason string suitable for
    tooltips when the action is disabled.
    """
    if not vtk_available:
        return False, _TOOLTIP_VTK_MISSING

    idx = (
        int(subwindow_idx)
        if subwindow_idx is not None
        else int(app.get_focused_subwindow_index())
    )
    if idx < 0:
        return False, "No image window is focused"

    datasets = get_datasets_for_subwindow(app, idx)
    if datasets is None or len(datasets) < MIN_SLICES_FOR_VOLUME:
        count = len(datasets) if datasets else 0
        return (
            False,
            f"Requires at least {MIN_SLICES_FOR_VOLUME} slices "
            f"(current series has {count})",
        )

    if series_has_volume_geometry(datasets):
        return True, _TOOLTIP_ENABLED

    # For multiframe frame wrappers, allow 3D even without native geometry —
    # synthesize_frame_geometry will fill in IPP/IOP before the build step.
    is_mf, warning = classify_multiframe_for_3d(datasets)
    if is_mf:
        tooltip = _TOOLTIP_ENABLED
        if warning:
            tooltip += f" (warning: {warning})"
        return True, tooltip

    return (
        False,
        "Series lacks spatial metadata (ImagePositionPatient / "
        "ImageOrientationPatient)",
    )
