"""Tests for core.slice_location_line_helper.

Geometry primitives (plane intersection / projection / clipping) are covered
elsewhere; here we cover this module's own logic: image-size and
frame-of-reference lookups, effective slab-thickness rules, and the
segment-assembly dispatch (with _compute_segment stubbed to a canned segment).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from pydicom.dataset import Dataset

from core import slice_location_line_helper as helper
from core.slice_geometry import SlicePlane


def _plane(origin=(0.0, 0.0, 0.0)) -> SlicePlane:
    return SlicePlane(
        origin=np.array(origin, dtype=float),
        row_cosine=np.array([1.0, 0.0, 0.0]),
        col_cosine=np.array([0.0, 1.0, 0.0]),
        row_spacing=1.0,
        col_spacing=1.0,
    )


class _Coord:
    def __init__(self, planes, thickness=None) -> None:
        self._planes = planes
        self._thickness = thickness

    def get_current_plane(self, idx):
        return self._planes.get(idx)

    def get_slice_thickness(self, idx):
        return self._thickness


def _dicom_data(rows=4, cols=6, for_uid="FOR1") -> dict:
    ds = Dataset()
    ds.Rows = rows
    ds.Columns = cols
    if for_uid is not None:
        ds.FrameOfReferenceUID = for_uid
    return {"current_dataset": ds}


# --------------------------------------------------------------------------- #
# _make_offset_plane
# --------------------------------------------------------------------------- #

def test_make_offset_plane_shifts_origin_along_normal() -> None:
    plane = _plane()
    shifted = helper._make_offset_plane(plane, 5.0)
    # normal of (x,y) plane is +z, so origin moves by (0,0,5).
    assert np.allclose(shifted.origin, [0.0, 0.0, 5.0])
    assert np.allclose(shifted.row_cosine, plane.row_cosine)


# --------------------------------------------------------------------------- #
# _get_image_size
# --------------------------------------------------------------------------- #

def test_get_image_size_dicom() -> None:
    app = SimpleNamespace(subwindow_data={0: _dicom_data(rows=4, cols=6)})
    assert helper._get_image_size(app, 0) == (6.0, 4.0)


def test_get_image_size_no_dataset() -> None:
    app = SimpleNamespace(subwindow_data={0: {"current_dataset": None}})
    assert helper._get_image_size(app, 0) == (None, None)


def test_get_image_size_bad_rows() -> None:
    ds = Dataset()  # no Rows/Columns -> AttributeError path
    app = SimpleNamespace(subwindow_data={0: {"current_dataset": ds}})
    assert helper._get_image_size(app, 0) == (None, None)


def test_get_image_size_mpr() -> None:
    mpr = SimpleNamespace(slices=[np.zeros((3, 5))])
    app = SimpleNamespace(subwindow_data={0: {"is_mpr": True, "mpr_result": mpr}})
    assert helper._get_image_size(app, 0) == (5.0, 3.0)


def test_get_image_size_mpr_empty_slices() -> None:
    mpr = SimpleNamespace(slices=[])
    app = SimpleNamespace(subwindow_data={0: {"is_mpr": True, "mpr_result": mpr}})
    assert helper._get_image_size(app, 0) == (None, None)


# --------------------------------------------------------------------------- #
# _get_frame_of_reference_uid
# --------------------------------------------------------------------------- #

def test_for_uid_from_dataset() -> None:
    app = SimpleNamespace(subwindow_data={0: _dicom_data(for_uid="ABC")})
    assert helper._get_frame_of_reference_uid(app, 0) == "ABC"


def test_for_uid_none_when_no_dataset() -> None:
    app = SimpleNamespace(subwindow_data={0: {"current_dataset": None}})
    assert helper._get_frame_of_reference_uid(app, 0) is None


def test_for_uid_from_mpr_source_volume() -> None:
    src_ds = SimpleNamespace(FrameOfReferenceUID="MPRFOR")
    vol = SimpleNamespace(source_datasets=[src_ds])
    mpr = SimpleNamespace(source_volume=vol)
    app = SimpleNamespace(subwindow_data={0: {"is_mpr": True, "mpr_result": mpr}})
    assert helper._get_frame_of_reference_uid(app, 0) == "MPRFOR"


# --------------------------------------------------------------------------- #
# _get_source_plane_thickness_mm
# --------------------------------------------------------------------------- #

def test_thickness_none_when_unavailable() -> None:
    app = SimpleNamespace(subwindow_data={}, subwindow_managers={})
    assert helper._get_source_plane_thickness_mm(app, _Coord({}, thickness=None), 0) is None


def test_thickness_non_numeric_returns_none() -> None:
    app = SimpleNamespace(subwindow_data={}, subwindow_managers={})
    assert helper._get_source_plane_thickness_mm(app, _Coord({}, thickness="x"), 0) is None


def test_thickness_plain_series() -> None:
    app = SimpleNamespace(subwindow_data={0: {}}, subwindow_managers={0: {}})
    assert helper._get_source_plane_thickness_mm(app, _Coord({}, thickness=2.5), 0) == 2.5


def test_thickness_mpr_combine() -> None:
    app = SimpleNamespace(
        subwindow_data={0: {"is_mpr": True, "mpr_combine_enabled": True,
                            "mpr_combine_slice_count": 4}},
        subwindow_managers={0: {}},
    )
    assert helper._get_source_plane_thickness_mm(app, _Coord({}, thickness=2.0), 0) == 8.0


def test_thickness_projection() -> None:
    sdm = SimpleNamespace(projection_enabled=True, projection_slice_count=3)
    app = SimpleNamespace(
        subwindow_data={0: {}},
        subwindow_managers={0: {"slice_display_manager": sdm}},
    )
    assert helper._get_source_plane_thickness_mm(app, _Coord({}, thickness=2.0), 0) == 6.0


# --------------------------------------------------------------------------- #
# get_slice_location_line_segments — early returns and dispatch
# --------------------------------------------------------------------------- #

def test_segments_no_coordinator() -> None:
    app = SimpleNamespace(_slice_sync_coordinator=None)
    assert helper.get_slice_location_line_segments(0, app) == []


def test_segments_no_target_plane() -> None:
    app = SimpleNamespace(_slice_sync_coordinator=_Coord({}))
    assert helper.get_slice_location_line_segments(0, app) == []


def test_segments_bad_image_size() -> None:
    app = SimpleNamespace(
        _slice_sync_coordinator=_Coord({0: _plane()}),
        subwindow_data={0: {"current_dataset": None}},
    )
    assert helper.get_slice_location_line_segments(0, app) == []


def test_segments_middle_mode(monkeypatch) -> None:
    monkeypatch.setattr(helper, "_compute_segment", lambda *a: (0.0, 0.0, 10.0, 10.0))
    app = SimpleNamespace(
        _slice_sync_coordinator=_Coord({0: _plane(), 1: _plane((0, 0, 5))}),
        subwindow_data={0: _dicom_data(), 1: _dicom_data()},
    )
    segs = helper.get_slice_location_line_segments(0, app, other_indices=[1])
    assert len(segs) == 1
    assert segs[0]["line_id"] == "middle:1"
    assert segs[0]["source_idx"] == 1


def test_segments_skips_different_frame_of_reference(monkeypatch) -> None:
    monkeypatch.setattr(helper, "_compute_segment", lambda *a: (0.0, 0.0, 10.0, 10.0))
    app = SimpleNamespace(
        _slice_sync_coordinator=_Coord({0: _plane(), 1: _plane()}),
        subwindow_data={0: _dicom_data(for_uid="A"), 1: _dicom_data(for_uid="B")},
    )
    assert helper.get_slice_location_line_segments(0, app, other_indices=[1]) == []


def test_segments_begin_end_mode(monkeypatch) -> None:
    monkeypatch.setattr(helper, "_compute_segment", lambda *a: (0.0, 0.0, 10.0, 10.0))
    app = SimpleNamespace(
        _slice_sync_coordinator=_Coord({0: _plane(), 1: _plane((0, 0, 5))}, thickness=4.0),
        subwindow_data={0: _dicom_data(), 1: _dicom_data()},
        subwindow_managers={0: {}, 1: {}},
    )
    segs = helper.get_slice_location_line_segments(0, app, other_indices=[1], mode="begin_end")
    ids = sorted(s["line_id"] for s in segs)
    assert ids == ["begin:1", "end:1"]


def test_append_begin_end_thickness_none_fallback(monkeypatch) -> None:
    monkeypatch.setattr(helper, "_compute_segment", lambda *a: (0.0, 0.0, 10.0, 10.0))
    segments: list = []
    helper._append_begin_end_segments(
        segments, 2, _plane(), _plane(), 10.0, 10.0, thickness=None,
    )
    assert len(segments) == 1
    assert segments[0]["line_id"] == "middle:2"
