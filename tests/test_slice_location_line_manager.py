"""
Tests for gui.slice_location_line_manager.SliceLocationLineManager.

Guards against duplicate slice-location lines when the scene is cleared or items
are detached outside the manager (MPR / multi-pane refresh ordering).

Run: python -m pytest tests/test_slice_location_line_manager.py -v
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsScene

from gui.slice_location_line_manager import SliceLocationLineManager


def _count_line_items(scene: QGraphicsScene) -> int:
    return sum(1 for it in scene.items() if isinstance(it, QGraphicsLineItem))


@pytest.mark.qt
def test_scene_clear_then_update_does_not_duplicate_lines(qapp: QApplication) -> None:
    scene = QGraphicsScene()
    mgr = SliceLocationLineManager(scene)
    seg = {"source_idx": 1, "line_id": "middle:1", "col1": 0, "row1": 10, "col2": 100, "row2": 10}
    mgr.update_lines([seg])
    assert _count_line_items(scene) == 1

    scene.clear()
    mgr.update_lines([seg])
    assert _count_line_items(scene) == 1


@pytest.mark.qt
def test_manual_remove_then_update_reattaches_single_line(qapp: QApplication) -> None:
    scene = QGraphicsScene()
    mgr = SliceLocationLineManager(scene)
    seg = {"source_idx": 0, "line_id": "middle:0", "col1": 0, "row1": 5, "col2": 50, "row2": 5}
    mgr.update_lines([seg])
    lines_before = [it for it in scene.items() if isinstance(it, QGraphicsLineItem)]
    assert len(lines_before) == 1
    line = lines_before[0]
    scene.removeItem(line)
    assert line.scene() is None

    mgr.update_lines(
        [{"source_idx": 0, "line_id": "middle:0", "col1": 0, "row1": 20, "col2": 50, "row2": 20}]
    )
    assert _count_line_items(scene) == 1
    assert line.scene() is scene


@pytest.mark.qt
def test_slice_location_line_pen_is_cosmetic(qapp: QApplication) -> None:
    """Stroke width should match ROI-style overlays (viewport pixels, not scene scale)."""
    scene = QGraphicsScene()
    mgr = SliceLocationLineManager(scene)
    seg = {"source_idx": 2, "line_id": "middle:2", "col1": 0, "row1": 0, "col2": 10, "row2": 10}
    mgr.update_lines([seg], line_width_px=3)
    lines = [it for it in scene.items() if isinstance(it, QGraphicsLineItem)]
    assert len(lines) == 1
    assert lines[0].pen().isCosmetic()
    assert lines[0].pen().width() == 3
