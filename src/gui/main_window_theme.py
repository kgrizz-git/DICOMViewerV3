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
from pathlib import Path

from PySide6.QtGui import QColor


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

    QSS placeholder tokens substituted:

    * ``{white_checkmark_path}`` / ``{black_checkmark_path}`` – checkbox icons
    * ``{accent}``        – primary accent hex (buttons, selection, slider fill)
    * ``{accent_light}``  – lighter accent (dark-theme hover states)
    * ``{accent_dark}``   – darker accent (light-theme hover/press states)
    * ``{accent_soft}``   – pale accent tint for readable light-theme rows
    * ``{accent_muted}``  – dark accent tint for readable dark-theme rows

    Args:
        theme: ``"light"`` or ``"dark"``
        white_checkmark_path: URL/path for white checkbox checkmark image
        black_checkmark_path: URL/path for black checkbox checkmark image
        accent_id: Key into ``gui.accent_presets.ACCENT_PRESETS``; defaults to
            ``"steel-blue"`` (the shipped QSS values).

    Returns:
        Stylesheet string to pass to ``QApplication.instance().setStyleSheet()``.
    """
    from gui.accent_presets import get_preset

    themes_dir = _themes_dir()
    qss_file = themes_dir / f"{theme}.qss"
    if not qss_file.exists():
        qss_file = themes_dir / "light.qss"
    if not qss_file.exists():
        # Keep startup resilient in mis-packaged bundles: log and continue unstyled.
        print(
            "Warning: Theme stylesheet not found. "
            f"Searched in '{themes_dir}' for '{theme}.qss' and 'light.qss'."
        )
        return ""
    preset = get_preset(accent_id)
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
    )


def get_theme_viewer_background_color(theme: str) -> QColor:
    """
    Return the image viewer background color for the given theme.

    Args:
        theme: "light" or "dark"

    Returns:
        QColor for ImageViewer.set_background_color()
    """
    # Letterbox around the image: keep the same near-black frame in both themes.
    return QColor(14, 14, 14)  # #0e0e0e
