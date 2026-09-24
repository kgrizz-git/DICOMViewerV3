"""MONOCHROME1 polarity for the on-screen intensity-projection pane.

The single-slice viewer gets its baseline inversion from ``render_grayscale_image``; these tests
pin the equivalent behaviour for the projection path, which bypasses that function.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydicom.dataset import Dataset

from core import slice_display_pixels as sdp


class _FakeProc:
    """Projection helpers return a fixed 2-D array; window/level clamps to uint8."""

    def __init__(self, array=None) -> None:
        self._array = (
            array
            if array is not None
            else np.array([[10.0, 20.0], [30.0, 240.0]], dtype=np.float32)
        )

    def average_intensity_projection(self, slices):
        _ = slices
        return self._array

    maximum_intensity_projection = average_intensity_projection
    minimum_intensity_projection = average_intensity_projection

    def apply_window_level(self, array, window_center, window_width):
        _ = (window_center, window_width)
        return np.clip(array, 0, 255).astype(np.uint8)


def _studies(photometric_interpretation: str | None, n: int = 3):
    ds = Dataset()
    if photometric_interpretation is not None:
        ds.PhotometricInterpretation = photometric_interpretation
    return {"st": {"sr": [ds for _ in range(n)]}}


def _call(studies, *, ptype="aip", wc=40.0, ww=400.0, proc=None, **kwargs):
    return sdp.create_slice_projection_pil_image(
        dicom_processor=proc or _FakeProc(),
        projection_type=ptype,
        projection_slice_count=3,
        current_studies=studies,
        current_study_uid="st",
        current_series_uid="sr",
        current_slice_index=0,
        window_center=wc,
        window_width=ww,
        use_rescaled_values=False,
        rescale_slope=None,
        rescale_intercept=None,
        **kwargs,
    )


@pytest.mark.parametrize("projection_type", ["aip", "mip", "minip"])
def test_monochrome1_inverts_windowed_projection(projection_type):
    mono1 = _call(_studies("MONOCHROME1"), ptype=projection_type)
    mono2 = _call(_studies("MONOCHROME2"), ptype=projection_type)
    assert mono1 is not None and mono2 is not None
    assert np.array_equal(np.array(mono1), 255 - np.array(mono2))


@pytest.mark.parametrize("projection_type", ["aip", "mip", "minip"])
def test_monochrome1_inverts_normalized_projection(projection_type):
    """The no-window/level branch normalizes to uint8; polarity must apply there too."""
    mono1 = _call(_studies("MONOCHROME1"), ptype=projection_type, wc=None, ww=None)
    mono2 = _call(_studies("MONOCHROME2"), ptype=projection_type, wc=None, ww=None)
    assert mono1 is not None and mono2 is not None
    assert np.array_equal(np.array(mono1), 255 - np.array(mono2))


def test_monochrome2_matches_no_photometric_tag():
    tagged = _call(_studies("MONOCHROME2"))
    untagged = _call(_studies(None))
    assert tagged is not None and untagged is not None
    assert np.array_equal(np.array(tagged), np.array(untagged))


def test_explicit_argument_overrides_dataset_tag():
    from_arg = _call(_studies("MONOCHROME2"), photometric_interpretation="MONOCHROME1")
    from_tag = _call(_studies("MONOCHROME1"))
    assert from_arg is not None and from_tag is not None
    assert np.array_equal(np.array(from_arg), np.array(from_tag))


def test_photometric_interpretation_read_from_series_first_dataset():
    """The fallback uses the series-first dataset, not the slab-start slice."""
    first = Dataset()
    first.PhotometricInterpretation = "MONOCHROME1"
    later = Dataset()
    later.PhotometricInterpretation = "MONOCHROME2"
    studies = {"st": {"sr": [first, later, later]}}

    result = sdp.create_slice_projection_pil_image(
        dicom_processor=_FakeProc(),
        projection_type="aip",
        projection_slice_count=3,
        current_studies=studies,
        current_study_uid="st",
        current_series_uid="sr",
        current_slice_index=1,  # slab starts at the MONOCHROME2 slice
        window_center=40.0,
        window_width=400.0,
        use_rescaled_values=False,
        rescale_slope=None,
        rescale_intercept=None,
    )
    assert result is not None
    assert np.array_equal(np.array(result), 255 - np.array(_call(_studies("MONOCHROME2"))))


def test_reads_photometric_interpretation_through_frame_wrapper_proxy():
    """Multi-frame XA/RF series are per-frame wrappers proxying metadata to the parent."""

    class _FrameProxy:
        def __init__(self, parent):
            self._parent = parent

        def __getattr__(self, name):
            return getattr(self._parent, name)

    parent = Dataset()
    parent.PhotometricInterpretation = "MONOCHROME1"
    studies = {"st": {"sr": [_FrameProxy(parent) for _ in range(3)]}}

    result = _call(studies)
    assert result is not None
    assert np.array_equal(np.array(result), 255 - np.array(_call(_studies("MONOCHROME2"))))


def test_raw_projection_array_is_never_inverted():
    """Invariant 4: the histogram / ROI source stays in stored-value polarity."""
    ds = Dataset()
    ds.PhotometricInterpretation = "MONOCHROME1"
    proc = _FakeProc()
    raw = sdp.compute_intensity_projection_raw_array(proc, "aip", 3, [ds, ds, ds], 0)
    assert raw is not None
    assert np.array_equal(raw, proc._array)
