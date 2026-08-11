"""Tests for core.dicom_image_render — color-shape classification, normalization, and PIL rendering."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

from core.dicom_image_render import (
    classify_color_shape,
    convert_color_pixel_array,
    normalize_channels_to_uint8,
    normalize_to_uint8,
    reclassify_color_shape,
    render_color_image,
    render_grayscale_image,
)
from core.dicom_window_level import (
    apply_color_window_level_luminance,
    apply_window_level,
)


def test_normalize_to_uint8_range():
    arr = np.array([[0, 128, 255]], dtype=np.uint8)
    result = normalize_to_uint8(arr)
    assert result.dtype == np.uint8
    assert result.min() == 0
    assert result.max() == 255


def test_normalize_to_uint8_flat():
    arr = np.full((3, 3), 42, dtype=np.uint8)
    result = normalize_to_uint8(arr)
    assert np.all(result == 0)


def test_normalize_channels_to_uint8_per_channel():
    # Each channel has its own min/max so scaling is independent per channel,
    # not derived from a single global min/max across the array.
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[:, :, 0] = 10
    arr[0, 0, 0] = 30
    arr[:, :, 1] = 50
    arr[0, 0, 1] = 150
    arr[:, :, 2] = 100
    arr[0, 0, 2] = 200
    result = normalize_channels_to_uint8(arr)
    assert result.shape == (4, 4, 3)
    assert result.dtype == np.uint8
    # The min of each channel scales to 0, the max to 255, independently per channel.
    assert tuple(result[0, 0]) == (255, 255, 255)
    assert tuple(result[1, 1]) == (0, 0, 0)


def test_normalize_channels_flat_channel():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[:, :, 1] = 50
    result = normalize_channels_to_uint8(arr)
    assert np.all(result[:, :, 0] == 0)
    assert np.all(result[:, :, 2] == 0)


def test_classify_color_shape_grayscale():
    ds = Dataset()
    ds.SamplesPerPixel = 1
    arr = np.zeros((4, 4), dtype=np.uint8)
    assert classify_color_shape(ds, arr, is_color=False) == (False, False)


def test_classify_color_shape_4d():
    ds = Dataset()
    ds.SamplesPerPixel = 3
    arr = np.zeros((2, 4, 4, 3), dtype=np.uint8)
    assert classify_color_shape(ds, arr, is_color=True) == (True, False)


def test_classify_color_shape_single_frame():
    ds = Dataset()
    ds.SamplesPerPixel = 3
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    assert classify_color_shape(ds, arr, is_color=True) == (False, True)


def test_classify_color_shape_mismatch():
    ds = Dataset()
    ds.SamplesPerPixel = 1
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    assert classify_color_shape(ds, arr, is_color=True) == (False, False)


def test_classify_color_shape_3d_grayscale():
    ds = Dataset()
    ds.SamplesPerPixel = 1
    arr = np.zeros((5, 4, 4), dtype=np.uint8)
    assert classify_color_shape(ds, arr, is_color=True) == (False, False)


def test_classify_color_shape_no_samples_per_pixel_attribute():
    ds = Dataset()  # no SamplesPerPixel set -- falls back to grayscale default of 1
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    assert classify_color_shape(ds, arr, is_color=True) == (False, False)


def test_reclassify_color_shape_4d():
    arr = np.zeros((2, 4, 4, 3), dtype=np.uint8)
    assert reclassify_color_shape(arr) == (True, False)


def test_reclassify_color_shape_3d():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    assert reclassify_color_shape(arr) == (False, True)


def test_reclassify_color_shape_2d():
    arr = np.zeros((4, 4), dtype=np.uint8)
    assert reclassify_color_shape(arr) == (False, False)


def test_reclassify_color_shape_3d_not_rgb():
    arr = np.zeros((4, 4, 4), dtype=np.uint8)
    assert reclassify_color_shape(arr) == (False, False)


def test_convert_color_pixel_array_ybr():
    # Non-grey YBR values so a no-op or grey-only conversion would be caught.
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[:, :, 0] = 200
    arr[:, :, 1] = 90
    arr[:, :, 2] = 200
    ds = Dataset()
    out, did_ybr = convert_color_pixel_array(arr, "YBR_FULL", None, ds)
    assert did_ybr is True
    assert out.shape == (4, 4, 3)
    assert out.dtype == np.uint8
    assert not np.array_equal(out, arr)
    assert np.array_equal(out[0, 0], [255, 161, 132])


def test_convert_color_pixel_array_ybr_full_422():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[:, :, 0] = 200
    arr[:, :, 1] = 90
    arr[:, :, 2] = 200
    ds = Dataset()
    out, did_ybr = convert_color_pixel_array(arr, "YBR_FULL_422", None, ds)
    assert did_ybr is True
    assert out is not None
    assert out.shape == (4, 4, 3)
    assert out.dtype == np.uint8
    assert not np.array_equal(out, arr)
    assert np.array_equal(out[0, 0], [255, 161, 132])


def test_convert_color_pixel_array_ybr_ict():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[:, :, 0] = 200
    arr[:, :, 1] = 90
    arr[:, :, 2] = 200
    ds = Dataset()
    out, did_ybr = convert_color_pixel_array(arr, "YBR_ICT", None, ds)
    assert did_ybr is True
    assert out is not None
    assert out.shape == (4, 4, 3)
    assert out.dtype == np.uint8
    assert not np.array_equal(out, arr)
    assert np.array_equal(out[0, 0], [255, 161, 132])


def test_convert_color_pixel_array_ybr_rct():
    arr = np.zeros((4, 4, 3), dtype=np.uint8)
    arr[:, :, 0] = 200
    arr[:, :, 1] = 90
    arr[:, :, 2] = 200
    ds = Dataset()
    out, did_ybr = convert_color_pixel_array(arr, "YBR_RCT", None, ds)
    assert did_ybr is True
    assert out is not None
    assert out.shape == (4, 4, 3)
    assert out.dtype == np.uint8
    assert not np.array_equal(out, arr)
    assert np.array_equal(out[0, 0], [255, 128, 218])


def test_convert_color_pixel_array_rgb():
    arr = np.full((4, 4, 3), 100, dtype=np.uint8)
    ds = Dataset()
    out, did_ybr = convert_color_pixel_array(arr, "RGB", None, ds)
    assert did_ybr is False
    assert out.shape == (4, 4, 3)


def test_convert_color_pixel_array_no_photometric():
    arr = np.full((4, 4, 3), 100, dtype=np.uint8)
    ds = Dataset()
    out, did_ybr = convert_color_pixel_array(arr, None, None, ds)
    assert did_ybr is False
    assert out is arr


def test_render_color_image_with_window_level():
    arr = np.zeros((8, 8, 3), dtype=np.uint8)
    arr[0, 0] = [200, 100, 50]
    arr[4, 4] = [10, 220, 30]
    result = render_color_image(arr, 40.0, 400.0, 1.0, 0.0, is_multi_frame_color=False)
    assert result is not None
    assert isinstance(result, Image.Image)
    assert result.mode == "RGB"
    assert result.size == (8, 8)
    expected = apply_color_window_level_luminance(arr, 40.0, 400.0, 1.0, 0.0)
    assert np.array_equal(np.array(result), expected)


def test_render_color_image_no_window_level():
    arr = np.zeros((8, 8, 3), dtype=np.uint8)
    arr[0, 0] = [200, 100, 50]
    arr[4, 4] = [10, 220, 30]
    result = render_color_image(arr, None, None, None, None, is_multi_frame_color=False)
    assert result is not None
    assert result.mode == "RGB"
    expected = normalize_channels_to_uint8(arr)
    assert np.array_equal(np.array(result), expected)


def test_render_color_image_multi_frame():
    arr = np.zeros((3, 8, 8, 3), dtype=np.uint8)
    arr[0, 0, 0] = [200, 100, 50]
    arr[0, 4, 4] = [10, 220, 30]
    arr[1, :, :, :] = 255  # other frames must be ignored -- only frame 0 is rendered
    result = render_color_image(arr, None, None, None, None, is_multi_frame_color=True)
    assert result is not None
    assert result.mode == "RGB"
    assert result.size == (8, 8)
    expected = normalize_channels_to_uint8(arr[0])
    assert np.array_equal(np.array(result), expected)


def test_render_color_image_returns_none_on_error():
    arr = np.zeros((8, 8, 3), dtype=np.uint8)
    with patch("core.dicom_image_render.Image.fromarray", side_effect=ValueError("boom")):
        result = render_color_image(arr, None, None, None, None, is_multi_frame_color=False)
    assert result is None


def test_render_grayscale_image_with_window_level():
    arr = np.zeros((8, 8), dtype=np.uint8)
    arr[0, 0] = 200
    arr[4, 4] = 50
    result = render_grayscale_image(arr, 40.0, 400.0, 1.0, 0.0)
    assert result is not None
    assert isinstance(result, Image.Image)
    assert result.mode == "L"
    assert result.size == (8, 8)
    expected = apply_window_level(arr, 40.0, 400.0, 1.0, 0.0)
    assert np.array_equal(np.array(result), expected)


def test_render_grayscale_image_no_window_level():
    arr = np.zeros((8, 8), dtype=np.uint8)
    arr[0, 0] = 200
    arr[4, 4] = 50
    result = render_grayscale_image(arr, None, None, None, None)
    assert result is not None
    assert result.mode == "L"
    expected = normalize_to_uint8(arr)
    assert np.array_equal(np.array(result), expected)


def test_render_grayscale_image_3d_fallback():
    arr = np.zeros((3, 8, 8), dtype=np.uint8)
    arr[0, 0, 0] = 200
    arr[0, 4, 4] = 50
    arr[1, :, :] = 255  # other frames must be ignored -- only frame 0 is rendered
    result = render_grayscale_image(arr, None, None, None, None)
    assert result is not None
    assert result.mode == "L"
    assert result.size == (8, 8)
    # normalize_to_uint8 runs on the full 3D array before the first-frame fallback slice.
    expected = normalize_to_uint8(arr)[0]
    assert np.array_equal(np.array(result), expected)


def test_render_grayscale_image_returns_none_on_error():
    arr = np.zeros((8, 8), dtype=np.uint8)
    with patch("core.dicom_image_render.Image.fromarray", side_effect=ValueError("boom")):
        result = render_grayscale_image(arr, None, None, None, None)
    assert result is None
