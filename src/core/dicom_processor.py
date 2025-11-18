"""
DICOM Image Processor

This module handles image processing operations on DICOM data including:
- Window/level adjustment
- Image array extraction
- Average and Maximum Intensity Projections (AIP/MIP)
- Image format conversions

Inputs:
    - pydicom.Dataset objects
    - Window/level values
    - Slice indices for projections
    
Outputs:
    - Processed image arrays
    - PIL Image objects
    - NumPy arrays
    
Requirements:
    - pydicom library
    - numpy for array operations
    - PIL/Pillow for image handling
"""

import numpy as np
from typing import Optional, List, Tuple
from PIL import Image
import pydicom
from pydicom.dataset import Dataset

# Try to import pydicom's convert_color_space (available in pydicom 3.0+)
try:
    from pydicom.pixels import convert_color_space
    PYDICOM_CONVERT_AVAILABLE = True
except ImportError:
    PYDICOM_CONVERT_AVAILABLE = False
    convert_color_space = None
from core.multiframe_handler import get_frame_pixel_array, is_multiframe


class DICOMProcessor:
    """
    Processes DICOM image data for display and analysis.
    
    Handles:
    - Extracting pixel arrays from DICOM datasets
    - Applying window/level transformations
    - Creating intensity projections (AIP/MIP)
    - Converting to displayable formats
    """
    
    # Class-level set to track files that have shown compression errors (to suppress redundant messages)
    _compression_error_files: set = set()
    
    @staticmethod
    def get_rescale_parameters(dataset: Dataset) -> Tuple[Optional[float], Optional[float], Optional[str]]:
        """
        Extract rescale parameters from DICOM dataset.
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            Tuple of (rescale_slope, rescale_intercept, rescale_type) or (None, None, None) if not present
        """
        try:
            # RescaleSlope (0028,1053)
            rescale_slope = None
            if hasattr(dataset, 'RescaleSlope'):
                slope_value = dataset.RescaleSlope
                if isinstance(slope_value, (list, tuple)):
                    rescale_slope = float(slope_value[0])
                else:
                    rescale_slope = float(slope_value)
            
            # RescaleIntercept (0028,1502) - Note: tag is 0028,1502, not 0028,1052
            rescale_intercept = None
            if hasattr(dataset, 'RescaleIntercept'):
                intercept_value = dataset.RescaleIntercept
                if isinstance(intercept_value, (list, tuple)):
                    rescale_intercept = float(intercept_value[0])
                else:
                    rescale_intercept = float(intercept_value)
            
            # RescaleType (0028,1054)
            rescale_type = None
            if hasattr(dataset, 'RescaleType'):
                type_value = dataset.RescaleType
                if isinstance(type_value, (list, tuple)):
                    rescale_type = str(type_value[0]).strip()
                else:
                    rescale_type = str(type_value).strip()
                # Return None if empty string
                if not rescale_type:
                    rescale_type = None
            
            return rescale_slope, rescale_intercept, rescale_type
        except Exception as e:
            print(f"Error extracting rescale parameters: {e}")
            return None, None, None
    
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
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
                    jpeg2000_syntaxes = [
                        '1.2.840.10008.1.2.4.90',  # JPEG 2000 Image Compression (Lossless Only)
                        '1.2.840.10008.1.2.4.91',  # JPEG 2000 Image Compression
                    ]
                    
                    # Check if pydicom already converted YBR to RGB
                    # pydicom often auto-converts YBR to RGB but doesn't update PhotometricInterpretation tag
                    # This happens for JPEG2000-YBR_RCT and sometimes for uncompressed YBR_FULL
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
                            test_rgb = DICOMProcessor._convert_ybr_to_rgb_2d(test_sample, use_rct=use_rct_test)
                            
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
                                # print(f"[YBR] Data appears already RGB "
                                #       f"(Cb_var_ratio={cb_var_ratio:.2f}, Cr_var_ratio={cr_var_ratio:.2f}), skipping conversion")
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
                rgb_2d = DICOMProcessor._convert_ybr_to_rgb_2d(ybr_2d, use_rct=use_rct)
                # Reshape back to original: (frames, height, width, 3)
                rgb_array = rgb_2d.reshape(num_frames, height, width, 3)
            elif len(original_shape) == 3:
                # Single-frame YBR: (height, width, 3)
                rgb_array = DICOMProcessor._convert_ybr_to_rgb_2d(ybr_array, use_rct=use_rct)
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
    
    @staticmethod
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
                    # print(f"[JPEGLS-RGB] PlanarConfiguration = 1, channels already handled, trusting order")
                    return pixel_array
            
            # Analysis shows the algebraic relationship b-(r+g)/2 in JPEG2000 ≈ (g+b)/2-r in JPEGLS
            # holds better with original order. User confirmed: do not swap channels.
            # Return pixel array as-is without any channel swapping.
            # print(f"[JPEGLS-RGB] Keeping original channel order (no swap)")
            
            return pixel_array
            
        except Exception as e:
            print(f"[RGB/BGR] Error detecting/fixing channel order: {e}")
            import traceback
            traceback.print_exc()
            # Return original array on error
            return pixel_array
    
    @staticmethod
    def _convert_ybr_to_rgb_2d(ybr_array: np.ndarray, use_rct: bool = False) -> np.ndarray:
        """
        Convert 2D YBR array (height, width, 3) to RGB.
        
        Internal helper method for the actual conversion.
        
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
    
    @staticmethod
    def _handle_planar_configuration(pixel_array: np.ndarray, dataset: Dataset) -> np.ndarray:
        """
        Handle PlanarConfiguration tag (0028,0006).
        
        PlanarConfiguration = 0: Color channels are interleaved (RGBRGB...)
        PlanarConfiguration = 1: Color channels are stored in separate planes (all R, then all G, then all B)
        
        Args:
            pixel_array: Pixel array from dataset
            dataset: pydicom Dataset
            
        Returns:
            Pixel array with interleaved channels (PlanarConfiguration = 0 format)
        """
        try:
            # Check PlanarConfiguration tag (0028,0006)
            planar_config = 0  # Default to interleaved
            if hasattr(dataset, 'PlanarConfiguration'):
                pc_value = dataset.PlanarConfiguration
                if isinstance(pc_value, (list, tuple)):
                    planar_config = int(pc_value[0])
                else:
                    planar_config = int(pc_value)
            
            # If PlanarConfiguration = 1 (separate planes), convert to interleaved
            if planar_config == 1:
                # print(f"[PLANAR] PlanarConfiguration = 1 detected, converting separate planes to interleaved")
                
                # For separate planes, the array shape is typically (3, height, width) for single-frame
                # or (frames, 3, height, width) for multi-frame
                # We need to convert to (height, width, 3) or (frames, height, width, 3)
                
                if len(pixel_array.shape) == 3:
                    # Single-frame: shape is (3, height, width) or (height, width, 3)
                    # Check if first dimension is 3 (separate planes)
                    if pixel_array.shape[0] == 3:
                        # Separate planes: (3, height, width) -> (height, width, 3)
                        height, width = pixel_array.shape[1], pixel_array.shape[2]
                        # Transpose and reorder: (3, H, W) -> (H, W, 3)
                        pixel_array = np.transpose(pixel_array, (1, 2, 0))
                        print(f"[PLANAR] Converted from (3, {height}, {width}) to ({height}, {width}, 3)")
                elif len(pixel_array.shape) == 4:
                    # Multi-frame: shape could be (frames, 3, height, width) or (frames, height, width, 3)
                    # Check if second dimension is 3 (separate planes)
                    if pixel_array.shape[1] == 3:
                        # Separate planes: (frames, 3, height, width) -> (frames, height, width, 3)
                        num_frames, height, width = pixel_array.shape[0], pixel_array.shape[2], pixel_array.shape[3]
                        # Transpose and reorder: (F, 3, H, W) -> (F, H, W, 3)
                        pixel_array = np.transpose(pixel_array, (0, 2, 3, 1))
                        print(f"[PLANAR] Converted from ({num_frames}, 3, {height}, {width}) to ({num_frames}, {height}, {width}, 3)")
            
            return pixel_array
            
        except Exception as e:
            print(f"[PLANAR] Error handling PlanarConfiguration: {e}")
            # Return original array on error
            return pixel_array
    
    @staticmethod
    def get_pixel_array(dataset: Dataset) -> Optional[np.ndarray]:
        """
        Extract pixel array from DICOM dataset.
        
        For multi-frame datasets that have been wrapped (frame dataset wrappers),
        this will return the specific frame's pixel array.
        For original multi-frame datasets, this will return the full 3D array.
        
        Includes diagnostic logging for color space and transfer syntax information.
        Handles PlanarConfiguration to ensure channels are interleaved.
        
        Args:
            dataset: pydicom Dataset (may be a frame wrapper for multi-frame files)
            
        Returns:
            NumPy array of pixel data, or None if extraction fails
        """
        try:
            # Get transfer syntax for diagnostic logging
            transfer_syntax = None
            if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
            
            # Get photometric interpretation for diagnostic logging
            photometric_interpretation = None
            if hasattr(dataset, 'PhotometricInterpretation'):
                pi_value = dataset.PhotometricInterpretation
                if isinstance(pi_value, (list, tuple)):
                    photometric_interpretation = str(pi_value[0]).strip()
                else:
                    photometric_interpretation = str(pi_value).strip()
            
            # Get PlanarConfiguration for diagnostic logging
            planar_config = 0
            if hasattr(dataset, 'PlanarConfiguration'):
                pc_value = dataset.PlanarConfiguration
                if isinstance(pc_value, (list, tuple)):
                    planar_config = int(pc_value[0])
                else:
                    planar_config = int(pc_value)
            
            # Log diagnostic information
            # if transfer_syntax or photometric_interpretation:
            #     jpegls_syntaxes = [
            #         '1.2.840.10008.1.2.4.80',  # JPEG-LS Lossless
            #         '1.2.840.10008.1.2.4.81',  # JPEG-LS Lossy
            #     ]
            #     is_jpegls = transfer_syntax in jpegls_syntaxes if transfer_syntax else False
            #     log_msg = f"[PIXEL ARRAY] TransferSyntax: {transfer_syntax or 'Unknown'}, "
            #     log_msg += f"PhotometricInterpretation: {photometric_interpretation or 'Unknown'}, "
            #     log_msg += f"PlanarConfiguration: {planar_config}"
            #     if is_jpegls:
            #         log_msg += " (JPEGLS)"
            #     print(log_msg)
            
            # Check if this is a frame wrapper from a multi-frame file
            if hasattr(dataset, '_frame_index') and hasattr(dataset, '_original_dataset'):
                # This is a frame wrapper - use the pixel_array property which returns the specific frame
                pixel_array = dataset.pixel_array
                # Handle PlanarConfiguration
                pixel_array = DICOMProcessor._handle_planar_configuration(pixel_array, dataset)
                return pixel_array
            
            # Regular dataset (single-frame or original multi-frame)
            pixel_array = dataset.pixel_array
            
            # Handle PlanarConfiguration before returning
            pixel_array = DICOMProcessor._handle_planar_configuration(pixel_array, dataset)
            
            # If this is an original multi-frame dataset, return the full array
            # (The organizer should have split it into frame wrappers, but handle this case)
            # Multi-frame grayscale: shape (frames, rows, cols)
            # Multi-frame RGB: shape (frames, rows, cols, channels)
            if is_multiframe(dataset):
                if len(pixel_array.shape) == 3 or len(pixel_array.shape) == 4:
                    # This is a multi-frame array - return as-is
                    # Caller should extract specific frame if needed
                    return pixel_array
            
            return pixel_array
            
        except MemoryError as e:
            print(f"Memory error extracting pixel array: {e}")
            return None
        except Exception as e:
            error_msg = str(e)
            # Check if this is a compressed DICOM decoding error
            is_compression_error = (
                "pylibjpeg-libjpeg" in error_msg.lower() or
                "missing required dependencies" in error_msg.lower() or
                "unable to convert" in error_msg.lower() or
                "decode" in error_msg.lower()
            )
            
            if is_compression_error:
                # Get file path if available from dataset
                file_path = None
                if hasattr(dataset, 'filename'):
                    file_path = dataset.filename
                elif hasattr(dataset, 'file_path'):
                    file_path = dataset.file_path
                
                # Only show error message once per file
                if file_path and file_path not in DICOMProcessor._compression_error_files:
                    DICOMProcessor._compression_error_files.add(file_path)
                    print(f"[COMPRESSION ERROR] File: {file_path}")
                    print(f"  Compressed DICOM pixel data cannot be decoded.")
                    print(f"  Error: {error_msg[:200]}")  # Truncate long error messages
                    print(f"  To decode compressed DICOM files, install optional dependencies:")
                    print(f"    pip install pylibjpeg pyjpegls")
                    print(f"  Note: GDCM support may require additional system libraries")
                elif not file_path:
                    # If no file path available, show error once per unique error message
                    error_key = error_msg[:100]  # Use first 100 chars as key
                    if error_key not in DICOMProcessor._compression_error_files:
                        DICOMProcessor._compression_error_files.add(error_key)
                        print(f"[COMPRESSION ERROR] Compressed DICOM pixel data cannot be decoded.")
                        print(f"  Error: {error_msg[:200]}")
                        print(f"  Install optional dependencies: pip install pylibjpeg pyjpegls")
            else:
                print(f"Error extracting pixel array: {e}")
            return None
    
    @staticmethod
    def apply_window_level(pixel_array: np.ndarray, window_center: float, 
                          window_width: float, 
                          rescale_slope: Optional[float] = None,
                          rescale_intercept: Optional[float] = None) -> np.ndarray:
        """
        Apply window/level transformation to pixel array.
        
        Args:
            pixel_array: Input pixel array
            window_center: Window center value
            window_width: Window width value
            rescale_slope: Optional rescale slope from DICOM
            rescale_intercept: Optional rescale intercept from DICOM
            
        Returns:
            Windowed pixel array (0-255 uint8)
        """
        # Apply rescale if provided
        if rescale_slope is not None and rescale_intercept is not None:
            pixel_array = pixel_array * rescale_slope + rescale_intercept
        
        # Calculate window bounds
        window_min = window_center - window_width / 2.0
        window_max = window_center + window_width / 2.0
        
        # Clip values to window
        windowed = np.clip(pixel_array, window_min, window_max)
        
        # Normalize to 0-255
        if window_max > window_min:
            normalized = ((windowed - window_min) / (window_max - window_min) * 255.0).astype(np.uint8)
        else:
            normalized = np.zeros_like(windowed, dtype=np.uint8)
        
        return normalized
    
    @staticmethod
    def apply_color_window_level_luminance(pixel_array: np.ndarray, window_center: float,
                                          window_width: float,
                                          rescale_slope: Optional[float] = None,
                                          rescale_intercept: Optional[float] = None) -> np.ndarray:
        """
        Apply window/level to color images using luminance-based approach.
        
        Preserves color relationships while adjusting brightness/contrast by applying
        window/level to the luminance (brightness) component and scaling all color
        channels proportionally.
        
        Args:
            pixel_array: RGB array with shape (height, width, 3)
            window_center: Window center value
            window_width: Window width value
            rescale_slope: Optional rescale slope from DICOM
            rescale_intercept: Optional rescale intercept from DICOM
            
        Returns:
            Windowed RGB array (0-255 uint8)
        """
        try:
            # Ensure we have a 3-channel RGB array
            if len(pixel_array.shape) != 3 or pixel_array.shape[2] != 3:
                raise ValueError(f"Expected RGB array with shape (height, width, 3), got {pixel_array.shape}")
            
            # Convert to float32 for calculations
            rgb_float = pixel_array.astype(np.float32)
            
            # Apply rescale if provided
            if rescale_slope is not None and rescale_intercept is not None:
                rgb_float = rgb_float * rescale_slope + rescale_intercept
            
            # Convert RGB to luminance (Y in YCbCr or grayscale equivalent)
            # Formula: Y = 0.299*R + 0.587*G + 0.114*B (ITU-R BT.601)
            luminance = np.dot(rgb_float[..., :3], [0.299, 0.587, 0.114])
            
            # Apply window/level to luminance
            window_min = window_center - window_width / 2.0
            window_max = window_center + window_width / 2.0
            windowed_luminance = np.clip(luminance, window_min, window_max)
            
            # Normalize luminance to 0-255
            if window_max > window_min:
                normalized_luminance = ((windowed_luminance - window_min) / 
                                       (window_max - window_min) * 255.0)
            else:
                normalized_luminance = np.zeros_like(luminance)
            
            # Calculate scaling factor for each pixel
            # Avoid division by zero by adding small epsilon
            epsilon = 1e-10
            scale = normalized_luminance / (luminance + epsilon)
            
            # Handle edge case: if luminance is zero or very small, preserve original colors
            # but scale down brightness
            zero_luminance_mask = luminance < epsilon
            if np.any(zero_luminance_mask):
                # For zero luminance pixels, scale based on max channel value
                max_channel = np.max(rgb_float, axis=2)
                scale[zero_luminance_mask] = normalized_luminance[zero_luminance_mask] / (max_channel[zero_luminance_mask] + epsilon)
            
            # Apply scaling to each color channel while preserving ratios
            windowed_rgb = rgb_float * scale[..., np.newaxis]
            
            # Clip to valid range and convert to uint8
            windowed_rgb = np.clip(windowed_rgb, 0, 255).astype(np.uint8)
            
            return windowed_rgb
            
        except Exception as e:
            print(f"Error applying color window/level: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: return original array normalized
            if pixel_array.max() > pixel_array.min():
                normalized = ((pixel_array - pixel_array.min()) / 
                             (pixel_array.max() - pixel_array.min()) * 255.0).astype(np.uint8)
            else:
                normalized = pixel_array.astype(np.uint8)
            return normalized
    
    @staticmethod
    def convert_window_level_rescaled_to_raw(center: float, width: float, 
                                            slope: float, intercept: float) -> Tuple[float, float]:
        """
        Convert window/level values from rescaled to raw pixel values.
        
        Args:
            center: Window center in rescaled units
            width: Window width in rescaled units
            slope: Rescale slope
            intercept: Rescale intercept
            
        Returns:
            Tuple of (raw_center, raw_width)
        """
        # Formula: raw = (rescaled - intercept) / slope
        # For center: raw_center = (rescaled_center - intercept) / slope
        # For width: raw_width = rescaled_width / slope (width scales proportionally)
        if slope == 0.0:
            # Edge case: slope is zero, cannot convert
            return center, width
        
        raw_center = (center - intercept) / slope
        raw_width = width / slope
        
        return raw_center, raw_width
    
    @staticmethod
    def convert_window_level_raw_to_rescaled(center: float, width: float,
                                             slope: float, intercept: float) -> Tuple[float, float]:
        """
        Convert window/level values from raw to rescaled pixel values.
        
        Args:
            center: Window center in raw units
            width: Window width in raw units
            slope: Rescale slope
            intercept: Rescale intercept
            
        Returns:
            Tuple of (rescaled_center, rescaled_width)
        """
        # Formula: rescaled = raw * slope + intercept
        # For center: rescaled_center = raw_center * slope + intercept
        # For width: rescaled_width = raw_width * slope (width scales proportionally)
        rescaled_center = center * slope + intercept
        rescaled_width = width * slope
        
        return rescaled_center, rescaled_width
    
    @staticmethod
    def get_window_level_from_dataset(dataset: Dataset, 
                                     rescale_slope: Optional[float] = None,
                                     rescale_intercept: Optional[float] = None) -> Tuple[Optional[float], Optional[float], bool]:
        """
        Get window center and width from DICOM dataset.
        
        If rescale parameters are provided and window/level comes from DICOM metadata tags,
        assume the values are in rescaled units.
        
        Args:
            dataset: pydicom Dataset
            rescale_slope: Optional rescale slope
            rescale_intercept: Optional rescale intercept
            
        Returns:
            Tuple of (window_center, window_width, is_rescaled)
            is_rescaled is True if rescale params exist and window/level came from DICOM tags (not calculated)
        """
        try:
            window_center = None
            window_width = None
            from_dicom_tags = False  # Track if values came from DICOM tags
            
            # Try to get from WindowCenter tag
            if hasattr(dataset, 'WindowCenter'):
                wc = dataset.WindowCenter
                if isinstance(wc, (list, tuple)):
                    window_center = float(wc[0])
                else:
                    window_center = float(wc)
                from_dicom_tags = True
            
            # Try to get from WindowWidth tag
            if hasattr(dataset, 'WindowWidth'):
                ww = dataset.WindowWidth
                if isinstance(ww, (list, tuple)):
                    window_width = float(ww[0])
                else:
                    window_width = float(ww)
                from_dicom_tags = True
            
            # If not found, try to calculate from pixel data
            if window_center is None or window_width is None:
                pixel_array = DICOMProcessor.get_pixel_array(dataset)
                if pixel_array is not None:
                    pixel_min = float(np.min(pixel_array))
                    pixel_max = float(np.max(pixel_array))
                    if window_center is None:
                        # Calculate both median (excluding zeros) and midpoint, use the greater value
                        midpoint = (pixel_min + pixel_max) / 2.0
                        non_zero_values = pixel_array[pixel_array != 0]
                        if len(non_zero_values) > 0:
                            median = float(np.median(non_zero_values))
                            window_center = max(median, midpoint)
                        else:
                            # Fallback to midpoint if all values are zero
                            window_center = midpoint
                    if window_width is None:
                        window_width = pixel_max - pixel_min
                # Calculated values are not from DICOM tags, so not rescaled
                from_dicom_tags = False
            
            # Determine if values are in rescaled units
            # Only if values came from DICOM tags AND rescale parameters exist
            is_rescaled = (from_dicom_tags and 
                          rescale_slope is not None and 
                          rescale_intercept is not None and
                          rescale_slope != 0.0)
            
            return window_center, window_width, is_rescaled
        except Exception:
            return None, None, False
    
    @staticmethod
    def get_window_level_presets_from_dataset(dataset: Dataset, 
                                             rescale_slope: Optional[float] = None,
                                             rescale_intercept: Optional[float] = None) -> List[Tuple[float, float, bool, Optional[str]]]:
        """
        Get all window center and width presets from DICOM dataset.
        
        WindowWidth and WindowCenter can be single values or arrays. This method
        extracts all presets and returns them as a list.
        
        Supports multiple formats:
        - Backslash-separated strings: "C1\\C2" and "W1\\W2"
        - MultiValue objects from pydicom
        - Lists/tuples: [W1, W2] and [C1, C2]
        - Single values
        
        Args:
            dataset: pydicom Dataset
            rescale_slope: Optional rescale slope
            rescale_intercept: Optional rescale intercept
            
        Returns:
            List of tuples: (window_center, window_width, is_rescaled, preset_name)
            preset_name is None for first preset, or "Preset 2", "Preset 3", etc. for subsequent ones
            Returns empty list if no presets found
        """
        presets = []
        
        try:
            window_centers = []
            window_widths = []
            from_dicom_tags = False
            
            # Helper function to parse a value (handles multiple formats)
            def parse_window_value(value):
                """Parse window value from various formats."""
                if value is None:
                    return []
                
                # Check for MultiValue type (pydicom)
                try:
                    from pydicom.multival import MultiValue
                    if isinstance(value, MultiValue):
                        return [float(x) for x in value]
                except ImportError:
                    pass
                
                # Check for list/tuple
                if isinstance(value, (list, tuple)):
                    return [float(x) for x in value]
                
                # Check for backslash-separated string
                if isinstance(value, str):
                    if '\\' in value:
                        # Split on backslash and parse each value
                        parts = [p.strip() for p in value.split('\\') if p.strip()]
                        return [float(p) for p in parts]
                    # Check for bracket format [W1, W2] - strip brackets and split on comma
                    elif value.strip().startswith('[') and value.strip().endswith(']'):
                        inner = value.strip()[1:-1]
                        parts = [p.strip() for p in inner.split(',') if p.strip()]
                        return [float(p) for p in parts]
                    else:
                        # Single string value
                        return [float(value)]
                
                # Single numeric value
                return [float(value)]
            
            # Get WindowCenter values
            if hasattr(dataset, 'WindowCenter'):
                wc_raw = dataset.WindowCenter
                # print(f"[DEBUG-WL-PRESETS] WindowCenter found: type={type(wc_raw)}, value={wc_raw}")
                window_centers = parse_window_value(wc_raw)
                # print(f"[DEBUG-WL-PRESETS] WindowCenter parsed: {window_centers}")
                from_dicom_tags = True
            else:
                # print(f"[DEBUG-WL-PRESETS] WindowCenter tag not found")
                pass
            
            # Get WindowWidth values
            if hasattr(dataset, 'WindowWidth'):
                ww_raw = dataset.WindowWidth
                # print(f"[DEBUG-WL-PRESETS] WindowWidth found: type={type(ww_raw)}, value={ww_raw}")
                window_widths = parse_window_value(ww_raw)
                # print(f"[DEBUG-WL-PRESETS] WindowWidth parsed: {window_widths}")
                from_dicom_tags = True
            else:
                # print(f"[DEBUG-WL-PRESETS] WindowWidth tag not found")
                pass
            
            # Create presets from pairs
            # If one array is longer, use the last value for missing pairs
            num_presets = max(len(window_centers), len(window_widths))
            
            # print(f"[DEBUG-WL-PRESETS] Found {len(window_centers)} center(s) and {len(window_widths)} width(s), creating {num_presets} preset(s)")
            
            if num_presets == 0:
                # print(f"[DEBUG-WL-PRESETS] No presets to create, returning empty list")
                return presets
            
            for i in range(num_presets):
                # Get center value (use last value if index out of range)
                if i < len(window_centers):
                    wc = window_centers[i]
                elif window_centers:
                    wc = window_centers[-1]
                else:
                    continue  # Skip if no center values at all
                
                # Get width value (use last value if index out of range)
                if i < len(window_widths):
                    ww = window_widths[i]
                elif window_widths:
                    ww = window_widths[-1]
                else:
                    continue  # Skip if no width values at all
                
                # Determine preset name
                preset_name = None if i == 0 else f"Preset {i + 1}"
                
                # Determine if values are in rescaled units
                # Only if values came from DICOM tags AND rescale parameters exist
                is_rescaled = (from_dicom_tags and 
                              rescale_slope is not None and 
                              rescale_intercept is not None and
                              rescale_slope != 0.0)
                
                presets.append((wc, ww, is_rescaled, preset_name))
                # print(f"[DEBUG-WL-PRESETS] Created preset {i}: center={wc}, width={ww}, is_rescaled={is_rescaled}, name={preset_name}")
            
            # print(f"[DEBUG-WL-PRESETS] Returning {len(presets)} preset(s)")
            return presets
        except Exception as e:
            # print(f"[DEBUG-WL-PRESETS] Exception occurred: {type(e).__name__}: {e}")
            # import traceback
            # traceback.print_exc()
            return []
    
    @staticmethod
    def dataset_to_image(dataset: Dataset, window_center: Optional[float] = None,
                        window_width: Optional[float] = None, apply_rescale: bool = False) -> Optional[Image.Image]:
        """
        Convert DICOM dataset to PIL Image.
        
        Args:
            dataset: pydicom Dataset
            window_center: Optional window center (uses dataset default if None)
            window_width: Optional window width (uses dataset default if None)
            apply_rescale: If True, apply rescale slope/intercept in window/level calculation
            
        Returns:
            PIL Image or None if conversion fails
        """
        # print(f"[PROCESSOR] dataset_to_image called")
        # print(f"[PROCESSOR] Getting pixel array from dataset...")
        pixel_array = DICOMProcessor.get_pixel_array(dataset)
        if pixel_array is None:
            # print(f"[PROCESSOR] Pixel array is None, returning None")
            return None
        print(f"[PROCESSOR] Pixel array shape: {pixel_array.shape}, dtype: {pixel_array.dtype}")
        print(f"[PROCESSOR] Pixel array min: {pixel_array.min()}, max: {pixel_array.max()}, mean: {pixel_array.mean():.2f}")
        
        # Detect if this is a color image
        is_color, photometric_interpretation = DICOMProcessor.is_color_image(dataset)
        
        # Get transfer syntax for RGB/BGR detection
        transfer_syntax = None
        if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
            transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
        
        # Determine array dimensions
        # Multi-frame grayscale: shape = (frames, height, width)
        # Color single-frame: shape = (height, width, channels)
        # Multi-frame color: shape = (frames, height, width, channels)
        array_shape = pixel_array.shape
        is_multi_frame_color = False
        is_single_frame_color = False
        
        if is_color:
            if len(array_shape) == 4:
                # Multi-frame color: (frames, height, width, channels)
                is_multi_frame_color = True
            elif len(array_shape) == 3:
                # Could be single-frame color (height, width, channels) or multi-frame grayscale (frames, height, width)
                # Check if last dimension matches SamplesPerPixel
                samples_per_pixel = 1
                if hasattr(dataset, 'SamplesPerPixel'):
                    samples_value = dataset.SamplesPerPixel
                    if isinstance(samples_value, (list, tuple)):
                        samples_per_pixel = int(samples_value[0])
                    else:
                        samples_per_pixel = int(samples_value)
                
                if samples_per_pixel > 1 and array_shape[2] == samples_per_pixel:
                    # Single-frame color: (height, width, channels)
                    is_single_frame_color = True
                # Otherwise assume multi-frame grayscale (will be handled by existing logic)
        
        # Track whether window/level values were extracted from dataset or explicitly provided
        values_extracted_from_dataset = False
        is_rescaled = False
        
        # Get window/level from dataset if not provided
        if window_center is None or window_width is None:
            # Values are being extracted from the dataset
            values_extracted_from_dataset = True
            
            # Get rescale parameters for determining if window/level is in rescaled units
            # We need these even if apply_rescale is False, to check if window/level values are in rescaled units
            rescale_slope_for_wl, rescale_intercept_for_wl, _ = DICOMProcessor.get_rescale_parameters(dataset)
            
            ds_wc, ds_ww, is_rescaled = DICOMProcessor.get_window_level_from_dataset(
                dataset,
                rescale_slope=rescale_slope_for_wl,
                rescale_intercept=rescale_intercept_for_wl
            )
            if window_center is None:
                window_center = ds_wc
            if window_width is None:
                window_width = ds_ww
        
        # Get rescale parameters if apply_rescale is True (needed for pixel processing)
        rescale_slope = None
        rescale_intercept = None
        if apply_rescale:
            rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(dataset)
        
        # Convert window/level values ONLY if they were extracted from the dataset
        # Explicitly provided values are assumed to already be in the correct units for apply_rescale
        if window_center is not None and window_width is not None and values_extracted_from_dataset:
            # Get rescale parameters for conversion (if not already retrieved)
            if rescale_slope is None or rescale_intercept is None:
                rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(dataset)
            
            # Convert window/level values to match the apply_rescale setting
            if rescale_slope is not None and rescale_intercept is not None and rescale_slope != 0.0:
                if not apply_rescale and is_rescaled:
                    # Window/level is in rescaled units (HU), but we're not applying rescale to pixels
                    # Convert window/level from rescaled to raw pixel values
                    window_center, window_width = DICOMProcessor.convert_window_level_rescaled_to_raw(
                        window_center, window_width, rescale_slope, rescale_intercept
                    )
                elif apply_rescale and not is_rescaled:
                    # Window/level is in raw units, but we're applying rescale to pixels
                    # Convert window/level from raw to rescaled units
                    window_center, window_width = DICOMProcessor.convert_window_level_raw_to_rescaled(
                        window_center, window_width, rescale_slope, rescale_intercept
                    )
        
        # Convert YBR to RGB for color images before processing
        if is_color and (is_single_frame_color or is_multi_frame_color):
            if photometric_interpretation:
                pi_upper = photometric_interpretation.upper()
                ybr_types = ['YBR_FULL', 'YBR_FULL_422', 'YBR_ICT', 'YBR_RCT']
                if any(ybr_type in pi_upper for ybr_type in ybr_types):
                    # Convert YBR to RGB (pass PhotometricInterpretation for correct coefficient selection)
                    # Also pass transfer_syntax to help determine if pydicom already converted
                    pixel_array = DICOMProcessor.convert_ybr_to_rgb(
                        pixel_array, 
                        photometric_interpretation=photometric_interpretation,
                        transfer_syntax=transfer_syntax
                    )
                    # Update shape after conversion (in case it was multi-frame)
                    array_shape = pixel_array.shape
                    if len(array_shape) == 4:
                        is_multi_frame_color = True
                    elif len(array_shape) == 3 and array_shape[2] == 3:
                        is_single_frame_color = True
                elif 'RGB' in pi_upper:
                    # RGB images - check for JPEGLS-RGB channel order issues
                    pixel_array = DICOMProcessor.detect_and_fix_rgb_channel_order(
                        pixel_array, 
                        photometric_interpretation=photometric_interpretation,
                        transfer_syntax=transfer_syntax,
                        dataset=dataset
                    )
        
        # Apply window/level
        # print(f"[PROCESSOR] Applying window/level...")
        if is_color and (is_single_frame_color or is_multi_frame_color):
            # Handle multi-frame color: take first frame for now
            if is_multi_frame_color:
                pixel_array = pixel_array[0]  # Shape becomes (height, width, channels)
            
            # Color image processing
            if window_center is not None and window_width is not None:
                # Use color-aware window/level
                # print(f"[PROCESSOR] Applying color-aware window/level...")
                processed_array = DICOMProcessor.apply_color_window_level_luminance(
                    pixel_array, window_center, window_width,
                    rescale_slope, rescale_intercept
                )
            else:
                # No window/level, normalize each channel independently
                # print(f"[PROCESSOR] No window/level for color image, normalizing...")
                processed_array = pixel_array.astype(np.float32)
                if len(processed_array.shape) == 3:
                    # Color image: normalize each channel
                    for channel in range(processed_array.shape[2]):
                        channel_data = processed_array[:, :, channel]
                        if channel_data.max() > channel_data.min():
                            processed_array[:, :, channel] = ((channel_data - channel_data.min()) / 
                                                              (channel_data.max() - channel_data.min()) * 255.0)
                        else:
                            processed_array[:, :, channel] = np.zeros_like(channel_data)
                    processed_array = np.clip(processed_array, 0, 255).astype(np.uint8)
                else:
                    # Fallback: normalize entire array
                    if processed_array.max() > processed_array.min():
                        processed_array = ((processed_array - processed_array.min()) / 
                                         (processed_array.max() - processed_array.min()) * 255.0)
                    processed_array = processed_array.astype(np.uint8)
            
            # Convert color image to PIL Image
            try:
                if len(processed_array.shape) == 3 and processed_array.shape[2] == 3:
                    # RGB color image
                    image = Image.fromarray(processed_array, mode='RGB')
                    return image
                else:
                    # Fallback to grayscale
                    image = Image.fromarray(processed_array, mode='L')
                    return image
            except Exception as e:
                print(f"[PROCESSOR] Error converting color image to PIL Image: {e}")
                import traceback
                traceback.print_exc()
                return None
        else:
            # Grayscale image processing (existing logic)
            if window_center is not None and window_width is not None:
                # print(f"[PROCESSOR] Window center: {window_center}, width: {window_width}")
                processed_array = DICOMProcessor.apply_window_level(
                    pixel_array, window_center, window_width,
                    rescale_slope, rescale_intercept
                )
            else:
                # print(f"[PROCESSOR] No window/level, normalizing...")
                # No windowing, just normalize
                processed_array = pixel_array.astype(np.float32)
                if processed_array.max() > processed_array.min():
                    processed_array = ((processed_array - processed_array.min()) / 
                                     (processed_array.max() - processed_array.min()) * 255.0)
                processed_array = processed_array.astype(np.uint8)
            
            # print(f"[PROCESSOR] After window/level - shape: {processed_array.shape}, dtype: {processed_array.dtype}")
            
            # Handle 3D arrays (multi-frame grayscale)
            # Note: If this is reached, it means we're working with an original multi-frame dataset
            # that wasn't split by the organizer. Frame wrappers should already return 2D arrays.
            if len(processed_array.shape) == 3:
                # print(f"[PROCESSOR] WARNING: Got 3D array, taking first frame")
                # Take first frame (fallback - should not normally happen if organizer worked correctly)
                processed_array = processed_array[0]
            
            # Convert grayscale image to PIL Image
            # print(f"[PROCESSOR] Converting to PIL Image...")
            # print(f"[PROCESSOR] Array shape: {processed_array.shape}, dtype: {processed_array.dtype}, min: {processed_array.min()}, max: {processed_array.max()}")
            try:
                if len(processed_array.shape) == 2:
                    # Grayscale
                    # print(f"[PROCESSOR] Creating grayscale image...")
                    image = Image.fromarray(processed_array, mode='L')
                    # print(f"[PROCESSOR] PIL Image created successfully: {image.size}")
                    return image
                else:
                    # RGB or other (shouldn't happen for grayscale, but handle gracefully)
                    # print(f"[PROCESSOR] Creating RGB/other image...")
                    image = Image.fromarray(processed_array)
                    # print(f"[PROCESSOR] PIL Image created successfully: {image.size}")
                    return image
            except Exception as e:
                # print(f"[PROCESSOR] Error converting to PIL Image: {e}")
                import traceback
                traceback.print_exc()
                return None
    
    @staticmethod
    def average_intensity_projection(slices: List[Dataset]) -> Optional[np.ndarray]:
        """
        Create Average Intensity Projection (AIP) from multiple slices.
        
        Args:
            slices: List of pydicom Dataset objects
            
        Returns:
            NumPy array representing the AIP, or None if failed
        """
        if not slices:
            return None
        
        pixel_arrays = []
        for dataset in slices:
            pixel_array = DICOMProcessor.get_pixel_array(dataset)
            if pixel_array is not None:
                pixel_arrays.append(pixel_array)
        
        if not pixel_arrays:
            return None
        
        # Stack arrays and compute mean
        stacked = np.stack(pixel_arrays, axis=0)
        aip = np.mean(stacked, axis=0).astype(np.float32)
        
        return aip
    
    @staticmethod
    def maximum_intensity_projection(slices: List[Dataset]) -> Optional[np.ndarray]:
        """
        Create Maximum Intensity Projection (MIP) from multiple slices.
        
        Args:
            slices: List of pydicom Dataset objects
            
        Returns:
            NumPy array representing the MIP, or None if failed
        """
        if not slices:
            return None
        
        pixel_arrays = []
        for dataset in slices:
            pixel_array = DICOMProcessor.get_pixel_array(dataset)
            if pixel_array is not None:
                pixel_arrays.append(pixel_array)
        
        if not pixel_arrays:
            return None
        
        # Stack arrays and compute maximum
        stacked = np.stack(pixel_arrays, axis=0)
        mip = np.max(stacked, axis=0).astype(np.float32)
        
        return mip
    
    @staticmethod
    def get_pixel_value_range(dataset: Dataset, apply_rescale: bool = False) -> Tuple[Optional[float], Optional[float]]:
        """
        Get the minimum and maximum pixel values from a DICOM dataset.
        Optionally applies rescale slope and intercept if present.
        
        Args:
            dataset: pydicom Dataset
            apply_rescale: If True, apply rescale slope/intercept if present
            
        Returns:
            Tuple of (min_value, max_value) or (None, None) if extraction fails
        """
        try:
            pixel_array = DICOMProcessor.get_pixel_array(dataset)
            if pixel_array is None:
                return None, None
            
            # Apply rescale if requested and parameters exist
            if apply_rescale:
                rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(dataset)
                if rescale_slope is not None and rescale_intercept is not None:
                    pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
            
            pixel_min = float(np.min(pixel_array))
            pixel_max = float(np.max(pixel_array))
            
            return pixel_min, pixel_max
        except MemoryError as e:
            print(f"Memory error calculating pixel value range: {e}")
            return None, None
        except (ValueError, AttributeError, RuntimeError) as e:
            # Pixel array access errors
            print(f"Error calculating pixel value range: {e}")
            return None, None
        except Exception as e:
            error_type = type(e).__name__
            print(f"Error calculating pixel value range ({error_type}): {e}")
            return None, None
    
    @staticmethod
    def get_series_pixel_value_range(datasets: List[Dataset], apply_rescale: bool = False) -> Tuple[Optional[float], Optional[float]]:
        """
        Get the minimum and maximum pixel values across an entire series.
        Optionally applies rescale slope and intercept if present.
        
        Args:
            datasets: List of pydicom Dataset objects for the series
            apply_rescale: If True, apply rescale slope/intercept if present
            
        Returns:
            Tuple of (min_value, max_value) across all slices, or (None, None) if extraction fails
        """
        if not datasets:
            return None, None
        
        try:
            series_min = None
            series_max = None
            successful_datasets = 0
            
            for dataset in datasets:
                try:
                    pixel_array = DICOMProcessor.get_pixel_array(dataset)
                    if pixel_array is None:
                        continue
                    
                    # Apply rescale if requested and parameters exist
                    if apply_rescale:
                        rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(dataset)
                        if rescale_slope is not None and rescale_intercept is not None:
                            pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
                    
                    slice_min = float(np.min(pixel_array))
                    slice_max = float(np.max(pixel_array))
                    
                    if series_min is None or slice_min < series_min:
                        series_min = slice_min
                    if series_max is None or slice_max > series_max:
                        series_max = slice_max
                    
                    successful_datasets += 1
                    
                except MemoryError as e:
                    # Memory error for this dataset - log and continue with others
                    print(f"Memory error processing dataset in series pixel range calculation: {e}")
                    continue
                except (ValueError, AttributeError, RuntimeError) as e:
                    # Pixel array access errors - log and continue with others
                    print(f"Error processing dataset in series pixel range calculation: {e}")
                    continue
                except Exception as e:
                    # Other unexpected errors - log and continue
                    error_type = type(e).__name__
                    print(f"Unexpected error ({error_type}) processing dataset in series pixel range calculation: {e}")
                    continue
            
            # Only return values if we successfully processed at least one dataset
            if successful_datasets > 0:
                return series_min, series_max
            else:
                print("Failed to process any datasets in series pixel range calculation")
                return None, None
                
        except Exception as e:
            error_type = type(e).__name__
            print(f"Error calculating series pixel value range ({error_type}): {e}")
            return None, None
    
    @staticmethod
    def get_series_pixel_median(datasets: List[Dataset], apply_rescale: bool = False) -> Optional[float]:
        """
        Get the median pixel value across an entire series.
        Optionally applies rescale slope and intercept if present.
        
        Args:
            datasets: List of pydicom Dataset objects for the series
            apply_rescale: If True, apply rescale slope/intercept if present
            
        Returns:
            Median pixel value across all slices, or None if extraction fails
        """
        if not datasets:
            return None
        
        try:
            all_pixel_values = []
            successful_datasets = 0
            
            for dataset in datasets:
                try:
                    pixel_array = DICOMProcessor.get_pixel_array(dataset)
                    if pixel_array is None:
                        continue
                    
                    # Apply rescale if requested and parameters exist
                    if apply_rescale:
                        rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(dataset)
                        if rescale_slope is not None and rescale_intercept is not None:
                            pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
                    
                    # Flatten array and add to collection
                    # For very large series, we could sample, but for now collect all values
                    flat_values = pixel_array.flatten()
                    all_pixel_values.append(flat_values)
                    
                    successful_datasets += 1
                    
                except MemoryError as e:
                    # Memory error for this dataset - log and continue with others
                    print(f"Memory error processing dataset in series pixel median calculation: {e}")
                    continue
                except (ValueError, AttributeError, RuntimeError) as e:
                    # Pixel array access errors - log and continue with others
                    print(f"Error processing dataset in series pixel median calculation: {e}")
                    continue
                except Exception as e:
                    # Other unexpected errors - log and continue
                    error_type = type(e).__name__
                    print(f"Unexpected error ({error_type}) processing dataset in series pixel median calculation: {e}")
                    continue
            
            # Only calculate median if we successfully processed at least one dataset
            if successful_datasets > 0 and all_pixel_values:
                # Concatenate all pixel values from all slices
                combined_values = np.concatenate(all_pixel_values)
                # Exclude zero values from median calculation
                non_zero_values = combined_values[combined_values != 0]
                if len(non_zero_values) > 0:
                    median_value = float(np.median(non_zero_values))
                    return median_value
                else:
                    # Fallback: if all values are zero, return None
                    return None
            else:
                print("Failed to process any datasets in series pixel median calculation")
                return None
                
        except MemoryError as e:
            print(f"Memory error calculating series pixel median: {e}")
            return None
        except Exception as e:
            error_type = type(e).__name__
            print(f"Error calculating series pixel median ({error_type}): {e}")
            return None

