"""
Unit tests for core.dicom_projections (AIP/MIP/MinIP intensity projections + cache).
"""

from __future__ import annotations

import numpy as np
import pytest
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from core.dicom_projections import (
    average_intensity_projection,
    clear_projection_cache,
    maximum_intensity_projection,
    minimum_intensity_projection,
)


def _make_dataset(pixel_values) -> Dataset:
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
    ds.PixelData = arr.tobytes()
    return ds


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_projection_cache()
    yield
    clear_projection_cache()


class TestAverageIntensityProjection:
    def test_empty_list_returns_none(self):
        assert average_intensity_projection([]) is None

    def test_computes_mean_across_slices(self):
        datasets = [_make_dataset([[10, 20]]), _make_dataset([[30, 40]])]
        result = average_intensity_projection(datasets)
        assert result is not None
        assert result.dtype == np.float32
        np.testing.assert_array_equal(result, np.array([[20.0, 30.0]], dtype=np.float32))

    def test_result_is_cached_for_identical_series(self):
        datasets = [_make_dataset([[10, 20]]), _make_dataset([[30, 40]])]
        first = average_intensity_projection(datasets)
        second = average_intensity_projection(datasets)
        assert first is second


class TestMaximumIntensityProjection:
    def test_empty_list_returns_none(self):
        assert maximum_intensity_projection([]) is None

    def test_computes_max_across_slices(self):
        datasets = [_make_dataset([[10, 99]]), _make_dataset([[30, 40]])]
        result = maximum_intensity_projection(datasets)
        np.testing.assert_array_equal(result, np.array([[30.0, 99.0]], dtype=np.float32))


class TestMinimumIntensityProjection:
    def test_empty_list_returns_none(self):
        assert minimum_intensity_projection([]) is None

    def test_computes_min_across_slices(self):
        datasets = [_make_dataset([[10, 99]]), _make_dataset([[30, 40]])]
        result = minimum_intensity_projection(datasets)
        np.testing.assert_array_equal(result, np.array([[10.0, 40.0]], dtype=np.float32))


def test_different_projection_types_do_not_share_cache_entries():
    datasets = [_make_dataset([[10, 20]]), _make_dataset([[30, 40]])]
    aip = average_intensity_projection(datasets)
    mip = maximum_intensity_projection(datasets)
    assert not np.array_equal(aip, mip)
