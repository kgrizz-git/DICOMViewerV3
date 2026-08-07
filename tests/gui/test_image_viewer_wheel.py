"""Focused wheel-gesture checks for image-viewer input routing."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from PySide6.QtCore import QPoint, Qt

from gui.image_viewer import ImageViewer


@dataclass
class _WheelEvent:
    """Minimal wheel-event stand-in for the input mixin's public contract."""

    delta_y: int
    modifier: Qt.KeyboardModifier
    delta_x: int = 0
    accepted: bool = False

    def modifiers(self) -> Qt.KeyboardModifier:
        return self.modifier

    def angleDelta(self) -> QPoint:
        return QPoint(self.delta_x, self.delta_y)

    def accept(self) -> None:
        self.accepted = True


@pytest.mark.qt
def test_shift_wheel_adjusts_overlay_font_size(qapp) -> None:
    viewer = ImageViewer()
    changes: list[int] = []
    viewer.overlay_font_size_adjust_requested.connect(changes.append)

    up = _WheelEvent(120, Qt.KeyboardModifier.ShiftModifier)
    down = _WheelEvent(-120, Qt.KeyboardModifier.ShiftModifier)
    viewer.wheelEvent(up)  # type: ignore[arg-type]
    viewer.wheelEvent(down)  # type: ignore[arg-type]

    assert changes == [1, -1]
    assert up.accepted and down.accepted


def test_shift_horizontal_wheel_adjusts_overlay_font_size(qapp) -> None:
    viewer = ImageViewer()
    changes: list[int] = []
    viewer.overlay_font_size_adjust_requested.connect(changes.append)

    horizontal = _WheelEvent(0, Qt.KeyboardModifier.ShiftModifier, delta_x=120)
    viewer.wheelEvent(horizontal)  # type: ignore[arg-type]

    assert changes == [1]
    assert horizontal.accepted


def test_control_wheel_remains_zoom_for_trackpad_pinch_compatibility(qapp, monkeypatch) -> None:
    viewer = ImageViewer()
    changes: list[int] = []
    zoom_events: list[str] = []
    viewer.overlay_font_size_adjust_requested.connect(changes.append)
    monkeypatch.setattr(viewer, "zoom_in", lambda: zoom_events.append("in"))
    monkeypatch.setattr(viewer, "zoom_out", lambda: zoom_events.append("out"))

    up = _WheelEvent(120, Qt.KeyboardModifier.ControlModifier)
    down = _WheelEvent(-120, Qt.KeyboardModifier.ControlModifier)
    viewer.wheelEvent(up)  # type: ignore[arg-type]
    viewer.wheelEvent(down)  # type: ignore[arg-type]

    assert zoom_events == ["in", "out"]
    assert changes == []
    assert up.accepted and down.accepted


def test_meta_wheel_keeps_normal_slice_navigation(qapp) -> None:
    viewer = ImageViewer()
    viewer.scroll_wheel_mode = "slice"
    changes: list[int] = []
    slices: list[int] = []
    viewer.overlay_font_size_adjust_requested.connect(changes.append)
    viewer.wheel_event_for_slice.connect(slices.append)

    event = _WheelEvent(120, Qt.KeyboardModifier.MetaModifier)
    viewer.wheelEvent(event)  # type: ignore[arg-type]

    assert changes == []
    assert slices == [120]
    assert event.accepted
