"""
itemChange helpers for measurement graphics items (Sonar S3776 slice).

Extracted from ``MeasurementHandle.itemChange`` and ``MeasurementItem.itemChange``
to clear cognitive-complexity findings while preserving handle-drag, group-drag,
selection, and debug logging behavior.

Inputs:
    - MeasurementHandle / MeasurementItem instances and Qt change/value payloads

Outputs:
    - Updated measurement geometry / handles / callbacks; veto or allow positions

Requirements:
    - PySide6 QGraphicsItem change enums
    - ``utils.debug_flags.DEBUG_MEASUREMENT_DRAG``
    - ``gui.view_transform_helpers.graphics_view_uniform_zoom``
"""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QLineF, QPointF
from PySide6.QtWidgets import QGraphicsItem

from gui.view_transform_helpers import graphics_view_uniform_zoom
from utils.debug_flags import DEBUG_MEASUREMENT_DRAG


def _fmt_point(pt: Any) -> str:
    """Format a QPointF-like value for DEBUG_MEASUREMENT_DRAG logs."""
    return f"({pt.x():.1f}, {pt.y():.1f})"


def _line_item_str(line_item: Any) -> str:
    """Format a QGraphicsLineItem's local line endpoints for debug logs."""
    line = line_item.line()
    return f"p1={_fmt_point(line.p1())} p2={_fmt_point(line.p2())}"


def debug_log_handle_drag(handle: Any, measurement: Any, *, phase: str) -> None:
    """Emit a DEBUG_MEASUREMENT_DRAG snapshot for a handle move."""
    if not DEBUG_MEASUREMENT_DRAG:
        return
    h_label = "START" if handle.is_start else "END"
    line_item = measurement.line_item
    line = line_item.line()
    ln_scene_p1 = line_item.mapToScene(line.p1())
    ln_scene_p2 = line_item.mapToScene(line.p2())
    sh_pos = measurement.start_handle.pos() if measurement.start_handle else None
    eh_pos = measurement.end_handle.pos() if measurement.end_handle else None
    if phase == "before":
        print(
            f"[DRAG] {h_label} handle moved → handle.pos={_fmt_point(handle.pos())}\n"
            f"       group.pos={_fmt_point(measurement.pos())}  "
            f"start_point={_fmt_point(measurement.start_point)}  "
            f"end_point={_fmt_point(measurement.end_point)}\n"
            f"       end_relative={_fmt_point(measurement.end_relative)}\n"
            f"       line item coords: {_line_item_str(line_item)}\n"
            f"       line scene:  p1={_fmt_point(ln_scene_p1)}  p2={_fmt_point(ln_scene_p2)}\n"
            f"       start_handle.pos={_fmt_point(sh_pos) if sh_pos else 'None'}  "
            f"end_handle.pos={_fmt_point(eh_pos) if eh_pos else 'None'}"
        )
        return
    print(
        f"[DRAG] {h_label} AFTER update:\n"
        f"       group.pos={_fmt_point(measurement.pos())}  "
        f"start_point={_fmt_point(measurement.start_point)}  "
        f"end_point={_fmt_point(measurement.end_point)}\n"
        f"       end_relative={_fmt_point(measurement.end_relative)}\n"
        f"       line item coords: {_line_item_str(line_item)}\n"
        f"       line scene:  p1={_fmt_point(ln_scene_p1)}  p2={_fmt_point(ln_scene_p2)}\n"
        f"       start_handle.pos={_fmt_point(sh_pos) if sh_pos else 'None'}  "
        f"end_handle.pos={_fmt_point(eh_pos) if eh_pos else 'None'}"
    )


def _invalidate_measurement_line_scene(measurement: Any) -> None:
    """Request a scene update for the measurement line's mapped bounds."""
    if measurement.scene() is None:
        return
    line_rect = measurement.line_item.boundingRect()
    line_scene_rect = measurement.line_item.mapRectToScene(line_rect)
    measurement.scene().update(line_scene_rect)


def apply_start_handle_scene_move(measurement: Any, scene_pos: QPointF) -> None:
    """Reposition the measurement group so the start handle is at *scene_pos*."""
    original_end_point = measurement.end_point
    measurement.start_point = scene_pos
    measurement.setPos(measurement.start_point)
    measurement.end_point = original_end_point
    measurement.end_relative = measurement.end_point - measurement.start_point
    measurement.update_distance()
    measurement.line_item.update()
    measurement.update()
    _invalidate_measurement_line_scene(measurement)


