"""Tests for MprDicomSaveDialog option collection."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

from gui.dialogs.mpr_dicom_save_dialog import MprDicomSaveDialog


@pytest.mark.qt
def test_build_options_defaults(qapp) -> None:
    dlg = MprDicomSaveDialog(orientation_label="Sagittal")
    opts = dlg.build_options("Sagittal")
    assert opts.orientation_label == "Sagittal"
    assert opts.series_description_suffix == ""
    assert opts.anonymize is False
    assert opts.use_rescaled_pixel_values is True


@pytest.mark.qt
def test_build_options_reflects_field_edits(qapp) -> None:
    dlg = MprDicomSaveDialog(orientation_label="Axial")
    dlg._suffix.setText("  MPR-test  ")
    dlg._anonymize.setChecked(True)
    dlg._rescaled.setChecked(False)
    opts = dlg.build_options("Axial")
    assert opts.series_description_suffix == "MPR-test"
    assert opts.anonymize is True
    assert opts.use_rescaled_pixel_values is False


@pytest.mark.qt
def test_orientation_label_appears_in_info(qapp) -> None:
    dlg = MprDicomSaveDialog(orientation_label="Coronal")
    texts = [lab.text() for lab in dlg.findChildren(QLabel)]
    assert any("Orientation: Coronal" in t for t in texts)
