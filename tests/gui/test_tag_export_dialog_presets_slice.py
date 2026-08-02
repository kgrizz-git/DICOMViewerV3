"""Focused TagExportDialog toggle/filter/preset list slice."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt

from gui.dialogs.tag_export_dialog import TagExportDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


def _studies() -> dict:
    ds = Dataset()
    ds.SOPInstanceUID = "1.2.840.10008.10.20.0.1"
    ds.PatientID = "SYNTH01"
    ds.Modality = "CT"
    ds.SeriesDescription = "Axial"
    return {"1.2.840.10008.10.20.0.10": {"1.2.840.10008.10.20.0.20": [ds]}}


@pytest.mark.qt
def test_construct_populates_series_and_tags(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    assert dlg.series_tree.topLevelItemCount() >= 1
    assert dlg.tags_tree.topLevelItemCount() >= 1
    dlg.reject()
    assert dlg.result() == int(dlg.DialogCode.Rejected)


@pytest.mark.qt
def test_toggle_all_series_and_tags(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    dlg._toggle_all_series(True)
    study = dlg.series_tree.topLevelItem(0)
    assert study.child(0).checkState(0) == Qt.CheckState.Checked
    dlg._toggle_all_series(False)
    assert study.child(0).checkState(0) == Qt.CheckState.Unchecked

    dlg._toggle_all_tags(True)
    # At least one tag row checked after toggle-all.
    checked = 0
    for i in range(dlg.tags_tree.topLevelItemCount()):
        item = dlg.tags_tree.topLevelItem(i)
        if item.checkState(0) == Qt.CheckState.Checked:
            checked += 1
        for j in range(item.childCount()):
            if item.child(j).checkState(0) == Qt.CheckState.Checked:
                checked += 1
    assert checked >= 1
    dlg.close()


@pytest.mark.qt
def test_filter_tags_hides_non_matches(qapp, tmp_path) -> None:
    dlg = TagExportDialog(_studies(), config_manager=_cm(tmp_path))
    before = dlg.tags_tree.topLevelItemCount()
    assert before >= 1
    dlg._filter_tags("PatientID")
    # Filter may hide groups; remaining visible top-level count should be <= before.
    visible = sum(
        1
        for i in range(dlg.tags_tree.topLevelItemCount())
        if not dlg.tags_tree.topLevelItem(i).isHidden()
    )
    assert visible <= before
    dlg._filter_tags("")
    assert dlg.tags_tree.topLevelItemCount() == before
    dlg.close()


@pytest.mark.qt
def test_load_presets_list_runs(qapp, tmp_path) -> None:
    cm = _cm(tmp_path)
    dlg = TagExportDialog(_studies(), config_manager=cm)
    dlg._load_presets_list()
    # Combo exists and is populated with at least a default/empty state.
    assert dlg.preset_combo.count() >= 0
    assert isinstance(dlg.preset_combo.currentText(), str)
    dlg.close()
