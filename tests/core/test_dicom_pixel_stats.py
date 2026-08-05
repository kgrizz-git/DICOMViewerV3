"""
Unit tests for core.dicom_pixel_stats (pixel value range and median across series).
"""

from __future__ import annotations

import numpy as np
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from core.dicom_pixel_stats import (
    get_pixel_value_range,
    get_series_pixel_median,
    get_series_pixel_value_range,
)


def _make_dataset(pixel_values, rescale_slope=None, rescale_intercept=None) -> Dataset:
    arr = np.asarray(pixel_values, dtype=np.uint16)
    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.SOPClassUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.Modality = "CT"
    ds.Rows = arr.shape[0]
    ds.Columns = arr.shape[1]
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    ds.PixelRepresentation = 0
    ds.BitsAllocated = 16
    ds.BitsStored = 16
    ds.HighBit = 15
    if rescale_slope is not None:
        ds.RescaleSlope = rescale_slope
    if rescale_intercept is not None:
        ds.RescaleIntercept = rescale_intercept
    ds.PixelData = arr.tobytes()
    return ds


class TestGetPixelValueRange:
    def test_returns_min_max_without_rescale(self):
        ds = _make_dataset([[10, 20], [30, 40]])
        assert get_pixel_value_range(ds) == (10.0, 40.0)

    def test_applies_rescale_when_requested(self):
        ds = _make_dataset([[0, 100]], rescale_slope=2.0, rescale_intercept=-1000.0)
        result = get_pixel_value_range(ds, apply_rescale=True)
        assert result == (-1000.0, -800.0)

    def test_ignores_rescale_when_not_requested(self):
        ds = _make_dataset([[0, 100]], rescale_slope=2.0, rescale_intercept=-1000.0)
        assert get_pixel_value_range(ds, apply_rescale=False) == (0.0, 100.0)

    def test_no_pixel_data_returns_none_none(self):
        ds = Dataset()
        ds.Modality = "SR"
        ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.11"  # Basic Text SR
        result = get_pixel_value_range(ds)
        assert result == (None, None)


class TestGetSeriesPixelValueRange:
    def test_empty_list_returns_none_none(self):
        assert get_series_pixel_value_range([]) == (None, None)

    def test_full_scan_across_small_series(self):
        datasets = [
            _make_dataset([[5, 10]]),
            _make_dataset([[1, 50]]),
            _make_dataset([[20, 30]]),
        ]
        assert get_series_pixel_value_range(datasets, sample=False) == (1.0, 50.0)

    def test_sampling_still_includes_first_and_last_slice(self):
        # 30 single-value slices; sampling kicks in for len > 20.
        datasets = [_make_dataset([[i]]) for i in range(30)]
        result = get_series_pixel_value_range(datasets, sample=True)
        assert result == (0.0, 29.0)

    def test_applies_rescale_across_series(self):
        datasets = [
            _make_dataset([[0]], rescale_slope=1.0, rescale_intercept=-100.0),
            _make_dataset([[10]], rescale_slope=1.0, rescale_intercept=-100.0),
        ]
        assert get_series_pixel_value_range(datasets, apply_rescale=True, sample=False) == (-100.0, -90.0)


class TestGetSeriesPixelMedian:
    def test_empty_list_returns_none(self):
        assert get_series_pixel_median([]) is None

    def test_excludes_zeros_from_median(self):
        datasets = [_make_dataset([[0, 0, 10, 20]])]
        assert get_series_pixel_median(datasets) == 15.0

    def test_all_zero_returns_none(self):
        datasets = [_make_dataset([[0, 0], [0, 0]])]
        assert get_series_pixel_median(datasets) is None

    def test_applies_rescale_to_median(self):
        datasets = [_make_dataset([[10, 20]], rescale_slope=2.0, rescale_intercept=0.0)]
        assert get_series_pixel_median(datasets, apply_rescale=True) == 30.0
