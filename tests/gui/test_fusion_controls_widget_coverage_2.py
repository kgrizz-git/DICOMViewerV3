"""Coverage expansion for FusionControlsWidget — offset/resampling/pixel-spacing tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from gui.fusion_controls_widget import FusionControlsWidget


def _widget(cm=None):
    return FusionControlsWidget(config_manager=cm)


class TestSetCalculatedOffset:
    @pytest.mark.qt
    def test_basic(self, qapp):
        w = _widget()
        w.set_calculated_offset(10.0, -5.0)
        assert w._calculated_offset_x == 10.0
        assert w._calculated_offset_y == -5.0
        assert "X=10.0" in w.calculated_offset_label.text()
        assert "Y=-5.0" in w.calculated_offset_label.text()

    @pytest.mark.qt
    def test_user_modified_not_overwritten(self, qapp):
        w = _widget()
        w._user_modified_offset = True
        w.x_offset_spinbox.setValue(99)
        w.y_offset_spinbox.setValue(-1)
        w.set_calculated_offset(5.0, 3.0)
        assert w.x_offset_spinbox.value() == 99

    @pytest.mark.qt
    def test_not_user_modified_updates_spinboxes(self, qapp):
        w = _widget()
        w.set_pixel_spacing(1.0, 1.0, "test")
        w._offset_unit = "px"
        w.set_calculated_offset(20.0, -10.0)
        assert w.x_offset_spinbox.value() == 20
        assert w.y_offset_spinbox.value() == -10

    @pytest.mark.qt
    def test_debug_offset_enabled(self, qapp):
        w = _widget()
        with patch("gui.fusion_controls_widget.DEBUG_OFFSET", True):
            w.set_calculated_offset(5.0, 3.0)


class TestSetScalingFactors:
    @pytest.mark.qt
    def test_basic(self, qapp):
        w = _widget()
        w.set_scaling_factors(1.5, 2.0)
        text = w.scaling_factors_label.text()
        assert "X=1.50" in text
        assert "Y=2.00" in text


class TestGetTranslationOffset:
    @pytest.mark.qt
    def test_px_unit(self, qapp):
        w = _widget()
        w._offset_unit = "px"
        w.x_offset_spinbox.setValue(7)
        w.y_offset_spinbox.setValue(-3)
        x, y = w.get_translation_offset()
        assert x == pytest.approx(7.0)
        assert y == pytest.approx(-3.0)

    @pytest.mark.qt
    def test_mm_unit(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.25, "pixel_spacing")
        w._offset_unit = "mm"
        w.x_offset_spinbox.setValue(4)
        w.y_offset_spinbox.setValue(2)
        x, y = w.get_translation_offset()
        assert x == pytest.approx(16.0)
        assert y == pytest.approx(4.0)


class TestPixelMmConversion:
    @pytest.mark.qt
    def test_set_pixel_spacing(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.75, "pixel_spacing")
        assert w._row_spacing_mm == 0.5
        assert w._col_spacing_mm == 0.75
        assert w._spacing_source == "pixel_spacing"
        assert w._can_use_mm is True

    @pytest.mark.qt
    def test_set_pixel_spacing_none(self, qapp):
        w = _widget()
        w.set_pixel_spacing(None, None, None)
        assert w._can_use_mm is False

    @pytest.mark.qt
    def test_set_pixel_spacing_partial_none(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, None, "test")
        assert w._can_use_mm is False

    @pytest.mark.qt
    def test_mm_unavailable_forces_px_unit(self, qapp):
        w = _widget()
        w._offset_unit = "mm"
        w.set_pixel_spacing(0.5, 0.5, "test")
        w.set_pixel_spacing(None, None, None)
        assert w._offset_unit == "px"
        assert w.offset_unit_combo.currentText() == "px"

    @pytest.mark.qt
    def test_pixels_to_mm(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.25, "test")
        x_mm, y_mm = w._pixels_to_mm(4.0, 8.0)
        assert x_mm == pytest.approx(1.0)
        assert y_mm == pytest.approx(4.0)

    @pytest.mark.qt
    def test_pixels_to_mm_no_spacing(self, qapp):
        w = _widget()
        w._can_use_mm = False
        x_mm, y_mm = w._pixels_to_mm(4.0, 8.0)
        assert x_mm == 4.0
        assert y_mm == 8.0

    @pytest.mark.qt
    def test_mm_to_pixels(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.25, "test")
        x_px, y_px = w._mm_to_pixels(2.0, 4.0)
        assert x_px == pytest.approx(8.0)
        assert y_px == pytest.approx(8.0)

    @pytest.mark.qt
    def test_mm_to_pixels_no_spacing(self, qapp):
        w = _widget()
        w._can_use_mm = False
        x_px, y_px = w._mm_to_pixels(2.0, 4.0)
        assert x_px == 2.0
        assert y_px == 4.0

    @pytest.mark.qt
    def test_on_offset_unit_changed_mm(self, qapp):
        w = _widget()
        w.set_pixel_spacing(1.0, 1.0, "test")
        w.set_calculated_offset(10.0, 5.0)
        w._on_offset_unit_changed("mm")
        assert w._offset_unit == "mm"

    @pytest.mark.qt
    def test_on_offset_unit_changed_px(self, qapp):
        w = _widget()
        w._on_offset_unit_changed("px")
        assert w._offset_unit == "px"

    @pytest.mark.qt
    def test_on_offset_unit_changed_invalid(self, qapp):
        w = _widget()
        original = w._offset_unit
        w._on_offset_unit_changed("cm")
        assert w._offset_unit == original

    @pytest.mark.qt
    def test_update_offset_spinboxes_from_pixels_px(self, qapp):
        w = _widget()
        w._calculated_offset_x = 15.0
        w._calculated_offset_y = -8.0
        w._offset_unit = "px"
        w._update_offset_spinboxes_from_pixels()
        assert w.x_offset_spinbox.value() == 15
        assert w.y_offset_spinbox.value() == -8

    @pytest.mark.qt
    def test_update_offset_spinboxes_from_pixels_mm(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.5, "test")
        w._calculated_offset_x = 10.0
        w._calculated_offset_y = 4.0
        w._offset_unit = "mm"
        w._update_offset_spinboxes_from_pixels()
        assert w.x_offset_spinbox.value() == 5
        assert w.y_offset_spinbox.value() == 2

    @pytest.mark.qt
    def test_offset_combo_changed_triggers_update(self, qapp):
        w = _widget()
        w.set_pixel_spacing(1.0, 1.0, "test")
        w.set_calculated_offset(10.0, 5.0)
        w.offset_unit_combo.setCurrentText("px")
        QApplication.processEvents()

    @pytest.mark.qt
    def test_spacing_info_label_with_mm(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.75, "pixel_spacing")
        assert "0.500" in w.spacing_info_label.text()
        assert "0.750" in w.spacing_info_label.text()
        assert "pixel_spacing" in w.spacing_info_label.text()

    @pytest.mark.qt
    def test_spacing_info_label_without_mm(self, qapp):
        w = _widget()
        w.set_pixel_spacing(None, None, None)
        assert "pixels only" in w.spacing_info_label.text()


class TestGetResamplingMode:
    @pytest.mark.qt
    def test_fast(self, qapp):
        w = _widget()
        w.fast_mode_radio.setChecked(True)
        assert w.get_resampling_mode() == "fast"

    @pytest.mark.qt
    def test_high_accuracy(self, qapp):
        w = _widget()
        w.high_accuracy_mode_radio.setChecked(True)
        assert w.get_resampling_mode() == "high_accuracy"

    @pytest.mark.qt
    def test_default_fallback(self, qapp):
        w = _widget()
        w.fast_mode_radio.setChecked(False)
        w.high_accuracy_mode_radio.setChecked(False)
        assert w.get_resampling_mode() == "high_accuracy"


class TestSetResamplingMode:
    @pytest.mark.qt
    def test_fast(self, qapp):
        w = _widget()
        w.set_resampling_mode("fast")
        assert w.fast_mode_radio.isChecked()
        assert w.get_resampling_mode() == "fast"

    @pytest.mark.qt
    def test_high_accuracy(self, qapp):
        w = _widget()
        w.set_resampling_mode("high_accuracy")
        assert w.high_accuracy_mode_radio.isChecked()

    @pytest.mark.qt
    def test_unknown_defaults_high_accuracy(self, qapp):
        w = _widget()
        w.set_resampling_mode("bogus")
        assert w.high_accuracy_mode_radio.isChecked()


class TestSetInterpolationMethod:
    @pytest.mark.qt
    def test_valid_method(self, qapp):
        w = _widget()
        w.set_interpolation_method("cubic")
        assert w.get_interpolation_method() == "cubic"

    @pytest.mark.qt
    def test_invalid_method_unchanged(self, qapp):
        w = _widget()
        original = w.get_interpolation_method()
        w.set_interpolation_method("nonexistent")
        assert w.get_interpolation_method() == original


class TestSetResamplingStatus:
    @pytest.mark.qt
    def test_show_warning(self, qapp):
        w = _widget()
        w.show()
        QApplication.processEvents()
        w.resampling_group.setVisible(True)
        w.set_resampling_status("Fast", "reason", show_warning=True, warning_text="Watch out")
        assert w.resampling_warning_label.text() == "Watch out"
        assert w.resampling_warning_label.isVisible()

    @pytest.mark.qt
    def test_hide_warning(self, qapp):
        w = _widget()
        w.set_resampling_status("Fast", "reason", show_warning=True, warning_text="Warn")
        w.set_resampling_status("Fast", "reason", show_warning=False)
        assert not w.resampling_warning_label.isVisible()

    @pytest.mark.qt
    def test_empty_warning_text_hides(self, qapp):
        w = _widget()
        w.set_resampling_status("Fast", "reason", show_warning=True, warning_text="")
        assert not w.resampling_warning_label.isVisible()

    @pytest.mark.qt
    def test_warning_false_hides(self, qapp):
        w = _widget()
        w.set_resampling_status("Fast", "reason", show_warning=False, warning_text="text")
        assert not w.resampling_warning_label.isVisible()


class TestSetOffsetStatusText:
    @pytest.mark.qt
    def test_3d_mode_text(self, qapp):
        w = _widget()
        w.set_offset_status_text(True)
        assert "3D Fusion" in w.spacing_info_label.text()
        assert w._use_3d_mode is True
        assert not w.offset_unit_combo.isEnabled()

    @pytest.mark.qt
    def test_2d_mode_text_with_mm(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.75, "fov_rows")
        w.set_offset_status_text(False)
        assert "0.500" in w.spacing_info_label.text()
        assert "fov_rows" in w.spacing_info_label.text()
        assert w.offset_unit_combo.isEnabled()

    @pytest.mark.qt
    def test_2d_mode_text_without_mm(self, qapp):
        w = _widget()
        w.set_offset_status_text(False)
        assert "pixels only" in w.spacing_info_label.text()

    @pytest.mark.qt
    def test_no_spacing_info_label(self, qapp):
        w = _widget()
        del w.spacing_info_label
        w.set_offset_status_text(True)


class TestUserModifiedOffset:
    @pytest.mark.qt
    def test_set_clear_cycle(self, qapp):
        w = _widget()
        assert w.has_user_modified_offset() is False
        w.x_offset_spinbox.setValue(5)
        assert w.has_user_modified_offset() is True
        w.reset_user_modified_offset()
        assert w.has_user_modified_offset() is False

    @pytest.mark.qt
    def test_reset_flag_in_calculated_offset(self, qapp):
        w = _widget()
        w._user_modified_offset = True
        w.set_calculated_offset(10.0, 5.0)
        assert w.has_user_modified_offset() is True


class TestColormapInitial:
    @pytest.mark.qt
    def test_default_colormap(self, qapp):
        w = _widget()
        assert w.colormap_combo.currentText() == "hot"

    @pytest.mark.qt
    def test_all_colormaps_present(self, qapp):
        w = _widget()
        items = [w.colormap_combo.itemText(i) for i in range(w.colormap_combo.count())]
        assert items == ["hot", "jet", "viridis", "plasma", "inferno", "rainbow", "cool", "spring"]


class TestSliderDefaults:
    @pytest.mark.qt
    def test_opacity_default(self, qapp):
        w = _widget()
        assert w.opacity_slider.value() == 50
        assert w.opacity_value_label.text() == "50%"

    @pytest.mark.qt
    def test_threshold_default(self, qapp):
        w = _widget()
        assert w.threshold_slider.value() == 20
        assert w.threshold_value_label.text() == "20%"
