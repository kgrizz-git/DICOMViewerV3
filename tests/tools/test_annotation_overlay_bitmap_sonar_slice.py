"""
Characterization tests for overlay bitmap helpers (Sonar S3776 slice).

Covers byte extraction, bitmap resolution, coordinate/path extraction, and the
no-NumPy fallback extracted from ``AnnotationManager._convert_overlay_bitmap_to_graphics``.
"""

from __future__ import annotations

import numpy as np

from tools.annotation_overlay_bitmap import (
    convert_overlay_bitmap_to_graphics,
    extract_overlay_bytes,
    overlay_bitmap_from_bytes,
    overlay_bitmap_from_non_bytes,
    overlay_coordinates_from_bitmap,
    overlay_coordinates_no_numpy,
    overlay_paths_from_bitmap,
    overlay_pixel_to_image_coords,
    resolve_overlay_numpy_bitmap,
)


def test_extract_overlay_bytes_handles_value_bytes_and_failures() -> None:
    class _Element:
        value = bytes([0b00001111])

    assert extract_overlay_bytes(_Element()) == (bytes([0b00001111]), False)
    assert extract_overlay_bytes(b"abc") == (b"abc", False)
    assert extract_overlay_bytes(object()) == (None, True)


def test_overlay_bitmap_from_bytes_lsb_first_2x2() -> None:
    bitmap = overlay_bitmap_from_bytes(bytes([0b00001011]), 2, 2, np)
    assert bitmap.shape == (2, 2)
    assert bitmap[0, 0] == 1
    assert bitmap[0, 1] == 1
    assert bitmap[1, 0] == 0
    assert bitmap[1, 1] == 1


def test_overlay_bitmap_from_bytes_pads_truncated_payload() -> None:
    # One byte supplies 8 bits for a 3x3 (9-bit) grid — pad the missing bit with 0.
    bitmap = overlay_bitmap_from_bytes(bytes([0b00000001]), 3, 3, np)
    assert bitmap is not None
    assert bitmap.shape == (3, 3)
    assert bitmap[0, 0] == 1
    assert int(bitmap.sum()) == 1


def test_overlay_coordinates_no_numpy_matches_lsb_numpy() -> None:
    payload = bytes([0b00001011])
    numpy_coords = overlay_coordinates_from_bitmap(
        overlay_bitmap_from_bytes(payload, 2, 2, np), 0.0, 0.0, np
    )
    fallback_coords = overlay_coordinates_no_numpy(payload, 2, 2, 0.0, 0.0)
    assert sorted(fallback_coords) == sorted(numpy_coords)


def test_overlay_bitmap_from_non_bytes_list() -> None:
    bitmap = overlay_bitmap_from_non_bytes([1, 0, 0, 1], 2, 2, np)
    assert bitmap is not None
    assert bitmap.tolist() == [[1, 0], [0, 1]]


def test_resolve_overlay_numpy_bitmap_invalid_returns_none() -> None:
    assert resolve_overlay_numpy_bitmap(object(), 2, 2, np) is None


def test_overlay_pixel_to_image_coords() -> None:
    assert overlay_pixel_to_image_coords(1, 2, 10.0, 20.0) == (12.0, 21.0)


def test_overlay_coordinates_from_bitmap() -> None:
    bitmap = np.array([[1, 1], [0, 1]], dtype=np.uint8)
    coords = overlay_coordinates_from_bitmap(bitmap, 10.0, 20.0, np)
    assert sorted(coords) == [(10.0, 20.0), (11.0, 20.0), (11.0, 21.0)]


def test_overlay_paths_from_bitmap_uses_scipy_fallback() -> None:
    bitmap = np.array([[1, 1], [0, 1]], dtype=np.uint8)
    labeled = np.array([[1, 1], [0, 1]], dtype=np.int32)

    class _FakeNdimage:
        @staticmethod
        def label(_bitmap):
            return labeled, 1

    def _fake_import_module(name: str):
        if name == "cv2":
            raise ImportError
        if name == "scipy.ndimage":
            return _FakeNdimage()
        raise ImportError(name)

    paths = overlay_paths_from_bitmap(
        bitmap, 10.0, 20.0, np, import_module=_fake_import_module
    )
    assert paths == [[(10.0, 20.0), (11.0, 20.0), (11.0, 21.0)]]


def test_overlay_coordinates_no_numpy_lsb_within_byte() -> None:
    # LSB-first: bit 0 of 0b00000001 lights pixel (0,0), matching NumPy unpackbits little.
    coords = overlay_coordinates_no_numpy(bytes([0b00000001]), 2, 2, 0.0, 0.0)
    assert coords == [(0.0, 0.0)]


def test_convert_overlay_bitmap_to_graphics_invalid_input_returns_empty() -> None:
    result = convert_overlay_bitmap_to_graphics(object(), 2, 2, 0.0, 0.0)
    assert result == {"coordinates": [], "paths": []}


def test_convert_overlay_bitmap_to_graphics_scipy_integration() -> None:
    labeled = np.array([[1, 1], [0, 1]], dtype=np.int32)

    class _FakeNdimage:
        @staticmethod
        def label(_bitmap):
            return labeled, 1

    def _fake_import_module(name: str):
        if name == "cv2":
            raise ImportError
        if name == "scipy.ndimage":
            return _FakeNdimage()
        raise ImportError(name)

    result = convert_overlay_bitmap_to_graphics(
        bytes([0b00001011]),
        2,
        2,
        10.0,
        20.0,
        import_module=_fake_import_module,
    )
    assert sorted(result["coordinates"]) == [(10.0, 20.0), (11.0, 20.0), (11.0, 21.0)]
    assert result["paths"] == [[(10.0, 20.0), (11.0, 20.0), (11.0, 21.0)]]
