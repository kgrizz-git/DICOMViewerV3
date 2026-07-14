"""
DICOM intensity projections (AIP, MIP, MinIP).

This module creates average, maximum, and minimum intensity projections from
lists of DICOM slice datasets. Used for MPR and similar views.

Inputs:
    - List of pydicom Dataset objects (slices)

Outputs:
    - NumPy arrays (float32) representing the projection, or None

Requirements:
    - numpy, pydicom
    - core.dicom_pixel_array (get_pixel_array)
"""

from collections import OrderedDict
from typing import Any

import numpy as np
from pydicom.dataset import Dataset

from core.dicom_pixel_array import get_pixel_array

# --- Projection frame cache ---
_projection_cache: "OrderedDict[tuple[str, tuple[str, ...]], Any]" = OrderedDict()
_MAX_PROJECTION_CACHE = 10


def _cache_key(
    projection_type: str, slices: list[Dataset]
) -> tuple[str, tuple[str, ...]] | None:
    """Build a cache key from projection type and SOPInstanceUIDs of slices.

    Returns ``None`` if any dataset lacks a SOPInstanceUID, making the
    result uncacheable.
    """
    uids: list[str] = []
    for ds in slices:
        uid = getattr(ds, "SOPInstanceUID", None)
        if uid is None:
            return None
        uids.append(str(uid))
    return (projection_type, tuple(uids))


def clear_projection_cache() -> None:
    """Clear the module-level projection cache."""
    _projection_cache.clear()


def average_intensity_projection(slices: list[Dataset]) -> np.ndarray | None:
    """Create Average Intensity Projection from multiple slices. Returns float32 array or None."""
    if not slices:
        return None

    key = _cache_key("aip", slices)
    if key is not None and key in _projection_cache:
        _projection_cache.move_to_end(key)
        return _projection_cache[key]

    pixel_arrays = []
    for dataset in slices:
        arr = get_pixel_array(dataset)
        if arr is not None:
            pixel_arrays.append(arr)
    if not pixel_arrays:
        return None
    stacked = np.stack(pixel_arrays, axis=0)
    result = np.mean(stacked, axis=0).astype(np.float32)

    if key is not None:
        _projection_cache[key] = result
        if len(_projection_cache) > _MAX_PROJECTION_CACHE:
            _projection_cache.popitem(last=False)

    return result


def maximum_intensity_projection(slices: list[Dataset]) -> np.ndarray | None:
    """Create Maximum Intensity Projection from multiple slices. Returns float32 array or None."""
    if not slices:
        return None

    key = _cache_key("mip", slices)
    if key is not None and key in _projection_cache:
        _projection_cache.move_to_end(key)
        return _projection_cache[key]

    pixel_arrays = []
    for dataset in slices:
        arr = get_pixel_array(dataset)
        if arr is not None:
            pixel_arrays.append(arr)
    if not pixel_arrays:
        return None
    stacked = np.stack(pixel_arrays, axis=0)
    result = np.max(stacked, axis=0).astype(np.float32)

    if key is not None:
        _projection_cache[key] = result
        if len(_projection_cache) > _MAX_PROJECTION_CACHE:
            _projection_cache.popitem(last=False)

    return result


def minimum_intensity_projection(slices: list[Dataset]) -> np.ndarray | None:
    """Create Minimum Intensity Projection from multiple slices. Returns float32 array or None."""
    if not slices:
        return None

    key = _cache_key("minip", slices)
    if key is not None and key in _projection_cache:
        _projection_cache.move_to_end(key)
        return _projection_cache[key]

    pixel_arrays = []
    for dataset in slices:
        arr = get_pixel_array(dataset)
        if arr is not None:
            pixel_arrays.append(arr)
    if not pixel_arrays:
        return None
    stacked = np.stack(pixel_arrays, axis=0)
    result = np.min(stacked, axis=0).astype(np.float32)

    if key is not None:
        _projection_cache[key] = result
        if len(_projection_cache) > _MAX_PROJECTION_CACHE:
            _projection_cache.popitem(last=False)

    return result
