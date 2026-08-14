"""Round-5 coverage tests for gui.image_viewer_view — state setters, smoothing, view transform."""

from __future__ import annotations

from image_viewer_view_round5_helpers import create_image as _img
from image_viewer_view_round5_helpers import create_viewer as _viewer
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

# ---------------------------------------------------------------------------
# Simple state setters
# ---------------------------------------------------------------------------

def test_set_background_color(qapp) -> None:
    v = _viewer(qapp)
    v.set_background_color(QColor(0, 0, 0))
    bg = v.backgroundBrush().color()
    assert bg.red() == 0 and bg.green() == 0 and bg.blue() == 0


def test_set_subwindow_index(qapp) -> None:
    v = _viewer(qapp)
    v.set_subwindow_index(2)
    assert v.subwindow_index == 2


def test_set_smooth_when_zoomed_state_true(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.set_smooth_when_zoomed_state(True)
    assert v._smooth_when_zoomed is True
    assert v._smooth_idle_interacting is False


def test_set_smooth_when_zoomed_state_false(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.set_smooth_when_zoomed_state(False)
    assert v._smooth_when_zoomed is False


def test_set_slice_sync_enabled_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_slice_sync_enabled_state(True)
    assert v._slice_sync_enabled is True
    v.set_slice_sync_enabled_state(False)
    assert v._slice_sync_enabled is False


def test_set_scale_markers_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_scale_markers_state(True)
    assert v._show_scale_markers is True
    v.set_scale_markers_state(False)
    assert v._show_scale_markers is False


def test_set_direction_labels_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_direction_labels_state(True)
    assert v._show_direction_labels is True
    v.set_direction_labels_state(False)
    assert v._show_direction_labels is False


def test_set_scale_markers_color_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_scale_markers_color_state((100, 200, 50))
    assert v._scale_markers_color == (100, 200, 50)


def test_set_direction_labels_color_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_direction_labels_color_state((255, 0, 128))
    assert v._direction_labels_color == (255, 0, 128)


def test_set_direction_label_size_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_direction_label_size_state(20)
    assert v._direction_label_size == 20


def test_set_direction_label_size_clamps_to_one(qapp) -> None:
    v = _viewer(qapp)
    v.set_direction_label_size_state(0)
    assert v._direction_label_size == 1
    v.set_direction_label_size_state(-5)
    assert v._direction_label_size == 1


def test_set_scale_markers_tick_intervals_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_scale_markers_tick_intervals_state(8, 2)
    assert v._scale_markers_major_tick_interval_mm == 8
    assert v._scale_markers_minor_tick_interval_mm == 2


def test_set_scale_markers_tick_intervals_clamp(qapp) -> None:
    v = _viewer(qapp)
    v.set_scale_markers_tick_intervals_state(0, 0)
    assert v._scale_markers_major_tick_interval_mm == 1
    assert v._scale_markers_minor_tick_interval_mm == 1


def test_set_scroll_wheel_mode_valid(qapp) -> None:
    v = _viewer(qapp)
    v.set_scroll_wheel_mode("zoom")
    assert v.scroll_wheel_mode == "zoom"
    v.set_scroll_wheel_mode("slice")
    assert v.scroll_wheel_mode == "slice"


def test_set_scroll_wheel_mode_invalid_ignored(qapp) -> None:
    v = _viewer(qapp)
    v.scroll_wheel_mode = "slice"
    v.set_scroll_wheel_mode("invalid")
    assert v.scroll_wheel_mode == "slice"


def test_set_rescale_toggle_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_rescale_toggle_state(True)
    assert v.use_rescaled_values is True


def test_set_cine_controls_enabled(qapp) -> None:
    v = _viewer(qapp)
    v.set_cine_controls_enabled(True)
    assert v.cine_controls_enabled is True


def test_set_privacy_view_state(qapp) -> None:
    v = _viewer(qapp)
    v.set_privacy_view_state(True)
    assert v._privacy_view_enabled is True


# ---------------------------------------------------------------------------
# set_window_level_for_drag
# ---------------------------------------------------------------------------

def test_set_window_level_for_drag_positive_range(qapp) -> None:
    v = _viewer(qapp)
    v.set_window_level_for_drag(
        center=40.0, width=100.0,
        center_range=(0.0, 200.0), width_range=(0.0, 300.0),
    )
    assert v.right_mouse_drag_start_center == 40.0
    assert v.right_mouse_drag_start_width == 100.0
    assert v.window_center_sensitivity == 200.0 / 1000.0
    assert v.window_width_sensitivity == 300.0 / 1000.0


def test_set_window_level_for_drag_zero_range(qapp) -> None:
    v = _viewer(qapp)
    v.set_window_level_for_drag(
        center=0.0, width=0.0,
        center_range=(5.0, 5.0), width_range=(5.0, 5.0),
    )
    assert v.window_center_sensitivity == 1.0
    assert v.window_width_sensitivity == 1.0


# ---------------------------------------------------------------------------
# _apply_smoothing_mode
# ---------------------------------------------------------------------------

def test_apply_smoothing_mode_smooth_no_image(qapp) -> None:
    v = _viewer(qapp)
    v._smooth_when_zoomed = True
    v._smooth_idle_interacting = False
    v._apply_smoothing_mode()
    assert v._smooth_when_zoomed is True


def test_apply_smoothing_mode_fast_no_image(qapp) -> None:
    v = _viewer(qapp)
    v._smooth_when_zoomed = False
    v._apply_smoothing_mode()
    assert v._smooth_when_zoomed is False


def test_apply_smoothing_mode_interacting_with_image(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v._smooth_when_zoomed = True
    v._smooth_idle_interacting = True
    v._apply_smoothing_mode()
    assert v.image_item.transformationMode() == Qt.TransformationMode.FastTransformation


def test_apply_smoothing_mode_idle_with_image(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v._smooth_when_zoomed = True
    v._smooth_idle_interacting = False
    v._apply_smoothing_mode()
    assert v.image_item.transformationMode() == Qt.TransformationMode.SmoothTransformation


# ---------------------------------------------------------------------------
# _on_smooth_idle_timeout and _restart_smooth_idle_timer
# ---------------------------------------------------------------------------

def test_on_smooth_idle_timeout(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v._smooth_when_zoomed = True
    v._smooth_idle_interacting = True
    v._on_smooth_idle_timeout()
    assert v._smooth_idle_interacting is False


def test_restart_smooth_idle_timer_when_enabled(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v._smooth_when_zoomed = True
    v._restart_smooth_idle_timer()
    assert v._smooth_idle_interacting is True
    assert v._smooth_idle_timer.isActive()


def test_restart_smooth_idle_timer_when_disabled(qapp) -> None:
    v = _viewer(qapp)
    v._smooth_when_zoomed = False
    v._restart_smooth_idle_timer()
    assert v._smooth_idle_interacting is False


# ---------------------------------------------------------------------------
# _apply_view_transform
# ---------------------------------------------------------------------------

def test_apply_view_transform_no_rotation_no_flip(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.current_zoom = 1.0
    v._rotation_deg = 0
    v._flip_h = False
    v._flip_v = False
    v._apply_view_transform()
    t = v.transform()
    assert abs(t.m11() - 1.0) < 1e-6
    assert abs(t.m22() - 1.0) < 1e-6


def test_apply_view_transform_with_zoom(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.current_zoom = 2.5
    v._apply_view_transform()
    t = v.transform()
    assert abs(t.m11() - 2.5) < 1e-6
    assert abs(t.m22() - 2.5) < 1e-6


def test_apply_view_transform_with_flip_h(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.current_zoom = 1.0
    v._flip_h = True
    v._flip_v = False
    v._apply_view_transform()
    t = v.transform()
    assert t.m11() < 0


def test_apply_view_transform_with_flip_v(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.current_zoom = 1.0
    v._flip_h = False
    v._flip_v = True
    v._apply_view_transform()
    t = v.transform()
    assert t.m22() < 0


def test_apply_view_transform_with_rotation(qapp) -> None:
    v = _viewer(qapp)
    v.set_image(_img(), preserve_view=False)
    v.current_zoom = 1.0
    v._rotation_deg = 90
    v._apply_view_transform()
    t = v.transform()
    assert abs(t.m12() - 1.0) < 1e-3
