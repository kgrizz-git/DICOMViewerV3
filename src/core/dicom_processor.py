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


class DICOMProcessor:
    """
    Processes DICOM image data for display and analysis.
    
    Handles:
    - Extracting pixel arrays from DICOM datasets
    - Applying window/level transformations
    - Creating intensity projections (AIP/MIP)
    - Converting to displayable formats
    """
    
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
    def get_pixel_array(dataset: Dataset) -> Optional[np.ndarray]:
        """
        Extract pixel array from DICOM dataset.
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            NumPy array of pixel data, or None if extraction fails
        """
        try:
            pixel_array = dataset.pixel_array
            return pixel_array
        except Exception as e:
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
                        window_center = (pixel_min + pixel_max) / 2.0
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
        pixel_array = DICOMProcessor.get_pixel_array(dataset)
        if pixel_array is None:
            return None
        
        # Get window/level from dataset if not provided
        if window_center is None or window_width is None:
            # Get rescale parameters if apply_rescale is True
            rescale_slope_for_wl = None
            rescale_intercept_for_wl = None
            if apply_rescale:
                rescale_slope_for_wl, rescale_intercept_for_wl, _ = DICOMProcessor.get_rescale_parameters(dataset)
            
            ds_wc, ds_ww, _ = DICOMProcessor.get_window_level_from_dataset(
                dataset,
                rescale_slope=rescale_slope_for_wl,
                rescale_intercept=rescale_intercept_for_wl
            )
            if window_center is None:
                window_center = ds_wc
            if window_width is None:
                window_width = ds_ww
        
        # Get rescale parameters if apply_rescale is True
        rescale_slope = None
        rescale_intercept = None
        if apply_rescale:
            rescale_slope, rescale_intercept, _ = DICOMProcessor.get_rescale_parameters(dataset)
        
        # Apply window/level
        if window_center is not None and window_width is not None:
            processed_array = DICOMProcessor.apply_window_level(
                pixel_array, window_center, window_width,
                rescale_slope, rescale_intercept
            )
        else:
            # No windowing, just normalize
            processed_array = pixel_array.astype(np.float32)
            if processed_array.max() > processed_array.min():
                processed_array = ((processed_array - processed_array.min()) / 
                                 (processed_array.max() - processed_array.min()) * 255.0)
            processed_array = processed_array.astype(np.uint8)
        
        # Handle 3D arrays (multi-frame)
        if len(processed_array.shape) == 3:
            # Take first frame
            processed_array = processed_array[0]
        
        # Convert to PIL Image
        try:
            if len(processed_array.shape) == 2:
                # Grayscale
                return Image.fromarray(processed_array, mode='L')
            else:
                # RGB or other
                return Image.fromarray(processed_array)
        except Exception as e:
            print(f"Error converting to PIL Image: {e}")
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
        except Exception as e:
            print(f"Error calculating pixel value range: {e}")
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
            
            for dataset in datasets:
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
            
            return series_min, series_max
        except Exception as e:
            print(f"Error calculating series pixel value range: {e}")
            return None, None

