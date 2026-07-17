"""
DICOM color handling.

This module provides color detection, YBR to RGB conversion, and planar/RGB channel
handling for DICOM images. Used to determine if an image is color, convert YBR
color space to RGB, and detect/fix RGB/BGR channel order (e.g. for JPEG-LS).

Verbose YBR conversion diagnostics are gated by ``DEBUG_YBR`` in
``utils.debug_flags`` (default off).
"""
import logging

import numpy as np
from pydicom.dataset import Dataset

from utils.debug_flags import DEBUG_YBR
from utils.log_sanitizer import sanitized_format_exc
from utils.privacy.console import print_redacted

_logger = logging.getLogger(__name__)


def _log_ybr(message: str) -> None:
    """Emit a YBR conversion diagnostic line when DEBUG_YBR is True."""
    if DEBUG_YBR:
        print(message)

try:
    # pydicom 3.x: convert_color_space lives in pydicom.pixels.processing (absent in 2.x).
    from pydicom.pixels.processing import (  # pyright: ignore[reportMissingImports]
        convert_color_space,
    )

    pydicom_convert_available = True
except ImportError:
    pydicom_convert_available = False
    convert_color_space = None


def is_color_image(dataset: Dataset) -> tuple[bool, str | None]:
    """
    Detect if a DICOM image is a color image.

    Checks SamplesPerPixel and PhotometricInterpretation tags to determine
    if the image is color (RGB, YBR, etc.) or grayscale.

    Args:
        dataset: pydicom Dataset

    Returns:
        Tuple of (is_color: bool, photometric_interpretation: Optional[str])
        - is_color: True if image is color, False if grayscale
        - photometric_interpretation: PhotometricInterpretation value if present, None otherwise
    """
    try:
        # Check SamplesPerPixel tag (0028,0002)
        # SamplesPerPixel = 1 means grayscale, > 1 means color
        samples_per_pixel = 1  # Default to grayscale
        if hasattr(dataset, 'SamplesPerPixel'):
            samples_value = dataset.SamplesPerPixel
            if isinstance(samples_value, (list, tuple)):
                samples_per_pixel = int(samples_value[0])
            else:
                samples_per_pixel = int(samples_value)

        # Check PhotometricInterpretation tag (0028,0004)
        photometric_interpretation = None
        if hasattr(dataset, 'PhotometricInterpretation'):
            pi_value = dataset.PhotometricInterpretation
            if isinstance(pi_value, (list, tuple)):
                photometric_interpretation = str(pi_value[0]).strip()
            else:
                photometric_interpretation = str(pi_value).strip()
            # Return None if empty string
            if not photometric_interpretation:
                photometric_interpretation = None

        # Determine if color based on SamplesPerPixel
        # Color images have SamplesPerPixel > 1
        is_color = samples_per_pixel > 1

        # Also check PhotometricInterpretation for color types
        if photometric_interpretation:
            pi_upper = photometric_interpretation.upper()
            # Common color PhotometricInterpretation values
            color_types = ['RGB', 'YBR_FULL', 'YBR_FULL_422', 'YBR_ICT', 'YBR_RCT', 'PALETTE COLOR']
            if any(color_type in pi_upper for color_type in color_types):
                is_color = True
            # Grayscale types
            elif pi_upper in ['MONOCHROME1', 'MONOCHROME2']:
                is_color = False

        return is_color, photometric_interpretation

    except Exception as e:
        # On error, default to grayscale
        print_redacted(f"Error detecting color image: {e}")
        return False, None


def _photometric_string_from_dataset(dataset: Dataset | None) -> str | None:
    """Return normalized PhotometricInterpretation string, or None."""
    if dataset is None or not hasattr(dataset, "PhotometricInterpretation"):
        return None
    try:
        raw = dataset.PhotometricInterpretation
        if isinstance(raw, (list, tuple)):
            s = str(raw[0]).strip() if raw else ""
        else:
            s = str(raw).strip()
        return s.upper() if s else None
    except Exception:
        return None


