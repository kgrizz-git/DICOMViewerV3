"""
Shared int16 + RescaleSlope/Intercept encoding for derived DICOM exports.

Used by the MPR and projection exporters. Qt-free.
"""

from __future__ import annotations

import numpy as np


def float_to_int16_with_rescale(
    physical: np.ndarray, p_min: float, p_max: float
) -> tuple[np.ndarray, float, float]:
    """Map physical float values to int16 with DICOM rescale tags."""
    if p_max <= p_min:
        slope = 1.0
        intercept = float(p_min)
        stored = np.zeros_like(physical, dtype=np.int16)
        return stored, slope, intercept
    slope = (p_max - p_min) / 65535.0
    intercept = p_min + 32768.0 * slope
    stored = np.clip(
        np.rint((physical.astype(np.float64) - intercept) / slope),
        -32768,
        32767,
    ).astype(np.int16)
    return stored, float(slope), float(intercept)
