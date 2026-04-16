"""
Bottom overlay for image panes with no pixel data (e.g. Structured Report).

Shows a short hint and **Open structured report…**, which opens the **radiation dose summary**
when the file is a recognized dose SR, otherwise the **DICOM tag** viewer (modeless), until a
full SR tree browser exists.

Inputs:
    - Parent: ``ImageViewer.viewport()`` (viewport-local coordinates).
    - ``configure(active, show_button, open_callback)`` — ``open_callback`` invoked
      with no arguments; caller should close over the target dataset.

Outputs:
    - Visible bar at bottom of viewport when active.

Requirements: PySide6.
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class NoPixelPlaceholderOverlay(QWidget):
    """Thin bottom bar: hint + button to open dose summary or tag viewer for SR without pixels."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._open_cb: Optional[Callable[[], None]] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        self._hint = QLabel(
            "Structured Report — no pixel image. Use the button for the SR browser (document tree, "
            "dose events, summary) or the flat tag list; Tools → Structured Report… matches this action."
        )
        self._hint.setWordWrap(True)
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet("color: white; background: rgba(0,0,0,140); padding: 6px; border-radius: 4px;")
        outer.addWidget(self._hint)

        row = QHBoxLayout()
        row.addStretch()
        self._btn = QPushButton("Open structured report…")
        self._btn.setStyleSheet(
            "QPushButton { padding: 6px 14px; font-weight: bold; }"
        )
        self._btn.clicked.connect(self._on_open_clicked)
        row.addWidget(self._btn)
        row.addStretch()
        outer.addLayout(row)

        self.setVisible(False)

    def configure(
        self,
        *,
        active: bool,
        show_open_button: bool,
        open_callback: Optional[Callable[[], None]],
    ) -> None:
        self._open_cb = (
            open_callback if (active and show_open_button and open_callback is not None) else None
        )
        self._btn.setVisible(bool(active and show_open_button and open_callback is not None))
        self.setVisible(bool(active))

    def _on_open_clicked(self) -> None:
        if self._open_cb is not None:
            self._open_cb()
