"""Tests for MONOCHROME1 inversion in core.dicom_image_render.render_grayscale_image."""

from __future__ import annotations

import numpy as np

from core.dicom_image_render import normalize_to_uint8, render_grayscale_image


def test_monochrome1_inverts_unsigned():
    arr = np.array([[0, 100, 200]], dtype=np.uint8)
    result = render_grayscale_image(arr, None, None, None, None, photometric_interpretation="MONOCHROME1")
    assert result is not None
    expected = 255 - normalize_to_uint8(arr)
    assert np.array_equal(np.array(result), expected)


def test_monochrome1_inverts_signed():
    arr = np.array([[-128, 0, 127]], dtype=np.int16)
    result = render_grayscale_image(arr, None, None, None, None, photometric_interpretation="MONOCHROME1")
    assert result is not None
    expected = 255 - normalize_to_uint8(arr)
    assert np.array_equal(np.array(result), expected)


def test_monochrome2_no_inversion():
    arr = np.array([[0, 100, 200]], dtype=np.uint8)
    result = render_grayscale_image(arr, None, None, None, None, photometric_interpretation="MONOCHROME2")
    assert result is not None
    expected = normalize_to_uint8(arr)
    assert np.array_equal(np.array(result), expected)


def test_no_photometric_no_inversion():
    arr = np.array([[0, 100, 200]], dtype=np.uint8)
    result = render_grayscale_image(arr, None, None, None, None, photometric_interpretation=None)
    assert result is not None
    expected = normalize_to_uint8(arr)
    assert np.array_equal(np.array(result), expected)


def test_monochrome1_with_window_level():
    arr = np.array([[0, 100, 200]], dtype=np.uint8)
    result = render_grayscale_image(arr, 100.0, 200.0, None, None, photometric_interpretation="MONOCHROME1")
    assert result is not None
    assert result.mode == "L"


def test_monochrome1_3d_array_first_frame():
    arr = np.zeros((3, 4, 4), dtype=np.uint8)
    arr[0, 0, 0] = 200
    arr[1, :, :] = 255
    result = render_grayscale_image(arr, None, None, None, None, photometric_interpretation="MONOCHROME1")
    assert result is not None
    assert result.size == (4, 4)
