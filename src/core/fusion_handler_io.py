"""
Pure DICOM spatial reads and NumPy helpers for PET/CT (and related) fusion.

Holds logic extracted from ``FusionHandler`` so the handler can focus on
caching, resampling policy, and orchestration. This module has **no Qt**
dependencies.

Inputs:
    - ``pydicom.Dataset`` instances for tag-based readers.
    - NumPy arrays and scalar slice locations for 2D interpolation between slices.

Outputs:
    - Primitive types, tuples, optional NumPy arrays, and small dicts for UI/spatial summaries.

Requirements:
    - numpy, pydicom
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pydicom.dataset import Dataset


def read_slice_location(dataset: Dataset) -> Optional[float]:
    """Return a scalar slice position from ``SliceLocation`` or Z of ``ImagePositionPatient``."""
    slice_location = getattr(dataset, "SliceLocation", None)
    if slice_location is not None:
        try:
            return float(slice_location)
        except (ValueError, TypeError):
            pass

    image_position = getattr(dataset, "ImagePositionPatient", None)
    if image_position is not None and len(image_position) >= 3:
        try:
            return float(image_position[2])
        except (ValueError, TypeError, IndexError):
            pass

    return None


def read_pixel_spacing(dataset: Dataset) -> Optional[Tuple[float, float]]:
    """Return ``(row_spacing, col_spacing)`` in mm from ``PixelSpacing``, or ``None``."""
    pixel_spacing = getattr(dataset, "PixelSpacing", None)
    if pixel_spacing is not None and len(pixel_spacing) >= 2:
        try:
            row_spacing = float(pixel_spacing[0])
            col_spacing = float(pixel_spacing[1])
            return (row_spacing, col_spacing)
        except (ValueError, TypeError, IndexError):
            pass

    return None


def read_pixel_spacing_with_source(
    dataset: Dataset,
) -> Tuple[Optional[Tuple[float, float]], Optional[str]]:
    """
    Return pixel spacing and a short source label describing how it was obtained.

    Priority matches ``FusionHandler.get_pixel_spacing_with_source``:
    ``PixelSpacing``, then ``ImagerPixelSpacing``, then ``ReconstructionDiameter`` heuristic.
    """
    pixel_spacing = getattr(dataset, "PixelSpacing", None)
    if pixel_spacing is not None and len(pixel_spacing) >= 2:
        try:
            row_spacing = float(pixel_spacing[0])
            col_spacing = float(pixel_spacing[1])
            return (row_spacing, col_spacing), "pixel_spacing"
        except (ValueError, TypeError, IndexError):
            pass

    imager_spacing = getattr(dataset, "ImagerPixelSpacing", None)
    if imager_spacing is not None and len(imager_spacing) >= 2:
        try:
            row_spacing = float(imager_spacing[0])
            col_spacing = float(imager_spacing[1])
            return (row_spacing, col_spacing), "pixel_spacing"
        except (ValueError, TypeError, IndexError):
            pass

    recon_diameter = getattr(dataset, "ReconstructionDiameter", None)
    rows = getattr(dataset, "Rows", None)
    cols = getattr(dataset, "Columns", None)

    if recon_diameter is not None and rows is not None and cols is not None:
        try:
            recon_diameter_mm = float(recon_diameter)
            rows_int = int(rows)
            cols_int = int(cols)
            if rows_int > 0 and cols_int > 0:
                col_spacing = recon_diameter_mm / float(cols_int)
                row_spacing = recon_diameter_mm / float(rows_int)
                return (row_spacing, col_spacing), "reconDiameter_cols"
        except (ValueError, TypeError, ZeroDivisionError):
            pass

    return None, None


def read_image_position_patient(
    dataset: Dataset,
) -> Optional[Tuple[float, float, float]]:
    """Return ``(x, y, z)`` from ``ImagePositionPatient``, or ``None``."""
    image_position = getattr(dataset, "ImagePositionPatient", None)
    if image_position is not None and len(image_position) >= 3:
        try:
            x = float(image_position[0])
            y = float(image_position[1])
            z = float(image_position[2])
            return (x, y, z)
        except (ValueError, TypeError, IndexError):
            pass

    return None


def check_frame_of_reference_match(
    series1_datasets: List[Dataset],
    series2_datasets: List[Dataset],
) -> bool:
    """True if both series have the same ``FrameOfReferenceUID`` on their first slice."""
    if not series1_datasets or not series2_datasets:
        return False

    frame_ref_1 = getattr(series1_datasets[0], "FrameOfReferenceUID", None)
    frame_ref_2 = getattr(series2_datasets[0], "FrameOfReferenceUID", None)

    if frame_ref_1 is None or frame_ref_2 is None:
        return False

    return frame_ref_1 == frame_ref_2


def sorted_slice_index_locations(datasets: List[Dataset]) -> List[Tuple[int, float]]:
    """
    Build a list of ``(original_index, slice_location)`` sorted by location.

    Slices without a readable location are omitted.
    """
    locations = []
    for idx, dataset in enumerate(datasets):
        location = read_slice_location(dataset)
        if location is not None:
            locations.append((idx, location))
    locations.sort(key=lambda x: x[1])
    return locations


def linear_blend_rescaled_slices(
    array1: np.ndarray,
    array2: np.ndarray,
    base_location: float,
    loc1: float,
    loc2: float,
) -> np.ndarray:
    """
    Linearly blend two same-shape rescaled overlay slices along the slice normal.

    ``weight`` is 0 at ``loc1`` and 1 at ``loc2``, clipped to ``[0, 1]``.
    Callers must ensure shapes match and locations are valid.
    """
    weight = (base_location - loc1) / (loc2 - loc1)
    weight = float(np.clip(weight, 0.0, 1.0))
    return array1 * (1.0 - weight) + array2 * weight


def translation_offset_pixels_from_ipps(
    base_ipp: Tuple[float, float, float],
    overlay_ipp: Tuple[float, float, float],
    base_pixel_spacing: Tuple[float, float],
) -> Tuple[float, float]:
    """
    Convert mm offset between IPPs into pixel offset in base image coordinates.

    ``base_pixel_spacing`` is ``(row_spacing, col_spacing)`` in mm.
    """
    offset_mm_x = overlay_ipp[0] - base_ipp[0]
    offset_mm_y = overlay_ipp[1] - base_ipp[1]
    offset_px_x = offset_mm_x / base_pixel_spacing[1]
    offset_px_y = offset_mm_y / base_pixel_spacing[0]
    return (offset_px_x, offset_px_y)


def series_spatial_info_dict(datasets: List[Dataset]) -> Dict[str, Any]:
    """
    Summarize spacing, origin, matrix size, and FOV from the first dataset in *datasets*.
    """
    if not datasets:
        return {}

    first_ds = datasets[0]
    info: Dict[str, Any] = {}

    pixel_spacing = read_pixel_spacing(first_ds)
    if pixel_spacing is not None:
        info["pixel_spacing"] = pixel_spacing

    image_position = read_image_position_patient(first_ds)
    if image_position is not None:
        info["image_position"] = image_position

    rows = getattr(first_ds, "Rows", None)
    cols = getattr(first_ds, "Columns", None)
    if rows is not None and cols is not None:
        info["matrix_size"] = (int(rows), int(cols))

        if pixel_spacing is not None:
            fov_y = rows * pixel_spacing[0]
            fov_x = cols * pixel_spacing[1]
            info["field_of_view"] = (fov_x, fov_y)

    return info
