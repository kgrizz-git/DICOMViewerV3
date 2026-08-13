"""Focused state, transform, and synchronization contracts for ViewStateManager."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
from PySide6.QtCore import QPointF

from gui.view_state_manager import ViewStateManager


def _dataset(study: str = "study", series: str = "series", number: int = 2):
    return SimpleNamespace(
        StudyInstanceUID=study,
        SeriesInstanceUID=series,
        SeriesNumber=number,
        Modality="CT",
    )


def _manager() -> ViewStateManager:
    viewer = MagicMock()
    viewer.current_zoom = 1.25
    viewer.image_inverted = False
    viewer.image_item = object()
    viewer.parent.return_value = None
    viewer.get_viewport_center_scene.return_value = QPointF(10.0, 20.0)
    viewer.horizontalScrollBar.return_value.value.return_value = 7
    viewer.verticalScrollBar.return_value.value.return_value = 9

    manager = ViewStateManager(
        dicom_processor=MagicMock(),
        image_viewer=viewer,
        window_level_controls=MagicMock(),
        main_window=MagicMock(),
        overlay_manager=MagicMock(),
    )
    manager.current_window_center = 40.0
    manager.current_window_width = 400.0
    manager.redisplay_slice_callback = MagicMock()
    return manager


def test_setters_update_callbacks_and_navigator_reference() -> None:
    manager = _manager()
    callback = MagicMock()
    navigator = object()

    manager.set_redisplay_slice_callback(callback)
    manager.set_series_navigator(navigator)
    manager._redisplay_current_slice(True)

    assert manager.series_navigator is navigator
    callback.assert_called_once_with(True)


def test_apply_context_preset_updates_state_without_user_modified_flag() -> None:
    manager = _manager()

    manager.apply_window_level_from_context_menu_preset(55.0, 550.0, 2)

    assert (manager.current_window_center, manager.current_window_width) == (55.0, 550.0)
    assert manager.current_preset_index == 2
    assert manager.window_level_user_modified is False
    manager.redisplay_slice_callback.assert_called_once_with(True)


def test_series_identity_and_new_series_detection() -> None:
    manager = _manager()
    first = _dataset()
    manager.current_series_identifier = manager.get_series_identifier(first)

    assert manager.is_new_study_or_series(first) is False
    assert manager.is_new_study_or_series(_dataset(series="other")) is True


def test_initial_fit_zoom_prefers_saved_series_default() -> None:
    manager = _manager()
    manager.current_dataset = _dataset()
    manager.initial_fit_zoom = 1.5
    manager.series_defaults[manager.get_series_identifier(manager.current_dataset)] = {
        "initial_fit_zoom": 2.75
    }

    assert manager.get_initial_fit_zoom() == 2.75


def test_store_initial_view_state_captures_global_fallbacks_only_once() -> None:
    manager = _manager()
    manager.initial_zoom = 9.0
    manager.current_series_identifier = "series-id"

    manager.store_initial_view_state()

    assert manager.initial_zoom == 9.0
    assert manager.initial_h_scroll == 7
    assert manager.initial_v_scroll == 9
    assert manager.initial_scene_center == QPointF(10.0, 20.0)
    assert manager.series_defaults["series-id"]["scene_center"] == QPointF(10.0, 20.0)


def test_reset_view_returns_when_no_reset_zoom_is_available() -> None:
    manager = _manager()
    manager.current_dataset = _dataset()
    manager.initial_zoom = None
    manager.initial_window_center = 40.0
    manager.initial_window_width = 400.0

    manager.reset_view()

    manager.redisplay_slice_callback.assert_not_called()
    manager.window_level_controls.set_window_level.assert_not_called()


def test_reset_view_recalculates_missing_window_level_from_series_range() -> None:
    manager = _manager()
    manager.current_dataset = _dataset()
    manager.current_study_uid = "study"
    manager.current_series_uid = "series"
    manager.current_studies = {"study": {"series": [_dataset()]}}
    manager.series_defaults[manager.get_series_identifier(manager.current_dataset)] = {
        "zoom": 1.0,
        "window_center": None,
        "window_width": None,
        "use_rescaled_values": False,
    }
    manager.dicom_processor.get_series_pixel_value_range.return_value = (0.0, 100.0)
    manager.dicom_processor.get_series_pixel_median.return_value = 60.0
    manager.dicom_processor.get_window_level_from_dataset.return_value = (None, None, False)
    manager.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)

    manager.reset_view(skip_redisplay=True)

    assert (manager.current_window_center, manager.current_window_width) == (60.0, 100.0)
    manager.window_level_controls.set_ranges.assert_called_once_with((0.0, 100.0), (1.0, 100.0))


def test_reset_view_converts_saved_rescaled_window_level_to_raw() -> None:
    manager = _manager()
    manager.current_dataset = _dataset()
    manager.use_rescaled_values = False
    manager.rescale_slope = 2.0
    manager.rescale_intercept = -10.0
    sid = manager.get_series_identifier(manager.current_dataset)
    manager.series_defaults[sid] = {
        "zoom": 1.0,
        "window_center": 20.0,
        "window_width": 40.0,
        "use_rescaled_values": True,
    }
    manager.dicom_processor.get_pixel_value_range.return_value = (0.0, 100.0)
    manager.dicom_processor.convert_window_level_rescaled_to_raw.return_value = (15.0, 20.0)

    manager.reset_view(skip_redisplay=True)

    assert (manager.current_window_center, manager.current_window_width) == (15.0, 20.0)
    manager.dicom_processor.convert_window_level_rescaled_to_raw.assert_called_once_with(
        20.0, 40.0, 2.0, -10.0
    )


@patch("core.view_state_handlers.update_zoom_wl_status_from_view_state")
def test_window_level_drag_clamps_and_redisplays(mock_status: MagicMock) -> None:
    manager = _manager()
    manager.image_viewer.right_mouse_drag_start_center = 50.0
    manager.image_viewer.right_mouse_drag_start_width = 100.0
    manager.window_level_controls.center_range = (0.0, 100.0)
    manager.window_level_controls.width_range = (10.0, 150.0)
    manager.window_level_controls.set_window_level = MagicMock()
    manager.window_level_presets = []

    manager.handle_window_level_drag(75.0, 100.0)

    manager.window_level_controls.set_window_level.assert_called_once_with(
        100.0, 150.0, block_signals=True
    )
    manager.redisplay_slice_callback.assert_called_once_with(True)
    mock_status.assert_called_once_with(manager)


def test_window_level_drag_without_initialized_start_is_ignored() -> None:
    manager = _manager()
    manager.image_viewer.right_mouse_drag_start_center = None
    manager.image_viewer.right_mouse_drag_start_width = 10.0

    manager.handle_window_level_drag(1.0, 1.0)

    manager.window_level_controls.set_window_level.assert_not_called()


def test_right_mouse_press_captures_control_values_and_ranges() -> None:
    manager = _manager()
    manager.window_level_controls.get_window_level.return_value = (40.0, 400.0)
    manager.window_level_controls.center_range = (-100.0, 100.0)
    manager.window_level_controls.width_range = (1.0, 800.0)

    manager.handle_right_mouse_press_for_drag()

    manager.image_viewer.set_window_level_for_drag.assert_called_once_with(
        40.0, 400.0, (-100.0, 100.0), (1.0, 800.0)
    )


def test_transform_and_zoom_updates_are_guarded_without_dataset() -> None:
    manager = _manager()
    manager.current_dataset = None
    transform = MagicMock()
    transform.m31.return_value = 0.0
    transform.m32.return_value = 0.0
    manager.image_viewer.transform.return_value = transform

    manager.handle_zoom_changed(2.0)
    manager.handle_transform_changed()

    manager.overlay_manager.update_overlay_positions.assert_not_called()


def test_transform_and_zoom_updates_refresh_overlay_with_dataset() -> None:
    manager = _manager()
    manager.current_dataset = _dataset()
    transform = MagicMock()
    transform.m31.return_value = 0.0
    transform.m32.return_value = 0.0
    manager.image_viewer.transform.return_value = transform

    manager.handle_zoom_changed(2.0)
    manager.handle_transform_changed()

    assert manager.overlay_manager.update_overlay_positions.call_count == 2
    manager.overlay_manager.update_overlay_positions.assert_called_with(manager.image_viewer.scene)


def test_viewport_resize_capture_guard_and_overlay_focus_policy() -> None:
    manager = _manager()
    manager.image_viewer.image_item = None
    manager.current_dataset = None
    manager.overlay_manager.use_widget_overlays = False
    manager.handle_viewport_resizing()
    manager.handle_viewport_resized()

    assert manager.saved_scene_center is None
    assert manager._viewport_pixel_size_at_last_resize is None
    manager.overlay_manager.update_overlay_positions.assert_not_called()


def test_user_window_level_cache_requires_modified_complete_state() -> None:
    manager = _manager()
    manager.current_series_identifier = "series-id"
    manager.window_level_user_modified = True

    manager.save_user_window_level()

    assert manager.get_user_window_level("series-id") == {
        "window_center": 40.0,
        "window_width": 400.0,
    }
    manager.clear_user_window_level("series-id")
    assert manager.get_user_window_level("series-id") is None


def test_reset_state_clears_window_level_series_and_pixel_range() -> None:
    manager = _manager()
    manager.window_level_presets = [(1.0, 2.0, False, "preset")]
    manager._wl_preset_objects = [object()]
    manager.series_defaults["series-id"] = {"zoom": 1.0}
    manager._user_wl_cache["series-id"] = {"window_center": 1.0, "window_width": 2.0}
    manager.set_series_pixel_range(1.0, 9.0)

    manager.reset_window_level_state()
    manager.reset_series_tracking()

    assert manager.current_window_center is None
    assert manager.window_level_presets == []
    assert manager.current_series_identifier is None
    assert manager.series_defaults == {}
    assert manager.get_series_pixel_range() == (None, None)


def test_rescale_conversion_and_control_refresh_preserve_window_level() -> None:
    manager = _manager()
    manager.current_dataset = _dataset()
    manager.rescale_slope = 2.0
    manager.rescale_intercept = -10.0
    manager.rescale_type = "HU"
    manager.dicom_processor.convert_window_level_raw_to_rescaled.return_value = (70.0, 800.0)
    manager.dicom_processor.get_pixel_value_range.return_value = (-20.0, 200.0)

    with patch("core.view_state_handlers.update_zoom_wl_status_from_view_state"):
        manager.handle_rescale_toggle(True)

    assert manager.use_rescaled_values is True
    assert (manager.current_window_center, manager.current_window_width) == (70.0, 800.0)
    manager.window_level_controls.set_unit.assert_called_with("HU")
    manager.redisplay_slice_callback.assert_called_once_with(True)


def test_single_slice_fallback_uses_nonzero_median_and_rescale() -> None:
    manager = _manager()
    dataset = _dataset()
    manager.dicom_processor.get_pixel_value_range.return_value = (0.0, 20.0)
    manager.dicom_processor.get_pixel_array.return_value = np.array([0, 4, 8], dtype=np.int16)
    manager.dicom_processor.get_rescale_parameters.return_value = (2.0, 10.0, "HU")

    center, width = manager._wl_from_single_slice_fallback(dataset, use_rescaled=True)

    assert (center, width) == (18.0, 20.0)


def test_inversion_and_orientation_guards_use_current_series() -> None:
    manager = _manager()
    manager.current_series_identifier = "series-id"
    manager.image_viewer._flip_h = False
    manager.image_viewer._flip_v = False
    manager.image_viewer._rotation_deg = 0

    assert manager.get_series_inversion_state() is False
    manager.set_series_inversion_state(inverted=True)
    assert manager.get_series_inversion_state() is True
    manager.save_orientation()
    manager.restore_orientation()

    assert manager.series_defaults["series-id"]["flip_h"] is False
    manager.image_viewer._apply_view_transform.assert_called_once_with()
