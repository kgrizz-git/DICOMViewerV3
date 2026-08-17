"""
Comprehensive unit tests for src/gui/main_window_theme.py.

Achieves 100% statement and branch coverage for main_window_theme.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtGui import QColor

from gui.main_window_theme import (
    _blend_hex_colors,
    _boost_hex_saturation,
    _themes_dir,
    get_theme_stylesheet,
    get_theme_viewer_background_color,
    metadata_tag_band_color,
)


def test_blend_hex_colors() -> None:
    """Test blending hex colors with fraction clamping."""
    # Midpoint blend
    assert _blend_hex_colors("#000000", "#ffffff", 0.5) == "#808080"

    # Fraction < 0.0 clamped to 0.0 (returns base color)
    assert _blend_hex_colors("#123456", "#ffffff", -0.5) == "#123456"

    # Fraction > 1.0 clamped to 1.0 (returns tint color)
    assert _blend_hex_colors("#123456", "#ffffff", 1.5) == "#ffffff"


def test_boost_hex_saturation() -> None:
    """Test boosting saturation of a hex color."""
    boosted = _boost_hex_saturation("#141414", 1.18)
    assert boosted.startswith("#")
    assert len(boosted) == 7


def test_metadata_tag_band_color() -> None:
    """Test metadata tag band color for dark and light themes."""
    dark_band = metadata_tag_band_color("dark", "#2196F3")
    assert dark_band.startswith("#")
    assert len(dark_band) == 7

    light_band = metadata_tag_band_color("light", "#2196F3")
    assert light_band.startswith("#")
    assert len(light_band) == 7


def test_themes_dir_default_and_frozen(tmp_path: Path, monkeypatch) -> None:
    """Test _themes_dir in standard dev mode and frozen PyInstaller mode."""
    # 1. Normal dev mode
    monkeypatch.delattr(sys, "frozen", raising=False)
    dev_dir = _themes_dir()
    assert dev_dir.name == "themes"

    # 2. Frozen mode with _MEIPASS set
    fake_meipass = tmp_path / "meipass"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(fake_meipass), raising=False)
    frozen_dir = _themes_dir()
    assert frozen_dir == fake_meipass / "resources" / "themes"

    # 3. Frozen mode with _MEIPASS set to None (fallthrough branch)
    monkeypatch.setattr(sys, "_MEIPASS", None, raising=False)
    fallthrough_dir = _themes_dir()
    assert fallthrough_dir.name == "themes"


def test_get_theme_stylesheet_success() -> None:
    """Test get_theme_stylesheet loads and substitutes placeholders for valid theme and accent."""
    dark_qss = get_theme_stylesheet("dark", "path/white.png", "path/black.png", accent_id="steel-blue")
    assert "path/white.png" in dark_qss
    assert len(dark_qss) > 0

    light_qss = get_theme_stylesheet("light", "path/white.png", "path/black.png", accent_id="emerald")
    assert "path/black.png" in light_qss
    assert len(light_qss) > 0


def test_get_theme_stylesheet_fallback_to_light() -> None:
    """Test get_theme_stylesheet falls back to light.qss when requested theme does not exist."""
    fallback_qss = get_theme_stylesheet("non_existent_theme", "white.png", "black.png")
    assert "black.png" in fallback_qss
    assert len(fallback_qss) > 0



def test_get_theme_stylesheet_missing_all_files(tmp_path: Path) -> None:
    """Test get_theme_stylesheet returns empty string when neither theme nor light.qss exist."""
    empty_dir = tmp_path / "empty_themes"
    empty_dir.mkdir()

    with patch("gui.main_window_theme._themes_dir", return_value=empty_dir):
        result = get_theme_stylesheet("non_existent", "w.png", "b.png")
        assert result == ""


def test_get_theme_viewer_background_color() -> None:
    """Test get_theme_viewer_background_color returns QColor(14, 14, 14)."""
    dark_bg = get_theme_viewer_background_color("dark")
    assert isinstance(dark_bg, QColor)
    assert dark_bg.red() == 14
    assert dark_bg.green() == 14
    assert dark_bg.blue() == 14

    light_bg = get_theme_viewer_background_color("light")
    assert light_bg == dark_bg


def test_blend_hex_colors_rejects_invalid_trusted_color_inputs() -> None:
    """Theme helpers reject malformed colors outside their trusted-input contract."""
    with pytest.raises(ValueError):
        _blend_hex_colors("invalid", "#ffffff", 0.5)

    with pytest.raises(ValueError):
        _blend_hex_colors("#000000", "#ZZZZZZ", 0.5)


def test_boost_hex_saturation_rejects_invalid_trusted_color_inputs() -> None:
    """Theme helpers reject malformed colors outside their trusted-input contract."""
    with pytest.raises(ValueError):
        _boost_hex_saturation("not_a_hex_color", 1.2)


def test_themes_dir_frozen_without_meipass_uses_current_fallback(monkeypatch) -> None:
    """Record the current fallback pending frozen-build reproduction."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", None, raising=False)
    resolved_dir = _themes_dir()
    expected_dev_path = Path(__file__).parent.parent.parent / "resources" / "themes"
    assert resolved_dir == expected_dev_path


