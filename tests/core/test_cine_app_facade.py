"""Tests for core.cine_app_facade.CineAppFacade.

The facade only orchestrates the app's cine player / controls, so a MagicMock
app (with real dicts for iterated state) is sufficient.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from core.cine_app_facade import CineAppFacade


def _app() -> MagicMock:
    app = MagicMock()
    app.current_studies = {}
    app.subwindow_data = {}
    app.focused_subwindow_index = -1
    app.image_viewer = MagicMock()
    return app


def test_update_context_capable_series() -> None:
    app = _app()
    app.current_studies = {"st": {"sr": [object(), object()]}}
    app.current_study_uid = "st"
    app.current_series_uid = "sr"
    app.subwindow_data = {0: {}}
    app.focused_subwindow_index = 0
    app.cine_player.is_cine_capable.return_value = True
    app.cine_player.is_playback_active.return_value = False
    app.slice_navigator.total_slices = 5
    app.slice_navigator.get_current_slice.return_value = 2

    CineAppFacade(app).update_cine_player_context()

    app.cine_player.set_datasets.assert_called_once()
    app.cine_controls_widget.set_controls_enabled.assert_called_once_with(True)
    app.cine_controls_widget.update_frame_position.assert_called_with(2, 5)
    app.image_viewer.set_cine_controls_enabled.assert_called_once_with(True)


def test_update_context_not_capable_stops_active_playback() -> None:
    app = _app()
    app.current_study_uid = ""
    app.current_series_uid = ""
    app.cine_player.is_cine_capable.return_value = False
    app.cine_player.is_playback_active.return_value = True

    CineAppFacade(app).update_cine_player_context()

    app.cine_controls_widget.set_controls_enabled.assert_called_once_with(False)
    app.cine_controls_widget.update_frame_position.assert_called_with(0, 0)
    app.cine_player.stop_playback.assert_called_once()


def test_update_context_mpr_forces_capable() -> None:
    app = _app()
    app.current_study_uid = ""
    app.current_series_uid = ""
    app.focused_subwindow_index = 0
    app.subwindow_data = {0: {"is_mpr": True, "mpr_result": SimpleNamespace(n_slices=10)}}
    app.cine_player.is_cine_capable.return_value = False
    app.cine_player.is_playback_active.return_value = False
    app.slice_navigator.total_slices = 10
    app.slice_navigator.get_current_slice.return_value = 0

    CineAppFacade(app).update_cine_player_context()

    app.cine_player.set_use_linear_cine_navigation.assert_called_once_with(True)
    app.cine_controls_widget.set_controls_enabled.assert_called_once_with(True)


def test_update_context_image_viewer_none() -> None:
    app = _app()
    app.image_viewer = None
    app.current_study_uid = ""
    app.current_series_uid = ""
    app.cine_player.is_cine_capable.return_value = False
    app.cine_player.is_playback_active.return_value = False
    # Should not raise when image_viewer is None.
    CineAppFacade(app).update_cine_player_context()


def test_on_manual_slice_navigation_pauses_when_playing_not_advancing() -> None:
    app = _app()
    app.cine_player.is_playback_active.return_value = True
    app.cine_player.is_cine_advancing.return_value = False
    CineAppFacade(app).on_manual_slice_navigation(3)
    app.cine_player.pause_playback.assert_called_once()


def test_on_manual_slice_navigation_noop_when_advancing() -> None:
    app = _app()
    app.cine_player.is_playback_active.return_value = True
    app.cine_player.is_cine_advancing.return_value = True
    CineAppFacade(app).on_manual_slice_navigation(3)
    app.cine_player.pause_playback.assert_not_called()


def test_on_cine_frame_advance_uses_loop_flag() -> None:
    app = _app()
    app.cine_player.loop_enabled = True
    CineAppFacade(app).on_cine_frame_advance(7)
    app.slice_navigator.advance_to_frame.assert_called_once_with(7, loop=True)


def test_on_playback_state_changed_playing_sets_pause_icon() -> None:
    app = _app()
    app.cine_player.get_effective_frame_rate.return_value = 12.0
    action = MagicMock()
    app.main_window.cine_play_pause_action = action
    CineAppFacade(app).on_cine_playback_state_changed(True)
    app.cine_controls_widget.update_playback_state.assert_called_once_with(True)
    app.cine_controls_widget.update_fps_display.assert_called_once_with(12.0)
    action.setToolTip.assert_called_once()


def test_on_playback_state_changed_no_action() -> None:
    app = _app()
    app.main_window.cine_play_pause_action = None
    CineAppFacade(app).on_cine_playback_state_changed(False)
    app.cine_controls_widget.update_playback_state.assert_called_once_with(False)


def test_on_cine_play_with_dataset() -> None:
    app = _app()
    app.current_dataset = object()
    app.cine_player.get_frame_rate_from_dicom.return_value = 15.0
    app.cine_player.start_playback.return_value = True
    CineAppFacade(app).on_cine_play()
    app.cine_player.start_playback.assert_called_once()
    app.cine_controls_widget.update_fps_display.assert_called_once()


def test_on_cine_play_dataset_none_uses_lifecycle_controller() -> None:
    app = _app()
    app.current_dataset = None
    app.get_focused_subwindow_index.return_value = 1
    app._subwindow_lifecycle_controller.get_subwindow_dataset.return_value = object()
    app.cine_player.start_playback.return_value = False
    CineAppFacade(app).on_cine_play()
    app._subwindow_lifecycle_controller.get_subwindow_dataset.assert_called_once_with(1)
    app.cine_controls_widget.update_fps_display.assert_not_called()


def test_on_cine_play_lifecycle_error_swallowed() -> None:
    app = _app()
    app.current_dataset = None
    app.get_focused_subwindow_index.side_effect = RuntimeError("no focus")
    app.cine_player.start_playback.return_value = False
    # Should not raise.
    CineAppFacade(app).on_cine_play()


def test_play_pause_toggle_when_playing_pauses() -> None:
    app = _app()
    app.cine_player.is_playing = True
    CineAppFacade(app).on_cine_play_pause_toggle()
    app.cine_player.pause_playback.assert_called_once()


def test_play_pause_toggle_when_stopped_plays() -> None:
    app = _app()
    app.cine_player.is_playing = False
    app.current_dataset = None
    app.get_focused_subwindow_index.return_value = 0
    app._subwindow_lifecycle_controller.get_subwindow_dataset.return_value = None
    app.cine_player.start_playback.return_value = False
    CineAppFacade(app).on_cine_play_pause_toggle()
    app.cine_player.start_playback.assert_called_once()


def test_simple_passthroughs() -> None:
    app = _app()
    facade = CineAppFacade(app)
    facade.on_cine_pause()
    app.cine_player.pause_playback.assert_called_once()
    facade.on_cine_stop()
    app.cine_player.stop_playback.assert_called_once()
    app.cine_player.loop_enabled = True
    assert facade.get_cine_loop_state() is True


def test_on_cine_speed_changed() -> None:
    app = _app()
    app.cine_player.get_effective_frame_rate.return_value = 20.0
    CineAppFacade(app).on_cine_speed_changed(2.0)
    app.cine_player.set_speed.assert_called_once_with(2.0)
    app.cine_controls_widget.update_fps_display.assert_called_once_with(20.0)


def test_on_cine_loop_toggled_persists() -> None:
    app = _app()
    CineAppFacade(app).on_cine_loop_toggled(True)
    app.cine_player.set_loop.assert_called_once_with(True)
    app.cine_controls_widget.set_loop.assert_called_once_with(True)
    app.config_manager.set_cine_default_loop.assert_called_once_with(True)


def test_loop_bounds_start_end_clear() -> None:
    app = _app()
    facade = CineAppFacade(app)
    app.cine_player.loop_end_frame = 9
    facade.on_cine_loop_start_set(2)
    app.cine_player.set_loop_bounds.assert_called_with(2, 9)
    app.cine_player.loop_start_frame = 2
    facade.on_cine_loop_end_set(8)
    app.cine_player.set_loop_bounds.assert_called_with(2, 8)
    facade.on_cine_loop_bounds_cleared()
    app.cine_player.clear_loop_bounds.assert_called_once()
    app.cine_controls_widget.set_loop_bounds.assert_called_with(None, None)


def test_on_frame_slider_changed_pauses_and_jumps() -> None:
    app = _app()
    app.cine_player.is_playback_active.return_value = True
    app.slice_navigator.total_slices = 10
    CineAppFacade(app).on_frame_slider_changed(4)
    app.cine_player.pause_playback.assert_called_once()
    app.slice_navigator.set_current_slice.assert_called_once_with(4)


def test_on_frame_slider_changed_out_of_range_no_jump() -> None:
    app = _app()
    app.cine_player.is_playback_active.return_value = False
    app.slice_navigator.total_slices = 3
    CineAppFacade(app).on_frame_slider_changed(9)
    app.slice_navigator.set_current_slice.assert_not_called()
