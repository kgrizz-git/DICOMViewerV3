"""
Tests for viewer pylinac subclasses (relaxed image index bounds).

Uses a minimal dummy with _RelaxedImageExtentMixin; full ACRCT construction
is not required.
"""

from __future__ import annotations

import pytest

from qa.pylinac_extent_subclasses import _RelaxedImageExtentMixin


class _DummyStack(_RelaxedImageExtentMixin):
    """Minimal stand-in: only ``num_images`` is used by _is_within_image_extent."""

    def __init__(self, n: int) -> None:
        self._n = n

    @property
    def num_images(self) -> int:
        return self._n


def test_relaxed_image_extent_accepts_first_and_last_slice() -> None:
    d = _DummyStack(25)
    assert d._is_within_image_extent(0) is True
    assert d._is_within_image_extent(1) is True
    assert d._is_within_image_extent(24) is True


def test_relaxed_image_extent_rejects_out_of_range() -> None:
    d = _DummyStack(5)
    with pytest.raises(ValueError):
        d._is_within_image_extent(-1)
    with pytest.raises(ValueError):
        d._is_within_image_extent(5)


def test_build_profile_marks_relaxed_image_for_forviewer_engine() -> None:
    from qa.analysis_types import QARequest, build_pylinac_analysis_profile

    req = QARequest(analysis_type="acr_ct", dicom_paths=[])
    p = build_pylinac_analysis_profile(req, engine="ACRCTForViewer")
    assert p["relaxed_image_extent"] is True
    assert p["vanilla_equivalent"] is False
    assert p["vanilla_pylinac"] is False

    p2 = build_pylinac_analysis_profile(req, engine="ACRCT")
    assert p2["relaxed_image_extent"] is False

    req_v = QARequest(
        analysis_type="acr_ct", dicom_paths=[], vanilla_pylinac=True
    )
    pv = build_pylinac_analysis_profile(req_v, engine="ACRCT")
    assert pv["vanilla_pylinac"] is True
    assert pv["relaxed_image_extent"] is False
