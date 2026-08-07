"""
Unit tests for Main Window Theme module (gui.main_window_theme).

Phase 1 refactoring: theme logic extracted from main_window.py to main_window_theme.py.
Tests get_theme_stylesheet and get_theme_viewer_background_color.
No QApplication required for these tests.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from PySide6.QtGui import QColor

from gui.main_window_theme import (
    get_theme_stylesheet,
    get_theme_viewer_background_color,
    metadata_tag_band_color,
)


def _dummy_paths():
    """Return dummy checkmark paths for stylesheet tests."""
    return ("/dummy/white.png", "/dummy/black.png")


class TestGetThemeStylesheet(unittest.TestCase):
    """Tests for get_theme_stylesheet."""

    def test_dark_theme_returns_non_empty_string(self):
        """Dark-theme stylesheet is a non-empty string (sanity check)."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("dark", white_p, black_p)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_dark_theme_contains_dark_colors(self):
        """Dark-theme stylesheet includes dark surface colors from dark.qss."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("dark", white_p, black_p)
        self.assertIn("#1e1e1e", result)
        self.assertIn("#252525", result)

    def test_dark_theme_uses_white_checkmark_path(self):
        """Dark-theme checkbox uses the white checkmark icon path."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("dark", white_p, black_p)
        self.assertIn(white_p, result)

    def test_light_theme_returns_non_empty_string(self):
        """Light-theme stylesheet is a non-empty string (sanity check)."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("light", white_p, black_p)
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 100)

    def test_light_theme_contains_light_colors(self):
        """Light-theme stylesheet includes light surface colors from light.qss."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("light", white_p, black_p)
        self.assertIn("#f0f0f0", result)
        self.assertIn("#ffffff", result)

    def test_light_theme_uses_accent_tinted_alternate_rows(self):
        """Light theme substitutes accent_soft (#f6e5e7 for garnet) as the
        alternate-row color, not the raw accent (#a0303f) — keep rows readable
        against the light background. See src/gui/accent_presets.py
        (accent_soft / accent_muted) for the palette derivation."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("light", white_p, black_p, accent_id="garnet")
        self.assertIn("alternate-background-color: #f6e5e7", result)
        self.assertNotIn("alternate-background-color: #a0303f", result)

    def test_dark_theme_uses_readable_accent_tinted_alternate_rows(self):
        """Dark theme substitutes accent_muted (#32151a for garnet) as the
        alternate-row color, not the raw accent (#a0303f) — keep rows readable
        against the dark background. See src/gui/accent_presets.py (accent_soft / accent_muted)."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("dark", white_p, black_p, accent_id="garnet")
        self.assertIn("alternate-background-color: #32151a", result)
        self.assertNotIn("alternate-background-color: #a0303f", result)

    def test_metadata_bands_are_subtly_derived_from_the_selected_accent(self):
        """The {metadata_tag_band} QSS placeholder is substituted with
        metadata_tag_band_color(theme, accent) — a deliberately subtle
        accent-derived tint — for both light and dark themes."""
        white_p, black_p = _dummy_paths()

        light = get_theme_stylesheet("light", white_p, black_p, accent_id="garnet")
        dark = get_theme_stylesheet("dark", white_p, black_p, accent_id="garnet")

        expected_light = metadata_tag_band_color("light", "#a0303f")
        expected_dark = metadata_tag_band_color("dark", "#a0303f")
        self.assertIn(
            f"QTreeWidget#metadata_tag_tree {{\n                    alternate-background-color: {expected_light};",
            light,
        )
        self.assertIn(
            f"QTreeWidget#metadata_tag_tree {{\n                    alternate-background-color: {expected_dark};",
            dark,
        )

    def test_light_theme_uses_black_checkmark_path(self):
        """Light-theme checkbox uses the black checkmark icon path."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("light", white_p, black_p)
        self.assertIn(black_p, result)

    def test_unknown_theme_defaults_to_light_stylesheet(self):
        """Unknown theme name should fall through to else branch (light)."""
        white_p, black_p = _dummy_paths()
        result = get_theme_stylesheet("unknown", white_p, black_p)
        self.assertIn("#f0f0f0", result)

    def test_missing_dark_qss_falls_back_to_light_metadata_band(self):
        """Regression: when dark.qss is absent and only light.qss exists, the
        metadata band tint must follow the *effective* (resolved-from-fallback)
        theme — light — not the originally requested ``"dark"``. Otherwise the
        band color returned by ``metadata_tag_band_color("dark", ...)`` is
        layered onto a light QSS and renders as a near-black alternate row."""
        import tempfile
        from pathlib import Path

        import gui.main_window_theme as mw_theme

        white_p, black_p = _dummy_paths()
        with tempfile.TemporaryDirectory() as themes_dir:
            themes = Path(themes_dir)
            (themes / "light.qss").write_text(
                "QTreeWidget#metadata_tag_tree {\n"
                "    alternate-background-color: {metadata_tag_band};\n"
                "}\n",
                encoding="utf-8",
            )
            original_themes_dir = mw_theme._themes_dir
            mw_theme._themes_dir = lambda: themes
            try:
                result = get_theme_stylesheet(
                    "dark", white_p, black_p, accent_id="garnet"
                )
            finally:
                mw_theme._themes_dir = original_themes_dir

            expected_light_band = metadata_tag_band_color("light", "#a0303f")
            expected_dark_band = metadata_tag_band_color("dark", "#a0303f")
            self.assertIn(expected_light_band, result)
            self.assertNotIn(expected_dark_band, result)


class TestGetThemeViewerBackgroundColor(unittest.TestCase):
    """Tests for get_theme_viewer_background_color."""

    def test_dark_theme_returns_expected_color(self):
        """Viewer background for dark theme is the near-black letterbox #0e0e0e."""
        result = get_theme_viewer_background_color("dark")
        self.assertIsInstance(result, QColor)
        # Match main_window_theme: #0e0e0e letterbox (was #1b1b1b)
        self.assertEqual(result.red(), 14)
        self.assertEqual(result.green(), 14)
        self.assertEqual(result.blue(), 14)

    def test_light_theme_returns_expected_color(self):
        """Viewer background for light theme is the same near-black letterbox
        #0e0e0e (the function intentionally ignores theme)."""
        result = get_theme_viewer_background_color("light")
        self.assertIsInstance(result, QColor)
        # Match the dark theme's near-black viewer letterbox.
        self.assertEqual(result.red(), 14)
        self.assertEqual(result.green(), 14)
        self.assertEqual(result.blue(), 14)

    def test_unknown_theme_returns_light_viewer_color(self):
        """Unknown theme uses else branch: same as light (#0e0e0e)."""
        result = get_theme_viewer_background_color("unknown")
        self.assertIsInstance(result, QColor)
        self.assertEqual(result.red(), 14)
        self.assertEqual(result.green(), 14)
        self.assertEqual(result.blue(), 14)
