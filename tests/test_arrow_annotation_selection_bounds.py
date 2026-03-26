"""
Sanity tests for ArrowAnnotationItem selection outline vs Graphics View invalidation.

When selected, custom dashed stroke is painted in paint(); Qt requires the stroke to lie
inside boundingRect() so scene updates clear the full region (avoids dash pixel trails).
See plan: fix_arrow_selection_smear (boundingRect + prepareGeometryChange).
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsScene

from tools.arrow_annotation_tool import (
    ARROWHEAD_SIZE_MULTIPLIER,
    ArrowAnnotationItem,
    ArrowHeadItem,
    _SELECTION_BOUNDS_INFLATE,
    _SELECTION_OUTLINE_PEN_WIDTH,
    _line_end_shortened,
)


def _make_arrow_item() -> ArrowAnnotationItem:
    """Build a representative arrow (mirrors ArrowAnnotationTool._create_arrow_item)."""
    start = QPointF(100.0, 50.0)
    end = QPointF(220.0, 80.0)
    size = 6
    arrowhead_size = size * ARROWHEAD_SIZE_MULTIPLIER
    color = QColor(255, 255, 0)
    relative_end = end - start
    line_end = _line_end_shortened(relative_end)
    line_item = QGraphicsLineItem(QLineF(QPointF(0, 0), line_end))
    pen = QPen(color, size)
    pen.setCosmetic(True)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    line_item.setPen(pen)
    arrowhead = ArrowHeadItem(QPointF(0, 0), relative_end, color, arrowhead_size)
    item = ArrowAnnotationItem(start, end, line_item, arrowhead, color)
    item.setPos(start)
    return item


class TestArrowAnnotationSelectionBounds(unittest.TestCase):
    """Requires PySide6 QApplication."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            app = QApplication.instance()
            if app is None:
                cls._app = QApplication(sys.argv)
            else:
                cls._app = app
        except ImportError:
            cls._app = None

    def setUp(self) -> None:
        if QApplication.instance() is None:
            self.skipTest("QApplication not available")

    def test_selected_bounding_rect_contains_inflated_selection_hull(self) -> None:
        """Dashed outline region must be inside item boundingRect when selected."""
        arrow = _make_arrow_item()
        scene = QGraphicsScene()
        scene.addItem(arrow)
        arrow.setSelected(True)

        br = arrow.boundingRect()
        hull_bounds = arrow._selection_hull_path().boundingRect()
        inflate = _SELECTION_OUTLINE_PEN_WIDTH / 2.0 + _SELECTION_BOUNDS_INFLATE
        expanded = hull_bounds.adjusted(-inflate, -inflate, inflate, inflate)
        self.assertFalse(expanded.isNull(), "selection hull should have non-empty bounds")
        self.assertTrue(
            br.contains(expanded),
            "boundingRect must fully contain inflated hull so the dashed stroke invalidates correctly",
        )

        expanded_scene = arrow.mapRectToScene(expanded)
        br_scene = arrow.mapRectToScene(br)
        self.assertTrue(
            br_scene.contains(expanded_scene),
            "mapped item bounds must contain mapped selection stroke (scene coords)",
        )


if __name__ == "__main__":
    unittest.main()
