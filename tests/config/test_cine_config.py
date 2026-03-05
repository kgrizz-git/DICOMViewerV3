"""
Tests for CineConfigMixin.

Covers cine default speed and loop setting.
"""
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestCineDefaultSpeed:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_cine_default_speed() == 1.0

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_cine_default_speed(2.0)
        assert cm.get_cine_default_speed() == 2.0

    def test_fractional_speed(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_cine_default_speed(0.25)
        assert cm.get_cine_default_speed() == 0.25


class TestCineDefaultLoop:
    def test_default_true(self, tmp_path):
        assert _cm(tmp_path).get_cine_default_loop() is True

    def test_set_false(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_cine_default_loop(False)
        assert cm.get_cine_default_loop() is False

    def test_set_true_again(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_cine_default_loop(False)
        cm.set_cine_default_loop(True)
        assert cm.get_cine_default_loop() is True
