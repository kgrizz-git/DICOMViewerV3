"""
Unit tests for core.dicom_pixel_array.
"""

import numpy as np
from pydicom.dataset import Dataset

from core.dicom_pixel_array import (
    _classify_pixel_array_error,
    get_pixel_array,
    handle_planar_configuration,
)


def test_classify_pixel_array_error_structured_report():
    ds = Dataset()
    ds.Modality = "SR"
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.33"
    is_comp, msg = _classify_pixel_array_error(
        ds,
        "one of pixel data, float pixel data or double float pixel data must be present",
    )
    assert is_comp is False
    assert "DICOM Structured Report" in msg


def test_classify_pixel_array_error_missing_pixel_data():
    ds = Dataset()
    ds.Modality = "CT"
    is_comp, msg = _classify_pixel_array_error(
        ds,
        "one of pixel data, float pixel data or double float pixel data must be present",
    )
    assert is_comp is False
    assert "does not contain Pixel Data" in msg


def test_classify_pixel_array_error_compression():
    ds = Dataset()
    is_comp, msg = _classify_pixel_array_error(
        ds, "unable to decode pixel data (pylibjpeg-libjpeg)"
    )
    assert is_comp is True
    assert (
        "compression" in msg.lower()
        or "codec" in msg.lower()
        or "decode" in msg.lower()
    )


def test_handle_planar_configuration_none():
    arr = np.zeros((10, 10, 3), dtype=np.uint8)
    ds = Dataset()
    out = handle_planar_configuration(arr, ds)
    assert np.array_equal(out, arr)


def test_handle_planar_configuration_3d_planar_1():
    arr = np.zeros((3, 10, 20), dtype=np.uint8)
    ds = Dataset()
    ds.PlanarConfiguration = 1
    out = handle_planar_configuration(arr, ds)
    assert out.shape == (10, 20, 3)


def test_handle_planar_configuration_4d_planar_1():
    arr = np.zeros((5, 3, 10, 20), dtype=np.uint8)
    ds = Dataset()
    ds.PlanarConfiguration = 1
    out = handle_planar_configuration(arr, ds)
    assert out.shape == (5, 10, 20, 3)


def test_handle_planar_configuration_exception():
    # Pass invalid input to trigger conversion exception
    ds = Dataset()
    ds.PlanarConfiguration = 1
    out = handle_planar_configuration(None, ds)
    assert out is None


def test_get_pixel_array_structured_report():
    ds = Dataset()
    ds.SOPClassUID = "1.2.840.10008.5.1.4.1.1.88.33"  # SR
    out = get_pixel_array(ds)
    assert out is None
    assert ds._no_pixel_reason == "structured_report"


def test_get_pixel_array_frame_wrapper():
    class MockFrameWrapper(Dataset):
        @property
        def pixel_array(self):
            return np.zeros((10, 10, 3), dtype=np.uint8)

    ds = MockFrameWrapper()
    # Simulating a frame wrapper
    ds._frame_index = 0
    ds._original_dataset = Dataset()
    out = get_pixel_array(ds)
    assert out.shape == (10, 10, 3)


def test_get_pixel_array_memory_error():
    class MockMemoryErrorDataset(Dataset):
        @property
        def pixel_array(self):
            raise MemoryError("out of memory")

    ds = MockMemoryErrorDataset()
    assert get_pixel_array(ds) is None


def test_get_pixel_array_decode_exception():
    class MockValueErrorDataset(Dataset):
        @property
        def pixel_array(self):
            raise ValueError("failed decode")

    ds = MockValueErrorDataset()
    assert get_pixel_array(ds) is None
