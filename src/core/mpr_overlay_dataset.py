"""Synthetic overlay dataset for an MPR slice (pure core, no Qt).

The source metadata is preserved for patient/study/series overlay text; the
slice-specific DICOM fields that are meaningless for a resampled stack are
replaced or removed. The source dataset is deep-copied so the edits never
reach the dataset in ``current_studies``.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np


def build_overlay_dataset(result: Any, slice_index: int) -> Any:
    """
    Build a synthetic dataset for MPR overlay text.

    The source metadata is preserved for patient/study/series text, but
    slice-specific DICOM fields that are meaningless for a resampled stack
    are replaced or removed:
    - ``InstanceNumber`` becomes the MPR stack index (1-based).
    - ``ImageOrientationPatient`` matches the **displayed** MPR plane (row/column
      cosines from ``slice_stack.planes[slice_index]``) so direction labels and
      geometry match the reformatted view.
    - ``PixelSpacing`` matches ``result.output_spacing_mm`` for scale markers.
    - ``SliceLocation`` is removed.
    - ``ImagePositionPatient`` is removed.

    Args:
        result:      Current MPR result.
        slice_index: Zero-based MPR stack index.

    Returns:
        Dataset-like object suitable for ``DICOMParser``.
    """
    # pydicom Dataset.copy() is ``copy.copy`` (shallow): mutating tags on the
    # copy still updates the original dataset in ``current_studies``, which
    # corrupts native-series overlays (InstanceNumber / IOP). Deep-copy the
    # first source slice so MPR-only metadata edits stay isolated.
    source_ds = copy.deepcopy(result.source_volume.source_datasets[0])
    source_ds.InstanceNumber = int(slice_index + 1)
    _overlay_apply_thickness(source_ds, result)
    _overlay_apply_orientation(source_ds, result, slice_index)
    _overlay_apply_spacing(source_ds, result)
    _overlay_strip_location_attrs(source_ds)
    return source_ds


def _overlay_apply_thickness(source_ds: Any, result: Any) -> None:
    """Set SliceThickness / SpacingBetweenSlices from MPR output thickness."""
    try:
        source_ds.SliceThickness = float(result.output_thickness_mm)
    except Exception:
        pass
    try:
        source_ds.SpacingBetweenSlices = float(result.output_thickness_mm)
    except Exception:
        pass


def _overlay_apply_orientation(
    source_ds: Any, result: Any, slice_index: int
) -> None:
    """Set ImageOrientationPatient from the displayed MPR plane."""
    planes = getattr(result.slice_stack, "planes", None) or []
    si = int(slice_index)
    if not planes or not (0 <= si < len(planes)):
        return
    plane = planes[si]
    rc = np.asarray(plane.row_cosine, dtype=float).reshape(-1)
    cc = np.asarray(plane.col_cosine, dtype=float).reshape(-1)
    if rc.size != 3 or cc.size != 3:
        return
    try:
        source_ds.ImageOrientationPatient = [
            float(rc[0]),
            float(rc[1]),
            float(rc[2]),
            float(cc[0]),
            float(cc[1]),
            float(cc[2]),
        ]
    except Exception:
        pass


def _overlay_apply_spacing(source_ds: Any, result: Any) -> None:
    """Set PixelSpacing from MPR output spacing."""
    try:
        rs, cs = result.output_spacing_mm[0], result.output_spacing_mm[1]
        source_ds.PixelSpacing = [float(rs), float(cs)]
    except Exception:
        pass


def _overlay_strip_location_attrs(source_ds: Any) -> None:
    """Remove SliceLocation / ImagePositionPatient from the overlay dataset."""
    for attr in ("SliceLocation", "ImagePositionPatient"):
        if hasattr(source_ds, attr):
            try:
                delattr(source_ds, attr)
            except Exception:
                setattr(source_ds, attr, "")
