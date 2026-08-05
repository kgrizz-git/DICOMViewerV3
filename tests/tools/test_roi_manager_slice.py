"""Focused tests for ROIManager draw/finish/delete and statistics mask."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest
from pydicom.dataset import Dataset
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
    assert bool(mask[10, 10])  # interior of 5..15 rectangle
    assert not bool(mask[0, 0])  # exterior
    assert not bool(mask[31, 31])


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


@pytest.mark.qt
def test_enter_exit_roi_geometry_edit_mode(qapp) -> None:
    mgr = ROIManager()
    mgr.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()

    mgr.start_drawing(QPointF(5, 5), shape_type="rectangle")
    mgr.update_drawing(QPointF(15, 15), scene)
    roi = mgr.finish_drawing()

    commit_mock = MagicMock()
    mgr.enter_roi_geometry_edit_mode(roi, scene, commit_mock)

    assert mgr._editing_roi == roi
    assert mgr._geometry_edit_scene == scene
    assert len(roi._resize_handles) == 8

    # Enter again with same parameters - should return early
    mgr.enter_roi_geometry_edit_mode(roi, scene, commit_mock)
    assert mgr._editing_roi == roi

    # Exit edit mode
    assert mgr.exit_roi_geometry_edit_mode() is True
    assert mgr._editing_roi is None
    assert len(roi._resize_handles) == 0


@pytest.mark.qt
def test_begin_continue_finish_resize_handle_drag(qapp) -> None:
    mgr = ROIManager()
    mgr.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()

    mgr.start_drawing(QPointF(10, 10), shape_type="rectangle")
    mgr.update_drawing(QPointF(20, 20), scene)
    roi = mgr.finish_drawing()

    commit_mock = MagicMock()
    mgr.enter_roi_geometry_edit_mode(roi, scene, commit_mock)

    # Start dragging top-left handle
    roi.begin_resize_handle_drag("tl", QPointF(10, 10))
    assert roi._resize_drag_active is True

    # Move to (5, 5)
    roi.continue_resize_handle_drag(QPointF(5, 5))

    # Finish drag
    roi.finish_resize_handle_drag()
    assert roi._resize_drag_active is False
    commit_mock.assert_called_once()
    committed_roi, initial_rect, final_rect = commit_mock.call_args.args
    assert committed_roi is roi
    assert final_rect.left() < initial_rect.left()
    assert final_rect.top() < initial_rect.top()
    assert final_rect.right() == pytest.approx(initial_rect.right())
    assert final_rect.bottom() == pytest.approx(initial_rect.bottom())


@pytest.mark.qt
def test_calculate_statistics_multichannel(qapp) -> None:
    config = MagicMock()
    config.get_roi_show_per_channel_statistics.return_value = True
    config.get_roi_line_thickness.return_value = 2
    config.get_roi_line_color.return_value = (255, 0, 0)
    config.get_roi_default_visible_statistics.return_value = ["mean", "std"]

    mgr = ROIManager(config_manager=config)
    mgr.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()

    mgr.start_drawing(QPointF(2, 2), shape_type="rectangle")
    mgr.update_drawing(QPointF(6, 6), scene)
    roi = mgr.finish_drawing()

    # 10x10 multichannel image (RGB style: 3 channels)
    pixels = np.zeros((10, 10, 3), dtype=np.uint8)
    # Put values inside ROI region
    pixels[1:7, 1:7, 0] = 100
    pixels[1:7, 1:7, 1] = 150
    pixels[1:7, 1:7, 2] = 200

    ds = Dataset()
    ds.PhotometricInterpretation = "RGB"
    ds.SamplesPerPixel = 3

    stats = mgr.calculate_statistics(
        roi,
        pixels,
        rescale_slope=1.0,
        rescale_intercept=10.0,
        pixel_spacing=(2.0, 3.0),
        dataset=ds,
    )

    assert stats["count"] == 36
    assert stats["area_pixels"] == 36.0
    assert stats["area_mm2"] == 36.0 * 2.0 * 3.0
    assert "channel_labels" in stats
    assert stats["channel_labels"] == ("R", "G", "B")

    # Verify per-channel stats are present
    assert "mean_ch0" in stats
    assert (
        stats["mean_ch0"] == 110.0
    )  # slope/intercept are correctly applied to per-channel stats too
