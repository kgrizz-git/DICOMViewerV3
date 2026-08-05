"""Tests for utils.bundled_fonts: font registry, path resolution, and Qt QFont helpers."""

from __future__ import annotations

import os
from unittest.mock import patch

from PySide6.QtGui import QFont

from utils.bundled_fonts import (
    DEFAULT_FONT_FAMILY,
    get_bundled_ttf_path,
    get_font_families,
    get_font_variants,
    get_variant_weight_italic,
    make_qfont,
    register_fonts_with_qt,
    resolve_font,
)


def test_get_font_families_and_variants() -> None:
    """Test get_font_families and get_font_variants including fallbacks."""
    families = get_font_families()
    assert isinstance(families, list)
    assert len(families) > 0
    assert DEFAULT_FONT_FAMILY in families
    assert "Noto Sans" in families
    assert "DejaVu Sans" in families

    # Valid family variants
    ibm_variants = get_font_variants("IBM Plex Sans")
    assert "Regular" in ibm_variants
    assert "Bold" in ibm_variants
    assert "SemiCond Regular" in ibm_variants

    # Unknown family fallback
    unknown_variants = get_font_variants("NonExistentFamily123")
    assert unknown_variants == get_font_variants(DEFAULT_FONT_FAMILY)


def test_resolve_font_fallbacks() -> None:
    """Test resolve_font for valid combinations and fallback logic."""
    # Valid family and variant
    fam, var = resolve_font("Noto Sans", "Italic")
    assert fam == "Noto Sans"
    assert var == "Italic"

    # Unknown family falls back to DEFAULT_FONT_FAMILY
    fam_unknown, var_kept = resolve_font("UnknownFontFamily", "Light")
    assert fam_unknown == DEFAULT_FONT_FAMILY
    assert var_kept == "Light"

    # Unknown variant falls back to "Bold" when available
    fam_ibm, var_fallback_bold = resolve_font("IBM Plex Sans", "SuperUltraBold")
    assert fam_ibm == "IBM Plex Sans"
    assert var_fallback_bold == "Bold"

    # Test fallback to "Regular" when "Bold" is not available
    mock_fonts = {
        "TestFamilyNoBold": {
            "Light": "path/light.ttf",
            "Regular": "path/regular.ttf",
        }
    }
    with patch("utils.bundled_fonts.BUNDLED_FONTS", mock_fonts):
        fam_test, var_reg = resolve_font("TestFamilyNoBold", "NonExistentVariant")
        assert fam_test == "TestFamilyNoBold"
        assert var_reg == "Regular"

    # Test fallback to first available variant when neither "Bold" nor "Regular" is present
    mock_fonts_custom = {
        "TestFamilyCustom": {
            "CustomVariant": "path/custom.ttf",
        }
    }
    with patch("utils.bundled_fonts.BUNDLED_FONTS", mock_fonts_custom):
        fam_custom, var_first = resolve_font("TestFamilyCustom", "NonExistentVariant")
        assert fam_custom == "TestFamilyCustom"
        assert var_first == "CustomVariant"


def test_get_bundled_ttf_path() -> None:
    """Test get_bundled_ttf_path returns absolute paths and handles frozen sys mode."""
    # Normal dev environment lookup
    path_str = get_bundled_ttf_path("IBM Plex Sans", "Regular")
    assert isinstance(path_str, str)
    assert path_str.endswith(".ttf")
    assert os.path.isabs(path_str)
    assert "IBM_Plex_Sans" in path_str

    # Fallback lookup for unknown inputs
    path_fallback = get_bundled_ttf_path("UnknownFontFamily", "UnknownVariant")
    assert isinstance(path_fallback, str)
    assert path_fallback.endswith(".ttf")
    assert os.path.isabs(path_fallback)

    # Test PyInstaller frozen sys mode path resolution
    fake_meipass = "/tmp/fake_meipass_bundled_fonts"
    with patch("sys.frozen", True, create=True), patch("sys._MEIPASS", fake_meipass, create=True):
        frozen_path = get_bundled_ttf_path("IBM Plex Sans", "Regular")
        assert frozen_path.startswith(fake_meipass)
        assert "resources" in frozen_path
        assert "fonts" in frozen_path


def test_get_variant_weight_italic() -> None:
    """Test get_variant_weight_italic for standard, SemiCond, and unknown variants."""
    # Standard variants
    assert get_variant_weight_italic("Light") == (300, False)
    assert get_variant_weight_italic("Regular") == (400, False)
    assert get_variant_weight_italic("Medium") == (500, False)
    assert get_variant_weight_italic("SemiBold") == (600, False)
    assert get_variant_weight_italic("Bold") == (700, False)
    assert get_variant_weight_italic("Italic") == (400, True)
    assert get_variant_weight_italic("Bold Italic") == (700, True)

    # SemiCondensed variants (prefix "SemiCond " is stripped)
    assert get_variant_weight_italic("SemiCond Light") == (300, False)
    assert get_variant_weight_italic("SemiCond Regular") == (400, False)
    assert get_variant_weight_italic("SemiCond Medium Italic") == (500, True)
    assert get_variant_weight_italic("SemiCond Bold Italic") == (700, True)

    # Unknown variant fallback (700, False)
    assert get_variant_weight_italic("NonExistentVariant") == (700, False)


def test_make_qfont_and_register_fonts_with_qt() -> None:
    """Test make_qfont output properties and register_fonts_with_qt execution."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    # Standard font creation
    font = make_qfont("IBM Plex Sans", "Regular", 14)
    assert isinstance(font, QFont)
    assert font.family() == "IBM Plex Sans"
    assert font.pointSize() == 14
    assert font.weight() == QFont.Weight.Normal
    assert font.italic() is False

    # SemiCondensed font creation (maps family name via _SEMICOND_QT_FAMILY)
    font_semicond = make_qfont("IBM Plex Sans", "SemiCond Bold", 12)
    assert font_semicond.family() == "IBM Plex Sans SemiCondensed"
    assert font_semicond.pointSize() == 12
    assert font_semicond.weight() == QFont.Weight.Bold
    assert font_semicond.italic() is False

    # Invalid font fallback creation
    font_fallback = make_qfont("UnknownFamily", "UnknownVariant", 10)
    assert isinstance(font_fallback, QFont)
    assert font_fallback.pointSize() == 10

    # Ensure register_fonts_with_qt executes without error
    register_fonts_with_qt()
