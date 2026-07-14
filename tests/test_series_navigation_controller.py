"""
Unit tests for core.series_navigation_controller (series navigation, subwindow
assignment, series navigator selection handlers).

``app`` is stubbed with a plain namespace (not MagicMock) so that
``hasattr``/``getattr`` checks for optional attributes (``_mpr_controller``,
``study_cache``, ``_refresh_window_slot_map_widgets``) behave like the real
DICOMViewerApp instead of auto-vivifying on a mock.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset

import core.series_navigation_controller as series_navigation_controller
from core.series_navigation_controller import (
    _try_navigate_multiframe_instance,
    assign_series_to_subwindow,
    build_flat_series_list,
    on_assign_series_from_context_menu,
    on_series_navigation_requested,
    on_series_navigator_instance_selected,
    on_series_navigator_selected,
)
from utils.dicom_utils import get_composite_series_key


def _make_dataset(study_uid="study1", series_uid="series1", series_number=1):
    ds = Dataset()
    ds.StudyInstanceUID = study_uid
    ds.SeriesInstanceUID = series_uid
    if series_number is not None:
        ds.SeriesNumber = series_number
    return ds


def _make_app(**overrides):
    defaults = {
        "current_studies": {},
        "subwindow_data": {},
        "subwindow_managers": {},
        "multi_window_layout": MagicMock(),
        "main_window": MagicMock(),
        "dialog_coordinator": MagicMock(),
        "slice_navigator": MagicMock(),
        "series_navigator": MagicMock(),
        "cine_app_facade": MagicMock(),
        "config_manager": MagicMock(),
        "dicom_organizer": MagicMock(),
        "slice_display_manager": MagicMock(),
        "intensity_projection_controls_widget": MagicMock(),
        "_slice_sync_coordinator": MagicMock(),
        "_slice_location_line_coordinator": MagicMock(),
        "_update_series_navigator_highlighting": MagicMock(),
        "_update_right_panel_for_focused_subwindow": MagicMock(),
        "_update_undo_redo_state": MagicMock(),
        "_refresh_series_navigator_state": MagicMock(),
        "_get_subwindow_assignments": MagicMock(return_value={}),
        "_subwindow_lifecycle_controller": MagicMock(),
        "_series_navigation_in_progress": False,
        "focused_subwindow_index": 0,
        "current_series_uid": "",
        "current_study_uid": "",
        "current_slice_index": 0,
        "current_dataset": None,
    }
    defaults.update(overrides)
    app = SimpleNamespace(**defaults)
    app.config_manager.get_show_instances_separately.return_value = False
    return app


@pytest.fixture(autouse=True)
def _patch_about_dialog(monkeypatch):
    monkeypatch.setattr(
        series_navigation_controller, "update_about_this_file_dialog", MagicMock()
    )


class TestBuildFlatSeriesList:
    def test_empty_studies_returns_empty_list(self):
        assert build_flat_series_list({}) == []

    def test_sorts_by_series_number_within_study(self):
        ds_a = _make_dataset(series_number=3)
        ds_b = _make_dataset(series_number=1)
        studies = {"study1": {"seriesA": [ds_a], "seriesB": [ds_b]}}
        result = build_flat_series_list(studies)
        assert [r[2] for r in result] == ["seriesB", "seriesA"]

    def test_skips_series_with_no_datasets(self):
        studies = {"study1": {"empty_series": []}}
        assert build_flat_series_list(studies) == []

    def test_non_numeric_series_number_defaults_to_zero(self):
        # SimpleNamespace (not a real Dataset) since pydicom's IS VR would
        # reject a non-numeric string outright; build_flat_series_list only
        # does getattr() duck-typing so this is a faithful stand-in.
        ds = SimpleNamespace(SeriesNumber="not-a-number")
        studies = {"study1": {"series1": [ds]}}
        result = build_flat_series_list(studies)
        assert result[0][0] == 0

    def test_missing_series_number_defaults_to_zero(self):
        ds = _make_dataset(series_number=None)
        studies = {"study1": {"series1": [ds]}}
        result = build_flat_series_list(studies)
        assert result[0][0] == 0

    def test_flattens_across_multiple_studies(self):
        ds1 = _make_dataset(study_uid="study1", series_uid="s1", series_number=1)
        ds2 = _make_dataset(study_uid="study2", series_uid="s2", series_number=1)
        studies = {"study1": {"s1": [ds1]}, "study2": {"s2": [ds2]}}
        result = build_flat_series_list(studies)
        assert len(result) == 2


class TestAssignSeriesToSubwindow:
    def test_noop_when_subwindow_not_registered(self):
        subwindow = MagicMock()
        app = _make_app()
        app.multi_window_layout.get_all_subwindows.return_value = []
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        subwindow.set_assigned_series.assert_not_called()

    def test_shows_toast_and_returns_when_mpr_active(self):
        subwindow = MagicMock()
        app = _make_app(_mpr_controller=MagicMock())
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app._mpr_controller.is_mpr.return_value = True
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        app.main_window.show_toast_message.assert_called_once()
        subwindow.set_assigned_series.assert_not_called()

    def test_ensures_managers_when_idx_missing(self):
        subwindow = MagicMock()
        app = _make_app(_subwindow_lifecycle_controller=MagicMock())
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.current_studies = {}
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        app._subwindow_lifecycle_controller.ensure_all_subwindows_have_managers.assert_called_once()

    def test_returns_when_no_current_studies(self):
        subwindow = MagicMock()
        app = _make_app()
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.current_studies = {}
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        subwindow.set_assigned_series.assert_not_called()

    def test_returns_when_target_study_not_present(self):
        subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        assign_series_to_subwindow(app, subwindow, "series1", 0, target_study_uid="other_study")
        subwindow.set_assigned_series.assert_not_called()

    def test_returns_when_series_not_in_target_study(self):
        subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        assign_series_to_subwindow(app, subwindow, "unknown_series", 0, target_study_uid="study1")
        subwindow.set_assigned_series.assert_not_called()

    def test_searches_for_study_containing_series_when_target_not_given(self):
        subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = None
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        subwindow.set_assigned_series.assert_called_once_with("series1", 0)

    def test_returns_when_series_uid_not_found_anywhere(self):
        subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        assign_series_to_subwindow(app, subwindow, "nonexistent", 0)
        subwindow.set_assigned_series.assert_not_called()

    def test_returns_when_series_datasets_empty(self):
        subwindow = MagicMock()
        app = _make_app(current_studies={"study1": {"series1": []}})
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        subwindow.set_assigned_series.assert_not_called()

    def test_clamps_slice_index_to_valid_range(self, qapp):
        subwindow = MagicMock()
        ds1, ds2 = _make_dataset(), _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds1, ds2]}})
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = None
        assign_series_to_subwindow(app, subwindow, "series1", 99)
        assert app.subwindow_data[0]["current_slice_index"] == 1

    def test_non_focused_subwindow_skips_focused_only_updates(self, qapp):
        subwindow = MagicMock()
        other_subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = other_subwindow
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        subwindow.set_assigned_series.assert_called_once_with("series1", 0)
        app.slice_navigator.set_total_slices.assert_not_called()
        app.dialog_coordinator.update_histogram_for_subwindow.assert_called_once_with(0)

    def test_focused_subwindow_updates_current_state(self, qapp):
        subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = subwindow
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        assert app.current_series_uid == "series1"
        assert app.current_study_uid == "study1"
        assert app.current_slice_index == 0
        app._update_series_navigator_highlighting.assert_called_once()
        app._update_right_panel_for_focused_subwindow.assert_called_once()
        app.cine_app_facade.update_cine_player_context.assert_called_once()
        app.slice_navigator.set_total_slices.assert_called_once_with(1)
        app.series_navigator.set_current_series.assert_called_once_with("series1", "study1")

    def test_calls_display_slice_with_manager_when_present(self, qapp):
        subwindow = MagicMock()
        ds = _make_dataset()
        slice_display_manager = MagicMock()
        app = _make_app(
            current_studies={"study1": {"series1": [ds]}},
            subwindow_managers={0: {"slice_display_manager": slice_display_manager}},
        )
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = subwindow
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        slice_display_manager.display_slice.assert_called_once()
        _, kwargs = slice_display_manager.display_slice.call_args
        assert kwargs["update_controls"] is True
        assert kwargs["update_metadata"] is True

    def test_calls_crosshair_coordinator_when_present(self, qapp):
        subwindow = MagicMock()
        ds = _make_dataset()
        crosshair_coordinator = MagicMock()
        app = _make_app(
            current_studies={"study1": {"series1": [ds]}},
            subwindow_managers={0: {
                "slice_display_manager": MagicMock(),
                "crosshair_coordinator": crosshair_coordinator,
            }},
        )
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = subwindow
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        crosshair_coordinator.update_crosshairs_for_slice.assert_called_once()

    def test_marks_study_cache_accessed_when_present(self, qapp):
        subwindow = MagicMock()
        ds = _make_dataset()
        study_cache = MagicMock()
        app = _make_app(current_studies={"study1": {"series1": [ds]}}, study_cache=study_cache)
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = None
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        study_cache.mark_accessed.assert_called_once_with("study1")

    def test_calls_refresh_window_slot_map_when_present(self, qapp):
        subwindow = MagicMock()
        ds = _make_dataset()
        refresh = MagicMock()
        app = _make_app(
            current_studies={"study1": {"series1": [ds]}},
            _refresh_window_slot_map_widgets=refresh,
        )
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = None
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        refresh.assert_called_once()

    def test_reuses_existing_subwindow_data_entry(self, qapp):
        subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(
            current_studies={"study1": {"series1": [ds]}},
            subwindow_data={0: {"existing_key": "keep_me"}},
        )
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = None
        assign_series_to_subwindow(app, subwindow, "series1", 0)
        assert app.subwindow_data[0]["existing_key"] == "keep_me"

    def test_skips_refresh_window_slot_map_when_absent(self, qapp):
        subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.multi_window_layout.get_focused_subwindow.return_value = None
        assign_series_to_subwindow(app, subwindow, "series1", 0)  # should not raise


class TestOnSeriesNavigatorSelected:
    def test_shows_toast_when_mpr_active(self):
        app = _make_app(_mpr_controller=MagicMock(), focused_subwindow_index=1)
        app._mpr_controller.is_mpr.return_value = True
        on_series_navigator_selected(app, "series1")
        app.main_window.show_toast_message.assert_called_once()

    def test_returns_when_no_current_studies(self):
        app = _make_app(current_studies={})
        on_series_navigator_selected(app, "series1")
        app.multi_window_layout.get_focused_subwindow.assert_not_called()

    def test_returns_when_series_not_found(self):
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        on_series_navigator_selected(app, "unknown")
        app.multi_window_layout.get_focused_subwindow.assert_not_called()

    def test_returns_when_series_datasets_empty(self):
        app = _make_app(current_studies={"study1": {"series1": []}})
        on_series_navigator_selected(app, "series1")
        app.multi_window_layout.get_focused_subwindow.assert_not_called()

    def test_assigns_to_focused_subwindow(self, qapp):
        subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_focused_subwindow.return_value = subwindow
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        on_series_navigator_selected(app, "series1")
        subwindow.set_assigned_series.assert_called_once_with("series1", 0)

    def test_noop_when_no_focused_subwindow(self):
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_focused_subwindow.return_value = None
        on_series_navigator_selected(app, "series1")  # should not raise


class TestOnSeriesNavigatorInstanceSelected:
    def test_shows_toast_when_mpr_active(self):
        app = _make_app(_mpr_controller=MagicMock(), focused_subwindow_index=0)
        app._mpr_controller.is_mpr.return_value = True
        on_series_navigator_instance_selected(app, "study1", "series1", 2)
        app.main_window.show_toast_message.assert_called_once()

    def test_returns_when_study_missing(self):
        app = _make_app(current_studies={})
        on_series_navigator_instance_selected(app, "study1", "series1", 2)
        app.multi_window_layout.get_focused_subwindow.assert_not_called()

    def test_returns_when_series_missing_from_study(self):
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"other_series": [ds]}})
        on_series_navigator_instance_selected(app, "study1", "series1", 2)
        app.multi_window_layout.get_focused_subwindow.assert_not_called()

    def test_assigns_instance_slice_to_focused_subwindow(self, qapp):
        subwindow = MagicMock()
        ds1, ds2, ds3 = _make_dataset(), _make_dataset(), _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds1, ds2, ds3]}})
        app.multi_window_layout.get_focused_subwindow.return_value = subwindow
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        on_series_navigator_instance_selected(app, "study1", "series1", 2)
        subwindow.set_assigned_series.assert_called_once_with("series1", 2)

    def test_noop_when_no_focused_subwindow(self):
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_focused_subwindow.return_value = None
        on_series_navigator_instance_selected(app, "study1", "series1", 0)  # should not raise


class TestOnAssignSeriesFromContextMenu:
    def test_delegates_to_series_navigator_selected(self, qapp):
        subwindow = MagicMock()
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.multi_window_layout.get_focused_subwindow.return_value = subwindow
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        on_assign_series_from_context_menu(app, "series1")
        subwindow.set_assigned_series.assert_called_once_with("series1", 0)


class TestTryNavigateMultiframeInstance:
    def test_returns_false_when_show_instances_separately_disabled(self):
        app = _make_app()
        app.config_manager.get_show_instances_separately.return_value = False
        assert _try_navigate_multiframe_instance(app, 0, "study1", "series1", 0, 1) is False

    def test_returns_false_when_study_or_series_missing(self):
        app = _make_app(current_studies={})
        app.config_manager.get_show_instances_separately.return_value = True
        assert _try_navigate_multiframe_instance(app, 0, "study1", "series1", 0, 1) is False

    def test_returns_false_when_study_uid_empty(self):
        app = _make_app(current_studies={})
        app.config_manager.get_show_instances_separately.return_value = True
        assert _try_navigate_multiframe_instance(app, 0, "", "series1", 0, 1) is False

    def test_returns_false_when_series_uid_empty(self):
        app = _make_app(current_studies={})
        app.config_manager.get_show_instances_separately.return_value = True
        assert _try_navigate_multiframe_instance(app, 0, "study1", "", 0, 1) is False

    def test_returns_false_when_series_datasets_empty(self):
        app = _make_app(current_studies={"study1": {"series1": []}})
        app.config_manager.get_show_instances_separately.return_value = True
        assert _try_navigate_multiframe_instance(app, 0, "study1", "series1", 0, 1) is False

    def test_returns_false_when_not_multiframe(self):
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.config_manager.get_show_instances_separately.return_value = True
        app.dicom_organizer.get_series_multiframe_info.return_value = SimpleNamespace(
            instance_count=1, max_frame_count=1
        )
        assert _try_navigate_multiframe_instance(app, 0, "study1", "series1", 0, 1) is False

    def test_returns_false_when_single_instance_entry(self):
        ds = _make_dataset()
        app = _make_app(current_studies={"study1": {"series1": [ds]}})
        app.config_manager.get_show_instances_separately.return_value = True
        app.dicom_organizer.get_series_multiframe_info.return_value = SimpleNamespace(
            instance_count=2, max_frame_count=3
        )
        app.series_navigator.build_instance_entries.return_value = [(0, 3)]
        assert _try_navigate_multiframe_instance(app, 0, "study1", "series1", 0, 1) is False

    def test_navigates_forward_to_next_instance_start(self, qapp):
        subwindow = MagicMock()
        datasets = [_make_dataset() for _ in range(4)]
        app = _make_app(current_studies={"study1": {"series1": datasets}})
        app.multi_window_layout.get_focused_subwindow.return_value = subwindow
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.config_manager.get_show_instances_separately.return_value = True
        app.dicom_organizer.get_series_multiframe_info.return_value = SimpleNamespace(
            instance_count=2, max_frame_count=2
        )
        app.series_navigator.build_instance_entries.return_value = [(0, 2), (2, 2)]
        result = _try_navigate_multiframe_instance(app, 0, "study1", "series1", 0, 1)
        assert result is True
        subwindow.set_assigned_series.assert_called_once_with("series1", 2)

    def test_returns_false_at_last_instance_going_forward(self):
        datasets = [_make_dataset() for _ in range(4)]
        app = _make_app(current_studies={"study1": {"series1": datasets}})
        app.config_manager.get_show_instances_separately.return_value = True
        app.dicom_organizer.get_series_multiframe_info.return_value = SimpleNamespace(
            instance_count=2, max_frame_count=2
        )
        app.series_navigator.build_instance_entries.return_value = [(0, 2), (2, 2)]
        assert _try_navigate_multiframe_instance(app, 0, "study1", "series1", 2, 1) is False

    def test_navigates_backward_to_previous_instance_start(self, qapp):
        subwindow = MagicMock()
        datasets = [_make_dataset() for _ in range(4)]
        app = _make_app(current_studies={"study1": {"series1": datasets}})
        app.multi_window_layout.get_focused_subwindow.return_value = subwindow
        app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
        app.config_manager.get_show_instances_separately.return_value = True
        app.dicom_organizer.get_series_multiframe_info.return_value = SimpleNamespace(
            instance_count=2, max_frame_count=2
        )
        app.series_navigator.build_instance_entries.return_value = [(0, 2), (2, 2)]
        result = _try_navigate_multiframe_instance(app, 0, "study1", "series1", 2, -1)
        assert result is True
        subwindow.set_assigned_series.assert_called_once_with("series1", 0)

    def test_returns_false_at_first_instance_going_backward(self):
        datasets = [_make_dataset() for _ in range(4)]
        app = _make_app(current_studies={"study1": {"series1": datasets}})
        app.config_manager.get_show_instances_separately.return_value = True
        app.dicom_organizer.get_series_multiframe_info.return_value = SimpleNamespace(
            instance_count=2, max_frame_count=2
        )
        app.series_navigator.build_instance_entries.return_value = [(0, 2), (2, 2)]
        assert _try_navigate_multiframe_instance(app, 0, "study1", "series1", 0, -1) is False

    def test_returns_false_when_no_focused_subwindow(self):
        datasets = [_make_dataset() for _ in range(4)]
        app = _make_app(current_studies={"study1": {"series1": datasets}})
        app.multi_window_layout.get_focused_subwindow.return_value = None
        app.config_manager.get_show_instances_separately.return_value = True
        app.dicom_organizer.get_series_multiframe_info.return_value = SimpleNamespace(
            instance_count=2, max_frame_count=2
        )
        app.series_navigator.build_instance_entries.return_value = [(0, 2), (2, 2)]
        assert _try_navigate_multiframe_instance(app, 0, "study1", "series1", 0, 1) is False

    def test_loop_completes_without_break_when_slice_index_before_first_start(self):
        datasets = [_make_dataset() for _ in range(4)]
        app = _make_app(current_studies={"study1": {"series1": datasets}})
        app.config_manager.get_show_instances_separately.return_value = True
        app.dicom_organizer.get_series_multiframe_info.return_value = SimpleNamespace(
            instance_count=2, max_frame_count=2
        )
        # Entries deliberately don't start at 0, so slice_index=0 never satisfies
        # "slice_index >= starts[j]" and the search loop runs to completion.
        app.series_navigator.build_instance_entries.return_value = [(1, 2), (3, 2)]
        app.multi_window_layout.get_focused_subwindow.return_value = None
        assert _try_navigate_multiframe_instance(app, 0, "study1", "series1", 0, -1) is False


class TestOnSeriesNavigationRequested:
    def test_noop_when_navigation_already_in_progress(self):
        app = _make_app(_series_navigation_in_progress=True)
        on_series_navigation_requested(app, 1)
        assert app._series_navigation_in_progress is True

    def test_shows_toast_when_mpr_active_on_focused_window(self):
        app = _make_app(_mpr_controller=MagicMock(), focused_subwindow_index=0)
        app._mpr_controller.is_mpr.return_value = True
        on_series_navigation_requested(app, 1)
        app.main_window.show_toast_message.assert_called_once()
        assert app._series_navigation_in_progress is False

    def test_releases_lock_when_focused_idx_not_in_subwindow_data(self):
        app = _make_app(subwindow_data={}, focused_subwindow_index=0)
        on_series_navigation_requested(app, 1)
        assert app._series_navigation_in_progress is False

    def test_loads_first_series_when_none_loaded_direction_forward(self, qapp):
        ds_first = _make_dataset(study_uid="study1", series_uid="s1", series_number=1)
        ds_second = _make_dataset(study_uid="study1", series_uid="s2", series_number=2)
        key1, key2 = get_composite_series_key(ds_first), get_composite_series_key(ds_second)
        app = _make_app(
            current_studies={"study1": {key1: [ds_first], key2: [ds_second]}},
            subwindow_data={0: {"current_study_uid": "", "current_series_uid": "", "current_slice_index": 0, "current_dataset": None}},
        )
        on_series_navigation_requested(app, 1)
        assert app.current_series_uid == key1
        assert app.current_study_uid == "study1"
        assert app._series_navigation_in_progress is False
        app.slice_display_manager.display_slice.assert_called()

    def test_loads_last_series_when_none_loaded_direction_backward(self, qapp):
        ds_first = _make_dataset(study_uid="study1", series_uid="s1", series_number=1)
        ds_second = _make_dataset(study_uid="study1", series_uid="s2", series_number=2)
        key1, key2 = get_composite_series_key(ds_first), get_composite_series_key(ds_second)
        app = _make_app(
            current_studies={"study1": {key1: [ds_first], key2: [ds_second]}},
            subwindow_data={0: {"current_study_uid": "", "current_series_uid": "", "current_slice_index": 0, "current_dataset": None}},
        )
        on_series_navigation_requested(app, -1)
        assert app.current_series_uid == key2

    def test_loads_first_series_with_no_series_instance_uid_skips_navigator_refresh(self, qapp):
        # Dataset lacking SeriesInstanceUID -> get_composite_series_key returns "",
        # so the post-load series_navigator refresh block is skipped.
        ds_first = Dataset()
        app = _make_app(
            current_studies={"study1": {"series1": [ds_first]}},
            subwindow_data={0: {"current_study_uid": "", "current_series_uid": "", "current_slice_index": 0, "current_dataset": None}},
        )
        on_series_navigation_requested(app, 1)
        assert app.current_series_uid == ""
        assert app._series_navigation_in_progress is False
        app.series_navigator.set_current_series.assert_not_called()

    def test_noop_when_no_series_loaded_and_no_studies(self):
        app = _make_app(
            current_studies={},
            subwindow_data={0: {"current_study_uid": "", "current_series_uid": "", "current_slice_index": 0, "current_dataset": None}},
        )
        on_series_navigation_requested(app, 1)
        assert app._series_navigation_in_progress is False

    def test_noop_when_study_has_no_series(self):
        app = _make_app(
            current_studies={"study1": {}},
            subwindow_data={0: {"current_study_uid": "study1", "current_series_uid": "", "current_slice_index": 0, "current_dataset": None}},
        )
        on_series_navigation_requested(app, 1)
        assert app._series_navigation_in_progress is False

    def test_navigates_forward_between_existing_series(self, qapp):
        ds1 = _make_dataset(study_uid="study1", series_uid="s1", series_number=1)
        ds2 = _make_dataset(study_uid="study1", series_uid="s2", series_number=2)
        key1, key2 = get_composite_series_key(ds1), get_composite_series_key(ds2)
        app = _make_app(
            current_studies={"study1": {key1: [ds1], key2: [ds2]}},
            subwindow_data={0: {
                "current_study_uid": "study1",
                "current_series_uid": key1,
                "current_slice_index": 0,
                "current_dataset": None,
            }},
        )
        app.slice_display_manager.current_study_uid = "study1"
        app.slice_display_manager.current_series_uid = key1
        on_series_navigation_requested(app, 1)
        assert app.current_series_uid == key2
        assert app._series_navigation_in_progress is False

    def test_navigates_backward_between_existing_series(self, qapp):
        ds1 = _make_dataset(study_uid="study1", series_uid="s1", series_number=1)
        ds2 = _make_dataset(study_uid="study1", series_uid="s2", series_number=2)
        key1, key2 = get_composite_series_key(ds1), get_composite_series_key(ds2)
        app = _make_app(
            current_studies={"study1": {key1: [ds1], key2: [ds2]}},
            subwindow_data={0: {
                "current_study_uid": "study1",
                "current_series_uid": key2,
                "current_slice_index": 0,
                "current_dataset": None,
            }},
        )
        app.slice_display_manager.current_study_uid = "study1"
        app.slice_display_manager.current_series_uid = key2
        on_series_navigation_requested(app, -1)
        assert app.current_series_uid == key1

    def test_noop_at_last_series_going_forward(self, qapp):
        ds1 = _make_dataset(study_uid="study1", series_uid="s1", series_number=1)
        key1 = get_composite_series_key(ds1)
        app = _make_app(
            current_studies={"study1": {key1: [ds1]}},
            subwindow_data={0: {
                "current_study_uid": "study1",
                "current_series_uid": key1,
                "current_slice_index": 0,
                "current_dataset": None,
            }},
            current_series_uid=key1,
            current_study_uid="study1",
        )
        app.slice_display_manager.current_study_uid = "study1"
        app.slice_display_manager.current_series_uid = key1
        on_series_navigation_requested(app, 1)
        assert app.current_series_uid == key1
        assert app._series_navigation_in_progress is False

    def test_invalid_study_uid_releases_lock(self):
        app = _make_app(
            current_studies={"study1": {}},
            subwindow_data={0: {
                "current_study_uid": "missing_study",
                "current_series_uid": "s1",
                "current_slice_index": 0,
                "current_dataset": None,
            }},
        )
        on_series_navigation_requested(app, 1)
        assert app._series_navigation_in_progress is False

    def test_falls_back_to_first_series_when_focused_series_missing_from_study(self, qapp):
        ds1 = _make_dataset(study_uid="study1", series_uid="s1", series_number=1)
        key1 = get_composite_series_key(ds1)
        app = _make_app(
            current_studies={"study1": {key1: [ds1]}},
            subwindow_data={0: {
                "current_study_uid": "study1",
                "current_series_uid": "missing_series",
                "current_slice_index": 0,
                "current_dataset": None,
            }},
        )
        app.slice_display_manager.current_study_uid = "study1"
        app.slice_display_manager.current_series_uid = key1
        on_series_navigation_requested(app, 1)
        assert app._series_navigation_in_progress is False

    def test_mismatch_between_stored_and_extracted_series_uid_updates_data(self, qapp):
        displayed = _make_dataset(study_uid="study1", series_uid="s1", series_number=1)
        key1 = get_composite_series_key(displayed)
        app = _make_app(
            current_studies={"study1": {key1: [displayed]}},
            subwindow_data={0: {
                "current_study_uid": "study1",
                "current_series_uid": "stale_series",
                "current_slice_index": 0,
                "current_dataset": displayed,
            }},
        )
        app.slice_display_manager.current_study_uid = "study1"
        app.slice_display_manager.current_series_uid = key1
        on_series_navigation_requested(app, 1)
        assert app._series_navigation_in_progress is False
