"""
Tests for StudyLoadConfigMixin.

Covers the study-load memory budget fraction and study-count safety cap.
"""
from pathlib import Path

from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestStudyLoadMemoryFraction:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_study_load_memory_fraction() == 0.40

    def test_round_trip(self, tmp_path):
        cm = _cm(tmp_path)
        assert cm.set_study_load_memory_fraction(0.25) is True
        assert cm.get_study_load_memory_fraction() == 0.25

    def test_clamps_low_out_of_range(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_study_load_memory_fraction(0.01)
        assert cm.get_study_load_memory_fraction() == 0.1

    def test_clamps_high_out_of_range(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_study_load_memory_fraction(0.99)
        assert cm.get_study_load_memory_fraction() == 0.9

    def test_invalid_stored_value_falls_back_to_default(self, tmp_path):
        cm = _cm(tmp_path)
        cm.config["study_load_memory_fraction"] = "not-a-number"
        assert cm.get_study_load_memory_fraction() == 0.40

    def test_persists_to_file(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_study_load_memory_fraction(0.55)
        cm2 = ConfigManager()
        cm2.config_path = cm.config_path
        cm2.config = cm2._load_config()
        assert cm2.get_study_load_memory_fraction() == 0.55


class TestStudyLoadMaxStudiesCap:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_study_load_max_studies_cap() == 20

    def test_round_trip(self, tmp_path):
        cm = _cm(tmp_path)
        assert cm.set_study_load_max_studies_cap(50) is True
        assert cm.get_study_load_max_studies_cap() == 50

    def test_clamps_low_out_of_range(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_study_load_max_studies_cap(0)
        assert cm.get_study_load_max_studies_cap() == 1

    def test_clamps_high_out_of_range(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_study_load_max_studies_cap(10000)
        assert cm.get_study_load_max_studies_cap() == 200

    def test_invalid_stored_value_falls_back_to_default(self, tmp_path):
        cm = _cm(tmp_path)
        cm.config["study_load_max_studies_cap"] = None
        assert cm.get_study_load_max_studies_cap() == 20

    def test_persists_to_file(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_study_load_max_studies_cap(30)
        cm2 = ConfigManager()
        cm2.config_path = cm.config_path
        cm2.config = cm2._load_config()
        assert cm2.get_study_load_max_studies_cap() == 30
