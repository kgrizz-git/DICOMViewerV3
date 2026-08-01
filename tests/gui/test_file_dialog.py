"""Tests for FileDialog path memory helpers and confirm_large_files."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gui.dialogs.file_dialog import FileDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


@pytest.mark.qt
def test_open_files_darwin_saves_last_path(qapp, tmp_path, monkeypatch) -> None:
    cm = _cm(tmp_path)
    fd = FileDialog(cm)
    chosen = [str(tmp_path / "a.dcm"), str(tmp_path / "b.dcm")]
    monkeypatch.setattr(
        "gui.dialogs.file_dialog.platform.system", lambda: "Darwin"
    )
    monkeypatch.setattr(
        "gui.dialogs.file_dialog.QFileDialog.getOpenFileNames",
        lambda *a, **k: (chosen, ""),
    )
    result = fd.open_files()
    assert result == chosen
    assert cm.get_last_path() == chosen[0]


@pytest.mark.qt
def test_open_files_cancel_returns_empty(qapp, tmp_path, monkeypatch) -> None:
    cm = _cm(tmp_path)
    fd = FileDialog(cm)
    monkeypatch.setattr(
        "gui.dialogs.file_dialog.platform.system", lambda: "Darwin"
    )
    monkeypatch.setattr(
        "gui.dialogs.file_dialog.QFileDialog.getOpenFileNames",
        lambda *a, **k: ([], ""),
    )
    assert fd.open_files() == []


@pytest.mark.qt
def test_open_folder_saves_directory(qapp, tmp_path, monkeypatch) -> None:
    cm = _cm(tmp_path)
    fd = FileDialog(cm)
    folder = str(tmp_path / "study")
    Path(folder).mkdir()
    monkeypatch.setattr(
        "gui.dialogs.file_dialog.platform.system", lambda: "Darwin"
    )
    monkeypatch.setattr(
        "gui.dialogs.file_dialog.QFileDialog.getExistingDirectory",
        lambda *a, **k: folder,
    )
    assert fd.open_folder() == folder
    assert cm.get_last_path() == folder


@pytest.mark.qt
def test_confirm_large_files_empty_returns_true(qapp, tmp_path) -> None:
    fd = FileDialog(_cm(tmp_path))
    assert fd.confirm_large_files(large_files=[]) is True


@pytest.mark.qt
def test_confirm_large_files_continue(qapp, tmp_path, monkeypatch) -> None:
    fd = FileDialog(_cm(tmp_path))
    box = MagicMock()
    continue_btn = object()
    box.addButton.side_effect = [continue_btn, object()]
    box.clickedButton.return_value = continue_btn
    monkeypatch.setattr("gui.dialogs.file_dialog.QMessageBox", MagicMock(return_value=box))
    # Re-bind Icon/ButtonRole used in method via the MagicMock is awkward;
    # instead patch exec path by replacing the whole method body target:
    from PySide6.QtWidgets import QMessageBox

    real_box = QMessageBox()
    real_box.setIcon = MagicMock()
    real_box.setWindowTitle = MagicMock()
    real_box.setText = MagicMock()
    real_box.setInformativeText = MagicMock()
    real_box.setWindowFlags = MagicMock()
    real_box.activateWindow = MagicMock()
    real_box.raise_ = MagicMock()
    real_box.exec = MagicMock()
    cont = object()
    real_box.addButton = MagicMock(side_effect=[cont, object()])
    real_box.setDefaultButton = MagicMock()
    real_box.clickedButton = MagicMock(return_value=cont)
    monkeypatch.setattr("gui.dialogs.file_dialog.QMessageBox", MagicMock(return_value=real_box))
    # Need StandardButton enums still on class
    monkeypatch.setattr(
        "gui.dialogs.file_dialog.QMessageBox.Icon", QMessageBox.Icon
    )
    monkeypatch.setattr(
        "gui.dialogs.file_dialog.QMessageBox.ButtonRole", QMessageBox.ButtonRole
    )
    assert fd.confirm_large_files(large_files=[("big.dcm", 40.0)]) is True
