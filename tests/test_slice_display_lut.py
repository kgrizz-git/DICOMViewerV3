"""
Unit tests for core.slice_display_lut.apply_window_level_rescale_conversion.
"""

from core.dicom_processor import DICOMProcessor
from core.slice_display_lut import apply_window_level_rescale_conversion


def test_same_space_leaves_values_unchanged_rescaled_both_true():
    wc, ww = apply_window_level_rescale_conversion(
        40.0,
        400.0,
        is_rescaled=True,
        use_rescaled_values=True,
        rescale_slope=1.0,
        rescale_intercept=-1024.0,
        dicom_processor=DICOMProcessor,
    )
    assert (wc, ww) == (40.0, 400.0)


def test_same_space_leaves_values_unchanged_raw_both_false():
    wc, ww = apply_window_level_rescale_conversion(
        40.0,
        400.0,
        is_rescaled=False,
        use_rescaled_values=False,
        rescale_slope=1.0,
        rescale_intercept=-1024.0,
        dicom_processor=DICOMProcessor,
    )
    assert (wc, ww) == (40.0, 400.0)


def test_dataset_rescaled_viewer_wants_raw_converts_down():
    wc, ww = apply_window_level_rescale_conversion(
        40.0,
        400.0,
        is_rescaled=True,
        use_rescaled_values=False,
        rescale_slope=1.0,
        rescale_intercept=-1024.0,
        dicom_processor=DICOMProcessor,
    )
    expected = DICOMProcessor.convert_window_level_rescaled_to_raw(40.0, 400.0, 1.0, -1024.0)
    assert (wc, ww) == expected
    assert (wc, ww) != (40.0, 400.0)


def test_dataset_raw_viewer_wants_rescaled_converts_up():
    wc, ww = apply_window_level_rescale_conversion(
        40.0,
        400.0,
        is_rescaled=False,
        use_rescaled_values=True,
        rescale_slope=1.0,
        rescale_intercept=-1024.0,
        dicom_processor=DICOMProcessor,
    )
    expected = DICOMProcessor.convert_window_level_raw_to_rescaled(40.0, 400.0, 1.0, -1024.0)
    assert (wc, ww) == expected
    assert (wc, ww) != (40.0, 400.0)


def test_missing_rescale_params_leaves_values_unchanged():
    wc, ww = apply_window_level_rescale_conversion(
        40.0,
        400.0,
        is_rescaled=True,
        use_rescaled_values=False,
        rescale_slope=None,
        rescale_intercept=None,
        dicom_processor=DICOMProcessor,
    )
    assert (wc, ww) == (40.0, 400.0)


def test_zero_slope_leaves_values_unchanged():
    wc, ww = apply_window_level_rescale_conversion(
        40.0,
        400.0,
        is_rescaled=True,
        use_rescaled_values=False,
        rescale_slope=0.0,
        rescale_intercept=-1024.0,
        dicom_processor=DICOMProcessor,
    )
    assert (wc, ww) == (40.0, 400.0)


def test_raw_to_rescaled_missing_intercept_leaves_values_unchanged():
    wc, ww = apply_window_level_rescale_conversion(
        40.0,
        400.0,
        is_rescaled=False,
        use_rescaled_values=True,
        rescale_slope=1.0,
        rescale_intercept=None,
        dicom_processor=DICOMProcessor,
    )
    assert (wc, ww) == (40.0, 400.0)
