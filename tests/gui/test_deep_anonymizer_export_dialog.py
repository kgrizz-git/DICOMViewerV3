"""Tests for DeepAnonymizerExportDialog selection and mocked export."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtWidgets import QMessageBox

from gui.dialogs.deep_anonymizer_export_dialog import DeepAnonymizerExportDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


def _studies() -> dict:
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.840.10008.10.20.0.9"
    ds.Modality = "CT"
    return {"1.2.840.10008.10.20.0.1": {"1.2.840.10008.10.20.0.2": [ds]}}


@pytest.mark.qt
def test_get_options_returns_standard_share_defaults(qapp, tmp_path) -> None:
    dlg = DeepAnonymizerExportDialog(_studies(), config_manager=_cm(tmp_path))
    opts = dlg.get_options()
    assert opts.__class__.__name__ == "DeepAnonymizerOptions"
    assert opts.strip_private is True
    assert opts == dlg.options_widget.get_options()


@pytest.mark.qt
def test_export_without_selection_warns(qapp, tmp_path, monkeypatch) -> None:
    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a[1]) or QMessageBox.StandardButton.Ok,
    )
    dlg = DeepAnonymizerExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg.selected_items.clear()
    dlg._on_export()
    assert "No Selection" in warned


@pytest.mark.qt
def test_export_without_output_path_warns(qapp, tmp_path, monkeypatch) -> None:
    warned: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *a, **k: warned.append(a[1]) or QMessageBox.StandardButton.Ok,
    )
    dlg = DeepAnonymizerExportDialog(_studies(), config_manager=_cm(tmp_path))
    # Select something via tree if needed
    if not dlg.selected_items:
        # Force a fake selection
        ds = Dataset()
        ds.SOPInstanceUID = "1.2.3"
        dlg.selected_items[("1", "2", 0)] = ds
    dlg.output_path = ""
    dlg._on_export()
    assert "No Output Directory" in warned


@pytest.mark.qt
def test_export_success_mocks_manager(qapp, tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    mgr = MagicMock()
    mgr.export_selected.return_value = (1, False)
    monkeypatch.setattr(
        "gui.dialogs.deep_anonymizer_export_dialog.ExportManager",
        MagicMock(return_value=mgr),
    )
    monkeypatch.setattr(
        "gui.dialogs.deep_anonymizer_export_dialog.ExportManager.build_deep_anonymized_selection",
        MagicMock(return_value={}),
    )
    monkeypatch.setattr(
        "gui.dialogs.deep_anonymizer_export_dialog.ExportManager.get_export_paths_for_selection",
        MagicMock(return_value=[]),
    )
    cm = _cm(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    dlg = DeepAnonymizerExportDialog(_studies(), config_manager=cm)
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.3"
    dlg.selected_items[("1", "2", 0)] = ds
    dlg.output_path = str(out)
    dlg._on_export()
    mgr.export_selected.assert_called_once()
    assert dlg.result() == int(dlg.DialogCode.Accepted)