def apply_end_handle_scene_move(measurement: Any, scene_pos: QPointF) -> None:
    """Update the end endpoint to *scene_pos* without moving the group origin."""
    measurement.end_point = scene_pos
    measurement.end_relative = measurement.end_point - measurement.start_point
    measurement.update_distance()
    measurement.line_item.update()
    measurement.update()
    _invalidate_measurement_line_scene(measurement)


def sync_other_handle_during_drag(handle: Any, measurement: Any) -> None:
    """Keep the non-dragged handle aligned while update_handle_positions is skipped."""
    was_updating = getattr(measurement, "_updating_handles", False)
    measurement._updating_handles = True
    try:
        if (
            handle.is_start
            and measurement.end_handle is not None
            and measurement.end_handle.scene() is not None
        ):
            measurement.end_handle.setPos(measurement.end_point)
        elif (
            not handle.is_start
            and measurement.start_handle is not None
            and measurement.start_handle.scene() is not None
        ):
            measurement.start_handle.setPos(measurement.start_point)
    finally:
        measurement._updating_handles = was_updating


def notify_handle_drag_callbacks(measurement: Any, handle_scene_pos: QPointF) -> None:
    """Invoke on_moved and handle-drag-move callbacks when present."""
    if measurement.on_moved_callback:
        try:
            measurement.on_moved_callback()
        except Exception:
            pass
    move_callback = measurement.on_handle_drag_move_callback
    if move_callback is not None:
        try:
            move_callback(handle_scene_pos)
        except Exception:
            pass


def process_measurement_handle_item_change(
    handle: Any,
    change: QGraphicsItem.GraphicsItemChange,
    value: object,
) -> tuple[bool, object]:
    """
    Process MeasurementHandle.itemChange special cases.

    Returns:
        ``(True, result)`` when the caller should return *result* immediately
        (before ``super``), or ``(False, value)`` to fall through to ``super``.
    """
    if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
        return True, value

    if change != QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
        return False, value

    measurement = handle.parent_measurement
    if measurement is None:
        return False, value
    if measurement.scene() is None:
        return True, value
    if (
        hasattr(measurement, "_updating_handles")
        and measurement._updating_handles
    ):
        return True, value

    debug_log_handle_drag(handle, measurement, phase="before")
    measurement._updating_handles = True
    try:
        if handle.is_start:
            apply_start_handle_scene_move(measurement, handle.pos())
        else:
            apply_end_handle_scene_move(measurement, handle.pos())
    finally:
        measurement._updating_handles = False

    sync_other_handle_during_drag(handle, measurement)
    debug_log_handle_drag(handle, measurement, phase="after")
    notify_handle_drag_callbacks(measurement, handle.pos())
    return False, value


def resolve_measurement_group_position_change(
    measurement: Any,
    value: QPointF,
) -> QPointF:
    """Resolve MeasurementItem ItemPositionChange (allow, our setPos, or veto)."""
    if hasattr(measurement, "_updating_handles") and measurement._updating_handles:
        if DEBUG_MEASUREMENT_DRAG:
            print(
                "[DRAG] GROUP ItemPositionChange → ALLOWED (our setPos): "
                f"proposed={value.x():.1f},{value.y():.1f}"
            )
        return value
    if getattr(measurement, "_handle_drag_in_progress", False):
        if DEBUG_MEASUREMENT_DRAG:
            cur = measurement.pos()
            print(
                "[DRAG] GROUP ItemPositionChange → BLOCKED (handle drag): "
                f"proposed={value.x():.1f},{value.y():.1f}  "
                f"kept={cur.x():.1f},{cur.y():.1f}"
            )
        return measurement.pos()
    return value


def _viewport_to_scene_scale(measurement: Any) -> float:
    """Inverse uniform zoom for converting viewport text offsets to scene units."""
    view = (
        measurement.scene().views()[0]
        if measurement.scene() and measurement.scene().views()
        else None
    )
    return (1.0 / graphics_view_uniform_zoom(view)) if view is not None else 1.0


