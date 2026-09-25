"""MONOCHROME1 polarity for exported and cine projection frames.

``export_manager`` and ``cine_video_export`` both skip
``process_image_by_photometric_interpretation`` for projections, and that helper no longer inverts
MONOCHROME1 in any case, so ``create_projection_for_export`` has to own the polarity itself.

The screen==export test is the contract that catches a half-applied change. It compares the two
*builders* directly, which is also the only correct comparison: export deliberately ignores the
manual Invert toggle, so a comparison made through a viewer with Invert on would fail by design.
"""

from __future__ import annotations

import numpy as np
import pytest
from pydicom.dataset import Dataset

from core import slice_display_pixels as sdp
from gui import export_rendering as _er

_PROJECTION = np.array([[10.0, 20.0], [30.0, 240.0]], dtype=np.float32)


class _FakeProc:
    def __init__(self, array=None) -> None:
        self._array = _PROJECTION if array is None else array

    def average_intensity_projection(self, slices):
        _ = slices
        return self._array

    maximum_intensity_projection = average_intensity_projection
    minimum_intensity_projection = average_intensity_projection

    def apply_window_level(self, array, window_center, window_width):
        _ = (window_center, window_width)
        return np.clip(array, 0, 255).astype(np.uint8)


@pytest.fixture
def patched_processor(monkeypatch):
    """Point the export path's DICOMProcessor statics at the same fake maths the viewer uses."""
    proc = _FakeProc()
    monkeypatch.setattr(
        _er.DICOMProcessor, "average_intensity_projection", staticmethod(proc.average_intensity_projection)
    )
    monkeypatch.setattr(
        _er.DICOMProcessor, "maximum_intensity_projection", staticmethod(proc.maximum_intensity_projection)
    )
    monkeypatch.setattr(
        _er.DICOMProcessor, "minimum_intensity_projection", staticmethod(proc.minimum_intensity_projection)
    )
    monkeypatch.setattr(
        _er.DICOMProcessor, "apply_window_level", staticmethod(proc.apply_window_level)
    )
    return proc


def _dataset(photometric_interpretation: str | None) -> Dataset:
    ds = Dataset()
    if photometric_interpretation is not None:
        ds.PhotometricInterpretation = photometric_interpretation
    return ds


def _export(dataset, *, projection_type="aip", wc=40.0, ww=400.0):
    studies = {"st": {"sr": [dataset, dataset, dataset]}}
    return _er.create_projection_for_export(
        dataset, studies, "st", "sr", 0, projection_type, 3, wc, ww, False
    )


def _screen(dataset, *, projection_type="aip", wc=40.0, ww=400.0):
    studies = {"st": {"sr": [dataset, dataset, dataset]}}
    return sdp.create_slice_projection_pil_image(
        dicom_processor=_FakeProc(),
        projection_type=projection_type,
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
    )


@pytest.mark.parametrize("projection_type", ["aip", "mip", "minip"])
def test_export_projection_inverts_monochrome1(patched_processor, projection_type):
    mono1 = _export(_dataset("MONOCHROME1"), projection_type=projection_type)
    mono2 = _export(_dataset("MONOCHROME2"), projection_type=projection_type)
    assert mono1 is not None and mono2 is not None
    assert np.array_equal(np.array(mono1), 255 - np.array(mono2))


def test_export_projection_leaves_monochrome2_alone(patched_processor):
    tagged = _export(_dataset("MONOCHROME2"))
    untagged = _export(_dataset(None))
    assert tagged is not None and untagged is not None
    assert np.array_equal(np.array(tagged), np.array(untagged))


@pytest.mark.parametrize("projection_type", ["aip", "mip", "minip"])
@pytest.mark.parametrize("photometric_interpretation", ["MONOCHROME1", "MONOCHROME2"])
def test_screen_and_export_projections_match(
    patched_processor, projection_type, photometric_interpretation
):
    """The contract: what the pane shows is what the export writes, for the same slab and W/L."""
    dataset = _dataset(photometric_interpretation)
    on_screen = _screen(dataset, projection_type=projection_type)
    exported = _export(dataset, projection_type=projection_type)
    assert on_screen is not None and exported is not None
    assert np.array_equal(np.array(on_screen), np.array(exported))


@pytest.mark.parametrize("photometric_interpretation", ["MONOCHROME1", "MONOCHROME2"])
def test_screen_and_export_match_on_the_normalize_branch(
    patched_processor, photometric_interpretation
):
    """No window/level: both builders normalize to uint8, and polarity must still agree."""
    dataset = _dataset(photometric_interpretation)
    on_screen = _screen(dataset, wc=None, ww=None)
    exported = _export(dataset, wc=None, ww=None)
    assert on_screen is not None and exported is not None
    assert np.array_equal(np.array(on_screen), np.array(exported))


def test_export_reads_photometric_interpretation_from_series_first_dataset(patched_processor):
    """Both builders use the series-first dataset, so a mixed-PI series cannot diverge."""
    first = _dataset("MONOCHROME1")
    later = _dataset("MONOCHROME2")
    studies = {"st": {"sr": [first, later, later]}}

    # The current dataset passed to export is the MONOCHROME2 one; series-first must win.
    exported = _er.create_projection_for_export(
        later, studies, "st", "sr", 1, "aip", 3, 40.0, 400.0, False
    )
    on_screen = sdp.create_slice_projection_pil_image(
        dicom_processor=_FakeProc(),
        projection_type="aip",
        projection_slice_count=3,
        current_studies=studies,
        current_study_uid="st",
        current_series_uid="sr",
        current_slice_index=1,
        window_center=40.0,
        window_width=400.0,
        use_rescaled_values=False,
        rescale_slope=None,
        rescale_intercept=None,
    )
    assert exported is not None and on_screen is not None
    assert np.array_equal(np.array(exported), np.array(on_screen))
    assert np.array_equal(np.array(exported), 255 - np.array(_export(_dataset("MONOCHROME2"))))


def test_photometric_helper_still_does_not_invert_monochrome1():
    """Guards the predecessor plan's invariant: export must not re-invert on top of the builder."""
    from PIL import Image

    image = Image.fromarray(np.array([[0, 100, 255]], dtype=np.uint8), mode="L")
    out = _er.process_image_by_photometric_interpretation(image, _dataset("MONOCHROME1"))
    assert np.array_equal(np.array(out), np.array(image))
