"""
GUI style constants shared across widgets.

Provides centralized QColor definitions for focus borders and other
reusable visual accents so that changes stay consistent across the UI.

Requirements:
    - PySide6 for QColor
"""

from PySide6.QtGui import QColor


# Light-blue focus border color used for the active image subwindow and any
# other widgets that need to visually match that highlight (e.g. layout map).
FOCUS_BORDER_COLOR = QColor(0, 170, 255)

