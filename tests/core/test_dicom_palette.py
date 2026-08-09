"""
Tests for ``core.dicom_palette`` — PALETTE COLOR LUT handling.

No Qt or DICOM files needed; all datasets are built in-test.
"""

from __future__ import annotations

import numpy as np
from pydicom.dataset import Dataset

from core.dicom_palette import (
    _apply_one_lut,
    apply_palette_luts,
    convert_palette_color_to_rgb,
    extract_indexed_array,
    read_palette_lut,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lut_bytes(values: list[int], bits: int = 8) -> bytes:
    """Return a LUT byte string from a list of integer values."""
    dt = np.uint8 if bits == 8 else np.uint16
    return np.array(values, dtype=dt).tobytes()


def _palette_dataset(
    n_entries: int = 256,
    first_value: int = 0,
    bits: int = 8,
    red: list[int] | None = None,
    green: list[int] | None = None,
    blue: list[int] | None = None,
) -> Dataset:
    """Build a minimal palette-color dataset."""
    ds = Dataset()
    if red is None:
        red = list(range(n_entries))
    if green is None:
        green = [0] * n_entries
    if blue is None:
        blue = [255] * n_entries

    for prefix, values in (("Red", red), ("Green", green), ("Blue", blue)):
        descriptor_attr = f"{prefix}PaletteColorLookupTableDescriptor"
        data_attr = f"{prefix}PaletteColorLookupTableData"
        # DICOM descriptor: [n_entries, first_value, bits_allocated]
        setattr(ds, descriptor_attr, [n_entries, first_value, bits])
        setattr(ds, data_attr, _make_lut_bytes(values, bits=bits))

    return ds


# ---------------------------------------------------------------------------
# read_palette_lut
# ---------------------------------------------------------------------------


class TestReadPaletteLut:
    def test_returns_none_when_descriptor_absent(self):
        ds = Dataset()
        lut, first = read_palette_lut(ds, "Red")
        assert lut is None
        assert first is None

    def test_returns_lut_array_and_first_value_8bit(self):
        values = list(range(256))
        ds = _palette_dataset(red=values)
        lut, first = read_palette_lut(ds, "Red")
        assert lut is not None
        assert len(lut) == 256
        assert first == 0

    def test_returns_lut_with_non_zero_first_value(self):
        ds = _palette_dataset(n_entries=128, first_value=64)
        _, first = read_palette_lut(ds, "Red")
        assert first == 64

    def test_16bit_lut(self):
        values = [i * 256 for i in range(256)]
        ds = Dataset()
        ds.RedPaletteColorLookupTableDescriptor = [256, 0, 16]
        ds.RedPaletteColorLookupTableData = _make_lut_bytes(values, bits=16)
        lut, first = read_palette_lut(ds, "Red")
        assert lut is not None
        assert lut.dtype == np.uint16
        assert first == 0

    def test_lut_from_list_type(self):
        ds = Dataset()
        ds.GreenPaletteColorLookupTableDescriptor = [4, 0, 8]
        ds.GreenPaletteColorLookupTableData = [10, 20, 30, 40]
        lut, first = read_palette_lut(ds, "Green")
        assert lut is not None
        assert list(lut) == [10, 20, 30, 40]

    def test_descriptor_not_sequence_uses_defaults(self):
        """Non-sequence descriptor falls back to first_value=0, bits=8."""
        ds = Dataset()
        ds.RedPaletteColorLookupTableDescriptor = "bad"
        ds.RedPaletteColorLookupTableData = bytes(range(4))
        lut, first = read_palette_lut(ds, "Red")
        assert lut is not None
        assert first == 0


# ---------------------------------------------------------------------------
# extract_indexed_array
# ---------------------------------------------------------------------------


class TestExtractIndexedArray:
    def test_2d_passthrough(self):
        arr = np.arange(6, dtype=np.uint8).reshape(2, 3)
        out = extract_indexed_array(arr)
        assert out.shape == (2, 3)

    def test_3d_single_channel_drops_last_dim(self):
        arr = np.arange(6, dtype=np.uint8).reshape(2, 3, 1)
        out = extract_indexed_array(arr)
        assert out.shape == (2, 3)

    def test_4d_returns_first_frame(self):
        arr = np.zeros((5, 4, 3, 1), dtype=np.uint8)
        arr[0, :, :, 0] = np.arange(12).reshape(4, 3)
        out = extract_indexed_array(arr)
        assert out.shape == (4, 3)

    def test_4d_multi_channel_preserves_channels_in_first_frame(self):
        arr = np.zeros((3, 4, 5, 3), dtype=np.uint8)
        out = extract_indexed_array(arr)
        assert out.shape == (4, 5, 3)


# ---------------------------------------------------------------------------
# _apply_one_lut
# ---------------------------------------------------------------------------


class TestApplyOneLut:
    def test_identity_mapping(self):
        lut = np.arange(256, dtype=np.uint8)
        indexed = np.array([[0, 100, 255]], dtype=np.uint8)
        out = _apply_one_lut(indexed, lut, 0, 255)
        np.testing.assert_array_equal(out, [[0, 100, 255]])

    def test_first_value_shifts_indices(self):
        lut = np.array([10, 20, 30, 40], dtype=np.uint8)
        indexed = np.array([[1, 2]], dtype=np.uint8)
        # first_value=1 shifts: index 1 -> lut[0]=10, index 2 -> lut[1]=20
        out = _apply_one_lut(indexed, lut, first_value=1, clamp_max=3)
        np.testing.assert_array_equal(out, [[10, 20]])

    def test_clamps_below_zero(self):
        lut = np.array([99, 88, 77], dtype=np.uint8)
        indexed = np.array([[0]], dtype=np.uint8)
        # first_value=5 => 0-5=-5 => clamped to 0
        out = _apply_one_lut(indexed, lut, first_value=5, clamp_max=2)
        np.testing.assert_array_equal(out, [[99]])

    def test_16bit_lut_normalized_to_8bit(self):
        lut_16 = np.array([0, 65535], dtype=np.uint16)
        indexed = np.array([[0, 1]], dtype=np.uint8)
        out = _apply_one_lut(indexed, lut_16, 0, 1)
        assert out[0, 0] == 0
        assert out[0, 1] == 255


# ---------------------------------------------------------------------------
# apply_palette_luts
# ---------------------------------------------------------------------------


class TestApplyPaletteLuts:
    def test_output_shape_2d_indexed(self):
        lut = np.arange(256, dtype=np.uint8)
        indexed = np.zeros((4, 4), dtype=np.uint8)
        out = apply_palette_luts(indexed, lut, lut, lut, 0, 0, 0)
        assert out.shape == (4, 4, 3)

    def test_channels_match_separate_luts(self):
        red = np.full(256, 100, dtype=np.uint8)
        green = np.full(256, 150, dtype=np.uint8)
        blue = np.full(256, 200, dtype=np.uint8)
        indexed = np.array([[0, 127]], dtype=np.uint8)
        out = apply_palette_luts(indexed, red, green, blue, 0, 0, 0)
        assert out.shape == (1, 2, 3)
        assert out[0, 0, 0] == 100  # red
        assert out[0, 0, 1] == 150  # green
        assert out[0, 0, 2] == 200  # blue


# ---------------------------------------------------------------------------
# convert_palette_color_to_rgb
# ---------------------------------------------------------------------------


class TestConvertPaletteColorToRgb:
    def test_successful_conversion_returns_rgb_and_true(self):
        ds = _palette_dataset(
            red=list(range(256)),
            green=[0] * 256,
            blue=[255] * 256,
        )
        pixel_array = np.arange(16, dtype=np.uint8).reshape(4, 4)
        rgb, did_convert = convert_palette_color_to_rgb(pixel_array, ds)
        assert did_convert is True
        assert rgb.shape == (4, 4, 3)

    def test_missing_lut_returns_original_and_false(self):
        ds = Dataset()  # no LUT tags
        pixel_array = np.zeros((4, 4), dtype=np.uint8)
        out, did_convert = convert_palette_color_to_rgb(pixel_array, ds)
        assert did_convert is False
        np.testing.assert_array_equal(out, pixel_array)

    def test_exception_in_lut_returns_original_and_false(self):
        """Corrupt descriptor should be handled gracefully."""
        ds = Dataset()
        ds.RedPaletteColorLookupTableDescriptor = None  # will cause AttributeError
        pixel_array = np.zeros((2, 2), dtype=np.uint8)
        out, did_convert = convert_palette_color_to_rgb(pixel_array, ds)
        assert did_convert is False
        np.testing.assert_array_equal(out, pixel_array)
