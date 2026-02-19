"""
DICOM pixel value statistics (range, median).

This module computes min/max pixel value and median across a single dataset
or a series of datasets, with optional rescale application.

Inputs:
    - pydicom Dataset or list of Datasets
    - apply_rescale: bool

Outputs:
    - (min_value, max_value) or median float, or None

Requirements:
    - numpy, pydicom
    - core.dicom_pixel_array (get_pixel_array)
    - core.dicom_rescale (get_rescale_parameters)
"""

import numpy as np
from typing import Optional, List, Tuple
from pydicom.dataset import Dataset

from core.dicom_pixel_array import get_pixel_array
from core.dicom_rescale import get_rescale_parameters


def get_pixel_value_range(dataset: Dataset, apply_rescale: bool = False) -> Tuple[Optional[float], Optional[float]]:
    """Get min and max pixel values from a DICOM dataset. Returns (min_value, max_value) or (None, None)."""
    try:
        pixel_array = get_pixel_array(dataset)
        if pixel_array is None:
            return None, None
        if apply_rescale:
            rescale_slope, rescale_intercept, _ = get_rescale_parameters(dataset)
            if rescale_slope is not None and rescale_intercept is not None:
                pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
        return float(np.min(pixel_array)), float(np.max(pixel_array))
    except (MemoryError, ValueError, AttributeError, RuntimeError, Exception) as e:
        if not isinstance(e, MemoryError):
            print(f"Error calculating pixel value range: {e}")
        return None, None


def get_series_pixel_value_range(
    datasets: List[Dataset], apply_rescale: bool = False
) -> Tuple[Optional[float], Optional[float]]:
    """Get min and max pixel values across a series. Returns (min_value, max_value) or (None, None)."""
    if not datasets:
        return None, None
    try:
        series_min = None
        series_max = None
        for dataset in datasets:
            try:
                pixel_array = get_pixel_array(dataset)
                if pixel_array is None:
                    continue
                if apply_rescale:
                    rescale_slope, rescale_intercept, _ = get_rescale_parameters(dataset)
                    if rescale_slope is not None and rescale_intercept is not None:
                        pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
                slice_min = float(np.min(pixel_array))
                slice_max = float(np.max(pixel_array))
                if series_min is None or slice_min < series_min:
                    series_min = slice_min
                if series_max is None or slice_max > series_max:
                    series_max = slice_max
            except Exception:
                continue
        return (series_min, series_max) if (series_min is not None and series_max is not None) else (None, None)
    except Exception as e:
        print(f"Error calculating series pixel value range: {e}")
        return None, None


def get_series_pixel_median(datasets: List[Dataset], apply_rescale: bool = False) -> Optional[float]:
    """Get median pixel value across a series (excluding zeros). Returns float or None."""
    if not datasets:
        return None
    try:
        all_pixel_values = []
        for dataset in datasets:
            try:
                pixel_array = get_pixel_array(dataset)
                if pixel_array is None:
                    continue
                if apply_rescale:
                    rescale_slope, rescale_intercept, _ = get_rescale_parameters(dataset)
                    if rescale_slope is not None and rescale_intercept is not None:
                        pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
                all_pixel_values.append(pixel_array.flatten())
            except Exception:
                continue
        if not all_pixel_values:
            return None
        combined = np.concatenate(all_pixel_values)
        non_zero = combined[combined != 0]
        if len(non_zero) > 0:
            return float(np.median(non_zero))
        return None
    except (MemoryError, Exception) as e:
        if not isinstance(e, MemoryError):
            print(f"Error calculating series pixel median: {e}")
        return None
