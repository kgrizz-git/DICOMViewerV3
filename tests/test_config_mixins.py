"""
Unit tests for the small config mixins: AppConfigMixin, CineConfigMixin,
MetadataUIConfigMixin, MeasurementConfigMixin.

Each mixin expects a host providing ``self.config`` (dict) and
``self.save_config()``; a minimal ``_Host`` stands in for ConfigManager.
"""

from __future__ import annotations

from utils.config.app_config import AppConfigMixin
from utils.config.cine_config import CineConfigMixin
from utils.config.measurement_config import MeasurementConfigMixin
from utils.config.metadata_ui_config import MetadataUIConfigMixin


def _make_host(mixin_cls):
    class _Host(mixin_cls):
        def __init__(self):
            self.config = {}
            self.save_calls = 0

        def save_config(self):
            self.save_calls += 1

    return _Host()


class TestAppConfigMixin:
    def test_default_disclaimer_not_accepted(self):
        host = _make_host(AppConfigMixin)
        assert host.get_disclaimer_accepted() is False

    def test_set_disclaimer_accepted_persists_and_saves(self):
        host = _make_host(AppConfigMixin)
        host.set_disclaimer_accepted(True)
        assert host.get_disclaimer_accepted() is True
        assert host.save_calls == 1


class TestCineConfigMixin:
    def test_defaults(self):
        host = _make_host(CineConfigMixin)
        assert host.get_cine_default_speed() == 1.0
        assert host.get_cine_default_loop() is True

    def test_set_speed_and_loop(self):
        host = _make_host(CineConfigMixin)
        host.set_cine_default_speed(2.0)
        host.set_cine_default_loop(False)
        assert host.get_cine_default_speed() == 2.0
        assert host.get_cine_default_loop() is False
        assert host.save_calls == 2


class TestMetadataUIConfigMixin:
    def test_defaults(self):
        host = _make_host(MetadataUIConfigMixin)
        assert host.get_metadata_panel_column_widths() == [100, 200, 50, 200]
        assert host.get_metadata_panel_column_order() == [0, 1, 2, 3]

    def test_set_widths_and_order(self):
        host = _make_host(MetadataUIConfigMixin)
        host.set_metadata_panel_column_widths([120, 220, 60, 220])
        host.set_metadata_panel_column_order([1, 0, 2, 3])
        assert host.get_metadata_panel_column_widths() == [120, 220, 60, 220]
        assert host.get_metadata_panel_column_order() == [1, 0, 2, 3]
        assert host.save_calls == 2


class TestMeasurementConfigMixin:
    def test_font_size_defaults_and_set(self):
        host = _make_host(MeasurementConfigMixin)
        assert host.get_measurement_font_size() == 12
        host.set_measurement_font_size(16)
        assert host.get_measurement_font_size() == 16

    def test_set_font_size_ignores_non_positive(self):
        host = _make_host(MeasurementConfigMixin)
        host.set_measurement_font_size(0)
        host.set_measurement_font_size(-5)
        assert host.get_measurement_font_size() == 12
        assert host.save_calls == 0

    def test_font_color_defaults_and_set(self):
        host = _make_host(MeasurementConfigMixin)
        assert host.get_measurement_font_color() == (0, 255, 0)
        host.set_measurement_font_color(255, 128, 0)
        assert host.get_measurement_font_color() == (255, 128, 0)

    def test_set_font_color_ignores_out_of_range(self):
        host = _make_host(MeasurementConfigMixin)
        host.set_measurement_font_color(256, 0, 0)
        host.set_measurement_font_color(0, -1, 0)
        assert host.get_measurement_font_color() == (0, 255, 0)
        assert host.save_calls == 0

    def test_line_thickness_defaults_and_set(self):
        host = _make_host(MeasurementConfigMixin)
        assert host.get_measurement_line_thickness() == 3
        host.set_measurement_line_thickness(5)
        assert host.get_measurement_line_thickness() == 5

    def test_set_line_thickness_ignores_non_positive(self):
        host = _make_host(MeasurementConfigMixin)
        host.set_measurement_line_thickness(0)
        assert host.get_measurement_line_thickness() == 3
        assert host.save_calls == 0

    def test_line_color_defaults_and_set(self):
        host = _make_host(MeasurementConfigMixin)
        assert host.get_measurement_line_color() == (0, 255, 0)
        host.set_measurement_line_color(10, 20, 30)
        assert host.get_measurement_line_color() == (10, 20, 30)

    def test_set_line_color_ignores_out_of_range(self):
        host = _make_host(MeasurementConfigMixin)
        host.set_measurement_line_color(300, 0, 0)
        assert host.get_measurement_line_color() == (0, 255, 0)
        assert host.save_calls == 0

    def test_font_family_default_and_set(self):
        host = _make_host(MeasurementConfigMixin)
        assert host.get_measurement_font_family() == "IBM Plex Sans"
        host.set_measurement_font_family("Noto Sans")
        assert host.get_measurement_font_family() == "Noto Sans"

    def test_set_font_family_ignores_unknown_family(self):
        host = _make_host(MeasurementConfigMixin)
        host.set_measurement_font_family("Not A Real Font")
        assert host.get_measurement_font_family() == "IBM Plex Sans"
        assert host.save_calls == 0

    def test_font_variant_default_and_set(self):
        host = _make_host(MeasurementConfigMixin)
        assert host.get_measurement_font_variant() == "Bold"
        host.set_measurement_font_variant("Regular")
        assert host.get_measurement_font_variant() == "Regular"

    def test_set_font_variant_ignores_unknown_variant(self):
        host = _make_host(MeasurementConfigMixin)
        host.set_measurement_font_variant("NotAVariant")
        assert host.get_measurement_font_variant() == "Bold"
        assert host.save_calls == 0
