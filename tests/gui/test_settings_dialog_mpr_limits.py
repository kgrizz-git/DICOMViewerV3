"""MPR limits in the existing Settings dialog: pair validation, atomic persistence, rollback."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from gui.dialogs.settings_dialog import SettingsDialog
from utils.config_manager import ConfigManager


def _config(tmp_path: Path) -> ConfigManager:
    return ConfigManager(config_dir=tmp_path / "config")


@pytest.mark.qt
class TestMprLimitsControls:
    def test_defaults_load_from_config(self, qapp, tmp_path) -> None:
        dialog = SettingsDialog(_config(tmp_path))
        assert (dialog._mpr_session_cap_spin.value(), dialog._mpr_view_cap_spin.value()) == (8, 16)

    def test_the_view_limit_can_never_drop_below_the_session_limit(self, qapp, tmp_path) -> None:
        dialog = SettingsDialog(_config(tmp_path))
        dialog._mpr_session_cap_spin.setValue(20)
        assert dialog._mpr_view_cap_spin.minimum() == 20
        assert dialog._mpr_view_cap_spin.value() == 20  # pushed up, never inconsistent
        dialog._mpr_view_cap_spin.setValue(1)
        assert dialog._mpr_view_cap_spin.value() == 20

    def test_accept_persists_the_pair_in_the_regular_config_file(self, qapp, tmp_path) -> None:
        config = _config(tmp_path)
        dialog = SettingsDialog(config)
        dialog._mpr_session_cap_spin.setValue(3)
        dialog._mpr_view_cap_spin.setValue(9)

        dialog._on_accept()

        assert dialog.result() == dialog.DialogCode.Accepted
        assert ConfigManager(config_dir=tmp_path / "config").get_mpr_caps() == (3, 9)

    def test_raising_the_session_limit_above_the_old_view_limit_persists_as_a_pair(self, qapp, tmp_path) -> None:
        config = _config(tmp_path)
        dialog = SettingsDialog(config)
        dialog._mpr_session_cap_spin.setValue(30)  # old view limit was 16
        dialog._on_accept()
        assert config.get_mpr_caps() == (30, 30)

    def test_unchanged_limits_are_not_rewritten(self, qapp, tmp_path) -> None:
        dialog = SettingsDialog(_config(tmp_path))
        with patch.object(dialog.config_manager, "set_mpr_caps") as setter:
            dialog._on_accept()
        setter.assert_not_called()

    def test_a_stored_value_above_the_spin_ceiling_is_honored_not_clamped(self, qapp, tmp_path) -> None:
        config = _config(tmp_path)
        assert config.set_mpr_caps(100, 400) is True
        dialog = SettingsDialog(config)
        assert (dialog._mpr_session_cap_spin.value(), dialog._mpr_view_cap_spin.value()) == (100, 400)
        dialog._on_accept()
        assert config.get_mpr_caps() == (100, 400)

    def test_failed_save_reports_it_keeps_the_dialog_open_and_rolls_the_pair_back(self, qapp, tmp_path) -> None:
        config = _config(tmp_path)
        dialog = SettingsDialog(config)
        dialog._mpr_session_cap_spin.setValue(2)
        dialog._mpr_view_cap_spin.setValue(4)
        with (
            patch.object(config, "save_config", return_value=False),
            patch("gui.dialogs.settings_dialog.QMessageBox") as box,
        ):
            dialog._on_accept()
        box.warning.assert_called_once()
        assert dialog.result() != dialog.DialogCode.Accepted
        assert config.get_mpr_caps() == (8, 16)  # neither key changed in memory
        assert (config.config["mpr_session_cap"], config.config["mpr_view_cap"]) == (8, 16)

    def test_the_limits_live_in_normal_config_not_privacy_storage(self, qapp, tmp_path) -> None:
        config = _config(tmp_path)
        assert config.set_mpr_caps(4, 8) is True
        text = config.config_path.read_text(encoding="utf-8")
        assert "mpr_session_cap" in text and "mpr_view_cap" in text
