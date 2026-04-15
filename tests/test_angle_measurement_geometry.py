"""Unit tests for in-plane angle-at-vertex geometry (angle measurement tool)."""

from PySide6.QtCore import QPointF

from tools.angle_measurement_items import interior_angle_at_vertex_degrees, format_angle_label


def test_right_angle() -> None:
    p1 = QPointF(0, 0)
    p2 = QPointF(0, 10)
    p3 = QPointF(10, 10)
    deg = interior_angle_at_vertex_degrees(p1, p2, p3)
    assert abs(deg - 90.0) < 1e-6


def test_straight_line_180() -> None:
    p1 = QPointF(0, 0)
    p2 = QPointF(5, 0)
    p3 = QPointF(10, 0)
    deg = interior_angle_at_vertex_degrees(p1, p2, p3)
    assert abs(deg - 180.0) < 1e-6


def test_format_angle_label() -> None:
    assert "°" in format_angle_label(90.0)

