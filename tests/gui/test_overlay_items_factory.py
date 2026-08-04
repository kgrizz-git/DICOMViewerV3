"""Tests for create_graphics_overlay_text_item factory."""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGraphicsItem

from gui.overlay_items_factory import create_graphics_overlay_text_item


@pytest.mark.qt
def test_creates_item_with_text_position_and_color(qapp) -> None:
    item = create_graphics_overlay_text_item(
        "Patient",
        10.0,
        20.0,
        (255, 0, 0),
        12,
    )
    assert item.toPlainText() == "Patient"
    assert item.pos().x() == 10.0
    assert item.pos().y() == 20.0
    assert item.defaultTextColor().red() == 255
    assert item.zValue() == 1000
    assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations


@pytest.mark.qt
def test_small_font_applies_scale_transform(qapp) -> None:
    item = create_graphics_overlay_text_item("x", 0.0, 0.0, (0, 255, 0), 3)
    # font_size < 6 uses 6pt font with scale = font_size/6
    sx = item.transform().m11()
    assert abs(sx - (3 / 6.0)) < 1e-6


@pytest.mark.qt
def test_right_align_with_text_width(qapp) -> None:
    item = create_graphics_overlay_text_item(
        "Right",
        100.0,
        0.0,
        (255, 255, 255),
        10,
        alignment=Qt.AlignmentFlag.AlignRight,
        text_width=80.0,
    )
    doc = item.document()
    assert doc is not None
    assert doc.textWidth() == 80.0
