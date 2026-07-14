"""Tests for raw projection helper used by histogram projection mode."""

from __future__ import annotations

import numpy as np

from core.slice_display_pixels import compute_intensity_projection_raw_array


class _FakeDICOMProcessor:
    def average_intensity_projection(self, slices):
        _ = slices
        return np.array([[1, 2], [3, 4]], dtype=np.float32)

    def maximum_intensity_projection(self, slices):
        _ = slices
        return np.array([[5, 6], [7, 8]], dtype=np.float32)

    def minimum_intensity_projection(self, slices):
        _ = slices
        return np.array([[0, 1], [1, 0]], dtype=np.float32)


def test_projection_raw_array_respects_slice_window() -> None:
    processor = _FakeDICOMProcessor()
    series = [object(), object(), object()]

    out = compute_intensity_projection_raw_array(
        dicom_processor=processor,
        projection_type="mip",
        projection_slice_count=2,
        series_datasets=series,
        current_slice_index=1,
    )

    assert out is not None
    assert np.array_equal(out, np.array([[5, 6], [7, 8]], dtype=np.float32))


def test_projection_raw_array_requires_two_slices() -> None:
    processor = _FakeDICOMProcessor()
    series = [object()]

    out = compute_intensity_projection_raw_array(
        dicom_processor=processor,
        projection_type="aip",
        projection_slice_count=3,
        series_datasets=series,
        current_slice_index=0,
    )

    assert out is None
