"""Tests for core.dicom_pixel_range — tag-only stored pixel-value range helper."""

from __future__ import annotations

from pydicom.dataset import Dataset

from core.dicom_pixel_range import get_stored_value_range
from core.dicom_processor import DICOMProcessor


def _make_dataset(
    *,
    bits_allocated: int = 16,
    bits_stored: int | None = None,
    high_bit: int | None = None,
    pixel_representation: int = 0,
) -> Dataset:
    ds = Dataset()
    ds.BitsAllocated = bits_allocated
    if bits_stored is not None:
        ds.BitsStored = bits_stored
    if high_bit is not None:
        ds.HighBit = high_bit
    ds.PixelRepresentation = pixel_representation
    return ds


class TestGetStoredValueRange:
    def test_16bit_unsigned(self):
        ds = _make_dataset(bits_allocated=16, bits_stored=16, high_bit=15)
        assert get_stored_value_range(ds) == (0.0, 65535.0)

    def test_12bit_unsigned(self):
        ds = _make_dataset(bits_allocated=16, bits_stored=12, high_bit=11)
        assert get_stored_value_range(ds) == (0.0, 4095.0)

    def test_10bit_unsigned(self):
        ds = _make_dataset(bits_allocated=16, bits_stored=10, high_bit=9)
        assert get_stored_value_range(ds) == (0.0, 1023.0)

    def test_14bit_unsigned(self):
        ds = _make_dataset(bits_allocated=16, bits_stored=14, high_bit=13)
        assert get_stored_value_range(ds) == (0.0, 16383.0)

    def test_16bit_signed(self):
        ds = _make_dataset(bits_allocated=16, bits_stored=16, high_bit=15, pixel_representation=1)
        assert get_stored_value_range(ds) == (-32768.0, 32767.0)

    def test_12bit_signed(self):
        ds = _make_dataset(bits_allocated=16, bits_stored=12, high_bit=11, pixel_representation=1)
        assert get_stored_value_range(ds) == (-2048.0, 2047.0)

    def test_missing_bits_stored_falls_back_to_bits_allocated(self):
        ds = _make_dataset(bits_allocated=10)
        assert get_stored_value_range(ds) == (0.0, 1023.0)

    def test_zero_bits_stored_falls_back_to_bits_allocated(self):
        ds = _make_dataset(bits_allocated=12, bits_stored=0)
        assert get_stored_value_range(ds) == (0.0, 4095.0)

    def test_bits_stored_exceeds_bits_allocated_clamped(self):
        ds = _make_dataset(bits_allocated=12, bits_stored=16, high_bit=15)
        assert get_stored_value_range(ds) == (0.0, 4095.0)

    def test_missing_high_bit_no_crash(self):
        ds = _make_dataset(bits_allocated=16, bits_stored=12)
        assert get_stored_value_range(ds) == (0.0, 4095.0)

    def test_missing_bits_allocated_defaults_to_16(self):
        ds = Dataset()
        ds.BitsStored = 12
        ds.PixelRepresentation = 0
        assert get_stored_value_range(ds) == (0.0, 4095.0)

    def test_non_zero_width_guarantee(self):
        ds = _make_dataset(bits_allocated=1, bits_stored=1, high_bit=0)
        stored_min, stored_max = get_stored_value_range(ds)
        assert stored_max > stored_min


class TestDICOMProcessorWrapper:
    def test_static_method_delegates(self):
        ds = _make_dataset(bits_allocated=16, bits_stored=16, high_bit=15)
        assert DICOMProcessor.get_stored_value_range(ds) == (0.0, 65535.0)
