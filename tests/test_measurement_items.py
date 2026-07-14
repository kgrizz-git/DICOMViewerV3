"""
Unit tests for Measurement Items module (tools.measurement_items).

Phase 1 refactoring: DraggableMeasurementText, MeasurementHandle, and MeasurementItem
were moved from measurement_tool.py to measurement_items.py. measurement_tool re-exports them.
Tests import from both modules, construction, and key attributes/methods.
Requires PySide6 and qapp fixture for Qt-based tests.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Optional pytest for qapp fixture
try:
    import pytest
except ImportError:
    pytest = None

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsTextItem


class TestMeasurementItemsImports(unittest.TestCase):
    """Test that Phase 1 modules and re-exports are available."""

    def test_import_from_measurement_items_module(self):
        """Classes must be importable from tools.measurement_items."""
        from tools.measurement_items import (
            DraggableMeasurementText,
            MeasurementHandle,
            MeasurementItem,
        )
        self.assertIsNotNone(DraggableMeasurementText)
        self.assertIsNotNone(MeasurementHandle)
        self.assertIsNotNone(MeasurementItem)

    def test_reexport_from_measurement_tool(self):
        """Phase 1: measurement_tool re-exports item classes for backward compatibility."""
        from tools.measurement_tool import (
            DraggableMeasurementText,
            MeasurementHandle,
            MeasurementItem,
            MeasurementTool,
        )
        self.assertIsNotNone(DraggableMeasurementText)
        self.assertIsNotNone(MeasurementHandle)
        self.assertIsNotNone(MeasurementItem)
        self.assertIsNotNone(MeasurementTool)


class TestMeasurementItemConstruction(unittest.TestCase):
    """Test MeasurementItem construction and attributes. Requires QApplication."""

    @classmethod
    def setUpClass(cls):
        """Ensure QApplication exists for Qt graphics items."""
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                cls._app = QApplication(sys.argv)
            else:
                cls._app = app
        except ImportError:
            cls._app = None

    def test_measurement_item_constructs_and_has_expected_attributes(self):
        """MeasurementItem can be constructed with line and text items and exposes key attributes."""
        try:
            from PySide6.QtWidgets import QApplication
            if QApplication.instance() is None:
                self.skipTest("QApplication not available")
        except ImportError:
            self.skipTest("PySide6 not installed")

        from tools.measurement_items import MeasurementItem

        start = QPointF(0.0, 0.0)
        end = QPointF(10.0, 0.0)
        line_item = QGraphicsLineItem(0, 0, 10, 0)
        text_item = QGraphicsTextItem("0.0 mm")
        pixel_spacing = (1.0, 1.0)

        item = MeasurementItem(start, end, line_item, text_item, pixel_spacing)

        self.assertEqual(item.start_point, start)
        self.assertEqual(item.end_point, end)
        self.assertIs(item.line_item, line_item)
        self.assertIs(item.text_item, text_item)
        self.assertEqual(item.pixel_spacing, pixel_spacing)
        self.assertIsNotNone(item.start_handle)
        self.assertIsNotNone(item.end_handle)
        self.assertTrue(item.start_handle.is_start)
        self.assertFalse(item.end_handle.is_start)
        self.assertIs(item.start_handle.parent_measurement, item)
        self.assertIs(item.end_handle.parent_measurement, item)

    def test_measurement_item_distance_updated(self):
        """MeasurementItem computes distance (pixels and formatted) after construction."""
        try:
            from PySide6.QtWidgets import QApplication
            if QApplication.instance() is None:
                self.skipTest("QApplication not available")
        except ImportError:
            self.skipTest("PySide6 not installed")

        from tools.measurement_items import MeasurementItem

        start = QPointF(0.0, 0.0)
        end = QPointF(10.0, 0.0)
        line_item = QGraphicsLineItem(0, 0, 10, 0)
        text_item = QGraphicsTextItem("")
        pixel_spacing = (1.0, 1.0)

        item = MeasurementItem(start, end, line_item, text_item, pixel_spacing)

        self.assertEqual(item.distance_pixels, 10.0)
        self.assertIsInstance(item.distance_formatted, str)
        self.assertGreater(len(item.distance_formatted), 0)


class TestDraggableMeasurementTextConstruction(unittest.TestCase):
    """Test DraggableMeasurementText construction."""

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                cls._app = QApplication(sys.argv)
            else:
                cls._app = app
        except ImportError:
            cls._app = None

    def test_draggable_text_constructs_with_none_measurement(self):
        """DraggableMeasurementText can be created with measurement=None and a callback."""
        try:
            from PySide6.QtWidgets import QApplication
            if QApplication.instance() is None:
                self.skipTest("QApplication not available")
        except ImportError:
            self.skipTest("PySide6 not installed")

        from tools.measurement_items import DraggableMeasurementText

        calls = []

        def callback(pt):
            calls.append(pt)

        text = DraggableMeasurementText(None, callback)
        self.assertIsNone(text.measurement)
        self.assertIs(text.offset_update_callback, callback)
        self.assertFalse(text._updating_position)


class TestMeasurementHandleConstruction(unittest.TestCase):
    """Test MeasurementHandle construction. Requires a MeasurementItem (and thus QApplication)."""

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app is None:
                cls._app = QApplication(sys.argv)
            else:
                cls._app = app
        except ImportError:
            cls._app = None

    def test_handle_constructs_with_measurement_and_color(self):
        """MeasurementHandle can be created with parent measurement and optional color."""
        try:
            from PySide6.QtWidgets import QApplication
            if QApplication.instance() is None:
                self.skipTest("QApplication not available")
        except ImportError:
            self.skipTest("PySide6 not installed")

        from tools.measurement_items import MeasurementHandle, MeasurementItem

        start = QPointF(0.0, 0.0)
        end = QPointF(5.0, 0.0)
        line_item = QGraphicsLineItem(0, 0, 5, 0)
        text_item = QGraphicsTextItem("")
        item = MeasurementItem(start, end, line_item, text_item, None)

        handle_start = item.start_handle
        handle_end = item.end_handle
        self.assertIsInstance(handle_start, MeasurementHandle)
        self.assertIsInstance(handle_end, MeasurementHandle)
        self.assertTrue(handle_start.is_start)
        self.assertFalse(handle_end.is_start)
        self.assertIs(handle_start.parent_measurement, item)
        self.assertIs(handle_end.parent_measurement, item)

    def test_handle_accepts_custom_color(self):
        """MeasurementHandle uses provided QColor when given."""
        try:
            from PySide6.QtWidgets import QApplication
            if QApplication.instance() is None:
                self.skipTest("QApplication not available")
        except ImportError:
            self.skipTest("PySide6 not installed")

        # We need a MeasurementItem reference; create a minimal one
        from tools.measurement_items import MeasurementHandle, MeasurementItem
        start = QPointF(0.0, 0.0)
        end = QPointF(1.0, 0.0)
        line_item = QGraphicsLineItem(0, 0, 1, 0)
        text_item = QGraphicsTextItem("")
        item = MeasurementItem(start, end, line_item, text_item, None)

        custom_color = QColor(255, 0, 0)
        handle = MeasurementHandle(item, is_start=True, color=custom_color)
        self.assertEqual(handle.pen().color(), custom_color)


class TestHandleDragHighlightSuppression(unittest.TestCase):
    """Selected styling must be suppressed only while a handle is actively dragged.

    Regression for TO_DO Bugs / Correctness "Measurement handle drag - spurious
    highlight": dragging an endpoint handle must not flash the yellow selected
    outline (in the main viewer or the handle-drag magnifier).
    """

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            cls._app = app if app is not None else QApplication(sys.argv)
        except ImportError:
            cls._app = None

    def _require_qt(self):
        try:
            from PySide6.QtWidgets import QApplication
            if QApplication.instance() is None:
                self.skipTest("QApplication not available")
        except ImportError:
            self.skipTest("PySide6 not installed")

    def _make_item(self):
        from tools.measurement_items import MeasurementItem
        line_item = QGraphicsLineItem(0, 0, 40, 0)
        line_item.setPen(QColor(0, 255, 0))
        text_item = QGraphicsTextItem("")
        return MeasurementItem(QPointF(0.0, 0.0), QPointF(40.0, 0.0), line_item, text_item, (1.0, 1.0))

    def test_paint_decision_tracks_drag_state(self):
        """_should_paint_selection_outline() is True when selected, False mid-drag, True after release."""
        self._require_qt()
        item = self._make_item()

        # Not selected -> no outline regardless of drag flag.
        self.assertFalse(item._should_paint_selection_outline())

        item.setSelected(True)
        self.assertTrue(item._should_paint_selection_outline())

        # During a handle drag the outline is suppressed (both start and end handles).
        for handle in (item.start_handle, item.end_handle):
            item._handle_drag_in_progress = True
            item._dragging_handle = handle
            self.assertFalse(
                item._should_paint_selection_outline(),
                f"outline should be suppressed while dragging {'start' if handle.is_start else 'end'} handle",
            )

        # Release restores normal selected styling.
        item._handle_drag_in_progress = False
        item._dragging_handle = None
        self.assertTrue(item._should_paint_selection_outline())

    def _count_yellow_pixels(self, dragging: bool) -> int:
        """Render a fresh selected measurement (optionally mid-drag) and count yellow pixels.

        A new item + scene is built per call and the scene is retained on the
        instance so shiboken does not delete the item before/while rendering.
        """
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QImage, QPainter
        from PySide6.QtWidgets import QGraphicsScene

        item = self._make_item()
        scene = QGraphicsScene()
        scene.addItem(item)
        item.setSelected(True)
        if dragging:
            item._handle_drag_in_progress = True
            item._dragging_handle = item.end_handle
        if not hasattr(self, "_scenes"):
            self._scenes = []
        self._scenes.append(scene)  # keep alive for the duration of the test

        image = QImage(140, 100, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(QColor(0, 0, 0))
        painter = QPainter(image)
        try:
            scene.render(painter, QRectF(0, 0, 140, 100), QRectF(-10, -10, 60, 40))
        finally:
            painter.end()

        yellow = 0
        for y in range(image.height()):
            for x in range(image.width()):
                c = image.pixelColor(x, y)
                if c.red() > 180 and c.green() > 180 and c.blue() < 90:
                    yellow += 1
        return yellow

    def test_render_has_no_yellow_overlay_during_drag(self):
        """The rendered scene (used by the magnifier) shows yellow when selected, none mid-drag."""
        self._require_qt()

        yellow_selected = self._count_yellow_pixels(dragging=False)
        self.assertGreater(yellow_selected, 0, "selected measurement should render a yellow outline")

        yellow_dragging = self._count_yellow_pixels(dragging=True)
        self.assertEqual(yellow_dragging, 0, "no yellow selection overlay should render during a handle drag")
