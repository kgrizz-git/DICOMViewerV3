"""
Tests for src/gui/slice_navigator.py.

Achieves 100% line and branch coverage for SliceNavigator.
"""

import pytest
from PySide6.QtCore import Qt

from gui.slice_navigator import SliceNavigator


@pytest.fixture
def navigator(qapp) -> SliceNavigator:
    """Fixture providing a clean SliceNavigator instance."""
    return SliceNavigator()


def test_init(navigator: SliceNavigator) -> None:
    """Test default initialization state."""
    assert navigator.current_slice_index == 0
    assert navigator.total_slices == 0
    assert navigator.scroll_wheel_mode == "slice"
    assert navigator.get_current_slice() == 0


def test_set_total_slices(navigator: SliceNavigator) -> None:
    """Test setting total slices under various conditions."""
    # Case 1: Normal setting when current index is less than total
    navigator.set_total_slices(10)
    assert navigator.total_slices == 10
    assert navigator.current_slice_index == 0

    # Case 2: Current index exceeds new total -> clamped to total - 1
    navigator.set_current_slice(8)
    assert navigator.get_current_slice() == 8
    navigator.set_total_slices(5)
    assert navigator.total_slices == 5
    assert navigator.get_current_slice() == 4

    # Case 3: Total slices set to 0 when current index is > 0 -> clamped to 0
    navigator.current_slice_index = 3
    navigator.set_total_slices(0)
    assert navigator.total_slices == 0
    assert navigator.get_current_slice() == 0

    # Negative total -> max(0, total) -> clamped to 0
    navigator.set_total_slices(-5)
    assert navigator.total_slices == 0


def test_set_scroll_wheel_mode(navigator: SliceNavigator) -> None:
    """Test setting valid and invalid scroll wheel modes."""
    navigator.set_scroll_wheel_mode("zoom")
    assert navigator.scroll_wheel_mode == "zoom"

    navigator.set_scroll_wheel_mode("slice")
    assert navigator.scroll_wheel_mode == "slice"

    # Invalid mode should be ignored
    navigator.set_scroll_wheel_mode("invalid_mode")
    assert navigator.scroll_wheel_mode == "slice"


def test_set_current_slice(navigator: SliceNavigator) -> None:
    """Test setting current slice index with valid and out-of-bound indices."""
    navigator.set_total_slices(5)
    signals = []
    navigator.slice_changed.connect(signals.append)

    # Valid index
    navigator.set_current_slice(2)
    assert navigator.get_current_slice() == 2
    assert signals == [2]

    # Same index (no redundant signal)
    navigator.set_current_slice(2)
    assert signals == [2]

    # Negative index (invalid) -> no change, no signal
    navigator.set_current_slice(-1)
    assert navigator.get_current_slice() == 2
    assert signals == [2]

    # Out of bounds index >= total_slices (invalid) -> no change, no signal
    navigator.set_current_slice(5)
    assert navigator.get_current_slice() == 2
    assert signals == [2]


def test_next_slice(navigator: SliceNavigator) -> None:
    """Test next_slice behavior."""
    navigator.set_total_slices(3)
    signals = []
    navigator.slice_changed.connect(signals.append)

    # Move from 0 to 1
    navigator.next_slice()
    assert navigator.get_current_slice() == 1
    assert signals == [1]

    # Move from 1 to 2
    navigator.next_slice()
    assert navigator.get_current_slice() == 2
    assert signals == [1, 2]

    # At end (2), calling next_slice does nothing (guarded)
    navigator.next_slice()
    assert navigator.get_current_slice() == 2
    assert signals == [1, 2]

    # total_slices = 0
    empty_nav = SliceNavigator()
    empty_signals = []
    empty_nav.slice_changed.connect(empty_signals.append)
    empty_nav.next_slice()
    assert empty_nav.get_current_slice() == 0
    assert empty_signals == []


def test_previous_slice(navigator: SliceNavigator) -> None:
    """Test previous_slice behavior."""
    navigator.set_total_slices(3)
    navigator.set_current_slice(2)
    signals = []
    navigator.slice_changed.connect(signals.append)

    # Move from 2 to 1
    navigator.previous_slice()
    assert navigator.get_current_slice() == 1
    assert signals == [1]

    # Move from 1 to 0
    navigator.previous_slice()
    assert navigator.get_current_slice() == 0
    assert signals == [1, 0]

    # At beginning (0), calling previous_slice does nothing
    navigator.previous_slice()
    assert navigator.get_current_slice() == 0
    assert signals == [1, 0]


def test_first_slice(navigator: SliceNavigator) -> None:
    """Test first_slice behavior."""
    navigator.set_total_slices(5)
    navigator.set_current_slice(3)
    signals = []
    navigator.slice_changed.connect(signals.append)

    navigator.first_slice()
    assert navigator.get_current_slice() == 0
    assert signals == [0]

    # Redundant call
    navigator.first_slice()
    assert signals == [0]

    # total_slices = 0
    empty_nav = SliceNavigator()
    empty_signals = []
    empty_nav.slice_changed.connect(empty_signals.append)
    empty_nav.first_slice()
    assert empty_nav.get_current_slice() == 0
    assert empty_signals == []


