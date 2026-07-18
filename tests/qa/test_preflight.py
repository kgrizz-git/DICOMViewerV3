"""Tests for qa.preflight slice-geometry and modality preflight checks."""

from __future__ import annotations

from types import SimpleNamespace

from pydicom.dataset import Dataset

from qa import preflight

_AXIAL = [1, 0, 0, 0, 1, 0]  # normal = +z


def _slice(z: float, iop=None, ipp=None) -> Dataset:
    ds = Dataset()
    ds.ImagePositionPatient = ipp if ipp is not None else [0.0, 0.0, z]
    ds.ImageOrientationPatient = iop if iop is not None else list(_AXIAL)
    return ds


def test_fewer_than_two_slices_no_warnings() -> None:
    assert preflight.collect_slice_position_warnings([_slice(0)]) == []


def test_monotonic_increasing_no_warnings() -> None:
    out = preflight.collect_slice_position_warnings([_slice(0), _slice(1), _slice(2)])
    assert out == []


def test_monotonic_decreasing_no_warnings() -> None:
    out = preflight.collect_slice_position_warnings([_slice(2), _slice(1), _slice(0)])
    assert out == []


def test_non_monotonic_warns() -> None:
    out = preflight.collect_slice_position_warnings([_slice(0), _slice(2), _slice(1)])
    assert any("not monotonic" in w for w in out)


def test_duplicate_positions_warn() -> None:
    out = preflight.collect_slice_position_warnings([_slice(0), _slice(0)])
    assert any("Duplicate or near-duplicate" in w for w in out)


def test_missing_tags_warns() -> None:
    ds = Dataset()  # no IPP/IOP
    out = preflight.collect_slice_position_warnings([_slice(0), ds])
    assert any("missing or invalid" in w for w in out)


def test_invalid_values_warn() -> None:
    # pydicom rejects non-numeric DS at assignment, so use a duck-typed slice
    # (the checker reads the tags via getattr).
    bad = SimpleNamespace(
        ImagePositionPatient=["x", "y", "z"],
        ImageOrientationPatient=list(_AXIAL),
    )
    out = preflight.collect_slice_position_warnings([_slice(1), bad])
    assert any("missing or invalid" in w for w in out)


def test_short_vectors_warn() -> None:
    bad = _slice(0)
    bad.ImagePositionPatient = [0.0, 0.0]  # len < 3
    out = preflight.collect_slice_position_warnings([_slice(1), bad])
    assert any("missing or invalid" in w for w in out)


def test_degenerate_orientation_warns() -> None:
    # row parallel to col -> zero normal
    degen = _slice(0, iop=[1, 0, 0, 1, 0, 0])
    other = _slice(1, iop=[1, 0, 0, 1, 0, 0])
    out = preflight.collect_slice_position_warnings([degen, other])
    assert any("degenerate" in w for w in out)


def test_modality_match_returns_none() -> None:
    assert preflight.modality_preflight_warning("CT", "ct") is None


def test_modality_mismatch_warns() -> None:
    msg = preflight.modality_preflight_warning("MR", "CT")
    assert msg is not None and "targets CT" in msg


def test_modality_empty_returns_none() -> None:
    assert preflight.modality_preflight_warning("", "CT") is None
    assert preflight.modality_preflight_warning("CT", "") is None
