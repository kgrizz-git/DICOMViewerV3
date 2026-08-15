"""Coverage expansion for FusionControlsWidget — signal/control/series/status tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from gui.fusion_controls_widget import FusionControlsWidget


def _widget(cm=None):
    """Return a FusionControlsWidget wired to an offscreen QApplication."""
    return FusionControlsWidget(config_manager=cm)


def _make_cm(theme="light"):
    """Return a MagicMock config_manager with a get_theme() returning *theme*."""
    cm = MagicMock()
    cm.get_theme.return_value = theme
    return cm


class TestSignalHandlers:
    @pytest.mark.qt
    def test_enable_toggled_emits(self, qapp):
        w = _widget()
        signals = []
        w.fusion_enabled_changed.connect(lambda v: signals.append(v))
        w.enable_checkbox.setChecked(True)
        assert signals == [True]
        w.enable_checkbox.setChecked(False)
        assert signals == [True, False]

    @pytest.mark.qt
    def test_overlay_series_changed(self, qapp):
        w = _widget()
        signals = []
        w.overlay_series_changed.connect(lambda uid: signals.append(uid))
        w.update_series_lists(
            [("uid1", "Series A"), ("uid2", "Series B")],
            current_overlay_uid="uid1",
        )
        w.overlay_series_combo.setCurrentIndex(1)
        QApplication.processEvents()
        assert "uid2" in signals

    @pytest.mark.qt
    def test_overlay_series_changed_no_data(self, qapp):
        w = _widget()
        signals = []
        w.overlay_series_changed.connect(lambda uid: signals.append(uid))
        w.update_series_lists([], current_overlay_uid="")
        w._on_overlay_series_changed(0)
        assert signals == []

    @pytest.mark.qt
    def test_opacity_changed(self, qapp):
        w = _widget()
        signals = []
        w.opacity_changed.connect(lambda v: signals.append(v))
        w.opacity_slider.setValue(75)
        assert signals == [pytest.approx(0.75)]
        assert w.opacity_value_label.text() == "75%"

    @pytest.mark.qt
    def test_opacity_changed_suppressed_when_updating(self, qapp):
        w = _widget()
        signals = []
        w.opacity_changed.connect(lambda v: signals.append(v))
        w._updating = True
        w._on_opacity_changed(50)
        assert signals == []

    @pytest.mark.qt
    def test_threshold_changed(self, qapp):
        w = _widget()
        signals = []
        w.threshold_changed.connect(lambda v: signals.append(v))
        w.threshold_slider.setValue(60)
        assert signals == [pytest.approx(0.60)]
        assert w.threshold_value_label.text() == "60%"

    @pytest.mark.qt
    def test_colormap_changed(self, qapp):
        w = _widget()
        signals = []
        w.colormap_changed.connect(lambda name: signals.append(name))
        w.colormap_combo.setCurrentText("viridis")
        assert signals == ["viridis"]

    @pytest.mark.qt
    def test_colormap_changed_suppressed_when_updating(self, qapp):
        w = _widget()
        signals = []
        w.colormap_changed.connect(lambda v: signals.append(v))
        w._updating = True
        w._on_colormap_changed("jet")
        assert signals == []

    @pytest.mark.qt
    def test_overlay_wl_changed(self, qapp):
        w = _widget()
        signals = []
        w.overlay_window_level_changed.connect(lambda win, lvl: signals.append((win, lvl)))
        w.overlay_window_spinbox.setValue(1500)
        w.overlay_level_spinbox.setValue(400)
        assert (1500.0, 400.0) in signals

    @pytest.mark.qt
    def test_overlay_wl_changed_suppressed_when_updating(self, qapp):
        w = _widget()
        signals = []
        w.overlay_window_level_changed.connect(lambda win, lvl: signals.append((win, lvl)))
        w._updating = True
        w._on_overlay_wl_changed()
        assert signals == []

    @pytest.mark.qt
    def test_translation_offset_px_unit(self, qapp):
        w = _widget()
        w._offset_unit = "px"
        signals = []
        w.translation_offset_changed.connect(lambda x, y: signals.append((x, y)))
        w.x_offset_spinbox.setValue(10)
        w.y_offset_spinbox.setValue(-5)
        assert (10.0, -5.0) in signals

    @pytest.mark.qt
    def test_translation_offset_mm_unit(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.5, "pixel_spacing")
        w._offset_unit = "mm"
        signals = []
        w.translation_offset_changed.connect(lambda x, y: signals.append((x, y)))
        w.x_offset_spinbox.setValue(5)
        w.y_offset_spinbox.setValue(-3)
        assert (10.0, -6.0) in signals

    @pytest.mark.qt
    def test_translation_offset_suppressed_when_updating(self, qapp):
        w = _widget()
        signals = []
        w.translation_offset_changed.connect(lambda x, y: signals.append((x, y)))
        w._updating = True
        w._on_translation_offset_changed()
        assert signals == []

    @pytest.mark.qt
    def test_reset_offset_clicked(self, qapp):
        w = _widget()
        w._calculated_offset_x = 7.0
        w._calculated_offset_y = -4.0
        signals = []
        w.translation_offset_changed.connect(lambda x, y: signals.append((x, y)))
        w._on_reset_offset_clicked()
        assert signals == [(7.0, -4.0)]
        assert w.has_user_modified_offset() is False

    @pytest.mark.qt
    def test_resampling_mode_changed_fast(self, qapp):
        w = _widget()
        signals = []
        w.resampling_mode_changed.connect(lambda m: signals.append(m))
        w.fast_mode_radio.setChecked(True)
        w._on_resampling_mode_changed(w.fast_mode_radio)
        assert signals == ["fast"]

    @pytest.mark.qt
    def test_resampling_mode_changed_high_accuracy(self, qapp):
        w = _widget()
        signals = []
        w.resampling_mode_changed.connect(lambda m: signals.append(m))
        w._on_resampling_mode_changed(w.high_accuracy_mode_radio)
        assert signals == ["high_accuracy"]

    @pytest.mark.qt
    def test_resampling_mode_changed_unknown_button(self, qapp):
        w = _widget()
        signals = []
        w.resampling_mode_changed.connect(lambda m: signals.append(m))
        other = MagicMock()
        other.__eq__ = lambda self, other: False
        w._on_resampling_mode_changed(other)
        assert signals == []

    @pytest.mark.qt
    def test_resampling_mode_suppressed_when_updating(self, qapp):
        w = _widget()
        signals = []
        w.resampling_mode_changed.connect(lambda m: signals.append(m))
        w._updating = True
        w._on_resampling_mode_changed(w.fast_mode_radio)
        assert signals == []

    @pytest.mark.qt
    def test_interpolation_method_changed(self, qapp):
        w = _widget()
        signals = []
        w.interpolation_method_changed.connect(lambda m: signals.append(m))
        w.interpolation_combo.setCurrentText("cubic")
        assert signals == ["cubic"]

    @pytest.mark.qt
    def test_interpolation_method_suppressed_when_updating(self, qapp):
        w = _widget()
        signals = []
        w.interpolation_method_changed.connect(lambda m: signals.append(m))
        w._updating = True
        w._on_interpolation_method_changed("nearest")
        assert signals == []


class TestSetControlsEnabled:
    @pytest.mark.qt
    def test_disabled_hides_overlay_groups(self, qapp):
        w = _widget()
        w._set_controls_enabled(False)
        assert not w.overlay_series_widget.isVisible()
        assert not w.opacity_widget.isVisible()
        assert not w.threshold_widget.isVisible()
        assert not w.colormap_widget.isVisible()
        assert not w.resampling_group.isVisible()
        assert not w.window_level_widget.isVisible()
        assert not w.advanced_group.isVisible()
        assert not w.x_offset_spinbox.isEnabled()

    @pytest.mark.qt
    def test_enabled_shows_overlay_groups(self, qapp):
        w = _widget()
        w.show()
        QApplication.processEvents()
        w._set_controls_enabled(True)
        assert w.overlay_series_widget.isVisible()
        assert w.opacity_widget.isVisible()
        assert w.threshold_widget.isVisible()
        assert w.colormap_widget.isVisible()
        assert w.resampling_group.isVisible()
        assert w.window_level_widget.isVisible()
        assert w.advanced_group.isVisible()

    @pytest.mark.qt
    def test_offset_unit_combo_disabled_when_no_mm(self, qapp):
        w = _widget()
        w._set_controls_enabled(True)
        assert not w.offset_unit_combo.isEnabled()

    @pytest.mark.qt
    def test_offset_unit_combo_enabled_when_mm_available(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.5, "pixel_spacing")
        w._set_controls_enabled(True)
        assert w.offset_unit_combo.isEnabled()

    @pytest.mark.qt
    def test_offset_unit_combo_disabled_in_3d_mode(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.5, "pixel_spacing")
        w._use_3d_mode = True
        w._set_controls_enabled(True)
        assert not w.offset_unit_combo.isEnabled()


class TestSetOffsetControlsEnabled:
    @pytest.mark.qt
    def test_independent_disable(self, qapp):
        w = _widget()
        w.set_fusion_enabled(True)
        w.set_offset_controls_enabled(False)
        assert not w.x_offset_spinbox.isEnabled()
        assert not w.y_offset_spinbox.isEnabled()
        assert not w.reset_offset_button.isEnabled()

    @pytest.mark.qt
    def test_independent_enable(self, qapp):
        w = _widget()
        w.set_fusion_enabled(True)
        w.set_offset_controls_enabled(True)
        assert w.x_offset_spinbox.isEnabled()
        assert w.y_offset_spinbox.isEnabled()

    @pytest.mark.qt
    def test_noop_when_fusion_disabled(self, qapp):
        w = _widget()
        w.set_fusion_enabled(False)
        w.set_offset_controls_enabled(True)
        assert not w.x_offset_spinbox.isEnabled()

    @pytest.mark.qt
    def test_unit_combo_enable_path(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.5, "pixel_spacing")
        w.set_fusion_enabled(True)
        w.set_offset_controls_enabled(True)
        assert w.offset_unit_combo.isEnabled()

    @pytest.mark.qt
    def test_unit_combo_disable_explicit(self, qapp):
        w = _widget()
        w.set_pixel_spacing(0.5, 0.5, "pixel_spacing")
        w.set_fusion_enabled(True)
        w.set_offset_controls_enabled(False)
        assert not w.offset_unit_combo.isEnabled()

    @pytest.mark.qt
    def test_disabled_and_fusion_off_sets_status(self, qapp):
        w = _widget()
        w.set_fusion_enabled(False)
        w.set_offset_controls_enabled(False)
        text = w.status_text_edit.toPlainText()
        assert "Disabled" in text
        assert "[INFO]" in text


class TestUpdateSeriesLists:
    @pytest.mark.qt
    def test_empty_list_no_overlay(self, qapp):
        w = _widget()
        w.update_series_lists([], current_overlay_uid="")
        assert w.overlay_series_combo.count() >= 1
        assert w.overlay_series_combo.itemText(0) == "Empty - Please Select"

    @pytest.mark.qt
    def test_empty_list_with_existing_overlay(self, qapp):
        w = _widget()
        w.update_series_lists([("uid1", "S1")], current_overlay_uid="uid1")
        w.update_series_lists([], current_overlay_uid="")
        assert w.overlay_series_combo.findData("uid1") == -1

    @pytest.mark.qt
    def test_placeholder_not_inserted_when_prev_exists(self, qapp):
        w = _widget()
        w.update_series_lists([("uid1", "S1")], current_overlay_uid="uid1")
        w.update_series_lists([], current_overlay_uid="")
        assert w.overlay_series_combo.count() == 0

    @pytest.mark.qt
    def test_current_overlay_uid_restored(self, qapp):
        w = _widget()
        w.update_series_lists(
            [("uid1", "S1"), ("uid2", "S2")], current_overlay_uid="uid2"
        )
        assert w.get_selected_overlay_series() == "uid2"

    @pytest.mark.qt
    def test_prev_overlay_restored_when_not_in_new_list(self, qapp):
        w = _widget()
        w.update_series_lists([("uid1", "S1")], current_overlay_uid="uid1")
        w.update_series_lists([("uid2", "S2")], current_overlay_uid="")
        assert w.get_selected_overlay_series() == "uid2"

    @pytest.mark.qt
    def test_placeholder_index_restored(self, qapp):
        w = _widget()
        w.update_series_lists([], current_overlay_uid="")
        assert w.overlay_series_combo.currentIndex() == 0


class TestSetStatus:
    @pytest.mark.qt
    def test_info_light_theme(self, qapp):
        w = _widget(_make_cm("light"))
        w.set_status("hello", severity="info")
        assert "[INFO] hello" in w.status_text_edit.toPlainText()

    @pytest.mark.qt
    def test_warning_light_theme(self, qapp):
        w = _widget(_make_cm("light"))
        w.set_status("careful", severity="warning")
        assert "[WARNING] careful" in w.status_text_edit.toPlainText()

    @pytest.mark.qt
    def test_error_light_theme(self, qapp):
        w = _widget(_make_cm("light"))
        w.set_status("fail", severity="error")
        assert "[ERROR] fail" in w.status_text_edit.toPlainText()

    @pytest.mark.qt
    def test_info_dark_theme(self, qapp):
        w = _widget(_make_cm("dark"))
        w.set_status("hello", severity="info")
        assert "[INFO] hello" in w.status_text_edit.toPlainText()

    @pytest.mark.qt
    def test_warning_dark_theme(self, qapp):
        w = _widget(_make_cm("dark"))
        w.set_status("careful", severity="warning")
        assert "[WARNING] careful" in w.status_text_edit.toPlainText()

    @pytest.mark.qt
    def test_error_dark_theme(self, qapp):
        w = _widget(_make_cm("dark"))
        w.set_status("fail", severity="error")
        assert "[ERROR] fail" in w.status_text_edit.toPlainText()

    @pytest.mark.qt
    def test_multiple_messages_get_newlines(self, qapp):
        w = _widget()
        w.set_status("first", severity="info")
        w.set_status("second", severity="warning")
        text = w.status_text_edit.toPlainText()
        assert text.startswith("[INFO] first\n[WARNING] second")

    @pytest.mark.qt
    def test_no_config_manager_defaults_light(self, qapp):
        w = _widget(cm=None)
        w.set_status("test")
        assert "[INFO] test" in w.status_text_edit.toPlainText()


class TestClearStatus:
    @pytest.mark.qt
    def test_clear_removes_all(self, qapp):
        w = _widget()
        w.set_status("a")
        w.set_status("b")
        w.clear_status()
        assert w.status_text_edit.toPlainText() == ""

    @pytest.mark.qt
    def test_clear_when_status_text_edit_none(self, qapp):
        w = _widget()
        original = w.status_text_edit
        w.status_text_edit = None
        w.clear_status()
        w.status_text_edit = original


class TestUpdateStatusTextColors:
    @pytest.mark.qt
    def test_light_theme_info_error_warning(self, qapp):
        w = _widget(_make_cm("light"))
        w.set_status("info msg", severity="info")
        w.set_status("warn msg", severity="warning")
        w.set_status("err msg", severity="error")
        w.update_status_text_colors()
        text = w.status_text_edit.toPlainText()
        assert "[INFO]" in text
        assert "[WARNING]" in text
        assert "[ERROR]" in text

    @pytest.mark.qt
    def test_dark_theme_info_error_warning(self, qapp):
        w = _widget(_make_cm("dark"))
        w.set_status("info msg", severity="info")
        w.set_status("warn msg", severity="warning")
        w.set_status("err msg", severity="error")
        w.update_status_text_colors()
        text = w.status_text_edit.toPlainText()
        assert "[INFO]" in text
        assert "[WARNING]" in text
        assert "[ERROR]" in text

    @pytest.mark.qt
    def test_no_config_manager(self, qapp):
        w = _widget(cm=None)
        w.set_status("test", severity="info")
        w.update_status_text_colors()

    @pytest.mark.qt
    def test_no_status_text_edit(self, qapp):
        w = _widget()
        w.status_text_edit = None
        w.update_status_text_colors()

    @pytest.mark.qt
    def test_no_document(self, qapp):
        w = _widget()
        with patch.object(w.status_text_edit, "document", return_value=None):
            w.update_status_text_colors()

    @pytest.mark.qt
    def test_block_without_prefix_skipped(self, qapp):
        w = _widget()
        w.status_text_edit.setPlainText("no prefix here")
        w.update_status_text_colors()


class TestGetSelectedBaseSeries:
    @pytest.mark.qt
    def test_returns_empty(self, qapp):
        w = _widget()
        assert w.get_selected_base_series() == ""


class TestSetBaseDisplay:
    @pytest.mark.qt
    def test_with_text(self, qapp):
        w = _widget()
        w.set_base_display("My CT")
        assert w.base_series_display.text() == "My CT"
        assert "italic" not in w.base_series_display.styleSheet().lower()

    @pytest.mark.qt
    def test_with_empty_string(self, qapp):
        w = _widget()
        w.set_base_display("")
        assert w.base_series_display.text() == "Not set"
        assert "italic" in w.base_series_display.styleSheet().lower()


class TestGetThreshold:
    @pytest.mark.qt
    def test_default(self, qapp):
        w = _widget()
        assert w.get_threshold() == pytest.approx(0.20)

    @pytest.mark.qt
    def test_after_change(self, qapp):
        w = _widget()
        w.threshold_slider.setValue(80)
        assert w.get_threshold() == pytest.approx(0.80)
