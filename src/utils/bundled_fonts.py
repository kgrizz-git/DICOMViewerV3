"""
Bundled Font Registry

Enumerates the TrueType fonts shipped in resources/fonts/ and provides
helpers for:
  - Registering them with Qt's QFontDatabase at startup.
  - Resolving an absolute TTF path for PIL/Pillow (export rendering).
  - Creating QFont instances with correct weight and italic flags.

Usage:
    from utils.bundled_fonts import (
        get_font_families, get_font_variants, get_bundled_ttf_path,
        make_qfont, resolve_font, register_fonts_with_qt,
        DEFAULT_FONT_FAMILY, DEFAULT_FONT_VARIANT,
    )
"""

import sys
from pathlib import Path

# Nested dict: family → {variant_display_name: relative_ttf_path}
# Variants are listed in logical order (lightest to heaviest, then italic),
# followed by SemiCondensed variants with the same ordering.
# Excluded across all families: Thin, ExtraBold, Black, ExtraCondensed, Condensed.
BUNDLED_FONTS: dict = {
    "IBM Plex Sans": {
        "Light":                   "IBM_Plex_Sans/static/IBMPlexSans-Light.ttf",
        "Regular":                 "IBM_Plex_Sans/static/IBMPlexSans-Regular.ttf",
        "Medium":                  "IBM_Plex_Sans/static/IBMPlexSans-Medium.ttf",
        "SemiBold":                "IBM_Plex_Sans/static/IBMPlexSans-SemiBold.ttf",
        "Bold":                    "IBM_Plex_Sans/static/IBMPlexSans-Bold.ttf",
        "Light Italic":            "IBM_Plex_Sans/static/IBMPlexSans-LightItalic.ttf",
        "Italic":                  "IBM_Plex_Sans/static/IBMPlexSans-Italic.ttf",
        "Medium Italic":           "IBM_Plex_Sans/static/IBMPlexSans-MediumItalic.ttf",
        "SemiBold Italic":         "IBM_Plex_Sans/static/IBMPlexSans-SemiBoldItalic.ttf",
        "Bold Italic":             "IBM_Plex_Sans/static/IBMPlexSans-BoldItalic.ttf",
        "SemiCond Light":          "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-Light.ttf",
        "SemiCond Regular":        "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-Regular.ttf",
        "SemiCond Medium":         "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-Medium.ttf",
        "SemiCond SemiBold":       "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-SemiBold.ttf",
        "SemiCond Bold":           "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-Bold.ttf",
        "SemiCond Light Italic":   "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-LightItalic.ttf",
        "SemiCond Italic":         "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-Italic.ttf",
        "SemiCond Medium Italic":  "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-MediumItalic.ttf",
        "SemiCond SemiBold Italic": "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-SemiBoldItalic.ttf",
        "SemiCond Bold Italic":    "IBM_Plex_Sans/static/IBMPlexSans_SemiCondensed-BoldItalic.ttf",
    },
    "Noto Sans": {
        "Light":                   "Noto_Sans/static/NotoSans-Light.ttf",
        "Regular":                 "Noto_Sans/static/NotoSans-Regular.ttf",
        "Medium":                  "Noto_Sans/static/NotoSans-Medium.ttf",
        "SemiBold":                "Noto_Sans/static/NotoSans-SemiBold.ttf",
        "Bold":                    "Noto_Sans/static/NotoSans-Bold.ttf",
        "Light Italic":            "Noto_Sans/static/NotoSans-LightItalic.ttf",
        "Italic":                  "Noto_Sans/static/NotoSans-Italic.ttf",
        "Medium Italic":           "Noto_Sans/static/NotoSans-MediumItalic.ttf",
        "SemiBold Italic":         "Noto_Sans/static/NotoSans-SemiBoldItalic.ttf",
        "Bold Italic":             "Noto_Sans/static/NotoSans-BoldItalic.ttf",
        "SemiCond Light":          "Noto_Sans/static/NotoSans_SemiCondensed-Light.ttf",
        "SemiCond Regular":        "Noto_Sans/static/NotoSans_SemiCondensed-Regular.ttf",
        "SemiCond Medium":         "Noto_Sans/static/NotoSans_SemiCondensed-Medium.ttf",
        "SemiCond SemiBold":       "Noto_Sans/static/NotoSans_SemiCondensed-SemiBold.ttf",
        "SemiCond Bold":           "Noto_Sans/static/NotoSans_SemiCondensed-Bold.ttf",
        "SemiCond Light Italic":   "Noto_Sans/static/NotoSans_SemiCondensed-LightItalic.ttf",
        "SemiCond Italic":         "Noto_Sans/static/NotoSans_SemiCondensed-Italic.ttf",
        "SemiCond Medium Italic":  "Noto_Sans/static/NotoSans_SemiCondensed-MediumItalic.ttf",
        "SemiCond SemiBold Italic": "Noto_Sans/static/NotoSans_SemiCondensed-SemiBoldItalic.ttf",
        "SemiCond Bold Italic":    "Noto_Sans/static/NotoSans_SemiCondensed-BoldItalic.ttf",
    },
    "Noto Serif": {
        "Light":                   "Noto_Serif/static/NotoSerif-Light.ttf",
        "Regular":                 "Noto_Serif/static/NotoSerif-Regular.ttf",
        "Medium":                  "Noto_Serif/static/NotoSerif-Medium.ttf",
        "SemiBold":                "Noto_Serif/static/NotoSerif-SemiBold.ttf",
        "Bold":                    "Noto_Serif/static/NotoSerif-Bold.ttf",
        "Light Italic":            "Noto_Serif/static/NotoSerif-LightItalic.ttf",
        "Italic":                  "Noto_Serif/static/NotoSerif-Italic.ttf",
        "Medium Italic":           "Noto_Serif/static/NotoSerif-MediumItalic.ttf",
        "SemiBold Italic":         "Noto_Serif/static/NotoSerif-SemiBoldItalic.ttf",
        "Bold Italic":             "Noto_Serif/static/NotoSerif-BoldItalic.ttf",
        "SemiCond Light":          "Noto_Serif/static/NotoSerif_SemiCondensed-Light.ttf",
        "SemiCond Regular":        "Noto_Serif/static/NotoSerif_SemiCondensed-Regular.ttf",
        "SemiCond Medium":         "Noto_Serif/static/NotoSerif_SemiCondensed-Medium.ttf",
        "SemiCond SemiBold":       "Noto_Serif/static/NotoSerif_SemiCondensed-SemiBold.ttf",
        "SemiCond Bold":           "Noto_Serif/static/NotoSerif_SemiCondensed-Bold.ttf",
        "SemiCond Light Italic":   "Noto_Serif/static/NotoSerif_SemiCondensed-LightItalic.ttf",
        "SemiCond Italic":         "Noto_Serif/static/NotoSerif_SemiCondensed-Italic.ttf",
        "SemiCond Medium Italic":  "Noto_Serif/static/NotoSerif_SemiCondensed-MediumItalic.ttf",
        "SemiCond SemiBold Italic": "Noto_Serif/static/NotoSerif_SemiCondensed-SemiBoldItalic.ttf",
        "SemiCond Bold Italic":    "Noto_Serif/static/NotoSerif_SemiCondensed-BoldItalic.ttf",
    },
    "Open Sans": {
        "Light":                   "Open_Sans/static/OpenSans-Light.ttf",
        "Regular":                 "Open_Sans/static/OpenSans-Regular.ttf",
        "Medium":                  "Open_Sans/static/OpenSans-Medium.ttf",
        "SemiBold":                "Open_Sans/static/OpenSans-SemiBold.ttf",
        "Bold":                    "Open_Sans/static/OpenSans-Bold.ttf",
        "Light Italic":            "Open_Sans/static/OpenSans-LightItalic.ttf",
        "Italic":                  "Open_Sans/static/OpenSans-Italic.ttf",
        "Medium Italic":           "Open_Sans/static/OpenSans-MediumItalic.ttf",
        "SemiBold Italic":         "Open_Sans/static/OpenSans-SemiBoldItalic.ttf",
        "Bold Italic":             "Open_Sans/static/OpenSans-BoldItalic.ttf",
        "SemiCond Light":          "Open_Sans/static/OpenSans_SemiCondensed-Light.ttf",
        "SemiCond Regular":        "Open_Sans/static/OpenSans_SemiCondensed-Regular.ttf",
        "SemiCond Medium":         "Open_Sans/static/OpenSans_SemiCondensed-Medium.ttf",
        "SemiCond SemiBold":       "Open_Sans/static/OpenSans_SemiCondensed-SemiBold.ttf",
        "SemiCond Bold":           "Open_Sans/static/OpenSans_SemiCondensed-Bold.ttf",
        "SemiCond Light Italic":   "Open_Sans/static/OpenSans_SemiCondensed-LightItalic.ttf",
        "SemiCond Italic":         "Open_Sans/static/OpenSans_SemiCondensed-Italic.ttf",
        "SemiCond Medium Italic":  "Open_Sans/static/OpenSans_SemiCondensed-MediumItalic.ttf",
        "SemiCond SemiBold Italic": "Open_Sans/static/OpenSans_SemiCondensed-SemiBoldItalic.ttf",
        "SemiCond Bold Italic":    "Open_Sans/static/OpenSans_SemiCondensed-BoldItalic.ttf",
    },
    "Liberation Sans": {
        "Regular":     "liberation_sans/LiberationSans-Regular.ttf",
        "Bold":        "liberation_sans/LiberationSans-Bold.ttf",
        "Italic":      "liberation_sans/LiberationSans-Italic.ttf",
        "Bold Italic": "liberation_sans/LiberationSans-BoldItalic.ttf",
    },
    "Raleway": {
        "Light":             "Raleway/static/Raleway-Light.ttf",
        "Regular":           "Raleway/static/Raleway-Regular.ttf",
        "Medium":            "Raleway/static/Raleway-Medium.ttf",
        "SemiBold":          "Raleway/static/Raleway-SemiBold.ttf",
        "Bold":              "Raleway/static/Raleway-Bold.ttf",
        "Light Italic":      "Raleway/static/Raleway-LightItalic.ttf",
        "Italic":            "Raleway/static/Raleway-Italic.ttf",
        "Medium Italic":     "Raleway/static/Raleway-MediumItalic.ttf",
        "SemiBold Italic":   "Raleway/static/Raleway-SemiBoldItalic.ttf",
        "Bold Italic":       "Raleway/static/Raleway-BoldItalic.ttf",
    },
    "Red Hat Text": {
        "Light":           "Red_Hat_Text/static/RedHatText-Light.ttf",
        "Regular":         "Red_Hat_Text/static/RedHatText-Regular.ttf",
        "Medium":          "Red_Hat_Text/static/RedHatText-Medium.ttf",
        "SemiBold":        "Red_Hat_Text/static/RedHatText-SemiBold.ttf",
        "Bold":            "Red_Hat_Text/static/RedHatText-Bold.ttf",
        "Light Italic":    "Red_Hat_Text/static/RedHatText-LightItalic.ttf",
        "Italic":          "Red_Hat_Text/static/RedHatText-Italic.ttf",
        "Medium Italic":   "Red_Hat_Text/static/RedHatText-MediumItalic.ttf",
        "SemiBold Italic": "Red_Hat_Text/static/RedHatText-SemiBoldItalic.ttf",
        "Bold Italic":     "Red_Hat_Text/static/RedHatText-BoldItalic.ttf",
    },
    "Spectral": {
        "Light":             "Spectral/Spectral-Light.ttf",
        "Regular":           "Spectral/Spectral-Regular.ttf",
        "Medium":            "Spectral/Spectral-Medium.ttf",
        "SemiBold":          "Spectral/Spectral-SemiBold.ttf",
        "Bold":              "Spectral/Spectral-Bold.ttf",
        "Light Italic":      "Spectral/Spectral-LightItalic.ttf",
        "Italic":            "Spectral/Spectral-Italic.ttf",
        "Medium Italic":     "Spectral/Spectral-MediumItalic.ttf",
        "SemiBold Italic":   "Spectral/Spectral-SemiBoldItalic.ttf",
        "Bold Italic":       "Spectral/Spectral-BoldItalic.ttf",
    },
    "DejaVu Sans": {
        "Regular": "DejaVuSans.ttf",
        "Bold":    "DejaVuSans-Bold.ttf",
    },
}

