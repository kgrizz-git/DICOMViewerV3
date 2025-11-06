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
    def get_window_level_from_dataset(dataset: Dataset) -> Tuple[Optional[float], Optional[float]]:
        """
        Get window center and width from DICOM dataset.
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            Tuple of (window_center, window_width) or (None, None)
        """
        try:
            window_center = None
            window_width = None
            
            # Try to get from WindowCenter tag
            if hasattr(dataset, 'WindowCenter'):
                wc = dataset.WindowCenter
                if isinstance(wc, (list, tuple)):
                    window_center = float(wc[0])
                else:
                    window_center = float(wc)
            
            # Try to get from WindowWidth tag
            if hasattr(dataset, 'WindowWidth'):
                ww = dataset.WindowWidth
                if isinstance(ww, (list, tuple)):
                    window_width = float(ww[0])
                else:
                    window_width = float(ww)
            
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
            
            return window_center, window_width
        except Exception:
            return None, None
    
    @staticmethod
    def dataset_to_image(dataset: Dataset, window_center: Optional[float] = None,
                        window_width: Optional[float] = None) -> Optional[Image.Image]:
        """
        Convert DICOM dataset to PIL Image.
        
        Args:
            dataset: pydicom Dataset
            window_center: Optional window center (uses dataset default if None)
            window_width: Optional window width (uses dataset default if None)
            
        Returns:
            PIL Image or None if conversion fails
        """
        pixel_array = DICOMProcessor.get_pixel_array(dataset)
        if pixel_array is None:
            return None
        
        # Get window/level from dataset if not provided
        if window_center is None or window_width is None:
            ds_wc, ds_ww = DICOMProcessor.get_window_level_from_dataset(dataset)
            if window_center is None:
                window_center = ds_wc
            if window_width is None:
                window_width = ds_ww
        
        # Get rescale parameters
        rescale_slope = getattr(dataset, 'RescaleSlope', None)
        rescale_intercept = getattr(dataset, 'RescaleIntercept', None)
        
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
    def get_pixel_value_range(dataset: Dataset) -> Tuple[Optional[float], Optional[float]]:
        """
        Get the minimum and maximum pixel values from a DICOM dataset.
        Considers rescale slope and intercept if present.
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            Tuple of (min_value, max_value) or (None, None) if extraction fails
        """
        try:
            pixel_array = DICOMProcessor.get_pixel_array(dataset)
            if pixel_array is None:
                return None, None
            
            # Get rescale parameters
            rescale_slope = getattr(dataset, 'RescaleSlope', None)
            rescale_intercept = getattr(dataset, 'RescaleIntercept', None)
            
            # Apply rescale if present
            if rescale_slope is not None and rescale_intercept is not None:
                pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
            
            pixel_min = float(np.min(pixel_array))
            pixel_max = float(np.max(pixel_array))
            
            return pixel_min, pixel_max
        except Exception as e:
            print(f"Error calculating pixel value range: {e}")
            return None, None

