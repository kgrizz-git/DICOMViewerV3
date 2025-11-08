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


def calculate_pixel_spacing_from_fov(dataset: Dataset) -> Optional[Tuple[float, float]]:
    """
    Calculate pixel spacing from Field of View and matrix size.
    Handles MR-specific logic with Percent Phase Field of View.
    
    Args:
        dataset: pydicom Dataset
        
    Returns:
        Tuple of (row_spacing, column_spacing) in mm, or None if not available
    """
    try:
        # Get matrix size (Rows and Columns)
        rows = None
        columns = None
        if hasattr(dataset, 'Rows'):
            rows = int(dataset.Rows)
        if hasattr(dataset, 'Columns'):
            columns = int(dataset.Columns)
        
        if rows is None or columns is None or rows <= 0 or columns <= 0:
            return None
        
        # Get modality to determine calculation method
        modality = None
        if hasattr(dataset, 'Modality'):
            modality = str(dataset.Modality).upper()
        
        # For MR modality, use special logic
        if modality == 'MR':
            # Get Reconstruction Diameter (0018,1100)
            recon_diameter = None
            if hasattr(dataset, 'ReconstructionDiameter'):
                recon_diameter = float(dataset.ReconstructionDiameter)
            
            if recon_diameter is None or recon_diameter <= 0:
                return None
            
            # Get Percent Phase Field of View (0018,0094)
            percent_phase_fov = None
            if hasattr(dataset, 'PercentPhaseFieldOfView'):
                percent_phase_fov = float(dataset.PercentPhaseFieldOfView)
            
            # Get In Plane Phase Encoding Direction (0018,1312)
            phase_encoding_direction = None
            if hasattr(dataset, 'InPlanePhaseEncodingDirection'):
                phase_encoding_direction = str(dataset.InPlanePhaseEncodingDirection).upper()
            
            # Calculate FOV for each direction
            if percent_phase_fov is not None and phase_encoding_direction is not None:
                # Phase encoding direction FOV = Reconstruction Diameter * (Percent Phase FOV / 100)
                phase_fov = recon_diameter * (percent_phase_fov / 100.0)
                # Frequency encoding direction FOV = Reconstruction Diameter
                freq_fov = recon_diameter
                
                if phase_encoding_direction == 'ROW':
                    # Phase encoding is in row direction
                    row_spacing = phase_fov / rows
                    col_spacing = freq_fov / columns
                elif phase_encoding_direction == 'COL':
                    # Phase encoding is in column direction
                    row_spacing = freq_fov / rows
                    col_spacing = phase_fov / columns
                else:
                    # Unknown direction, use reconstruction diameter for both
                    row_spacing = recon_diameter / rows
                    col_spacing = recon_diameter / columns
            else:
                # Missing phase encoding info, use reconstruction diameter for both
                row_spacing = recon_diameter / rows
                col_spacing = recon_diameter / columns
            
            return (row_spacing, col_spacing)
        
        # For other modalities, try Field of View or Reconstruction Diameter
        fov = None
        if hasattr(dataset, 'FieldOfView'):
            fov = float(dataset.FieldOfView)
        elif hasattr(dataset, 'ReconstructionDiameter'):
            fov = float(dataset.ReconstructionDiameter)
        
        if fov is not None and fov > 0:
            # Use same FOV for both directions
            row_spacing = fov / rows
            col_spacing = fov / columns
            return (row_spacing, col_spacing)
    
    except Exception:
        pass
    
    return None


def get_pixel_spacing(dataset: Dataset) -> Optional[Tuple[float, float]]:
    """
    Get pixel spacing from DICOM dataset.
    Checks multiple sources in priority order:
    1. Pixel Spacing (0028,0030) - primary
    2. Imager Pixel Spacing (0018,1164) - fallback
    3. Calculate from Field of View + Matrix Size - fallback
    
    Args:
        dataset: pydicom Dataset
        
    Returns:
        Tuple of (row_spacing, column_spacing) in mm, or None if not available
    """
    # Priority 1: Pixel Spacing (0028,0030)
    try:
        if hasattr(dataset, 'PixelSpacing'):
            pixel_spacing = dataset.PixelSpacing
            if pixel_spacing and len(pixel_spacing) >= 2:
                row_spacing = float(pixel_spacing[0])
                col_spacing = float(pixel_spacing[1])
                if row_spacing > 0 and col_spacing > 0:
                    return (row_spacing, col_spacing)
    except Exception:
        pass
    
    # Priority 2: Imager Pixel Spacing (0018,1164)
    try:
        if hasattr(dataset, 'ImagerPixelSpacing'):
            imager_pixel_spacing = dataset.ImagerPixelSpacing
            if imager_pixel_spacing and len(imager_pixel_spacing) >= 2:
                row_spacing = float(imager_pixel_spacing[0])
                col_spacing = float(imager_pixel_spacing[1])
                if row_spacing > 0 and col_spacing > 0:
                    return (row_spacing, col_spacing)
    except Exception:
        pass
    
    # Priority 3: Calculate from Field of View + Matrix Size
    fov_spacing = calculate_pixel_spacing_from_fov(dataset)
    if fov_spacing is not None:
        return fov_spacing
    
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