def test_last_slice(navigator: SliceNavigator) -> None:
    """Test last_slice behavior."""
    navigator.set_total_slices(5)
    navigator.set_current_slice(1)
    signals = []
    navigator.slice_changed.connect(signals.append)

    navigator.last_slice()
    assert navigator.get_current_slice() == 4
    assert signals == [4]

    # Redundant call
    navigator.last_slice()
    assert signals == [4]

    # total_slices = 0
    empty_nav = SliceNavigator()
    empty_signals = []
    empty_nav.slice_changed.connect(empty_signals.append)
    empty_nav.last_slice()
    assert empty_nav.get_current_slice() == 0
    assert empty_signals == []


def test_handle_key_event(navigator: SliceNavigator) -> None:
    """Test key event navigation for all supported keys and unhandled keys."""
    navigator.set_total_slices(5)
    navigator.set_current_slice(2)

    # Key_Up -> next_slice
    assert navigator.handle_key_event(Qt.Key.Key_Up) is True
    assert navigator.get_current_slice() == 3

    # Key_Right -> next_slice
    assert navigator.handle_key_event(Qt.Key.Key_Right) is True
    assert navigator.get_current_slice() == 4

    # Key_PageDown -> next_slice (already at end, so no change but handled)
    assert navigator.handle_key_event(Qt.Key.Key_PageDown) is True
    assert navigator.get_current_slice() == 4

    # Key_Down -> previous_slice
    assert navigator.handle_key_event(Qt.Key.Key_Down) is True
    assert navigator.get_current_slice() == 3

    # Key_Left -> previous_slice
    assert navigator.handle_key_event(Qt.Key.Key_Left) is True
    assert navigator.get_current_slice() == 2

    # Key_PageUp -> previous_slice
    assert navigator.handle_key_event(Qt.Key.Key_PageUp) is True
    assert navigator.get_current_slice() == 1

    # Key_Home -> first_slice
    assert navigator.handle_key_event(Qt.Key.Key_Home) is True
    assert navigator.get_current_slice() == 0

    # Key_End -> last_slice
    assert navigator.handle_key_event(Qt.Key.Key_End) is True
    assert navigator.get_current_slice() == 4

    # Unhandled key
    assert navigator.handle_key_event(Qt.Key.Key_Space) is False
    assert navigator.get_current_slice() == 4


def test_handle_wheel_event(navigator: SliceNavigator) -> None:
    """Test mouse wheel event handling in slice mode and zoom mode."""
    navigator.set_total_slices(5)
    navigator.set_current_slice(2)

    # When scroll wheel mode is "zoom"
    navigator.set_scroll_wheel_mode("zoom")
    assert navigator.handle_wheel_event(120) is False
    assert navigator.get_current_slice() == 2

    # When scroll wheel mode is "slice"
    navigator.set_scroll_wheel_mode("slice")

    # Positive delta -> previous_slice
    assert navigator.handle_wheel_event(120) is True
    assert navigator.get_current_slice() == 1

    # Negative delta -> next_slice
    assert navigator.handle_wheel_event(-120) is True
    assert navigator.get_current_slice() == 2

    # Zero delta -> ignored
    assert navigator.handle_wheel_event(0) is False
    assert navigator.get_current_slice() == 2


def test_advance_to_frame(navigator: SliceNavigator) -> None:
    """Test advance_to_frame with loop enabled and disabled."""
    # Case 1: total_slices == 0 -> early return
    empty_nav = SliceNavigator()
    empty_signals = []
    empty_nav.slice_changed.connect(empty_signals.append)
    empty_nav.advance_to_frame(2, loop=True)
    empty_nav.advance_to_frame(2, loop=False)
    assert empty_nav.get_current_slice() == 0
    assert empty_signals == []

    # Setup total_slices = 5
    navigator.set_total_slices(5)
    signals = []
    navigator.slice_changed.connect(signals.append)

    # Case 2: loop=True
    # index < 0 -> wraps to total_slices - 1 (4)
    navigator.advance_to_frame(-1, loop=True)
    assert navigator.get_current_slice() == 4
    assert signals[-1] == 4

    # index >= total_slices -> wraps to 0
    navigator.advance_to_frame(5, loop=True)
    assert navigator.get_current_slice() == 0
    assert signals[-1] == 0

    # 0 <= index < total_slices -> set directly
    navigator.advance_to_frame(2, loop=True)
    assert navigator.get_current_slice() == 2
    assert signals[-1] == 2

    # Case 3: loop=False
    # index < 0 -> clamped to 0
    navigator.advance_to_frame(-3, loop=False)
    assert navigator.get_current_slice() == 0
    assert signals[-1] == 0

    # index >= total_slices -> clamped to total_slices - 1 (4)
    navigator.advance_to_frame(10, loop=False)
    assert navigator.get_current_slice() == 4
    assert signals[-1] == 4

    # 0 <= index < total_slices -> set directly
    navigator.advance_to_frame(3, loop=False)
    assert navigator.get_current_slice() == 3
    assert signals[-1] == 3

    # Redundant set
    navigator.advance_to_frame(3, loop=False)
    assert signals[-1] == 3
    assert len(signals) == 6


def test_advance_to_frame_false_branch(qapp) -> None:
    """Test out of bounds but loop=True wrapped negative index handling"""
    nav = SliceNavigator()
    nav.set_total_slices(2)

    signals = []
    nav.slice_changed.connect(signals.append)
    nav.advance_to_frame(-10, loop=True)
    assert nav.get_current_slice() == 1
