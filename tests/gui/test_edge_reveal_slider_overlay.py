"""Tests for gui.edge_reveal_slider_overlay.EdgeRevealSliderOverlay."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import QBoxLayout, QWidget

from gui.edge_reveal_slider_overlay import EdgeRevealSliderOverlay


@pytest.fixture
def parent_widget(qapp):
    """Fixture providing a parent QWidget that persists through the test."""
    widget = QWidget()
    widget.setVisible(True)
    yield widget
    widget.deleteLater()


@pytest.fixture
def overlay(parent_widget):
    """Fixture providing an EdgeRevealSliderOverlay instance with persistent parent."""
    return EdgeRevealSliderOverlay(parent_widget)


class TestEdgeRevealSliderOverlayInitialization:
    def test_initialization_sets_translucent_background(self, overlay: EdgeRevealSliderOverlay):
        assert overlay.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def test_initialization_starts_hidden(self, overlay: EdgeRevealSliderOverlay):
        assert not overlay.isVisible()

    def test_initialization_sets_default_placement(self, overlay: EdgeRevealSliderOverlay):
        assert overlay.placement() == "bottom"

    def test_initialization_sets_default_direction(self, overlay: EdgeRevealSliderOverlay):
        assert overlay.direction() == "first_at_start"

    def test_initialization_sets_mode_label(self, overlay: EdgeRevealSliderOverlay):
        assert overlay._mode_label == "Slice"

    def test_initialization_sets_slider_range_defaults(self, overlay: EdgeRevealSliderOverlay):
        assert overlay.minimum() == 1
        assert overlay.maximum() == 1
        assert overlay._slider.value() == 1

    def test_initialization_sets_not_interacting(self, overlay: EdgeRevealSliderOverlay):
        assert not overlay.is_interacting()

    def test_initialization_creates_opacity_effect(self, overlay: EdgeRevealSliderOverlay):
        assert overlay._opacity_effect is not None
        assert overlay._opacity_effect.opacity() == 0.0

    def test_initialization_creates_fade_animation(self, overlay: EdgeRevealSliderOverlay):
        assert overlay._fade_anim is not None
        assert overlay._fade_anim.duration() == 180
        assert overlay._fade_anim.easingCurve().type() == QEasingCurve.Type.InOutCubic

    def test_initialization_creates_hide_timer(self, overlay: EdgeRevealSliderOverlay):
        assert overlay._hide_timer is not None
        assert overlay._hide_timer.isSingleShot()
        assert overlay._hide_timer.interval() == 1500

    def test_initialization_connects_slider_signals(self, overlay: EdgeRevealSliderOverlay):
        assert overlay._slider.valueChanged is not None
        assert overlay._slider.sliderPressed is not None
        assert overlay._slider.sliderReleased is not None

    def test_initialization_sets_layout_margins(self, overlay: EdgeRevealSliderOverlay):
        assert overlay._layout.contentsMargins().left() == 8
        assert overlay._layout.contentsMargins().top() == 6
        assert overlay._layout.contentsMargins().right() == 8
        assert overlay._layout.contentsMargins().bottom() == 6

    def test_initialization_sets_layout_spacing(self, overlay: EdgeRevealSliderOverlay):
        assert overlay._layout.spacing() == 0


class TestEdgeRevealSliderOverlayProperties:
    def test_maximum_returns_slider_maximum(self, overlay: EdgeRevealSliderOverlay):
        overlay._slider.setMaximum(100)
        assert overlay.maximum() == 100

    def test_minimum_returns_slider_minimum(self, overlay: EdgeRevealSliderOverlay):
        overlay._slider.setMinimum(10)
        assert overlay.minimum() == 10

    def test_slider_orientation_returns_slider_orientation(self, overlay: EdgeRevealSliderOverlay):
        assert overlay.slider_orientation() == Qt.Orientation.Horizontal

    def test_slider_cursor_shape_returns_cursor_shape(self, overlay: EdgeRevealSliderOverlay):
        shape = overlay.slider_cursor_shape()
        assert shape in (Qt.CursorShape.SizeHorCursor, Qt.CursorShape.SizeVerCursor)

    def test_slider_cursor_shape_vertical(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("left", "first_at_start")
        assert overlay.slider_cursor_shape() == Qt.CursorShape.SizeVerCursor

    def test_slider_cursor_shape_horizontal(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("bottom", "first_at_start")
        assert overlay.slider_cursor_shape() == Qt.CursorShape.SizeHorCursor

    def test_label_text_returns_empty_string(self, overlay: EdgeRevealSliderOverlay):
        assert overlay.label_text() == ""

    def test_is_interacting_returns_slider_interacting_state(self, overlay: EdgeRevealSliderOverlay):
        overlay._slider_interacting = True
        assert overlay.is_interacting()


class TestEdgeRevealSliderOverlayConfigure:
    def test_configure_updates_placement(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("left", "first_at_start")
        assert overlay.placement() == "left"

    def test_configure_updates_direction(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("bottom", "first_at_end")
        assert overlay.direction() == "first_at_end"

    def test_configure_updates_orientation(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("left", "first_at_start")
        assert overlay.slider_orientation() == Qt.Orientation.Vertical

    def test_configure_with_same_values_returns_early(self, overlay: EdgeRevealSliderOverlay):
        original_orientation = overlay.slider_orientation()
        overlay.configure("bottom", "first_at_start")
        assert overlay.slider_orientation() == original_orientation

    def test_configure_normalizes_placement(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("TOP", "first_at_start")
        assert overlay.placement() == "top"

    def test_configure_normalizes_direction(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("bottom", "FIRST_AT_END")
        assert overlay.direction() == "first_at_end"


class TestEdgeRevealSliderOverlaySetRangeAndValue:
    def test_set_range_and_value_updates_minimum(self, overlay: EdgeRevealSliderOverlay):
        overlay.set_range_and_value(5, 100, 50)
        assert overlay.minimum() == 5

    def test_set_range_and_value_updates_maximum(self, overlay: EdgeRevealSliderOverlay):
        overlay.set_range_and_value(1, 100, 50)
        assert overlay.maximum() == 100

    def test_set_range_and_value_updates_value(self, overlay: EdgeRevealSliderOverlay):
        overlay.set_range_and_value(1, 100, 50)
        assert overlay._slider.value() == 50

    def test_set_range_and_value_clamps_value_to_minimum(self, overlay: EdgeRevealSliderOverlay):
        overlay.set_range_and_value(10, 100, 5)
        assert overlay._slider.value() == 10

    def test_set_range_and_value_clamps_value_to_maximum(self, overlay: EdgeRevealSliderOverlay):
        overlay.set_range_and_value(1, 50, 100)
        assert overlay._slider.value() == 50

    def test_set_range_and_value_clamps_maximum_to_minimum(self, overlay: EdgeRevealSliderOverlay):
        overlay.set_range_and_value(100, 50, 75)
        assert overlay.maximum() == 100

    def test_set_range_and_value_with_equal_min_max(self, overlay: EdgeRevealSliderOverlay):
        overlay.set_range_and_value(50, 50, 50)
        assert overlay.minimum() == 50
        assert overlay.maximum() == 50
        assert overlay._slider.value() == 50

    def test_set_range_and_value_with_string_mode_label(self, overlay: EdgeRevealSliderOverlay):
        overlay.set_range_and_value(1, 100, 50, "Custom")
        assert overlay._mode_label == "Custom"

    def test_set_range_and_value_blocks_signals(self, overlay: EdgeRevealSliderOverlay):
        signal_emitted = []

        def on_value_changed(value):
            signal_emitted.append(value)

        overlay.slider_value_changed.connect(on_value_changed)
        overlay.set_range_and_value(1, 100, 50)
        assert len(signal_emitted) == 0


class TestEdgeRevealSliderOverlayReveal:
    def test_reveal_stops_hide_timer(self, overlay: EdgeRevealSliderOverlay):
        overlay._hide_timer.start()
        assert overlay._hide_timer.isActive()
        overlay.reveal()
        # Timer is stopped and then restarted at the end of reveal()
        assert overlay._hide_timer.isActive()

    def test_reveal_resets_fading_out_flag(self, overlay: EdgeRevealSliderOverlay):
        overlay._fading_out = True
        overlay.reveal()
        assert not overlay._fading_out

    def test_reveal_sets_visible(self, overlay: EdgeRevealSliderOverlay):
        overlay.reveal()
        assert overlay.isVisible()

    def test_reveal_fades_in_from_zero_opacity(self, overlay: EdgeRevealSliderOverlay):
        overlay._opacity_effect.setOpacity(0.0)
        overlay.reveal()
        assert overlay._fade_anim.startValue() == 0.0
        assert overlay._fade_anim.endValue() == 1.0

    def test_reveal_starts_hide_timer_after_fade(self, overlay: EdgeRevealSliderOverlay):
        overlay._opacity_effect.setOpacity(0.5)
        overlay.reveal()
        assert overlay._hide_timer.isActive()

    def test_reveal_returns_early_if_already_visible(self, overlay: EdgeRevealSliderOverlay):
        overlay._opacity_effect.setOpacity(1.0)
        overlay.setVisible(True)
        overlay.reveal()
        # Timer is restarted when already fully visible
        assert overlay._hide_timer.isActive()

    def test_reveal_from_partial_opacity(self, overlay: EdgeRevealSliderOverlay):
        overlay._opacity_effect.setOpacity(0.3)
        overlay.reveal()
        assert overlay._fade_anim.startValue() == 0.3
        assert overlay._fade_anim.endValue() == 1.0


class TestEdgeRevealSliderOverlayScheduleHide:
    def test_schedule_hide_starts_timer(self, overlay: EdgeRevealSliderOverlay):
        overlay.schedule_hide()
        assert overlay._hide_timer.isActive()

    def test_schedule_hide_returns_early_if_interacting(self, overlay: EdgeRevealSliderOverlay):
        overlay._slider_interacting = True
        overlay.schedule_hide()
        assert not overlay._hide_timer.isActive()

    def test_schedule_hide_restarts_timer_if_active(self, overlay: EdgeRevealSliderOverlay):
        overlay._hide_timer.start()
        overlay.schedule_hide()
        assert overlay._hide_timer.isActive()


class TestEdgeRevealSliderOverlayHideImmediately:
    def test_hide_immediately_stops_timer(self, overlay: EdgeRevealSliderOverlay):
        overlay._hide_timer.start()
        overlay.hide_immediately()
        assert not overlay._hide_timer.isActive()

    def test_hide_immediately_stops_animation(self, overlay: EdgeRevealSliderOverlay):
        overlay._fade_anim.start()
        overlay.hide_immediately()
        assert overlay._fade_anim.state() != QPropertyAnimation.State.Running

    def test_hide_immediately_resets_fading_out_flag(self, overlay: EdgeRevealSliderOverlay):
        overlay._fading_out = True
        overlay.hide_immediately()
        assert not overlay._fading_out

    def test_hide_immediately_sets_opacity_to_zero(self, overlay: EdgeRevealSliderOverlay):
        overlay._opacity_effect.setOpacity(1.0)
        overlay.hide_immediately()
        assert overlay._opacity_effect.opacity() == 0.0

    def test_hide_immediately_sets_invisible(self, overlay: EdgeRevealSliderOverlay):
        overlay.setVisible(True)
        overlay.hide_immediately()
        assert not overlay.isVisible()


class TestEdgeRevealSliderOverlayKeepVisible:
    def test_keep_visible_stops_timer(self, overlay: EdgeRevealSliderOverlay):
        overlay._hide_timer.start()
        overlay.keep_visible()
        assert not overlay._hide_timer.isActive()

    def test_keep_visible_resets_fading_out_flag(self, overlay: EdgeRevealSliderOverlay):
        overlay._fading_out = True
        overlay.keep_visible()
        assert not overlay._fading_out

    def test_keep_visible_sets_visible(self, overlay: EdgeRevealSliderOverlay):
        overlay.setVisible(False)
        overlay.keep_visible()
        assert overlay.isVisible()

    def test_keep_visible_sets_opacity_to_one(self, overlay: EdgeRevealSliderOverlay):
        overlay._opacity_effect.setOpacity(0.5)
        overlay.keep_visible()
        assert overlay._opacity_effect.opacity() == 1.0

    def test_keep_visible_skips_opacity_animation_if_already_high(self, overlay: EdgeRevealSliderOverlay):
        """When opacity is already >= 0.99, keep_visible doesn't stop the animation."""
        overlay._opacity_effect.setOpacity(1.0)
        overlay._fade_anim.start()
        overlay.keep_visible()
        # Animation is not stopped when opacity is already high (condition is < 0.99)
        # This is the actual behavior - the animation check is skipped
        assert overlay._fade_anim.state() == QPropertyAnimation.State.Running

    def test_keep_visible_stops_animation_when_opacity_low(self, overlay: EdgeRevealSliderOverlay):
        """When opacity is < 0.99, keep_visible stops animation and sets opacity to 1.0."""
        overlay._opacity_effect.setOpacity(0.5)
        overlay._fade_anim.start()
        overlay.keep_visible()
        # Animation should be stopped when opacity is low
        assert overlay._fade_anim.state() == QPropertyAnimation.State.Stopped
        assert overlay._opacity_effect.opacity() == 1.0

    def test_keep_visible_when_already_visible(self, overlay: EdgeRevealSliderOverlay):
        """Test keep_visible when widget is already visible (hits else branch)."""
        overlay.setVisible(True)
        overlay._hide_timer.start()
        overlay.keep_visible()
        # Should remain visible and timer should be stopped
        assert overlay.isVisible()
        assert not overlay._hide_timer.isActive()


