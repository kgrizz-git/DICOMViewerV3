"""Focused tests for MeasurementTool distance start/finish and cancel."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from tools.measurement_tool import MeasurementTool


@pytest.mark.qt
def test_finish_distance_measurement_with_spacing(qapp) -> None:
    tool = MeasurementTool()
    tool.set_pixel_spacing((1.0, 1.0))  # row, col mm
    tool.set_current_slice("st", "se", 0)
    scene = QGraphicsScene()
    tool.start_measurement(QPointF(0, 0))
    tool.update_measurement(QPointF(10, 0), scene)
    item = tool.finish_measurement(scene)
    assert item is not None
    assert len(tool.get_measurements_for_slice("st", "se", 0)) == 1


@pytest.mark.qt
def test_cancel_measurement_clears_preview(qapp) -> None:
    tool = MeasurementTool()
    tool.set_current_slice("st", "se", 1)
    scene = QGraphicsScene()
    tool.start_measurement(QPointF(0, 0))
    tool.update_measurement(QPointF(5, 5), scene)
    tool.cancel_measurement(scene)
    assert tool.get_measurements_for_slice("st", "se", 1) == []


@pytest.mark.qt
def test_clear_slice_measurements(qapp) -> None:
    tool = MeasurementTool()
    tool.set_pixel_spacing((0.5, 0.5))
    tool.set_current_slice("st", "se", 2)
    scene = QGraphicsScene()
    tool.start_measurement(QPointF(0, 0))
    tool.update_measurement(QPointF(8, 0), scene)
    tool.finish_measurement(scene)
    assert tool.get_measurements_for_slice("st", "se", 2)
    tool.clear_slice_measurements("st", "se", 2, scene)
    assert tool.get_measurements_for_slice("st", "se", 2) == []
