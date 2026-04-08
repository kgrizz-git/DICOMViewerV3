"""Tests for ``tools.roi_persistence`` clipboard serialization."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF

from tools.roi_manager import ROIItem, ROIGraphicsEllipseItem, ROIGraphicsRectItem
from tools.roi_persistence import serialize_roi_for_clipboard, serialize_rois_for_clipboard


@pytest.mark.qt
def test_serialize_rectangle_roi_clipboard_dict(qapp) -> None:
    rect = QRectF(1.0, 2.0, 30.0, 40.0)
    item = ROIGraphicsRectItem(rect)
    roi = ROIItem("rectangle", item, pen_width=2, pen_color=(10, 20, 30))
    d = serialize_roi_for_clipboard(roi)
    assert d["shape_type"] == "rectangle"
    assert d["rect"] == {"x": 1.0, "y": 2.0, "width": 30.0, "height": 40.0}
    assert d["pen_width"] == 2
    assert d["pen_color"] == (10, 20, 30)
    assert "visible_statistics" in d
    assert isinstance(d["visible_statistics"], list)


@pytest.mark.qt
def test_serialize_ellipse_roi_and_list(qapp) -> None:
    rect = QRectF(0.0, 0.0, 10.0, 10.0)
    item = ROIGraphicsEllipseItem(rect)
    roi = ROIItem("ellipse", item, pen_width=3, pen_color=(255, 0, 0))
    lst = serialize_rois_for_clipboard([roi])
    assert len(lst) == 1
    assert lst[0]["shape_type"] == "ellipse"
    assert lst[0]["rect"]["width"] == 10.0