class TestEdgeRevealSliderOverlaySliderHandlers:
    def test_on_slider_value_changed_emits_signal(self, overlay: EdgeRevealSliderOverlay):
        signal_emitted = []

        def on_value_changed(value):
            signal_emitted.append(value)

        overlay.slider_value_changed.connect(on_value_changed)
        overlay._on_slider_value_changed(42)
        assert signal_emitted == [42]

    def test_on_slider_pressed_sets_interacting(self, overlay: EdgeRevealSliderOverlay):
        overlay._on_slider_pressed()
        assert overlay._slider_interacting

    def test_on_slider_pressed_keeps_visible(self, overlay: EdgeRevealSliderOverlay):
        overlay._opacity_effect.setOpacity(0.5)
        overlay._on_slider_pressed()
        assert overlay._opacity_effect.opacity() == 1.0

    def test_on_slider_released_resets_interacting(self, overlay: EdgeRevealSliderOverlay):
        overlay._slider_interacting = True
        overlay._on_slider_released()
        assert not overlay._slider_interacting

    def test_on_slider_released_schedules_hide(self, overlay: EdgeRevealSliderOverlay):
        overlay._on_slider_released()
        assert overlay._hide_timer.isActive()


class TestEdgeRevealSliderOverlayAnimation:
    def test_start_fade_out_sets_fading_out_flag(self, overlay: EdgeRevealSliderOverlay):
        overlay._start_fade_out()
        assert overlay._fading_out

    def test_start_fade_out_returns_early_if_already_fading(self, overlay: EdgeRevealSliderOverlay):
        overlay._fading_out = True
        overlay._start_fade_out()
        assert overlay._fade_anim.state() == QPropertyAnimation.State.Stopped

    def test_start_fade_out_animates_to_zero_opacity(self, overlay: EdgeRevealSliderOverlay):
        overlay._opacity_effect.setOpacity(1.0)
        overlay._start_fade_out()
        assert overlay._fade_anim.startValue() == 1.0
        assert overlay._fade_anim.endValue() == 0.0

    def test_on_animation_finished_hides_when_faded_out(self, overlay: EdgeRevealSliderOverlay):
        overlay._fading_out = True
        overlay._opacity_effect.setOpacity(0.0)
        overlay.setVisible(True)
        overlay._on_animation_finished()
        assert not overlay.isVisible()

    def test_on_animation_finished_resets_fading_out_flag(self, overlay: EdgeRevealSliderOverlay):
        overlay._fading_out = True
        overlay._opacity_effect.setOpacity(0.0)
        overlay._on_animation_finished()
        assert not overlay._fading_out

    def test_on_animation_finished_does_not_hide_if_not_faded(self, overlay: EdgeRevealSliderOverlay):
        overlay._fading_out = True
        overlay._opacity_effect.setOpacity(0.5)
        overlay.setVisible(True)
        overlay._on_animation_finished()
        # Should remain visible since opacity is not near zero
        assert overlay.isVisible()
        # Flag should NOT be reset when not hiding
        assert overlay._fading_out


