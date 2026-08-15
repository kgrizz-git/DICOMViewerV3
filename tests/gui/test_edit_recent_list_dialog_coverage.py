"""Behavioral coverage for the remaining EditRecentListDialog paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMessageBox

import gui.dialogs.edit_recent_list_dialog as dialog_module
from gui.dialogs.edit_recent_list_dialog import EditRecentListDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path, recent: list[str]) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "config.json"
    cm.config = cm.default_config.copy()
    cm.config["recent_files"] = list(recent)
    return cm


def _paths(tmp_path: Path, *names: str) -> list[str]:
    return [str(tmp_path / name) for name in names]


def _items(dialog: EditRecentListDialog) -> list[str]:
    return [
        dialog.list_widget.item(index).data(Qt.ItemDataRole.UserRole)
        for index in range(dialog.list_widget.count())
        if dialog.list_widget.item(index).flags() & Qt.ItemFlag.ItemIsEnabled
    ]


def _item(dialog: EditRecentListDialog, path: str):
    return next(
        dialog.list_widget.item(index)
        for index in range(dialog.list_widget.count())
        if dialog.list_widget.item(index).data(Qt.ItemDataRole.UserRole) == path
    )


@pytest.mark.qt
def test_empty_dialog_disables_all_action_buttons(qapp, tmp_path):
    dialog = EditRecentListDialog(_cm(tmp_path, []))

    assert dialog.remove_all_button.isEnabled() is False
    assert dialog.remove_button.isEnabled() is False
    assert dialog.move_up_button.isEnabled() is False
    assert dialog.move_down_button.isEnabled() is False
    assert dialog.list_widget.item(0).flags() == Qt.ItemFlag.NoItemFlags


@pytest.mark.qt
def test_duplicate_and_missing_paths_are_displayed_and_preserved(qapp, tmp_path):
    paths = _paths(tmp_path, "missing.dcm", "missing.dcm", "folder")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))

    assert _items(dialog) == paths
    assert dialog.list_widget.item(0).toolTip() == paths[0]
    assert dialog.list_widget.item(1).data(Qt.ItemDataRole.UserRole) == paths[1]

    dialog._on_ok()
    assert dialog.config_manager.config["recent_files"] == paths


@pytest.mark.qt
def test_checkbox_change_syncs_selection_and_move_buttons(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b", "c")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    item = dialog.list_widget.item(1)

    item.setCheckState(Qt.CheckState.Checked)
    assert item.isSelected() is True
    assert dialog.move_up_button.isEnabled() is True
    assert dialog.move_down_button.isEnabled() is True

    item.setCheckState(Qt.CheckState.Unchecked)
    assert item.isSelected() is False
    assert dialog.move_up_button.isEnabled() is False
    assert dialog.move_down_button.isEnabled() is False


@pytest.mark.qt
def test_item_changed_ignores_placeholder(qapp, tmp_path):
    dialog = EditRecentListDialog(_cm(tmp_path, []))
    placeholder = dialog.list_widget.item(0)

    dialog._on_item_changed(placeholder)

    assert dialog.list_widget.selectedItems() == []
    assert dialog.move_up_button.isEnabled() is False


@pytest.mark.qt
def test_row_click_toggles_checkbox_and_selection(qapp, tmp_path):
    path = _paths(tmp_path, "a")[0]
    dialog = EditRecentListDialog(_cm(tmp_path, [path]))
    item = dialog.list_widget.item(0)

    dialog._on_item_clicked(item)
    assert item.checkState() == Qt.CheckState.Checked
    assert item.isSelected() is True

    dialog._on_item_clicked(item)
    assert item.checkState() == Qt.CheckState.Unchecked
    assert item.isSelected() is False


@pytest.mark.qt
def test_checkbox_click_detection_does_not_toggle_twice(qapp, tmp_path):
    path = _paths(tmp_path, "a")[0]
    dialog = EditRecentListDialog(_cm(tmp_path, [path]))
    item = dialog.list_widget.item(0)

    dialog._on_item_pressed(item)
    item.setCheckState(Qt.CheckState.Checked)
    dialog._on_item_clicked(item)

    assert item.checkState() == Qt.CheckState.Checked
    assert item.isSelected() is True
    assert dialog._checkbox_state_before_click == {}


@pytest.mark.qt
def test_item_clicked_cleans_unchanged_checkbox_tracking(qapp, tmp_path):
    path = _paths(tmp_path, "a")[0]
    dialog = EditRecentListDialog(_cm(tmp_path, [path]))
    item = dialog.list_widget.item(0)
    dialog._on_item_pressed(item)

    dialog._on_item_clicked(item)

    assert item.checkState() == Qt.CheckState.Checked
    assert dialog._checkbox_state_before_click == {}


@pytest.mark.qt
def test_item_pressed_ignores_noninteractive_and_missing_data(qapp, tmp_path):
    empty = EditRecentListDialog(_cm(tmp_path, []))
    empty._on_item_pressed(empty.list_widget.item(0))
    assert empty._checkbox_state_before_click == {}

    path = _paths(tmp_path, "a")[0]
    dialog = EditRecentListDialog(_cm(tmp_path, [path]))
    item = dialog.list_widget.item(0)
    item.setData(Qt.ItemDataRole.UserRole, None)
    dialog._on_item_pressed(item)
    assert dialog._checkbox_state_before_click == {}


@pytest.mark.qt
def test_item_clicked_ignores_placeholder_and_missing_data(qapp, tmp_path):
    empty = EditRecentListDialog(_cm(tmp_path, []))
    empty._on_item_clicked(empty.list_widget.item(0))
    assert empty.list_widget.item(0).text() == "No recent files"

    path = _paths(tmp_path, "a")[0]
    dialog = EditRecentListDialog(_cm(tmp_path, [path]))
    item = dialog.list_widget.item(0)
    item.setData(Qt.ItemDataRole.UserRole, None)
    dialog._on_item_clicked(item)
    assert item.checkState() == Qt.CheckState.Unchecked


@pytest.mark.qt
def test_remove_selected_removes_multiple_items_and_updates_empty_state(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b", "c")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    for index in (0, 2):
        dialog.list_widget.item(index).setCheckState(Qt.CheckState.Checked)

    dialog._remove_selected()
    assert _items(dialog) == [paths[1]]
    assert dialog.remove_button.isEnabled() is True
    assert dialog.remove_all_button.isEnabled() is True

    dialog.list_widget.item(0).setCheckState(Qt.CheckState.Checked)
    dialog._remove_selected()
    assert dialog.list_widget.count() == 1
    assert dialog.list_widget.item(0).text() == "No recent files"
    assert dialog.remove_button.isEnabled() is False
    assert dialog.remove_all_button.isEnabled() is False
    assert dialog.move_up_button.isEnabled() is False
    assert dialog.move_down_button.isEnabled() is False


@pytest.mark.qt
def test_remove_selected_with_no_checked_items_is_noop(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))

    dialog._remove_selected()

    assert _items(dialog) == paths


@pytest.mark.qt
def test_remove_all_empty_widget_returns_without_modal(qapp, tmp_path, monkeypatch):
    dialog = EditRecentListDialog(_cm(tmp_path, [str(tmp_path / "a")]))
    dialog.list_widget.clear()
    question = Mock()
    monkeypatch.setattr(QMessageBox, "question", question)

    dialog._remove_all()

    question.assert_not_called()


@pytest.mark.qt
def test_context_menu_skips_empty_and_placeholder_positions(qapp, tmp_path):
    empty = EditRecentListDialog(_cm(tmp_path, []))
    empty._show_context_menu(QPoint(1, 1))
    assert empty.list_widget.count() == 1

    paths = _paths(tmp_path, "a")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    dialog._show_context_menu(QPoint(2000, 2000))
    assert _items(dialog) == paths


@pytest.mark.qt
def test_context_menu_selects_item_and_exposes_boundary_actions(qapp, tmp_path, monkeypatch):
    paths = _paths(tmp_path, "a", "b", "c")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    observed: dict[str, object] = {}

    class FakeMenu:
        def __init__(self, parent):
            observed["parent"] = parent
            self.actions: list[QAction] = []

        def addAction(self, action):
            self.actions.append(action)

        def addSeparator(self):
            observed["separator"] = True

        def exec(self, position):
            observed["position"] = position
            observed["actions"] = self.actions

    monkeypatch.setattr(dialog_module, "QMenu", FakeMenu)
    dialog._show_context_menu(dialog.list_widget.visualItemRect(dialog.list_widget.item(1)).center())

    actions = observed["actions"]
    assert observed["parent"] is dialog
    assert observed["separator"] is True
    assert len(actions) == 3
    assert actions[0].text() == "Remove This Item"
    assert actions[1].isEnabled() is True
    assert actions[2].isEnabled() is True
    assert dialog.list_widget.item(1).isSelected() is True
    assert dialog.list_widget.item(1).checkState() == Qt.CheckState.Checked


@pytest.mark.qt
def test_context_menu_boundary_action_states(qapp, tmp_path, monkeypatch):
    paths = _paths(tmp_path, "a", "b")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    menus = []

    class FakeMenu:
        def __init__(self, parent):
            self.actions = []
            menus.append(self)

        def addAction(self, action):
            self.actions.append(action)

        def addSeparator(self):
            pass

        def exec(self, position):
            pass

    monkeypatch.setattr(dialog_module, "QMenu", FakeMenu)
    first = dialog.list_widget.item(0)
    first.setSelected(True)
    dialog._show_context_menu(dialog.list_widget.visualItemRect(first).center())
    assert menus[-1].actions[1].isEnabled() is False
    assert menus[-1].actions[2].isEnabled() is True

    last = dialog.list_widget.item(1)
    dialog._show_context_menu(dialog.list_widget.visualItemRect(last).center())
    assert menus[-1].actions[1].isEnabled() is True
    assert menus[-1].actions[2].isEnabled() is False


@pytest.mark.qt
def test_context_actions_delete_and_move_boundaries(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b", "c")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    middle = dialog.list_widget.item(1)

    dialog._move_context_item_up(middle)
    assert _items(dialog) == [paths[1], paths[0], paths[2]]
    assert dialog.list_widget.item(0).isSelected() is True

    dialog._move_context_item_down(dialog.list_widget.item(0))
    assert _items(dialog) == paths

    dialog._move_context_item_up(dialog.list_widget.item(0))
    dialog._move_context_item_down(dialog.list_widget.item(2))
    assert _items(dialog) == paths

    dialog._delete_context_item(dialog.list_widget.item(1))
    assert _items(dialog) == [paths[0], paths[2]]


@pytest.mark.qt
def test_context_delete_last_item_restores_placeholder(qapp, tmp_path):
    path = _paths(tmp_path, "a")[0]
    dialog = EditRecentListDialog(_cm(tmp_path, [path]))

    dialog._delete_context_item(dialog.list_widget.item(0))

    assert dialog.list_widget.count() == 1
    assert dialog.list_widget.item(0).flags() == Qt.ItemFlag.NoItemFlags
    assert dialog.remove_button.isEnabled() is False
    assert dialog.remove_all_button.isEnabled() is False


@pytest.mark.qt
def test_remove_all_guards_placeholder_and_empty_list(qapp, tmp_path, monkeypatch):
    question = Mock(return_value=QMessageBox.StandardButton.Yes)
    monkeypatch.setattr(QMessageBox, "question", question)
    empty = EditRecentListDialog(_cm(tmp_path, []))
    empty._remove_all()
    assert question.call_count == 0

    paths = _paths(tmp_path, "a")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    dialog._delete_context_item(dialog.list_widget.item(0))
    dialog._remove_all()
    assert question.call_count == 0


@pytest.mark.qt
@pytest.mark.parametrize("reply", [QMessageBox.StandardButton.No, QMessageBox.StandardButton.Cancel])
def test_remove_all_nonconfirmation_preserves_items(qapp, tmp_path, monkeypatch, reply):
    paths = _paths(tmp_path, "a", "b")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: reply)

    dialog._remove_all()

    assert _items(dialog) == paths
    assert dialog.remove_all_button.isEnabled() is True


@pytest.mark.qt
def test_remove_all_single_item_requires_confirmation(qapp, tmp_path, monkeypatch):
    path = _paths(tmp_path, "a")[0]
    dialog = EditRecentListDialog(_cm(tmp_path, [path]))
    question = Mock(return_value=QMessageBox.StandardButton.No)
    monkeypatch.setattr(QMessageBox, "question", question)

    dialog._remove_all()

    question.assert_called_once()
    assert _items(dialog) == [path]


@pytest.mark.qt
def test_remove_all_yes_clears_items_and_disables_buttons(qapp, tmp_path, monkeypatch):
    paths = _paths(tmp_path, "a", "b")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    dialog._remove_all()

    assert _items(dialog) == []
    assert dialog.remove_button.isEnabled() is False
    assert dialog.remove_all_button.isEnabled() is False
    assert dialog.move_up_button.isEnabled() is False
    assert dialog.move_down_button.isEnabled() is False


@pytest.mark.qt
def test_move_buttons_handle_no_selection_and_boundaries(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b", "c")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))

    dialog._move_item_up()
    dialog._move_item_down()
    assert _items(dialog) == paths

    dialog.list_widget.item(0).setSelected(True)
    dialog._move_item_up()
    assert _items(dialog) == paths
    assert dialog.move_up_button.isEnabled() is False
    assert dialog.move_down_button.isEnabled() is True

    dialog.list_widget.clearSelection()
    dialog.list_widget.item(2).setSelected(True)
    dialog._move_item_down()
    assert _items(dialog) == paths
    assert dialog.move_up_button.isEnabled() is True
    assert dialog.move_down_button.isEnabled() is False


@pytest.mark.qt
def test_move_selected_items_preserves_order_and_selection(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b", "c", "d")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    dialog.list_widget.item(1).setSelected(True)
    dialog.list_widget.item(2).setSelected(True)

    dialog._move_item_up()
    assert _items(dialog) == [paths[1], paths[2], paths[0], paths[3]]
    assert [item.data(Qt.ItemDataRole.UserRole) for item in dialog.list_widget.selectedItems()] == [
        paths[1],
        paths[2],
    ]

    dialog._move_item_down()
    assert _items(dialog) == paths
    assert {item.data(Qt.ItemDataRole.UserRole) for item in dialog.list_widget.selectedItems()} == {
        paths[1],
        paths[2],
    }


@pytest.mark.qt
def test_move_non_adjacent_selected_items_up_preserves_order(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b", "c", "d", "e")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    dialog.list_widget.item(1).setSelected(True)
    dialog.list_widget.item(3).setSelected(True)

    dialog._move_item_up()

    assert _items(dialog) == [paths[1], paths[0], paths[3], paths[2], paths[4]]
    assert [item.data(Qt.ItemDataRole.UserRole) for item in dialog.list_widget.selectedItems()] == [
        paths[1],
        paths[3],
    ]


@pytest.mark.qt
def test_move_selected_items_at_boundary_is_noop(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b", "c")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    dialog.list_widget.item(0).setSelected(True)
    dialog.list_widget.item(1).setSelected(True)
    dialog._move_item_up()
    assert _items(dialog) == paths

    dialog.list_widget.clearSelection()
    dialog.list_widget.item(1).setSelected(True)
    dialog.list_widget.item(2).setSelected(True)
    dialog._move_item_down()
    assert _items(dialog) == paths


@pytest.mark.qt
def test_move_multiple_selected_items_down_restores_selection(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b", "c", "d")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))
    dialog.list_widget.item(1).setSelected(True)
    dialog.list_widget.item(2).setSelected(True)

    dialog._move_item_down()

    assert _items(dialog) == [paths[0], paths[3], paths[1], paths[2]]
    assert {item.data(Qt.ItemDataRole.UserRole) for item in dialog.list_widget.selectedItems()} == {
        paths[1],
        paths[2],
    }


@pytest.mark.qt
def test_ok_skips_placeholder_and_saves_reordered_paths(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b")
    cm = _cm(tmp_path, paths)
    dialog = EditRecentListDialog(cm)
    dialog._move_context_item_down(dialog.list_widget.item(0))
    dialog._on_ok()

    assert cm.config["recent_files"] == [paths[1], paths[0]]
    assert dialog.result() == int(dialog.DialogCode.Accepted)


@pytest.mark.qt
def test_ok_skips_enabled_item_without_path_data(qapp, tmp_path):
    cm = _cm(tmp_path, _paths(tmp_path, "a", "b"))
    dialog = EditRecentListDialog(cm)
    dialog.list_widget.item(1).setData(Qt.ItemDataRole.UserRole, None)

    dialog._on_ok()

    assert cm.config["recent_files"] == [_paths(tmp_path, "a")[0]]


@pytest.mark.qt
def test_ok_accepts_empty_placeholder_as_empty_recent_list(qapp, tmp_path):
    cm = _cm(tmp_path, [])
    dialog = EditRecentListDialog(cm)

    dialog._on_ok()

    assert cm.config["recent_files"] == []
    assert dialog.result() == int(dialog.DialogCode.Accepted)


@pytest.mark.qt
def test_ok_propagates_save_error_without_accepting(qapp, tmp_path):
    cm = _cm(tmp_path, _paths(tmp_path, "a"))
    cm.save_config = Mock(side_effect=OSError("synthetic save failure"))
    dialog = EditRecentListDialog(cm)

    with pytest.raises(OSError, match="synthetic save failure"):
        dialog._on_ok()

    assert dialog.result() == int(dialog.DialogCode.Rejected)


@pytest.mark.qt
def test_item_selection_changed_updates_button_state(qapp, tmp_path):
    paths = _paths(tmp_path, "a", "b", "c")
    dialog = EditRecentListDialog(_cm(tmp_path, paths))

    dialog.list_widget.item(1).setSelected(True)
    assert dialog.move_up_button.isEnabled() is True
    assert dialog.move_down_button.isEnabled() is True
    dialog.list_widget.clearSelection()
    assert dialog.move_up_button.isEnabled() is False
    assert dialog.move_down_button.isEnabled() is False
