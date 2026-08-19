"""
Main Window Theme – stylesheet and viewer background for light/dark themes.

Provides stylesheet strings and viewer background color for MainWindow theme switching.
Used by gui.main_window.MainWindow._apply_theme(); no dependency on MainWindow or config.

Purpose:
    - Return stylesheet for a given theme name
    - Return image viewer background QColor for a given theme

Inputs:
    - theme: "light" or "dark"
    - (for get_theme_stylesheet) checkmark image paths for checkbox icons

Outputs:
    - Stylesheet string for QApplication.setStyleSheet
    - QColor for image viewer background

Requirements:
    - PySide6.QtGui.QColor
"""

import sys
from colorsys import hsv_to_rgb, rgb_to_hsv
from pathlib import Path

from PySide6.QtGui import QColor


def _blend_hex_colors(base: str, tint: str, tint_fraction: float) -> str:
    """Return *base* with a restrained amount of *tint* mixed in."""
    base_rgb = tuple(int(base[index : index + 2], 16) for index in (1, 3, 5))
    tint_rgb = tuple(int(tint[index : index + 2], 16) for index in (1, 3, 5))
    fraction = max(0.0, min(1.0, tint_fraction))
    mixed = tuple(
        round(base_channel * (1.0 - fraction) + tint_channel * fraction)
        for base_channel, tint_channel in zip(base_rgb, tint_rgb, strict=True)
    )
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def _boost_hex_saturation(color: str, factor: float) -> str:
    """Scale a tint's chroma without changing its value (factor < 1 desaturates)."""
    red, green, blue = (int(color[index : index + 2], 16) / 255 for index in (1, 3, 5))
    hue, saturation, value = rgb_to_hsv(red, green, blue)
    saturated = hsv_to_rgb(hue, min(1.0, saturation * factor), value)
    return "#" + "".join(f"{round(channel * 255):02x}" for channel in saturated)


def metadata_tag_band_color(theme: str, accent: str) -> str:
    """Return a grey-leaning, accent-hued alternate-row color for metadata tags.

    The selected accent still shifts the stripe hue; chroma is kept lower than a
    raw mix so bands stay faint in both themes.
    """
    if theme == "dark":
        return _blend_hex_colors("#141414", accent, 0.045)
    mixed = _blend_hex_colors("#ffffff", accent, 0.08)
    return _boost_hex_saturation(mixed, 0.72)


def metadata_tag_hover_color(theme: str, accent: str) -> str:
    """Tokenized hover wash for ``#metadata_tag_tree`` rows (not global tree grey)."""
    if theme == "dark":
        return _blend_hex_colors("#141414", accent, 0.12)
    return _blend_hex_colors("#ffffff", accent, 0.14)


def metadata_tag_selection_color(theme: str, accent: str) -> str:
    """Low-contrast selection fill for metadata tag rows (readable on stripe rows)."""
    if theme == "dark":
        return _boost_hex_saturation(_blend_hex_colors("#141414", accent, 0.28), 1.12)
    return _blend_hex_colors("#ffffff", accent, 0.22)


def metadata_tag_selection_fg_color(theme: str) -> str:
    """Foreground on the low-contrast metadata selection fill (not white-on-pale)."""
    if theme == "dark":
        return "#e0e0e0"
    return "#000000"


def _themes_dir() -> Path:
    """
    Resolve resources/themes for dev and frozen PyInstaller builds.

    In a frozen bundle, resources are unpacked under ``sys._MEIPASS``.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass is not None:
            return Path(str(meipass)) / "resources" / "themes"
    return Path(__file__).parent.parent.parent / "resources" / "themes"


def get_theme_stylesheet(
    theme: str,
    white_checkmark_path: str,
    black_checkmark_path: str,
    accent_id: str = "steel-blue",
) -> str:
    """
    Return the full application stylesheet for the given theme.

    Loads the QSS from ``resources/themes/{theme}.qss`` and substitutes the
    checkmark image paths and accent colour placeholders before returning.
    Missing theme files fall back to ``light.qss``; ``{metadata_tag_band}`` is
    derived from that *effective* resolved theme (``qss_file.stem``), not the
    originally requested name, so a dark request that lands on light QSS still
    gets a light-appropriate band tint.

    QSS placeholder tokens substituted:

    * ``{white_checkmark_path}`` / ``{black_checkmark_path}`` – checkbox icons
    * ``{accent}``        – primary accent hex (buttons, selection, slider fill)
    * ``{accent_light}``  – lighter accent (dark-theme hover states)
    * ``{accent_dark}``   – darker accent (light-theme hover/press states)
    * ``{accent_soft}``   – pale accent tint for readable light-theme rows
    * ``{accent_muted}``  – dark accent tint for readable dark-theme rows
    * ``{metadata_tag_band}`` – accent-hued, desaturated tint for metadata row bands
    * ``{metadata_tag_hover}`` – scoped metadata-tree hover wash
    * ``{metadata_tag_selection}`` – scoped metadata-tree selection fill
    * ``{metadata_tag_selection_fg}`` – scoped metadata-tree selection text

    Args:
        theme: ``"light"`` or ``"dark"``
        white_checkmark_path: URL/path for white checkbox checkmark image
        black_checkmark_path: URL/path for black checkbox checkmark image
        accent_id: Key into ``gui.accent_presets.ACCENT_PRESETS``; defaults to
            ``"steel-blue"`` (the shipped QSS values).

    Returns:
        Stylesheet string to pass to ``QApplication.instance().setStyleSheet()``.
        Empty string if neither the requested nor the light fallback QSS exists.
    """
    from gui.accent_presets import get_preset

    themes_dir = _themes_dir()
    qss_file = themes_dir / f"{theme}.qss"
    if not qss_file.exists():
        qss_file = themes_dir / "light.qss"
    if not qss_file.exists():
        # Keep startup resilient in mis-packaged bundles: log and continue unstyled.
        print("Warning: Theme stylesheet resources were not found.")
        return ""
    # Stem of the resolved file (may differ from *theme* after light.qss fallback).
    effective_theme = qss_file.stem
    preset = get_preset(accent_id)
    metadata_tag_band = metadata_tag_band_color(effective_theme, preset.accent)
    metadata_tag_hover = metadata_tag_hover_color(effective_theme, preset.accent)
    metadata_tag_selection = metadata_tag_selection_color(effective_theme, preset.accent)
    metadata_tag_selection_fg = metadata_tag_selection_fg_color(effective_theme)
    stylesheet = qss_file.read_text(encoding="utf-8")
    return (
        stylesheet
        .replace("{white_checkmark_path}", white_checkmark_path)
        .replace("{black_checkmark_path}", black_checkmark_path)
        .replace("{accent}", preset.accent)
        .replace("{accent_light}", preset.accent_light)
        .replace("{accent_dark}", preset.accent_dark)
        .replace("{accent_soft}", preset.accent_soft)
        .replace("{accent_muted}", preset.accent_muted)
        .replace("{metadata_tag_band}", metadata_tag_band)
        .replace("{metadata_tag_hover}", metadata_tag_hover)
        .replace("{metadata_tag_selection}", metadata_tag_selection)
        .replace("{metadata_tag_selection_fg}", metadata_tag_selection_fg)
    )


def get_theme_viewer_background_color(theme: str) -> QColor:
    """
    Return the image viewer background color for the given theme.

    Args:
        theme: "light" or "dark"

    Returns:
        QColor for ImageViewer.set_background_color()
    """
    _ = theme  # reserved for theme-specific backgrounds
    # Letterbox around the image: keep the same near-black frame in both themes.
    return QColor(14, 14, 14)  # #0e0e0e
