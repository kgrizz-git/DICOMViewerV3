"""
Multi-Frame DICOM Handler

This module handles detection and processing of multi-frame DICOM files.
Multi-frame DICOM files contain multiple image frames within a single DICOM instance,
commonly used in tomographic imaging (e.g., breast tomosynthesis).

Inputs:
    - pydicom.Dataset objects
    - Frame indices
    
Outputs:
    - Boolean flags for multi-frame detection
    - Frame counts
    - Individual frame pixel arrays
    - Frame dataset wrappers
    
Requirements:
    - pydicom library
    - numpy for array operations
"""

import numpy as np
from typing import Optional
import pydicom
from pydicom.dataset import Dataset


def is_multiframe(dataset: Dataset) -> bool:
    """
    Check if a DICOM dataset contains multiple frames.
    
    Args:
        dataset: pydicom Dataset
        
    Returns:
        True if dataset contains multiple frames, False otherwise
    """
    try:
        if hasattr(dataset, 'NumberOfFrames'):
            num_frames = dataset.NumberOfFrames
            # Handle both string and numeric values
            if isinstance(num_frames, str):
                try:
                    num_frames = int(num_frames)
                except (ValueError, TypeError):
                    return False
            return int(num_frames) > 1
        return False
    except Exception:
        return False


def get_frame_count(dataset: Dataset) -> int:
    """
    Get the number of frames in a DICOM dataset.
    
    Args:
        dataset: pydicom Dataset
        
    Returns:
        Number of frames (1 for single-frame, >1 for multi-frame)
    """
    try:
        if hasattr(dataset, 'NumberOfFrames'):
            num_frames = dataset.NumberOfFrames
            # Handle both string and numeric values
            if isinstance(num_frames, str):
                try:
                    num_frames = int(num_frames)
                except (ValueError, TypeError):
                    return 1
            return int(num_frames)
        return 1  # Default to single-frame if tag not present
    except Exception:
        return 1


def get_frame_pixel_array(dataset: Dataset, frame_index: int) -> Optional[np.ndarray]:
    """
    Extract pixel array for a specific frame from a multi-frame DICOM dataset.
    
    For single-frame datasets, returns the entire pixel array.
    For multi-frame datasets, returns the specified frame.
    
    Args:
        dataset: pydicom Dataset
        frame_index: Zero-based index of the frame to extract
        
    Returns:
        NumPy array for the specified frame, or None if extraction fails
    """
    # print(f"[FRAME] Extracting frame {frame_index}...")
    
    try:
        # Check if this is a multi-frame dataset before accessing pixel array
        if is_multiframe(dataset):
            num_frames = get_frame_count(dataset)
            # print(f"[FRAME] Multi-frame dataset, frames: {num_frames}")
            
            # Validate frame index
            if frame_index < 0 or frame_index >= num_frames:
                # print(f"[FRAME] Invalid frame index {frame_index} (valid range: 0-{num_frames-1})")
                return None
        
        # Get the full pixel array
        # For Enhanced Multi-frame, use cached pixel array if available (pre-loaded in dicom_loader)
        # This avoids the issue where accessing pixel_array later returns 2D instead of 3D
        if hasattr(dataset, '_cached_pixel_array'):
            pixel_array = dataset._cached_pixel_array
            # print(f"[FRAME] Using cached pixel array, shape: {pixel_array.shape}, dtype: {pixel_array.dtype}")
        else:
            # This may raise various exceptions from pydicom's pixel data processing
            # NOTE: For multi-frame, this loads ALL frames into memory
            pixel_array = dataset.pixel_array
            # print(f"[FRAME] Pixel array loaded, shape: {pixel_array.shape}, dtype: {pixel_array.dtype}")
        
        if pixel_array is None:
            # print(f"[FRAME] Pixel array is None")
            return None
        
        # Check for Enhanced Multi-frame issue
        if is_multiframe(dataset) and len(pixel_array.shape) == 2:
            # print(f"[FRAME] ⚠️  WARNING: Got 2D array for multi-frame file!")
            # print(f"[FRAME] This indicates the dataset is not fully loaded or is partially loaded.")
            # print(f"[FRAME] Has PerFrameFunctionalGroupsSequence: {hasattr(dataset, 'PerFrameFunctionalGroupsSequence')}")
            # print(f"[FRAME] Has PixelData attribute: {hasattr(dataset, 'PixelData')}")
            # print(f"[FRAME] Dataset type: {type(dataset)}")
            # For Enhanced Multi-frame that loaded as 2D, return the single frame for frame_index 0
            if frame_index == 0:
                # print(f"[FRAME] Returning 2D array as frame 0 (fallback)")
                return pixel_array
            else:
                # print(f"[FRAME] Cannot extract frame {frame_index} from 2D array")
                return None
        
        # Check if this is a multi-frame dataset
        if is_multiframe(dataset):
            # Extract the specific frame
            if len(pixel_array.shape) == 3:
                # Shape is (frames, rows, columns)
                try:
                    frame = pixel_array[frame_index]
                    # print(f"[FRAME] Extracted frame {frame_index}, shape: {frame.shape}")
                    return frame
                except (IndexError, ValueError) as e:
                    # print(f"[FRAME] Error extracting frame {frame_index} from pixel array: {e}")
                    return None
            elif len(pixel_array.shape) == 2:
                # Single frame, but NumberOfFrames tag says otherwise
                # Return the single frame if frame_index is 0
                if frame_index == 0:
                    # print(f"[FRAME] Returning single 2D array for frame 0")
                    return pixel_array
                else:
                    # print(f"[FRAME] 2D array but frame_index={frame_index} (not 0)")
                    return None
            else:
                # Unexpected shape
                print(f"Unexpected pixel array shape: {pixel_array.shape}")
                return None
        else:
            # Single-frame dataset
            # print(f"[FRAME] Single-frame dataset, returning full array")
            if frame_index == 0:
                return pixel_array
            return None
            
    except MemoryError as e:
        print(f"Memory error extracting frame {frame_index} from dataset: {e}")
        return None
    except ValueError as e:
        # Can occur with malformed pixel data or excess padding issues
        print(f"Value error extracting frame {frame_index} from dataset: {e}")
        return None
    except AttributeError as e:
        # Can occur if pixel_array property doesn't exist or is not accessible
        print(f"Attribute error extracting frame {frame_index} from dataset: {e}")
        return None
    except Exception as e:
        # Catch any other exceptions from pydicom's pixel data processing
        error_type = type(e).__name__
        print(f"Error ({error_type}) extracting frame {frame_index} from dataset: {e}")
        return None


