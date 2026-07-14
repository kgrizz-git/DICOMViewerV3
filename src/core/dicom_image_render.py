"""
Color-shape classification, normalization, and PIL rendering for DICOM pixel data.

This module classifies color vs. grayscale array shapes, normalizes arrays to
0-255 uint8 (with and without window/level), dispatches YBR/RGB channel-order
conversion, and constructs the final PIL Image for both color and grayscale
paths.

Inputs:
    - NumPy pixel arrays, pydicom Dataset, window/level and rescale values

Outputs:
    - Normalized uint8 arrays, PIL Image objects (or None on failure)

Requirements:
    - numpy, Pillow, pydicom
    - core.dicom_color (YBR/RGB conversion)
    - core.dicom_window_level (window/level application)
"""

import logging

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

from core import dicom_color
from core.dicom_window_level import (
    apply_color_window_level_luminance,
    apply_window_level,
)
from utils.log_sanitizer import sanitized_format_exc

_logger = logging.getLogger(__name__)


def normalize_to_uint8(array: np.ndarray) -> np.ndarray:
    """Normalize an array to 0-255 uint8. No clip, no zeroing of flat arrays (see
    dev-docs/TO_DO.md for the flat-array uint8-wraparound quirk this preserves)."""
    processed = array.astype(np.float32)
    if processed.max() > processed.min():
        processed = ((processed - processed.min()) / (processed.max() - processed.min()) * 255.0)
    return processed.astype(np.uint8)


def normalize_channels_to_uint8(array: np.ndarray) -> np.ndarray:
    """Normalize a (height, width, channels) array to 0-255 uint8, per channel.
    Flat channels are zeroed (unlike normalize_to_uint8) and the result is clipped."""
    processed = array.astype(np.float32)
    for channel in range(processed.shape[2]):
        channel_data = processed[:, :, channel]
        if channel_data.max() > channel_data.min():
            processed[:, :, channel] = (
                (channel_data - channel_data.min()) / (channel_data.max() - channel_data.min()) * 255.0
            )
        else:
            processed[:, :, channel] = np.zeros_like(channel_data)
    return np.clip(processed, 0, 255).astype(np.uint8)


def _samples_per_pixel(dataset: Dataset) -> int:
    """Best-effort SamplesPerPixel extraction with grayscale fallback."""
    if not hasattr(dataset, 'SamplesPerPixel'):
        return 1

    samples_value = dataset.SamplesPerPixel
    if isinstance(samples_value, (list, tuple)):
        return int(samples_value[0])
    return int(samples_value)


def classify_color_shape(
    dataset: Dataset, pixel_array: np.ndarray, is_color: bool
) -> tuple[bool, bool]:
    """
    Initial color-shape classification, based on ``SamplesPerPixel``.

    Returns ``(is_multi_frame_color, is_single_frame_color)``. Use
    ``reclassify_color_shape`` instead after palette or YBR conversion --
    ``SamplesPerPixel`` is 1 for PALETTE COLOR even though it is color, so this
    function correctly returns ``(False, False)`` pre-conversion.
    """
    if not is_color:
        return False, False

    array_shape = pixel_array.shape
    if len(array_shape) == 4:
        # Multi-frame color: (frames, height, width, channels)
        return True, False

    if len(array_shape) != 3:
        return False, False

    # Could be single-frame color (height, width, channels) or multi-frame
    # grayscale (frames, height, width). Check if last dimension matches
    # SamplesPerPixel.
    samples_per_pixel = _samples_per_pixel(dataset)
    is_single_frame_color = samples_per_pixel > 1 and array_shape[2] == samples_per_pixel
    return False, is_single_frame_color


def reclassify_color_shape(pixel_array: np.ndarray) -> tuple[bool, bool]:
    """Shape-only color-shape classification, used after palette or YBR conversion
    (once the array is genuinely RGB, SamplesPerPixel no longer needs consulting)."""
    array_shape = pixel_array.shape
    is_multi_frame_color = len(array_shape) == 4
    is_single_frame_color = len(array_shape) == 3 and array_shape[2] == 3
    return is_multi_frame_color, is_single_frame_color


