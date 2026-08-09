"""
Unit tests for ``gui.main_app_key_event_filter``.

Exercises the layout-shortcut allow-list, fullscreen Escape routing, and undo
shortcut pass-through. Uses lightweight stand-ins for the app object and real
PySide6 key events; ``QApplication.focusWidget`` is monkeypatched so focus can
be controlled deterministically.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLineEdit, QSpinBox, QWidget

from gui.main_app_key_event_filter import (
    _escape_may_exit_fullscreen,
    dispatch_app_key_event,
    is_widget_allowed_for_layout_shortcuts,
)

pytestmark = pytest.mark.qt


@pytest.fixture
def app(qapp):
    a = MagicMock()
    a.series_navigator = QWidget()
    a.main_window = MagicMock()
    a.main_window.left_panel = QWidget()
    a.main_window.right_panel = QWidget()
    a.keyboard_event_handler = MagicMock()
    a.keyboard_event_handler.handle_key_event.return_value = True
    return a


def _key_event(key, modifiers=Qt.KeyboardModifier.NoModifier, etype=QKeyEvent.Type.KeyPress):
    return QKeyEvent(etype, key, modifiers)


class TestEscapeFullscreen:
    def test_not_fullscreen_returns_false(self, app):
        app.main_window.isFullScreen.return_value = False
        assert _escape_may_exit_fullscreen(app) is False

    def test_fullscreen_with_modal_does_not_exit(self, app):
        app.main_window.isFullScreen.return_value = True
        modal = QWidget()
        modal.setWindowModality(Qt.WindowModality.ApplicationModal)
        with patch.object(QApplication, "activeModalWidget", return_value=modal):
            assert _escape_may_exit_fullscreen(app) is False

    def test_fullscreen_no_focus_exits(self, app):
        app.main_window.isFullScreen.return_value = True
        with patch.object(QApplication, "focusWidget", return_value=None):
            assert _escape_may_exit_fullscreen(app) is True

    def test_fullscreen_with_text_focus_does_not_exit(self, app):
        app.main_window.isFullScreen.return_value = True
        edit = QLineEdit()
        with patch.object(QApplication, "focusWidget", return_value=edit):
            assert _escape_may_exit_fullscreen(app) is False

    def test_fullscreen_with_spin_focus_does_not_exit(self, app):
        app.main_window.isFullScreen.return_value = True
        spin = QSpinBox()
        with patch.object(QApplication, "focusWidget", return_value=spin):
            assert _escape_may_exit_fullscreen(app) is False

    def test_fullscreen_with_other_focus_exits(self, app):
        app.main_window.isFullScreen.return_value = True
        other = QWidget()
        with patch.object(QApplication, "focusWidget", return_value=other):
            assert _escape_may_exit_fullscreen(app) is True

    def test_escape_routes_to_set_fullscreen_false(self, app):
        app.main_window.isFullScreen.return_value = True
        with patch.object(QApplication, "focusWidget", return_value=None):
            result = dispatch_app_key_event(app, _key_event(Qt.Key.Key_Escape))
        assert result is True
        app.main_window.set_fullscreen.assert_called_once_with(False)

    def test_escape_keyrelease_delegated_to_handler(self, app):
        # dispatch_app_key_event delegates *every* real QKeyEvent (including
        # KeyRelease) to keyboard_event_handler and returns its result. The
        # handler decides propagation (e.g. returns False for KeyRelease so Qt
        # continues). This test pins that delegation contract; the handler result
        # is mocked here to verify the delegation, not the handler's own logic.
        app.main_window.isFullScreen.return_value = True
        ev = _key_event(Qt.Key.Key_Escape, etype=QKeyEvent.Type.KeyRelease)
        assert dispatch_app_key_event(app, ev) is True
        app.keyboard_event_handler.handle_key_event.assert_called_once_with(ev)


class TestUndoShortcut:
    def test_ctrl_z_passes_through(self, app):
        result = dispatch_app_key_event(
            app, _key_event(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        )
        assert result is False

    def test_cmd_z_passes_through(self, app):
        result = dispatch_app_key_event(
            app, _key_event(Qt.Key.Key_Z, Qt.KeyboardModifier.MetaModifier)
        )
        assert result is False


class TestLayoutShortcuts:
    def test_digit_with_allowed_focus_dispatches(self, app):
        with patch.object(QApplication, "focusWidget", return_value=app.series_navigator):
            result = dispatch_app_key_event(app, _key_event(Qt.Key.Key_1))
        assert result is True
        app.keyboard_event_handler.handle_key_event.assert_called_once()

    def test_digit_with_line_edit_focus_blocked(self, app):
        edit = QLineEdit()
        with patch.object(QApplication, "focusWidget", return_value=edit):
            result = dispatch_app_key_event(app, _key_event(Qt.Key.Key_2))
        assert result is False

    def test_digit_with_disallowed_widget_blocked(self, app):
        other = QWidget()
        with patch.object(QApplication, "focusWidget", return_value=other):
            result = dispatch_app_key_event(app, _key_event(Qt.Key.Key_3))
        assert result is False

    def test_non_key_event_returns_none(self, app):
        assert dispatch_app_key_event(app, "not-a-key-event") is None


class TestAllowListHelper:
    def test_none_widget(self, app):
        assert is_widget_allowed_for_layout_shortcuts(app, None) is False

    def test_series_navigator_allowed(self, app):
        assert is_widget_allowed_for_layout_shortcuts(app, app.series_navigator) is True

    def test_child_of_left_panel_allowed(self, app):
        child = QWidget(app.main_window.left_panel)
        assert is_widget_allowed_for_layout_shortcuts(app, child) is True

    def test_object_name_left_panel_allowed(self, app):
        w = QWidget()
        w.setObjectName("left_panel")
        assert is_widget_allowed_for_layout_shortcuts(app, w) is True

    def test_object_name_right_panel_allowed(self, app):
        w = QWidget()
        w.setObjectName("right_panel")
        assert is_widget_allowed_for_layout_shortcuts(app, w) is True

    def test_unrelated_widget_not_allowed(self, app):
        assert is_widget_allowed_for_layout_shortcuts(app, QWidget()) is False
