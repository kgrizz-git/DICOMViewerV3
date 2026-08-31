"""Tests for ExportROIStatisticsDialog series selection and export paths."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox

from gui.dialogs.export_roi_statistics_dialog import (
    ExportROIStatisticsDialog,
    _any_series_has_rescale,
    _count_annotations_for_series,
)


def _ds(**kwargs) -> Dataset:
    ds = Dataset()
    for k, v in kwargs.items():
        setattr(ds, k, v)
    return ds


def _studies() -> dict:
    return {
        "1.2.840.10008.10.20.0.1": {
            "1.2.840.10008.10.20.0.2": [
                _ds(
                    AccessionNumber="ACC123",
                    PatientID="SYNTH01",
                    RescaleSlope=1.0,
                    RescaleIntercept=-1024.0,
                )
            ]
        }
    }


@pytest.mark.qt
def test_count_annotations_helper(qapp) -> None:
    class FakeRoi:
        def __init__(self) -> None:
            self.rois = {("s", "ser", 0): [object(), object()]}

    class FakeXh:
        def __init__(self) -> None:
            self.crosshairs = {("s", "ser", 0): [object()]}

    class FakeMt:
        def get_measurements_for_slice(self, study, series, z):
            return [object()] if z == 0 else []

    managers = {0: {"roi_manager": FakeRoi(), "crosshair_manager": FakeXh(), "measurement_tool": FakeMt()}}
    assert _count_annotations_for_series("s", "ser", 1, managers) == (2, 1, 1)


@pytest.mark.qt
def test_any_series_has_rescale(qapp) -> None:
    assert _any_series_has_rescale(_studies()) is True
    bare = {"1": {"2": [_ds()]}}
    assert _any_series_has_rescale(bare) is False


@pytest.mark.qt
def test_dialog_populates_tree_and_default_path(qapp) -> None:
    dlg = ExportROIStatisticsDialog(_studies(), {}, config_manager=None)
    assert dlg.series_tree.topLevelItemCount() == 1
    # With no series checked, default basename is ROI_stats.
    assert "ROI_stats" in dlg.file_path_edit.text()
    study = dlg.series_tree.topLevelItem(0)
    study.child(0).setCheckState(0, Qt.CheckState.Checked)
    dlg._update_default_file_path()
    assert "ACC123" in dlg.file_path_edit.text()
    dlg.radio_csv.setChecked(True)
    dlg._on_format_changed()
    assert dlg.file_path_edit.text().lower().endswith(".csv")
    notice = dlg.findChild(QLabel, "roiExportPrivacyNotice")
    assert notice is not None
    assert "accession number" in notice.text()


@pytest.mark.qt
def test_export_without_selection_warns(qapp, monkeypatch) -> None:
    warned: list[str] = []

    def _warn(parent, title, text):
        warned.append(title)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    dlg = ExportROIStatisticsDialog(_studies(), {})
    # Deselect all series
    for i in range(dlg.series_tree.topLevelItemCount()):
        study = dlg.series_tree.topLevelItem(i)
        for j in range(study.childCount()):
            study.child(j).setCheckState(0, Qt.CheckState.Unchecked)
    dlg._do_export()
    assert "No Series Selected" in warned


@pytest.mark.qt
def test_export_success_calls_run_export(qapp, monkeypatch, tmp_path) -> None:
    run = MagicMock()
    monkeypatch.setattr(
        "gui.dialogs.export_roi_statistics_dialog.run_export", run
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **k: QMessageBox.StandardButton.Ok
    )
    dlg = ExportROIStatisticsDialog(_studies(), {})
    # Ensure series checked
    study = dlg.series_tree.topLevelItem(0)
    study.child(0).setCheckState(0, Qt.CheckState.Checked)
    out = str(tmp_path / "out.csv")
    dlg.radio_csv.setChecked(True)
    dlg.file_path_edit.setText(out)
    dlg._do_export()
    run.assert_called_once()
    assert run.call_args.kwargs["format_key"] == "CSV"
    assert dlg.result() == int(dlg.DialogCode.Accepted)


@pytest.mark.qt
def test_browse_cancel_leaves_path_unchanged(qapp, monkeypatch) -> None:
    """Canceling the save dialog must not change the export path or call run_export."""
    run = MagicMock()
    monkeypatch.setattr(
        "gui.dialogs.export_roi_statistics_dialog.run_export", run
    )
    monkeypatch.setattr(
        "gui.dialogs.export_roi_statistics_dialog.QFileDialog.getSaveFileName",
        lambda *a, **k: ("", ""),
    )
    dlg = ExportROIStatisticsDialog(_studies(), {})
    before = dlg.file_path_edit.text()
    dlg._browse_file()
    assert dlg.file_path_edit.text() == before
    run.assert_not_called()
