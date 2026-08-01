"""Focused tests for ROIManager draw/finish/delete and statistics mask."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from tools.roi_manager import ROIManager


@pytest.mark.qt
def test_draw_rectangle_finish_stores_roi(qapp) -> None:
    mgr = ROIManager()
    mgr.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()
    mgr.start_drawing(QPointF(10, 10), shape_type="rectangle")
    mgr.update_drawing(QPointF(40, 30), scene)
    roi = mgr.finish_drawing()
    assert roi is not None
    assert roi.shape_type == "rectangle"
    assert mgr.get_rois_for_slice("st", "se", 0) == [roi]


@pytest.mark.qt
def test_delete_roi_removes_from_slice(qapp) -> None:
    mgr = ROIManager()
    mgr.set_current_slice("st", "se", 1)
    scene = QGraphicsScene()
    mgr.start_drawing(QPointF(0, 0), shape_type="ellipse")
    mgr.update_drawing(QPointF(20, 20), scene)
    roi = mgr.finish_drawing()
    assert roi is not None
    assert mgr.delete_roi(roi, scene) is True
    assert mgr.get_rois_for_slice("st", "se", 1) == []


@pytest.mark.qt
def test_roi_mask_covers_bounds(qapp) -> None:
    mgr = ROIManager()
    mgr.set_current_slice("st", "se", 2)
    scene = QGraphicsScene()
    mgr.start_drawing(QPointF(5, 5), shape_type="rectangle")
    mgr.update_drawing(QPointF(15, 15), scene)
    roi = mgr.finish_drawing()
    assert roi is not None
    mask = roi.get_mask(32, 32)
    assert mask.shape == (32, 32)
    assert bool(np.any(mask))


@pytest.mark.qt
def test_clear_slice_rois(qapp) -> None:
    mgr = ROIManager()
    mgr.set_current_slice("st", "se", 3)
    scene = QGraphicsScene()
    mgr.start_drawing(QPointF(1, 1), shape_type="rectangle")
    mgr.update_drawing(QPointF(10, 10), scene)
    mgr.finish_drawing()
    mgr.clear_slice_rois("st", "se", 3, scene)
    assert mgr.get_rois_for_slice("st", "se", 3) == []
