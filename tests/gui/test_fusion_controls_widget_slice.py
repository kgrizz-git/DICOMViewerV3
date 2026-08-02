"""Focused tests for FusionControlsWidget enable/status/offset getters."""

from __future__ import annotations

import pytest

from gui.fusion_controls_widget import FusionControlsWidget


@pytest.mark.qt
def test_construct_defaults_and_enable_toggle(qapp) -> None:
    widget = FusionControlsWidget(config_manager=None)
    assert widget.is_fusion_enabled() is False
    widget.set_fusion_enabled(True)
    assert widget.is_fusion_enabled() is True
    widget.set_fusion_enabled(False)
    assert widget.is_fusion_enabled() is False


@pytest.mark.qt
def test_opacity_threshold_colormap_and_wl(qapp) -> None:
    widget = FusionControlsWidget()
    widget.set_fusion_enabled(True)
    widget.set_overlay_window_level(400.0, 40.0)
    window, level = widget.get_overlay_window_level()
    assert window == pytest.approx(400.0)
    assert level == pytest.approx(40.0)
    widget.opacity_slider.setValue(75)
    assert widget.get_opacity() == pytest.approx(0.75)
    assert widget.get_colormap() == "hot"


@pytest.mark.qt
def test_status_set_and_clear(qapp) -> None:
    widget = FusionControlsWidget()
    widget.set_status("Aligned", severity="info")
    assert "Aligned" in widget.status_text_edit.toPlainText()
    widget.set_status("Mismatch", severity="error")
    text = widget.status_text_edit.toPlainText()
    assert "Mismatch" in text
    assert "[ERROR]" in text
    widget.clear_status()
    assert widget.status_text_edit.toPlainText() == ""


@pytest.mark.qt
def test_series_lists_and_base_display(qapp) -> None:
    widget = FusionControlsWidget()
    # API: list of (series_uid, display_name)
    widget.update_series_lists(
        [("st/se1", "Base CT"), ("st/se2", "Overlay MR")],
        current_overlay_uid="st/se2",
    )
    widget.set_base_display("Base CT")
    assert "Base CT" in widget.base_series_display.text()
    assert widget.overlay_series_combo.count() >= 2
    assert widget.get_selected_overlay_series() == "st/se2"


@pytest.mark.qt
def test_offset_and_resampling_mode(qapp) -> None:
    widget = FusionControlsWidget()
    widget.set_calculated_offset(3.0, -2.0)
    assert "X=3.0" in widget.calculated_offset_label.text()
    assert "Y=-2.0" in widget.calculated_offset_label.text()
    ox, oy = widget.get_translation_offset()
    assert ox == pytest.approx(3.0)
    assert oy == pytest.approx(-2.0)
    widget.set_resampling_mode("fast")
    assert widget.get_resampling_mode() == "fast"
    widget.set_interpolation_method("cubic")
    assert widget.get_interpolation_method() == "cubic"
    widget.reset_user_modified_offset()
    assert widget.has_user_modified_offset() is False
