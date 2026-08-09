"""
Comprehensive unit tests for src/gui/subwindow_image_viewer_sync.py.

Achieves 100% statement and branch coverage for subwindow_image_viewer_sync.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from gui.subwindow_image_viewer_sync import (
    _iter_image_viewers,
    apply_initial_image_viewer_display_state,
    apply_theme_viewer_background_all,
    set_direction_labels_all,
    set_direction_labels_color_all,
    set_scale_markers_all,
    set_scale_markers_color_all,
    set_slice_slider_all,
    set_slice_slider_options_all,
    set_smooth_when_zoomed_all,
)


@pytest.fixture
def mock_app() -> SimpleNamespace:
    """Fixture providing a mock app instance with multi_window_layout and config_manager."""
    app = SimpleNamespace()
    app.privacy_view_enabled = False
    app.config_manager = MagicMock()
    app.multi_window_layout = MagicMock()

    # Configure default config_manager returns
    app.config_manager.get_theme.return_value = "dark"
    app.config_manager.get_slice_sync_enabled.return_value = True
    app.config_manager.get_smooth_image_when_zoomed.return_value = False
    app.config_manager.get_show_scale_markers.return_value = True
    app.config_manager.get_show_direction_labels.return_value = True
    app.config_manager.get_show_slice_slider.return_value = False
    app.config_manager.get_slice_slider_placement.return_value = "left"
    app.config_manager.get_slice_slider_direction.return_value = "normal"
    app.config_manager.get_scale_markers_color.return_value = (255, 255, 0)
    app.config_manager.get_direction_labels_color.return_value = (0, 255, 255)
    app.config_manager.get_direction_label_size.return_value = "medium"
    app.config_manager.get_scale_markers_major_tick_interval_mm.return_value = 10.0
    app.config_manager.get_scale_markers_minor_tick_interval_mm.return_value = 2.0

    return app


def test_iter_image_viewers_filtering(mock_app: SimpleNamespace) -> None:
    """Test _iter_image_viewers filters None subwindows and subwindows without image_viewer."""
    v0 = MagicMock()
    v2 = MagicMock()

    sub0 = SimpleNamespace(image_viewer=v0)
    sub1_none_viewer = SimpleNamespace(image_viewer=None)
    sub2 = SimpleNamespace(image_viewer=v2)

    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        sub0,
        None,
        sub1_none_viewer,
        sub2,
    ]

    viewers = list(_iter_image_viewers(mock_app))
    assert viewers == [v0, v2]


def test_apply_theme_viewer_background_all(mock_app: SimpleNamespace) -> None:
    """Test apply_theme_viewer_background_all applies background color to all viewers."""
    v0 = MagicMock()
    v1 = MagicMock()

    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0),
        SimpleNamespace(image_viewer=v1),
    ]

    mock_app.config_manager.get_theme.return_value = "dark"
    apply_theme_viewer_background_all(mock_app)

    v0.set_background_color.assert_called_once()
    v1.set_background_color.assert_called_once()


def test_apply_initial_image_viewer_display_state(mock_app: SimpleNamespace) -> None:
    """Test apply_initial_image_viewer_display_state applies all config properties to viewers."""
    v0 = MagicMock()
    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0)
    ]
    mock_app.privacy_view_enabled = True

    apply_initial_image_viewer_display_state(mock_app)

    v0.set_privacy_view_state.assert_called_once_with(True)
    v0.set_slice_sync_enabled_state.assert_called_once_with(True)
    v0.set_smooth_when_zoomed_state.assert_called_once_with(False)
    v0.set_scale_markers_state.assert_called_once_with(True)
    v0.set_direction_labels_state.assert_called_once_with(True)
    v0.set_slice_slider_options.assert_called_once_with("left", "normal")
    v0.set_slice_slider_enabled.assert_called_once_with(False)
    v0.set_scale_markers_color_state.assert_called_once_with((255, 255, 0))
    v0.set_direction_labels_color_state.assert_called_once_with((0, 255, 255))
    v0.set_direction_label_size_state.assert_called_once_with("medium")
    v0.set_scale_markers_tick_intervals_state.assert_called_once_with(10.0, 2.0)


def test_set_smooth_when_zoomed_all(mock_app: SimpleNamespace) -> None:
    """Test set_smooth_when_zoomed_all propagates to all viewers."""
    v0 = MagicMock()
    v1 = MagicMock()
    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0),
        SimpleNamespace(image_viewer=v1),
    ]

    set_smooth_when_zoomed_all(mock_app, True)
    v0.set_smooth_when_zoomed_state.assert_called_once_with(True)
    v1.set_smooth_when_zoomed_state.assert_called_once_with(True)


def test_set_scale_markers_all(mock_app: SimpleNamespace) -> None:
    """Test set_scale_markers_all propagates to all viewers."""
    v0 = MagicMock()
    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0)
    ]

    set_scale_markers_all(mock_app, False)
    v0.set_scale_markers_state.assert_called_once_with(False)


def test_set_direction_labels_all(mock_app: SimpleNamespace) -> None:
    """Test set_direction_labels_all propagates to all viewers."""
    v0 = MagicMock()
    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0)
    ]

    set_direction_labels_all(mock_app, True)
    v0.set_direction_labels_state.assert_called_once_with(True)


def test_set_scale_markers_color_all(mock_app: SimpleNamespace) -> None:
    """Test set_scale_markers_color_all propagates to all viewers."""
    v0 = MagicMock()
    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0)
    ]

    set_scale_markers_color_all(mock_app, (255, 0, 0))
    v0.set_scale_markers_color_state.assert_called_once_with((255, 0, 0))


def test_set_direction_labels_color_all(mock_app: SimpleNamespace) -> None:
    """Test set_direction_labels_color_all propagates to all viewers."""
    v0 = MagicMock()
    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0)
    ]

    set_direction_labels_color_all(mock_app, (0, 255, 0))
    v0.set_direction_labels_color_state.assert_called_once_with((0, 255, 0))


def test_set_slice_slider_all(mock_app: SimpleNamespace) -> None:
    """Test set_slice_slider_all propagates to all viewers."""
    v0 = MagicMock()
    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0)
    ]

    set_slice_slider_all(mock_app, True)
    v0.set_slice_slider_enabled.assert_called_once_with(True)


def test_set_slice_slider_options_all(mock_app: SimpleNamespace) -> None:
    """Test set_slice_slider_options_all propagates placement and direction to all viewers."""
    v0 = MagicMock()
    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0)
    ]

    set_slice_slider_options_all(mock_app, "right", "inverted")
    v0.set_slice_slider_options.assert_called_once_with("right", "inverted")


def test_iter_image_viewers_handles_absent_layout() -> None:
    """Viewer iteration must be empty when no multi-window layout exists."""
    app = SimpleNamespace(multi_window_layout=None)
    assert list(_iter_image_viewers(app)) == []


def test_apply_initial_display_state_requires_privacy_view_contract(
    mock_app: SimpleNamespace,
) -> None:
    """Initialization requires the application privacy-view state."""
    del mock_app.privacy_view_enabled
    v0 = MagicMock()
    mock_app.multi_window_layout.get_all_subwindows.return_value = [
        SimpleNamespace(image_viewer=v0)
    ]

    with pytest.raises(
        AttributeError,
        match=r"'types.SimpleNamespace' object has no attribute 'privacy_view_enabled'",
    ):
        apply_initial_image_viewer_display_state(mock_app)
