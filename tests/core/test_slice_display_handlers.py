"""Unit tests for core.slice_display_handlers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import core.slice_display_handlers as slice_display_handlers


def _make_app(**overrides) -> SimpleNamespace:
    defaults = {
        "current_dataset": None,
        "current_studies": {},
        "current_study_uid": "study",
        "current_series_uid": "1.2.826.0.1.3680043.8.498.2",
        "current_slice_index": 1,
        "slice_display_manager": SimpleNamespace(
            set_current_data_context=MagicMock(),
            display_slice=MagicMock(),
            display_rois_for_slice=MagicMock(),
            display_measurements_for_slice=MagicMock(),
        ),
        "roi_manager": SimpleNamespace(
            get_rois_for_slice=MagicMock(return_value=[]),
            get_selected_roi=MagicMock(return_value=None),
        ),
        "roi_list_panel": SimpleNamespace(select_roi_in_list=MagicMock(), update_roi_list=MagicMock()),
        "roi_coordinator": SimpleNamespace(update_roi_statistics=MagicMock()),
        "roi_statistics_panel": SimpleNamespace(clear_statistics=MagicMock()),
        "_update_series_navigator_highlighting": MagicMock(),
        "series_navigator": SimpleNamespace(set_subwindow_assignments=MagicMock()),
        "_get_subwindow_assignments": MagicMock(return_value={"A": 0}),
        "view_state_manager": SimpleNamespace(initial_zoom=None, store_initial_view_state=MagicMock()),
        "main_window": SimpleNamespace(update_status=MagicMock()),
        "file_dialog": SimpleNamespace(show_error=MagicMock()),
        "focused_subwindow_index": 0,
        "_mpr_controller": SimpleNamespace(is_mpr=MagicMock(return_value=False), display_mpr_slice=MagicMock()),
        "subwindow_data": {},
        "subwindow_managers": {},
        "cine_player": SimpleNamespace(is_cine_advancing=MagicMock(return_value=False), reset_cine_advancing_flag=MagicMock()),
        "cine_controls_widget": SimpleNamespace(update_frame_position=MagicMock()),
        "image_viewer": SimpleNamespace(set_navigation_slider_state=MagicMock()),
        "_slice_sync_coordinator": SimpleNamespace(on_slice_changed=MagicMock()),
        "_slice_location_line_coordinator": SimpleNamespace(refresh_all=MagicMock()),
        "_update_about_this_file_dialog": MagicMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestDisplaySlice:
    def test_displays_slice_rois_assignments_and_stores_initial_view(self, monkeypatch) -> None:
        single_shot = MagicMock()
        monkeypatch.setattr(slice_display_handlers.QTimer, "singleShot", single_shot)
        display_rois = MagicMock()
        monkeypatch.setattr(slice_display_handlers, "display_rois_for_slice", display_rois)
        app = _make_app()

        slice_display_handlers.display_slice(app, "dataset", preserve_view_override=False)

        assert app.current_dataset == "dataset"
        app.slice_display_manager.set_current_data_context.assert_called_once_with(
            app.current_studies,
            app.current_study_uid,
            app.current_series_uid,
            app.current_slice_index,
        )
        app.slice_display_manager.display_slice.assert_called_once_with(
            "dataset",
            app.current_studies,
            app.current_study_uid,
            app.current_series_uid,
            app.current_slice_index,
            preserve_view_override=False,
        )
        display_rois.assert_called_once_with(app, "dataset")
        app._update_series_navigator_highlighting.assert_called_once_with()
        app.series_navigator.set_subwindow_assignments.assert_called_once_with({"A": 0})
        single_shot.assert_called_once_with(100, app.view_state_manager.store_initial_view_state)

    def test_memory_error_updates_status_and_shows_dialog(self) -> None:
        app = _make_app()
        app.slice_display_manager.display_slice.side_effect = MemoryError("out")

        slice_display_handlers.display_slice(app, "dataset")

        app.main_window.update_status.assert_called_once()
        app.file_dialog.show_error.assert_called_once()

    def test_general_exception_updates_status_without_dialog(self) -> None:
        app = _make_app(file_dialog=None)
        app.slice_display_manager.display_slice.side_effect = RuntimeError("boom")

        slice_display_handlers.display_slice(app, "dataset")

        app.main_window.update_status.assert_called_once()


class TestRedisplayCurrentSlice:
    def test_uses_mpr_controller_for_mpr_subwindow(self) -> None:
        app = _make_app(
            _mpr_controller=SimpleNamespace(is_mpr=MagicMock(return_value=True), display_mpr_slice=MagicMock()),
            subwindow_data={0: {"mpr_slice_index": 7}},
        )

        slice_display_handlers.redisplay_current_slice(app, preserve_view=False)

        app._mpr_controller.display_mpr_slice.assert_called_once_with(0, 7)

    def test_redisplays_current_dataset_when_present(self, monkeypatch) -> None:
        display_slice = MagicMock()
        monkeypatch.setattr(slice_display_handlers, "display_slice", display_slice)
        app = _make_app(current_dataset="dataset")

        slice_display_handlers.redisplay_current_slice(app, preserve_view=False)

        display_slice.assert_called_once_with(app, "dataset", preserve_view_override=False)


class TestDisplayRoisForSlice:
    def test_selected_roi_in_slice_updates_list_and_statistics(self) -> None:
        dataset = SimpleNamespace(
            StudyInstanceUID="study",
            SeriesInstanceUID="1.2.826.0.1.3680043.8.498.9",
            SeriesNumber="4",
        )
        app = _make_app()
        app.roi_manager.get_rois_for_slice.return_value = ["roi-1"]
        app.roi_manager.get_selected_roi.return_value = "roi-1"

        slice_display_handlers.display_rois_for_slice(app, dataset)

        app.roi_list_panel.select_roi_in_list.assert_called_once_with("roi-1")
        app.roi_coordinator.update_roi_statistics.assert_called_once_with("roi-1")
        app.roi_statistics_panel.clear_statistics.assert_not_called()

    def test_missing_or_unselected_roi_clears_statistics(self) -> None:
        dataset = SimpleNamespace(
            StudyInstanceUID="study",
            SeriesInstanceUID="1.2.826.0.1.3680043.8.498.9",
            SeriesNumber="4",
        )
        app = _make_app()
        app.roi_manager.get_rois_for_slice.return_value = []
        app.roi_manager.get_selected_roi.return_value = "roi-1"

        slice_display_handlers.display_rois_for_slice(app, dataset)
        slice_display_handlers.display_measurements_for_slice(app, dataset)

        app.roi_statistics_panel.clear_statistics.assert_called_once_with()
        app.slice_display_manager.display_measurements_for_slice.assert_called_once_with(dataset)


def test_update_roi_list_uses_current_dataset_when_present() -> None:
    dataset = SimpleNamespace(
        StudyInstanceUID="study",
        SeriesInstanceUID="1.2.826.0.1.3680043.8.498.11",
        SeriesNumber="2",
    )
    app = _make_app(current_dataset=dataset, current_slice_index=3)

    slice_display_handlers.update_roi_list(app)

    app.roi_list_panel.update_roi_list.assert_called_once_with(
        "study",
        "1.2.826.0.1.3680043.8.498.11_2",
        3,
    )


class TestOnSliceChanged:
    def test_mpr_path_updates_frame_position_slider_and_sync(self, monkeypatch) -> None:
        single_shot = MagicMock()
        monkeypatch.setattr(slice_display_handlers.QTimer, "singleShot", single_shot)
        app = _make_app(
            _mpr_controller=SimpleNamespace(is_mpr=MagicMock(return_value=True), display_mpr_slice=MagicMock()),
            subwindow_data={0: {"mpr_result": SimpleNamespace(n_slices=12)}},
            cine_player=SimpleNamespace(is_cine_advancing=MagicMock(return_value=True), reset_cine_advancing_flag=MagicMock()),
        )

        slice_display_handlers.on_slice_changed(app, 4)

        app._mpr_controller.display_mpr_slice.assert_called_once_with(0, 4)
        app.cine_controls_widget.update_frame_position.assert_called_once_with(4, 12)
        app.image_viewer.set_navigation_slider_state.assert_called_once()
        app._slice_sync_coordinator.on_slice_changed.assert_called_once_with(0)
        app._slice_location_line_coordinator.refresh_all.assert_called_once_with()
        single_shot.assert_called_once_with(0, app.cine_player.reset_cine_advancing_flag)

    def test_regular_path_updates_subwindow_state_and_display(self, monkeypatch) -> None:
        single_shot = MagicMock()
        monkeypatch.setattr(slice_display_handlers.QTimer, "singleShot", single_shot)
        dataset0 = SimpleNamespace(
            StudyInstanceUID="study",
            SeriesInstanceUID="1.2.826.0.1.3680043.8.498.12",
            SeriesNumber="1",
        )
        dataset1 = SimpleNamespace(
            StudyInstanceUID="study",
            SeriesInstanceUID="1.2.826.0.1.3680043.8.498.12",
            SeriesNumber="1",
        )
        crosshair = SimpleNamespace(update_crosshairs_for_slice=MagicMock())
        managers = {"slice_display_manager": SimpleNamespace(display_slice=MagicMock()), "crosshair_coordinator": crosshair}
        app = _make_app(
            subwindow_data={0: {"current_series_uid": "series", "current_study_uid": "study"}},
            subwindow_managers={0: managers},
            current_studies={"study": {"series": [dataset0, dataset1]}},
            cine_player=SimpleNamespace(is_cine_advancing=MagicMock(return_value=True), reset_cine_advancing_flag=MagicMock()),
        )

        slice_display_handlers.on_slice_changed(app, 1)

        assert app.subwindow_data[0]["current_slice_index"] == 1
        assert app.subwindow_data[0]["current_dataset"] is dataset1
        assert app.current_dataset is dataset1
        managers["slice_display_manager"].display_slice.assert_called_once_with(
            dataset1,
            app.current_studies,
            "study",
            "series",
            1,
        )
        app._update_series_navigator_highlighting.assert_called_once_with()
        app.series_navigator.set_subwindow_assignments.assert_called_once_with({"A": 0})
        app._update_about_this_file_dialog.assert_called_once_with()
        crosshair.update_crosshairs_for_slice.assert_called_once_with()
        app.cine_controls_widget.update_frame_position.assert_called_once_with(1, 2)
        app.image_viewer.set_navigation_slider_state.assert_called_once()
        app._slice_sync_coordinator.on_slice_changed.assert_called_once_with(0)
        app._slice_location_line_coordinator.refresh_all.assert_called_once_with()
        single_shot.assert_called_once_with(0, app.cine_player.reset_cine_advancing_flag)

    def test_returns_early_for_invalid_series_context(self) -> None:
        app = _make_app(
            subwindow_data={0: {"current_series_uid": "", "current_study_uid": "study"}},
            subwindow_managers={0: {"slice_display_manager": SimpleNamespace(display_slice=MagicMock())}},
            current_studies={"study": {"series": [SimpleNamespace()]}},
        )

        slice_display_handlers.on_slice_changed(app, 0)

        app._slice_sync_coordinator.on_slice_changed.assert_not_called()
