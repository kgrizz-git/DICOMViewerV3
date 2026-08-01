"""Tests for MprOrientationChoiceDialog: selection and cancel behavior."""

from __future__ import annotations

import pytest
from pydicom.dataset import Dataset

from gui.dialogs.mpr_orientation_choice_dialog import MprOrientationChoiceDialog


def _ds(uid: str) -> Dataset:
    ds = Dataset()
    ds.SOPInstanceUID = uid
    return ds


@pytest.mark.qt
def test_combo_lists_groups_with_counts(qapp) -> None:
    groups = [
        ("Axial", [_ds("1"), _ds("2")]),
        ("Sagittal", [_ds("3")]),
    ]
    dlg = MprOrientationChoiceDialog(groups)
    assert dlg._combo is not None
    assert dlg._combo.count() == 2
    assert dlg._combo.itemText(0) == "Axial — 2 images"
    assert dlg._combo.itemText(1) == "Sagittal — 1 image"


@pytest.mark.qt
def test_get_selected_datasets_none_until_accepted(qapp) -> None:
    groups = [
        ("Axial", [_ds("1"), _ds("2")]),
        ("Coronal", [_ds("3"), _ds("4"), _ds("5")]),
    ]
    dlg = MprOrientationChoiceDialog(groups)
    assert dlg.get_selected_datasets() is None
    dlg._combo.setCurrentIndex(1)
    dlg.accept()
    selected = dlg.get_selected_datasets()
    assert selected is not None
    assert [d.SOPInstanceUID for d in selected] == ["3", "4", "5"]


@pytest.mark.qt
def test_get_selected_datasets_none_when_rejected(qapp) -> None:
    groups = [
        ("Axial", [_ds("1")]),
        ("Sagittal", [_ds("2")]),
    ]
    dlg = MprOrientationChoiceDialog(groups)
    dlg.reject()
    assert dlg.get_selected_datasets() is None