def sync_measurement_geometry_after_external_move(measurement: Any) -> None:
    """Translate endpoints/line/text/handles after an external group position change."""
    current_pos = measurement.pos()
    if current_pos == measurement.start_point:
        return
    delta = current_pos - measurement.start_point
    measurement.start_point += delta
    measurement.end_point += delta
    measurement.end_relative = measurement.end_point - measurement.start_point
    measurement.line_item.prepareGeometryChange()
    if measurement.scene() is not None:
        measurement.scene().invalidate(
            measurement.line_item.mapRectToScene(measurement.line_item.boundingRect())
        )
    measurement.line_item.setLine(QLineF(QPointF(0, 0), measurement.end_relative))
    if measurement.scene() is not None:
        measurement.scene().invalidate(
            measurement.line_item.mapRectToScene(measurement.line_item.boundingRect())
        )
        measurement.scene().invalidate(measurement.mapRectToScene(measurement.boundingRect()))
    measurement.line_item.update()
    measurement.update()

    mid_point_scene = QPointF(
        (measurement.start_point.x() + measurement.end_point.x()) / 2.0,
        (measurement.start_point.y() + measurement.end_point.y()) / 2.0,
    )
    viewport_to_scene_scale = _viewport_to_scene_scale(measurement)
    measurement.text_offset = QPointF(
        measurement.text_offset_viewport.x() * viewport_to_scene_scale,
        measurement.text_offset_viewport.y() * viewport_to_scene_scale,
    )
    text_pos_scene = mid_point_scene + measurement.text_offset

    # Avoid importing measurement_items at module load (circular).
    text_item = measurement.text_item
    if hasattr(text_item, "_updating_position"):
        text_item._updating_position = True
    text_item.setPos(text_pos_scene)
    if hasattr(text_item, "_updating_position"):
        text_item._updating_position = False
    measurement.update_handle_positions(force=True)


def apply_measurement_group_position_has_changed(measurement: Any) -> bool:
    """
    Handle MeasurementItem ItemPositionHasChanged.

    Returns:
        True when the caller should return *value* immediately (skip ``super``).
    """
    if measurement._last_drag_pos is not None:
        return True
    if measurement.on_moved_callback:
        try:
            measurement.on_moved_callback()
        except Exception:
            pass
    # Mirror the original nested ``if self._last_drag_pos is None:`` guard: when
    # still None, early-return on update/handle-drag flags or sync geometry;
    # otherwise fall through to ``super``.
    if measurement._last_drag_pos is not None:
        return False
    if hasattr(measurement, "_updating_handles") and measurement._updating_handles:
        return True
    if getattr(measurement, "_handle_drag_in_progress", False):
        return True
    sync_measurement_geometry_after_external_move(measurement)
    return False


def apply_measurement_group_selection_changed(measurement: Any, selected: object) -> bool:
    """
    Show or hide handles when selection changes.

    Returns:
        True when the caller should return *value* immediately (skip ``super``).
    """
    if selected:
        if hasattr(measurement, "_handle_drag_in_progress") and measurement._handle_drag_in_progress:
            return True
        measurement.show_handles()
    else:
        if hasattr(measurement, "_handle_drag_in_progress"):
            measurement._handle_drag_in_progress = False
        if hasattr(measurement, "_dragging_handle"):
            measurement._dragging_handle = None
        measurement.hide_handles()
    measurement.update()
    return False


def process_measurement_group_item_change(
    measurement: Any,
    change: QGraphicsItem.GraphicsItemChange,
    value: object,
) -> tuple[bool, object]:
    """
    Process MeasurementItem.itemChange special cases.

    Returns:
        ``(True, result)`` to return immediately (skip ``super``), or
        ``(False, value)`` to call ``super().itemChange(change, value)``.
    """
    if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
        return True, resolve_measurement_group_position_change(
            measurement, cast(QPointF, value)
        )

    if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
        if apply_measurement_group_position_has_changed(measurement):
            return True, value
        return False, value

    if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
        if apply_measurement_group_selection_changed(measurement, value):
            return True, value
        return False, value

    if change == QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged:
        if value is not None:
            measurement.update_text_offset_for_zoom()
        return True, value

    return False, value
