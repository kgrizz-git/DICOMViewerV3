"""Tests for gui.actions.view_actions slots (orchestration over the app)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from gui.actions import view_actions as va

_HELPERS = (
    "set_smooth_when_zoomed_all",
    "set_scale_markers_all",
    "set_direction_labels_all",
    "set_slice_slider_all",
    "set_slice_slider_options_all",
    "set_scale_markers_color_all",
    "set_direction_labels_color_all",
)


@pytest.fixture(autouse=True)
def _patch_sync_helpers(monkeypatch):
    for name in _HELPERS:
        monkeypatch.setattr(va, name, MagicMock())


def _app() -> MagicMock:
    app = MagicMock()
    app.multi_window_layout.get_all_subwindows.return_value = []
    return app


def test_privacy_toggled_on_syncs_navigator_and_action() -> None:
    app = _app()
    app.main_window.privacy_action.isChecked.return_value = False
    va.on_privacy_view_toggled(app, True)
    assert app.privacy_view_enabled is True
    app._privacy_controller.apply_privacy.assert_called_once_with(True)
    app.series_navigator.set_privacy_mode.assert_called_once_with(True)
    app.main_window.privacy_action.setChecked.assert_called_once_with(True)


def test_privacy_toggled_off_shows_toast() -> None:
    app = _app()
    app.main_window.privacy_action.isChecked.return_value = False
    va.on_privacy_view_toggled(app, False)
    app.main_window.show_toast_message.assert_called_once()


def test_slice_sync_toggled_persists_and_pushes() -> None:
    app = _app()
    va.on_slice_sync_toggled(app, True)
    app.config_manager.set_slice_sync_enabled.assert_called_once_with(True)
    app._slice_sync_coordinator.set_enabled.assert_called_once_with(True)
    app._refresh_slice_sync_group_indicators.assert_called_once()


def test_slice_sync_groups_changed() -> None:
    app = _app()
    va.on_slice_sync_groups_changed(app, [[0, 1]])
    app.config_manager.set_slice_sync_groups.assert_called_once_with([[0, 1]])
    app._slice_sync_coordinator.set_groups.assert_called_once_with([[0, 1]])
    app._slice_sync_coordinator.invalidate_cache.assert_called_once()


def test_slice_location_line_toggles() -> None:
    app = _app()
    va.on_slice_location_lines_toggled(app, True)
    app.config_manager.set_slice_location_lines_visible.assert_called_once_with(True)
    va.on_slice_location_lines_same_group_only_toggled(app, True)
    app.config_manager.set_slice_location_lines_same_group_only.assert_called_once_with(True)
    va.on_slice_location_lines_focused_only_toggled(app, False)
    app.config_manager.set_slice_location_lines_focused_only.assert_called_once_with(False)
    va.on_slice_location_lines_mode_toggled(app, "begin_end")
    app.config_manager.set_slice_location_line_mode.assert_called_once_with("begin_end")


def test_smooth_when_zoomed_toggled() -> None:
    app = _app()
    va.on_smooth_when_zoomed_toggled(app, True)
    app.config_manager.set_smooth_image_when_zoomed.assert_called_once_with(True)
    va.set_smooth_when_zoomed_all.assert_called_once_with(app, True)
    app.main_window.set_smooth_when_zoomed_checked.assert_called_once_with(True)


def test_orientation_actions_with_viewer() -> None:
    app = _app()
    va.on_orientation_flip_h(app)
    app.image_viewer.flip_h.assert_called_once()
    va.on_orientation_flip_v(app)
    app.image_viewer.flip_v.assert_called_once()
    va.on_orientation_rotate_cw(app)
    app.image_viewer.rotate_cw.assert_called_once()
    va.on_orientation_rotate_ccw(app)
    app.image_viewer.rotate_ccw.assert_called_once()
    va.on_orientation_rotate_180(app)
    app.image_viewer.rotate_180.assert_called_once()
    va.on_orientation_reset(app)
    app.image_viewer.reset_orientation.assert_called_once()


def test_orientation_actions_without_viewer() -> None:
    app = _app()
    app.image_viewer = None
    # None of these should raise.
    va.on_orientation_flip_h(app)
    va.on_orientation_rotate_180(app)
    va.on_orientation_reset(app)


def test_marker_and_label_toggles() -> None:
    app = _app()
    va.on_scale_markers_toggled(app, True)
    app.config_manager.set_show_scale_markers.assert_called_once_with(True)
    va.on_direction_labels_toggled(app, False)
    app.config_manager.set_show_direction_labels.assert_called_once_with(False)
    va.on_slice_slider_toggled(app, True)
    app.config_manager.set_show_slice_slider.assert_called_once_with(True)


def test_slice_slider_placement_and_direction() -> None:
    app = _app()
    va.on_slice_slider_placement_changed(app, "left")
    app.config_manager.set_slice_slider_placement.assert_called_once_with("left")
    va.set_slice_slider_options_all.assert_called()
    va.on_slice_slider_direction_changed(app, "ttb")
    app.config_manager.set_slice_slider_direction.assert_called_once_with("ttb")


def test_color_changes() -> None:
    app = _app()
    va.on_scale_markers_color_changed(app, 1, 2, 3)
    app.config_manager.set_scale_markers_color.assert_called_once_with(1, 2, 3)
    va.set_scale_markers_color_all.assert_called_once_with(app, (1, 2, 3))
    va.on_direction_labels_color_changed(app, 4, 5, 6)
    app.config_manager.set_direction_labels_color.assert_called_once_with(4, 5, 6)


def test_show_instances_separately_toggled() -> None:
    app = _app()
    va.on_show_instances_separately_toggled(app, True)
    app.config_manager.set_show_instances_separately.assert_called_once_with(True)
    app.series_navigator.set_show_instances_separately.assert_called_once_with(True)
    app._refresh_series_navigator_state.assert_called_once()
