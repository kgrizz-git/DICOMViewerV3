"""The Phase 0 stacking tracer logs class names and never window titles."""

from __future__ import annotations

from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QWidget

from gui import window_stacking_debug as wsd


def test_tracer_logs_activation_without_titles(qapp, capsys) -> None:
    wsd.install_window_stacking_trace(qapp)
    window = QWidget()
    window.setWindowTitle("Doe^Jane CT")
    qapp.sendEvent(window, QEvent(QEvent.Type.WindowActivate))
    out = capsys.readouterr().out
    assert "WindowActivate on QWidget" in out
    assert "Doe" not in out
    window.deleteLater()