def convert_color_pixel_array(
    pixel_array: np.ndarray,
    photometric_interpretation: str | None,
    transfer_syntax: str | None,
    dataset: Dataset,
) -> tuple[np.ndarray, bool]:
    """
    Convert YBR pixel data to RGB, or fix RGB channel order, based on
    ``photometric_interpretation``. Returns ``(pixel_array, did_ybr_convert)``;
    ``did_ybr_convert`` is True only for the YBR branch, matching the original's
    shape reclassification (which only re-derives flags after a YBR conversion,
    not after the RGB channel-order fix).
    """
    if not photometric_interpretation:
        return pixel_array, False

    pi_upper = photometric_interpretation.upper()
    ybr_types = ['YBR_FULL', 'YBR_FULL_422', 'YBR_ICT', 'YBR_RCT']
    if any(ybr_type in pi_upper for ybr_type in ybr_types):
        # Convert YBR to RGB (pass PhotometricInterpretation for correct coefficient selection).
        # Also pass transfer_syntax to help determine if pydicom already converted.
        pixel_array = dicom_color.convert_ybr_to_rgb(
            pixel_array,
            photometric_interpretation=photometric_interpretation,
            transfer_syntax=transfer_syntax,
        )
        return pixel_array, True
    if 'RGB' in pi_upper:
        # RGB images - check for JPEGLS-RGB channel order issues
        pixel_array = dicom_color.detect_and_fix_rgb_channel_order(
            pixel_array,
            photometric_interpretation=photometric_interpretation,
            transfer_syntax=transfer_syntax,
            dataset=dataset,
        )
    return pixel_array, False


def render_color_image(
    pixel_array: np.ndarray,
    window_center: float | None,
    window_width: float | None,
    rescale_slope: float | None,
    rescale_intercept: float | None,
    is_multi_frame_color: bool,
) -> Image.Image | None:
    """Apply window/level (or normalize) to a color pixel array and build a PIL Image."""
    if is_multi_frame_color:
        # Handle multi-frame color: take first frame for now
        pixel_array = pixel_array[0]  # Shape becomes (height, width, channels)

    if window_center is not None and window_width is not None:
        # Use color-aware window/level
        processed_array = apply_color_window_level_luminance(
            pixel_array, window_center, window_width, rescale_slope, rescale_intercept
        )
    else:
        # No window/level, normalize each channel independently
        if len(pixel_array.shape) == 3:
            processed_array = normalize_channels_to_uint8(pixel_array)
        else:
            processed_array = normalize_to_uint8(pixel_array)

    try:
        if len(processed_array.shape) == 3 and processed_array.shape[2] == 3:
            # RGB color image
            return Image.fromarray(processed_array, mode='RGB')
        # Fallback to grayscale
        return Image.fromarray(processed_array, mode='L')
    except Exception as e:
        print(f"[PROCESSOR] Error converting color image to PIL Image: {e}")
        _logger.debug("%s", sanitized_format_exc())
        return None


def render_grayscale_image(
    pixel_array: np.ndarray,
    window_center: float | None,
    window_width: float | None,
    rescale_slope: float | None,
    rescale_intercept: float | None,
) -> Image.Image | None:
    """Apply window/level (or normalize) to a grayscale pixel array and build a PIL Image."""
    if window_center is not None and window_width is not None:
        processed_array = apply_window_level(
            pixel_array, window_center, window_width, rescale_slope, rescale_intercept
        )
    else:
        # No windowing, just normalize
        processed_array = normalize_to_uint8(pixel_array)

    # Handle 3D arrays (multi-frame grayscale)
    # Note: If this is reached, it means we're working with an original multi-frame dataset
    # that wasn't split by the organizer. Frame wrappers should already return 2D arrays.
    if len(processed_array.shape) == 3:
        # Take first frame (fallback - should not normally happen if organizer worked correctly)
        processed_array = processed_array[0]

    try:
        if len(processed_array.shape) == 2:
            # Grayscale
            return Image.fromarray(processed_array, mode='L')
        # RGB or other (shouldn't happen for grayscale, but handle gracefully)
        return Image.fromarray(processed_array)
    except Exception:
        _logger.debug("%s", sanitized_format_exc())
        return None