DEFAULT_FONT_FAMILY = "IBM Plex Sans"
DEFAULT_FONT_VARIANT = "Bold"

# Maps a bundled family name to the Qt-registered family name for its
# SemiCondensed width.  Used by make_qfont for "SemiCond ..." variants.
_SEMICOND_QT_FAMILY: dict = {
    "IBM Plex Sans": "IBM Plex Sans SemiCondensed",
    "Noto Sans":     "Noto Sans SemiCondensed",
    "Noto Serif":    "Noto Serif SemiCondensed",
    "Open Sans":     "Open Sans SemiCondensed",
}

# Maps variant display name → (Qt weight int, is_italic bool).
# Qt weight values: Thin=100, ExtraLight=200, Light=300, Regular=400,
#                   Medium=500, SemiBold=600, Bold=700, ExtraBold=800, Black=900
# "SemiCond ..." variant names are resolved by stripping the prefix first.
_VARIANT_ATTRS: dict = {
    "Thin":              (100, False),
    "ExtraLight":        (200, False),
    "Light":             (300, False),
    "Regular":           (400, False),
    "Medium":            (500, False),
    "SemiBold":          (600, False),
    "Bold":              (700, False),
    "ExtraBold":         (800, False),
    "Black":             (900, False),
    "Thin Italic":       (100, True),
    "ExtraLight Italic": (200, True),
    "Light Italic":      (300, True),
    "Italic":            (400, True),
    "Medium Italic":     (500, True),
    "SemiBold Italic":   (600, True),
    "Bold Italic":       (700, True),
    "ExtraBold Italic":  (800, True),
    "Black Italic":      (900, True),
}


