"""
DICOM pixel array extraction and planar configuration handling.

This module extracts raw pixel arrays from DICOM datasets and handles
PlanarConfiguration (interleaved vs separate planes). Used by the
DICOMProcessor facade and by dicom_projections, dicom_pixel_stats, and
dicom_window_level.

Inputs:
    - pydicom Dataset

Outputs:
    - NumPy pixel arrays (or None on failure)

Requirements:
    - pydicom, numpy
    - core.multiframe_handler (is_multiframe)
"""

import numpy as np
from typing import Optional
from pydicom.dataset import Dataset

from core.multiframe_handler import is_multiframe

# Track files that have shown compression errors (suppress redundant messages)
_compression_error_files: set = set()


def handle_planar_configuration(pixel_array: np.ndarray, dataset: Dataset) -> np.ndarray:
    """
    Handle PlanarConfiguration tag (0028,0006).
    PlanarConfiguration = 0: interleaved (RGBRGB...)
    PlanarConfiguration = 1: separate planes (all R, then all G, then all B).

    Args:
        pixel_array: Pixel array from dataset
        dataset: pydicom Dataset

    Returns:
        Pixel array with interleaved channels (PlanarConfiguration = 0 format)
    """
    try:
        planar_config = 0
        if hasattr(dataset, 'PlanarConfiguration'):
            pc_value = dataset.PlanarConfiguration
            if isinstance(pc_value, (list, tuple)):
                planar_config = int(pc_value[0])
            else:
                planar_config = int(pc_value)

        if planar_config == 1:
            if len(pixel_array.shape) == 3:
                if pixel_array.shape[0] == 3:
                    pixel_array = np.transpose(pixel_array, (1, 2, 0))
            elif len(pixel_array.shape) == 4:
                if pixel_array.shape[1] == 3:
                    pixel_array = np.transpose(pixel_array, (0, 2, 3, 1))

        return pixel_array
    except Exception as e:
        print(f"[PLANAR] Error handling PlanarConfiguration: {e}")
        return pixel_array


def get_pixel_array(dataset: Dataset) -> Optional[np.ndarray]:
    """
    Extract pixel array from DICOM dataset.
    Handles frame wrappers for multi-frame and PlanarConfiguration.

    Args:
        dataset: pydicom Dataset (may be a frame wrapper for multi-frame files)

    Returns:
        NumPy array of pixel data, or None if extraction fails
    """
    try:
        if hasattr(dataset, '_frame_index') and hasattr(dataset, '_original_dataset'):
            pixel_array = dataset.pixel_array
            pixel_array = handle_planar_configuration(pixel_array, dataset)
            return pixel_array

        pixel_array = dataset.pixel_array
        pixel_array = handle_planar_configuration(pixel_array, dataset)

        if is_multiframe(dataset):
            if len(pixel_array.shape) == 3 or len(pixel_array.shape) == 4:
                return pixel_array

        return pixel_array

    except MemoryError as e:
        print(f"Memory error extracting pixel array: {e}")
        return None
    except Exception as e:
        error_msg = str(e)
        is_compression_error = (
            "pylibjpeg-libjpeg" in error_msg.lower() or
            "missing required dependencies" in error_msg.lower() or
            "unable to convert" in error_msg.lower() or
            "decode" in error_msg.lower()
        )
        if is_compression_error:
            file_path = None
            if hasattr(dataset, 'filename'):
                file_path = dataset.filename
            elif hasattr(dataset, 'file_path'):
                file_path = dataset.file_path
            if file_path and file_path not in _compression_error_files:
                _compression_error_files.add(file_path)
                print(f"[COMPRESSION ERROR] File: {file_path}")
                print(f"  Compressed DICOM pixel data cannot be decoded.")
                print(f"  Error: {error_msg[:200]}")
                print(f"  To decode compressed DICOM files, install optional dependencies:")
                print(f"    pip install pylibjpeg pyjpegls")
            elif not file_path:
                error_key = error_msg[:100]
                if error_key not in _compression_error_files:
                    _compression_error_files.add(error_key)
                    print(f"[COMPRESSION ERROR] Compressed DICOM pixel data cannot be decoded.")
                    print(f"  Error: {error_msg[:200]}")
        else:
            print(f"Error extracting pixel array: {e}")
        return None
