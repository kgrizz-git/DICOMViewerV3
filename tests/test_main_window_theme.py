"""
Unit tests for Main Window Theme module (gui.main_window_theme).

Phase 1 refactoring: theme logic extracted from main_window.py to main_window_theme.py.
Tests get_theme_stylesheet and get_theme_viewer_background_color.
No QApplication required for these tests.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtGui import QColor

from gui.main_window_theme import get_theme_stylesheet, get_theme_viewer_background_color


def _dummy_paths():
    """Return dummy checkmark paths for stylesheet tests."""
    return ("/dummy/white.png", "/dummy/black.png")


class TestGetThemeStylesheet(unittest.TestCase):
    """Tests for get_theme_stylesheet."""

    def test_dark_theme_returns_non_empty_string(self):
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("dark", white_p, black_p)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_dark_theme_contains_dark_colors(self):
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("dark", white_p, black_p)
        self.assertIn("#2b2b2b", result)
        self.assertIn("#1b1b1b", result)

    def test_dark_theme_uses_white_checkmark_path(self):
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("dark", white_p, black_p)
        self.assertIn(white_p, result)

    def test_light_theme_returns_non_empty_string(self):
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("light", white_p, black_p)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_light_theme_contains_light_colors(self):
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("light", white_p, black_p)
        self.assertIn("#f0f0f0", result)
        self.assertIn("#ffffff", result)

    def test_light_theme_uses_black_checkmark_path(self):
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("light", white_p, black_p)
        self.assertIn(black_p, result)

    def test_unknown_theme_defaults_to_light_stylesheet(self):
        """Unknown theme name should fall through to else branch (light)."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("unknown", white_p, black_p)
        self.assertIn("#f0f0f0", result)


class TestGetThemeViewerBackgroundColor(unittest.TestCase):
    """Tests for get_theme_viewer_background_color."""

    def test_dark_theme_returns_expected_color(self):
        result = get_theme_viewer_background_color("dark")
        self.assertIsInstance(result, QColor)
        self.assertEqual(result.red(), 27)
        self.assertEqual(result.green(), 27)
        self.assertEqual(result.blue(), 27)

    def test_light_theme_returns_expected_color(self):
        result = get_theme_viewer_background_color("light")
        self.assertIsInstance(result, QColor)
        self.assertEqual(result.red(), 64)
        self.assertEqual(result.green(), 64)
        self.assertEqual(result.blue(), 64)

    def test_unknown_theme_returns_light_viewer_color(self):
        """Unknown theme uses else branch: #404040."""
        result = get_theme_viewer_background_color("unknown")
        self.assertIsInstance(result, QColor)
        self.assertEqual(result.red(), 64)
        self.assertEqual(result.green(), 64)
        self.assertEqual(result.blue(), 64)
