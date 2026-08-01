"""Tests for TagEditDialog VR validation and accept."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialogButtonBox, QMessageBox

from gui.dialogs.tag_edit_dialog import TagEditDialog


@pytest.mark.qt
def test_string_vr_accept_sets_new_value(qapp) -> None:
    dlg = TagEditDialog(
        tag_str="(0010,0010)",
        tag_name="Patient Name",
        vr="PN",
        current_value="DOE^JOHN",
    )
    dlg.value_input.setText("SYNTHETIC^PATIENT")
    dlg._validate_and_accept()
    assert dlg.new_value == "SYNTHETIC^PATIENT"
    assert dlg.result() == int(dlg.DialogCode.Accepted)


@pytest.mark.qt
def test_numeric_us_spinbox_accept(qapp) -> None:
    dlg = TagEditDialog(
        tag_str="(0028,0010)",
        tag_name="Rows",
        vr="US",
        current_value=64,
    )
    dlg.value_input.setValue(128)
    dlg._validate_and_accept()
    assert dlg.new_value == 128


@pytest.mark.qt
def test_read_only_sq_disables_ok(qapp) -> None:
    dlg = TagEditDialog(
        tag_str="(0008,1115)",
        tag_name="Referenced Series Sequence",
        vr="SQ",
        current_value="",
    )
    button_box = dlg.findChild(QDialogButtonBox)
    ok = button_box.button(QDialogButtonBox.StandardButton.Ok)
    assert ok is not None
    assert ok.isEnabled() is False


@pytest.mark.qt
def test_invalid_da_rejected(qapp, monkeypatch) -> None:
    warned: list[str] = []

    def _warn(parent, title, text):
        warned.append(title)
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", _warn)
    dlg = TagEditDialog(
        tag_str="(0008,0020)",
        tag_name="Study Date",
        vr="DA",
        current_value="20200101",
    )
    dlg.value_input.setText("not-a-date")
    dlg._validate_and_accept()
    assert dlg.new_value is None
    assert warned  # validation warning shown
