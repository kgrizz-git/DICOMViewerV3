"""Tests for core.study_navigation_handlers orchestration helpers.

These functions coordinate navigator/subwindow state on the app object, so
they are exercised with a MagicMock ``app`` whose iterated structures
(subwindow_data, subwindow_managers) are real dicts.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from core import study_navigation_handlers as snh


def _app() -> MagicMock:
    app = MagicMock()
    app.subwindow_data = {}
    app.subwindow_managers = {}
    return app


def test_get_subwindow_assignments_filters_invalid_and_empty() -> None:
    app = _app()
    app.multi_window_layout.get_slot_to_view.return_value = [0, 1, -1, 7]
    app.subwindow_data = {
        0: {
            "current_dataset": object(),
            "current_study_uid": "st",
            "current_series_uid": "sr",
            "current_slice_index": 3,
        },
        1: {"current_dataset": None},  # skipped: no dataset
    }
    out = snh.get_subwindow_assignments(app)
    assert out == {0: ("st", "sr", 3)}


def test_get_subwindow_assignments_stops_after_four_slots() -> None:
    app = _app()
    app.multi_window_layout.get_slot_to_view.return_value = [9, 9, 9, 9, 0]
    app.subwindow_data = {0: {"current_dataset": object(),
                              "current_study_uid": "s", "current_series_uid": "r"}}
    # slot 4 (view 0) is past the >=4 break, so nothing is assigned.
    assert snh.get_subwindow_assignments(app) == {}


@pytest.mark.parametrize(
    ("study", "series", "expected_args"),
    [
        ("st", "sr", ("sr", "st", 2)),   # both present -> positional
        ("", "sr", None),                # series only -> kwargs branch
        ("", "", ("", "", 0)),           # neither -> reset call
    ],
)
def test_update_series_navigator_highlighting_branches(
    monkeypatch, study, series, expected_args
) -> None:
    monkeypatch.setattr(snh, "refresh_series_navigator_state", lambda app: None)
    app = _app()
    app.focused_subwindow_index = 0
    app.subwindow_data = {0: {
        "current_series_uid": series,
        "current_study_uid": study,
        "current_slice_index": 2,
    }}
    snh.update_series_navigator_highlighting(app)
    call = app.series_navigator.set_current_position
    if expected_args is None:
        call.assert_called_once_with("sr", slice_index=2)
    else:
        call.assert_called_once_with(*expected_args)


def test_refresh_series_navigator_state_no_current_series(monkeypatch) -> None:
    monkeypatch.setattr(snh, "update_3d_view_action_state", lambda app: None)
    app = _app()
    app.config_manager.get_show_instances_separately.return_value = False
    app.current_study_uid = ""
    app.current_series_uid = ""
    snh.refresh_series_navigator_state(app)
    app.series_navigator.set_multiframe_info_map.assert_called_once()
    # No current series -> multiframe_info None -> enabled only if show flag set (False here).
    app.main_window.set_show_instances_separately_enabled.assert_called_once_with(False)


def test_refresh_series_navigator_state_expandable_multiframe(monkeypatch) -> None:
    monkeypatch.setattr(snh, "update_3d_view_action_state", lambda app: None)
    app = _app()
    app.config_manager.get_show_instances_separately.return_value = False
    app.current_study_uid = "st"
    app.current_series_uid = "sr"
    info = MagicMock(max_frame_count=8, instance_count=4)
    app.dicom_organizer.get_series_multiframe_info.return_value = info
    snh.refresh_series_navigator_state(app)
    app.main_window.set_show_instances_separately_enabled.assert_called_once_with(True)


def test_update_3d_view_action_state(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.volume_render_eligibility.can_launch_3d_volume_render",
        lambda app: (True, "ready"),
    )
    app = _app()
    snh.update_3d_view_action_state(app)
    app.main_window.set_3d_view_actions_enabled.assert_called_once_with(True, "ready")


def test_clear_subwindow_clears_managers_and_resets_data() -> None:
    app = _app()
    roi = MagicMock()
    meas = MagicMock()
    app.subwindow_managers = {0: {"roi_manager": roi, "measurement_tool": meas}}
    snh.clear_subwindow(app, 0)
    app._reset_fusion_handler_for_subwindow.assert_called_once_with(0)
    roi.clear_all_rois.assert_called_once()
    meas.clear_measurements.assert_called_once()
    assert app.subwindow_data[0]["current_dataset"] is None
    assert app.subwindow_data[0]["current_series_uid"] == ""
    app._sync_navigation_slider_for_subwindow.assert_called_once_with(0)


def test_clear_subwindow_swallows_coordinator_error() -> None:
    app = _app()
    app.subwindow_managers = {}
    app._slice_location_line_coordinator.remove_manager.side_effect = RuntimeError("boom")
    # Should not raise despite the coordinator error.
    snh.clear_subwindow(app, 2)
    assert app.subwindow_data[2]["current_slice_index"] == 0


def test_reset_focused_subwindow_state_after_close() -> None:
    app = _app()
    snh.reset_focused_subwindow_state_after_close(app)
    assert app.current_dataset is None
    assert app.current_study_uid == ""
    assert app.current_datasets == []
    app.metadata_panel.set_dataset.assert_called_once_with(None)
    app.roi_statistics_panel.clear_statistics.assert_called_once()


def test_clear_subwindow_content_early_return() -> None:
    app = _app()
    app.subwindow_data = {0: {"current_dataset": None, "is_mpr": False}}
    snh.clear_subwindow_content(app, 0)
    app.series_navigator.set_subwindow_assignments.assert_not_called()


def test_clear_subwindow_content_mpr_branch() -> None:
    app = _app()
    app.subwindow_data = {1: {"current_dataset": None, "is_mpr": True}}
    app.focused_subwindow_index = 1
    snh.clear_subwindow_content(app, 1)
    app._mpr_controller.detach_mpr_from_subwindow.assert_called_once_with(1)
    app._update_focused_subwindow_references.assert_called_once()


def test_clear_subwindow_content_normal_branch(monkeypatch) -> None:
    monkeypatch.setattr(snh, "clear_subwindow", MagicMock())
    monkeypatch.setattr(snh, "reset_focused_subwindow_state_after_close", MagicMock())
    app = _app()
    app.subwindow_data = {0: {"current_dataset": object(), "is_mpr": False}}
    app.focused_subwindow_index = 0
    app.cine_player = MagicMock()
    snh.clear_subwindow_content(app, 0)
    snh.clear_subwindow.assert_called_once_with(app, 0)
    snh.reset_focused_subwindow_state_after_close.assert_called_once_with(app)
    app.series_navigator.set_subwindow_assignments.assert_called_once()


def test_close_series_empty_returns_early() -> None:
    app = _app()
    app.current_studies = {}
    snh.close_series(app, "st", "sr")
    app.dicom_organizer.remove_series.assert_not_called()


def test_close_series_removes_and_refreshes(monkeypatch) -> None:
    monkeypatch.setattr(snh, "clear_subwindow", MagicMock())
    monkeypatch.setattr(snh, "reset_focused_subwindow_state_after_close", MagicMock())
    app = _app()
    app.current_studies = {"st": {"sr": [object(), object()]}}
    app.subwindow_data = {0: {"current_study_uid": "st", "current_series_uid": "sr"}}
    app.focused_subwindow_index = 0
    app.dicom_organizer.studies = {}  # study now gone -> annotations removed
    snh.close_series(app, "st", "sr")
    app.dicom_organizer.remove_series.assert_called_once_with("st", "sr")
    app.annotation_manager.remove_study_annotations.assert_called_once_with("st")
    snh.clear_subwindow.assert_called_once_with(app, 0)
    snh.reset_focused_subwindow_state_after_close.assert_called_once_with(app)
    app._slice_sync_coordinator.invalidate_cache.assert_called_once_with("st", "sr")


def test_close_study_empty_returns_early() -> None:
    app = _app()
    app.current_studies = {}
    snh.close_study(app, "st")
    app.dicom_organizer.remove_study.assert_not_called()


def test_close_study_removes_and_refreshes(monkeypatch) -> None:
    monkeypatch.setattr(snh, "clear_subwindow", MagicMock())
    monkeypatch.setattr(snh, "reset_focused_subwindow_state_after_close", MagicMock())
    app = _app()
    app.current_studies = {"st": {"sr": [object()]}}
    app.subwindow_data = {2: {"current_study_uid": "st"}}
    app.focused_subwindow_index = 2
    snh.close_study(app, "st")
    app.dicom_organizer.remove_study.assert_called_once_with("st")
    app.annotation_manager.remove_study_annotations.assert_called_once_with("st")
    snh.clear_subwindow.assert_called_once_with(app, 2)
    app._slice_sync_coordinator.invalidate_cache.assert_called_once_with("st")
