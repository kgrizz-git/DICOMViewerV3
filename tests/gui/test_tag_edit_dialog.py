"""Tests for TagEditDialog VR validation and accept."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
)

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
def test_edit_scope_notice_is_visible(qapp) -> None:
    dlg = TagEditDialog(tag_str="(0010,0010)", tag_name="Patient Name", vr="PN")
    notice = dlg.findChild(QLabel, "tagEditScopeNotice")
    assert notice is not None
    assert "not a de-identification workflow" in notice.text()


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
    assert isinstance(dlg.value_input, QLineEdit)
    assert dlg.value_input.isReadOnly() is True
    assert dlg.value_input.text() == "(Read-only: Complex VR type)"
    assert dlg.value_input.styleSheet() == "background-color: #f0f0f0; color: #666;"


@pytest.mark.qt
def test_create_ui_configures_float_and_bounded_integer_inputs(qapp) -> None:
    float_dialog = TagEditDialog(vr="FD", current_value=3.25)
    assert isinstance(float_dialog.value_input, QDoubleSpinBox)
    assert float_dialog.value_input.decimals() == 6
    assert float_dialog.value_input.value() == 3.25

    integer_dialog = TagEditDialog(vr="US", current_value=[42])
    assert isinstance(integer_dialog.value_input, QSpinBox)
    assert integer_dialog.value_input.minimum() == 0
    assert integer_dialog.value_input.maximum() == 65535
    assert integer_dialog.value_input.value() == 42


@pytest.mark.qt
def test_create_ui_uses_line_edit_for_unsigned_long_and_fallbacks(qapp) -> None:
    maximum_unsigned_long = 4294967295
    dialog = TagEditDialog(vr="UL", current_value=[maximum_unsigned_long])
    assert isinstance(dialog.value_input, QLineEdit)
    assert dialog.value_input.text() == str(maximum_unsigned_long)

    invalid_dialog = TagEditDialog(vr="UL", current_value="not-a-number")
    assert isinstance(invalid_dialog.value_input, QLineEdit)
    assert invalid_dialog.value_input.text() == "0"


@pytest.mark.qt
def test_create_ui_joins_string_list_values(qapp) -> None:
    dialog = TagEditDialog(vr="LO", current_value=["first", "second"])
    assert isinstance(dialog.value_input, QLineEdit)
    assert dialog.value_input.text() == "first, second"


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