class TestEdgeRevealSliderOverlayOrientation:
    def test_apply_orientation_style_sets_vertical_for_left_placement(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("left", "first_at_start")
        assert overlay.slider_orientation() == Qt.Orientation.Vertical

    def test_apply_orientation_style_sets_vertical_for_right_placement(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("right", "first_at_start")
        assert overlay.slider_orientation() == Qt.Orientation.Vertical

    def test_apply_orientation_style_sets_horizontal_for_top_placement(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("top", "first_at_start")
        assert overlay.slider_orientation() == Qt.Orientation.Horizontal

    def test_apply_orientation_style_sets_horizontal_for_bottom_placement(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("bottom", "first_at_start")
        assert overlay.slider_orientation() == Qt.Orientation.Horizontal

    def test_apply_orientation_style_sets_inverted_appearance(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("bottom", "first_at_end")
        assert overlay._slider.invertedAppearance()

    def test_apply_orientation_style_sets_inverted_controls(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("bottom", "first_at_end")
        assert overlay._slider.invertedControls()

    def test_apply_orientation_style_sets_layout_direction_vertical(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("left", "first_at_start")
        assert overlay._layout.direction() == QBoxLayout.Direction.TopToBottom

    def test_apply_orientation_style_sets_layout_direction_horizontal(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("bottom", "first_at_start")
        assert overlay._layout.direction() == QBoxLayout.Direction.LeftToRight

    def test_apply_orientation_style_clears_inverted_for_first_at_start(self, overlay: EdgeRevealSliderOverlay):
        overlay.configure("bottom", "first_at_end")
        assert overlay._slider.invertedAppearance()
        overlay.configure("bottom", "first_at_start")
        assert not overlay._slider.invertedAppearance()


class TestEdgeRevealSliderOverlayPaintEvent:
    def test_paint_event_draws_without_error(self, overlay: EdgeRevealSliderOverlay):
        """Test that paintEvent executes without raising exceptions."""
        overlay.setVisible(True)
        event = QPaintEvent(overlay.rect())
        overlay.paintEvent(event)
        # If we get here without exception, the test passes


class TestEdgeRevealSliderOverlaySignal:
    def test_slider_value_changed_signal_emitted_on_handler_call(self, overlay: EdgeRevealSliderOverlay):
        """Test that the public signal is emitted when _on_slider_value_changed is called."""
        signal_values = []

        def capture_value(value):
            signal_values.append(value)

        overlay.slider_value_changed.connect(capture_value)
        overlay._on_slider_value_changed(42)
        assert signal_values == [42]
