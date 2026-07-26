"""
Characterization tests for additive-load helpers (Sonar S3776 slice).

Covers helpers extracted from ``FileSeriesLoadingCoordinator.handle_additive_load``
beyond the existing study-cache eviction suite.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from gui.file_series_additive_load import (
    auto_assign_first_new_series,
    find_first_empty_subwindow_index,
    finish_additive_load_side_effects,
    handle_additive_noop_refresh,
    load_ps_ko_for_new_studies,
    maybe_show_navigator_for_new_series,
    refresh_appended_series_subwindows,
    refresh_focused_fusion_series_list,
    show_additive_load_status,
    show_duplicate_skip_toast,
)
from gui.file_series_loading_coordinator import FileSeriesLoadingCoordinator


def _merge(**overrides):
    base = {
        "new_series": [],
        "appended_series": [],
        "skipped_file_count": 0,
        "added_file_count": 0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_show_duplicate_skip_toast_noop_and_message() -> None:
    app = MagicMock()
    show_duplicate_skip_toast(app, 0)
    app.main_window.show_toast_message.assert_not_called()
    show_duplicate_skip_toast(app, 3)
    app.main_window.show_toast_message.assert_called_once()
    assert "3 file(s)" in app.main_window.show_toast_message.call_args.args[0]


def test_handle_additive_noop_refresh_messages() -> None:
    app = MagicMock()
    app.current_studies = {}
    app.current_study_uid = "s"
    app.current_series_uid = "ser"
    handle_additive_noop_refresh(app, _merge(skipped_file_count=2))
    msg = app.main_window.statusBar().showMessage.call_args.args[0]
    assert "already loaded" in msg
    app.main_window.show_toast_message.assert_called_once()


def test_load_ps_ko_for_new_studies() -> None:
    app = MagicMock()
    app.dicom_organizer.get_presentation_states.side_effect = lambda uid: (
        {"ps": 1} if uid == "A" else None
    )
    app.dicom_organizer.get_key_objects.side_effect = lambda uid: (
        {"ko": 1} if uid == "B" else None
    )
    load_ps_ko_for_new_studies(app, {"A", "B"})
    app.annotation_manager.load_presentation_states.assert_called_once_with({"A": {"ps": 1}})
    app.annotation_manager.load_key_objects.assert_called_once_with({"B": {"ko": 1}})


def test_refresh_appended_series_updates_focused_slice_count() -> None:
    app = MagicMock()
    datasets = [MagicMock(), MagicMock()]
    app.current_studies = {"st": {"ser": datasets}}
    app.focused_subwindow_index = 1
    app.subwindow_data = {
        1: {"current_study_uid": "st", "current_series_uid": "ser", "current_datasets": []},
    }
    refresh_appended_series_subwindows(app, [("st", "ser")])
    assert app.subwindow_data[1]["current_datasets"] is datasets
    app.slice_navigator.set_total_slices.assert_called_once_with(2)


def test_find_first_empty_subwindow_index() -> None:
    app = MagicMock()
    app.multi_window_layout.get_all_subwindows.return_value = [0, 1, 2]
    app.subwindow_data = {
        0: {"current_dataset": MagicMock()},
        1: {"current_dataset": None},
    }
    assert find_first_empty_subwindow_index(app) == 1


def test_auto_assign_first_new_series_into_empty_focused_pane() -> None:
    app = MagicMock()
    ds0 = object()
    datasets = [ds0]
    app.current_studies = {"st": {"ser": datasets}}
    app.focused_subwindow_index = 0
    app.subwindow_data = {}
    app.subwindow_managers = {}
    sdm = MagicMock()
    vsm = MagicMock()
    managers = {
        "slice_display_manager": sdm,
        "view_state_manager": vsm,
        "roi_coordinator": MagicMock(),
    }

    def _ensure():
        app.subwindow_managers[0] = managers

    app._ensure_all_subwindows_have_managers.side_effect = _ensure

    with patch("gui.file_series_additive_load.QTimer.singleShot"):
        auto_assign_first_new_series(app, 0, ("st", "ser"))

    sdm.display_slice.assert_called_once()
    assert app.subwindow_data[0]["current_dataset"] is ds0
    assert app.current_dataset is ds0
    assert app.current_study_uid == "st"
    assert app.slice_display_manager is sdm
    app._connect_focused_subwindow_signals.assert_called_once()


def test_maybe_show_navigator_and_status_and_fusion() -> None:
    app = MagicMock()
    app.main_window.series_navigator_visible = False
    maybe_show_navigator_for_new_series(app, _merge(new_series=[("a", "s")]))
    app.main_window.toggle_series_navigator.assert_called_once()

    show_additive_load_status(app, _merge(new_series=[("a", "s1"), ("a", "s2"), ("b", "s1")]))
    msg = app.main_window.statusBar().showMessage.call_args.args[0]
    assert "3 new series" in msg and "2 studies" in msg

    show_additive_load_status(
        app, _merge(appended_series=[("a", "s")], added_file_count=4)
    )
    msg = app.main_window.statusBar().showMessage.call_args.args[0]
    assert "4 slice" in msg

    focused = object()
    app.multi_window_layout.get_focused_subwindow.return_value = focused
    app.multi_window_layout.get_all_subwindows.return_value = [focused]
    fusion = MagicMock()
    app.subwindow_managers = {0: {"fusion_coordinator": fusion}}
    refresh_focused_fusion_series_list(app)
    fusion.update_fusion_controls_series_list.assert_called_once()


def test_finish_additive_load_side_effects_schedules_work() -> None:
    app = MagicMock()
    with patch("gui.file_series_additive_load.QTimer.singleShot") as shot:
        finish_additive_load_side_effects(app)
    app._slice_sync_coordinator.invalidate_cache.assert_called_once()
    app._schedule_tag_export_union_rebuild.assert_called_once()
    assert shot.call_count == 2


def test_handle_additive_load_orchestrates_helpers() -> None:
    app = MagicMock()
    app.dicom_organizer.studies = {"st": {}}
    app.current_studies = app.dicom_organizer.studies
    coordinator = FileSeriesLoadingCoordinator(app)
    merge = _merge(new_series=[("st", "ser")], appended_series=[("st", "ser")])

    with (
        patch(
            "gui.file_series_loading_coordinator.maybe_evict_after_additive_load",
            return_value=True,
        ) as evict,
        patch("gui.file_series_loading_coordinator.load_ps_ko_for_new_studies") as ps_ko,
        patch(
            "gui.file_series_loading_coordinator.refresh_appended_series_subwindows"
        ) as refresh_appended,
        patch(
            "gui.file_series_loading_coordinator.find_first_empty_subwindow_index",
            return_value=None,
        ),
        patch(
            "gui.file_series_loading_coordinator._get_first_new_series_by_dicom",
            return_value=None,
        ),
        patch("gui.file_series_loading_coordinator.refresh_navigator_after_additive") as nav,
        patch("gui.file_series_loading_coordinator.maybe_show_navigator_for_new_series"),
        patch("gui.file_series_loading_coordinator.refresh_focused_fusion_series_list"),
        patch("gui.file_series_loading_coordinator.show_additive_load_status"),
        patch("gui.file_series_loading_coordinator.finish_additive_load_side_effects") as finish,
    ):
        coordinator.handle_additive_load(merge)

    evict.assert_called_once()
    ps_ko.assert_called_once()
    refresh_appended.assert_called_once_with(app, merge.appended_series)
    nav.assert_called_once()
    finish.assert_called_once()
