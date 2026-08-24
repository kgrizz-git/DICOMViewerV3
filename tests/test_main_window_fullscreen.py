"""
Tests for View → Fullscreen (MainWindow.set_fullscreen).

Uses a headless QApplication; avoids relying on platform fullscreen compositing.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src = os.path.join(_project_root, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeyEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QLineEdit, QToolButton
from qt_widget_scope import widget_scope

from gui.main_app_key_event_filter import (
    _escape_may_exit_fullscreen,
    dispatch_app_key_event,
)
from gui.main_window import MainWindow
from utils.config_manager import ConfigManager

_TOOLBAR_ICON_DIR = Path(_project_root) / "resources" / "icons" / "toolbar"


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app



@pytest.fixture(autouse=True)
def _destroy_leaked_windows():
    """Destroy windows this module's tests create (see ``qt_widget_scope``)."""
    with widget_scope():
        yield

@pytest.mark.qt
def test_main_splitter_has_an_eight_pixel_hit_zone(qapp, tmp_path):
    """The target size is explicit; QSS alone does not change every native handle."""
    w = MainWindow(ConfigManager(config_dir=tmp_path / "config"))

    assert w.splitter.handleWidth() == 8


@pytest.mark.qt
def test_default_labelled_toolbar_fits_at_1280_pixels(qapp, tmp_path):
    """The first-run icon-plus-label toolbar must not need a hidden overflow row."""
    w = MainWindow(ConfigManager(config_dir=tmp_path / "config"))

    assert w.main_toolbar is not None
    assert w.main_toolbar.sizeHint().width() <= 1280


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
def test_fullscreen_action_is_available_from_toolbar(qapp):
    w = MainWindow(ConfigManager())
    assert w.fullscreen_action is not None
    assert w.main_toolbar is not None
    assert w.fullscreen_action in w.main_toolbar.actions()
    assert any(
        target is w.fullscreen_action and icon_name == "fullscreen"
        for target, icon_name in w._toolbar_icon_registry
    )
    assert (_TOOLBAR_ICON_DIR / "fullscreen.svg").exists()


@pytest.mark.qt
def test_overlay_font_actions_are_available_in_view_menu(qapp):
    w = MainWindow(ConfigManager())

    assert w.increase_overlay_font_action is not None
    assert w.decrease_overlay_font_action is not None
    assert w.increase_overlay_font_action.text() == "Increase Font Size"
    assert w.decrease_overlay_font_action.text() == "Decrease Font Size"

    increase_shortcuts = {shortcut.toString() for shortcut in w.increase_overlay_font_action.shortcuts()}
    decrease_shortcuts = {shortcut.toString() for shortcut in w.decrease_overlay_font_action.shortcuts()}
    assert "Ctrl++" in increase_shortcuts
    assert "Ctrl+=" in increase_shortcuts
    assert "Ctrl+-" in decrease_shortcuts
    assert "Ctrl+_" in decrease_shortcuts


@pytest.mark.qt
def test_overlay_font_toolbar_button_opens_compact_adjustment_controls(qapp):
    w = MainWindow(ConfigManager())

    assert isinstance(w._overlay_font_size_toolbar_btn, QToolButton)
    assert (
        w._overlay_font_size_toolbar_btn.popupMode()
        == QToolButton.ToolButtonPopupMode.InstantPopup
    )
    assert w._overlay_font_size_toolbar_btn.menu() is w.overlay_font_size_toolbar_menu

    popup_buttons = {
        button.text(): button
        for button in w.overlay_font_size_toolbar_menu.findChildren(QToolButton)
    }
    assert set(popup_buttons) == {"−", "+"}

    initial_size = w.config_manager.get_overlay_font_size()
    popup_buttons["+"].click()
    assert w.config_manager.get_overlay_font_size() == min(24, initial_size + 1)
    popup_buttons["−"].click()
    assert w.config_manager.get_overlay_font_size() == initial_size


