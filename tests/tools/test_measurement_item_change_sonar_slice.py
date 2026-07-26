"""
Characterization tests for measurement itemChange helpers (Sonar S3776 slice).

Covers group position veto/allow and handle start/end geometry updates extracted
from ``MeasurementHandle.itemChange`` / ``MeasurementItem.itemChange``.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtCore import QLineF, QPointF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsLineItem, QGraphicsTextItem

from tools.measurement_item_change import (
    apply_end_handle_scene_move,
    apply_start_handle_scene_move,
    process_measurement_group_item_change,
    resolve_measurement_group_position_change,
)


def test_resolve_group_position_change_allow_and_block() -> None:
    m = SimpleNamespace(
        _updating_handles=True,
        _handle_drag_in_progress=False,
        pos=lambda: QPointF(1.0, 2.0),
    )
    proposed = QPointF(9.0, 9.0)
    assert resolve_measurement_group_position_change(m, proposed) == proposed

    m._updating_handles = False
    m._handle_drag_in_progress = True
    assert resolve_measurement_group_position_change(m, proposed) == QPointF(1.0, 2.0)

    m._handle_drag_in_progress = False
    assert resolve_measurement_group_position_change(m, proposed) == proposed


def test_process_group_scene_change_updates_text_offset() -> None:
    m = MagicMock()
    handled, result = process_measurement_group_item_change(
        m,
        QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged,
        object(),
    )
    assert handled is True
    m.update_text_offset_for_zoom.assert_called_once()
    assert result is not None


def test_apply_start_and_end_handle_moves(qapp) -> None:
    from tools.measurement_items import MeasurementItem

    start = QPointF(0.0, 0.0)
    end = QPointF(10.0, 0.0)
    line_item = QGraphicsLineItem(QLineF(0.0, 0.0, 10.0, 0.0))
    text_item = QGraphicsTextItem("x")
    item = MeasurementItem(start, end, line_item, text_item, pixel_spacing=(1.0, 1.0))

    apply_end_handle_scene_move(item, QPointF(20.0, 5.0))
    assert item.end_point == QPointF(20.0, 5.0)
    assert item.start_point == QPointF(0.0, 0.0)

    apply_start_handle_scene_move(item, QPointF(2.0, 2.0))
    assert item.start_point == QPointF(2.0, 2.0)
    assert item.end_point == QPointF(20.0, 5.0)
    assert item.pos() == QPointF(2.0, 2.0)
