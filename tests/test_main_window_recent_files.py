"""
Characterization tests for MainWindow recent-files menu and list management.

Uses isolated ConfigManager(config_dir=...) and headless QApplication.
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

from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QMenu

from gui.main_window import MainWindow
from utils.config_manager import ConfigManager


def _seed_recent_files(cm: ConfigManager, paths: list[str]) -> list[str]:
    """Add paths in order; return most-recent-first list as stored in config."""
    for path in paths:
        cm.add_recent_file(path)
    return cm.get_recent_files()


def _enabled_recent_actions(menu: QMenu) -> list:
    """Return enabled recent-file actions that carry a stored path in .data()."""
    return [a for a in menu.actions() if a.isEnabled() and a.data()]


@pytest.fixture
def config_manager(tmp_path):
    return ConfigManager(config_dir=tmp_path / "config")


@pytest.fixture
def main_window(config_manager, qapp):
    return MainWindow(config_manager)


@pytest.mark.qt
def test_update_recent_menu_builds_actions_matching_config_order(main_window, config_manager):
    paths = ["/data/study_a", "/data/study_b", "/data/study_c"]
    expected = _seed_recent_files(config_manager, paths)

    main_window._update_recent_menu()

    actions = _enabled_recent_actions(main_window.recent_menu)
    assert [a.data() for a in actions] == expected
    assert len(actions) == 3


@pytest.mark.qt
def test_update_recent_menu_public_wrapper_matches_private(main_window, config_manager):
    paths = ["/tmp/one", "/tmp/two", "/tmp/three"]
    expected = _seed_recent_files(config_manager, paths)

    main_window.update_recent_menu()

    actions = _enabled_recent_actions(main_window.recent_menu)
    assert [a.data() for a in actions] == expected


@pytest.mark.qt
def test_recent_menu_context_menu_shows_remove_move_actions(
    main_window, config_manager, monkeypatch, qapp
):
    """Context-menu path must offer Remove / Move without blocking on QMenu.exec.

    PySide6 C++ ``QMenu.exec`` is not reliably monkeypatchable on the class;
    replace ``gui.main_window.QMenu`` for the popup constructed inside eventFilter.
    """
    paths = ["/data/first", "/data/second", "/data/third"]
    _seed_recent_files(config_manager, paths)
    main_window._update_recent_menu()

    target_action = _enabled_recent_actions(main_window.recent_menu)[1]
    monkeypatch.setattr(
        main_window.recent_menu,
        "actionAt",
        lambda _pos: target_action,
    )

    captured_labels: list[list[str]] = []

    class _FakeContextMenu:
        def __init__(self, parent=None):
            self._actions = []

        def addAction(self, action):
            self._actions.append(action)
            return action

        def addSeparator(self):
            self._actions.append(None)

        def exec(self, _pos=None):
            captured_labels.append(
                [a.text() for a in self._actions if a is not None]
            )
            return None

    monkeypatch.setattr("gui.main_window.QMenu", _FakeContextMenu)

    global_pos = QPoint(300, 300)
    local_pos = main_window.recent_menu.mapFromGlobal(global_pos)
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        local_pos,
        global_pos,
    )
    handled = main_window.eventFilter(main_window.recent_menu, event)

    assert handled is True
    assert len(captured_labels) == 1
    labels = captured_labels[0]
    assert "Remove" in labels
    assert "Move Up" in labels
    assert "Move Down" in labels


@pytest.mark.qt
def test_remove_recent_file_updates_config_and_menu(main_window, config_manager):
    paths = ["/data/a", "/data/b", "/data/c"]
    _seed_recent_files(config_manager, paths)
    main_window._update_recent_menu()

    main_window._remove_recent_file("/data/b")

    assert config_manager.get_recent_files() == ["/data/c", "/data/a"]
    actions = _enabled_recent_actions(main_window.recent_menu)
    assert [a.data() for a in actions] == ["/data/c", "/data/a"]


@pytest.mark.qt
def test_move_recent_file_updates_config_and_menu(main_window, config_manager):
    paths = ["/data/a", "/data/b", "/data/c"]
    _seed_recent_files(config_manager, paths)
    main_window._update_recent_menu()

    main_window._move_recent_file("/data/c", direction="down")

    assert config_manager.get_recent_files() == ["/data/b", "/data/c", "/data/a"]
    actions = _enabled_recent_actions(main_window.recent_menu)
    assert [a.data() for a in actions] == ["/data/b", "/data/c", "/data/a"]


@pytest.mark.qt
def test_open_edit_recent_list_dialog_constructs_and_refreshes_menu(
    main_window, config_manager, monkeypatch
):
    paths = ["/data/x", "/data/y"]
    _seed_recent_files(config_manager, paths)
    main_window._update_recent_menu()

    constructed: list[object] = []

    class _FakeEditRecentListDialog:
        def __init__(self, cm, parent):
            constructed.append(self)
            self._cm = cm
            self._parent = parent

        def exec(self):
            return 0

    monkeypatch.setattr(
        "gui.main_window.EditRecentListDialog",
        _FakeEditRecentListDialog,
    )

    main_window._open_edit_recent_list_dialog()

    assert len(constructed) == 1
    assert constructed[0]._cm is config_manager
    assert constructed[0]._parent is main_window
    actions = _enabled_recent_actions(main_window.recent_menu)
    assert [a.data() for a in actions] == config_manager.get_recent_files()


@pytest.mark.qt
def test_update_recent_menu_shows_disabled_placeholder_when_empty(main_window):
    main_window._update_recent_menu()

    actions = main_window.recent_menu.actions()
    assert len(actions) == 1
    assert actions[0].text() == "No recent files"
    assert actions[0].isEnabled() is False
