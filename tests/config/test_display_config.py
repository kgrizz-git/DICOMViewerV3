"""
Tests for DisplayConfigMixin.

Verifies theme, smooth_image_when_zoomed, privacy_view, and scroll_wheel_mode.
"""
import json
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
    def test_default_is_violet(self, tmp_path):
        cm = _cm(tmp_path)
        cm.config.pop("accent")

        assert cm.get_accent() == "violet"

    def test_set_valid_accent(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_accent("violet")
        assert cm.get_accent() == "violet"

    def test_invalid_accent_ignored(self, tmp_path):
        cm = _cm(tmp_path)
        cm.set_accent("not-a-preset")
        assert cm.get_accent() == "violet"


class TestFirstRunVisualDefaults:
    """New defaults apply only when a preference was never stored."""

    def test_new_install_uses_defaults_without_writing_a_config_file(self, tmp_path):
        cm = ConfigManager(config_dir=tmp_path)

        assert cm.get_show_scale_markers() is True
        assert cm.get_toolbar_label_style() == "text_under_icon"
        assert cm.config_path.exists() is False

    def test_defaults_make_the_initial_ui_more_legible(self, tmp_path):
        cm = _cm(tmp_path)
        for key in (
            "accent",
            "show_scale_markers",
            "show_direction_labels",
            "scale_markers_color_r",
            "scale_markers_color_g",
            "scale_markers_color_b",
            "toolbar_label_style",
        ):
            cm.config.pop(key)

        assert cm.get_accent() == "violet"
        assert cm.get_show_scale_markers() is True
        assert cm.get_show_direction_labels() is True
        assert cm.get_scale_markers_color() == (255, 0, 0)
        assert cm.get_toolbar_label_style() == "text_under_icon"

    def test_stored_legacy_visual_preferences_are_preserved(self, tmp_path):
        (tmp_path / "dicom_viewer_config.json").write_text(
            json.dumps(
                {
                    "accent": "steel-blue",
                    "overlay_font_size": 10,
                    "overlay_font_variant": "Bold",
                    "roi_font_size": 12,
                    "measurement_font_size": 12,
                    "text_annotation_font_size": 12,
                    "show_scale_markers": False,
                    "show_direction_labels": False,
                    "scale_markers_color_r": 255,
                    "scale_markers_color_g": 255,
                    "scale_markers_color_b": 0,
                    "toolbar_label_style": "icon_only",
                }
            ),
            encoding="utf-8",
        )

        cm = ConfigManager(config_dir=tmp_path)

        assert cm.get_accent() == "steel-blue"
        assert cm.get_overlay_font_size() == 10
        assert cm.get_overlay_font_variant() == "Bold"
        assert cm.get_roi_font_size() == 12
        assert cm.get_measurement_font_size() == 12
        assert cm.get_text_annotation_font_size() == 12
        assert cm.get_show_scale_markers() is False
        assert cm.get_show_direction_labels() is False
        assert cm.get_scale_markers_color() == (255, 255, 0)
        assert cm.get_toolbar_label_style() == "icon_only"


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
