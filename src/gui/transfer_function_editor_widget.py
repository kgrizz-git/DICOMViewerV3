"""
Transfer Function Editor Widget

A compact 1D transfer-function editor for scalar-opacity control points.
Displays the current opacity ramp as a filled polygon and lets users drag
control points vertically (opacity) and horizontally (scalar value).

This widget is intentionally minimal: it edits opacity only (not colour),
shows a single channel, and does not support 2D transfer functions.  It is
meant to live behind the Advanced disclosure in the 3D viewer panel.

Inputs:
    - List of ``(scalar_value, opacity)`` control points.

Outputs:
    - ``points_changed`` signal with the updated control-point list.

Requirements:
    - PySide6 (no VTK dependency).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import QWidget

_POINT_RADIUS = 5.0
_MARGIN = 10


class TransferFunctionEditorWidget(QWidget):
    """Compact 1D scalar-opacity curve editor."""

    points_changed = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: list[tuple[float, float]] = []
        self._dragging: int = -1
        self._scalar_range: tuple[float, float] = (0.0, 1.0)
        self.setMinimumSize(200, 80)
        self.setMaximumHeight(120)
        self.setMouseTracking(True)

    def set_points(self, points: list[tuple[float, float]]) -> None:
        self._points = list(points)
        if self._points:
            lo = min(s for s, _ in self._points)
            hi = max(s for s, _ in self._points)
            if hi - lo < 1e-6:
                hi = lo + 1.0
            self._scalar_range = (lo, hi)
        self.update()

    def get_points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def _plot_rect(self) -> QRectF:
        return QRectF(
            _MARGIN, _MARGIN,
            self.width() - 2 * _MARGIN,
            self.height() - 2 * _MARGIN,
        )

    def _scalar_to_x(self, scalar: float) -> float:
        r = self._plot_rect()
        lo, hi = self._scalar_range
        frac = (scalar - lo) / (hi - lo) if hi != lo else 0.0
        return r.left() + frac * r.width()

    def _opacity_to_y(self, opacity: float) -> float:
        r = self._plot_rect()
        return r.bottom() - opacity * r.height()

    def _x_to_scalar(self, x: float) -> float:
        r = self._plot_rect()
        frac = (x - r.left()) / r.width() if r.width() > 0 else 0.0
        lo, hi = self._scalar_range
        return lo + frac * (hi - lo)

    def _y_to_opacity(self, y: float) -> float:
        r = self._plot_rect()
        frac = (r.bottom() - y) / r.height() if r.height() > 0 else 0.0
        return max(0.0, min(1.0, frac))

    def paintEvent(self, event) -> None:
        if not self._points:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self._plot_rect()

        # Background.
        p.fillRect(r, QColor(30, 30, 35))

        # Grid lines.
        pen_grid = QPen(QColor(60, 60, 65), 1, Qt.PenStyle.DotLine)
        p.setPen(pen_grid)
        for frac in (0.25, 0.5, 0.75):
            y = r.bottom() - frac * r.height()
            p.drawLine(QPointF(r.left(), y), QPointF(r.right(), y))

        # Filled ramp.
        path = QPainterPath()
        pts = sorted(self._points, key=lambda pt: pt[0])
        first_x = self._scalar_to_x(pts[0][0])
        path.moveTo(first_x, r.bottom())
        for s, o in pts:
            path.lineTo(self._scalar_to_x(s), self._opacity_to_y(o))
        path.lineTo(self._scalar_to_x(pts[-1][0]), r.bottom())
        path.closeSubpath()

        grad = QLinearGradient(0, r.top(), 0, r.bottom())
        grad.setColorAt(0.0, QColor(120, 180, 255, 140))
        grad.setColorAt(1.0, QColor(60, 100, 200, 40))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(140, 200, 255, 200), 1.5))
        p.drawPath(path)

        # Control points.
        for i, (s, o) in enumerate(pts):
            cx = self._scalar_to_x(s)
            cy = self._opacity_to_y(o)
            if i == self._dragging:
                p.setBrush(QBrush(QColor(255, 220, 80)))
                p.setPen(QPen(QColor(255, 255, 255), 1.5))
            else:
                p.setBrush(QBrush(QColor(200, 220, 255)))
                p.setPen(QPen(QColor(160, 180, 220), 1.0))
            p.drawEllipse(QPointF(cx, cy), _POINT_RADIUS, _POINT_RADIUS)

        p.end()

    def _hit_test(self, pos: QPointF) -> int:
        for i, (s, o) in enumerate(self._points):
            cx = self._scalar_to_x(s)
            cy = self._opacity_to_y(o)
            dx = pos.x() - cx
            dy = pos.y() - cy
            if dx * dx + dy * dy <= (_POINT_RADIUS + 3) ** 2:
                return i
        return -1

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._hit_test(event.position())
            if idx >= 0:
                self._dragging = idx
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging >= 0 and self._dragging < len(self._points):
            pos = event.position()
            new_scalar = self._x_to_scalar(pos.x())
            new_opacity = self._y_to_opacity(pos.y())
            # Keep first and last points pinned to their scalar position
            # (the ramp boundaries).
            if self._dragging == 0 or self._dragging == len(self._points) - 1:
                old_scalar = self._points[self._dragging][0]
                self._points[self._dragging] = (old_scalar, new_opacity)
            else:
                lo, hi = self._scalar_range
                new_scalar = max(lo, min(hi, new_scalar))
                self._points[self._dragging] = (new_scalar, new_opacity)
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging >= 0:
            self._dragging = -1
            self._points.sort(key=lambda pt: pt[0])
            self.update()
            self.points_changed.emit(list(self._points))
        super().mouseReleaseEvent(event)
