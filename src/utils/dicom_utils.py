"""
DICOM Utility Functions

This module provides helper functions for DICOM operations including:
- Pixel spacing calculations
- Distance conversions
- Coordinate transformations
- Common DICOM tag lookups

Inputs:
    - pydicom.Dataset objects
    - Coordinate values
    - Distance measurements
    
Outputs:
    - Converted values
    - Calculated distances
    
Requirements:
    - pydicom library
    - numpy for calculations
"""

from typing import Optional, Tuple
import numpy as np
import pydicom
from pydicom.dataset import Dataset


def get_pixel_spacing(dataset: Dataset) -> Optional[Tuple[float, float]]:
    """
    Get pixel spacing from DICOM dataset.
    
    Args:
        dataset: pydicom Dataset
        
    Returns:
        Tuple of (row_spacing, column_spacing) in mm, or None if not available
    """
    try:
        if hasattr(dataset, 'PixelSpacing'):
            pixel_spacing = dataset.PixelSpacing
            if pixel_spacing and len(pixel_spacing) >= 2:
                return (float(pixel_spacing[0]), float(pixel_spacing[1]))
    except Exception:
        pass
    
    return None


def get_slice_thickness(dataset: Dataset) -> Optional[float]:
    """
    Get slice thickness from DICOM dataset.
    
    Args:
        dataset: pydicom Dataset
        
    Returns:
        Slice thickness in mm, or None if not available
    """
    try:
        if hasattr(dataset, 'SliceThickness'):
            return float(dataset.SliceThickness)
    except Exception:
        pass
    
    return None


def pixels_to_mm(pixels: float, pixel_spacing: Optional[Tuple[float, float]], 
                 dimension: int = 0) -> Optional[float]:
    """
    Convert pixel distance to millimeters.
    
    Args:
        pixels: Distance in pixels
        pixel_spacing: Tuple of (row_spacing, column_spacing) in mm
        dimension: 0 for row (Y), 1 for column (X)
        
    Returns:
        Distance in mm, or None if pixel spacing not available
    """
    if pixel_spacing is None:
        return None
    
    if dimension == 0:
        return pixels * pixel_spacing[0]  # Row spacing
    elif dimension == 1:
        return pixels * pixel_spacing[1]  # Column spacing
    else:
        return None


def mm_to_pixels(mm: float, pixel_spacing: Optional[Tuple[float, float]], 
                 dimension: int = 0) -> Optional[float]:
    """
    Convert millimeter distance to pixels.
    
    Args:
        mm: Distance in millimeters
        pixel_spacing: Tuple of (row_spacing, column_spacing) in mm
        dimension: 0 for row (Y), 1 for column (X)
        
    Returns:
        Distance in pixels, or None if pixel spacing not available
    """
    if pixel_spacing is None:
        return None
    
    if dimension == 0:
        return mm / pixel_spacing[0]  # Row spacing
    elif dimension == 1:
        return mm / pixel_spacing[1]  # Column spacing
    else:
        return None


def format_distance(pixels: float, pixel_spacing: Optional[Tuple[float, float]] = None,
                    dimension: int = 0) -> str:
    """
    Format distance measurement as string with appropriate units.
    
    Args:
        pixels: Distance in pixels
        pixel_spacing: Optional pixel spacing tuple
        dimension: 0 for row (Y), 1 for column (X)
        
    Returns:
        Formatted string (e.g., "10.5 mm" or "25 pixels")
    """
    if pixel_spacing is not None:
        mm = pixels_to_mm(pixels, pixel_spacing, dimension)
        if mm is not None:
            if mm >= 10:
                return f"{mm:.1f} mm"
            else:
                return f"{mm:.2f} mm"
    
    return f"{pixels:.1f} pixels"


def get_image_position(dataset: Dataset) -> Optional[np.ndarray]:
    """
    Get ImagePositionPatient from DICOM dataset.
    
    Args:
        dataset: pydicom Dataset
        
    Returns:
        NumPy array of [X, Y, Z] coordinates, or None if not available
    """
    try:
        if hasattr(dataset, 'ImagePositionPatient'):
            pos = dataset.ImagePositionPatient
            if pos and len(pos) >= 3:
                return np.array([float(pos[0]), float(pos[1]), float(pos[2])])
    except Exception:
        pass
    
    return None


def get_image_orientation(dataset: Dataset) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    """
    Get ImageOrientationPatient from DICOM dataset.
    
    Args:
        dataset: pydicom Dataset
        
    Returns:
        Tuple of (row_cosine, column_cosine) arrays, or None if not available
    """
    try:
        if hasattr(dataset, 'ImageOrientationPatient'):
            orient = dataset.ImageOrientationPatient
            if orient and len(orient) >= 6:
                row_cosine = np.array([float(orient[0]), float(orient[1]), float(orient[2])])
                col_cosine = np.array([float(orient[3]), float(orient[4]), float(orient[5])])
                return (row_cosine, col_cosine)
    except Exception:
        pass
    
    return None

