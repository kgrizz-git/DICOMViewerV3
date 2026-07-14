"""
Edge-reveal slice/frame slider overlay.

A translucent child widget anchored to one edge of an ``ImageViewer`` viewport.
The parent viewer owns placement geometry and reveal zones; this widget owns the
slider, cursor, orientation, fade behavior, and logical value signal.
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QBoxLayout, QGraphicsOpacityEffect, QSlider, QWidget

from core.navigation_slider_state import (
    DEFAULT_SLIDER_DIRECTION,
    DEFAULT_SLIDER_PLACEMENT,
    normalize_slider_direction,
    normalize_slider_placement,
)


class EdgeRevealSliderOverlay(QWidget):
    """Translucent edge overlay with a slice/frame navigation slider."""

    slider_value_changed = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setVisible(False)

        self._placement = DEFAULT_SLIDER_PLACEMENT
        self._direction = DEFAULT_SLIDER_DIRECTION
        self._mode_label = "Slice"
        self._slider_interacting = False
        self._fading_out = False

        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setMinimum(1)
        self._slider.setMaximum(1)
        self._slider.setValue(1)

        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.addWidget(self._slider, 1)
        self._layout.setContentsMargins(8, 6, 8, 6)
        self._layout.setSpacing(0)

        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity_effect)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity", self)
        self._fade_anim.setDuration(180)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._fade_anim.finished.connect(self._on_animation_finished)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(1500)
        self._hide_timer.timeout.connect(self._start_fade_out)

        self._slider.valueChanged.connect(self._on_slider_value_changed)
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        self._slider.sliderReleased.connect(self._on_slider_released)
        self._apply_orientation_style()

    def maximum(self) -> int:
        """Return the current slider maximum."""
        return self._slider.maximum()

    def minimum(self) -> int:
        """Return the current slider minimum."""
        return self._slider.minimum()

    def placement(self) -> str:
        """Return the configured edge placement."""
        return self._placement

    def direction(self) -> str:
        """Return where the first slice/frame appears."""
        return self._direction

    def slider_orientation(self) -> Qt.Orientation:
        """Return the underlying slider orientation."""
        return self._slider.orientation()

    def slider_cursor_shape(self) -> Qt.CursorShape:
        """Return the cursor used when hovering the slider."""
        return self._slider.cursor().shape()

    def label_text(self) -> str:
        """Return embedded label text; intentionally blank because overlays own slice/frame text."""
        return ""

    def is_interacting(self) -> bool:
        """Return whether the user is actively dragging the slider handle."""
        return self._slider_interacting

    def configure(self, placement: str, direction: str) -> None:
        """Apply edge placement and first-slice/frame direction preferences."""
        normalized_placement = normalize_slider_placement(placement)
        normalized_direction = normalize_slider_direction(direction)
        if (
            normalized_placement == self._placement
            and normalized_direction == self._direction
        ):
            return
        self._placement = normalized_placement
        self._direction = normalized_direction
        self._apply_orientation_style()

    def set_range_and_value(
        self,
        minimum: int,
        maximum: int,
        value: int,
        mode_label: str = "Slice",
    ) -> None:
        """Update slider range, current 1-based position, and label text."""
        minimum = int(minimum)
        maximum = max(int(maximum), minimum)
        value = min(max(int(value), minimum), maximum)

        self._mode_label = mode_label
        self._slider.blockSignals(True)
        self._slider.setMinimum(minimum)
        self._slider.setMaximum(maximum)
        self._slider.setValue(value)
        self._slider.blockSignals(False)

    def reveal(self) -> None:
        """Fade the overlay in and restart the auto-hide countdown."""
        self._hide_timer.stop()
        self._fading_out = False

        if not self.isVisible():
            self.setVisible(True)

        current_opacity = self._opacity_effect.opacity()
        if current_opacity >= 0.99:
            self._hide_timer.start()
            return

        self._fade_anim.stop()
        self._fade_anim.setStartValue(current_opacity)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()
        self._hide_timer.start()

    def schedule_hide(self) -> None:
        """Start or restart the auto-hide countdown."""
        if self._slider_interacting:
            return
        if self._hide_timer.isActive():
            self._hide_timer.stop()
        self._hide_timer.start()

    def hide_immediately(self) -> None:
        """Hide at once, cancelling any pending timer or fade animation."""
        self._hide_timer.stop()
        self._fade_anim.stop()
        self._fading_out = False
        self._opacity_effect.setOpacity(0.0)
        self.setVisible(False)

    def keep_visible(self) -> None:
        """Cancel auto-hide while the pointer hovers over the overlay."""
        self._hide_timer.stop()
        self._fading_out = False
        if not self.isVisible():
            self.setVisible(True)
        if self._opacity_effect.opacity() < 0.99:
            self._fade_anim.stop()
            self._opacity_effect.setOpacity(1.0)

    def paintEvent(self, event) -> None:
        """Draw the semi-transparent rounded overlay background."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(0, 0, 0, 110))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 6, 6)

    def _start_fade_out(self) -> None:
        if self._fading_out:
            return
        self._fading_out = True
        current_opacity = self._opacity_effect.opacity()
        self._fade_anim.stop()
        self._fade_anim.setStartValue(current_opacity)
        self._fade_anim.setEndValue(0.0)
        self._fade_anim.start()

    def _on_animation_finished(self) -> None:
        if self._fading_out and self._opacity_effect.opacity() < 0.01:
            self.setVisible(False)
            self._fading_out = False

    def _on_slider_value_changed(self, value: int) -> None:
        self.slider_value_changed.emit(value)

    def _on_slider_pressed(self) -> None:
        self._slider_interacting = True
        self.keep_visible()

    def _on_slider_released(self) -> None:
        self._slider_interacting = False
        self.schedule_hide()

    def _apply_orientation_style(self) -> None:
        is_vertical = self._placement in ("left", "right")
        orientation = Qt.Orientation.Vertical if is_vertical else Qt.Orientation.Horizontal
        cursor = Qt.CursorShape.SizeVerCursor if is_vertical else Qt.CursorShape.SizeHorCursor

        self._slider.setOrientation(orientation)
        self._slider.setCursor(cursor)
        self._slider.setInvertedAppearance(self._direction == "first_at_end")
        self._slider.setInvertedControls(self._direction == "first_at_end")

        if is_vertical:
            self._layout.setDirection(QBoxLayout.Direction.TopToBottom)
            self._slider.setMinimumWidth(0)
            self._slider.setMinimumHeight(60)
            self._slider.setStyleSheet(
                "QSlider::groove:vertical { background: rgba(255,255,255,60); width: 6px; border-radius: 3px; }"
                "QSlider::handle:vertical { background: rgba(200,200,200,225); width: 22px; height: 22px;"
                "  margin: 0 -8px; border-radius: 11px; }"
                "QSlider::sub-page:vertical { background: rgba(255,255,255,120); border-radius: 3px; }"
            )
            return

        self._layout.setDirection(QBoxLayout.Direction.LeftToRight)
        self._slider.setMinimumWidth(60)
        self._slider.setMinimumHeight(0)
        self._slider.setStyleSheet(
            "QSlider::groove:horizontal { background: rgba(255,255,255,60); height: 6px; border-radius: 3px; }"
            "QSlider::handle:horizontal { background: rgba(200,200,200,225); width: 22px; height: 22px;"
            "  margin: -8px 0; border-radius: 11px; }"
            "QSlider::sub-page:horizontal { background: rgba(255,255,255,120); border-radius: 3px; }"
        )
