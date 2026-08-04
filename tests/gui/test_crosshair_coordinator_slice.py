"""Focused tests for CrosshairCoordinator with fake viewer/manager."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from gui.crosshair_coordinator import CrosshairCoordinator
from tools.crosshair_manager import CrosshairManager


@pytest.mark.qt
def test_handle_crosshair_clicked_creates_item(qapp) -> None:
    mgr = CrosshairManager()
    scene = QGraphicsScene()
    viewer = MagicMock()
    viewer.scene = scene
    coord = CrosshairCoordinator(
        crosshair_manager=mgr,
        image_viewer=viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord.handle_crosshair_clicked(QPointF(12, 8), "42", 12, 8, 0)
    assert len(mgr.get_crosshairs_for_slice()) == 1


@pytest.mark.qt
def test_handle_noop_when_scene_missing(qapp) -> None:
    mgr = CrosshairManager()
    viewer = MagicMock()
    viewer.scene = None
    coord = CrosshairCoordinator(
        crosshair_manager=mgr,
        image_viewer=viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord.handle_crosshair_clicked(QPointF(1, 1), "1", 1, 1, 0)
    assert all(len(v) == 0 for v in mgr.crosshairs.values())