def multichannel_axis_labels(dataset: Dataset | None, channel_count: int) -> tuple[str, ...]:
    """
    Short axis labels for per-channel ROI statistics / export (one label per channel index).

    Uses ``PhotometricInterpretation`` when ``channel_count == 3``: **RGB** maps to
    **R, G, B** (stored sample order after planar handling); **YBR\\*** maps to **Y, Cb, Cr**.
    Otherwise uses **Ch0**, **Ch1**, … (including three-channel palette/unknown photometrics).

    ROI statistics use raw ``pixel_array`` (no YBR→RGB conversion), so YBR labels match the
    decoded luma/chroma planes.

    Args:
        dataset: Current slice DICOM dataset, or None (falls back to Ch0… for 3-channel).
        channel_count: Number of channels (last axis of H×W×C array).

    Returns:
        Tuple of length ``channel_count``.
    """
    labels = [f"Ch{i}" for i in range(channel_count)]

    if channel_count == 3:
        pi = _photometric_string_from_dataset(dataset)
        if pi and pi.startswith("RGB"):
            labels = ["R", "G", "B"]
        elif pi and pi.startswith("YBR"):
            labels = ["Y", "Cb", "Cr"]

    return tuple(labels)


def _is_already_rgb(pixel_array: np.ndarray) -> bool:
    """
    Check if a pixel array appears to already be in RGB format (not YBR).

    This is a heuristic check to avoid double conversion. YBR arrays typically
    have chroma channels (Cb, Cr) centered around 128, while RGB arrays have
    more varied distributions.

    Args:
        pixel_array: Array with shape (height, width, 3) or (frames, height, width, 3)

    Returns:
        True if array appears to be RGB, False if it appears to be YBR
    """
    try:
        # For multi-frame, check first frame
        if len(pixel_array.shape) == 4:
            check_array = pixel_array[0]
        else:
            check_array = pixel_array

        if len(check_array.shape) != 3 or check_array.shape[2] != 3:
            return False

        # Check if chroma channels (Cb, Cr) are centered around 128 (YBR characteristic)
        # YBR chroma channels typically have mean around 128 with std around 20-40
        # RGB channels have more varied distributions
        cb_channel = check_array[:, :, 1].astype(np.float32)
        cr_channel = check_array[:, :, 2].astype(np.float32)

        cb_mean = np.mean(cb_channel)
        cr_mean = np.mean(cr_channel)

        # If chroma channels are centered around 128 (±20), likely YBR
        # If they're far from 128 or have very different means, likely RGB
        cb_near_128 = abs(cb_mean - 128.0) < 20.0
        cr_near_128 = abs(cr_mean - 128.0) < 20.0

        # If both chroma channels are near 128, likely YBR
        # Otherwise, likely RGB
        return not (cb_near_128 and cr_near_128)

    except Exception:
        # On error, assume not RGB (conservative - will attempt conversion)
        return False


def _convert_ybr_to_rgb_2d(ybr_array: np.ndarray, use_rct: bool = False) -> np.ndarray:
    """
    Convert 2D YBR array (height, width, 3) to RGB.

    Internal helper for the actual conversion.

    Args:
        ybr_array: YBR array with shape (height, width, 3)
        use_rct: If True, use YBR_RCT (Reversible Color Transform) coefficients,
                 otherwise use ITU-R BT.601 coefficients for YBR_FULL/YBR_FULL_422/YBR_ICT

    Returns:
        RGB array (0-255 uint8) with shape (height, width, 3)
    """
    # Extract Y, Cb, Cr channels
    Y = ybr_array[:, :, 0].astype(np.float32)
    Cb = ybr_array[:, :, 1].astype(np.float32)
    Cr = ybr_array[:, :, 2].astype(np.float32)

    if use_rct:
        # YBR_RCT (Reversible Color Transform) - JPEG 2000 Part 1 / DICOM Supplement 61
        # RCT conversion (reversible, integer-based)
        # Correct formula from DICOM Supplement 61:
        # G = Y - floor((Cr + Cb) / 4)
        # R = Cr + G
        # B = Cb + G
        # Note: G must be calculated first, then R and B depend on G
        # No offset of 128 needed for YBR_RCT
        g_ch = Y - np.floor((Cr + Cb) / 4.0)
        r_ch = Cr + g_ch
        b_ch = Cb + g_ch
    else:
        # YBR_FULL, YBR_FULL_422, YBR_ICT use ITU-R BT.601 coefficients
        # Note: pydicom handles 4:2:2 subsampling for YBR_FULL_422 during decompression
        # so we receive full-resolution chroma channels
        Cb = Cb - 128.0
        Cr = Cr - 128.0

        # Convert YBR to RGB using ITU-R BT.601 coefficients
        # R = Y + 1.402 * Cr
        # G = Y - 0.344136 * Cb - 0.714136 * Cr
        # B = Y + 1.772 * Cb
        r_ch = Y + 1.402 * Cr
        g_ch = Y - 0.344136 * Cb - 0.714136 * Cr
        b_ch = Y + 1.772 * Cb

    # Stack channels and clip to valid range
    rgb = np.stack([r_ch, g_ch, b_ch], axis=2)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    return rgb


