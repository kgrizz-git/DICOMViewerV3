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


def test_block_depth_dropped_at_zero_and_cleared_on_destroy(qapp) -> None:
    w, helper = _shown(qapp)
    _block(w)
    assert len(helper._block_depth) == 1
    _unblock(w)
    assert helper._block_depth == {}
    _unblock(w)  # stray unblock must not go negative or leave an entry
    assert helper._block_depth == {}
    _block(w)
    depths = helper._block_depth
    w.close()
    w.deleteLater()
    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert depths == {}


def test_blocked_through_widget_and_qwindow_returns_to_unblocked(qapp) -> None:
    w, helper = _shown(qapp)
    handle = w.windowHandle()
    for target in (w, handle):
        QCoreApplication.sendEvent(target, QEvent(QEvent.Type.WindowBlocked))
    assert helper.is_blocked() and not _on_top(w)
    for target in (w, handle):
        QCoreApplication.sendEvent(target, QEvent(QEvent.Type.WindowUnblocked))
    assert not helper.is_blocked()
    assert _on_top(w)
    w.close()


def test_hide_show_cycle_clears_stuck_block(qapp) -> None:
    w, helper = _shown(qapp)
    _block(w)
    w.hide()  # the unblock may never arrive while hidden
    w.show()
    helper.on_shown()
    assert not helper.is_blocked()
    assert _on_top(w)
    w.close()


def _modal_dialog(parent, modality, qapp):
    from PySide6.QtWidgets import QProgressDialog

    dlg = QProgressDialog("working", "cancel", 0, 10, parent)
    dlg.setWindowModality(modality)
    dlg.show()
    qapp.processEvents()
    return dlg


@pytest.mark.parametrize("modality", [Qt.WindowModality.WindowModal, Qt.WindowModality.ApplicationModal])
def test_modal_dialog_on_another_window_suppresses_stay_on_top(qapp, modality) -> None:
    main = QWidget()
    main.show()
    tool, helper = _shown(qapp)  # parentless, like the 3D window
    assert _on_top(tool) and not helper.suppressed()
    dlg = _modal_dialog(main, modality, qapp)
    if qapp.activeModalWidget() is not dlg:
        dlg.close()
        pytest.skip("platform does not report the active modal widget")
    assert helper.suppressed()
    helper._reapply()
    assert not _on_top(tool)
    dlg.close()
    qapp.processEvents()
    helper._reapply()
    assert not helper.suppressed()
    assert _on_top(tool)
    tool.close()
    main.close()


def test_own_modal_child_does_not_suppress(qapp) -> None:
    tool, helper = _shown(qapp)
    dlg = _modal_dialog(tool, Qt.WindowModality.WindowModal, qapp)
    if qapp.activeModalWidget() is not dlg:
        dlg.close()
        pytest.skip("platform does not report the active modal widget")
    assert not helper._modal_other_active()
    dlg.close()
    tool.close()


@pytest.mark.parametrize(
    ("modality", "focus"),
    [
        (Qt.WindowModality.WindowModal, True),
        (Qt.WindowModality.WindowModal, False),
        (Qt.WindowModality.ApplicationModal, True),
    ],
)
@pytest.mark.parametrize("how", ["close", "hide"])
def test_modal_show_and_hide_reapply_without_focus_or_manual_calls(
    qapp, modality, focus, how
) -> None:
    from PySide6.QtWidgets import QProgressDialog

    main = QWidget()
    main.show()
    tool, helper = _shown(qapp)
    qapp.processEvents()
    assert _on_top(tool)
    dlg = QProgressDialog("working", "cancel", 0, 10, main)
    dlg.setWindowModality(modality)
    if not focus:
        dlg.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
    dlg.show()
    qapp.processEvents()
    if qapp.activeModalWidget() is not dlg:
        dlg.close()
        pytest.skip("platform does not report the active modal widget")
    assert not _on_top(tool)
    getattr(dlg, how)()
    qapp.processEvents()
    assert _on_top(tool)
    tool.close()
    main.close()


def test_destroyed_modal_triggers_reapply(qapp) -> None:
    from PySide6.QtWidgets import QProgressDialog

    main = QWidget()
    main.show()
    tool, helper = _shown(qapp)
    dlg = QProgressDialog("working", "cancel", 0, 10, main)
    dlg.setWindowModality(Qt.WindowModality.WindowModal)
    dlg.show()
    qapp.processEvents()
    if qapp.activeModalWidget() is not dlg:
        dlg.close()
        pytest.skip("platform does not report the active modal widget")
    assert not _on_top(tool)
    dlg.deleteLater()
    qapp.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    assert _on_top(tool)
    tool.close()
    main.close()


def test_destroyed_native_window_drops_its_block_entry(qapp) -> None:
    w, helper = _shown(qapp)
    handle = w.windowHandle()
    QCoreApplication.sendEvent(handle, QEvent(QEvent.Type.WindowBlocked))
    assert helper.is_blocked()
    w.destroy()
    qapp.processEvents()
    assert not helper.is_blocked()
    assert not helper.suppressed()
