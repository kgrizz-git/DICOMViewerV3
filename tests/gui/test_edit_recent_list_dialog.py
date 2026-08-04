"""Tests for EditRecentListDialog populate, remove, and OK persistence."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from gui.dialogs.edit_recent_list_dialog import EditRecentListDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path, recent: list[str] | None = None) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    cm.config["recent_files"] = list(recent or [])
    return cm


@pytest.mark.qt
def test_empty_list_shows_placeholder(qapp, tmp_path) -> None:
    dlg = EditRecentListDialog(_cm(tmp_path, []))
    assert dlg.list_widget.count() == 1
    assert "No recent" in dlg.list_widget.item(0).text()
    assert dlg.remove_button.isEnabled() is False


@pytest.mark.qt
def test_populate_lists_recent_paths(qapp, tmp_path) -> None:
    paths = [str(tmp_path / "a"), str(tmp_path / "b")]
    dlg = EditRecentListDialog(_cm(tmp_path, paths))
    assert dlg.list_widget.count() == 2
    assert dlg.list_widget.item(0).data(Qt.ItemDataRole.UserRole) == paths[0]


@pytest.mark.qt
def test_remove_selected_and_ok_persists(qapp, tmp_path) -> None:
    paths = [str(tmp_path / "keep"), str(tmp_path / "drop")]
    cm = _cm(tmp_path, paths)
    dlg = EditRecentListDialog(cm)
    dlg.list_widget.item(1).setCheckState(Qt.CheckState.Checked)
    dlg._remove_selected()
    assert dlg.list_widget.count() == 1
    dlg._on_ok()
    assert cm.config["recent_files"] == [paths[0]]
    assert dlg.result() == int(dlg.DialogCode.Accepted)


@pytest.mark.qt
def test_remove_all_clears_list(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    cm = _cm(tmp_path, [str(tmp_path / "x"), str(tmp_path / "y")])
    dlg = EditRecentListDialog(cm)
    dlg._remove_all()
    # After remove all, placeholder or empty list depending on implementation
    remaining = [
        dlg.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
        for i in range(dlg.list_widget.count())
        if dlg.list_widget.item(i).flags() & Qt.ItemFlag.ItemIsEnabled
    ]
    assert remaining == []