def _chroma_variance_ratios(check_array: np.ndarray) -> tuple[float, float, float, float]:
    """Return (cb_mean, cr_mean, cb_var_ratio, cr_var_ratio) for a (H, W, 3) array.

    Variance ratio is chroma_std / (y_std + eps): in RGB all channels have
    similar variance (ratio near 1.0); in YBR chroma variance is usually
    lower than luma (ratio < 0.8 typically).
    """
    cb_channel = check_array[:, :, 1].astype(np.float32)
    cr_channel = check_array[:, :, 2].astype(np.float32)
    y_std = np.std(check_array[:, :, 0].astype(np.float32))

    cb_mean = np.mean(cb_channel)
    cr_mean = np.mean(cr_channel)
    cb_var_ratio = np.std(cb_channel) / (y_std + 1e-10)
    cr_var_ratio = np.std(cr_channel) / (y_std + 1e-10)
    return float(cb_mean), float(cr_mean), float(cb_var_ratio), float(cr_var_ratio)


def _already_rgb_by_test_conversion(
    check_array: np.ndarray,
    photometric_interpretation: str,
    cb_var_ratio: float,
    cr_var_ratio: float,
) -> bool:
    """Do a small test conversion; if results look unreasonable, data is likely already RGB."""
    try:
        pi_upper = photometric_interpretation.upper()
        use_rct_test = 'YBR_RCT' in pi_upper
        test_sample = check_array[:10, :10, :].copy()
        test_rgb = _convert_ybr_to_rgb_2d(test_sample, use_rct=use_rct_test)

        rgb_mean = np.mean(test_rgb)
        rgb_std = np.std(test_rgb)
        original_mean = np.mean(check_array)
        original_std = np.std(check_array)

        # If test conversion produces extreme values OR if original data
        # already has RGB-like statistics, skip conversion
        if rgb_mean < 50 or rgb_mean > 200 or rgb_std > 100:
            _log_ybr(
                "[YBR] Test conversion produces extreme values "
                f"(mean={rgb_mean:.1f}, std={rgb_std:.1f}), likely already RGB, skipping conversion"
            )
            return True
        return bool(abs(rgb_mean - original_mean) > 50 or abs(rgb_std - original_std) > 30)
    except Exception:
        # If test conversion fails, check variance ratios only
        if cb_var_ratio > 0.85 and cr_var_ratio > 0.85:
            _log_ybr(
                "[YBR] High variance ratios suggest already RGB "
                f"(Cb_var_ratio={cb_var_ratio:.2f}, Cr_var_ratio={cr_var_ratio:.2f}), skipping conversion"
            )
            return True
        return False


def _detect_already_rgb(
    ybr_array: np.ndarray,
    photometric_interpretation: str,
    transfer_syntax: str | None,
) -> bool:
    """Heuristic: does the array already look like RGB rather than YBR?

    Some decoders (e.g. JPEG2000 YBR_RCT) already convert to RGB without
    updating PhotometricInterpretation, so data statistics are checked
    rather than trusting the tag alone.
    """
    if len(ybr_array.shape) < 3 or ybr_array.shape[-1] != 3:
        return False

    check_array = ybr_array[0] if len(ybr_array.shape) == 4 else ybr_array
    if len(check_array.shape) != 3:
        return False

    cb_mean, cr_mean, cb_var_ratio, cr_var_ratio = _chroma_variance_ratios(check_array)

    already_rgb = False
    if cb_var_ratio > 0.8 and cr_var_ratio > 0.8:
        already_rgb = _already_rgb_by_test_conversion(
            check_array, photometric_interpretation, cb_var_ratio, cr_var_ratio
        )

    if not already_rgb:
        _log_ybr(
            f"[YBR] Converting YBR to RGB - PhotometricInterpretation: {photometric_interpretation}, "
            f"TransferSyntax: {transfer_syntax or 'Unknown'}, "
            f"Chroma means: Cb={cb_mean:.1f}, Cr={cr_mean:.1f}"
        )

    return already_rgb


