"""Tests for RadiationDoseReportDialog table populate and mocked export."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QMessageBox

from core.rdsr_dose_sr import CtRadiationDoseSummary
from gui.dialogs.radiation_dose_report_dialog import RadiationDoseReportDialog


def _summary() -> CtRadiationDoseSummary:
    return CtRadiationDoseSummary(
        study_instance_uid="1.2.3",
        series_instance_uid="1.2.4",
        sop_instance_uid="1.2.5",
        manufacturer="SyntheticVendor",
        ctdi_vol_mgy=12.5,
        dlp_mgy_cm=350.0,
        irradiation_event_count=2,
    )


@pytest.mark.qt
def test_table_shows_summary_fields(qapp) -> None:
    dlg = RadiationDoseReportDialog(
        None, _summary(), get_privacy_enabled=lambda: False, series_description="Dose SR"
    )
    assert "Dose SR" in dlg.windowTitle()
    assert dlg._table.rowCount() == 11
    # Field column includes CTDIvol
    fields = [dlg._table.item(r, 0).text() for r in range(dlg._table.rowCount())]
    assert "CTDIvol (mGy)" in fields
    values = [dlg._table.item(r, 1).text() for r in range(dlg._table.rowCount())]
    assert "12.5" in values
    assert "SyntheticVendor" in values
    assert "does not de-identify the source DICOM" in dlg._hint.text()


@pytest.mark.qt
def test_privacy_mode_masks_uids(qapp) -> None:
    dlg = RadiationDoseReportDialog(
        None, _summary(), get_privacy_enabled=lambda: True
    )
    values = [dlg._table.item(r, 1).text() for r in range(dlg._table.rowCount())]
    assert "1.2.3" not in values


@pytest.mark.qt
def test_export_json_cancel_does_not_write(qapp, monkeypatch) -> None:
    write = MagicMock()
    monkeypatch.setattr(
        "gui.dialogs.radiation_dose_report_dialog.QFileDialog.getSaveFileName",
        lambda *a, **k: ("", ""),
    )
    monkeypatch.setattr(
        "gui.dialogs.radiation_dose_report_dialog.write_dose_summary_json", write
    )
    dlg = RadiationDoseReportDialog(
        None, _summary(), get_privacy_enabled=lambda: False
    )
    dlg._export_json()
    write.assert_not_called()


@pytest.mark.qt
def test_export_json_writes_when_path_chosen(qapp, monkeypatch, tmp_path) -> None:
    out = str(tmp_path / "dose.json")
    write = MagicMock()
    monkeypatch.setattr(
        "gui.dialogs.radiation_dose_report_dialog.QFileDialog.getSaveFileName",
        lambda *a, **k: (out, "JSON (*.json)"),
    )
    monkeypatch.setattr(
        "gui.dialogs.radiation_dose_report_dialog.write_dose_summary_json", write
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok
    )
    dlg = RadiationDoseReportDialog(
        None, _summary(), get_privacy_enabled=lambda: False
    )
    dlg._anonymize_cb.setChecked(True)
    dlg._export_json()
    write.assert_called_once()
    assert write.call_args.args[0] == out
    assert write.call_args.kwargs["anonymize"] is True
