"""
Tests for AnnotationConfigMixin.

Covers text annotation color/font size and arrow annotation color/size.
"""
from pathlib import Path
from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestTextAnnotation:
    def test_default_color_yellow(self, tmp_path):
        assert _cm(tmp_path).get_text_annotation_color() == (255, 255, 0)

    def test_set_color(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_text_annotation_color(100, 200, 50)
        assert cm.get_text_annotation_color() == (100, 200, 50)

    def test_out_of_range_color_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_text_annotation_color(300, 0, 0)
        assert cm.get_text_annotation_color() == (255, 255, 0)

    def test_default_font_size(self, tmp_path):
        assert _cm(tmp_path).get_text_annotation_font_size() == 12

    def test_set_font_size(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_text_annotation_font_size(16)
        assert cm.get_text_annotation_font_size() == 16

    def test_zero_font_size_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_text_annotation_font_size(0)
        assert cm.get_text_annotation_font_size() == 12


class TestArrowAnnotation:
    def test_default_color_yellow(self, tmp_path):
        assert _cm(tmp_path).get_arrow_annotation_color() == (255, 255, 0)

    def test_set_color(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_arrow_annotation_color(0, 0, 255)
        assert cm.get_arrow_annotation_color() == (0, 0, 255)

    def test_default_size(self, tmp_path):
        assert _cm(tmp_path).get_arrow_annotation_size() == 6

    def test_set_valid_size(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_arrow_annotation_size(10)
        assert cm.get_arrow_annotation_size() == 10

    def test_size_below_range_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_arrow_annotation_size(3)
        assert cm.get_arrow_annotation_size() == 6

    def test_size_above_range_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_arrow_annotation_size(31)
        assert cm.get_arrow_annotation_size() == 6
