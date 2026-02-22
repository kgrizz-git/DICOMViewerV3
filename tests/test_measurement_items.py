"""
Unit tests for Measurement Items module (tools.measurement_items).

Phase 1 refactoring: DraggableMeasurementText, MeasurementHandle, and MeasurementItem
were moved from measurement_tool.py to measurement_items.py. measurement_tool re-exports them.
Tests import from both modules, construction, and key attributes/methods.
Requires PySide6 and qapp fixture for Qt-based tests.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Optional pytest for qapp fixture
try:
    import pytest
except ImportError:
    pytest = None

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsTextItem
from PySide6.QtGui import QColor


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

        from tools.measurement_items import MeasurementItem, MeasurementHandle

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

        from tools.measurement_items import MeasurementHandle

        # We need a MeasurementItem reference; create a minimal one
        from tools.measurement_items import MeasurementItem
        start = QPointF(0.0, 0.0)
        end = QPointF(1.0, 0.0)
        line_item = QGraphicsLineItem(0, 0, 1, 0)
        text_item = QGraphicsTextItem("")
        item = MeasurementItem(start, end, line_item, text_item, None)

        custom_color = QColor(255, 0, 0)
        handle = MeasurementHandle(item, is_start=True, color=custom_color)
        self.assertEqual(handle.pen().color(), custom_color)
