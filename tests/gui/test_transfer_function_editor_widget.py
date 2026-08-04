"""Tests for TransferFunctionEditorWidget points API and mouse drag."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent

from gui.transfer_function_editor_widget import TransferFunctionEditorWidget


def _left_press(pos: QPointF) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _left_move(pos: QPointF) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseMove,
        pos,
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _left_release(pos: QPointF) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


@pytest.mark.qt
def test_set_and_get_points(qapp) -> None:
    w = TransferFunctionEditorWidget()
    w.resize(220, 100)
    pts = [(0.0, 0.0), (0.5, 0.8), (1.0, 1.0)]
    w.set_points(pts)
    assert w.get_points() == pts
    assert w._scalar_range == (0.0, 1.0)


@pytest.mark.qt
def test_set_points_expands_degenerate_scalar_range(qapp) -> None:
    w = TransferFunctionEditorWidget()
    w.set_points([(5.0, 0.0), (5.0, 1.0)])
    lo, hi = w._scalar_range
    assert lo == 5.0
    assert hi == 6.0


@pytest.mark.qt
def test_drag_endpoint_changes_opacity_only(qapp) -> None:
    w = TransferFunctionEditorWidget()
    w.resize(220, 100)
    w.set_points([(0.0, 0.0), (1.0, 1.0)])
    emitted: list[list[tuple[float, float]]] = []
    w.points_changed.connect(emitted.append)

    # Hit the first control point and drag upward (higher opacity).
    start = QPointF(w._scalar_to_x(0.0), w._opacity_to_y(0.0))
    w.mousePressEvent(_left_press(start))
    assert w._dragging == 0
    mid = QPointF(start.x(), w._opacity_to_y(0.7))
    w.mouseMoveEvent(_left_move(mid))
    w.mouseReleaseEvent(_left_release(mid))

    assert w._dragging == -1
    assert len(emitted) == 1
    assert emitted[0][0][0] == 0.0  # scalar pinned
    assert emitted[0][0][1] == pytest.approx(0.7, abs=0.05)


@pytest.mark.qt
def test_paint_event_noop_without_points(qapp) -> None:
    w = TransferFunctionEditorWidget()
    w.resize(220, 100)
    # Empty paint must not raise and must leave points unchanged.
    w.paintEvent(None)
    assert w.get_points() == []
    pts = [(0.0, 0.0), (1.0, 1.0)]
    w.set_points(pts)
    w.paintEvent(None)
    assert w.get_points() == pts
