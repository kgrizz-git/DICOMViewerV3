"""Tests for AngleMeasurementItem construction and handle visibility."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QLineF, QPointF
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene, QGraphicsTextItem

from tools.angle_measurement_items import (
    AngleMeasurementItem,
    format_angle_label,
    interior_angle_at_vertex_degrees,
)


@pytest.mark.qt
def test_construct_angle_item_and_geometry(qapp) -> None:
    p1, p2, p3 = QPointF(0, 0), QPointF(0, 50), QPointF(50, 50)
    line1 = QGraphicsLineItem(QLineF(p1, p2))
    line2 = QGraphicsLineItem(QLineF(p2, p3))
    text = QGraphicsTextItem(format_angle_label(90.0))
    item = AngleMeasurementItem(p1, p2, p3, line1, line2, text)
    scene = QGraphicsScene()
    scene.addItem(item)
    deg = interior_angle_at_vertex_degrees(p1, p2, p3)
    assert abs(deg - 90.0) < 1e-6
    item.show_handles()
    item.hide_handles()
    item.update_angle_geometry()
    assert item.scene() is scene
