"""
Shared color definitions for navigator and window-slot map indicators.

Per **grid slot** index 0–3 (2×2: 0=top-left, 1=top-right, 2=bottom-left,
3=bottom-right). **Display numbers** shown in the UI are 1–4 (``slot + 1``).

Colors tint the small slot **digits** on series thumbnails, MPR thumbnails,
and the window assignment map (same legend as slice-location lines).
"""

from typing import Dict


# Color per slot for digit / legend (Material-style hues)
SUBWINDOW_DOT_COLORS: Dict[int, str] = {
    0: "#2196F3",  # blue — window 1 (top-left)
    1: "#4CAF50",  # green — window 2 (top-right)
    2: "#FF9800",  # orange — window 3 (bottom-left)
    3: "#E91E63",  # magenta — window 4 (bottom-right)
}


def subwindow_slot_display_number(slot_index: int) -> str:
    """Return the user-visible window number (``'1'``…``'4'``) for slot ``0``…``3``."""
    if 0 <= slot_index <= 3:
        return str(slot_index + 1)
    return "?"

