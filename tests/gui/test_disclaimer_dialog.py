"""Tests for DisclaimerDialog: accept/exit paths and should_show."""

from __future__ import annotations

from pathlib import Path

import pytest

from gui.dialogs.disclaimer_dialog import DisclaimerDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


@pytest.mark.qt
def test_should_show_respects_accepted_flag(qapp, tmp_path: Path) -> None:
    cm = _cm(tmp_path)
    cm.set_disclaimer_accepted(False)
    dlg = DisclaimerDialog(cm)
    assert dlg.should_show() is True

    cm.set_disclaimer_accepted(True)
    dlg2 = DisclaimerDialog(cm)
    assert dlg2.should_show() is False

    dlg3 = DisclaimerDialog(cm, force_show=True)
    assert dlg3.should_show() is True


@pytest.mark.qt
def test_accept_persists_dont_show_checkbox(qapp, tmp_path: Path) -> None:
    cm = _cm(tmp_path)
    cm.set_disclaimer_accepted(False)
    dlg = DisclaimerDialog(cm)
    dlg.dont_show_checkbox.setChecked(True)
    dlg._on_accept()
    assert dlg.result() == int(dlg.DialogCode.Accepted)
    assert dlg.dont_show_again is True
    assert cm.get_disclaimer_accepted() is True


@pytest.mark.qt
def test_accept_clears_flag_when_checkbox_unchecked(qapp, tmp_path: Path) -> None:
    cm = _cm(tmp_path)
    cm.set_disclaimer_accepted(True)
    dlg = DisclaimerDialog(cm, force_show=True)
    dlg.dont_show_checkbox.setChecked(False)
    dlg._on_accept()
    assert cm.get_disclaimer_accepted() is False


@pytest.mark.qt
def test_exit_without_force_rejects_and_clears_flag(qapp, tmp_path: Path) -> None:
    cm = _cm(tmp_path)
    cm.set_disclaimer_accepted(True)
    dlg = DisclaimerDialog(cm, force_show=False)
    dlg._on_exit()
    assert dlg.result() == int(dlg.DialogCode.Rejected)
    assert cm.get_disclaimer_accepted() is False


@pytest.mark.qt
def test_checkbox_toggled_updates_config_immediately(qapp, tmp_path: Path) -> None:
    cm = _cm(tmp_path)
    cm.set_disclaimer_accepted(False)
    dlg = DisclaimerDialog(cm)
    dlg.dont_show_checkbox.setChecked(True)
    assert cm.get_disclaimer_accepted() is True
    dlg.dont_show_checkbox.setChecked(False)
    assert cm.get_disclaimer_accepted() is False
