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
    accepted: bool = False

    def modifiers(self) -> Qt.KeyboardModifier:
        return self.modifier

    def angleDelta(self) -> QPoint:
        return QPoint(0, self.delta_y)

    def accept(self) -> None:
        self.accepted = True


@pytest.mark.qt
@pytest.mark.parametrize(
    "modifier",
    [Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.MetaModifier],
)
def test_primary_modifier_wheel_adjusts_overlay_font_size(qapp, modifier) -> None:
    viewer = ImageViewer()
    changes: list[int] = []
    viewer.overlay_font_size_adjust_requested.connect(changes.append)

    up = _WheelEvent(120, modifier)
    down = _WheelEvent(-120, modifier)
    viewer.wheelEvent(up)  # type: ignore[arg-type]
    viewer.wheelEvent(down)  # type: ignore[arg-type]

    assert changes == [1, -1]
    assert up.accepted and down.accepted
