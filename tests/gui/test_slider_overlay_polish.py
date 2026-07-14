"""Focused tests for the in-window slice/frame slider polish."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt

from gui.edge_reveal_slider_overlay import EdgeRevealSliderOverlay
from gui.image_viewer import ImageViewer


@pytest.mark.qt
def test_overlay_placement_direction_updates_orientation_cursor_without_embedded_label(qapp) -> None:
    viewer = ImageViewer()
    overlay = EdgeRevealSliderOverlay(parent=viewer.viewport())

    overlay.configure("left", "first_at_end")
    overlay.set_range_and_value(1, 12, 3, "Frame")

    assert overlay.placement() == "left"
    assert overlay.direction() == "first_at_end"
    assert overlay.slider_orientation() == Qt.Orientation.Vertical
    assert overlay.slider_cursor_shape() == Qt.CursorShape.SizeVerCursor
    assert overlay.label_text() == ""


@pytest.mark.qt
def test_viewer_repositions_bottom_slider_to_centered_fifty_percent(qapp) -> None:
    viewer = ImageViewer()
    viewer.resize(500, 300)
    viewer.set_slice_slider_options("bottom", "first_at_start")
    viewer.set_navigation_slider_state(enabled=True, minimum=1, maximum=20, value=4)

    geometry = viewer._slider_overlay.geometry()
    assert geometry.width() == pytest.approx(viewer.viewport().width() * 0.5, abs=2)
    assert geometry.center().x() == pytest.approx(viewer.viewport().rect().center().x(), abs=2)
    assert geometry.bottom() == viewer.viewport().height() - 1


@pytest.mark.qt
def test_viewer_repositions_left_slider_to_centered_height(qapp) -> None:
    viewer = ImageViewer()
    viewer.resize(500, 300)
    viewer.set_slice_slider_options("left", "first_at_end")
    viewer.set_navigation_slider_state(enabled=True, minimum=1, maximum=20, value=4)

    geometry = viewer._slider_overlay.geometry()
    assert geometry.height() == pytest.approx(viewer.viewport().height() * 0.5, abs=2)
    assert geometry.center().y() == pytest.approx(viewer.viewport().rect().center().y(), abs=2)
    assert geometry.left() == 0


@pytest.mark.qt
def test_inverted_slider_still_calls_navigation_callback_with_logical_index(qapp) -> None:
    viewer = ImageViewer()
    calls: list[int] = []
    viewer.slider_navigate_callback = calls.append
    viewer.set_slice_slider_options("top", "first_at_end")
    viewer.set_navigation_slider_state(enabled=True, minimum=1, maximum=5, value=3)

    viewer._slider_overlay._slider.setValue(1)

    assert calls == [0]
