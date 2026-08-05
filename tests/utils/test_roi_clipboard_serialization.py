"""Tests for roi_persistence: utility clipboard serializers for ROIItem."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPen

from utils.roi_persistence import (
    serialize_roi_for_clipboard,
    serialize_rois_for_clipboard,
)


class MockROIItem:
    def __init__(
        self,
        shape: str,
        rect: QRectF,
        pos: QPointF,
        pen: QPen,
        stats: list | None = None,
    ):
        self.shape_type = shape
        self.item = MockGraphicsItem(rect, pos, pen)
        if stats is not None:
            self.visible_statistics = stats


class MockGraphicsItem:
    def __init__(self, rect: QRectF, pos: QPointF, pen: QPen):
        self._rect = rect
        self._pos = pos
        self._pen = pen

    def rect(self) -> QRectF:
        return self._rect

    def pos(self) -> QPointF:
        return self._pos

    def pen(self) -> QPen:
        return self._pen


class ZeroWidthFloatPen:
    """Mimics the legacy pen state that requires the integer-width fallback."""

    def widthF(self) -> float:
        return 0.0

    def width(self) -> int:
        return 4

    def color(self) -> QColor:
        return QColor(0, 0, 0)


def test_serialize_roi_rect() -> None:
    rect = QRectF(1.5, 2.5, 10.0, 20.0)
    pos = QPointF(5.0, 5.0)
    pen = QPen(QColor(255, 0, 0))
    pen.setWidthF(3.5)
    roi = MockROIItem("rectangle", rect, pos, pen)

    d = serialize_roi_for_clipboard(roi)
    assert d["shape_type"] == "rectangle"
    assert d["rect"] == {"x": 1.5, "y": 2.5, "width": 10.0, "height": 20.0}
    assert d["position"] == {"x": 5.0, "y": 5.0}
    assert d["pen_width"] == 3
    assert d["pen_color"] == (255, 0, 0)
    assert "visible_statistics" not in d


def test_serialize_roi_ellipse() -> None:
    rect = QRectF(0.0, 0.0, 15.0, 15.0)
    pos = QPointF(0.0, 0.0)
    pen = QPen(QColor(0, 255, 0))
    pen.setWidth(1)
    roi = MockROIItem("ellipse", rect, pos, pen)

    d = serialize_roi_for_clipboard(roi)
    assert d["shape_type"] == "ellipse"
    assert d["pen_width"] == 1
    assert d["pen_color"] == (0, 255, 0)


def test_serialize_roi_with_statistics() -> None:
    rect = QRectF(0.0, 0.0, 5.0, 5.0)
    pos = QPointF(10.0, 10.0)
    pen = QPen(QColor(0, 0, 255))
    roi = MockROIItem("rectangle", rect, pos, pen, stats=["mean: 120", "sd: 5.5"])

    d = serialize_roi_for_clipboard(roi)
    assert d["visible_statistics"] == ["mean: 120", "sd: 5.5"]
    roi.visible_statistics.append("max: 255")
    assert d["visible_statistics"] == ["mean: 120", "sd: 5.5"]


def test_serialize_roi_pen_width_fallback() -> None:
    rect = QRectF(0.0, 0.0, 5.0, 5.0)
    pos = QPointF(0.0, 0.0)
    roi = MockROIItem("rectangle", rect, pos, ZeroWidthFloatPen())

    d = serialize_roi_for_clipboard(roi)
    assert d["pen_width"] == 4


def test_serialize_rois_list() -> None:
    rect = QRectF(1.0, 1.0, 2.0, 2.0)
    pos = QPointF(0.0, 0.0)
    pen = QPen(QColor(0, 0, 0))
    roi = MockROIItem("ellipse", rect, pos, pen)

    lst = serialize_rois_for_clipboard([roi, roi])
    assert len(lst) == 2
    assert lst[0]["shape_type"] == "ellipse"
    assert lst[1]["shape_type"] == "ellipse"
    assert lst[0] is not lst[1]
