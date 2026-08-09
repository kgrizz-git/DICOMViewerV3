"""
Main-window toast overlay — ephemeral banner messages (refactor Stream C).

Extracted from ``gui/main_window.py`` so the window stays a layout + signal
surface, mirroring ``main_window_status_controller`` and the menu/toolbar builders.

The controller owns the QLabel overlay, opacity effect, dismiss timer, and
fade animation. ``MainWindow.show_toast_message`` remains the public entry point
and delegates here.
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QWidget


class MainWindowToastController:
    """Owns ephemeral toast/banner overlays on the main window."""

    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._toast_label: QLabel | None = None
        self._toast_effect: QGraphicsOpacityEffect | None = None
        self._toast_timer: QTimer | None = None
        self._toast_animation: QPropertyAnimation | None = None

    @property
    def label(self) -> QLabel | None:
        """Current toast QLabel, or None when no toast is visible."""
        return self._toast_label

    def show(
        self,
        message: str,
        timeout_ms: int = 5000,
        *,
        position: Literal["bottom-center", "center", "top-center"] = "top-center",
        bg_alpha: float = 0.75,
        severity: Literal["info", "warning", "error", "success"] = "info",
    ) -> None:
        """Show a temporary toast/banner message over the parent window.

        Auto-dismisses after ``timeout_ms``, then fades out over 300 ms.

        Args:
            message: Text to display.
            timeout_ms: Time in milliseconds before starting fade-out (default 5000).
            position: ``top-center`` (default), ``bottom-center``, or ``center`` of
                the parent client area (widget coordinates).
                ``top-center`` positions the toast just below the menu bar and toolbar.
            bg_alpha: Background opacity for the toast panel, clamped to [0.0, 1.0].
            severity: ``info`` (default), ``warning``, ``error``, or ``success``.
                Controls the left-border color and icon prefix.
        """
        _severity_map = {
            "info": ("#4285da", "ℹ"),
            "warning": ("#d68910", "⚠"),
            "error": ("#c0392b", "✕"),
            "success": ("#27ae60", "✓"),
        }
        border_color, icon = _severity_map.get(severity, _severity_map["info"])
        display_message = f"{icon}  {message}"

        if self._toast_timer is not None and self._toast_timer.isActive():
            self._toast_timer.stop()
        if self._toast_label is not None:
            self._toast_label.deleteLater()
        alpha = max(0.0, min(1.0, float(bg_alpha)))
        label = QLabel(display_message, self._parent)
        label.setStyleSheet(
            f"background-color: rgba(0, 0, 0, {alpha}); color: white; padding: 12px 22px; "
            f"border-radius: 8px; border-left: 5px solid {border_color}; "
            f"font-size: 14px; font-weight: 500;"
        )
        label.setWordWrap(True)
        label.setMinimumWidth(360)
        label.setMaximumWidth(640)
        label.adjustSize()
        effect = QGraphicsOpacityEffect(label)
        label.setGraphicsEffect(effect)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        x = (self._parent.width() - label.width()) // 2
        if position == "center":
            y = (self._parent.height() - label.height()) // 2
        elif position == "top-center":
            cw = self._parent.centralWidget()
            y = (cw.y() + 12) if cw is not None else 80
        else:
            y = self._parent.height() - 100
        label.setGeometry(max(0, x), max(0, y), label.width(), label.height())
        label.show()
        label.raise_()
        self._toast_label = label
        self._toast_effect = effect

        def start_fade() -> None:
            self._toast_timer = None  # single-shot fired; allow new toasts to schedule again
            anim = QPropertyAnimation(effect, b"opacity")
            anim.setDuration(300)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.finished.connect(
                lambda: (label.deleteLater(), setattr(self, "_toast_label", None))
            )
            anim.start()
            self._toast_animation = anim

        self._toast_timer = QTimer(self._parent)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(start_fade)
        self._toast_timer.start(timeout_ms)
