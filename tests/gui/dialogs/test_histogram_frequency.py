"""Tests for gui.dialogs.histogram_frequency — histogram stats helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np

from gui.dialogs.histogram_frequency import (
    accumulate_pixels_histogram_stats,
    compute_series_global_frequency_stats,
    parse_rescale_slope_intercept,
    resolve_series_datasets,
)


def test_resolve_series_datasets_returns_direct_when_available():
    get_series_datasets = MagicMock(return_value=["dataset1"])
    result = resolve_series_datasets(get_series_datasets, None, None, None)
    assert result == ["dataset1"]


def test_resolve_series_datasets_uses_fallback_when_direct_is_empty():
    get_series_datasets = MagicMock(return_value=[])
    get_all_studies = MagicMock(return_value={"study1": {"series1": ["dataset2"]}})
    get_series_study_uid = MagicMock(return_value="study1")
    get_series_uid = MagicMock(return_value="series1")
    result = resolve_series_datasets(get_series_datasets, get_all_studies, get_series_study_uid, get_series_uid)
    assert result == ["dataset2"]


def test_resolve_series_datasets_uses_fallback_when_direct_is_none():
    get_all_studies = MagicMock(return_value={"study1": {"series1": ["dataset3"]}})
    get_series_study_uid = MagicMock(return_value="study1")
    get_series_uid = MagicMock(return_value="series1")
    result = resolve_series_datasets(None, get_all_studies, get_series_study_uid, get_series_uid)
    assert result == ["dataset3"]


def test_resolve_series_datasets_returns_none_when_all_fail():
    get_series_datasets = MagicMock(return_value=[])
    get_all_studies = MagicMock(return_value={"study1": {}})
    get_series_study_uid = MagicMock(return_value="study1")
    get_series_uid = MagicMock(return_value="series2")
    result = resolve_series_datasets(get_series_datasets, get_all_studies, get_series_study_uid, get_series_uid)
    assert result is None


def test_parse_rescale_slope_intercept_not_used():
    slope, intercept = parse_rescale_slope_intercept(False, None)
    assert slope == 1.0
    assert intercept == 0.0


def test_parse_rescale_slope_intercept_used_valid():
    get_rescale_params = MagicMock(return_value=(2.5, -10.0, None))
    slope, intercept = parse_rescale_slope_intercept(True, get_rescale_params)
    assert slope == 2.5
    assert intercept == -10.0


def test_parse_rescale_slope_intercept_exception():
    get_rescale_params = MagicMock(side_effect=Exception("Failed"))
    slope, intercept = parse_rescale_slope_intercept(True, get_rescale_params)
    assert slope == 1.0
    assert intercept == 0.0


def test_parse_rescale_slope_intercept_nones():
    get_rescale_params = MagicMock(return_value=(None, None, None))
    slope, intercept = parse_rescale_slope_intercept(True, get_rescale_params)
    assert slope == 1.0
    assert intercept == 0.0


def test_accumulate_pixels_empty_array():
    pixels = np.array([], dtype=np.float32)
    max_f, min_v, max_v = accumulate_pixels_histogram_stats(pixels, 5.0, 1.0, 10.0)
    assert max_f == 5.0
    assert min_v == 1.0
    assert max_v == 10.0


def test_accumulate_pixels_single_frame():
    pixels = np.array([1.0, 1.0, 2.0, 3.0], dtype=np.float32)
    max_f, min_v, max_v = accumulate_pixels_histogram_stats(pixels, 0.0, None, None)
    assert max_f >= 2.0
    assert min_v == 1.0
    assert max_v == 3.0


def test_accumulate_pixels_two_calls():
    pixels1 = np.array([1.0, 5.0], dtype=np.float32)
    max_f, min_v, max_v = accumulate_pixels_histogram_stats(pixels1, 0.0, None, None)
    pixels2 = np.array([-2.0, 10.0], dtype=np.float32)
    max_f, min_v, max_v = accumulate_pixels_histogram_stats(pixels2, max_f, min_v, max_v)
    assert min_v == -2.0
    assert max_v == 10.0


@patch('gui.dialogs.histogram_frequency.DICOMProcessor.get_pixel_array')
@patch('gui.dialogs.histogram_frequency.is_multiframe')
def test_compute_series_global_frequency_stats_empty(mock_is_mf, mock_get_pa):
    mock_is_mf.return_value = False
    max_f, x_min, x_max = compute_series_global_frequency_stats([], False, 1.0, 0.0)
    assert max_f is None
    assert x_min is None
    assert x_max is None


@patch('gui.dialogs.histogram_frequency.DICOMProcessor.get_pixel_array')
@patch('gui.dialogs.histogram_frequency.is_multiframe')
def test_compute_series_global_frequency_stats_all_nones(mock_is_mf, mock_get_pa):
    mock_is_mf.return_value = False
    max_f, x_min, x_max = compute_series_global_frequency_stats([None, None], False, 1.0, 0.0)
    assert max_f is None
    assert x_min is None
    assert x_max is None


@patch('gui.dialogs.histogram_frequency.DICOMProcessor.get_pixel_array')
@patch('gui.dialogs.histogram_frequency.is_multiframe')
def test_compute_series_global_frequency_stats_single_dataset(mock_is_mf, mock_get_pa):
    mock_is_mf.return_value = False
    mock_get_pa.return_value = np.array([0, 255], dtype=np.uint16)
    ds = MagicMock()
    max_f, x_min, x_max = compute_series_global_frequency_stats([ds], False, 1.0, 0.0)
    assert max_f is not None
    assert x_min == 0.0
    assert x_max == 255.0


@patch('gui.dialogs.histogram_frequency.DICOMProcessor.get_pixel_array')
@patch('gui.dialogs.histogram_frequency.is_multiframe')
def test_compute_series_global_frequency_stats_equal_values(mock_is_mf, mock_get_pa):
    mock_is_mf.return_value = False
    mock_get_pa.return_value = np.array([100, 100], dtype=np.uint16)
    ds = MagicMock()
    max_f, x_min, x_max = compute_series_global_frequency_stats([ds], False, 1.0, 0.0)
    assert max_f is not None
    assert x_min is None
    assert x_max is None