# ---------------------------------------------------------------------------
# Accent/metadata-band regression tests adopted from initial-commit suite
# ---------------------------------------------------------------------------

def test_light_theme_uses_accent_tinted_alternate_rows() -> None:
    """Light theme must use accent_soft (#f6e5e7 for garnet) as alternate-row color, not raw accent (#a0303f)."""
    white_p, black_p = "/dummy/white.png", "/dummy/black.png"
    result = get_theme_stylesheet("light", white_p, black_p, accent_id="garnet")
    assert "alternate-background-color: #f6e5e7" in result
    assert "alternate-background-color: #a0303f" not in result


def test_dark_theme_uses_readable_accent_tinted_alternate_rows() -> None:
    """Dark theme must use accent_muted (#32151a for garnet) as alternate-row color, not raw accent (#a0303f)."""
    white_p, black_p = "/dummy/white.png", "/dummy/black.png"
    result = get_theme_stylesheet("dark", white_p, black_p, accent_id="garnet")
    assert "alternate-background-color: #32151a" in result
    assert "alternate-background-color: #a0303f" not in result


def test_export_tags_tree_selector_present_in_both_themes() -> None:
    """Phase A/B: stable objectName hook plus scoped indeterminate indicator."""
    white_p, black_p = "/dummy/white.png", "/dummy/black.png"
    light = get_theme_stylesheet("light", white_p, black_p, accent_id="garnet")
    dark = get_theme_stylesheet("dark", white_p, black_p, accent_id="garnet")
    assert "QTreeWidget#tag_export_tags_tree" in light
    assert "QTreeWidget#tag_export_tags_tree" in dark
    assert "QTreeWidget#tag_export_tags_tree::indicator:indeterminate" in light
    assert "QTreeWidget#tag_export_tags_tree::indicator:indeterminate" in dark
    light_indeterminate = light[
        light.index("QTreeWidget#tag_export_tags_tree::indicator:indeterminate") :
        light.index("}", light.index("QTreeWidget#tag_export_tags_tree::indicator:indeterminate"))
        + 1
    ]
    dark_indeterminate = dark[
        dark.index("QTreeWidget#tag_export_tags_tree::indicator:indeterminate") :
        dark.index("}", dark.index("QTreeWidget#tag_export_tags_tree::indicator:indeterminate"))
        + 1
    ]
    assert "#a0303f" in light_indeterminate
    assert "#a0303f" in dark_indeterminate


def test_metadata_bands_derived_from_selected_accent() -> None:
    """The {metadata_tag_band} placeholder is substituted with metadata_tag_band_color() for both themes."""
    white_p, black_p = "/dummy/white.png", "/dummy/black.png"
    light = get_theme_stylesheet("light", white_p, black_p, accent_id="garnet")
    dark = get_theme_stylesheet("dark", white_p, black_p, accent_id="garnet")
    expected_light = metadata_tag_band_color("light", "#a0303f")
    expected_dark = metadata_tag_band_color("dark", "#a0303f")
    assert f"QTreeWidget#metadata_tag_tree {{\n                    alternate-background-color: {expected_light};" in light
    assert f"QTreeWidget#metadata_tag_tree {{\n                    alternate-background-color: {expected_dark};" in dark


def test_missing_dark_qss_falls_back_to_light_metadata_band(tmp_path: Path) -> None:
    """Regression: when dark.qss is absent, metadata band must use light-theme tint, not dark-theme tint."""
    white_p, black_p = "/dummy/white.png", "/dummy/black.png"
    themes = tmp_path / "themes"
    themes.mkdir()
    (themes / "light.qss").write_text(
        "QTreeWidget#metadata_tag_tree {\n"
        "    alternate-background-color: {metadata_tag_band};\n"
        "}\n",
        encoding="utf-8",
    )
    with patch("gui.main_window_theme._themes_dir", return_value=themes):
        result = get_theme_stylesheet("dark", white_p, black_p, accent_id="garnet")
    expected_light_band = metadata_tag_band_color("light", "#a0303f")
    expected_dark_band = metadata_tag_band_color("dark", "#a0303f")
    assert expected_light_band in result
    assert expected_dark_band not in result