def _fonts_dir() -> Path:
    """Return the absolute path to resources/fonts/, works in dev and PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "resources" / "fonts"
    return Path(__file__).parent.parent.parent / "resources" / "fonts"


def get_font_families() -> list:
    """Return the ordered list of available bundled font family names."""
    return list(BUNDLED_FONTS.keys())


def get_font_variants(family: str) -> list:
    """Return the ordered list of variant names available for *family*.

    Falls back to DEFAULT_FONT_FAMILY if *family* is unknown.
    """
    return list(BUNDLED_FONTS.get(family, BUNDLED_FONTS[DEFAULT_FONT_FAMILY]).keys())


def resolve_font(family: str, variant: str = DEFAULT_FONT_VARIANT) -> tuple:
    """Return *(family, variant)* ensuring both are valid, with graceful fallback.

    - Unknown *family* falls back to DEFAULT_FONT_FAMILY.
    - Unknown *variant* falls back to "Bold" → "Regular" → first available.
    """
    if family not in BUNDLED_FONTS:
        family = DEFAULT_FONT_FAMILY
    variants = BUNDLED_FONTS[family]
    if variant not in variants:
        if "Bold" in variants:
            variant = "Bold"
        elif "Regular" in variants:
            variant = "Regular"
        else:
            variant = next(iter(variants))
    return family, variant


def get_bundled_ttf_path(family: str, variant: str = DEFAULT_FONT_VARIANT) -> str:
    """Return the absolute path to the TTF for *family* + *variant*.

    Uses :func:`resolve_font` so unknown families/variants always return a
    valid path.
    """
    family, variant = resolve_font(family, variant)
    return str(_fonts_dir() / BUNDLED_FONTS[family][variant])


def get_variant_weight_italic(variant: str) -> tuple:
    """Return *(qt_weight_int, is_italic)* for a variant display name.

    "SemiCond ..." variants are resolved by stripping the prefix.
    Falls back to (700, False) – Bold – for unknown variants.
    """
    lookup = variant[len("SemiCond "):] if variant.startswith("SemiCond ") else variant
    return _VARIANT_ATTRS.get(lookup, (700, False))


def make_qfont(family: str, variant: str, size: int):
    """Create a :class:`PySide6.QtGui.QFont` for *family*, *variant*, *size*.

    Uses :func:`resolve_font` so invalid combinations fall back gracefully.
    All bundled TTFs are registered at startup via :func:`register_fonts_with_qt`,
    so Qt can honour weight/italic requests.
    """
    from PySide6.QtGui import QFont
    family, variant = resolve_font(family, variant)
    weight, italic = get_variant_weight_italic(variant)
    # SemiCondensed TTFs register under a different Qt family name.
    if variant.startswith("SemiCond "):
        qt_family = _SEMICOND_QT_FAMILY.get(family, family)
    else:
        qt_family = family
    font = QFont(qt_family, size)
    font.setWeight(QFont.Weight(weight))
    font.setItalic(italic)
    return font


def register_fonts_with_qt() -> None:
    """Register all bundled TrueType font variants with Qt's QFontDatabase.

    Must be called after a QApplication exists and before any font-dependent
    widget is shown.  Safe to call multiple times (Qt deduplicates).
    """
    try:
        from PySide6.QtGui import QFontDatabase
        fonts_dir = _fonts_dir()
        for family, variants in BUNDLED_FONTS.items():
            for variant, relative in variants.items():
                path = fonts_dir / relative
                if path.exists():
                    QFontDatabase.addApplicationFont(str(path))
    except Exception:
        pass
