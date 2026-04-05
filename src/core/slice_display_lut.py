"""
Window/level rescale alignment for slice display.

Converts window center/width between raw and rescaled HU (or other) units when the
dataset tags are expressed in a different space than the viewer's current
raw-vs-rescaled setting.

Inputs: WC/WW, rescale flags, slope/intercept, DICOMProcessor.
Outputs: Adjusted (wc, ww) tuple.
Requirements: core.dicom_processor.DICOMProcessor conversion helpers.
"""

from typing import Optional, Tuple

from core.dicom_processor import DICOMProcessor


def apply_window_level_rescale_conversion(
    wc: float,
    ww: float,
    *,
    is_rescaled: bool,
    use_rescaled_values: bool,
    rescale_slope: Optional[float],
    rescale_intercept: Optional[float],
    dicom_processor: DICOMProcessor,
) -> Tuple[float, float]:
    """
    Align window center/width with the viewer's raw vs rescaled state.

    If dataset WL is already in the same space as the viewer, values are unchanged.
    """
    if is_rescaled and not use_rescaled_values:
        if (
            rescale_slope is not None
            and rescale_intercept is not None
            and rescale_slope != 0.0
        ):
            return dicom_processor.convert_window_level_rescaled_to_raw(
                wc, ww, rescale_slope, rescale_intercept
            )
    elif not is_rescaled and use_rescaled_values:
        if rescale_slope is not None and rescale_intercept is not None:
            return dicom_processor.convert_window_level_raw_to_rescaled(
                wc, ww, rescale_slope, rescale_intercept
            )
    return wc, ww
