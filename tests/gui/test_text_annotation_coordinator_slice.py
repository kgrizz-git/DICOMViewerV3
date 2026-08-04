"""Focused tests for TextAnnotationCoordinator display/clear with fakes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from gui.text_annotation_coordinator import TextAnnotationCoordinator
from tools.text_annotation_tool import TextAnnotationTool


@pytest.mark.qt
def test_display_annotations_for_slice_wires_callbacks(qapp) -> None:
    tool = TextAnnotationTool()
    tool.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()
    tool.start_annotation(QPointF(1, 1))
    assert tool.current_item is not None
    tool.current_item.setPlainText("hi")
    item = tool.finish_annotation(scene)
    assert item is not None

    viewer = MagicMock()
    viewer.scene = scene
    coord = TextAnnotationCoordinator(
        text_annotation_tool=tool,
        image_viewer=viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord.display_annotations_for_slice("st", "se", 0)
    assert item.on_moved_callback == coord._on_text_annotation_moved


@pytest.mark.qt
def test_display_noop_without_scene(qapp) -> None:
    tool = TextAnnotationTool()
    viewer = MagicMock()
    viewer.scene = None
    coord = TextAnnotationCoordinator(
        text_annotation_tool=tool,
        image_viewer=viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord.display_annotations_for_slice("st", "se", 0)
    assert tool.get_annotations_for_slice("st", "se", 0) == []
