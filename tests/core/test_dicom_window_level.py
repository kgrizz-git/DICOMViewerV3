"""
Tests for DICOM window/level extraction and application helpers.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
from pydicom.dataset import Dataset
from pydicom.multival import MultiValue
from pydicom.sequence import Sequence

from core.dicom_window_level import (
    _nth_or_last,
    apply_color_window_level_luminance,
    apply_window_level,
    convert_window_level_raw_to_rescaled,
    convert_window_level_rescaled_to_raw,
    convert_window_level_units,
    get_base_window_level,
    get_window_level_from_dataset,
    get_window_level_presets_from_dataset,
)
from core.multiframe_handler import create_frame_dataset


class TestApplyWindowLevel:
    def test_basic_mapping(self):
        arr = np.array([-10.0, 128.0, 999.0], dtype=np.float32)
        out = apply_window_level(arr, window_center=128, window_width=255)
        assert out.dtype == np.uint8
        assert out[0] == 0
        assert out[2] == 255

    def test_zero_width_returns_zeros(self):
        arr = np.array([-10.0, 128.0, 999.0], dtype=np.float32)
        out = apply_window_level(arr, window_center=100, window_width=0)
        assert np.all(out == 0)

    def test_rescale_params(self):
        arr = np.array([-10.0, 999.0], dtype=np.float32)
        out = apply_window_level(arr, window_center=128, window_width=255,
                                 rescale_slope=1.0, rescale_intercept=0.0)
        assert out[0] == 0
        assert out[1] == 255


class TestApplyColorWindowLevelLuminance:
    def test_non_rgb_returns_grayscale(self):
        arr_bad = np.zeros((10, 10), dtype=np.uint8)
        out = apply_color_window_level_luminance(arr_bad, window_center=128, window_width=256)
        assert out.shape == arr_bad.shape
        assert out.dtype == np.uint8

    def test_rgb_input(self):
        arr_rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        arr_rgb[0, 0] = [100, 100, 100]
        out = apply_color_window_level_luminance(arr_rgb, window_center=100, window_width=100)
        assert out.dtype == np.uint8
        assert out.shape == (2, 2, 3)
        # window [50, 150]: luminance 100 -> normalized to mid-scale grey.
        assert tuple(out[0, 0]) == (127, 127, 127)
        # zero-luminance pixels stay black regardless of windowing.
        assert tuple(out[0, 1]) == (0, 0, 0)
        assert tuple(out[1, 1]) == (0, 0, 0)

    def test_zero_width_returns_zeros(self):
        arr_rgb = np.zeros((2, 2, 3), dtype=np.uint8)
        out = apply_color_window_level_luminance(arr_rgb, window_center=100, window_width=0)
        assert np.all(out == 0)


class TestConvertWindowLevelRescaledToRaw:
    def test_normal(self):
        c, w = convert_window_level_rescaled_to_raw(100, 200, 2.0, -50.0)
        assert c == 75.0
        assert w == 100.0

    def test_zero_slope(self):
        c, w = convert_window_level_rescaled_to_raw(100, 200, 0.0, 50.0)
        assert c == 100
        assert w == 200


class TestConvertWindowLevelRawToRescaled:
    def test_normal(self):
        c, w = convert_window_level_raw_to_rescaled(75.0, 100.0, 2.0, -50.0)
        assert c == 100.0
        assert w == 200.0


class TestGetWindowLevelFromDataset:
    def test_with_tags(self):
        ds = Dataset()
        ds.WindowCenter = "50"
        ds.WindowWidth = "100"
        c, w, is_rescaled = get_window_level_from_dataset(ds, rescale_slope=1.0, rescale_intercept=0.0)
        assert c == 50.0
        assert w == 100.0
        assert is_rescaled is True

    def test_without_tags_fallback(self):
        ds = Dataset()
        arr = np.array([0, 100], dtype=np.uint16)
        with patch('core.dicom_window_level.get_pixel_array', return_value=arr):
            c, w, is_rescaled = get_window_level_from_dataset(ds, rescale_slope=1.0, rescale_intercept=0.0)
            assert w == 100.0
            assert c == 100.0
            assert is_rescaled is False

    def test_only_window_center_uses_fallback_for_width(self):
        ds = Dataset()
        ds.WindowCenter = "40"
        arr = np.array([0, 100], dtype=np.uint16)
        with patch('core.dicom_window_level.get_pixel_array', return_value=arr):
            c, w, is_rescaled = get_window_level_from_dataset(ds, rescale_slope=1.0, rescale_intercept=0.0)
            assert c == 40.0
            assert w == 100.0


class TestGetBaseWindowLevel:
    def test_both_provided_no_lookup(self):
        ds = Dataset()
        c, w, extracted, is_rescaled = get_base_window_level(ds, 50.0, 100.0, 1.0, 0.0)
        assert c == 50.0
        assert w == 100.0
        assert extracted is False

    def test_center_none_triggers_lookup(self):
        ds = Dataset()
        with patch('core.dicom_window_level.get_window_level_from_dataset', return_value=(40.0, 80.0, True)):
            c, w, extracted, is_rescaled = get_base_window_level(ds, None, 100.0, 1.0, 0.0)
            assert c == 40.0
            assert w == 100.0
            assert extracted is True

    def test_both_none_triggers_lookup(self):
        ds = Dataset()
        with patch('core.dicom_window_level.get_window_level_from_dataset', return_value=(40.0, 80.0, True)):
            c, w, extracted, is_rescaled = get_base_window_level(ds, None, None, 1.0, 0.0)
            assert c == 40.0
            assert w == 80.0
            assert extracted is True


class TestConvertWindowLevelUnits:
    def test_extracted_false_no_conversion(self):
        c, w = convert_window_level_units(100.0, 200.0, False, True, False, 2.0, 0.0)
        assert c == 100.0
        assert w == 200.0

    def test_both_rescaled_no_conversion(self):
        c, w = convert_window_level_units(100.0, 200.0, True, True, True, 2.0, 0.0)
        assert c == 100.0
        assert w == 200.0

    def test_rescaled_to_raw(self):
        c, w = convert_window_level_units(100.0, 200.0, True, True, False, 2.0, 0.0)
        assert c == 50.0
        assert w == 100.0


class TestGetWindowLevelPresetsFromDataset:
    def test_uses_explanations(self):
        ds = Dataset()
        ds.WindowCenter = [10, 20, 30]
        ds.WindowWidth = [100, 200, 300]
        ds.WindowCenterWidthExplanation = ["NORMAL", "HARDER", "SOFTER"]
        presets = get_window_level_presets_from_dataset(ds)
        assert [preset[3] for preset in presets] == ["NORMAL", "HARDER", "SOFTER"]

    def test_numeric_fallbacks_without_explanations(self):
        ds = Dataset()
        ds.WindowCenter = [10, 20, 30]
        ds.WindowWidth = [100, 200, 300]
        presets = get_window_level_presets_from_dataset(ds)
        assert [preset[3] for preset in presets] == ["1", "2", "3"]

    def test_fills_missing_explanations_by_index(self):
        ds = Dataset()
        ds.WindowCenter = [10, 20, 30]
        ds.WindowWidth = [100, 200, 300]
        ds.WindowCenterWidthExplanation = ["NORMAL", "", "SOFTER"]
        presets = get_window_level_presets_from_dataset(ds)
        assert [preset[3] for preset in presets] == ["NORMAL", "2", "SOFTER"]

    def test_single_explanation_name(self):
        ds = Dataset()
        ds.WindowCenter = 42
        ds.WindowWidth = 80
        ds.WindowCenterWidthExplanation = "Brain"
        presets = get_window_level_presets_from_dataset(ds)
        assert [preset[3] for preset in presets] == ["Brain"]

    def test_multi_value_presets(self):
        ds = Dataset()
        ds.WindowCenter = MultiValue(str, ["50", "60"])
        ds.WindowWidth = MultiValue(str, ["100", "120"])
        presets = get_window_level_presets_from_dataset(ds)
        assert len(presets) == 2
        assert presets[0][:2] == (50.0, 100.0)
        assert presets[1][:2] == (60.0, 120.0)

    def test_missing_all_tags(self):
        ds = Dataset()
        assert get_window_level_presets_from_dataset(ds) == []

    def test_reads_functional_group_explanations(self):
        voi = Dataset()
        voi.WindowCenter = [10, 20]
        voi.WindowWidth = [100, 200]
        voi.WindowCenterWidthExplanation = ["NORMAL", "SOFTER"]
        shared = Dataset()
        shared.FrameVOILUTSequence = Sequence([voi])
        ds = Dataset()
        ds.SharedFunctionalGroupsSequence = Sequence([shared])
        presets = get_window_level_presets_from_dataset(ds)
        assert [preset[3] for preset in presets] == ["NORMAL", "SOFTER"]


def test_multiframe_wrapper_uses_frame_voi_explanations() -> None:
    voi0 = Dataset()
    voi0.WindowCenter = [10, 20, 30]
    voi0.WindowWidth = [100, 200, 300]
    voi0.WindowCenterWidthExplanation = ["NORMAL", "HARDER", "SOFTER"]
    fg0 = Dataset()
    fg0.FrameVOILUTSequence = Sequence([voi0])
    ds = Dataset()
    ds.PerFrameFunctionalGroupsSequence = Sequence([fg0])
    ds.NumberOfFrames = 1
    frame = create_frame_dataset(ds, 0)
    assert frame is not None
    presets = get_window_level_presets_from_dataset(frame)
    assert [preset[3] for preset in presets] == ["NORMAL", "HARDER", "SOFTER"]


class TestNthOrLast:
    def test_first(self):
        assert _nth_or_last([1, 2, 3], 0) == 1

    def test_last(self):
        assert _nth_or_last([1, 2, 3], 2) == 3

    def test_out_of_range_returns_last(self):
        assert _nth_or_last([1, 2, 3], 5) == 3

    def test_empty_returns_none(self):
        assert _nth_or_last([], 0) is None
