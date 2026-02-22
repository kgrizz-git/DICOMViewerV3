"""
DICOM window/level handling.

This module applies window/level to pixel arrays, converts between raw and rescaled
window/level values, and extracts window center/width and presets from DICOM datasets.

Inputs:
    - pydicom Dataset, pixel arrays, rescale parameters

Outputs:
    - Windowed pixel arrays (0-255 uint8), (center, width) tuples, preset lists

Requirements:
    - numpy, pydicom
    - core.dicom_pixel_array (get_pixel_array)
"""

import numpy as np
from typing import Optional, List, Tuple
from pydicom.dataset import Dataset

from core.dicom_pixel_array import get_pixel_array


def apply_window_level(
    pixel_array: np.ndarray,
    window_center: float,
    window_width: float,
    rescale_slope: Optional[float] = None,
    rescale_intercept: Optional[float] = None,
) -> np.ndarray:
    """Apply window/level transformation to pixel array. Returns 0-255 uint8."""
    if rescale_slope is not None and rescale_intercept is not None:
        pixel_array = pixel_array * rescale_slope + rescale_intercept
    window_min = window_center - window_width / 2.0
    window_max = window_center + window_width / 2.0
    windowed = np.clip(pixel_array, window_min, window_max)
    if window_max > window_min:
        normalized = ((windowed - window_min) / (window_max - window_min) * 255.0).astype(np.uint8)
    else:
        normalized = np.zeros_like(windowed, dtype=np.uint8)
    return normalized


def apply_color_window_level_luminance(
    pixel_array: np.ndarray,
    window_center: float,
    window_width: float,
    rescale_slope: Optional[float] = None,
    rescale_intercept: Optional[float] = None,
) -> np.ndarray:
    """Apply window/level to color images using luminance-based approach. Returns 0-255 uint8 RGB."""
    try:
        if len(pixel_array.shape) != 3 or pixel_array.shape[2] != 3:
            raise ValueError(f"Expected RGB array with shape (height, width, 3), got {pixel_array.shape}")
        rgb_float = pixel_array.astype(np.float32)
        if rescale_slope is not None and rescale_intercept is not None:
            rgb_float = rgb_float * rescale_slope + rescale_intercept
        luminance = np.dot(rgb_float[..., :3], [0.299, 0.587, 0.114])
        window_min = window_center - window_width / 2.0
        window_max = window_center + window_width / 2.0
        windowed_luminance = np.clip(luminance, window_min, window_max)
        if window_max > window_min:
            normalized_luminance = ((windowed_luminance - window_min) / (window_max - window_min) * 255.0)
        else:
            normalized_luminance = np.zeros_like(luminance)
        epsilon = 1e-10
        scale = normalized_luminance / (luminance + epsilon)
        zero_luminance_mask = luminance < epsilon
        if np.any(zero_luminance_mask):
            max_channel = np.max(rgb_float, axis=2)
            scale[zero_luminance_mask] = normalized_luminance[zero_luminance_mask] / (max_channel[zero_luminance_mask] + epsilon)
        windowed_rgb = rgb_float * scale[..., np.newaxis]
        return np.clip(windowed_rgb, 0, 255).astype(np.uint8)
    except Exception as e:
        print(f"Error applying color window/level: {e}")
        if pixel_array.max() > pixel_array.min():
            return ((pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min()) * 255.0).astype(np.uint8)
        return pixel_array.astype(np.uint8)


def convert_window_level_rescaled_to_raw(
    center: float, width: float, slope: float, intercept: float
) -> Tuple[float, float]:
    """Convert window/level from rescaled to raw pixel values. Returns (raw_center, raw_width)."""
    if slope == 0.0:
        return center, width
    return (center - intercept) / slope, width / slope


def convert_window_level_raw_to_rescaled(
    center: float, width: float, slope: float, intercept: float
) -> Tuple[float, float]:
    """Convert window/level from raw to rescaled. Returns (rescaled_center, rescaled_width)."""
    return center * slope + intercept, width * slope


def get_window_level_from_dataset(
    dataset: Dataset,
    rescale_slope: Optional[float] = None,
    rescale_intercept: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float], bool]:
    """
    Get window center and width from DICOM dataset.
    Returns (window_center, window_width, is_rescaled).
    """
    try:
        window_center = None
        window_width = None
        from_dicom_tags = False
        if hasattr(dataset, 'WindowCenter'):
            wc = dataset.WindowCenter
            window_center = float(wc[0]) if isinstance(wc, (list, tuple)) else float(wc)
            from_dicom_tags = True
        if hasattr(dataset, 'WindowWidth'):
            ww = dataset.WindowWidth
            window_width = float(ww[0]) if isinstance(ww, (list, tuple)) else float(ww)
            from_dicom_tags = True
        if window_center is None or window_width is None:
            pixel_array = get_pixel_array(dataset)
            if pixel_array is not None:
                pixel_min = float(np.min(pixel_array))
                pixel_max = float(np.max(pixel_array))
                if window_center is None:
                    midpoint = (pixel_min + pixel_max) / 2.0
                    non_zero = pixel_array[pixel_array != 0]
                    window_center = max(float(np.median(non_zero)), midpoint) if len(non_zero) > 0 else midpoint
                if window_width is None:
                    window_width = pixel_max - pixel_min
            from_dicom_tags = False
        is_rescaled = (
            from_dicom_tags
            and rescale_slope is not None
            and rescale_intercept is not None
            and rescale_slope != 0.0
        )
        return window_center, window_width, is_rescaled
    except Exception:
        return None, None, False


def get_window_level_presets_from_dataset(
    dataset: Dataset,
    rescale_slope: Optional[float] = None,
    rescale_intercept: Optional[float] = None,
) -> List[Tuple[float, float, bool, Optional[str]]]:
    """
    Get all window center/width presets from DICOM dataset.
    Returns list of (window_center, window_width, is_rescaled, preset_name).
    """
    presets = []
    try:
        window_centers = []
        window_widths = []
        from_dicom_tags = False

        def parse_window_value(value):
            if value is None:
                return []
            try:
                from pydicom.multival import MultiValue
                if isinstance(value, MultiValue):
                    return [float(x) for x in value]
            except ImportError:
                pass
            if isinstance(value, (list, tuple)):
                return [float(x) for x in value]
            if isinstance(value, str):
                if '\\' in value:
                    return [float(p.strip()) for p in value.split('\\') if p.strip()]
                if value.strip().startswith('[') and value.strip().endswith(']'):
                    inner = value.strip()[1:-1]
                    return [float(p.strip()) for p in inner.split(',') if p.strip()]
                return [float(value)]
            return [float(value)]

        if hasattr(dataset, 'WindowCenter'):
            window_centers = parse_window_value(dataset.WindowCenter)
            from_dicom_tags = True
        if hasattr(dataset, 'WindowWidth'):
            window_widths = parse_window_value(dataset.WindowWidth)
            from_dicom_tags = True
        num_presets = max(len(window_centers), len(window_widths))
        if num_presets == 0:
            return presets
        for i in range(num_presets):
            wc = window_centers[i] if i < len(window_centers) else (window_centers[-1] if window_centers else None)
            ww = window_widths[i] if i < len(window_widths) else (window_widths[-1] if window_widths else None)
            if wc is None or ww is None:
                continue
            preset_name = None if i == 0 else f"Preset {i + 1}"
            is_rescaled = (
                from_dicom_tags
                and rescale_slope is not None
                and rescale_intercept is not None
                and rescale_slope != 0.0
            )
            presets.append((wc, ww, is_rescaled, preset_name))
        return presets
    except Exception:
        return []
