"""
Tests for OverlayConfigMixin.

Covers overlay mode, visibility state, custom fields, font size/color,
overlay tags (known and unknown modality), and get_all_modalities.
"""
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestOverlayMode:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_overlay_mode() == "minimal"

    def test_set_detailed(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_mode("detailed")
        assert cm.get_overlay_mode() == "detailed"

    def test_set_hidden(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_mode("hidden")
        assert cm.get_overlay_mode() == "hidden"

    def test_invalid_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_mode("invalid")
        assert cm.get_overlay_mode() == "minimal"


class TestOverlayVisibilityState:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_overlay_visibility_state() == 0

    def test_set_1(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_visibility_state(1)
        assert cm.get_overlay_visibility_state() == 1

    def test_invalid_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_visibility_state(5)
        assert cm.get_overlay_visibility_state() == 0


class TestOverlayCustomFields:
    def test_default_empty(self, tmp_path):
        assert _cm(tmp_path).get_overlay_custom_fields() == []

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_custom_fields(["FieldA", "FieldB"])
        assert cm.get_overlay_custom_fields() == ["FieldA", "FieldB"]


class TestOverlayFontSize:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_overlay_font_size() == 10

    def test_set_positive(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_font_size(14)
        assert cm.get_overlay_font_size() == 14

    def test_zero_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_font_size(0)
        assert cm.get_overlay_font_size() == 10


class TestOverlayFontColor:
    def test_default_yellow(self, tmp_path):
        assert _cm(tmp_path).get_overlay_font_color() == (255, 255, 0)

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_font_color(100, 150, 200)
        assert cm.get_overlay_font_color() == (100, 150, 200)

    def test_out_of_range_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_font_color(300, 0, 0)
        assert cm.get_overlay_font_color() == (255, 255, 0)


class TestOverlayTags:
    def test_unknown_modality_returns_defaults(self, tmp_path):
        cm = _cm(tmp_path)
        tags = cm.get_overlay_tags("UNKNOWN")
        assert "upper_left" in tags
        assert "PatientName" in tags["upper_left"]

    def test_set_and_get_known_modality(self, tmp_path):
        cm = _cm(tmp_path)
        corners = {"upper_left": ["PatientID"], "upper_right": [], "lower_left": [], "lower_right": []}
        cm.set_overlay_tags("CT", corners)
        result = cm.get_overlay_tags("CT")
        assert result["upper_left"] == ["PatientID"]

    def test_get_all_modalities_empty_by_default(self, tmp_path):
        assert _cm(tmp_path).get_all_modalities() == []

    def test_get_all_modalities_after_set(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_overlay_tags("MR", {"upper_left": [], "upper_right": [], "lower_left": [], "lower_right": []})
        cm.set_overlay_tags("CT", {"upper_left": [], "upper_right": [], "lower_left": [], "lower_right": []})
        modalities = cm.get_all_modalities()
        assert "MR" in modalities
        assert "CT" in modalities
