"""
Characterize ViewStateManager contracts targeted by the Sonar S3776 slice.

Covers store_initial_view_state, reset_view, handle_window_changed,
handle_rescale_toggle, and handle_viewport_resized.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QPointF

from gui.view_state_manager import ViewStateManager


def _mock_viewport(width: int = 800, height: int = 600) -> MagicMock:
    vp = MagicMock()
    vp.width.return_value = width
    vp.height.return_value = height
    return vp


def _make_vsm(**overrides) -> ViewStateManager:
    """Build a ViewStateManager with MagicMock collaborators."""
    scroll = MagicMock()
    scroll.value.return_value = 5
    image_viewer = MagicMock()
    image_viewer.current_zoom = 1.5
    image_viewer.image_inverted = False
    image_viewer.horizontalScrollBar.return_value = scroll
    image_viewer.verticalScrollBar.return_value = scroll
    image_viewer.get_viewport_center_scene.return_value = QPointF(100.0, 200.0)
    image_viewer.image_item = MagicMock()
    image_viewer.parent.return_value = None

    kwargs = {
        "dicom_processor": MagicMock(),
        "image_viewer": image_viewer,
        "window_level_controls": MagicMock(),
        "main_window": MagicMock(),
        "overlay_manager": MagicMock(),
    }
    kwargs.update(overrides)
    vsm = ViewStateManager(**kwargs)
    vsm.current_window_center = 40.0
    vsm.current_window_width = 400.0
    vsm.redisplay_slice_callback = MagicMock()
    vsm.dicom_processor.get_pixel_value_range.return_value = (0.0, 4095.0)
    return vsm


def _ds(
    *,
    study: str = "study-1",
    series: str = "series-1",
    series_number: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        StudyInstanceUID=study,
        SeriesInstanceUID=series,
        SeriesNumber=series_number,
    )


class TestStoreInitialViewState:
    def test_early_return_when_no_image_item(self) -> None:
        vsm = _make_vsm()
        vsm.image_viewer.image_item = None
        vsm.current_series_identifier = "study-1_series-1_1"
        vsm.store_initial_view_state()
        assert vsm.current_series_identifier not in vsm.series_defaults
        vsm.redisplay_slice_callback.assert_not_called()

    def test_creates_series_defaults_entry(self) -> None:
        vsm = _make_vsm()
        vsm.current_series_identifier = "study-1_series-1_1"
        vsm.use_rescaled_values = True
        vsm.store_initial_view_state()
        assert "study-1_series-1_1" in vsm.series_defaults
        entry = vsm.series_defaults["study-1_series-1_1"]
        assert entry["window_center"] == 40.0
        assert entry["window_width"] == 400.0
        assert entry["zoom"] == 1.5
        assert entry["use_rescaled_values"] is True

    def test_restores_wl_when_defaults_already_set(self) -> None:
        vsm = _make_vsm()
        sid = "study-1_series-1_1"
        vsm.current_series_identifier = sid
        vsm.current_window_center = 999.0
        vsm.current_window_width = 888.0
        vsm.rescale_type = "HU"
        vsm.series_defaults[sid] = {
            "window_center": 50.0,
            "window_width": 500.0,
            "use_rescaled_values": True,
            "window_level_defaults_set": True,
            "zoom": 1.0,
        }
        vsm.store_initial_view_state()
        assert vsm.current_window_center == 50.0
        assert vsm.current_window_width == 500.0
        vsm.window_level_controls.set_window_level.assert_called_with(
            50.0, 500.0, block_signals=True, unit="HU"
        )
        vsm.redisplay_slice_callback.assert_called_once_with(True)


class TestResetView:
    def test_early_return_when_no_dataset(self) -> None:
        vsm = _make_vsm()
        vsm.current_dataset = None
        vsm.reset_view()
        vsm.redisplay_slice_callback.assert_not_called()

    def test_applies_series_defaults_wl(self) -> None:
        vsm = _make_vsm()
        ds = _ds()
        vsm.current_dataset = ds
        sid = vsm.get_series_identifier(ds)
        vsm.series_defaults[sid] = {
            "zoom": 2.0,
            "window_center": 60.0,
            "window_width": 600.0,
            "use_rescaled_values": False,
        }
        vsm.reset_view()
        assert vsm.current_window_center == 60.0
        assert vsm.current_window_width == 600.0
        assert vsm.window_level_user_modified is False

    def test_skip_redisplay_does_not_redisplay(self) -> None:
        vsm = _make_vsm()
        ds = _ds()
        vsm.current_dataset = ds
        sid = vsm.get_series_identifier(ds)
        vsm.series_defaults[sid] = {
            "zoom": 2.0,
            "window_center": 60.0,
            "window_width": 600.0,
            "use_rescaled_values": False,
        }
        vsm.reset_view(skip_redisplay=True)
        vsm.redisplay_slice_callback.assert_not_called()

    def test_converts_wl_when_rescale_state_mismatches(self) -> None:
        vsm = _make_vsm()
        ds = _ds()
        vsm.current_dataset = ds
        vsm.use_rescaled_values = True
        vsm.rescale_slope = 1.0
        vsm.rescale_intercept = -1024.0
        sid = vsm.get_series_identifier(ds)
        vsm.series_defaults[sid] = {
            "zoom": 2.0,
            "window_center": 100.0,
            "window_width": 200.0,
            "use_rescaled_values": False,
        }
        vsm.dicom_processor.convert_window_level_raw_to_rescaled.return_value = (
            150.0,
            250.0,
        )
        vsm.reset_view(skip_redisplay=True)
        vsm.dicom_processor.convert_window_level_raw_to_rescaled.assert_called_once_with(
            100.0, 200.0, 1.0, -1024.0
        )
        assert vsm.current_window_center == 150.0
        assert vsm.current_window_width == 250.0


class TestHandleWindowChanged:
    @patch("core.view_state_handlers.update_zoom_wl_status_from_view_state")
    def test_stores_center_width(self, mock_status) -> None:
        vsm = _make_vsm()
        vsm.window_level_presets = []
        vsm.handle_window_changed(55.0, 550.0)
        assert vsm.current_window_center == 55.0
        assert vsm.current_window_width == 550.0
        vsm.redisplay_slice_callback.assert_called_once_with(True)

    @patch("core.view_state_handlers.update_zoom_wl_status_from_view_state")
    def test_marks_user_modified_when_no_presets(self, mock_status) -> None:
        vsm = _make_vsm()
        vsm.window_level_presets = []
        vsm.handle_window_changed(55.0, 550.0)
        assert vsm.window_level_user_modified is True

    @patch("core.view_state_handlers.update_zoom_wl_status_from_view_state")
    def test_matches_preset_when_values_align(self, mock_status) -> None:
        vsm = _make_vsm()
        vsm.use_rescaled_values = False
        vsm.window_level_presets = [
            (40.0, 400.0, False, "Soft tissue"),
            (80.0, 600.0, False, "Bone"),
        ]
        vsm.handle_window_changed(40.0, 400.0)
        assert vsm.current_preset_index == 0
        assert vsm.window_level_user_modified is False


class TestHandleRescaleToggle:
    @patch("core.view_state_handlers.update_zoom_wl_status_from_view_state")
    def test_flips_use_rescaled_values(self, mock_status) -> None:
        vsm = _make_vsm()
        vsm.use_rescaled_values = False
        vsm.rescale_slope = 2.0
        vsm.rescale_intercept = -1024.0
        vsm.current_dataset = _ds()
        vsm.dicom_processor.convert_window_level_raw_to_rescaled.return_value = (
            40.0,
            400.0,
        )
        vsm.handle_rescale_toggle(True)
        assert vsm.use_rescaled_values is True

    @patch("core.view_state_handlers.update_zoom_wl_status_from_view_state")
    def test_updates_toggle_states(self, mock_status) -> None:
        vsm = _make_vsm()
        vsm.current_dataset = _ds()
        vsm.dicom_processor.get_pixel_value_range.return_value = (0.0, 4095.0)
        vsm.handle_rescale_toggle(True)
        vsm.main_window.set_rescale_toggle_state.assert_called_once_with(True)
        vsm.image_viewer.set_rescale_toggle_state.assert_called_once_with(True)

    @patch("core.view_state_handlers.update_zoom_wl_status_from_view_state")
    def test_redisplays_when_dataset_present(self, mock_status) -> None:
        vsm = _make_vsm()
        vsm.current_dataset = _ds()
        vsm.dicom_processor.get_pixel_value_range.return_value = (0.0, 4095.0)
        vsm.handle_rescale_toggle(False)
        vsm.redisplay_slice_callback.assert_called_once_with(True)


class TestHandleViewportResized:
    def test_restores_saved_scene_center(self) -> None:
        vsm = _make_vsm()
        center = QPointF(50.0, 75.0)
        vsm.saved_scene_center = center
        vsm.image_viewer.viewport.return_value = _mock_viewport()
        vsm.handle_viewport_resized()
        vsm.image_viewer.fit_to_view.assert_called_once_with(center_image=False)
        vsm.image_viewer.centerOn.assert_called_once_with(center)
        assert vsm.saved_scene_center is None

    def test_fits_when_no_saved_center(self) -> None:
        vsm = _make_vsm()
        vsm.saved_scene_center = None
        vsm._viewport_pixel_size_at_last_resize = None
        vsm.image_viewer.viewport.return_value = _mock_viewport()
        vsm.image_viewer.is_effectively_fit_and_centered.return_value = False
        vsm.handle_viewport_resized()
        vsm.image_viewer.fit_to_view.assert_called_once_with(center_image=True)

    def test_skips_redundant_fit_when_size_unchanged(self) -> None:
        vsm = _make_vsm()
        vsm.saved_scene_center = None
        vsm._viewport_pixel_size_at_last_resize = (800, 600)
        vsm.image_viewer.viewport.return_value = _mock_viewport()
        vsm.image_viewer.is_effectively_fit_and_centered.return_value = True
        vsm.handle_viewport_resized()
        vsm.image_viewer.fit_to_view.assert_not_called()

    def test_updates_overlay_when_dataset_present(self) -> None:
        vsm = _make_vsm()
        vsm.current_dataset = _ds()
        vsm.overlay_manager.use_widget_overlays = True
        vsm.image_viewer.viewport.return_value = _mock_viewport()
        vsm.handle_viewport_resized()
        vsm.overlay_manager.update_overlay_positions.assert_called_once_with(
            vsm.image_viewer.scene
        )

    def test_no_image_item_clears_viewport_size(self) -> None:
        vsm = _make_vsm()
        vsm.image_viewer.image_item = None
        vsm._viewport_pixel_size_at_last_resize = (800, 600)
        vsm.handle_viewport_resized()
        assert vsm._viewport_pixel_size_at_last_resize is None
