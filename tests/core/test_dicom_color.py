"""Tests for core.dicom_color — color detection and conversion helpers."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
from pydicom.dataset import Dataset

from core.dicom_color import (
    _chroma_variance_ratios,
    _convert_ybr_to_rgb_2d,
    _is_already_rgb,
    convert_ybr_to_rgb,
    detect_and_fix_rgb_channel_order,
    is_color_image,
    multichannel_axis_labels,
)


def test_is_color_image():
    ds = Dataset()
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = "MONOCHROME2"
    is_color, pi = is_color_image(ds)
    assert not is_color
    assert pi == "MONOCHROME2"

    ds = Dataset()
    ds.SamplesPerPixel = 3
    ds.PhotometricInterpretation = "RGB"
    is_color, pi = is_color_image(ds)
    assert is_color
    assert pi == "RGB"

    ds = Dataset()
    ds.SamplesPerPixel = 3
    ds.PhotometricInterpretation = ""
    is_color, pi = is_color_image(ds)
    assert is_color
    assert pi is None

    class BadDataset:
        @property
        def SamplesPerPixel(self):
            raise ValueError("Test error")

    is_color, pi = is_color_image(BadDataset())
    assert not is_color
    assert pi is None


def test_multichannel_axis_labels():
    ds = Dataset()
    assert multichannel_axis_labels(ds, 2) == ("Ch0", "Ch1")

    ds.PhotometricInterpretation = "RGB"
    assert multichannel_axis_labels(ds, 3) == ("R", "G", "B")

    ds.PhotometricInterpretation = "YBR_FULL"
    assert multichannel_axis_labels(ds, 3) == ("Y", "Cb", "Cr")

    ds_none = Dataset()
    assert multichannel_axis_labels(ds_none, 3) == ("Ch0", "Ch1", "Ch2")

    ds_pal = Dataset()
    ds_pal.PhotometricInterpretation = "PALETTE COLOR"
    assert multichannel_axis_labels(ds_pal, 3) == ("Ch0", "Ch1", "Ch2")


def test_convert_ybr_to_rgb_2d():
    ybr = np.zeros((1, 1, 3), dtype=np.float32)
    ybr[0, 0] = [128, 128, 128]
    out = _convert_ybr_to_rgb_2d(ybr, use_rct=False)
    assert out.shape == (1, 1, 3)
    assert np.array_equal(out[0, 0], [128, 128, 128])

    ybr_rct = np.zeros((1, 1, 3), dtype=np.float32)
    ybr_rct[0, 0] = [100, 10, -10]
    out_rct = _convert_ybr_to_rgb_2d(ybr_rct, use_rct=True)
    assert out_rct.shape == (1, 1, 3)
    # RCT: G = Y - floor((Cr+Cb)/4) = 100; R = Cr+G = 90; B = Cb+G = 110
    assert np.array_equal(out_rct[0, 0], [90, 100, 110])


def test_convert_ybr_to_rgb():
    ybr = np.zeros((10, 10, 3), dtype=np.uint8)
    out = convert_ybr_to_rgb(ybr, photometric_interpretation=None)
    assert np.array_equal(out, ybr)

    ybr_rct = np.ones((10, 10, 3), dtype=np.uint8) * 128
    with patch('core.dicom_color._convert_via_pydicom', return_value=None):
        out_rct = convert_ybr_to_rgb(ybr_rct, photometric_interpretation="YBR_RCT")
    assert out_rct.shape == ybr_rct.shape
    assert out_rct.dtype == np.uint8

    ybr_grey = np.ones((10, 10, 3), dtype=np.uint8) * 128
    out_grey = convert_ybr_to_rgb(ybr_grey, photometric_interpretation="YBR_FULL")
    assert out_grey.shape == ybr_grey.shape
    assert out_grey.dtype == np.uint8
    # Uniform grey (Y=Cb=Cr=128) should convert to approximately (128,128,128) in RGB
    assert np.all(np.abs(out_grey.astype(int) - 128) <= 2)


def test_detect_and_fix_rgb_channel_order():
    arr = np.zeros((2, 2, 3), dtype=np.uint8)
    out = detect_and_fix_rgb_channel_order(arr)
    assert np.array_equal(out, arr)


def test_is_already_rgb():
    arr_rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    arr_rgb[:, :, 0] = 50
    arr_rgb[:, :, 1] = 50
    arr_rgb[:, :, 2] = 50
    assert _is_already_rgb(arr_rgb) is True

    arr_ybr = np.zeros((10, 10, 3), dtype=np.uint8)
    arr_ybr[:, :, 0] = 50
    arr_ybr[:, :, 1] = 128
    arr_ybr[:, :, 2] = 128
    assert _is_already_rgb(arr_ybr) is False


def test_chroma_variance_ratios():
    arr = np.random.randint(0, 255, (10, 10, 3), dtype=np.uint8)
    res = _chroma_variance_ratios(arr)
    assert len(res) == 4
    for val in res:
        assert isinstance(val, float)
