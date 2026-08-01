"""Tests for SliceSyncDialog group create/dissolve and OK signal."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from gui.dialogs.slice_sync_dialog import SliceSyncDialog


@pytest.mark.qt
def test_current_groups_reflect_initial(qapp) -> None:
    dlg = SliceSyncDialog([[0, 1]], n_windows=4)
    assert dlg.current_groups() == [[0, 1]]
    assert dlg._group_list.count() == 1


@pytest.mark.qt
def test_create_group_from_checkboxes(qapp, monkeypatch) -> None:
    dlg = SliceSyncDialog([], n_windows=4)
    dlg._checkboxes[0].setChecked(True)
    dlg._checkboxes[2].setChecked(True)
    dlg._create_group()
    assert dlg.current_groups() == [[0, 2]]
    assert all(not cb.isChecked() for cb in dlg._checkboxes)


@pytest.mark.qt
def test_create_group_warns_when_fewer_than_two(qapp, monkeypatch) -> None:
    warned: list[str] = []

    def _warn(parent, title, text):
        warned.append(title)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    dlg = SliceSyncDialog([], n_windows=4)
    dlg._checkboxes[1].setChecked(True)
    dlg._create_group()
    assert dlg.current_groups() == []
    assert warned == ["Not enough windows"]


@pytest.mark.qt
def test_dissolve_and_ok_emits_groups_changed(qapp) -> None:
    dlg = SliceSyncDialog([[0, 1], [2, 3]], n_windows=4)
    dlg._group_list.setCurrentRow(0)
    dlg._dissolve_group()
    assert dlg.current_groups() == [[2, 3]]
    emitted: list[list[list[int]]] = []
    dlg.groups_changed.connect(emitted.append)
    dlg._on_ok()
    assert emitted == [[[2, 3]]]
    assert dlg.result() == int(dlg.DialogCode.Accepted)
