"""
Tests for the "Study Load Memory Budget" controls in SettingsDialog.

Covers: default values loaded from config, round-trip persistence on
accept, and the computed budget preview label.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.study_cache import get_total_system_memory_mb
from gui.dialogs.settings_dialog import SettingsDialog
from utils.config_manager import ConfigManager


def _config(tmp_path: Path) -> ConfigManager:
    return ConfigManager(config_dir=tmp_path / "config")


@pytest.mark.qt
def test_defaults_loaded_from_config(qapp, tmp_path: Path) -> None:
    config = _config(tmp_path)
    dialog = SettingsDialog(config)

    assert dialog._memory_fraction_spin.value() == 40
    assert dialog._max_studies_cap_spin.value() == 20


@pytest.mark.qt
def test_accept_persists_changed_values(qapp, tmp_path: Path) -> None:
    config = _config(tmp_path)
    dialog = SettingsDialog(config)

    dialog._memory_fraction_spin.setValue(25)
    dialog._max_studies_cap_spin.setValue(35)
    dialog._on_accept()

    assert config.get_study_load_memory_fraction() == 0.25
    assert config.get_study_load_max_studies_cap() == 35


@pytest.mark.qt
def test_fraction_spin_is_clamped_to_configured_range(qapp, tmp_path: Path) -> None:
    config = _config(tmp_path)
    dialog = SettingsDialog(config)

    # QSpinBox itself enforces the widget range; verify it matches the
    # config mixin's validated range so the UI can't produce an
    # out-of-range value in the first place.
    assert dialog._memory_fraction_spin.minimum() == 10
    assert dialog._memory_fraction_spin.maximum() == 90


@pytest.mark.qt
def test_budget_preview_reflects_fraction_and_total_ram(qapp, tmp_path: Path) -> None:
    config = _config(tmp_path)
    dialog = SettingsDialog(config)

    total_ram_mb = get_total_system_memory_mb()
    if total_ram_mb <= 0.0:
        pytest.skip("total system RAM could not be determined on this platform")

    dialog._memory_fraction_spin.setValue(50)
    expected_budget_gb = max(0.50 * total_ram_mb, 1024.0) / 1024.0
    assert f"{expected_budget_gb:.1f}" in dialog._memory_budget_preview.text()
