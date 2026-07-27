"""
Characterization tests for first-slice load helpers (Sonar S3776 slice).

Covers helpers extracted from ``FileSeriesLoadingCoordinator.handle_load_first_slice``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydicom.dataset import Dataset

from gui.file_series_first_slice_load import (
    apply_first_slice_load,
    clear_stale_subwindow_data,
    finish_first_slice_paint_side_effects,
    load_presentation_states_and_key_objects,
    maybe_reveal_navigator_and_fit,
    pre_first_slice_reset,
)
from gui.file_series_loading_coordinator import FileSeriesLoadingCoordinator


def test_clear_stale_subwindow_data_clears_missing_series() -> None:
    app = MagicMock()
    app.subwindow_data = {
        0: {
            "current_study_uid": "gone",
            "current_series_uid": "ser",
            "current_dataset": object(),
        },
        1: {
            "current_study_uid": "st",
            "current_series_uid": "ser",
            "current_dataset": object(),
        },
        2: {
            "current_study_uid": "",
            "current_series_uid": "",
            "current_dataset": None,
        },
    }
    studies = {"st": {"ser": [MagicMock()]}}

    count = clear_stale_subwindow_data(app, studies)

    assert count == 1
    assert app.subwindow_data[0]["current_dataset"] is None
    assert app.subwindow_data[0]["current_series_uid"] == ""
    assert app.subwindow_data[1]["current_dataset"] is not None


def test_clear_stale_subwindow_data_clears_missing_study() -> None:
    app = MagicMock()
    app.subwindow_data = {
        3: {
            "current_study_uid": "st",
            "current_series_uid": "missing",
            "current_dataset": object(),
        },
    }
    studies = {"st": {"ser": [MagicMock()]}}

    count = clear_stale_subwindow_data(app, studies)

    assert count == 1
    assert app.subwindow_data[3]["current_datasets"] == []


def test_load_presentation_states_and_key_objects() -> None:
    app = MagicMock()
    app.dicom_organizer.get_presentation_states.side_effect = lambda uid: (
        {"ps": 1} if uid == "A" else None
    )
    app.dicom_organizer.get_key_objects.side_effect = lambda uid: (
        {"ko": 1} if uid == "B" else None
    )
    studies = {"A": {}, "B": {}}

    load_presentation_states_and_key_objects(app, studies)

    app.annotation_manager.load_presentation_states.assert_called_once_with({"A": {"ps": 1}})
    app.annotation_manager.load_key_objects.assert_called_once_with({"B": {"ko": 1}})


def test_pre_first_slice_reset_clears_state() -> None:
    app = MagicMock()
    subwindow = MagicMock()
    app.multi_window_layout.get_all_subwindows.return_value = [subwindow]
    app.subwindow_managers = {
        0: {"overlay_manager": MagicMock()},
    }
    app.current_dataset = object()
    app.tag_edit_history = MagicMock()

    pre_first_slice_reset(app)

    app._reset_fusion_for_all_subwindows.assert_called_once()
    app.tag_edit_history.clear_edited_tags.assert_called_once_with(app.current_dataset)
    subwindow.image_viewer.scene.clear.assert_called_once()
    app.slice_display_manager.reset_projection_state.assert_called_once()
    app.intensity_projection_controls_widget.set_enabled.assert_called_with(False)
    app.dialog_coordinator.clear_tag_viewer_filter.assert_called_once()


def test_maybe_reveal_navigator_and_fit_when_hidden() -> None:
    app = MagicMock()
    app.main_window.series_navigator_visible = False

    with patch("gui.file_series_first_slice_load.QTimer.singleShot") as shot:
        maybe_reveal_navigator_and_fit(app)

    app.main_window.toggle_series_navigator.assert_called_once()
    assert shot.call_count == 1
    assert shot.call_args.args[0] == 50


def test_finish_first_slice_paint_side_effects_schedules_work() -> None:
    app = MagicMock()
    with patch("gui.file_series_first_slice_load.QTimer.singleShot") as shot:
        finish_first_slice_paint_side_effects(app)

    app._slice_sync_coordinator.invalidate_cache.assert_called_once()
    assert shot.call_count == 2


def test_handle_load_first_slice_orchestrates_helpers() -> None:
    app = MagicMock()
    studies = {"st": {"ser": []}}
    app.file_operations_handler.load_first_slice.return_value = {
        "study_uid": "st",
        "series_uid": "ser",
        "slice_index": 0,
        "total_slices": 1,
        "dataset": Dataset(),
    }
    coordinator = FileSeriesLoadingCoordinator(app)

    with (
        patch(
            "gui.file_series_loading_coordinator.pre_first_slice_reset"
        ) as pre_reset,
        patch(
            "gui.file_series_loading_coordinator.apply_first_slice_load"
        ) as apply_load,
    ):
        coordinator.handle_load_first_slice(studies)

    pre_reset.assert_called_once_with(app)
    apply_load.assert_called_once_with(
        app,
        studies,
        app.file_operations_handler.load_first_slice.return_value,
    )


def test_apply_first_slice_load_focuses_subwindow_zero() -> None:
    app = MagicMock()
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3.st"
    ds.SeriesInstanceUID = "1.2.3.ser"
    studies = {"1.2.3.st": {"1.2.3.ser": [ds]}}
    first_slice_info = {
        "study_uid": "1.2.3.st",
        "series_uid": "1.2.3.ser",
        "slice_index": 0,
        "total_slices": 1,
        "dataset": ds,
    }
    subwindow_0 = object()
    app.multi_window_layout.get_subwindow.return_value = subwindow_0
    sdm = MagicMock()
    vsm = MagicMock()
    app.subwindow_managers = {
        0: {
            "slice_display_manager": sdm,
            "view_state_manager": vsm,
            "roi_coordinator": MagicMock(),
        },
    }

    with (
        patch(
            "gui.file_series_additive_load.refresh_focused_fusion_series_list"
        ),
        patch("gui.file_series_first_slice_load.QTimer.singleShot"),
    ):
        apply_first_slice_load(app, studies, first_slice_info)

    app.multi_window_layout.set_focused_subwindow.assert_called_once_with(subwindow_0)
    assert app.focused_subwindow_index == 0
    sdm.display_slice.assert_called_once()
    app._connect_focused_subwindow_signals.assert_called_once()
