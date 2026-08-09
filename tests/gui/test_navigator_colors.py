"""
Unit tests for src/gui/navigator_colors.py.

Achieves 100% statement and branch coverage for navigator_colors.
"""

from gui.navigator_colors import SUBWINDOW_DOT_COLORS, subwindow_slot_display_number


def test_subwindow_dot_colors_dict() -> None:
    """Test dictionary mapping slot indices to hex color strings."""
    assert SUBWINDOW_DOT_COLORS[0] == "#2196F3"
    assert SUBWINDOW_DOT_COLORS[1] == "#4CAF50"
    assert SUBWINDOW_DOT_COLORS[2] == "#FF9800"
    assert SUBWINDOW_DOT_COLORS[3] == "#E91E63"
    assert len(SUBWINDOW_DOT_COLORS) == 4


def test_subwindow_slot_display_number() -> None:
    """Test mapping slot indices 0-3 to display strings '1'-'4' and out-of-bounds fallback '?'."""
    assert subwindow_slot_display_number(0) == "1"
    assert subwindow_slot_display_number(1) == "2"
    assert subwindow_slot_display_number(2) == "3"
    assert subwindow_slot_display_number(3) == "4"

    # Out of bounds (< 0 or > 3)
    assert subwindow_slot_display_number(-1) == "?"
    assert subwindow_slot_display_number(4) == "?"
    assert subwindow_slot_display_number(100) == "?"
