"""Tests for core.slice_display_pixels intensity-projection pipeline.

Uses a fake DICOMProcessor exposing the projection + window/level methods, so
no real DICOM pixel decoding is required.
"""

from __future__ import annotations

import numpy as np
from pydicom.dataset import Dataset

from core import slice_display_pixels as sdp


class _FakeProc:
    """Projection helpers return a fixed 2-D array; window/level clamps to uint8."""

    def __init__(self, array=None) -> None:
        self._array = array if array is not None else np.array([[10.0, 20.0], [30.0, 40.0]], dtype=np.float32)

    def average_intensity_projection(self, slices):
        _ = slices
        return self._array

    maximum_intensity_projection = average_intensity_projection
    minimum_intensity_projection = average_intensity_projection

    def apply_window_level(self, array, window_center, window_width):
        _ = (window_center, window_width)
        return np.clip(array, 0, 255).astype(np.uint8)


def _studies(n=3):
    ds = Dataset()
    return {"st": {"sr": [ds for _ in range(n)]}}


def _call(proc, studies, *, ptype="aip", count=3, idx=0, wc=40.0, ww=400.0,
          rescale=False, slope=None, intercept=None):
    return sdp.create_slice_projection_pil_image(
        dicom_processor=proc,
        projection_type=ptype,
        projection_slice_count=count,
        current_studies=studies,
        current_study_uid="st",
        current_series_uid="sr",
        current_slice_index=idx,
        window_center=wc,
        window_width=ww,
        use_rescaled_values=rescale,
        rescale_slope=slope,
        rescale_intercept=intercept,
    )


def test_returns_none_when_no_studies() -> None:
    assert _call(_FakeProc(), {}) is None


def test_returns_none_when_series_missing() -> None:
    assert _call(_FakeProc(), {"st": {}}) is None


def test_returns_none_when_fewer_than_two_slices() -> None:
    assert _call(_FakeProc(), _studies(1)) is None


def test_returns_none_when_range_too_small() -> None:
    # projection_slice_count=1 -> end==start -> range < 2
    assert _call(_FakeProc(), _studies(3), count=1) is None


def test_returns_none_for_unknown_projection_type() -> None:
    assert _call(_FakeProc(), _studies(3), ptype="bogus") is None


def test_aip_with_window_level_returns_grayscale() -> None:
    img = _call(_FakeProc(), _studies(3))
    assert img is not None
    assert img.mode == "L"


def test_mip_auto_normalizes_without_window_level() -> None:
    img = _call(_FakeProc(), _studies(3), ptype="mip", wc=None, ww=None)
    assert img is not None
    assert img.mode == "L"


def test_rescale_applied_when_requested() -> None:
    img = _call(_FakeProc(), _studies(3), rescale=True, slope=2.0, intercept=-10.0, wc=None, ww=None)
    assert img is not None


def test_rgb_projection_returns_rgb_mode() -> None:
    rgb = np.zeros((2, 2, 3), dtype=np.float32)
    rgb[..., 0] = 255.0
    img = _call(_FakeProc(rgb), _studies(3), wc=None, ww=None)
    assert img is not None
    assert img.mode == "RGB"


def test_projection_none_returns_none() -> None:
    class _NoneProc(_FakeProc):
        def average_intensity_projection(self, slices):
            return None
        maximum_intensity_projection = average_intensity_projection
        minimum_intensity_projection = average_intensity_projection

    assert _call(_NoneProc(), _studies(3)) is None


# --------------------------------------------------------------------------- #
# compute_intensity_projection_raw_array
# --------------------------------------------------------------------------- #

def test_raw_array_too_few_slices() -> None:
    ds = Dataset()
    assert sdp.compute_intensity_projection_raw_array(_FakeProc(), "aip", 3, [ds], 0) is None


def test_raw_array_range_too_small() -> None:
    ds = Dataset()
    assert sdp.compute_intensity_projection_raw_array(_FakeProc(), "aip", 1, [ds, ds], 0) is None


def test_raw_array_returns_projection() -> None:
    ds = Dataset()
    arr = sdp.compute_intensity_projection_raw_array(_FakeProc(), "mip", 3, [ds, ds, ds], 0)
    assert isinstance(arr, np.ndarray)


def test_raw_array_unknown_type_returns_none() -> None:
    ds = Dataset()
    assert sdp.compute_intensity_projection_raw_array(_FakeProc(), "nope", 3, [ds, ds], 0) is None
