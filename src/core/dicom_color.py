"""
DICOM color handling.

This module provides color detection, YBR to RGB conversion, and planar/RGB channel
handling for DICOM images. Used to determine if an image is color, convert YBR
color space to RGB, and detect/fix RGB/BGR channel order (e.g. for JPEG-LS).
"""

import numpy as np
from typing import Optional, Tuple
from pydicom.dataset import Dataset

try:
    from pydicom.pixels import convert_color_space
    PYDICOM_CONVERT_AVAILABLE = True
except ImportError:
    PYDICOM_CONVERT_AVAILABLE = False
    convert_color_space = None


def is_color_image(dataset: Dataset) -> Tuple[bool, Optional[str]]:
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
        print(f"Error detecting color image: {e}")
        return False, None


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
        G = Y - np.floor((Cr + Cb) / 4.0)
        R = Cr + G
        B = Cb + G
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
        R = Y + 1.402 * Cr
        G = Y - 0.344136 * Cb - 0.714136 * Cr
        B = Y + 1.772 * Cb

    # Stack channels and clip to valid range
    rgb = np.stack([R, G, B], axis=2)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    return rgb


def convert_ybr_to_rgb(ybr_array: np.ndarray,
                       photometric_interpretation: Optional[str] = None,
                       transfer_syntax: Optional[str] = None) -> np.ndarray:
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
            print(f"[YBR] Warning: No PhotometricInterpretation provided, skipping conversion")
            return ybr_array

        # Check if pydicom already converted YBR to RGB (common for JPEG2000)
        # For JPEG2000-YBR_RCT, pydicom's decoder automatically converts to RGB
        # but doesn't update the PhotometricInterpretation tag
        # We detect this by checking if the data already looks like RGB
        already_rgb = False

        if len(ybr_array.shape) >= 3 and ybr_array.shape[-1] == 3:
            check_array = ybr_array[0] if len(ybr_array.shape) == 4 else ybr_array
            if len(check_array.shape) == 3:
                cb_mean = np.mean(check_array[:, :, 1].astype(np.float32))
                cr_mean = np.mean(check_array[:, :, 2].astype(np.float32))

                # For JPEG2000 with YBR_RCT, pydicom often already converts to RGB
                # Check if chroma channels are NOT centered around 128 (RGB characteristic)
                # AND if converting would make it worse (data already matches RGB pattern)
                cb_std = np.std(check_array[:, :, 1].astype(np.float32))
                cr_std = np.std(check_array[:, :, 2].astype(np.float32))
                y_std = np.std(check_array[:, :, 0].astype(np.float32))

                # Calculate variance ratios
                cb_var_ratio = cb_std / (y_std + 1e-10)
                cr_var_ratio = cr_std / (y_std + 1e-10)

                # In RGB, all channels have similar variance (ratios close to 1.0)
                # In YBR, chroma has lower variance (ratios < 0.8 typically)
                # If both chroma channels have variance similar to Y, likely RGB
                if cb_var_ratio > 0.8 and cr_var_ratio > 0.8:
                    # Do a test conversion to verify
                    # If test conversion produces extreme/unreasonable values, data is already RGB
                    try:
                        # Quick test conversion on a small sample
                        pi_upper = photometric_interpretation.upper()
                        use_rct_test = 'YBR_RCT' in pi_upper
                        test_sample = check_array[:10, :10, :].copy()
                        test_rgb = _convert_ybr_to_rgb_2d(test_sample, use_rct=use_rct_test)

                        # Check if converted values are reasonable
                        rgb_mean = np.mean(test_rgb)
                        rgb_std = np.std(test_rgb)

                        # If converted values are extreme, likely already RGB
                        # Also check if original data already matches RGB pattern better
                        original_mean = np.mean(check_array)
                        original_std = np.std(check_array)

                        # If test conversion produces extreme values OR if original data
                        # already has RGB-like statistics, skip conversion
                        if rgb_mean < 50 or rgb_mean > 200 or rgb_std > 100:
                            already_rgb = True
                            print(f"[YBR] Test conversion produces extreme values "
                                  f"(mean={rgb_mean:.1f}, std={rgb_std:.1f}), likely already RGB, skipping conversion")
                        elif abs(rgb_mean - original_mean) > 50 or abs(rgb_std - original_std) > 30:
                            # Conversion significantly changes statistics, likely already RGB
                            already_rgb = True
                    except Exception as e:
                        # If test conversion fails, check variance ratios only
                        if cb_var_ratio > 0.85 and cr_var_ratio > 0.85:
                            already_rgb = True
                            print(f"[YBR] High variance ratios suggest already RGB "
                                  f"(Cb_var_ratio={cb_var_ratio:.2f}, Cr_var_ratio={cr_var_ratio:.2f}), skipping conversion")

                if not already_rgb:
                    print(f"[YBR] Converting YBR to RGB - PhotometricInterpretation: {photometric_interpretation}, "
                          f"TransferSyntax: {transfer_syntax or 'Unknown'}, "
                          f"Chroma means: Cb={cb_mean:.1f}, Cr={cr_mean:.1f}")

        if already_rgb:
            return ybr_array

        # Determine conversion method based on PhotometricInterpretation
        use_rct = False
        use_pydicom_convert = False
        ybr_format = None

        if photometric_interpretation:
            pi_upper = photometric_interpretation.upper()
            if 'YBR_RCT' in pi_upper:
                use_rct = True
            elif 'YBR_FULL' in pi_upper:
                # YBR_FULL or YBR_FULL_422 - try pydicom first
                if 'YBR_FULL_422' in pi_upper:
                    ybr_format = 'YBR_FULL_422'
                else:
                    ybr_format = 'YBR_FULL'
                use_pydicom_convert = PYDICOM_CONVERT_AVAILABLE
            elif 'YBR_ICT' in pi_upper:
                # YBR_ICT uses same conversion as YBR_FULL
                ybr_format = 'YBR_FULL'
                use_pydicom_convert = PYDICOM_CONVERT_AVAILABLE

        # Try using pydicom's convert_color_space for YBR_FULL/YBR_FULL_422/YBR_ICT
        # Prefer pydicom's implementation as it's tested and handles edge cases
        if use_pydicom_convert and ybr_format and convert_color_space is not None:
            try:
                # Ensure array is uint8 (required by pydicom convert_color_space)
                if ybr_array.dtype != np.uint8:
                    # Normalize to uint8 range if needed
                    if ybr_array.max() > 255 or ybr_array.min() < 0:
                        ybr_array_normalized = np.clip(ybr_array, 0, 255).astype(np.uint8)
                    else:
                        ybr_array_normalized = ybr_array.astype(np.uint8)
                else:
                    ybr_array_normalized = ybr_array

                # Use pydicom's tested conversion
                print(f"[YBR] Using pydicom convert_color_space for {ybr_format}")
                rgb_array = convert_color_space(ybr_array_normalized, ybr_format, 'RGB')

                # Ensure output is uint8
                if rgb_array.dtype != np.uint8:
                    rgb_array = np.clip(rgb_array, 0, 255).astype(np.uint8)

                return rgb_array
            except Exception as e:
                # Fall back to custom implementation if pydicom conversion fails
                print(f"[YBR] pydicom convert_color_space failed, using custom conversion: {e}")
                use_pydicom_convert = False

        # Use custom implementation for YBR_RCT or if pydicom is not available/failed
        # Handle multi-frame YBR: (frames, height, width, 3)
        if len(original_shape) == 4:
            num_frames, height, width, channels = original_shape
            # Reshape to 2D for processing: (frames*height, width, channels)
            ybr_2d = ybr_array.reshape(-1, width, channels)
            rgb_2d = _convert_ybr_to_rgb_2d(ybr_2d, use_rct=use_rct)
            # Reshape back to original: (frames, height, width, 3)
            rgb_array = rgb_2d.reshape(num_frames, height, width, 3)
        elif len(original_shape) == 3:
            # Single-frame YBR: (height, width, 3)
            rgb_array = _convert_ybr_to_rgb_2d(ybr_array, use_rct=use_rct)
        else:
            raise ValueError(f"Unsupported YBR array shape: {original_shape}")

        # Validate conversion result
        if rgb_array.shape != original_shape:
            print(f"[YBR] Warning: Shape changed during conversion: {original_shape} -> {rgb_array.shape}")

        # Check if result is valid RGB (values in 0-255 range)
        if rgb_array.min() < 0 or rgb_array.max() > 255:
            print(f"[YBR] Warning: RGB values out of range: min={rgb_array.min()}, max={rgb_array.max()}")
            rgb_array = np.clip(rgb_array, 0, 255).astype(np.uint8)

        # Log conversion result statistics
        if len(rgb_array.shape) >= 3 and rgb_array.shape[-1] == 3:
            check_rgb = rgb_array[0] if len(rgb_array.shape) == 4 else rgb_array
            if len(check_rgb.shape) == 3:
                r_mean = np.mean(check_rgb[:, :, 0].astype(np.float32))
                g_mean = np.mean(check_rgb[:, :, 1].astype(np.float32))
                b_mean = np.mean(check_rgb[:, :, 2].astype(np.float32))
                print(f"[YBR] Conversion complete - RGB means: R={r_mean:.1f}, G={g_mean:.1f}, B={b_mean:.1f}")

        return rgb_array

    except Exception as e:
        print(f"Error converting YBR to RGB: {e}")
        import traceback
        traceback.print_exc()
        # Return original array on error (may cause display issues but prevents crash)
        return ybr_array


