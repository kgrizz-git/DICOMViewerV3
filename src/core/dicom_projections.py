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

import numpy as np
from typing import Optional, List
from pydicom.dataset import Dataset

from core.dicom_pixel_array import get_pixel_array


def average_intensity_projection(slices: List[Dataset]) -> Optional[np.ndarray]:
    """Create Average Intensity Projection from multiple slices. Returns float32 array or None."""
    if not slices:
        return None
    pixel_arrays = []
    for dataset in slices:
        arr = get_pixel_array(dataset)
        if arr is not None:
            pixel_arrays.append(arr)
    if not pixel_arrays:
        return None
    stacked = np.stack(pixel_arrays, axis=0)
    return np.mean(stacked, axis=0).astype(np.float32)


def maximum_intensity_projection(slices: List[Dataset]) -> Optional[np.ndarray]:
    """Create Maximum Intensity Projection from multiple slices. Returns float32 array or None."""
    if not slices:
        return None
    pixel_arrays = []
    for dataset in slices:
        arr = get_pixel_array(dataset)
        if arr is not None:
            pixel_arrays.append(arr)
    if not pixel_arrays:
        return None
    stacked = np.stack(pixel_arrays, axis=0)
    return np.max(stacked, axis=0).astype(np.float32)


def minimum_intensity_projection(slices: List[Dataset]) -> Optional[np.ndarray]:
    """Create Minimum Intensity Projection from multiple slices. Returns float32 array or None."""
    if not slices:
        return None
    pixel_arrays = []
    for dataset in slices:
        arr = get_pixel_array(dataset)
        if arr is not None:
            pixel_arrays.append(arr)
    if not pixel_arrays:
        return None
    stacked = np.stack(pixel_arrays, axis=0)
    return np.min(stacked, axis=0).astype(np.float32)
