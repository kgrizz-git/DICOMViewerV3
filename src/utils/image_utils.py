"""
Image Utility Functions

This module provides utility functions for image format conversions and
manipulations used throughout the application.

Inputs:
    - PIL Image objects
    - NumPy arrays
    - Image format specifications
    
Outputs:
    - Converted images
    - Formatted image data
    
Requirements:
    - PIL/Pillow for image handling
    - numpy for array operations
"""

from typing import Optional
import numpy as np
from PIL import Image


def array_to_image(array: np.ndarray) -> Optional[Image.Image]:
    """
    Convert NumPy array to PIL Image.
    
    Args:
        array: NumPy array (2D for grayscale, 3D for RGB)
        
    Returns:
        PIL Image or None if conversion fails
    """
    try:
        # Ensure array is in correct format
        if array.dtype != np.uint8:
            # Normalize to 0-255
            if array.max() > array.min():
                array = ((array - array.min()) / (array.max() - array.min()) * 255.0).astype(np.uint8)
            else:
                array = np.zeros_like(array, dtype=np.uint8)
        
        if len(array.shape) == 2:
            # Grayscale
            return Image.fromarray(array, mode='L')
        elif len(array.shape) == 3:
            # RGB or other
            return Image.fromarray(array)
        else:
            return None
    except Exception as e:
        print(f"Error converting array to image: {e}")
        return None


def image_to_array(image: Image.Image) -> np.ndarray:
    """
    Convert PIL Image to NumPy array.
    
    Args:
        image: PIL Image
        
    Returns:
        NumPy array
    """
    return np.array(image)


def resize_image(image: Image.Image, width: int, height: int, 
                 keep_aspect: bool = True) -> Image.Image:
    """
    Resize image with optional aspect ratio preservation.
    
    Args:
        image: PIL Image to resize
        width: Target width
        height: Target height
        keep_aspect: If True, maintain aspect ratio
        
    Returns:
        Resized PIL Image
    """
    if keep_aspect:
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        return image
    else:
        return image.resize((width, height), Image.Resampling.LANCZOS)

