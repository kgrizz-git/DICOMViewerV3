"""Focused coverage for undo/redo manager guards and move commands."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
)

from utils.undo_redo import (
    AngleMeasurementMoveCommand,
    ArrowAnnotationCommand,
    ArrowAnnotationMoveCommand,
    CompositeCommand,
    CrosshairCommand,
    CrosshairMoveCommand,
    MeasurementCommand,
    MeasurementMoveCommand,
    ROICommand,
    ROIGeometryResizeCommand,
    ROIMoveCommand,
    TextAnnotationCommand,
    TextAnnotationEditCommand,
    TextAnnotationMoveCommand,
    UndoRedoManager,
)
from utils.undo_redo_command import Command


class _RecordingCommand(Command):
    def __init__(self, name: str, events: list[str], fail: bool = False) -> None:
        self.name = name
        self.events = events
        self.fail = fail

    def execute(self) -> None:
        if self.fail:
            raise RuntimeError("command failed")
        self.events.append(f"execute:{self.name}")

    def undo(self) -> None:
        self.events.append(f"undo:{self.name}")


def test_manager_stack_guards_limit_and_recover_after_command_failure() -> None:
    events: list[str] = []
    manager = UndoRedoManager(max_history=2)
    first = _RecordingCommand("first", events)
    second = _RecordingCommand("second", events)
    third = _RecordingCommand("third", events)
    replacement = _RecordingCommand("replacement", events)

    assert manager.undo() is False
    assert manager.redo() is False
    assert manager.can_undo() is False
    assert manager.can_redo() is False

    manager.execute_command(first)
    manager.execute_command(second)
    manager.execute_command(third)
    assert manager.undo_stack == [second, third]
    assert manager.redo_stack == []

    assert manager.undo() is True
    assert manager.can_redo() is True
    assert manager.redo() is True
    assert manager.undo() is True
    manager.execute_command(replacement)
    assert manager.redo_stack == []

    with pytest.raises(RuntimeError, match="command failed"):
        manager.execute_command(_RecordingCommand("failed", events, fail=True))
    assert manager.undo_stack == [second, replacement]

    manager.clear()
    assert manager.undo_stack == []
    assert manager.redo_stack == []
    assert manager.can_undo() is False
    assert manager.can_redo() is False


@pytest.mark.qt
def test_resize_and_basic_move_commands_restore_scene_state(qapp) -> None:
    scene = QGraphicsScene()
    other_scene = QGraphicsScene()
    graphics_item = QGraphicsRectItem(QRectF(0, 0, 10, 10))
    scene.addItem(graphics_item)
    roi = MagicMock(item=graphics_item)
    applied: list[QRectF] = []

    def apply_resize(item, rect: QRectF) -> None:
        applied.append(QRectF(rect))
        item.item.setRect(rect)

    old_rect = QRectF(1, 2, 10, 11)
    new_rect = QRectF(3, 4, 20, 21)
    resize = ROIGeometryResizeCommand(roi, old_rect, new_rect, scene, apply_resize)
    resize.execute()
    resize.undo()
    resize.redo()
    assert applied == [new_rect, old_rect, new_rect]
    assert graphics_item.rect() == new_rect

    roi_move = ROIMoveCommand(roi, QPointF(1, 2), QPointF(8, 9), scene)
    roi_move.execute()
    assert graphics_item.pos() == QPointF(8, 9)
    roi_move.undo()
    assert graphics_item.pos() == QPointF(1, 2)

    text_item = QGraphicsTextItem("old")
    edit = TextAnnotationEditCommand(text_item, "old", "new")
    edit.execute()
    assert text_item.toPlainText() == "new"
    edit.undo()
    assert text_item.toPlainText() == "old"

    scene.addItem(text_item)
    text_move = TextAnnotationMoveCommand(
        text_item, QPointF(2, 3), QPointF(12, 13), scene
    )
    text_move.execute()
    assert text_item.pos() == QPointF(12, 13)
    text_move.undo()
    assert text_item.pos() == QPointF(2, 3)

    crosshair = QGraphicsRectItem(QRectF(0, 0, 5, 5))
    crosshair.position = QPointF(0, 0)
    crosshair.update_text_position = MagicMock()
    scene.addItem(crosshair)
    view = QGraphicsView(scene)
    crosshair_move = CrosshairMoveCommand(
        crosshair, QPointF(4, 5), QPointF(14, 15), scene
    )
    crosshair_move.execute()
    assert crosshair.position == QPointF(14, 15)
    assert crosshair.update_text_position.call_count == 1
    crosshair_move.undo()
    assert crosshair.position == QPointF(4, 5)
    assert crosshair.update_text_position.call_count == 2
    view.close()

    # Guards leave state untouched when an item or scene is unavailable.
    ROIGeometryResizeCommand(None, old_rect, new_rect, scene, apply_resize).execute()
    ROIGeometryResizeCommand(roi, old_rect, new_rect, None, apply_resize).execute()
    ROIGeometryResizeCommand(roi, old_rect, new_rect, other_scene, apply_resize).execute()
    ROIGeometryResizeCommand(roi, old_rect, new_rect, scene).execute()
    ROIMoveCommand(None, QPointF(), QPointF(1, 1), scene).execute()
    ROIMoveCommand(roi, QPointF(), QPointF(1, 1), other_scene).execute()
    TextAnnotationEditCommand(None, "old", "new").execute()
    TextAnnotationMoveCommand(None, QPointF(), QPointF(1, 1), scene).execute()
    TextAnnotationMoveCommand(text_item, QPointF(), QPointF(1, 1), other_scene).execute()
    assert applied == [new_rect, old_rect, new_rect]
    assert graphics_item.rect() == new_rect
    assert graphics_item.pos() == QPointF(1, 2)
    assert text_item.toPlainText() == "old"
    assert text_item.pos() == QPointF(2, 3)


class _ArrowMoveStub:
    def __init__(self, scene) -> None:
        self._scene = scene
        self.on_moved_callback = MagicMock()
        self._updating_position = False
        self.points = None

    def scene(self):
        return self._scene

    def update_endpoints(self, start, end) -> None:
        assert self._updating_position is True
        self.points = (start, end)


class _MeasurementMoveStub:
    def __init__(self, scene) -> None:
        self._scene = scene
        self.start_point = QPointF()
        self.end_point = QPointF()
        self.end_relative = QPointF()
        self.line_item = MagicMock()
        self.update_distance = MagicMock()
        self.position = QPointF()

    def scene(self):
        return self._scene

    def setPos(self, position) -> None:
        self.position = position


class _AngleMoveStub:
    def __init__(self, scene) -> None:
        self._scene = scene
        self.p1 = self.p2 = self.p3 = QPointF()
        self.position = QPointF()
        self.update_angle_geometry = MagicMock()

    def scene(self):
        return self._scene

    def setPos(self, position) -> None:
        self.position = position


@pytest.mark.qt
def test_arrow_measurement_and_angle_moves_preserve_geometry_and_callbacks(qapp) -> None:
    scene = QGraphicsScene()
    other_scene = QGraphicsScene()
    old_start, old_end = QPointF(1, 2), QPointF(3, 4)
    new_start, new_end = QPointF(10, 20), QPointF(30, 40)

    arrow = _ArrowMoveStub(scene)
    arrow_command = ArrowAnnotationMoveCommand(
        arrow, old_start, old_end, new_start, new_end, scene
    )
    arrow_command.execute()
    assert arrow.points == (new_start, new_end)
    assert arrow.on_moved_callback is not None
    assert arrow._updating_position is False
    arrow_command.undo()
    assert arrow.points == (old_start, old_end)

    measurement = _MeasurementMoveStub(scene)
    measurement_command = MeasurementMoveCommand(
        measurement, old_start, old_end, new_start, new_end, scene
    )
    measurement_command.execute()
    assert measurement.start_point == new_start
    assert measurement.end_point == new_end
    assert measurement.end_relative == new_end - new_start
    assert measurement.position == new_start
    measurement_command.undo()
    assert measurement.start_point == old_start
    assert measurement.position == old_start
    assert measurement.line_item.prepareGeometryChange.call_count == 2
    assert measurement.update_distance.call_count == 2

    angle = _AngleMoveStub(scene)
    angle_command = AngleMeasurementMoveCommand(
        angle,
        QPointF(1, 1),
        QPointF(2, 2),
        QPointF(3, 3),
        QPointF(11, 11),
        QPointF(12, 12),
        QPointF(13, 13),
        scene,
    )
    angle_command.execute()
    assert (angle.p1, angle.p2, angle.p3) == (
        QPointF(11, 11), QPointF(12, 12), QPointF(13, 13)
    )
    angle_command.undo()
    assert (angle.p1, angle.p2, angle.p3) == (
        QPointF(1, 1), QPointF(2, 2), QPointF(3, 3)
    )
    assert angle.update_angle_geometry.call_count == 2

    ArrowAnnotationMoveCommand(None, old_start, old_end, new_start, new_end, scene).execute()
    ArrowAnnotationMoveCommand(arrow, old_start, old_end, new_start, new_end, other_scene).execute()
    MeasurementMoveCommand(None, old_start, old_end, new_start, new_end, scene).execute()
    MeasurementMoveCommand(measurement, old_start, old_end, new_start, new_end, other_scene).execute()
    AngleMeasurementMoveCommand(
        None,
        QPointF(), QPointF(), QPointF(),
        QPointF(1, 1), QPointF(2, 2), QPointF(3, 3),
        scene,
    ).execute()
    AngleMeasurementMoveCommand(
        angle,
        QPointF(), QPointF(), QPointF(),
        QPointF(1, 1), QPointF(2, 2), QPointF(3, 3),
        other_scene,
    ).execute()
    assert arrow.points == (old_start, old_end)
    assert arrow.on_moved_callback.call_count == 0
    assert (measurement.start_point, measurement.end_point) == (old_start, old_end)
    assert measurement.update_distance.call_count == 2
    assert (angle.p1, angle.p2, angle.p3) == (QPointF(1, 1), QPointF(2, 2), QPointF(3, 3))
    assert angle.update_angle_geometry.call_count == 2


@pytest.mark.qt
def test_command_collection_guards_and_composite_order(qapp) -> None:
    scene = QGraphicsScene()
    key = ("study", "series", 0)

    roi_manager = MagicMock(rois={})
    roi = MagicMock(item=QGraphicsRectItem())
    ROICommand(roi_manager, "remove", roi, scene, *key).execute()
    ROICommand(roi_manager, "unknown", roi, scene, *key).execute()
    ROICommand(roi_manager, "add", roi, None, *key).execute()

    measurement_tool = MagicMock(measurements={})
    measurement = QGraphicsRectItem()
    MeasurementCommand(measurement_tool, "remove", measurement, scene, *key).execute()
    MeasurementCommand(measurement_tool, "unknown", measurement, scene, *key).execute()
    MeasurementCommand(measurement_tool, "add", measurement, None, *key).execute()

    annotation_tool = MagicMock(annotations={})
    annotation = QGraphicsTextItem("note")
    TextAnnotationCommand(annotation_tool, "remove", annotation, scene, *key).execute()
    TextAnnotationCommand(annotation_tool, "unknown", annotation, scene, *key).execute()
    TextAnnotationCommand(annotation_tool, "add", annotation, None, *key).execute()

    arrow_tool = MagicMock(arrows={})
    arrow = QGraphicsRectItem()
    ArrowAnnotationCommand(arrow_tool, "remove", arrow, scene, *key).execute()
    ArrowAnnotationCommand(arrow_tool, "unknown", arrow, scene, *key).execute()
    ArrowAnnotationCommand(arrow_tool, "add", arrow, None, *key).execute()

    crosshair_manager = MagicMock(crosshairs={})
    crosshair = QGraphicsRectItem()
    CrosshairCommand(crosshair_manager, "remove", crosshair, scene, *key).execute()
    CrosshairCommand(crosshair_manager, "unknown", crosshair, scene, *key).execute()
    CrosshairCommand(crosshair_manager, "add", crosshair, None, *key).execute()

    assert roi_manager.rois == {}
    assert measurement_tool.measurements == {}
    assert annotation_tool.annotations == {}
    assert arrow_tool.arrows == {}
    assert crosshair_manager.crosshairs == {}
    assert scene.items() == []

    events: list[str] = []
    first = _RecordingCommand("first", events)
    second = _RecordingCommand("second", events)
    composite = CompositeCommand([first, second])
    composite.execute()
    composite.undo()
    assert events == [
        "execute:first",
        "execute:second",
        "undo:second",
        "undo:first",
    ]