def create_frame_dataset(dataset: Dataset, frame_index: int) -> Optional[Dataset]:
    """
    Create a frame-specific dataset wrapper for a multi-frame DICOM file.
    
    This creates a wrapper that references the original dataset but provides
    frame-specific pixel array access. The wrapper preserves all DICOM metadata
    from the original dataset.
    
    Args:
        dataset: Original pydicom Dataset (multi-frame)
        frame_index: Zero-based index of the frame
        
    Returns:
        Dataset wrapper with frame-specific pixel array, or None if creation fails
    """
    try:
        # Validate frame index
        if not is_multiframe(dataset):
            # Single-frame: return original dataset if frame_index is 0
            if frame_index == 0:
                return dataset
            return None
        
        num_frames = get_frame_count(dataset)
        if frame_index < 0 or frame_index >= num_frames:
            return None
        
        # Create a copy of the dataset for the frame
        # We'll use a custom class that overrides pixel_array access
        frame_dataset = FrameDatasetWrapper(dataset, frame_index)
        return frame_dataset
        
    except Exception as e:
        print(f"Error creating frame dataset for frame {frame_index}: {e}")
        return None


class FrameDatasetWrapper(Dataset):
    """
    Wrapper class for a specific frame within a multi-frame DICOM dataset.
    
    This class provides transparent access to DICOM metadata while ensuring
    that pixel_array access returns only the specified frame.
    """
    
    def __init__(self, original_dataset: Dataset, frame_index: int):
        """
        Initialize frame dataset wrapper.
        
        Args:
            original_dataset: Original multi-frame DICOM dataset
            frame_index: Zero-based index of the frame this wrapper represents
        """
        # Copy all attributes from original dataset
        # We need to copy the dataset structure but override pixel_array access
        super().__init__()
        
        # Store reference to original dataset and frame index
        self._original_dataset = original_dataset
        self._frame_index = frame_index
        
        # Copy all non-pixel data attributes
        # We'll copy tags that aren't pixel data related
        # Note: We need to deep copy to avoid modifying the original dataset
        import copy
        for tag in original_dataset:
            # Skip pixel data tag (7FE0,0010)
            if tag.tag != (0x7FE0, 0x0010):
                try:
                    # Deep copy to avoid shared references
                    self[tag.tag] = copy.deepcopy(original_dataset[tag.tag])
                except Exception:
                    pass
        
        # Update NumberOfFrames to 1 for this frame
        # (This is now safe since we deep copied the tags)
        if hasattr(self, 'NumberOfFrames'):
            self.NumberOfFrames = 1
    
    @property
    def pixel_array(self) -> np.ndarray:
        """
        Get pixel array for the specific frame.
        
        Returns:
            NumPy array for this frame only
            
        Raises:
            Various exceptions from pydicom pixel data processing may be raised
            and should be caught by callers
        """
        try:
            result = get_frame_pixel_array(self._original_dataset, self._frame_index)
            if result is None:
                # If extraction failed, raise an informative error
                raise ValueError(
                    f"Failed to extract frame {self._frame_index} from multi-frame dataset. "
                    f"This may be due to pixel data processing errors or invalid frame index."
                )
            return result
        except (MemoryError, ValueError, AttributeError) as e:
            # Re-raise these with context
            raise type(e)(f"Error accessing pixel array for frame {self._frame_index}: {str(e)}") from e
        except Exception as e:
            # Wrap other exceptions
            error_type = type(e).__name__
            raise RuntimeError(
                f"Unexpected error ({error_type}) accessing pixel array for frame {self._frame_index}: {str(e)}"
            ) from e
    
    def __getattr__(self, name: str):
        """
        Delegate attribute access to original dataset if not found in wrapper.
        
        This ensures all DICOM tags are accessible through the wrapper.
        """
        # Try to get from wrapper first
        if hasattr(super(), name):
            return getattr(super(), name)
        # Fall back to original dataset
        return getattr(self._original_dataset, name)

