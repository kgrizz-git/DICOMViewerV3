"""
Name the active LUT in a corner of each image pane.

The label shows only when the pane's LUT is not the default Linear ramp, or
when "From DICOM" is on, and only while **View → Show LUT Label** is checked
(``ConfigManager.get_show_lut_label``). In privacy mode a user-named LUT reads
"Custom", because a saved name is free text and could hold an identifier.

The label is a small ``QLabel`` on the viewer's viewport. It refreshes when
the viewport repaints or resizes, so every redisplay path keeps it current
without the display code knowing about it.

Inputs:
    - An image viewer with ``current_series_lut`` and ``dicom_lut_state``
    - Callables for the show-label setting and privacy mode

Outputs:
    - A label positioned at the top center of the viewport

Requirements:
    - PySide6
    - core.lut_engine
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from typing import Any, ClassVar

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QLabel, QWidget

from core.lut_engine import LookUpTable, linear_transfer

_MARGIN = 6


def lut_label_text(lut: LookUpTable | None, voi_from_dicom: bool, privacy: bool) -> str:
    """Label text, or ``""`` when the pane shows plain window/level with Linear."""
    parts: list[str] = []
    if voi_from_dicom:
        parts.append("VOI LUT: DICOM")
    if lut is not None and not _is_default(lut):
        name = "Custom" if privacy and lut.source == "custom" else lut.name
        parts.append(f"LUT: {name}")
    return "  ·  ".join(parts)


def _is_default(lut: LookUpTable) -> bool:
    return (
        lut.lut_type == "grayscale_ramp"
        and lut.control_points is None
        and lut.transfer_fn in (None, linear_transfer)
    )


class LutPaneLabel(QObject):
    """Owns the label on one viewer's viewport. Refreshes on paint and resize."""

    _instances: ClassVar[weakref.WeakSet[LutPaneLabel]] = weakref.WeakSet()

    def __init__(
        self,
        viewer: Any,
        show_label: Callable[[], bool],
        privacy: Callable[[], bool],
    ) -> None:
        viewport = viewer.viewport()
        super().__init__(viewport)
        self._viewer = viewer
        self._show_label = show_label
        self._privacy = privacy
        self.label = QLabel(viewport)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.label.setStyleSheet(
            "color: #f0f0f0; background-color: rgba(0, 0, 0, 140);"
            " padding: 1px 6px; border-radius: 3px;"
        )
        self.label.hide()
        viewport.installEventFilter(self)
        LutPaneLabel._instances.add(self)

    @classmethod
    def refresh_all(cls) -> None:
        """Re-read every pane, for example after the View-menu toggle."""
        for instance in cls._instances:
            instance.refresh()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Refresh on the viewport's paint and resize; never consume the event."""
        if event.type() in (QEvent.Type.Paint, QEvent.Type.Resize):
            self.refresh()
        return super().eventFilter(watched, event)

    def refresh(self) -> None:
        """Update the text, visibility, and position from the pane's current state."""
        text = self.current_text()
        if not text:
            if self.label.isVisible():
                self.label.hide()
            return
        if self.label.text() != text:
            self.label.setText(text)
            self.label.adjustSize()
        parent = self.label.parentWidget()
        if isinstance(parent, QWidget):
            x = max(_MARGIN, (parent.width() - self.label.width()) // 2)
            self.label.move(x, _MARGIN)
        if not self.label.isVisible():
            self.label.show()

    def current_text(self) -> str:
        """The text the label should show now, ``""`` when hidden."""
        if not self._show_label():
            return ""
        getter = getattr(self._viewer, "current_series_lut", None)
        lut = getter() if callable(getter) else None
        state = getattr(self._viewer, "dicom_lut_state", None)
        found = state() if callable(state) else None
        # Only claim DICOM when it actually applied: asked for and supported.
        enabled = bool(found[0] and found[1]) if isinstance(found, tuple) and len(found) == 2 else False
        return lut_label_text(lut if isinstance(lut, LookUpTable) else None, enabled, self._privacy())
