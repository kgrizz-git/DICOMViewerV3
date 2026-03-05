"""
Tests for MeasurementConfigMixin.

Covers measurement font size/color and line thickness/color.
"""
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestMeasurementFontSize:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_measurement_font_size() == 14

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_measurement_font_size(20)
        assert cm.get_measurement_font_size() == 20

    def test_zero_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_measurement_font_size(0)
        assert cm.get_measurement_font_size() == 14


class TestMeasurementFontColor:
    def test_default_green(self, tmp_path):
        assert _cm(tmp_path).get_measurement_font_color() == (0, 255, 0)

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_measurement_font_color(255, 0, 0)
        assert cm.get_measurement_font_color() == (255, 0, 0)

    def test_out_of_range_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_measurement_font_color(256, 0, 0)
        assert cm.get_measurement_font_color() == (0, 255, 0)


class TestMeasurementLineThickness:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_measurement_line_thickness() == 6

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_measurement_line_thickness(2)
        assert cm.get_measurement_line_thickness() == 2

    def test_zero_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_measurement_line_thickness(0)
        assert cm.get_measurement_line_thickness() == 6


class TestMeasurementLineColor:
    def test_default_green(self, tmp_path):
        assert _cm(tmp_path).get_measurement_line_color() == (0, 255, 0)

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_measurement_line_color(128, 64, 32)
        assert cm.get_measurement_line_color() == (128, 64, 32)
