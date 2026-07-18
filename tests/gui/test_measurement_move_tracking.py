"""Regression: measurement undo-batch tracking is identical for handle vs group drag.

After collapsing the S3923 identical if/else arms in MeasurementCoordinator,
both `_updating_handles` True and False must seed / update the same tracking
dict for linear and angle measurements.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsTextItem

from gui.measurement_coordinator import MeasurementCoordinator
from tools.angle_measurement_items import AngleMeasurementItem


def _coord(qapp) -> MeasurementCoordinator:
    return MeasurementCoordinator(
        measurement_tool=MagicMock(),
        image_viewer=MagicMock(scene=MagicMock()),
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=None,
    )


@pytest.mark.qt
def test_linear_move_tracking_same_for_handle_and_group_drag(qapp) -> None:
    c = _coord(qapp)

    class _LinearStub:
        """Hashable stand-in for a linear MeasurementItem (dict-key safe)."""

        def __init__(self) -> None:
            self.start_point = QPointF(0, 0)
            self.end_point = QPointF(10, 0)
            self._updating_handles = True

    item = _LinearStub()
    c._on_measurement_moved(item)
    assert item in c._measurement_move_tracking
    first = dict(c._measurement_move_tracking[item])

    item._updating_handles = False
    item.start_point = QPointF(1, 1)
    item.end_point = QPointF(11, 1)
    c._on_measurement_moved(item)
    second = c._measurement_move_tracking[item]
    assert second["kind"] == "linear"
    assert first["initial_start"] == QPointF(0, 0)
    assert second["current_start"] == QPointF(1, 1)
    assert second["current_end"] == QPointF(11, 1)


@pytest.mark.qt
def test_angle_move_tracking_same_for_handle_and_group_drag(qapp) -> None:
    c = _coord(qapp)
    p1, p2, p3 = QPointF(0, 0), QPointF(5, 0), QPointF(5, 5)
    line1 = QGraphicsLineItem(0, 0, 5, 0)
    line2 = QGraphicsLineItem(5, 0, 5, 5)
    for ln in (line1, line2):
        ln.setPen(QPen(QColor(0, 255, 0)))
    text = QGraphicsTextItem("0°")
    angle = AngleMeasurementItem(p1, p2, p3, line1, line2, text)

    angle._updating_handles = True
    c._on_measurement_moved(angle)
    assert angle in c._measurement_move_tracking
    initial = c._measurement_move_tracking[angle]["initial_p1"]

    angle._updating_handles = False
    angle.p1 = QPointF(2, 2)
    c._on_measurement_moved(angle)
    tracking = c._measurement_move_tracking[angle]
    assert tracking["kind"] == "angle"
    assert tracking["initial_p1"] == initial
    assert tracking["current_p1"] == QPointF(2, 2)
