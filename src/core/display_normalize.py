"""
Min/max normalization of pixel arrays to uint8.

Split out of ``dicom_image_render`` so the LUT engine can match the no-window
display path without importing the renderer (that import cycle includes the LUT).

Inputs:
    - Numeric NumPy arrays, including flat arrays and per-channel color arrays

Outputs:
    - uint8 arrays in ``[0, 255]``. A flat range becomes zeros.

Requirements:
    - numpy
"""

from __future__ import annotations

import numpy as np


def normalize_to_uint8(array: np.ndarray) -> np.ndarray:
    """Normalize an array to 0-255 uint8. Flat arrays (max == min) are zeroed."""
    processed = array.astype(np.float32)
    if processed.max() > processed.min():
        processed = ((processed - processed.min()) / (processed.max() - processed.min()) * 255.0)
    else:
        processed = np.zeros_like(processed)
    return processed.astype(np.uint8)
