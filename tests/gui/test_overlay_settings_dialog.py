"""Tests for OverlaySettingsDialog apply and cancel restore."""

from __future__ import annotations

from pathlib import Path

import pytest

from gui.dialogs.overlay_settings_dialog import OverlaySettingsDialog
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


@pytest.mark.qt
def test_apply_persists_font_size(qapp, tmp_path) -> None:
    cm = _cm(tmp_path)
    original = cm.get_overlay_font_size()
    dlg = OverlaySettingsDialog(cm)
    applied: list[int] = []
    dlg.settings_applied.connect(lambda: applied.append(1))
    dlg.font_size_spinbox.setValue(max(original + 2, 14))
    dlg._apply_settings()
    assert cm.get_overlay_font_size() == dlg.font_size_spinbox.value()
    assert applied == [1]
    assert dlg.result() == int(dlg.DialogCode.Accepted)


@pytest.mark.qt
def test_reject_restores_original_font_size(qapp, tmp_path) -> None:
    cm = _cm(tmp_path)
    original = cm.get_overlay_font_size()
    dlg = OverlaySettingsDialog(cm)
    dlg.font_size_spinbox.setValue(original + 5)
    # Live change may write to config depending on wiring; reject must restore
    cm.set_overlay_font_size(original + 5)
    changed: list[int] = []
    dlg.settings_changed.connect(lambda: changed.append(1))
    dlg.reject()
    assert cm.get_overlay_font_size() == original
    assert changed  # revert refresh emitted
    assert dlg.result() == int(dlg.DialogCode.Rejected)


@pytest.mark.qt
def test_direction_labels_checkbox_roundtrip(qapp, tmp_path) -> None:
    cm = _cm(tmp_path)
    cm.set_show_direction_labels(True)
    dlg = OverlaySettingsDialog(cm)
    assert dlg.show_direction_labels_checkbox.isChecked() is True
    dlg.show_direction_labels_checkbox.setChecked(False)
    dlg._apply_settings()
    assert cm.get_show_direction_labels() is False
