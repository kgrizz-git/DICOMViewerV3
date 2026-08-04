"""Tests for TextAnnotationTool slice storage and finish/cancel.

finish_annotation ignores the initial_text arg and requires non-empty
plain text already on current_item (empty text cancels).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from tools.text_annotation_tool import TextAnnotationTool


def _finish_with_text(tool: TextAnnotationTool, scene: QGraphicsScene, text: str):
    assert tool.current_item is not None
    tool.current_item.setPlainText(text)
    return tool.finish_annotation(scene)


@pytest.mark.qt
def test_finish_annotation_stores_item(qapp) -> None:
    tool = TextAnnotationTool()
    tool.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()
    tool.start_annotation(QPointF(15, 25))
    item = _finish_with_text(tool, scene, "note")
    assert item is not None
    assert item.toPlainText() == "note"
    assert tool.get_annotations_for_slice("st", "se", 0) == [item]


@pytest.mark.qt
def test_finish_empty_text_cancels(qapp) -> None:
    tool = TextAnnotationTool()
    tool.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()
    tool.start_annotation(QPointF(0, 0))
    item = tool.finish_annotation(scene)  # empty → None
    assert item is None
    assert tool.get_annotations_for_slice("st", "se", 0) == []


@pytest.mark.qt
def test_cancel_annotation_leaves_slice_empty(qapp) -> None:
    tool = TextAnnotationTool()
    tool.set_current_slice("st", "se", 1)
    scene = QGraphicsScene()
    tool.start_annotation(QPointF(0, 0))
    tool.cancel_annotation(scene)
    assert tool.get_annotations_for_slice("st", "se", 1) == []


@pytest.mark.qt
def test_delete_annotation_removes_from_slice(qapp) -> None:
    tool = TextAnnotationTool()
    tool.set_current_slice("st", "se", 2)
    scene = QGraphicsScene()
    tool.start_annotation(QPointF(3, 4))
    item = _finish_with_text(tool, scene, "x")
    assert item is not None
    tool.delete_annotation(item, scene)
    assert tool.get_annotations_for_slice("st", "se", 2) == []


@pytest.mark.qt
def test_clear_slice_annotations(qapp) -> None:
    tool = TextAnnotationTool()
    tool.set_current_slice("st", "se", 3)
    scene = QGraphicsScene()
    tool.start_annotation(QPointF(1, 1))
    _finish_with_text(tool, scene, "a")
    tool.start_annotation(QPointF(2, 2))
    _finish_with_text(tool, scene, "b")
    assert len(tool.get_annotations_for_slice("st", "se", 3)) == 2
    tool.clear_slice_annotations("st", "se", 3, scene)
    assert tool.get_annotations_for_slice("st", "se", 3) == []
