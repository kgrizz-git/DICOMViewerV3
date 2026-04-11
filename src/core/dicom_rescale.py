"""
DICOM rescale parameters and type inference.

This module provides rescale slope, intercept, and type extraction from DICOM
datasets, and infers rescale type (e.g. HU for CT) when the tag is missing.

Inputs:
    - pydicom Dataset

Outputs:
    - (rescale_slope, rescale_intercept, rescale_type) tuples
    - Inferred rescale type string

Requirements:
    - pydicom
"""

from typing import Optional, Tuple
from pydicom.dataset import Dataset


def get_rescale_parameters(dataset: Dataset) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Extract rescale parameters from DICOM dataset.

    Args:
        dataset: pydicom Dataset

    Returns:
        Tuple of (rescale_slope, rescale_intercept, rescale_type) or (None, None, None) if not present
    """
    try:
        rescale_slope = None
        if hasattr(dataset, 'RescaleSlope'):
            slope_value = dataset.RescaleSlope
            if isinstance(slope_value, (list, tuple)):
                rescale_slope = float(slope_value[0])
            else:
                rescale_slope = float(slope_value)

        rescale_intercept = None
        if hasattr(dataset, 'RescaleIntercept'):
            intercept_value = dataset.RescaleIntercept
            if isinstance(intercept_value, (list, tuple)):
                rescale_intercept = float(intercept_value[0])
            else:
                rescale_intercept = float(intercept_value)

        rescale_type = None
        if hasattr(dataset, 'RescaleType'):
            type_value = dataset.RescaleType
            if isinstance(type_value, (list, tuple)):
                rescale_type = str(type_value[0]).strip()
            else:
                rescale_type = str(type_value).strip()
            if not rescale_type:
                rescale_type = None

        return rescale_slope, rescale_intercept, rescale_type
    except Exception as e:
        print(f"Error extracting rescale parameters: {e}")
        return None, None, None


def infer_rescale_type(
    dataset: Dataset,
    rescale_slope: Optional[float],
    rescale_intercept: Optional[float],
    rescale_type: Optional[str]
) -> Optional[str]:
    """
    Infer rescale type when RescaleType tag is missing.
    For CT images with both slope and intercept, returns "HU" (linear
    attenuation / Hounsfield storage convention).

    Args:
        dataset: pydicom Dataset
        rescale_slope: Rescale slope value
        rescale_intercept: Rescale intercept value
        rescale_type: Original rescale type from dataset (may be None)

    Returns:
        Inferred rescale type (e.g., "HU") or original rescale_type
    """
    if rescale_type:
        return rescale_type

    modality = getattr(dataset, "Modality", None)
    if modality and str(modality).upper() == "CT":
        if rescale_slope is not None and rescale_intercept is not None:
            # CT storage values are almost always mapped to linear attenuation
            # (HU) via RescaleSlope / RescaleIntercept; many vendors omit
            # RescaleType or use intercepts other than -1024.
            return "HU"

    return None
