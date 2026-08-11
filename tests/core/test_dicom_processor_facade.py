"""Tests for core.dicom_processor — DICOMProcessor facade delegation wiring and dataset_to_image integration."""

from __future__ import annotations

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

from core import (
    dicom_color,
    dicom_pixel_array,
    dicom_pixel_stats,
    dicom_projections,
    dicom_rescale,
    dicom_window_level,
)
from core.dicom_processor import DICOMProcessor


class _PixelDataset(Dataset):
    """Dataset subclass that returns a fixed numpy array from pixel_array."""

    def __init__(self, array: np.ndarray, **attrs) -> None:
        super().__init__()
        for key, value in attrs.items():
            setattr(self, key, value)
        self._pixel_array = array

    @property
    def pixel_array(self) -> np.ndarray:
        return self._pixel_array


def _make_grayscale_dataset() -> _PixelDataset:
    arr = np.arange(16, dtype=np.uint8).reshape(4, 4)
    return _PixelDataset(
        arr,
        SamplesPerPixel=1,
        PhotometricInterpretation="MONOCHROME2",
        Rows=4,
        Columns=4,
        BitsAllocated=8,
        BitsStored=8,
        HighBit=7,
        PixelRepresentation=0,
    )


def _make_color_dataset() -> _PixelDataset:
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[0, 0] = [200, 100, 50]
    arr[2, 2] = [10, 220, 30]
    return _PixelDataset(
        arr,
        SamplesPerPixel=3,
        PhotometricInterpretation="RGB",
        Rows=4,
        Columns=4,
        BitsAllocated=8,
        BitsStored=8,
        HighBit=7,
        PixelRepresentation=0,
        PlanarConfiguration=0,
    )


def test_get_rescale_parameters_delegates():
    ds = Dataset()
    ds.RescaleSlope = 1.5
    ds.RescaleIntercept = -100.0
    ds.RescaleType = "HU"
    assert DICOMProcessor.get_rescale_parameters(ds) == dicom_rescale.get_rescale_parameters(ds)


def test_infer_rescale_type_delegates():
    ds = Dataset()
    ds.Modality = "CT"
    assert (
        DICOMProcessor.infer_rescale_type(ds, 1.0, 0.0, None)
        == dicom_rescale.infer_rescale_type(ds, 1.0, 0.0, None)
    )


def test_is_color_image_delegates():
    ds = Dataset()
    ds.SamplesPerPixel = 3
    ds.PhotometricInterpretation = "RGB"
    result = DICOMProcessor.is_color_image(ds)
    expected = dicom_color.is_color_image(ds)
    assert result == expected
    assert isinstance(result, tuple)
    assert len(result) == 2


def test_get_pixel_array_delegates():
    ds = _make_grayscale_dataset()
    result = DICOMProcessor.get_pixel_array(ds)
    expected = dicom_pixel_array.get_pixel_array(ds)
    assert result is not None
    np.testing.assert_array_equal(result, expected)


def test_apply_window_level_delegates():
    arr = np.arange(16, dtype=np.uint8).reshape(4, 4)
    assert np.array_equal(
        DICOMProcessor.apply_window_level(arr, 40.0, 400.0, 1.0, 0.0),
        dicom_window_level.apply_window_level(arr, 40.0, 400.0, 1.0, 0.0),
    )


def test_average_intensity_projection_delegates():
    ds = _make_grayscale_dataset()
    result = DICOMProcessor.average_intensity_projection([ds])
    expected = dicom_projections.average_intensity_projection([ds])
    assert result is not None
    np.testing.assert_array_equal(result, expected)


def test_maximum_intensity_projection_delegates():
    ds = _make_grayscale_dataset()
    result = DICOMProcessor.maximum_intensity_projection([ds])
    expected = dicom_projections.maximum_intensity_projection([ds])
    assert result is not None
    np.testing.assert_array_equal(result, expected)


def test_minimum_intensity_projection_delegates():
    ds = _make_grayscale_dataset()
    result = DICOMProcessor.minimum_intensity_projection([ds])
    expected = dicom_projections.minimum_intensity_projection([ds])
    assert result is not None
    np.testing.assert_array_equal(result, expected)


def test_get_pixel_value_range_delegates():
    ds = _make_grayscale_dataset()
    assert DICOMProcessor.get_pixel_value_range(ds) == dicom_pixel_stats.get_pixel_value_range(ds)


def test_get_series_pixel_value_range_delegates():
    ds = _make_grayscale_dataset()
    assert (
        DICOMProcessor.get_series_pixel_value_range([ds])
        == dicom_pixel_stats.get_series_pixel_value_range([ds])
    )


def test_get_series_pixel_median_delegates():
    ds = _make_grayscale_dataset()
    assert (
        DICOMProcessor.get_series_pixel_median([ds])
        == dicom_pixel_stats.get_series_pixel_median([ds])
    )


def test_dataset_to_image_grayscale():
    ds = _make_grayscale_dataset()
    result = DICOMProcessor.dataset_to_image(ds)
    assert result is not None
    assert isinstance(result, Image.Image)
    assert result.mode == "L"
    assert result.size == (4, 4)
    # arange(16) input renders as a monotonically increasing gradient; a blank
    # or constant image would fail this.
    rendered = np.array(result).flatten()
    assert rendered[0] < rendered[-1]
    assert list(rendered) == sorted(rendered)


def test_dataset_to_image_color():
    ds = _make_color_dataset()
    result = DICOMProcessor.dataset_to_image(ds)
    assert result is not None
    assert isinstance(result, Image.Image)
    assert result.mode == "RGB"
    assert result.size == (4, 4)
    # The two non-zero source pixels must map to distinct, non-black output
    # pixels; a blank/incorrect render would collapse these to black or grey.
    rendered = np.array(result)
    assert tuple(rendered[0, 0]) != (0, 0, 0)
    assert tuple(rendered[2, 2]) != (0, 0, 0)
    assert tuple(rendered[0, 0]) != tuple(rendered[2, 2])
    assert tuple(rendered[1, 1]) == (0, 0, 0)


def test_dataset_to_image_none_pixels():
    ds = Dataset()
    assert DICOMProcessor.dataset_to_image(ds) is None