@pytest.mark.qt
def test_main_window_actions_have_no_duplicate_shortcuts(qapp):
    """Keep global action accelerators unambiguous as menu actions are added."""
    w = MainWindow(ConfigManager())
    actions_by_shortcut: dict[str, list[str]] = {}

    for action in w.findChildren(QAction):
        for shortcut in action.shortcuts():
            if shortcut.isEmpty():
                continue
            actions_by_shortcut.setdefault(shortcut.toString(), []).append(
                action.text().replace("&", "")
            )

    duplicates = {
        shortcut: actions
        for shortcut, actions in actions_by_shortcut.items()
        if len(actions) > 1
    }
    assert duplicates == {}


@pytest.mark.qt
def test_toolbar_places_export_and_index_immediately_after_open(qapp):
    w = MainWindow(ConfigManager())
    assert w.main_toolbar is not None
    visible_texts = []
    for action in w.main_toolbar.actions():
        if action.isSeparator():
            continue
        text = action.text()
        widget = w.main_toolbar.widgetForAction(action)
        if not text and widget is not None and hasattr(widget, "defaultAction"):
            default_action = widget.defaultAction()
            text = default_action.text() if default_action is not None else ""
        if not text and widget is not None and hasattr(widget, "text"):
            text = widget.text()
        if text:
            visible_texts.append(text.replace("&", ""))

    # Recent sits immediately after Open; Export/Index follow.
    assert visible_texts[:5] == ["Open", "Recent", "Export", "Index", "Ellipse"]
    assert visible_texts.index("Text Size") == visible_texts.index("Overlay") + 1


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


@pytest.mark.qt
def test_close_event_clears_fullscreen_snapshot(qapp, monkeypatch):
    """Closing while fullscreen restores chrome and clears the in-memory snapshot."""
    w = MainWindow(ConfigManager())
    w.resize(900, 700)
    w.splitter.setSizes([120, 400, 80])

    fullscreen_state = {"active": False}

    def _enter_fullscreen() -> None:
        fullscreen_state["active"] = True

    def _exit_fullscreen() -> None:
        fullscreen_state["active"] = False

    monkeypatch.setattr(w, "isFullScreen", lambda: fullscreen_state["active"])
    monkeypatch.setattr(w, "showFullScreen", _enter_fullscreen)
    monkeypatch.setattr(w, "showNormal", _exit_fullscreen)
    monkeypatch.setattr(w, "showMaximized", lambda: None)

    w.set_fullscreen(True)
    assert w._fullscreen_snapshot is not None

    w.closeEvent(QCloseEvent())
    assert w._fullscreen_snapshot is None


@pytest.mark.qt
def test_set_fullscreen_exit_restores_splitter_toolbar_and_navigator(qapp, monkeypatch):
    """Public set_fullscreen(False) restores splitter sizes and chrome visibility."""
    w = MainWindow(ConfigManager())
    w.resize(900, 700)
    w.show()
    qapp.processEvents()
    w.splitter.setSizes([120, 400, 80])
    expected_sizes = list(w.splitter.sizes())

    container = getattr(w, "series_navigator_container", None)
    if container is not None:
        container.setVisible(True)
        w.series_navigator_visible = True
    w.main_toolbar.show()
    qapp.processEvents()
    assert w.main_toolbar.isVisible() is True

    fullscreen_state = {"active": False}

    monkeypatch.setattr(w, "isFullScreen", lambda: fullscreen_state["active"])
    monkeypatch.setattr(
        w,
        "showFullScreen",
        lambda: fullscreen_state.update(active=True),
    )
    monkeypatch.setattr(
        w,
        "showNormal",
        lambda: fullscreen_state.update(active=False),
    )
    monkeypatch.setattr(w, "showMaximized", lambda: None)

    w.set_fullscreen(True)
    hidden_sizes = w.splitter.sizes()
    assert hidden_sizes[0] == 0
    assert hidden_sizes[2] == 0
    assert hidden_sizes[1] == sum(expected_sizes)
    if container is not None:
        assert container.isVisible() is False
    assert w.main_toolbar.isVisible() is False

    w.set_fullscreen(False)
    assert w.splitter.sizes() == expected_sizes
    if container is not None:
        assert container.isVisible() is True
    assert w.main_toolbar.isVisible() is True
    assert w._fullscreen_snapshot is None
    w.close()
