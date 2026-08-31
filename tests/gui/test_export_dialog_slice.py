"""Focused tests for ExportDialog selection/format paths with mocked I/O."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from gui.dialogs.export_dialog import ExportDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


def _studies() -> dict:
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.840.10008.10.20.0.1"
    ds.Modality = "CT"
    ds.SeriesDescription = "Axial SYNTH"
    return {"1.2.840.10008.10.20.0.10": {"1.2.840.10008.10.20.0.20": [ds]}}


@pytest.mark.qt
def test_construct_populates_tree(qapp, tmp_path) -> None:
    dlg = ExportDialog(_studies(), config_manager=_cm(tmp_path))
    assert dlg.tree_widget.topLevelItemCount() >= 1
    assert "Export" in dlg.windowTitle()
    assert dlg.png_radio.isChecked() is True
    dlg.reject()
    assert dlg.result() == int(dlg.DialogCode.Rejected)


@pytest.mark.qt
def test_format_change_to_jpg(qapp, tmp_path) -> None:
    dlg = ExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg.jpg_radio.setChecked(True)
    dlg._on_format_changed()
    assert dlg.jpg_radio.isChecked() is True
    assert dlg.png_radio.isChecked() is False
    dlg.close()


@pytest.mark.qt
def test_deidentification_notice_is_visible_when_enabled(qapp, tmp_path) -> None:
    dlg = ExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg.dicom_radio.setChecked(True)
    dlg._on_format_changed()
    assert dlg.anonymize_scope_notice.isHidden()
    dlg.anonymize_checkbox.setChecked(True)
    assert not dlg.anonymize_scope_notice.isHidden()
    assert "Burned-in text" in dlg.anonymize_scope_notice.text()
    dlg.anonymize_checkbox.setChecked(False)
    assert dlg.anonymize_scope_notice.isHidden()
    dlg.close()


@pytest.mark.qt
def test_export_without_selection_warns(qapp, tmp_path, monkeypatch) -> None:
    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(str(a[1])) or QMessageBox.StandardButton.Ok,
    )
    dlg = ExportDialog(_studies(), config_manager=_cm(tmp_path))
    for i in range(dlg.tree_widget.topLevelItemCount()):
        item = dlg.tree_widget.topLevelItem(i)
        item.setCheckState(0, Qt.CheckState.Unchecked)
        for j in range(item.childCount()):
            item.child(j).setCheckState(0, Qt.CheckState.Unchecked)
    dlg._update_selection()
    assert dlg.selected_items == {}
    dlg._on_export()
    assert "No Selection" in warned
    dlg.close()


@pytest.mark.qt
def test_browse_cancel_leaves_output_unchanged(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QFileDialog

    class _CancelDialog:
        FileMode = QFileDialog.FileMode

        def __init__(self, *a, **k) -> None:
            pass

        def setFileMode(self, *a, **k) -> None:
            return None

        def setWindowTitle(self, *a, **k) -> None:
            return None

        def setDirectory(self, *a, **k) -> None:
            return None

        def exec(self) -> int:
            return 0

        def selectedFiles(self) -> list[str]:
            return []

    monkeypatch.setattr("gui.dialogs.export_dialog.QFileDialog", _CancelDialog)
    dlg = ExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg.output_path = str(tmp_path / "keep")
    dlg.path_edit.setText(dlg.output_path)
    before = dlg.output_path
    dlg._browse_output()
    assert dlg.output_path == before
    dlg.close()