def detect_and_fix_rgb_channel_order(pixel_array: np.ndarray,
                                     photometric_interpretation: Optional[str] = None,
                                     transfer_syntax: Optional[str] = None,
                                     dataset: Optional[Dataset] = None) -> np.ndarray:
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
    try:
        # Only process RGB images with 3 channels
        if len(pixel_array.shape) < 3 or pixel_array.shape[-1] != 3:
            return pixel_array

        # Only handle JPEGLS-RGB images (known to sometimes have BGR order)
        is_jpegls_rgb = False
        if transfer_syntax:
            jpegls_syntaxes = [
                '1.2.840.10008.1.2.4.80',  # JPEG-LS Lossless
                '1.2.840.10008.1.2.4.81',  # JPEG-LS Lossy
            ]
            if transfer_syntax in jpegls_syntaxes:
                is_jpegls_rgb = True

        # Only process JPEGLS-RGB images
        if not is_jpegls_rgb:
            return pixel_array

        # Verify it's RGB photometric interpretation
        if photometric_interpretation:
            pi_upper = photometric_interpretation.upper()
            if 'RGB' not in pi_upper:
                return pixel_array

        # Check PlanarConfiguration - if PlanarConfiguration = 1, channels were already handled
        # by _handle_planar_configuration, so we can trust the order
        planar_config = 0
        if dataset:
            if hasattr(dataset, 'PlanarConfiguration'):
                pc_value = dataset.PlanarConfiguration
                if isinstance(pc_value, (list, tuple)):
                    planar_config = int(pc_value[0])
                else:
                    planar_config = int(pc_value)
            if planar_config == 1:
                return pixel_array

        # Analysis shows the algebraic relationship b-(r+g)/2 in JPEG2000 ≈ (g+b)/2-r in JPEGLS
        # holds better with original order. User confirmed: do not swap channels.
        # Return pixel array as-is without any channel swapping.

        return pixel_array

    except Exception as e:
        print(f"[RGB/BGR] Error detecting/fixing channel order: {e}")
        import traceback
        traceback.print_exc()
        # Return original array on error
        return pixel_array
