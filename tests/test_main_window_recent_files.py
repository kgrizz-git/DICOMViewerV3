"""
Characterization tests for MainWindow recent-files menu and list management.

Uses isolated ConfigManager(config_dir=...) and headless QApplication.

Post-extraction-#4 note: the recent-files menu rebuild, context menu (former
``MainWindow.eventFilter``), remove/move, and edit-list dialog now live in
``gui.main_window_recent_files_manager.MainWindowRecentFilesManager``
(``main_window._recent_files``). MainWindow keeps thin wrapper methods
(``_update_recent_menu``, ``_remove_recent_file``, ``_move_recent_file``,
``_open_edit_recent_list_dialog``, ``update_recent_menu``) that delegate to
the manager, so most of these tests still call them directly on
``main_window``. The context-menu test now calls the manager's
``eventFilter`` (``MainWindow.eventFilter`` was removed entirely), and the
``QMenu`` / ``EditRecentListDialog`` patches target the manager module.
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

from PySide6.QtCore import QObject, QPoint
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
    replace ``gui.main_window_recent_files_manager.QMenu`` for the popup
    constructed inside the manager's ``eventFilter``.
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

    class _FakeContextMenu(QObject):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._actions = []
            self.delete_later_called = False

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

        def deleteLater(self):
            self.delete_later_called = True

    monkeypatch.setattr("gui.main_window_recent_files_manager.QMenu", _FakeContextMenu)

    global_pos = QPoint(300, 300)
    local_pos = main_window.recent_menu.mapFromGlobal(global_pos)
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        local_pos,
        global_pos,
    )
    handled = main_window._recent_files.eventFilter(main_window.recent_menu, event)

    assert handled is True
    assert len(captured_labels) == 1
    labels = captured_labels[0]
    assert "Remove" in labels
    assert "Move Up" in labels
    assert "Move Down" in labels


def _qaction_child_count(menu: QMenu) -> int:
    """Count QAction children retained on a QMenu (leak detector for context popups)."""
    from PySide6.QtGui import QAction

    return sum(1 for child in menu.children() if isinstance(child, QAction))


@pytest.mark.qt
def test_recent_menu_context_menu_does_not_leak_actions_on_repeated_open(
    main_window, config_manager, monkeypatch, qapp
):
    """Repeated context-menu opens must not accumulate QAction children on recent_menu."""
    paths = ["/data/first", "/data/second", "/data/third"]
    _seed_recent_files(config_manager, paths)
    main_window._update_recent_menu()

    target_action = _enabled_recent_actions(main_window.recent_menu)[1]
    monkeypatch.setattr(
        main_window.recent_menu,
        "actionAt",
        lambda _pos: target_action,
    )

    class _FakeContextMenu(QObject):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._actions = []

        def addAction(self, action):
            self._actions.append(action)
            return action

        def addSeparator(self):
            self._actions.append(None)

        def exec(self, _pos=None):
            return None

        def deleteLater(self):
            pass

    monkeypatch.setattr("gui.main_window_recent_files_manager.QMenu", _FakeContextMenu)

    recent_menu = main_window.recent_menu
    baseline_children = _qaction_child_count(recent_menu)

    global_pos = QPoint(300, 300)
    local_pos = recent_menu.mapFromGlobal(global_pos)
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse,
        local_pos,
        global_pos,
    )

    for _ in range(5):
        handled = main_window._recent_files.eventFilter(recent_menu, event)
        assert handled is True

    assert _qaction_child_count(recent_menu) == baseline_children


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
        "gui.main_window_recent_files_manager.EditRecentListDialog",
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


@pytest.mark.qt
def test_main_window_no_longer_defines_event_filter(main_window):
    """MainWindow.eventFilter was removed entirely; the manager owns it now."""
    assert "eventFilter" not in type(main_window).__dict__
    assert "eventFilter" in type(main_window._recent_files).__dict__
