"""
Regression tests for duplicate-safe subwindow lifecycle signal wiring.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from core.subwindow_signal_wiring import (
    _connect_unique,
    _volume_render_enabled_callback,
)


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


def test_volume_render_enabled_callback_keeps_its_subwindow_index(monkeypatch) -> None:
    from core import volume_render_eligibility

    app = object()
    calls: list[tuple[object, int]] = []

    def can_launch(fake_app: object, subwindow_index: int) -> tuple[bool, str]:
        calls.append((fake_app, subwindow_index))
        return True, "available"

    monkeypatch.setattr(volume_render_eligibility, "can_launch_3d_volume_render", can_launch)

    callback = _volume_render_enabled_callback(app, 3)

    assert callback() is True
    assert calls == [(app, 3)]
