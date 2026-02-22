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

# Phase 2 refactor: domain modules (facade delegates to these)
from core import dicom_rescale
from core import dicom_color
from core import dicom_pixel_array
from core import dicom_window_level
from core import dicom_projections
from core import dicom_pixel_stats


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
        """Extract rescale parameters from DICOM dataset. Delegates to core.dicom_rescale."""
        return dicom_rescale.get_rescale_parameters(dataset)

    @staticmethod
    def infer_rescale_type(
        dataset: Dataset,
        rescale_slope: Optional[float],
        rescale_intercept: Optional[float],
        rescale_type: Optional[str]
    ) -> Optional[str]:
        """Infer rescale type when RescaleType tag is missing. Delegates to core.dicom_rescale."""
        return dicom_rescale.infer_rescale_type(dataset, rescale_slope, rescale_intercept, rescale_type)

    @staticmethod
    def is_color_image(dataset: Dataset) -> Tuple[bool, Optional[str]]:
        """Detect if a DICOM image is a color image. Delegates to core.dicom_color."""
        return dicom_color.is_color_image(dataset)

    @staticmethod
    def _is_already_rgb(pixel_array: np.ndarray) -> bool:
        """Check if pixel array appears to already be RGB (not YBR). Delegates to core.dicom_color."""
        return dicom_color._is_already_rgb(pixel_array)

    @staticmethod
    def convert_ybr_to_rgb(ybr_array: np.ndarray,
                          photometric_interpretation: Optional[str] = None,
                          transfer_syntax: Optional[str] = None) -> np.ndarray:
        """Convert YBR color space array to RGB. Delegates to core.dicom_color."""
        return dicom_color.convert_ybr_to_rgb(ybr_array, photometric_interpretation, transfer_syntax)

    @staticmethod
    def detect_and_fix_rgb_channel_order(pixel_array: np.ndarray,
                                         photometric_interpretation: Optional[str] = None,
                                         transfer_syntax: Optional[str] = None,
                                         dataset: Optional[Dataset] = None) -> np.ndarray:
        """Detect and fix RGB/BGR channel order issues. Delegates to core.dicom_color."""
        return dicom_color.detect_and_fix_rgb_channel_order(
            pixel_array, photometric_interpretation, transfer_syntax, dataset
        )

    @staticmethod
    def _convert_ybr_to_rgb_2d(ybr_array: np.ndarray, use_rct: bool = False) -> np.ndarray:
        """Convert 2D YBR array to RGB. Delegates to core.dicom_color."""
        return dicom_color._convert_ybr_to_rgb_2d(ybr_array, use_rct)

    @staticmethod
    def _handle_planar_configuration(pixel_array: np.ndarray, dataset: Dataset) -> np.ndarray:
        """Handle PlanarConfiguration tag. Delegates to core.dicom_pixel_array."""
        return dicom_pixel_array.handle_planar_configuration(pixel_array, dataset)

    @staticmethod
    def get_pixel_array(dataset: Dataset) -> Optional[np.ndarray]:
        """Extract pixel array from DICOM dataset. Delegates to core.dicom_pixel_array."""
        return dicom_pixel_array.get_pixel_array(dataset)

    @staticmethod
    def apply_window_level(pixel_array: np.ndarray, window_center: float,
                          window_width: float,
                          rescale_slope: Optional[float] = None,
                          rescale_intercept: Optional[float] = None) -> np.ndarray:
        """Apply window/level transformation to pixel array. Delegates to core.dicom_window_level."""
        return dicom_window_level.apply_window_level(
            pixel_array, window_center, window_width, rescale_slope, rescale_intercept
        )

    @staticmethod
    def apply_color_window_level_luminance(pixel_array: np.ndarray, window_center: float,
                                          window_width: float,
                                          rescale_slope: Optional[float] = None,
                                          rescale_intercept: Optional[float] = None) -> np.ndarray:
        """Apply window/level to color images (luminance-based). Delegates to core.dicom_window_level."""
        return dicom_window_level.apply_color_window_level_luminance(
            pixel_array, window_center, window_width, rescale_slope, rescale_intercept
        )

    @staticmethod
    def convert_window_level_rescaled_to_raw(center: float, width: float,
                                            slope: float, intercept: float) -> Tuple[float, float]:
        """Convert window/level from rescaled to raw. Delegates to core.dicom_window_level."""
        return dicom_window_level.convert_window_level_rescaled_to_raw(center, width, slope, intercept)

    @staticmethod
    def convert_window_level_raw_to_rescaled(center: float, width: float,
                                             slope: float, intercept: float) -> Tuple[float, float]:
        """Convert window/level from raw to rescaled. Delegates to core.dicom_window_level."""
        return dicom_window_level.convert_window_level_raw_to_rescaled(center, width, slope, intercept)

    @staticmethod
    def get_window_level_from_dataset(dataset: Dataset,
                                     rescale_slope: Optional[float] = None,
                                     rescale_intercept: Optional[float] = None) -> Tuple[Optional[float], Optional[float], bool]:
        """Get window center and width from DICOM dataset. Delegates to core.dicom_window_level."""
        return dicom_window_level.get_window_level_from_dataset(
            dataset, rescale_slope, rescale_intercept
        )

    @staticmethod
    def get_window_level_presets_from_dataset(dataset: Dataset,
                                             rescale_slope: Optional[float] = None,
                                             rescale_intercept: Optional[float] = None) -> List[Tuple[float, float, bool, Optional[str]]]:
        """Get all window/level presets from DICOM dataset. Delegates to core.dicom_window_level."""
        return dicom_window_level.get_window_level_presets_from_dataset(
            dataset, rescale_slope, rescale_intercept
        )

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
        # print(f"[PROCESSOR] Pixel array shape: {pixel_array.shape}, dtype: {pixel_array.dtype}")
        # print(f"[PROCESSOR] Pixel array min: {pixel_array.min()}, max: {pixel_array.max()}, mean: {pixel_array.mean():.2f}")
        
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
        
        # Handle PALETTE COLOR photometric interpretation
        # This must happen before YBR conversion and window/level application
        if photometric_interpretation:
            pi_upper = photometric_interpretation.upper()
            if 'PALETTE' in pi_upper and 'COLOR' in pi_upper:
                # PALETTE COLOR: Convert indexed pixel values to RGB using lookup tables
                try:
                    # Get palette lookup tables from dataset
                    red_lut = None
                    green_lut = None
                    blue_lut = None
                    
                    if hasattr(dataset, 'RedPaletteColorLookupTableDescriptor'):
                        # Get descriptor to determine LUT size and first value
                        red_desc = dataset.RedPaletteColorLookupTableDescriptor
                        if isinstance(red_desc, (list, tuple)) and len(red_desc) >= 3:
                            lut_size = int(red_desc[0])
                            first_value = int(red_desc[1]) if len(red_desc) > 1 else 0
                            bits_allocated = int(red_desc[2]) if len(red_desc) > 2 else 8
                        else:
                            lut_size = 256  # Default
                            first_value = 0
                            bits_allocated = 8
                        
                        if hasattr(dataset, 'RedPaletteColorLookupTableData'):
                            red_lut_data = dataset.RedPaletteColorLookupTableData
                            if isinstance(red_lut_data, bytes):
                                # Convert bytes to numpy array
                                if bits_allocated == 8:
                                    red_lut = np.frombuffer(red_lut_data, dtype=np.uint8)
                                else:
                                    red_lut = np.frombuffer(red_lut_data, dtype=np.uint16)
                            elif isinstance(red_lut_data, (list, tuple)):
                                red_lut = np.array(red_lut_data, dtype=np.uint16 if bits_allocated > 8 else np.uint8)
                    
                    if hasattr(dataset, 'GreenPaletteColorLookupTableDescriptor'):
                        green_desc = dataset.GreenPaletteColorLookupTableDescriptor
                        if isinstance(green_desc, (list, tuple)) and len(green_desc) >= 3:
                            lut_size = int(green_desc[0])
                            first_value = int(green_desc[1]) if len(green_desc) > 1 else 0
                            bits_allocated = int(green_desc[2]) if len(green_desc) > 2 else 8
                        else:
                            lut_size = 256
                            first_value = 0
                            bits_allocated = 8
                        
                        if hasattr(dataset, 'GreenPaletteColorLookupTableData'):
                            green_lut_data = dataset.GreenPaletteColorLookupTableData
                            if isinstance(green_lut_data, bytes):
                                if bits_allocated == 8:
                                    green_lut = np.frombuffer(green_lut_data, dtype=np.uint8)
                                else:
                                    green_lut = np.frombuffer(green_lut_data, dtype=np.uint16)
                            elif isinstance(green_lut_data, (list, tuple)):
                                green_lut = np.array(green_lut_data, dtype=np.uint16 if bits_allocated > 8 else np.uint8)
                    
                    if hasattr(dataset, 'BluePaletteColorLookupTableDescriptor'):
                        blue_desc = dataset.BluePaletteColorLookupTableDescriptor
                        if isinstance(blue_desc, (list, tuple)) and len(blue_desc) >= 3:
                            lut_size = int(blue_desc[0])
                            first_value = int(blue_desc[1]) if len(blue_desc) > 1 else 0
                            bits_allocated = int(blue_desc[2]) if len(blue_desc) > 2 else 8
                        else:
                            lut_size = 256
                            first_value = 0
                            bits_allocated = 8
                        
                        if hasattr(dataset, 'BluePaletteColorLookupTableData'):
                            blue_lut_data = dataset.BluePaletteColorLookupTableData
                            if isinstance(blue_lut_data, bytes):
                                if bits_allocated == 8:
                                    blue_lut = np.frombuffer(blue_lut_data, dtype=np.uint8)
                                else:
                                    blue_lut = np.frombuffer(blue_lut_data, dtype=np.uint16)
                            elif isinstance(blue_lut_data, (list, tuple)):
                                blue_lut = np.array(blue_lut_data, dtype=np.uint16 if bits_allocated > 8 else np.uint8)
                    
                    # Apply palette lookup if we have all three LUTs
                    if red_lut is not None and green_lut is not None and blue_lut is not None:
                        # Handle multi-frame palette color
                        if len(pixel_array.shape) == 3 and pixel_array.shape[2] == 1:
                            # Single-frame grayscale indexed: (height, width, 1) -> (height, width)
                            indexed_array = pixel_array[:, :, 0]
                        elif len(pixel_array.shape) == 2:
                            # Single-frame grayscale indexed: (height, width)
                            indexed_array = pixel_array
                        elif len(pixel_array.shape) == 4:
                            # Multi-frame: take first frame
                            indexed_array = pixel_array[0, :, :, 0] if pixel_array.shape[3] == 1 else pixel_array[0, :, :]
                        else:
                            indexed_array = pixel_array
                        
                        # Clamp indices to valid range
                        if first_value > 0:
                            indexed_array = indexed_array - first_value
                        indexed_array = np.clip(indexed_array, 0, len(red_lut) - 1)
                        
                        # Normalize LUTs to 0-255 range if they're 16-bit
                        if red_lut.dtype == np.uint16:
                            red_lut = (red_lut / 65535.0 * 255.0).astype(np.uint8)
                        if green_lut.dtype == np.uint16:
                            green_lut = (green_lut / 65535.0 * 255.0).astype(np.uint8)
                        if blue_lut.dtype == np.uint16:
                            blue_lut = (blue_lut / 65535.0 * 255.0).astype(np.uint8)
                        
                        # Apply lookup tables
                        red_channel = red_lut[indexed_array]
                        green_channel = green_lut[indexed_array]
                        blue_channel = blue_lut[indexed_array]
                        
                        # Combine into RGB array
                        if len(indexed_array.shape) == 2:
                            # Single-frame: (height, width) -> (height, width, 3)
                            rgb_array = np.stack([red_channel, green_channel, blue_channel], axis=2)
                        else:
                            # Multi-frame or other shape
                            rgb_array = np.stack([red_channel, green_channel, blue_channel], axis=-1)
                        
                        pixel_array = rgb_array
                        # Update flags to indicate this is now RGB color
                        array_shape = pixel_array.shape
                        if len(array_shape) == 4:
                            is_multi_frame_color = True
                        elif len(array_shape) == 3 and array_shape[2] == 3:
                            is_single_frame_color = True
                        is_color = True
                except Exception as e:
                    print(f"[PROCESSOR] Error applying palette color lookup: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fallback: treat as grayscale if palette lookup fails
                    pass
        
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
        """Create Average Intensity Projection from multiple slices. Delegates to core.dicom_projections."""
        return dicom_projections.average_intensity_projection(slices)

    @staticmethod
    def maximum_intensity_projection(slices: List[Dataset]) -> Optional[np.ndarray]:
        """Create Maximum Intensity Projection from multiple slices. Delegates to core.dicom_projections."""
        return dicom_projections.maximum_intensity_projection(slices)

    @staticmethod
    def minimum_intensity_projection(slices: List[Dataset]) -> Optional[np.ndarray]:
        """Create Minimum Intensity Projection from multiple slices. Delegates to core.dicom_projections."""
        return dicom_projections.minimum_intensity_projection(slices)

    @staticmethod
    def get_pixel_value_range(dataset: Dataset, apply_rescale: bool = False) -> Tuple[Optional[float], Optional[float]]:
        """Get min/max pixel values from a DICOM dataset. Delegates to core.dicom_pixel_stats."""
        return dicom_pixel_stats.get_pixel_value_range(dataset, apply_rescale)

    @staticmethod
    def get_series_pixel_value_range(datasets: List[Dataset], apply_rescale: bool = False) -> Tuple[Optional[float], Optional[float]]:
        """Get min/max pixel values across a series. Delegates to core.dicom_pixel_stats."""
        return dicom_pixel_stats.get_series_pixel_value_range(datasets, apply_rescale)

    @staticmethod
    def get_series_pixel_median(datasets: List[Dataset], apply_rescale: bool = False) -> Optional[float]:
        """Get median pixel value across a series. Delegates to core.dicom_pixel_stats."""
        return dicom_pixel_stats.get_series_pixel_median(datasets, apply_rescale)