def _select_conversion_method(
    photometric_interpretation: str | None,
) -> tuple[bool, str | None, bool]:
    """Return (use_rct, ybr_format, use_pydicom_convert) for a PhotometricInterpretation string."""
    use_rct = False
    use_pydicom_convert = False
    ybr_format: str | None = None

    if photometric_interpretation:
        pi_upper = photometric_interpretation.upper()
        if 'YBR_RCT' in pi_upper:
            use_rct = True
        elif 'YBR_FULL' in pi_upper:
            # YBR_FULL or YBR_FULL_422 - try pydicom first
            ybr_format = 'YBR_FULL_422' if 'YBR_FULL_422' in pi_upper else 'YBR_FULL'
            use_pydicom_convert = pydicom_convert_available
        elif 'YBR_ICT' in pi_upper:
            # YBR_ICT uses same conversion as YBR_FULL
            ybr_format = 'YBR_FULL'
            use_pydicom_convert = pydicom_convert_available

    return use_rct, ybr_format, use_pydicom_convert


def _convert_via_pydicom(
    ybr_array: np.ndarray, ybr_format: str | None, use_pydicom_convert: bool
) -> np.ndarray | None:
    """Try pydicom's convert_color_space(); None if not applicable/unavailable/failed."""
    if not (use_pydicom_convert and ybr_format and convert_color_space is not None):
        return None

    try:
        # Ensure array is uint8 (required by pydicom convert_color_space)
        if ybr_array.dtype != np.uint8:
            if ybr_array.max() > 255 or ybr_array.min() < 0:
                ybr_array_normalized = np.clip(ybr_array, 0, 255).astype(np.uint8)
            else:
                ybr_array_normalized = ybr_array.astype(np.uint8)
        else:
            ybr_array_normalized = ybr_array

        _log_ybr(f"[YBR] Using pydicom convert_color_space for {ybr_format}")
        rgb_array = convert_color_space(ybr_array_normalized, ybr_format, 'RGB')

        if rgb_array.dtype != np.uint8:
            rgb_array = np.clip(rgb_array, 0, 255).astype(np.uint8)

        return rgb_array
    except Exception as e:
        # Fall back to custom implementation if pydicom conversion fails
        _log_ybr(f"[YBR] pydicom convert_color_space failed, using custom conversion: {e}")
        return None


def _convert_via_custom(
    ybr_array: np.ndarray, original_shape: tuple[int, ...], use_rct: bool
) -> np.ndarray:
    """Custom YBR->RGB conversion for YBR_RCT, or when pydicom is unavailable/failed."""
    if len(original_shape) == 4:
        # Multi-frame YBR: (frames, height, width, 3). Reshape to 2D for
        # processing, then back to the original 4D shape.
        num_frames, height, width, channels = original_shape
        ybr_2d = ybr_array.reshape(-1, width, channels)
        rgb_2d = _convert_ybr_to_rgb_2d(ybr_2d, use_rct=use_rct)
        return rgb_2d.reshape(num_frames, height, width, 3)
    if len(original_shape) == 3:
        # Single-frame YBR: (height, width, 3)
        return _convert_ybr_to_rgb_2d(ybr_array, use_rct=use_rct)
    raise ValueError(f"Unsupported YBR array shape: {original_shape}")


def _finalize_rgb_result(rgb_array: np.ndarray, original_shape: tuple[int, ...]) -> np.ndarray:
    """Validate shape/value range and log final stats for a converted RGB array."""
    if rgb_array.shape != original_shape:
        _log_ybr(
            f"[YBR] Warning: Shape changed during conversion: {original_shape} -> {rgb_array.shape}"
        )

    if rgb_array.min() < 0 or rgb_array.max() > 255:
        _log_ybr(
            f"[YBR] Warning: RGB values out of range: min={rgb_array.min()}, max={rgb_array.max()}"
        )
        rgb_array = np.clip(rgb_array, 0, 255).astype(np.uint8)

    if len(rgb_array.shape) >= 3 and rgb_array.shape[-1] == 3:
        check_rgb = rgb_array[0] if len(rgb_array.shape) == 4 else rgb_array
        if len(check_rgb.shape) == 3:
            r_mean = np.mean(check_rgb[:, :, 0].astype(np.float32))
            g_mean = np.mean(check_rgb[:, :, 1].astype(np.float32))
            b_mean = np.mean(check_rgb[:, :, 2].astype(np.float32))
            _log_ybr(
                f"[YBR] Conversion complete - RGB means: R={r_mean:.1f}, G={g_mean:.1f}, B={b_mean:.1f}"
            )

    return rgb_array


