"""
Event filter / shortcut dispatch regression tests for DICOMViewerApp (Phase 0).

Pins ``eventFilter`` delegation to ``dispatch_app_key_event`` and one layout-hotkey
gating path plus the ROI keyboard-delete facade.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from main_test_helpers import with_test_config_manager
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget

import main as main_module
from gui.main_app_key_event_filter import dispatch_app_key_event


@pytest.mark.qt
def test_eventfilter_returns_dispatch_result_when_handled(tmp_path, monkeypatch):
    """Handled key events must return the dispatch result (short-circuit)."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        watched = QObject()
        monkeypatch.setattr(
            main_module,
            "dispatch_app_key_event",
            lambda _app, _event: True,
        )
        ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_G, Qt.KeyboardModifier.NoModifier)
        assert app.eventFilter(watched, ev) is True
    finally:
        restore()


@pytest.mark.qt
def test_eventfilter_falls_through_when_dispatch_returns_none(tmp_path, monkeypatch):
    """When dispatch returns None, ``eventFilter`` falls through to ``QObject`` (False)."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        watched = QObject()
        monkeypatch.setattr(
            main_module,
            "dispatch_app_key_event",
            lambda _app, _event: None,
        )
        ev = QEvent(QEvent.Type.Timer)
        assert app.eventFilter(watched, ev) is False
    finally:
        restore()


@pytest.mark.qt
def test_layout_digit_hotkey_blocked_when_focus_not_allowed(tmp_path, monkeypatch):
    """Digit layout shortcuts must not reach the keyboard handler from a disallowed focus."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        blocked = QWidget()
        blocked.show()
        monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: blocked))
        app.keyboard_event_handler.handle_key_event = MagicMock(return_value=True)

        ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier)
        assert dispatch_app_key_event(app, ev) is False
        app.keyboard_event_handler.handle_key_event.assert_not_called()
    finally:
        restore()


@pytest.mark.qt
def test_layout_digit_hotkey_reaches_keyboard_handler_when_focus_allowed(
    tmp_path, monkeypatch
):
    """Allowed focus under an image viewer must delegate layout digits to the handler."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        viewer = app.image_viewer
        viewer.show()
        monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: viewer))
        app.keyboard_event_handler.handle_key_event = MagicMock(return_value=True)

        ev = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_3, Qt.KeyboardModifier.NoModifier)
        assert dispatch_app_key_event(app, ev) is True
        app.keyboard_event_handler.handle_key_event.assert_called_once_with(ev)
    finally:
        restore()


@pytest.mark.qt
def test_keyboard_delete_roi_delegates_to_roi_coordinator(tmp_path):
    """``_keyboard_delete_roi`` must route wrapper objects through the ROI coordinator."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        item = object()
        wrapper = type("RoiWrapper", (), {"item": item})()
        app.roi_coordinator.handle_roi_delete_requested = MagicMock()

        app._keyboard_delete_roi(wrapper)

        app.roi_coordinator.handle_roi_delete_requested.assert_called_once_with(item)
    finally:
        restore()
