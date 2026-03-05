"""
Tests for AppConfigMixin.

Covers the disclaimer_accepted flag.
"""
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestDisclaimerAccepted:
    def test_default_false(self, tmp_path):
        assert _cm(tmp_path).get_disclaimer_accepted() is False

    def test_set_true(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_disclaimer_accepted(True)
        assert cm.get_disclaimer_accepted() is True

    def test_set_false(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_disclaimer_accepted(True)
        cm.set_disclaimer_accepted(False)
        assert cm.get_disclaimer_accepted() is False

    def test_persists_to_file(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_disclaimer_accepted(True)
        cm2 = ConfigManager()
        cm2.config_path = cm.config_path
        cm2.config = cm2._load_config()
        assert cm2.get_disclaimer_accepted() is True
