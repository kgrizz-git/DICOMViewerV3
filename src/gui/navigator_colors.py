"""
Shared color definitions for navigator and window-slot map indicators.

This module centralizes the per-subwindow slot colors used for the small
colored dots that indicate which window slots (0–3) are associated with
a given series or thumbnail.
"""

from typing import Dict


# Colored dot per open subwindow slot: blue, green, orange, magenta
SUBWINDOW_DOT_COLORS: Dict[int, str] = {
    0: "#2196F3",  # blue
    1: "#4CAF50",  # green
    2: "#FF9800",  # orange
    3: "#E91E63",  # magenta
}

