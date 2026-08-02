"""Focused tests for StructuredReportBrowserDialog construct/export cancel paths."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pydicom
import pytest
from PySide6.QtWidgets import QMessageBox

from gui.dialogs.structured_report_browser_dialog import StructuredReportBrowserDialog

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "dicom_rdsr"
    / "synthetic_ct_dose_xray_rdsr.dcm"
)


@pytest.fixture(scope="module")
def rdsr_ds():
    assert _FIXTURE.is_file()
    return pydicom.dcmread(str(_FIXTURE))


@pytest.mark.qt
def test_construct_populates_tree_and_tabs(qapp, rdsr_ds) -> None:
    dlg = StructuredReportBrowserDialog(
        None,
        rdsr_ds,
        get_privacy_enabled=lambda: False,
    )
    assert "Structured Report" in dlg.windowTitle()
    assert dlg._tree_data.total_nodes >= 1
    assert dlg._tabs.count() >= 2
    assert dlg._model.rowCount() >= 1
    dlg.close()


@pytest.mark.qt
def test_privacy_toggle_updates_model(qapp, rdsr_ds) -> None:
    privacy = {"on": False}

    def _get() -> bool:
        return privacy["on"]

    dlg = StructuredReportBrowserDialog(None, rdsr_ds, get_privacy_enabled=_get)
    assert dlg._model._privacy is False
    privacy["on"] = True
    dlg._on_privacy_toggled(True)
    assert dlg._effective_privacy() is True
    assert dlg._model._privacy is True
    dlg.close()


@pytest.mark.qt
def test_export_tree_json_cancel_does_not_write(qapp, rdsr_ds, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "gui.dialogs.structured_report_browser_dialog.QFileDialog.getSaveFileName",
        lambda *a, **k: ("", ""),
    )
    open_mock = MagicMock()
    monkeypatch.setattr("builtins.open", open_mock)
    dlg = StructuredReportBrowserDialog(None, rdsr_ds, get_privacy_enabled=lambda: False)
    dlg._export_tree_json()
    open_mock.assert_not_called()
    dlg.close()


@pytest.mark.qt
def test_export_tree_json_writes_when_path_chosen(qapp, rdsr_ds, monkeypatch, tmp_path) -> None:
    out = tmp_path / "sr_tree.json"
    infos: list[str] = []
    monkeypatch.setattr(
        "gui.dialogs.structured_report_browser_dialog.QFileDialog.getSaveFileName",
        lambda *a, **k: (str(out), "JSON (*.json)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *a, **k: infos.append(str(a[1])) or QMessageBox.StandardButton.Ok,
    )
    dlg = StructuredReportBrowserDialog(None, rdsr_ds, get_privacy_enabled=lambda: False)
    dlg._export_tree_json()
    assert out.is_file()
    assert out.read_text(encoding="utf-8").strip().startswith("{")
    assert "Export" in infos
    dlg.close()


@pytest.mark.qt
def test_export_events_cancel_skips_write(qapp, rdsr_ds, monkeypatch) -> None:
    monkeypatch.setattr(
        "gui.dialogs.structured_report_browser_dialog.QFileDialog.getSaveFileName",
        lambda *a, **k: ("", ""),
    )
    dlg = StructuredReportBrowserDialog(None, rdsr_ds, get_privacy_enabled=lambda: False)
    write_csv = MagicMock()
    write_xlsx = MagicMock()
    dlg._write_events_csv = write_csv  # type: ignore[method-assign]
    dlg._write_events_xlsx = write_xlsx  # type: ignore[method-assign]
    if dlg._events.rows:
        dlg._export_events_csv_xlsx(xlsx=False)
        write_csv.assert_not_called()
        write_xlsx.assert_not_called()
    else:
        # No rows: information path, still no writers.
        infos: list[str] = []
        monkeypatch.setattr(
            QMessageBox,
            "information",
            lambda *a, **k: infos.append(str(a[1])) or QMessageBox.StandardButton.Ok,
        )
        dlg._export_events_csv_xlsx(xlsx=False)
        assert infos
    dlg.close()
