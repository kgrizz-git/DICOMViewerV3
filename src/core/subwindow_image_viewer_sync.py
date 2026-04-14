"""
Propagate display and View-menu options to every subwindow ImageViewer.

Centralizes loops over ``multi_window_layout.get_all_subwindows()`` so startup
and toggles stay consistent across panes without duplicating logic in ``main.py``.

Inputs:
    app: Application object with ``multi_window_layout``, ``config_manager``,
        and ``privacy_view_enabled`` (same shape as ``DICOMViewerApp``).

Outputs:
    None; mutates each subwindow's ``image_viewer`` in place.

Requirements:
    PySide6; ``ConfigManager`` getters as called below.
"""

from __future__ import annotations

from typing import Any, Tuple

from gui.main_window_theme import get_theme_viewer_background_color


def _iter_image_viewers(app: Any):
    for subwindow in app.multi_window_layout.get_all_subwindows():
        if subwindow and subwindow.image_viewer:
            yield subwindow.image_viewer


def apply_theme_viewer_background_all(app: Any) -> None:
    """
    Set QGraphicsView letterbox background on every subwindow ImageViewer from
    the current config theme.

    ``MainWindow._apply_theme`` runs before subwindows exist and only updates
    ``main_window.image_viewer`` (one pane); without this pass, viewers keep Qt's
    default brush until the user toggles theme. Call once after subwindows are
    created and again whenever the theme changes (see ``theme_changed`` wiring).
    """
    theme = app.config_manager.get_theme()
    color = get_theme_viewer_background_color(theme)
    for viewer in _iter_image_viewers(app):
        viewer.set_background_color(color)


def apply_initial_image_viewer_display_state(app: Any) -> None:
    """
    One pass per viewer: same property order as the former six sequential loops
    in ``DICOMViewerApp._post_init_subwindows_and_handlers`` (privacy, slice sync,
    smooth zoom, scale markers, direction labels, then colors/sizes/ticks).
    Also applies the slice-slider enabled state from config.
    """
    sync_enabled = app.config_manager.get_slice_sync_enabled()
    smooth = app.config_manager.get_smooth_image_when_zoomed()
    show_scale = app.config_manager.get_show_scale_markers()
    show_direction = app.config_manager.get_show_direction_labels()
    show_slice_slider = app.config_manager.get_show_slice_slider()
    sm_color = app.config_manager.get_scale_markers_color()
    dir_color = app.config_manager.get_direction_labels_color()
    dir_size = app.config_manager.get_direction_label_size()
    major_mm = app.config_manager.get_scale_markers_major_tick_interval_mm()
    minor_mm = app.config_manager.get_scale_markers_minor_tick_interval_mm()

    for viewer in _iter_image_viewers(app):
        viewer.set_privacy_view_state(app.privacy_view_enabled)
        viewer.set_slice_sync_enabled_state(sync_enabled)
        viewer.set_smooth_when_zoomed_state(smooth)
        viewer.set_scale_markers_state(show_scale)
        viewer.set_direction_labels_state(show_direction)
        viewer.set_slice_slider_enabled(show_slice_slider)
        viewer.set_scale_markers_color_state(sm_color)
        viewer.set_direction_labels_color_state(dir_color)
        viewer.set_direction_label_size_state(dir_size)
        viewer.set_scale_markers_tick_intervals_state(major_mm, minor_mm)


def set_smooth_when_zoomed_all(app: Any, enabled: bool) -> None:
    for viewer in _iter_image_viewers(app):
        viewer.set_smooth_when_zoomed_state(enabled)


def set_scale_markers_all(app: Any, enabled: bool) -> None:
    for viewer in _iter_image_viewers(app):
        viewer.set_scale_markers_state(enabled)


def set_direction_labels_all(app: Any, enabled: bool) -> None:
    for viewer in _iter_image_viewers(app):
        viewer.set_direction_labels_state(enabled)


def set_scale_markers_color_all(app: Any, rgb: Tuple[int, int, int]) -> None:
    for viewer in _iter_image_viewers(app):
        viewer.set_scale_markers_color_state(rgb)


def set_direction_labels_color_all(app: Any, rgb: Tuple[int, int, int]) -> None:
    for viewer in _iter_image_viewers(app):
        viewer.set_direction_labels_color_state(rgb)


def set_slice_slider_all(app: Any, enabled: bool) -> None:
    """Propagate the slice/frame slider enabled state to every subwindow ImageViewer."""
    for viewer in _iter_image_viewers(app):
        viewer.set_slice_slider_enabled(enabled)
