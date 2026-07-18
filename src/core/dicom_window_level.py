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
from typing import Any

import numpy as np
from pydicom.dataset import Dataset

from core.dicom_pixel_array import get_pixel_array
from core.dicom_rescale import get_rescale_parameters
from utils.privacy.console import print_redacted


def _get_frame_voi_lut_item(dataset: Dataset) -> Dataset | None:
    """Return the first FrameVOILUTSequence item from functional groups, or None."""
    shared_seq = getattr(dataset, "SharedFunctionalGroupsSequence", None)
    if shared_seq:
        item = shared_seq[0]
        voi = getattr(item, "FrameVOILUTSequence", None)
        if voi:
            return voi[0]

    per_frame_seq = getattr(dataset, "PerFrameFunctionalGroupsSequence", None)
    if per_frame_seq:
        frame_index = int(getattr(dataset, "_frame_index", 0) or 0)
        if not (0 <= frame_index < len(per_frame_seq)):
            frame_index = 0
        item = per_frame_seq[frame_index]
        voi = getattr(item, "FrameVOILUTSequence", None)
        if voi:
            return voi[0]
    return None


def apply_window_level(
    pixel_array: np.ndarray,
    window_center: float,
    window_width: float,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
) -> np.ndarray:
    """Apply window/level transformation to pixel array. Returns 0-255 uint8."""
    if rescale_slope is not None and rescale_intercept is not None:
        arr = pixel_array * rescale_slope + rescale_intercept
    else:
        arr = pixel_array.astype(np.float64, copy=False)
    window_min = window_center - window_width / 2.0
    window_max = window_center + window_width / 2.0
    if window_max > window_min:
        # Fuse clip + normalize + uint8 cast with in-place ops (2 allocs vs 4)
        np.clip(arr, window_min, window_max, out=arr)
        arr -= window_min
        arr *= (255.0 / (window_max - window_min))
        return arr.astype(np.uint8)
    else:
        return np.zeros(pixel_array.shape, dtype=np.uint8)


def apply_color_window_level_luminance(
    pixel_array: np.ndarray,
    window_center: float,
    window_width: float,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
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
        print_redacted(f"Error applying color window/level: {e}")
        if pixel_array.max() > pixel_array.min():
            return ((pixel_array - pixel_array.min()) / (pixel_array.max() - pixel_array.min()) * 255.0).astype(np.uint8)
        return pixel_array.astype(np.uint8)


def convert_window_level_rescaled_to_raw(
    center: float, width: float, slope: float, intercept: float
) -> tuple[float, float]:
    """Convert window/level from rescaled to raw pixel values. Returns (raw_center, raw_width)."""
    if slope == 0.0:  # NOSONAR(S1244): RescaleSlope is DICOM DS-VR; exact 0.0 is well-defined
        return center, width
    return (center - intercept) / slope, width / slope


def convert_window_level_raw_to_rescaled(
    center: float, width: float, slope: float, intercept: float
) -> tuple[float, float]:
    """Convert window/level from raw to rescaled. Returns (rescaled_center, rescaled_width)."""
    return center * slope + intercept, width * slope


def get_window_level_from_dataset(
    dataset: Dataset,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
) -> tuple[float | None, float | None, bool]:
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
        # Fallback: Enhanced Multi-frame FrameVOILUTSequence in functional groups
        if window_center is None or window_width is None:
            voi_item = _get_frame_voi_lut_item(dataset)
            if voi_item is not None:
                if window_center is None and hasattr(voi_item, 'WindowCenter'):
                    wc = voi_item.WindowCenter
                    window_center = float(wc[0]) if isinstance(wc, (list, tuple)) else float(wc)
                    from_dicom_tags = True
                if window_width is None and hasattr(voi_item, 'WindowWidth'):
                    ww = voi_item.WindowWidth
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
            and rescale_slope != 0.0  # NOSONAR(S1244): RescaleSlope is DICOM DS-VR; exact 0.0 is well-defined
        )
        return window_center, window_width, is_rescaled
    except Exception:
        return None, None, False


