"""
Regression tests for duplicate-safe subwindow lifecycle signal wiring.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from core.subwindow_signal_wiring import _connect_unique


class _Emitter(QObject):
    fired = Signal()


def test_connect_unique_ignores_duplicate_qt_signal_connections(qapp) -> None:
    emitter = _Emitter()
    calls: list[str] = []

    def slot() -> None:
        calls.append("called")

    _connect_unique(emitter.fired, slot)
    _connect_unique(emitter.fired, slot)
    emitter.fired.emit()

    assert calls == ["called"]
