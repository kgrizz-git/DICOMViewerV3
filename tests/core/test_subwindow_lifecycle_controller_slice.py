"""Focused tests for SubwindowLifecycleController getters with a fake app."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from pydicom.dataset import Dataset

from core.subwindow_lifecycle_controller import SubwindowLifecycleController


def _fake_app(*, focused: int = 0, datasets: list | None = None) -> SimpleNamespace:
    ds_list = datasets if datasets is not None else []
    subwindow_data = {
        focused: {
            "current_datasets": ds_list,
            "current_dataset": ds_list[0] if ds_list else None,
            "current_study_uid": "st",
            "current_series_uid": "se",
            "current_slice_index": 0,
            "is_mpr": False,
        }
    }
    return SimpleNamespace(
        focused_subwindow_index=focused,
        subwindow_data=subwindow_data,
        subwindow_managers={},
        multi_window_layout=MagicMock(),
        config_manager=MagicMock(),
        current_studies={},
    )


def test_get_subwindow_dataset_and_uids() -> None:
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.3"
    app = _fake_app(datasets=[ds])
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_subwindow_dataset(0) is ds
    assert ctrl.get_subwindow_study_uid(0) == "st"
    assert ctrl.get_subwindow_series_uid(0) == "se"
    assert ctrl.get_subwindow_slice_index(0) == 0


def test_get_subwindow_dataset_missing_returns_none() -> None:
    app = _fake_app()
    app.subwindow_data = {}
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_subwindow_dataset(0) is None


def test_get_focused_subwindow_index() -> None:
    app = _fake_app(focused=2)
    ctrl = SubwindowLifecycleController(app)
    assert ctrl.get_focused_subwindow_index() == 2
    assert 2 in app.subwindow_data