def get_base_window_level(
    dataset: Dataset,
    window_center: float | None,
    window_width: float | None,
    rescale_slope: float | None,
    rescale_intercept: float | None,
) -> tuple[float | None, float | None, bool, bool]:
    """
    Fill in window center/width from the dataset when either is missing.

    Returns ``(window_center, window_width, extracted_from_dataset, is_rescaled)``.
    ``extracted_from_dataset`` reflects whether either value was ``None`` on
    entry (decided before defaulting), not whether the dataset actually had
    ``WindowCenter``/``WindowWidth`` tags.
    """
    extracted = window_center is None or window_width is None
    is_rescaled = False
    if extracted:
        ds_wc, ds_ww, is_rescaled = get_window_level_from_dataset(
            dataset, rescale_slope=rescale_slope, rescale_intercept=rescale_intercept
        )
        if window_center is None:
            window_center = ds_wc
        if window_width is None:
            window_width = ds_ww
    return window_center, window_width, extracted, is_rescaled


def convert_window_level_units(
    window_center: float | None,
    window_width: float | None,
    extracted_from_dataset: bool,
    is_rescaled: bool,
    apply_rescale: bool,
    rescale_slope: float | None,
    rescale_intercept: float | None,
) -> tuple[float | None, float | None]:
    """
    Convert window/level between raw and rescaled units, but only for values
    extracted from the dataset -- explicitly provided values are assumed to
    already be in the correct units for ``apply_rescale`` (caller's contract).
    """
    if (
        window_center is not None
        and window_width is not None
        and extracted_from_dataset
        and rescale_slope is not None
        and rescale_intercept is not None
        and rescale_slope != 0.0  # NOSONAR(S1244): RescaleSlope is DICOM DS-VR; exact 0.0 is well-defined
    ):
        if not apply_rescale and is_rescaled:
            # Window/level is in rescaled units (HU), but we're not applying rescale to
            # pixels. Convert window/level from rescaled to raw pixel values.
            window_center, window_width = convert_window_level_rescaled_to_raw(
                window_center, window_width, rescale_slope, rescale_intercept
            )
        elif apply_rescale and not is_rescaled:
            # Window/level is in raw units, but we're applying rescale to pixels.
            # Convert window/level from raw to rescaled units.
            window_center, window_width = convert_window_level_raw_to_rescaled(
                window_center, window_width, rescale_slope, rescale_intercept
            )
    return window_center, window_width


def resolve_window_level_and_rescale(
    dataset: Dataset,
    window_center: float | None,
    window_width: float | None,
    apply_rescale: bool,
) -> tuple[float | None, float | None, float | None, float | None]:
    """
    Resolve window/level (from dataset if not provided) and the rescale slope/
    intercept pair that should reach pixel processing.

    Returns ``(window_center, window_width, rescale_slope, rescale_intercept)``.
    The rescale pair reaches pixel processing only when ``apply_rescale`` is
    True. Unit conversion of the window/level itself uses the full rescale
    pair regardless of ``apply_rescale`` -- when the dataset's window/level is
    in rescaled (HU) units and ``apply_rescale`` is False, the window must be
    converted to raw units so it stays in the same unit space as the
    (unrescaled) pixels.
    """
    rescale_slope, rescale_intercept, _ = get_rescale_parameters(dataset)

    window_center, window_width, extracted, is_rescaled = get_base_window_level(
        dataset, window_center, window_width, rescale_slope, rescale_intercept
    )

    window_center, window_width = convert_window_level_units(
        window_center, window_width, extracted, is_rescaled,
        apply_rescale, rescale_slope, rescale_intercept,
    )

    out_slope, out_intercept = (rescale_slope, rescale_intercept) if apply_rescale else (None, None)
    return window_center, window_width, out_slope, out_intercept


