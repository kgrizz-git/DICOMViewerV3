"""Tests for gui.window_stacking.AppScopedStayOnTop."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtWidgets import QWidget

from gui import window_stacking
from gui.window_stacking import AppScopedStayOnTop

pytestmark = pytest.mark.qt

TOP = Qt.WindowType.WindowStaysOnTopHint


def _on_top(w: QWidget) -> bool:
    handle = w.windowHandle()
    assert handle is not None
    return bool(handle.flags() & TOP)


def _shown(qapp, helper_enabled=lambda: True, active=True):
    w = QWidget()
    helper = AppScopedStayOnTop(w, enabled=helper_enabled)
    helper.apply(active)
    w.show()
    helper.on_shown()
    return w, helper


def _block(w: QWidget) -> None:
    QCoreApplication.sendEvent(w, QEvent(QEvent.Type.WindowBlocked))


def _unblock(w: QWidget) -> None:
    QCoreApplication.sendEvent(w, QEvent(QEvent.Type.WindowUnblocked))


def test_follows_app_state(qapp) -> None:
    w, helper = _shown(qapp)
    helper._on_state_changed(Qt.ApplicationState.ApplicationActive)
    assert _on_top(w)
    helper._on_state_changed(Qt.ApplicationState.ApplicationInactive)
    assert not _on_top(w)
    helper._on_state_changed(Qt.ApplicationState.ApplicationActive)
    assert _on_top(w)
    w.close()


def test_noop_before_native_handle_and_applied_on_show(qapp) -> None:
    w = QWidget()
    helper = AppScopedStayOnTop(w)
    helper.apply(True)  # must not raise or create a handle
    assert w.windowHandle() is None
    w.show()
    helper.on_shown()
    assert _on_top(w)
    w.close()


def test_modal_block_clears_and_unblock_restores(qapp) -> None:
    w, helper = _shown(qapp)
    assert _on_top(w)
    _block(w)
    assert helper.is_blocked()
    assert not _on_top(w)
    _unblock(w)
    assert not helper.is_blocked()
    assert _on_top(w)
    w.close()


def test_nested_blocks(qapp) -> None:
    w, helper = _shown(qapp)
    _block(w)
    _block(w)
    _unblock(w)
    assert helper.is_blocked()
    assert not _on_top(w)
    _unblock(w)
    assert not helper.is_blocked()
    assert _on_top(w)
    w.close()


def test_unblock_while_inactive_stays_off(qapp) -> None:
    w, helper = _shown(qapp)
    _block(w)
    helper._on_state_changed(Qt.ApplicationState.ApplicationInactive)
    _unblock(w)
    assert not _on_top(w)
    helper._on_state_changed(Qt.ApplicationState.ApplicationActive)
    assert _on_top(w)
    w.close()


def test_enabled_false_keeps_it_off(qapp) -> None:
    state = {"on": False}
    w, helper = _shown(qapp, helper_enabled=lambda: state["on"])
    assert not _on_top(w)
    helper._on_state_changed(Qt.ApplicationState.ApplicationActive)
    assert not _on_top(w)
    state["on"] = True
    helper.apply(True)
    assert _on_top(w)
    w.close()


def test_toggling_keeps_visible_and_minimized(qapp) -> None:
    w, helper = _shown(qapp)
    w.showMinimized()
    if not w.isMinimized():
        pytest.skip("offscreen platform cannot minimize")
    for active in (False, True, False):
        helper.apply(active)
        assert w.isVisible()
        assert w.windowState() & Qt.WindowState.WindowMinimized
    w.close()


def test_toggling_never_hides_window(qapp) -> None:
    w, helper = _shown(qapp)
    for active in (False, True):
        helper.apply(active)
        assert w.isVisible()
    w.close()


def test_two_tool_windows_both_stay_on_top(qapp) -> None:
    a, ha = _shown(qapp)
    b, hb = _shown(qapp)
    assert _on_top(a)
    assert _on_top(b)
    a.close()
    b.close()


def test_windows_gate_disables_stay_on_top(qapp, monkeypatch) -> None:
    monkeypatch.setattr(window_stacking, "_current_platform", lambda: "win32")
    assert not window_stacking.platform_supports_stay_on_top()
    w, _helper = _shown(qapp, helper_enabled=window_stacking.platform_supports_stay_on_top)
    assert not _on_top(w)
    monkeypatch.setattr(window_stacking, "_current_platform", lambda: "darwin")
    assert window_stacking.platform_supports_stay_on_top()
    w.close()
