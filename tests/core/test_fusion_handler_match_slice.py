"""Tests for FusionHandler FoR match, slice matching, and alignment cache."""

from __future__ import annotations

from pydicom.dataset import Dataset

from core.fusion_handler import FusionHandler, OverlayMatchResult


def _ds(*, for_uid: str = "1.2.3", z: float = 0.0, loc: float | None = None) -> Dataset:
    ds = Dataset()
    ds.FrameOfReferenceUID = for_uid
    ds.ImagePositionPatient = [0.0, 0.0, z]
    if loc is not None:
        ds.SliceLocation = loc
    ds.PixelSpacing = [1.0, 1.0]
    return ds


def test_frame_of_reference_match() -> None:
    h = FusionHandler()
    a = [_ds(for_uid="1.2.3")]
    b = [_ds(for_uid="1.2.3")]
    c = [_ds(for_uid="9.9.9")]
    assert h.check_frame_of_reference_match(a, b) is True
    assert h.check_frame_of_reference_match(a, c) is False


def test_get_slice_location_prefers_tag() -> None:
    h = FusionHandler()
    ds = _ds(z=99.0, loc=12.5)
    assert h.get_slice_location(ds) == 12.5


def test_find_matching_slice_exact() -> None:
    h = FusionHandler()
    base = [_ds(z=0.0), _ds(z=5.0), _ds(z=10.0)]
    overlay = [_ds(z=0.0), _ds(z=5.0), _ds(z=10.0)]
    h.set_overlay_series("over")
    idx1, idx2 = h.find_matching_slice(1, base, overlay)
    assert idx1 == 1
    assert idx2 is None


def test_find_matching_with_classification_inside() -> None:
    h = FusionHandler()
    base = [_ds(z=0.0), _ds(z=10.0)]
    overlay = [_ds(z=0.0), _ds(z=10.0)]
    h.set_overlay_series("over")
    kind, i1, i2 = h.find_matching_slice_with_classification(0, base, overlay)
    assert kind == OverlayMatchResult.inside
    assert i1 == 0
    assert i2 is None


def test_find_matching_above_stack() -> None:
    h = FusionHandler()
    base = [_ds(z=100.0)]
    overlay = [_ds(z=0.0), _ds(z=10.0)]
    h.set_overlay_series("over")
    kind, i1, i2 = h.find_matching_slice_with_classification(0, base, overlay)
    assert kind == OverlayMatchResult.above_stack
    assert i1 is None and i2 is None


def test_alignment_cache_roundtrip() -> None:
    h = FusionHandler()
    h.set_alignment("base", "over", (1.0, 1.0), (2.0, 3.0))
    got = h.get_alignment("base", "over")
    assert got is not None
    assert got["scale"] == (1.0, 1.0)
    assert got["offset"] == (2.0, 3.0)
    h.clear_alignment_cache("base")
    assert h.get_alignment("base", "over") is None
