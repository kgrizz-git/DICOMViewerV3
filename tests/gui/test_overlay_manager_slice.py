"""Focused tests for OverlayManager visibility/mode setters and viewport widget."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from gui.overlay_manager import OverlayManager, ViewportOverlayWidget


@pytest.mark.qt
def test_viewport_overlay_setters_and_clear(qapp) -> None:
    parent = QWidget()
    widget = ViewportOverlayWidget(parent, font_size=8)
    widget.set_corner_text("upper_left", "UL", Qt.AlignmentFlag.AlignLeft)
    widget.set_corner_text("upper_right", "UR", Qt.AlignmentFlag.AlignRight)
    widget.set_mpr_banner("MPR Axial")
    widget.set_font_size(10)
    widget.set_font_family("IBM Plex Sans")
    widget.set_font_variant("Regular")
    widget.set_font_color((0, 255, 0))
    widget.update_positions(200, 150)

    assert widget.mpr_banner_label is not None
    assert "MPR Axial" in widget.mpr_banner_label.text()
    widget.clear_all()
    assert widget.mpr_banner_label.text() == ""
    assert not widget.mpr_banner_label.isVisible()


@pytest.mark.qt
def test_overlay_manager_mode_and_visibility_cycle(qapp) -> None:
    mgr = OverlayManager(font_size=7, font_color=(255, 0, 0), config_manager=None)
    assert mgr.mode == "minimal"
    assert mgr.visibility_state == 0
    assert mgr.should_show_text_overlays() is True

    mgr.set_mode("detailed")
    assert mgr.mode == "detailed"
    mgr.set_mode("hidden")
    assert mgr.mode == "hidden"
    assert mgr.should_show_text_overlays() is False

    state1 = mgr.toggle_overlay_visibility()
    assert state1 == 1
    assert mgr.visibility_state == 1
    mgr.set_visibility_state(2)
    assert mgr.visibility_state == 2
    assert mgr.should_show_text_overlays() is False
    mgr.set_mode("minimal")
    mgr.set_visibility_state(0)
    assert mgr.should_show_text_overlays() is True


@pytest.mark.qt
def test_overlay_manager_font_privacy_and_custom_fields(qapp) -> None:
    mgr = OverlayManager()
    mgr.set_custom_fields(["PatientID", "StudyDate"])
    assert mgr.custom_fields == ["PatientID", "StudyDate"]

    mgr.set_font_size(12)
    mgr.set_font_color(10, 20, 30)
    mgr.set_font_family("Courier New")
    mgr.set_font_variant("Bold")
    assert mgr.font_size == 12
    assert mgr.font_color == (10, 20, 30)
    assert mgr.font_family == "Courier New"
    assert mgr.font_variant == "Bold"

    mgr.set_privacy_mode(True)
    assert mgr.privacy_mode is True
    mgr.set_mpr_banner("Sagittal")
    # Banner is applied when a viewport widget exists; ensure no crash without one.
    assert mgr.viewport_overlay_widget is None

    tags = mgr._corner_tags_for_current_mode("CT")
    assert isinstance(tags, dict)
    assert set(tags.keys()) >= {"upper_left", "upper_right", "lower_left", "lower_right"}


@pytest.mark.qt
def test_overlay_manager_clear_items_noop_without_scene(qapp) -> None:
    mgr = OverlayManager()
    scene = MagicMock()
    scene.items.return_value = []
    mgr.clear_overlay_items(scene)
    assert mgr.overlay_items == []
    for corner_items in mgr.corner_item_map.values():
        assert corner_items == []
