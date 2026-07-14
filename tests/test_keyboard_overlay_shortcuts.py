"""
Targeted tests for overlay keyboard shortcuts.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from gui.keyboard_event_handler import KeyboardEventHandler


class _DummyScene:
    def selectedItems(self) -> list[object]:
        return []


class _DummyViewer:
    mouse_mode = "pan"
    scene = _DummyScene()


class _DummySliceNavigator:
    def next_slice(self) -> None:
        pass

    def previous_slice(self) -> None:
        pass


def _handler(calls: list[str]) -> KeyboardEventHandler:
    return KeyboardEventHandler(
        roi_manager=None,  # type: ignore[arg-type]
        measurement_tool=None,  # type: ignore[arg-type]
        slice_navigator=_DummySliceNavigator(),  # type: ignore[arg-type]
        overlay_manager=None,  # type: ignore[arg-type]
        image_viewer=_DummyViewer(),  # type: ignore[arg-type]
        set_mouse_mode=lambda _mode: None,
        delete_all_rois_callback=lambda: None,
        clear_measurements_callback=lambda: None,
        toggle_overlay_callback=lambda: calls.append("fallback"),
        get_selected_roi=lambda: None,
        delete_roi_callback=lambda _roi: None,
        delete_measurement_callback=lambda _measurement: None,
        cycle_overlay_detail_callback=lambda: calls.append("cycle-all-panes"),
        toggle_overlay_visibility_legacy_callback=lambda: calls.append("legacy-focused"),
    )


def test_space_cycles_overlay_detail_across_all_panes() -> None:
    calls: list[str] = []
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.NoModifier,
    )

    assert _handler(calls).handle_key_event(event)
    assert calls == ["cycle-all-panes"]


def test_shift_space_uses_legacy_focused_visibility_cycle() -> None:
    calls: list[str] = []
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.ShiftModifier,
    )

    assert _handler(calls).handle_key_event(event)
    assert calls == ["legacy-focused"]
