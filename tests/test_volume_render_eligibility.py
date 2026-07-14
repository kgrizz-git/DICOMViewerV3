"""Tests for 3D volume render eligibility helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.volume_render_eligibility import (
    MIN_SLICES_FOR_VOLUME,
    can_launch_3d_volume_render,
    get_datasets_for_subwindow,
    series_has_volume_geometry,
)


def _make_dataset(*, has_geometry: bool = True):
    ds = SimpleNamespace()
    if has_geometry:
        ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
        ds.ImagePositionPatient = [0.0, 0.0, 0.0]
    else:
        ds.ImageOrientationPatient = None
        ds.ImagePositionPatient = None
    return ds


def test_get_datasets_for_subwindow_prefers_subwindow_data() -> None:
    app = SimpleNamespace(
        subwindow_data={
            0: {"datasets": [_make_dataset(), _make_dataset(), _make_dataset()]},
        },
        current_studies={},
    )
    datasets = get_datasets_for_subwindow(app, 0)
    assert datasets is not None
    assert len(datasets) == 3


def test_get_datasets_for_subwindow_falls_back_to_current_studies() -> None:
    study_uid = "1.2.3"
    series_uid = "4.5.6"
    series = [_make_dataset(), _make_dataset(), _make_dataset()]
    app = SimpleNamespace(
        subwindow_data={
            0: {"study_uid": study_uid, "series_uid": series_uid},
        },
        current_studies={study_uid: {series_uid: series}},
    )
    datasets = get_datasets_for_subwindow(app, 0)
    assert datasets is series


def test_series_has_volume_geometry_requires_three_valid_slices() -> None:
    datasets = [_make_dataset(), _make_dataset(has_geometry=False), _make_dataset()]
    assert series_has_volume_geometry(datasets) is False

    datasets = [_make_dataset(), _make_dataset(), _make_dataset()]
    assert series_has_volume_geometry(datasets) is True


@patch("core.volume_render_eligibility.vtk_available", True)
def test_can_launch_3d_volume_render_true_for_valid_series() -> None:
    app = MagicMock()
    app.get_focused_subwindow_index.return_value = 0
    app.subwindow_data = {
        0: {"datasets": [_make_dataset() for _ in range(MIN_SLICES_FOR_VOLUME)]},
    }
    app.current_studies = {}

    enabled, tooltip = can_launch_3d_volume_render(app)
    assert enabled is True
    assert "Open 3D Volume Render" in tooltip


@patch("core.volume_render_eligibility.vtk_available", True)
def test_can_launch_3d_volume_render_false_for_single_slice() -> None:
    app = MagicMock()
    app.get_focused_subwindow_index.return_value = 0
    app.subwindow_data = {0: {"datasets": [_make_dataset()]}}
    app.current_studies = {}

    enabled, reason = can_launch_3d_volume_render(app)
    assert enabled is False
    assert "Requires at least" in reason


@patch("core.volume_render_eligibility.vtk_available", True)
def test_can_launch_3d_volume_render_false_without_geometry() -> None:
    app = MagicMock()
    app.get_focused_subwindow_index.return_value = 0
    app.subwindow_data = {
        0: {
            "datasets": [
                _make_dataset(has_geometry=False)
                for _ in range(MIN_SLICES_FOR_VOLUME)
            ],
        },
    }
    app.current_studies = {}

    enabled, reason = can_launch_3d_volume_render(app)
    assert enabled is False
    assert "spatial metadata" in reason


@patch("core.volume_render_eligibility.vtk_available", False)
def test_can_launch_3d_volume_render_false_when_vtk_missing() -> None:
    app = MagicMock()
    enabled, reason = can_launch_3d_volume_render(app)
    assert enabled is False
    assert "vtk" in reason.lower()


@patch("core.volume_render_eligibility.vtk_available", True)
def test_can_launch_3d_volume_render_honors_explicit_subwindow_index() -> None:
    app = MagicMock()
    app.get_focused_subwindow_index.return_value = 1
    app.subwindow_data = {
        0: {"datasets": [_make_dataset() for _ in range(MIN_SLICES_FOR_VOLUME)]},
        1: {"datasets": [_make_dataset()]},
    }
    app.current_studies = {}

    enabled, _ = can_launch_3d_volume_render(app, subwindow_idx=0)
    assert enabled is True

    enabled, _ = can_launch_3d_volume_render(app, subwindow_idx=1)
    assert enabled is False
