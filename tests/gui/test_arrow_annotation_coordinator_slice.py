"""Focused tests for ArrowAnnotationCoordinator display with fakes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from gui.arrow_annotation_coordinator import ArrowAnnotationCoordinator
from tools.arrow_annotation_tool import ArrowAnnotationTool


@pytest.mark.qt
def test_display_arrows_for_slice(qapp) -> None:
    tool = ArrowAnnotationTool()
    tool.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()
    tool.start_arrow(QPointF(0, 0))
    tool.update_arrow(QPointF(20, 20), scene)
    item = tool.finish_arrow(scene)
    assert item is not None

    viewer = MagicMock()
    viewer.scene = scene
    coord = ArrowAnnotationCoordinator(
        arrow_annotation_tool=tool,
        image_viewer=viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord.display_arrows_for_slice("st", "se", 0)
    assert tool.get_arrows_for_slice("st", "se", 0) == [item]


@pytest.mark.qt
def test_display_noop_without_scene(qapp) -> None:
    tool = ArrowAnnotationTool()
    viewer = MagicMock()
    viewer.scene = None
    coord = ArrowAnnotationCoordinator(
        arrow_annotation_tool=tool,
        image_viewer=viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord.display_arrows_for_slice("st", "se", 0)
    assert tool.get_arrows_for_slice("st", "se", 0) == []
