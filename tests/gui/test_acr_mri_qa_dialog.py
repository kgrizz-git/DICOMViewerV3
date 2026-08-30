"""Qt tests for ACR MRI options dialog echo defaults."""

from __future__ import annotations

import pytest


@pytest.mark.qt
def test_acr_mri_dialog_defaults_to_auto_highest_echo(qapp) -> None:
    """Checked 'highest echo' box means echo_number is None (runner auto-highest)."""
    from gui.dialogs.acr_mri_qa_dialog import AcrMrIQaOptionsDialog

    dlg = AcrMrIQaOptionsDialog(None)
    assert dlg._use_highest_echo.isChecked() is True
    assert "highest echo" in dlg._use_highest_echo.text().lower()
    echo, *_rest = dlg.get_options()
    assert echo is None


@pytest.mark.qt
def test_acr_mri_dialog_explicit_echo_when_highest_unchecked(qapp) -> None:
    from gui.dialogs.acr_mri_qa_dialog import AcrMrIQaOptionsDialog

    dlg = AcrMrIQaOptionsDialog(None)
    dlg._use_highest_echo.setChecked(False)
    dlg._echo_spin.setValue(2)
    echo, *_rest = dlg.get_options()
    assert echo == 2