def get_window_level_presets_from_dataset(
    dataset: Dataset,
    rescale_slope: float | None = None,
    rescale_intercept: float | None = None,
) -> list[tuple[float, float, bool, str | None]]:
    """
    Get all window center/width presets from DICOM dataset.
    Returns list of (window_center, window_width, is_rescaled, preset_name).
    """
    presets = []
    try:
        window_centers = []
        window_widths = []
        explanations: list[str] = []
        from_dicom_tags = False

        def parse_window_value(value: Any) -> list[float]:
            if value is None:
                return []
            from pydicom.multival import MultiValue
            if isinstance(value, MultiValue):
                return [float(x) for x in value]
            if isinstance(value, (list, tuple)):
                return [float(x) for x in value]
            if isinstance(value, str):
                if '\\' in value:
                    return [float(p.strip()) for p in value.split('\\') if p.strip()]
                if value.strip().startswith('[') and value.strip().endswith(']'):
                    inner = value.strip()[1:-1]
                    return [float(p.strip()) for p in inner.split(',') if p.strip()]
                return [float(value)]
            # Fallback for scalar numeric-ish values.
            return [float(value)]

        def parse_explanation_values(value: Any) -> list[str]:
            if value is None:
                return []
            from pydicom.multival import MultiValue
            if isinstance(value, MultiValue):
                return [str(x).strip() for x in value]
            if isinstance(value, (list, tuple)):
                return [str(x).strip() for x in value]
            text = str(value).strip()
            if not text:
                return []
            if '\\' in text:
                return [part.strip() for part in text.split('\\')]
            if text.startswith('[') and text.endswith(']'):
                inner = text[1:-1]
                return [part.strip().strip("'\"") for part in inner.split(',')]
            return [text]

        if hasattr(dataset, 'WindowCenter'):
            window_centers = parse_window_value(dataset.WindowCenter)
            from_dicom_tags = True
        if hasattr(dataset, 'WindowWidth'):
            window_widths = parse_window_value(dataset.WindowWidth)
            from_dicom_tags = True
        if hasattr(dataset, 'WindowCenterWidthExplanation'):
            explanations = parse_explanation_values(dataset.WindowCenterWidthExplanation)
        original_dataset = getattr(dataset, "_original_dataset", None)
        if not explanations and original_dataset is not None and hasattr(
            original_dataset, 'WindowCenterWidthExplanation'
        ):
            explanations = parse_explanation_values(
                original_dataset.WindowCenterWidthExplanation
            )
        # Fallback: Enhanced Multi-frame FrameVOILUTSequence
        voi_item = _get_frame_voi_lut_item(dataset)
        if not window_centers or not window_widths:
            if voi_item is not None:
                if not window_centers and hasattr(voi_item, 'WindowCenter'):
                    window_centers = parse_window_value(voi_item.WindowCenter)
                    from_dicom_tags = True
                if not window_widths and hasattr(voi_item, 'WindowWidth'):
                    window_widths = parse_window_value(voi_item.WindowWidth)
                    from_dicom_tags = True
                if not explanations and hasattr(voi_item, 'WindowCenterWidthExplanation'):
                    explanations = parse_explanation_values(
                        voi_item.WindowCenterWidthExplanation
                    )
        elif not explanations and voi_item is not None and hasattr(
            voi_item, 'WindowCenterWidthExplanation'
        ):
            explanations = parse_explanation_values(
                voi_item.WindowCenterWidthExplanation
            )
        num_presets = max(len(window_centers), len(window_widths))
        if num_presets == 0:
            return presets
        for i in range(num_presets):
            wc = window_centers[i] if i < len(window_centers) else (window_centers[-1] if window_centers else None)
            ww = window_widths[i] if i < len(window_widths) else (window_widths[-1] if window_widths else None)
            if wc is None or ww is None:
                continue
            preset_name = (
                explanations[i] if i < len(explanations) and explanations[i] else str(i + 1)
            )
            is_rescaled = (
                from_dicom_tags
                and rescale_slope is not None
                and rescale_intercept is not None
                and rescale_slope != 0.0  # NOSONAR(S1244): RescaleSlope is DICOM DS-VR; exact 0.0 is well-defined
            )
            presets.append((wc, ww, is_rescaled, preset_name))
        return presets
    except Exception:
        return []
