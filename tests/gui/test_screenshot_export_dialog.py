"""Tests for ScreenshotExportDialog mode selection and export validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QLabel, QMessageBox, QWidget

from gui.dialogs.screenshot_export_dialog import ScreenshotExportDialog
from utils.config_manager import ConfigManager


class _FakeViewer(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.image_item = QGraphicsPixmapItem(QPixmap(32, 32))

    def grab(self):
        pm = QPixmap(32, 32)
        pm.fill()
        return pm


class _FakeSub:
    def __init__(self) -> None:
        self.image_viewer = _FakeViewer()


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


@pytest.mark.qt
def test_default_mode_is_separate(qapp, tmp_path) -> None:
    dlg = ScreenshotExportDialog([_FakeSub()], config_manager=_cm(tmp_path))
    assert dlg.export_mode == ScreenshotExportDialog.MODE_SEPARATE
    assert len(dlg._checkboxes) == 1
    assert dlg._checkboxes[0].isChecked() is True


@pytest.mark.qt
def test_privacy_notice_is_visible(qapp, tmp_path) -> None:
    dlg = ScreenshotExportDialog([_FakeSub()], config_manager=_cm(tmp_path))
    notice = dlg.findChild(QLabel, "screenshotPrivacyNotice")
    assert notice is not None
    assert "captures what is visible on screen" in notice.text()


@pytest.mark.qt
def test_export_without_output_warns(qapp, tmp_path, monkeypatch) -> None:
    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(str(a[1])) or QMessageBox.StandardButton.Ok,
    )
    dlg = ScreenshotExportDialog([_FakeSub()], config_manager=_cm(tmp_path))
    dlg.output_path = ""
    dlg._on_export()
    assert "No directory" in warned


@pytest.mark.qt
def test_export_separate_accept_path_with_mocked_writer(qapp, tmp_path, monkeypatch) -> None:
    """Accept path: mock grab/export so we do not exercise viewport grab/processEvents."""
    infos: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *a, **k: infos.append(str(a[1])) or QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Ok
    )
    out = tmp_path / "shots"
    out.mkdir()
    dlg = ScreenshotExportDialog([_FakeSub()], config_manager=_cm(tmp_path))
    dlg.output_path = str(out)
    dlg.prefix_edit.setText("view")
    dlg._export_separate = MagicMock(return_value=(1, None, []))  # type: ignore[method-assign]
    dlg._set_subwindow_focus_borders_suppressed = MagicMock()  # type: ignore[method-assign]
    dlg._on_export()
    dlg._export_separate.assert_called_once()
    assert "Export complete" in infos
    assert dlg.result() == int(dlg.DialogCode.Accepted)


@pytest.mark.qt
def test_browse_cancel_leaves_output_path_unchanged(qapp, tmp_path, monkeypatch) -> None:
    """Canceling the directory picker must not change output_path or export."""
    monkeypatch.setattr(
        "gui.dialogs.screenshot_export_dialog.QFileDialog.getExistingDirectory",
        lambda *a, **k: "",
    )
    dlg = ScreenshotExportDialog([_FakeSub()], config_manager=_cm(tmp_path))
    dlg.output_path = str(tmp_path / "keep")
    dlg._export_separate = MagicMock()  # type: ignore[method-assign]
    dlg._browse()
    assert dlg.output_path == str(tmp_path / "keep")
    dlg._export_separate.assert_not_called()
