"""Tests for ArrowAnnotationTool start/finish/cancel and slice clear."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from tools.arrow_annotation_tool import ArrowAnnotationTool


@pytest.mark.qt
def test_finish_arrow_stores_item(qapp) -> None:
    tool = ArrowAnnotationTool()
    tool.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()
    tool.start_arrow(QPointF(0, 0))
    tool.update_arrow(QPointF(30, 40), scene)
    item = tool.finish_arrow(scene)
    assert item is not None
    assert tool.get_arrows_for_slice("st", "se", 0) == [item]


@pytest.mark.qt
def test_cancel_arrow_clears_in_progress(qapp) -> None:
    tool = ArrowAnnotationTool()
    tool.set_current_slice("st", "se", 1)
    scene = QGraphicsScene()
    tool.start_arrow(QPointF(5, 5))
    tool.update_arrow(QPointF(15, 15), scene)
    tool.cancel_arrow(scene)
    assert tool.get_arrows_for_slice("st", "se", 1) == []


@pytest.mark.qt
def test_delete_and_clear_slice(qapp) -> None:
    tool = ArrowAnnotationTool()
    tool.set_current_slice("st", "se", 2)
    scene = QGraphicsScene()
    tool.start_arrow(QPointF(0, 0))
    tool.update_arrow(QPointF(10, 10), scene)
    item = tool.finish_arrow(scene)
    assert item is not None
    tool.delete_arrow(item, scene)
    assert tool.get_arrows_for_slice("st", "se", 2) == []

    tool.start_arrow(QPointF(1, 1))
    tool.update_arrow(QPointF(20, 20), scene)
    tool.finish_arrow(scene)
    tool.clear_slice_arrows("st", "se", 2, scene)
    assert tool.get_arrows_for_slice("st", "se", 2) == []
