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
from pydicom.dataset import Dataset

from utils.privacy.console import print_redacted

_DISPLAY_NONE_RESCALE_TYPES = {"UNSPECIFIED", "US"}


def _normalize_explicit_rescale_type(rescale_type: str | None) -> str | None:
    """
    Normalize an explicit RescaleType value for viewer/display semantics.

    DICOM-defined placeholders such as ``UNSPECIFIED`` / ``US`` should not be
    surfaced as user-facing units, so treat them as missing and let inference
    decide whether a meaningful unit like ``HU`` applies.
    """
    if rescale_type is None:
        return None
    normalized = str(rescale_type).strip()
    if not normalized:
        return None
    if normalized.upper() in _DISPLAY_NONE_RESCALE_TYPES:
        return None
    return normalized


def _get_pixel_value_transformation_item(dataset: Dataset) -> Dataset | None:
    """Return the first PixelValueTransformationSequence item from functional groups, or None."""
    for seq_attr in ("SharedFunctionalGroupsSequence", "PerFrameFunctionalGroupsSequence"):
        seq = getattr(dataset, seq_attr, None)
        if seq:
            item = seq[0]
            pvt = getattr(item, "PixelValueTransformationSequence", None)
            if pvt:
                return pvt[0]
    return None


def get_rescale_parameters(dataset: Dataset) -> tuple[float | None, float | None, str | None]:
    """
    Extract rescale parameters from DICOM dataset.

    Checks top-level tags first, then falls back to
    PixelValueTransformationSequence inside SharedFunctionalGroupsSequence
    or PerFrameFunctionalGroupsSequence (Enhanced Multi-frame IODs).

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

        # Fallback: Enhanced Multi-frame functional groups
        if rescale_slope is None and rescale_intercept is None:
            pvt = _get_pixel_value_transformation_item(dataset)
            if pvt is not None:
                slope_val = getattr(pvt, "RescaleSlope", None)
                if slope_val is not None:
                    rescale_slope = float(slope_val[0]) if isinstance(slope_val, (list, tuple)) else float(slope_val)
                intercept_val = getattr(pvt, "RescaleIntercept", None)
                if intercept_val is not None:
                    rescale_intercept = float(intercept_val[0]) if isinstance(intercept_val, (list, tuple)) else float(intercept_val)
                if rescale_type is None:
                    type_val = getattr(pvt, "RescaleType", None)
                    if type_val is not None:
                        rescale_type = str(type_val[0]).strip() if isinstance(type_val, (list, tuple)) else str(type_val).strip()
                        if not rescale_type:
                            rescale_type = None

        return rescale_slope, rescale_intercept, rescale_type
    except Exception as e:
        print_redacted(f"Error extracting rescale parameters: {e}")
        return None, None, None


def infer_rescale_type(
    dataset: Dataset,
    rescale_slope: float | None,
    rescale_intercept: float | None,
    rescale_type: str | None
) -> str | None:
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
    normalized_rescale_type = _normalize_explicit_rescale_type(rescale_type)
    if normalized_rescale_type:
        return normalized_rescale_type

    modality = getattr(dataset, "Modality", None)
    if modality and str(modality).upper() == "CT":
        if rescale_slope is not None and rescale_intercept is not None:
            # CT storage values are almost always mapped to linear attenuation
            # (HU) via RescaleSlope / RescaleIntercept; many vendors omit
            # RescaleType or use intercepts other than -1024.
            return "HU"

    return None
