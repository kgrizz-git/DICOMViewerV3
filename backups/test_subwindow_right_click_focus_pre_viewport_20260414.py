"""
Regression: right-click on an unfocused image pane focuses it and still delivers
the press to ImageViewer (W/L prep / context menu on same gesture).

Covers SubWindowContainer.eventFilter branching (left swallowed vs non-left passes through).
"""

from __future__ import annotations

import pytest

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from gui.image_viewer import ImageViewer
from gui.sub_window_container import SubWindowContainer


def _right_press_on_view(viewer: ImageViewer) -> QMouseEvent:
    """Build a MouseButtonPress for the view widget (view coordinates)."""
    local = QPointF(24.0, 24.0)
    g = viewer.mapToGlobal(QPoint(int(local.x()), int(local.y())))
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        local,
        viewer.mapToScene(QPoint(int(local.x()), int(local.y()))),
        g,
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _left_press_on_view(viewer: ImageViewer) -> QMouseEvent:
    local = QPointF(24.0, 24.0)
    g = viewer.mapToGlobal(QPoint(int(local.x()), int(local.y())))
    return QMouseEvent(
        QEvent.Type.MouseButtonPress,
        local,
        viewer.mapToScene(QPoint(int(local.x()), int(local.y()))),
        g,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


@pytest.mark.qt
def test_unfocused_right_click_focuses_without_consuming_filter(qapp) -> None:
    viewer = ImageViewer()
    container = SubWindowContainer(viewer)
    assert container.is_focused is False

    ev = _right_press_on_view(viewer)
    handled = container.eventFilter(viewer, ev)

    assert handled is False
    assert container.is_focused is True


@pytest.mark.qt
def test_unfocused_right_click_then_viewer_gets_wl_prep(qapp) -> None:
    viewer = ImageViewer()
    container = SubWindowContainer(viewer)
    viewer.mouse_mode = "pan"
    viewer.resize(200, 200)
    container.resize(200, 200)

    ev = _right_press_on_view(viewer)
    assert container.eventFilter(viewer, ev) is False
    assert container.is_focused is True

    viewer.mousePressEvent(ev)
    assert viewer.right_mouse_drag_start_pos is not None


@pytest.mark.qt
def test_unfocused_left_click_still_swallowed_by_filter(qapp) -> None:
    viewer = ImageViewer()
    container = SubWindowContainer(viewer)
    ev = _left_press_on_view(viewer)
    assert container.eventFilter(viewer, ev) is True
    assert container.is_focused is True
