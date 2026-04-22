"""
Tests for ROIConfigMixin.

Covers roi font size/color, line thickness/color, and default visible statistics.
"""
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestROIFontSize:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_roi_font_size() == 12

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_roi_font_size(18)
        assert cm.get_roi_font_size() == 18

    def test_zero_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_roi_font_size(0)
        assert cm.get_roi_font_size() == 12


class TestROIFontColor:
    def test_default_yellow(self, tmp_path):
        assert _cm(tmp_path).get_roi_font_color() == (255, 255, 0)

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_roi_font_color(0, 128, 255)
        assert cm.get_roi_font_color() == (0, 128, 255)

    def test_out_of_range_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_roi_font_color(-1, 0, 0)
        assert cm.get_roi_font_color() == (255, 255, 0)


class TestROILineThickness:
    def test_default(self, tmp_path):
        assert _cm(tmp_path).get_roi_line_thickness() == 3

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_roi_line_thickness(3)
        assert cm.get_roi_line_thickness() == 3

    def test_zero_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_roi_line_thickness(0)
        assert cm.get_roi_line_thickness() == 3


class TestROILineColor:
    def test_default_red(self, tmp_path):
        assert _cm(tmp_path).get_roi_line_color() == (255, 0, 0)

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_roi_line_color(10, 20, 30)
        assert cm.get_roi_line_color() == (10, 20, 30)


class TestROIDefaultVisibleStatistics:
    def test_default_contains_standard_stats(self, tmp_path):
        stats = _cm(tmp_path).get_roi_default_visible_statistics()
        for s in ["mean", "std", "min", "max", "count", "area"]:
            assert s in stats

    def test_set_and_get(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_roi_default_visible_statistics(["mean", "max"])
        assert cm.get_roi_default_visible_statistics() == ["mean", "max"]
