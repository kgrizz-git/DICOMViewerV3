"""
Characterize Measurement / Text / Arrow / Crosshair undo-redo command contracts.

Covers add→undo, remove→undo→redo, duplicate prevention, and the measurement /
crosshair text-item side effects that helper extraction must preserve.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem

from tools.text_annotation_tool import TextAnnotationItem
from utils.undo_redo import (
    ArrowAnnotationCommand,
    CrosshairCommand,
    MeasurementCommand,
    TextAnnotationCommand,
    UndoRedoManager,
)

KEY = ("study", "series", 0)


class _MeasurementStub(QGraphicsRectItem):
    """Scene-capable stand-in for MeasurementItem with text and handle hooks."""

    def __init__(self) -> None:
        super().__init__(0.0, 0.0, 20.0, 10.0)
        self.text_item = QGraphicsTextItem("10.0 mm")
        self.hide_handles = MagicMock()
        self.update_distance = MagicMock()


class _CrosshairStub(QGraphicsRectItem):
    """Scene-capable stand-in for CrosshairItem with a mark_deleted text item."""

    def __init__(self) -> None:
        super().__init__(0.0, 0.0, 12.0, 12.0)
        text = QGraphicsTextItem("x")
        text.mark_deleted = MagicMock()
        self.text_item = text


def _measurement_tool() -> MagicMock:
    tool = MagicMock()
    tool.measurements = {}
    return tool


def _text_tool() -> MagicMock:
    tool = MagicMock()
    tool.annotations = {}
    return tool


def _arrow_tool() -> MagicMock:
    tool = MagicMock()
    tool.arrows = {}
    return tool


def _crosshair_manager() -> MagicMock:
    manager = MagicMock()
    manager.crosshairs = {}
    return manager


@pytest.mark.qt
def test_measurement_add_then_undo_and_no_duplicate(qapp) -> None:
    scene = QGraphicsScene()
    tool = _measurement_tool()
    item = _MeasurementStub()
    history = UndoRedoManager()

    history.execute_command(
        MeasurementCommand(tool, "add", item, scene, *KEY)
    )
    assert item in tool.measurements[KEY]
    assert item.scene() is scene
    assert item.text_item.scene() is scene

    # Second add must not duplicate.
    MeasurementCommand(tool, "add", item, scene, *KEY).execute()
    assert tool.measurements[KEY] == [item]

    history.undo()
    assert item not in tool.measurements[KEY]
    assert item.scene() is None
    assert item.text_item.scene() is None
    item.hide_handles.assert_called()


@pytest.mark.qt
def test_measurement_remove_undo_redo_refreshes_distance(qapp) -> None:
    scene = QGraphicsScene()
    tool = _measurement_tool()
    item = _MeasurementStub()
    scene.addItem(item)
    scene.addItem(item.text_item)
    tool.measurements[KEY] = [item]
    history = UndoRedoManager()

    history.execute_command(
        MeasurementCommand(tool, "remove", item, scene, *KEY)
    )
    assert item not in tool.measurements[KEY]
    assert item.scene() is None
    assert item.text_item.scene() is None
    item.hide_handles.assert_called()

    history.undo()
    assert item in tool.measurements[KEY]
    assert item.scene() is scene
    assert item.text_item.scene() is scene
    assert item.text_item.isVisible()
    item.update_distance.assert_called()

    history.redo()
    assert item not in tool.measurements[KEY]
    assert item.scene() is None


@pytest.mark.qt
def test_text_annotation_add_undo_and_remove_round_trip(qapp) -> None:
    scene = QGraphicsScene()
    tool = _text_tool()
    item = TextAnnotationItem("note")
    item.on_editing_finished = lambda _ok: None
    item._is_new_annotation = True
    history = UndoRedoManager()

    history.execute_command(
        TextAnnotationCommand(tool, "add", item, scene, *KEY)
    )
    assert item in tool.annotations[KEY]
    assert item.scene() is scene
    assert item.on_editing_finished is None
    assert item._is_new_annotation is False

    history.undo()
    assert item not in tool.annotations[KEY]
    assert item.scene() is None

    scene.addItem(item)
    tool.annotations[KEY] = [item]
    history.execute_command(
        TextAnnotationCommand(tool, "remove", item, scene, *KEY)
    )
    assert item not in tool.annotations[KEY]
    history.undo()
    assert item in tool.annotations[KEY]
    assert item.scene() is scene
    history.redo()
    assert item not in tool.annotations[KEY]


@pytest.mark.qt
def test_arrow_add_undo_and_remove_round_trip(qapp) -> None:
    scene = QGraphicsScene()
    tool = _arrow_tool()
    item = QGraphicsRectItem(0.0, 0.0, 8.0, 8.0)
    history = UndoRedoManager()

    history.execute_command(
        ArrowAnnotationCommand(tool, "add", item, scene, *KEY)
    )
    assert item in tool.arrows[KEY]
    assert item.scene() is scene

    ArrowAnnotationCommand(tool, "add", item, scene, *KEY).execute()
    assert tool.arrows[KEY] == [item]

    history.undo()
    assert item not in tool.arrows[KEY]
    assert item.scene() is None

    scene.addItem(item)
    tool.arrows[KEY] = [item]
    history.execute_command(
        ArrowAnnotationCommand(tool, "remove", item, scene, *KEY)
    )
    assert item not in tool.arrows[KEY]
    history.undo()
    assert item in tool.arrows[KEY]
    assert item.scene() is scene
    history.redo()
    assert item not in tool.arrows[KEY]


@pytest.mark.qt
def test_crosshair_remove_marks_text_deleted_and_undo_reattaches(qapp) -> None:
    scene = QGraphicsScene()
    manager = _crosshair_manager()
    item = _CrosshairStub()
    scene.addItem(item)
    scene.addItem(item.text_item)
    manager.crosshairs[KEY] = [item]
    history = UndoRedoManager()

    history.execute_command(
        CrosshairCommand(manager, "remove", item, scene, *KEY)
    )
    assert item not in manager.crosshairs[KEY]
    assert item.scene() is None
    assert item.text_item.scene() is None
    item.text_item.mark_deleted.assert_called_once()

    history.undo()
    assert item in manager.crosshairs[KEY]
    assert item.scene() is scene
    assert item.text_item.scene() is scene
    assert item.text_item.isVisible()

    history.redo()
    assert item not in manager.crosshairs[KEY]
    assert item.scene() is None


@pytest.mark.qt
def test_crosshair_add_then_undo(qapp) -> None:
    scene = QGraphicsScene()
    manager = _crosshair_manager()
    item = _CrosshairStub()
    history = UndoRedoManager()

    history.execute_command(
        CrosshairCommand(manager, "add", item, scene, *KEY)
    )
    assert item in manager.crosshairs[KEY]
    assert item.scene() is scene
    assert item.text_item.scene() is scene

    history.undo()
    assert item not in manager.crosshairs[KEY]
    assert item.scene() is None
    item.text_item.mark_deleted.assert_called()
