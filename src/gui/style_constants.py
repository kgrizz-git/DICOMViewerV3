"""
GUI style constants shared across widgets.

Provides centralized QColor helpers for focus borders and other reusable
visual accents so that changes stay consistent across the UI.

Requirements:
    - PySide6 for QColor
    - gui.accent_presets for ACCENT_PRESETS / DEFAULT_ACCENT_ID
"""

from PySide6.QtGui import QColor

from gui.accent_presets import get_preset


def get_focus_border_color(accent_id: str) -> QColor:
    """Return the focus-border QColor for *accent_id*.

    Falls back to the default preset when *accent_id* is unknown.
    """
    return QColor(get_preset(accent_id).accent)