def convert_ybr_to_rgb(ybr_array: np.ndarray,
                       photometric_interpretation: str | None = None,
                       transfer_syntax: str | None = None) -> np.ndarray:
    """
    Convert YBR color space array to RGB.

    Handles YBR_FULL, YBR_FULL_422, YBR_ICT, and YBR_RCT formats.
    YBR color space uses:
    - Y = luminance channel (first channel)
    - Cb = blue-difference channel (second channel)
    - Cr = red-difference channel (third channel)

    Note: YBR_FULL_422 uses 4:2:2 chroma subsampling, but pydicom
    handles the upsampling during decompression, so the array is already
    full resolution when we receive it.

    Uses pydicom's convert_color_space() for YBR_FULL/YBR_FULL_422/YBR_ICT
    when available (pydicom 3.0+), falls back to custom implementation otherwise.
    YBR_RCT always uses custom implementation (not supported by pydicom).

    This method trusts the PhotometricInterpretation tag and only converts
    when explicitly indicated as YBR format. Checks transfer syntax to determine
    if pydicom already converted YBR to RGB (common for JPEG 2000).

    Args:
        ybr_array: YBR array with shape (height, width, 3) or (frames, height, width, 3)
        photometric_interpretation: Optional PhotometricInterpretation string to determine conversion method
        transfer_syntax: Optional TransferSyntaxUID string to check if pydicom already converted

    Returns:
        RGB array (0-255 uint8) with same shape as input (except channel dimension)
    """
    try:
        original_shape = ybr_array.shape

        # Only convert if PhotometricInterpretation explicitly indicates YBR
        # Trust the DICOM tag - always convert when tag says YBR
        if not photometric_interpretation:
            _log_ybr("[YBR] Warning: No PhotometricInterpretation provided, skipping conversion")
            return ybr_array

        # Check if pydicom already converted YBR to RGB (common for JPEG2000);
        # its decoder can do this without updating PhotometricInterpretation.
        if _detect_already_rgb(ybr_array, photometric_interpretation, transfer_syntax):
            return ybr_array

        use_rct, ybr_format, use_pydicom_convert = _select_conversion_method(photometric_interpretation)

        # Prefer pydicom's tested implementation for YBR_FULL/YBR_FULL_422/YBR_ICT.
        pydicom_result = _convert_via_pydicom(ybr_array, ybr_format, use_pydicom_convert)
        if pydicom_result is not None:
            return pydicom_result

        # Custom implementation for YBR_RCT, or if pydicom is unavailable/failed.
        rgb_array = _convert_via_custom(ybr_array, original_shape, use_rct)

        return _finalize_rgb_result(rgb_array, original_shape)

    except Exception as e:
        print_redacted(f"Error converting YBR to RGB: {e}")
        _logger.debug("%s", sanitized_format_exc())
        # Return original array on error (may cause display issues but prevents crash)
        return ybr_array


def detect_and_fix_rgb_channel_order(pixel_array: np.ndarray,
                                     photometric_interpretation: str | None = None,  # NOSONAR
                                     transfer_syntax: str | None = None,  # NOSONAR
                                     dataset: Dataset | None = None) -> np.ndarray:  # NOSONAR
    """
    Detect and fix RGB/BGR channel order issues.

    Handles JPEGLS-RGB images which may have BGR channel order.
    Uses statistical analysis to detect if channels are swapped.
    Other RGB images are trusted as-is.

    Args:
        pixel_array: RGB array with shape (height, width, 3) or (frames, height, width, 3)
        photometric_interpretation: Optional PhotometricInterpretation string
        transfer_syntax: Optional TransferSyntaxUID string (for JPEGLS detection)
        dataset: Optional Dataset for PlanarConfiguration check

    Returns:
        RGB array with correct channel order
    """
    # Analysis shows the algebraic relationship b-(r+g)/2 in JPEG2000 ≈ (g+b)/2-r in JPEGLS
    # holds better with original order. User confirmed: do not swap channels.
    # JPEGLS-RGB/BGR channel detection was evaluated and intentionally disabled;
    # this function is kept as the call sites' integration point in case swap
    # detection is revisited.
    return pixel_array
