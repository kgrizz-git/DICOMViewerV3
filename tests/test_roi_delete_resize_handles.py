"""ROI deletion must remove corner/edge resize handles from the scene."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QGraphicsScene

from tools.roi_graphics_items import ROIResizeHandleItem
from tools.roi_manager import ROIGraphicsRectItem, ROIItem, ROIManager
from utils.undo_redo import ROICommand, UndoRedoManager


def _scene_handle_count(scene: QGraphicsScene) -> int:
    return sum(1 for item in scene.items() if isinstance(item, ROIResizeHandleItem))


def _make_roi_on_scene(scene: QGraphicsScene) -> ROIItem:
    rect = QRectF(10.0, 10.0, 80.0, 60.0)
    item = ROIGraphicsRectItem(rect)
    scene.addItem(item)
    return ROIItem("rectangle", item, pen_width=1, pen_color=(255, 255, 255))


@pytest.mark.qt
def test_roi_command_remove_clears_resize_handles(qapp) -> None:
    scene = QGraphicsScene()
    manager = ROIManager()
    roi = _make_roi_on_scene(scene)
    key = ("study", "series", 0)
    manager.rois[key] = [roi]
    manager.selected_roi = roi
    manager.enter_roi_geometry_edit_mode(roi, scene, on_commit=lambda _o, _n: None)

    assert _scene_handle_count(scene) == 8

    command = ROICommand(
        manager,
        "remove",
        roi,
        scene,
        "study",
        "series",
        0,
    )
    command.execute()

    assert _scene_handle_count(scene) == 0
    assert roi.item.scene() is None
    assert manager.selected_roi is None
    assert manager._editing_roi is None


@pytest.mark.qt
def test_roi_command_remove_undo_restores_roi_without_handles(qapp) -> None:
    scene = QGraphicsScene()
    manager = ROIManager()
    roi = _make_roi_on_scene(scene)
    key = ("study", "series", 0)
    manager.rois[key] = [roi]
    manager.enter_roi_geometry_edit_mode(roi, scene, on_commit=lambda _o, _n: None)

    history = UndoRedoManager()
    history.execute_command(
        ROICommand(manager, "remove", roi, scene, "study", "series", 0)
    )

    assert _scene_handle_count(scene) == 0
    assert roi not in manager.rois[key]

    history.undo()

    assert roi in manager.rois[key]
    assert roi.item.scene() is scene
    assert _scene_handle_count(scene) == 0
