"""Tests for StudyIndexPassphraseWarningDialog dismiss behavior."""

from __future__ import annotations

import pytest

from gui.dialogs.study_index_passphrase_warning_dialog import (
    StudyIndexPassphraseWarningDialog,
    _credential_how_to_open,
    _credential_store_name,
)


@pytest.mark.qt
def test_dialog_title_and_default_dismiss_flag(qapp) -> None:
    dlg = StudyIndexPassphraseWarningDialog()
    assert "Encryption Key" in dlg.windowTitle()
    assert dlg.dismissed_permanently is False


@pytest.mark.qt
def test_ok_without_checkbox_leaves_dismiss_false(qapp) -> None:
    dlg = StudyIndexPassphraseWarningDialog()
    dlg._dont_show_cb.setChecked(False)
    dlg._on_ok()
    assert dlg.result() == int(dlg.DialogCode.Accepted)
    assert dlg.dismissed_permanently is False


@pytest.mark.qt
def test_ok_with_checkbox_sets_dismiss_permanently(qapp) -> None:
    dlg = StudyIndexPassphraseWarningDialog()
    dlg._dont_show_cb.setChecked(True)
    dlg._on_ok()
    assert dlg.dismissed_permanently is True


def test_credential_helpers_return_nonempty_strings() -> None:
    assert len(_credential_store_name()) > 0
    assert "DICOMViewerV3" in _credential_how_to_open()
