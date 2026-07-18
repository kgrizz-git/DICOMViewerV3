"""
Characterize ROICommand add / remove / undo / redo scene and overlay contracts.

Covers resize-handle and selection clearing, scene membership, duplicate
prevention, and overlay-visible restoration on undo of a remove.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsTextItem

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


def _make_roi_off_scene() -> ROIItem:
    rect = QRectF(10.0, 10.0, 80.0, 60.0)
    item = ROIGraphicsRectItem(rect)
    return ROIItem("rectangle", item, pen_width=1, pen_color=(255, 255, 255))


@pytest.mark.qt
def test_add_then_undo_removes_from_manager_and_scene(qapp) -> None:
    scene = QGraphicsScene()
    manager = ROIManager()
    roi = _make_roi_off_scene()
    stats_cb = MagicMock()
    history = UndoRedoManager()

    history.execute_command(
        ROICommand(
            manager,
            "add",
            roi,
            scene,
            "study",
            "series",
            0,
            update_statistics_callback=stats_cb,
        )
    )

    key = ("study", "series", 0)
    assert roi in manager.rois[key]
    assert roi.item.scene() is scene
    stats_cb.assert_called_once()

    history.undo()

    assert roi not in manager.rois[key]
    assert roi.item.scene() is None


@pytest.mark.qt
def test_add_does_not_duplicate_existing_roi(qapp) -> None:
    scene = QGraphicsScene()
    manager = ROIManager()
    roi = _make_roi_on_scene(scene)
    key = ("study", "series", 0)
    manager.rois[key] = [roi]
    stats_cb = MagicMock()

    command = ROICommand(
        manager,
        "add",
        roi,
        scene,
        "study",
        "series",
        0,
        update_statistics_callback=stats_cb,
    )
    command.execute()

    assert manager.rois[key] == [roi]
    stats_cb.assert_not_called()


@pytest.mark.qt
def test_remove_then_undo_then_redo_restores_overlay_flag_and_selection_clear(qapp) -> None:
    scene = QGraphicsScene()
    manager = ROIManager()
    roi = _make_roi_on_scene(scene)
    key = ("study", "series", 0)
    manager.rois[key] = [roi]
    manager.selected_roi = roi
    manager.enter_roi_geometry_edit_mode(roi, scene, on_commit=lambda _o, _n: None)

    overlay = QGraphicsTextItem("stats")
    scene.addItem(overlay)
    roi.statistics_overlay_item = overlay
    roi.statistics_overlay_visible = True
    stats_cb = MagicMock()

    history = UndoRedoManager()
    history.execute_command(
        ROICommand(
            manager,
            "remove",
            roi,
            scene,
            "study",
            "series",
            0,
            update_statistics_callback=stats_cb,
        )
    )

    assert _scene_handle_count(scene) == 0
    assert roi not in manager.rois[key]
    assert roi.item.scene() is None
    assert manager.selected_roi is None
    assert manager._editing_roi is None
    assert roi.statistics_overlay_item is None

    # Simulate deletion path clearing the visibility flag after the command was built.
    roi.statistics_overlay_visible = False
    # Leave a surviving overlay graphics item detached from the scene.
    surviving = QGraphicsRectItem(QRectF(0, 0, 5, 5))
    roi.statistics_overlay_item = surviving

    history.undo()

    assert roi in manager.rois[key]
    assert roi.item.scene() is scene
    assert roi.statistics_overlay_visible is True
    assert surviving.scene() is scene
    assert surviving.isVisible()
    stats_cb.assert_called_once()
    assert _scene_handle_count(scene) == 0

    history.redo()

    assert roi not in manager.rois[key]
    assert roi.item.scene() is None
    assert manager.selected_roi is None
