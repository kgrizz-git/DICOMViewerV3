"""Unit tests for core.view_state_handlers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import core.view_state_handlers as view_state_handlers
from utils.dicom_utils import get_composite_series_key


def _make_app(**overrides):
    defaults = {
        "view_state_manager": MagicMock(),
        "roi_manager": MagicMock(),
        "roi_coordinator": MagicMock(),
        "roi_statistics_panel": MagicMock(),
        "current_dataset": None,
        "current_slice_index": 0,
        "focused_subwindow_index": 0,
        "main_window": MagicMock(),
        "measurement_tool": MagicMock(),
        "image_viewer": MagicMock(current_zoom=2.0),
        "window_level_controls": MagicMock(unit="HU"),
        "subwindow_managers": {},
        "subwindow_data": {},
        "current_studies": {},
        "_get_subwindow_dataset": MagicMock(return_value=None),
    }
    defaults.update(overrides)
    app = SimpleNamespace(**defaults)
    app.window_level_controls.get_window_level.return_value = (40.0, 400.0)
    return app


class TestOnRescaleToggleChanged:
    def test_calls_handle_rescale_toggle(self):
        app = _make_app()
        view_state_handlers.on_rescale_toggle_changed(app, True)
        app.view_state_manager.handle_rescale_toggle.assert_called_once_with(True)

    def test_no_selected_roi_clears_statistics(self):
        app = _make_app()
        app.roi_manager.get_selected_roi.return_value = None
        view_state_handlers.on_rescale_toggle_changed(app, False)
        app.roi_statistics_panel.clear_statistics.assert_called_once()
        app.roi_coordinator.update_roi_statistics.assert_not_called()

    def test_selected_roi_but_no_current_dataset_clears_statistics(self):
        app = _make_app()
        app.roi_manager.get_selected_roi.return_value = "roi1"
        app.current_dataset = None
        view_state_handlers.on_rescale_toggle_changed(app, False)
        app.roi_statistics_panel.clear_statistics.assert_called_once()

    def test_selected_roi_in_current_slice_updates_statistics(self):
        app = _make_app()
        ds = SimpleNamespace(StudyInstanceUID="study1", SeriesInstanceUID="series1", SeriesNumber=1)
        app.current_dataset = ds
        app.roi_manager.get_selected_roi.return_value = "roi1"
        app.roi_manager.get_rois_for_slice.return_value = ["roi1", "roi2"]
        view_state_handlers.on_rescale_toggle_changed(app, False)
        series_key = get_composite_series_key(ds)
        app.roi_manager.get_rois_for_slice.assert_called_once_with("study1", series_key, 0)
        app.roi_coordinator.update_roi_statistics.assert_called_once_with("roi1")
        app.roi_statistics_panel.clear_statistics.assert_not_called()

    def test_selected_roi_not_in_current_slice_clears_statistics(self):
        app = _make_app()
        ds = SimpleNamespace(StudyInstanceUID="study1", SeriesInstanceUID="series1", SeriesNumber=1)
        app.current_dataset = ds
        app.roi_manager.get_selected_roi.return_value = "roi1"
        app.roi_manager.get_rois_for_slice.return_value = ["roi2"]
        view_state_handlers.on_rescale_toggle_changed(app, False)
        app.roi_statistics_panel.clear_statistics.assert_called_once()
        app.roi_coordinator.update_roi_statistics.assert_not_called()

    def test_dialog_coordinator_present_updates_histogram(self):
        app = _make_app(dialog_coordinator=MagicMock(), focused_subwindow_index=3)
        view_state_handlers.on_rescale_toggle_changed(app, False)
        app.dialog_coordinator.update_histogram_for_subwindow.assert_called_once_with(3)

    def test_dialog_coordinator_absent_no_histogram_update(self):
        defaults = {
            "view_state_manager": MagicMock(),
            "roi_manager": MagicMock(),
            "roi_coordinator": MagicMock(),
            "roi_statistics_panel": MagicMock(),
            "current_dataset": None,
            "current_slice_index": 0,
            "focused_subwindow_index": 0,
        }
        app = SimpleNamespace(**defaults)
        app.roi_manager.get_selected_roi.return_value = None
        # Should not raise even though dialog_coordinator attribute doesn't exist.
        view_state_handlers.on_rescale_toggle_changed(app, False)
        app.roi_statistics_panel.clear_statistics.assert_called_once()


class TestOnResetAllViews:
    def test_no_subwindow_managers_is_noop(self):
        app = _make_app(subwindow_managers={})
        view_state_handlers.on_reset_all_views(app)  # should not raise

    def test_view_state_manager_none_skips(self):
        app = _make_app(subwindow_managers={0: {}})
        view_state_handlers.on_reset_all_views(app)  # no error, nothing to assert

    def test_current_dataset_none_skips_reset(self):
        vsm = MagicMock(current_dataset=None)
        app = _make_app(subwindow_managers={0: {"view_state_manager": vsm}})
        view_state_handlers.on_reset_all_views(app)
        vsm.reset_view.assert_not_called()

    def test_resets_view_without_subwindow_data(self):
        vsm = MagicMock(current_dataset=SimpleNamespace())
        app = _make_app(subwindow_managers={0: {"view_state_manager": vsm}}, subwindow_data={})
        view_state_handlers.on_reset_all_views(app)
        vsm.reset_view.assert_called_once_with(skip_redisplay=True)

    def test_display_slice_uses_subwindow_dataset_when_available(self):
        vsm = MagicMock(current_dataset=SimpleNamespace())
        sdm = MagicMock()
        dataset = SimpleNamespace(name="ds")
        app = _make_app(
            subwindow_managers={0: {"view_state_manager": vsm, "slice_display_manager": sdm}},
            subwindow_data={0: {"current_study_uid": "s1", "current_series_uid": "se1", "current_slice_index": 2}},
        )
        app._get_subwindow_dataset.return_value = dataset
        view_state_handlers.on_reset_all_views(app)
        sdm.display_slice.assert_called_once_with(
            dataset, app.current_studies, "s1", "se1", 2, preserve_view_override=False
        )

    def test_display_slice_falls_back_to_data_current_dataset(self):
        vsm = MagicMock(current_dataset=SimpleNamespace())
        sdm = MagicMock()
        fallback_dataset = SimpleNamespace(name="fallback")
        app = _make_app(
            subwindow_managers={0: {"view_state_manager": vsm, "slice_display_manager": sdm}},
            subwindow_data={0: {"current_dataset": fallback_dataset}},
        )
        app._get_subwindow_dataset.return_value = None
        view_state_handlers.on_reset_all_views(app)
        args, kwargs = sdm.display_slice.call_args
        assert args[0] is fallback_dataset

    def test_no_dataset_available_skips_display_slice(self):
        vsm = MagicMock(current_dataset=SimpleNamespace())
        sdm = MagicMock()
        app = _make_app(
            subwindow_managers={0: {"view_state_manager": vsm, "slice_display_manager": sdm}},
            subwindow_data={0: {}},
        )
        app._get_subwindow_dataset.return_value = None
        view_state_handlers.on_reset_all_views(app)
        sdm.display_slice.assert_not_called()

    def test_no_slice_display_manager_skips_display_slice(self):
        vsm = MagicMock(current_dataset=SimpleNamespace())
        dataset = SimpleNamespace()
        app = _make_app(
            subwindow_managers={0: {"view_state_manager": vsm, "slice_display_manager": None}},
            subwindow_data={0: {"current_dataset": dataset}},
        )
        view_state_handlers.on_reset_all_views(app)  # no error


class TestOnZoomChanged:
    def test_delegates_to_view_state_manager_and_measurement_tool(self):
        app = _make_app()
        view_state_handlers.on_zoom_changed(app, 1.5)
        app.view_state_manager.handle_zoom_changed.assert_called_once_with(1.5)
        app.measurement_tool.update_all_measurement_text_offsets.assert_called_once()
        app.main_window.update_zoom_preset_status.assert_called_once()


class TestOnTransformChanged:
    def test_delegates_to_view_state_manager_and_measurement_tool(self):
        app = _make_app()
        view_state_handlers.on_transform_changed(app)
        app.view_state_manager.handle_transform_changed.assert_called_once()
        app.measurement_tool.update_all_measurement_text_offsets.assert_called_once()


class TestOnViewportResizing:
    def test_delegates_to_view_state_manager(self):
        app = _make_app()
        view_state_handlers.on_viewport_resizing(app)
        app.view_state_manager.handle_viewport_resizing.assert_called_once()


class TestOnViewportResized:
    def test_delegates_to_view_state_manager(self):
        app = _make_app()
        view_state_handlers.on_viewport_resized(app)
        app.view_state_manager.handle_viewport_resized.assert_called_once()


class TestOnPixelInfoChanged:
    def test_pixel_value_str_present_formats_full_text(self):
        app = _make_app()
        app.main_window.pixel_info_label = MagicMock()
        view_state_handlers.on_pixel_info_changed(app, "100 HU", 5, 6, 7)
        app.main_window.pixel_info_label.setText.assert_called_once_with(
            "Pixel: 100 HU  (x: 5, y: 6, z: 7)"
        )

    def test_empty_pixel_value_with_nonzero_coords_shows_coords_only(self):
        app = _make_app()
        app.main_window.pixel_info_label = MagicMock()
        view_state_handlers.on_pixel_info_changed(app, "", 1, 0, 0)
        app.main_window.pixel_info_label.setText.assert_called_once_with("(x: 1, y: 0, z: 0)")

    def test_empty_pixel_value_with_all_zero_coords_shows_empty_string(self):
        app = _make_app()
        app.main_window.pixel_info_label = MagicMock()
        view_state_handlers.on_pixel_info_changed(app, "", 0, 0, 0)
        app.main_window.pixel_info_label.setText.assert_called_once_with("")

    def test_no_pixel_info_label_attribute_is_noop(self):
        app = _make_app()
        app.main_window = SimpleNamespace()  # no pixel_info_label attribute
        view_state_handlers.on_pixel_info_changed(app, "100 HU", 1, 2, 3)  # should not raise


class TestUpdateZoomPresetStatusBar:
    def test_uses_image_viewer_zoom_when_present(self):
        app = _make_app()
        app.image_viewer.current_zoom = 3.0
        view_state_handlers.update_zoom_preset_status_bar(app)
        app.main_window.update_zoom_preset_status.assert_called_once_with(3.0, 40.0, 400.0, unit="HU")

    def test_defaults_zoom_to_one_when_image_viewer_none(self):
        app = _make_app(image_viewer=None)
        view_state_handlers.update_zoom_preset_status_bar(app)
        app.main_window.update_zoom_preset_status.assert_called_once_with(1.0, 40.0, 400.0, unit="HU")


class TestUpdateZoomWlStatusFromViewState:
    def _make_vsm(self, **overrides):
        defaults = {
            "image_viewer": MagicMock(current_zoom=2.0),
            "current_window_center": None,
            "current_window_width": None,
            "window_level_controls": MagicMock(unit="HU"),
            "main_window": MagicMock(),
        }
        defaults.update(overrides)
        vsm = SimpleNamespace(**defaults)
        vsm.window_level_controls.get_window_level.return_value = (50.0, 500.0)
        return vsm

    def test_uses_current_window_center_width_when_both_present(self):
        vsm = self._make_vsm(current_window_center=10.0, current_window_width=20.0)
        view_state_handlers.update_zoom_wl_status_from_view_state(vsm)
        vsm.window_level_controls.get_window_level.assert_not_called()
        vsm.main_window.update_zoom_preset_status.assert_called_once_with(2.0, 10.0, 20.0, unit="HU")

    def test_falls_back_to_window_level_controls_when_center_missing(self):
        vsm = self._make_vsm(current_window_center=None, current_window_width=20.0)
        view_state_handlers.update_zoom_wl_status_from_view_state(vsm)
        vsm.main_window.update_zoom_preset_status.assert_called_once_with(2.0, 50.0, 500.0, unit="HU")

    def test_defaults_zoom_to_one_when_image_viewer_none(self):
        vsm = self._make_vsm(image_viewer=None, current_window_center=1.0, current_window_width=2.0)
        view_state_handlers.update_zoom_wl_status_from_view_state(vsm)
        vsm.main_window.update_zoom_preset_status.assert_called_once_with(1.0, 1.0, 2.0, unit="HU")
