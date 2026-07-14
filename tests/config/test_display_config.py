"""
Tests for DisplayConfigMixin.

Verifies theme, smooth_image_when_zoomed, privacy_view, and scroll_wheel_mode.
"""
from pathlib import Path

from utils.config_manager import ConfigManager


def _cm(tmp_path: Path) -> ConfigManager:
    cm = ConfigManager()
    cm.config_path = tmp_path / "cfg.json"
    cm.config = cm.default_config.copy()
    return cm


class TestTheme:
    def test_default_is_dark(self, tmp_path):
        assert _cm(tmp_path).get_theme() == "dark"

    def test_set_light(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_theme("light")
        assert cm.get_theme() == "light"

    def test_set_dark(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_theme("light")
        cm.set_theme("dark")
        assert cm.get_theme() == "dark"

    def test_invalid_theme_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_theme("invalid")
        assert cm.get_theme() == "dark"


class TestSmoothImageWhenZoomed:
    def test_default_is_true(self, tmp_path):
        assert _cm(tmp_path).get_smooth_image_when_zoomed() is True

    def test_missing_config_key_falls_back_to_true(self, tmp_path):
        cm = _cm(tmp_path)
        cm.config.pop("smooth_image_when_zoomed")
        assert cm.get_smooth_image_when_zoomed() is True

    def test_set_true(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_smooth_image_when_zoomed(True)
        assert cm.get_smooth_image_when_zoomed() is True

    def test_set_false(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_smooth_image_when_zoomed(True)
        cm.set_smooth_image_when_zoomed(False)
        assert cm.get_smooth_image_when_zoomed() is False


class TestAccent:
    def test_set_valid_accent(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_accent("violet")
        assert cm.get_accent() == "violet"

    def test_invalid_accent_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_accent("not-a-preset")
        assert cm.get_accent() == "steel-blue"


class TestPrivacyView:
    def test_default_is_false(self, tmp_path):
        assert _cm(tmp_path).get_privacy_view() is False

    def test_set_true(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_privacy_view(True)
        assert cm.get_privacy_view() is True


class TestScrollWheelMode:
    def test_default_is_slice(self, tmp_path):
        assert _cm(tmp_path).get_scroll_wheel_mode() == "slice"

    def test_set_zoom(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_scroll_wheel_mode("zoom")
        assert cm.get_scroll_wheel_mode() == "zoom"

    def test_invalid_mode_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_scroll_wheel_mode("invalid")
        assert cm.get_scroll_wheel_mode() == "slice"


class TestNavigatorSliceFrameCount:
    """Navigator thumbnail slice/frame count badge (display config)."""

    def test_default_true(self, tmp_path):
        assert _cm(tmp_path).get_navigator_show_slice_frame_count() is True

    def test_set_false(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_navigator_show_slice_frame_count(False)
        assert cm.get_navigator_show_slice_frame_count() is False


class TestSliceSliderSettings:
    """In-window slice/frame slider placement and direction settings."""

    def test_defaults(self, tmp_path):
        cm = _cm(tmp_path)

        assert cm.get_slice_slider_placement() == "bottom"
        assert cm.get_slice_slider_direction() == "first_at_start"

    def test_set_valid_values(self, tmp_path):
        cm = _cm(tmp_path)

        cm.set_slice_slider_placement("left")
        cm.set_slice_slider_direction("first_at_end")

        assert cm.get_slice_slider_placement() == "left"
        assert cm.get_slice_slider_direction() == "first_at_end"

    def test_invalid_values_fall_back_to_defaults(self, tmp_path):
        cm = _cm(tmp_path)
        cm.config["slice_slider_placement"] = "diagonal"
        cm.config["slice_slider_direction"] = "sideways"

        assert cm.get_slice_slider_placement() == "bottom"
        assert cm.get_slice_slider_direction() == "first_at_start"
