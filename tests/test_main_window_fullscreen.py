"""
Tests for View → Fullscreen (MainWindow.set_fullscreen).

Uses a headless QApplication; avoids relying on platform fullscreen compositing.
"""

from __future__ import annotations

import os
import sys

import pytest

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src = os.path.join(_project_root, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent, QKeySequence  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402

from core.main_app_key_event_filter import (  # noqa: E402
    _escape_may_exit_fullscreen,
    dispatch_app_key_event,
)
from gui.main_window import MainWindow  # noqa: E402
from utils.config_manager import ConfigManager  # noqa: E402


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.mark.qt
def test_fullscreen_chrome_hide_and_restore_splitter(qapp):
    """Collapsing side panes for fullscreen uses total width in center; restore brings back sizes."""
    cm = ConfigManager()
    w = MainWindow(cm)
    w.splitter.setSizes([120, 400, 80])
    w.resize(900, 700)
    expected = list(w.splitter.sizes())

    snap = w._take_fullscreen_snapshot()
    assert snap["splitter_sizes"] == expected

    w._fullscreen_snapshot = snap
    w._apply_fullscreen_chrome_hidden()
    sizes_hidden = w.splitter.sizes()
    assert sizes_hidden[0] == 0
    assert sizes_hidden[2] == 0
    assert sizes_hidden[1] == sum(expected)

    w._restore_fullscreen_chrome(snap)
    assert w.splitter.sizes() == expected


@pytest.mark.qt
def test_fullscreen_action_has_f11_and_portable_fullscreen_shortcuts(qapp):
    w = MainWindow(ConfigManager())
    assert w.fullscreen_action is not None
    seqs = w.fullscreen_action.shortcuts()
    assert len(seqs) >= 2
    texts = {s.toString() for s in seqs}
    assert "F11" in texts
    # Portable "Ctrl+F" is Cmd+F on macOS in Qt; compare with normalized QKeySequence.
    ctrl_f = QKeySequence("Ctrl+F")
    assert any(s == ctrl_f for s in seqs)


@pytest.mark.qt
def test_dispatch_escape_exits_fullscreen_when_allowed(qapp, monkeypatch):
    w = MainWindow(ConfigManager())

    class _App:
        main_window = w
        keyboard_event_handler = None

    app = _App()

    monkeypatch.setattr(w, "isFullScreen", lambda: True)
    called: list[bool] = []

    def _exit(_en: bool) -> None:
        called.append(True)

    monkeypatch.setattr(w, "set_fullscreen", _exit)

    ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    assert dispatch_app_key_event(app, ev) is True
    assert called == [True]


@pytest.mark.qt
def test_escape_blocked_when_focus_line_edit(qapp, monkeypatch):
    w = MainWindow(ConfigManager())

    class _App:
        main_window = w
        keyboard_event_handler = None

    app = _App()
    le = QLineEdit()

    monkeypatch.setattr(w, "isFullScreen", lambda: True)
    monkeypatch.setattr(QApplication, "activeModalWidget", staticmethod(lambda: None))
    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: le))
    assert _escape_may_exit_fullscreen(app) is False


@pytest.mark.qt
def test_splitter_moved_skips_save_config_in_fullscreen(qapp, monkeypatch):
    cm = ConfigManager()
    w = MainWindow(cm)
    w.splitter.setSizes([100, 500, 100])

    calls: list[int] = []

    def spy_save() -> None:
        calls.append(1)

    monkeypatch.setattr(cm, "save_config", spy_save)
    monkeypatch.setattr(w, "isFullScreen", lambda: True)
    w._on_splitter_moved(0, 0)
    assert calls == []
