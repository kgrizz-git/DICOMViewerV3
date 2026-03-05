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
    def test_default_is_false(self, tmp_path):
        assert _cm(tmp_path).get_smooth_image_when_zoomed() is False

    def test_set_true(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_smooth_image_when_zoomed(True)
        assert cm.get_smooth_image_when_zoomed() is True

    def test_set_false(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_smooth_image_when_zoomed(True)
        cm.set_smooth_image_when_zoomed(False)
        assert cm.get_smooth_image_when_zoomed() is False


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
