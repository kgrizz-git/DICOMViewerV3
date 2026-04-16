"""
Angle measurement graphics — two connected segments with interior angle at the middle vertex.

Implements Option B from the product plan: click P1, then P2 (first segment), then P3;
the reported angle is at P2 between segments P1–P2 and P2–P3 (in-plane, scene coordinates).

Inputs:
    - Three scene points (QPointF), shared measurement pen/font from ConfigManager via caller.

Outputs:
    - ``AngleMeasurementItem`` (selectable group + separate draggable label), vertex handles.

Requirements:
    - PySide6 (QtWidgets, QtCore, QtGui)
    - ``gui.view_transform_helpers.graphics_view_uniform_zoom``
    - ``utils.bundled_fonts.make_qfont`` for label font
"""

from __future__ import annotations

import math
from typing import Callable, Optional

from PySide6.QtCore import Qt, QPointF, QLineF, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsItemGroup,
    QGraphicsLineItem,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
    QStyle,
)

from gui.view_transform_helpers import graphics_view_uniform_zoom
from utils.bundled_fonts import make_qfont


def interior_angle_at_vertex_degrees(p1: QPointF, p2: QPointF, p3: QPointF) -> float:
    """
    Return the interior angle (0–180°) at vertex P2 between segments P1–P2 and P2–P3.

    Uses 2D vectors in scene coordinates (in-plane angle on the image).
    """
    v1x = p1.x() - p2.x()
    v1y = p1.y() - p2.y()
    v2x = p3.x() - p2.x()
    v2y = p3.y() - p2.y()
    cross = v1x * v2y - v1y * v2x
    dot = v1x * v2x + v1y * v2y
    return math.degrees(math.atan2(abs(cross), dot))


def format_angle_label(degrees: float) -> str:
    """Human-readable angle string for overlay."""
    if degrees >= 100.0 or degrees == 0.0:
        return f"{degrees:.1f}°"
    return f"{degrees:.2f}°"


class DraggableAngleMeasurementText(QGraphicsTextItem):
    """Draggable label for angle; anchor offset is relative to vertex P2."""

    def __init__(
        self,
        measurement: Optional["AngleMeasurementItem"],
        offset_update_callback: Callable[[QPointF], None],
    ) -> None:
        super().__init__()
        self.measurement = measurement
        self.offset_update_callback = offset_update_callback
        self._updating_position = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: object) -> object:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and not self._updating_position:
            if self.measurement is not None:
                text_pos_scene = self.pos()
                anchor = self.measurement.p2
                offset_scene = text_pos_scene - anchor
                view = self.scene().views()[0] if self.scene() and self.scene().views() else None
                scene_to_viewport_scale = (
                    graphics_view_uniform_zoom(view) if view is not None else 1.0
                )
                offset_viewport = QPointF(
                    offset_scene.x() * scene_to_viewport_scale,
                    offset_scene.y() * scene_to_viewport_scale,
                )
                self.measurement.text_offset_viewport = offset_viewport
                if self.offset_update_callback:
                    self.offset_update_callback(offset_scene)
        return super().itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        event.accept()
        if self.measurement is not None and self.measurement.isSelected():
            self.measurement.setSelected(False)
        self.setSelected(True)
        super().mousePressEvent(event)


class AngleVertexHandle(QGraphicsEllipseItem):
    """Resize handle for one of the three angle vertices (scene coordinates)."""

    def __init__(self, measurement: "AngleMeasurementItem", vertex_index: int, color: Optional[QColor] = None) -> None:
        handle_size = 6.0
        super().__init__(-handle_size, -handle_size, handle_size * 2, handle_size * 2)
        self.parent_measurement = measurement
        self.vertex_index = vertex_index
        handle_color = color if color is not None else QColor(0, 255, 0)
        handle_pen = QPen(handle_color, 2)
        handle_color_with_alpha = QColor(handle_color.red(), handle_color.green(), handle_color.blue(), 180)
        self.setPen(handle_pen)
        self.setBrush(QBrush(handle_color_with_alpha))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(200)
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        if (
            self.parent_measurement is not None
            and getattr(self.parent_measurement, "_dragging_handle", None) is self
        ):
            return
        super().paint(painter, option, widget)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        hit_radius = 18.0
        path.addEllipse(QRectF(-hit_radius, -hit_radius, hit_radius * 2, hit_radius * 2))
        return path

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        event.accept()
        if self.parent_measurement is not None:
            if not self.parent_measurement.isSelected():
                self.parent_measurement.setSelected(True)
            self.parent_measurement._handle_drag_in_progress = True
            self.parent_measurement._dragging_handle = self
            self.update()
            start_callback = self.parent_measurement.on_handle_drag_start_callback
            if start_callback is not None:
                try:
                    modifiers = event.modifiers()
                    shift_held = (modifiers & Qt.KeyboardModifier.ShiftModifier) != 0
                    start_callback(self.pos(), shift_held)
                except Exception:
                    pass
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        event.accept()
        if self.parent_measurement is not None:
            end_callback = self.parent_measurement.on_handle_drag_end_callback
            if end_callback is not None:
                try:
                    end_callback()
                except Exception:
                    pass
            self.parent_measurement._handle_drag_in_progress = False
            self.parent_measurement._dragging_handle = None
            self.update()
            self.parent_measurement.show_handles_after_drag()
        super().mouseReleaseEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: object) -> object:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.parent_measurement is None or self.parent_measurement.scene() is None:
                return value
            if getattr(self.parent_measurement, "_updating_handles", False):
                return value
            scene_pos = self.pos()
            m = self.parent_measurement
            m._updating_handles = True
            try:
                if self.vertex_index == 0:
                    m.p1 = scene_pos
                elif self.vertex_index == 1:
                    m.p2 = scene_pos
                    m.setPos(m.p2)
                else:
                    m.p3 = scene_pos
                m.update_angle_geometry()
                if m.h0 is not None and m.h0.scene() is not None:
                    m.h0.setPos(m.p1)
                if m.h1 is not None and m.h1.scene() is not None:
                    m.h1.setPos(m.p2)
                if m.h2 is not None and m.h2.scene() is not None:
                    m.h2.setPos(m.p3)
                if m.on_moved_callback:
                    try:
                        m.on_moved_callback()
                    except Exception:
                        pass
                move_callback = m.on_handle_drag_move_callback
                if move_callback is not None:
                    try:
                        move_callback(self.pos())
                    except Exception:
                        pass
            finally:
                m._updating_handles = False
        return super().itemChange(change, value)


HandleDragStartCallback = Callable[[QPointF, bool], None]
HandleDragMoveCallback = Callable[[QPointF], None]
HandleDragEndCallback = Callable[[], None]


class AngleMeasurementItem(QGraphicsItemGroup):
    """Two-line angle overlay with draggable label and three vertex handles."""

    def __init__(
        self,
        p1: QPointF,
        p2: QPointF,
        p3: QPointF,
        line1_item: QGraphicsLineItem,
        line2_item: QGraphicsLineItem,
        text_item: QGraphicsTextItem,
    ) -> None:
        super().__init__()
        self.p1 = QPointF(p1)
        self.p2 = QPointF(p2)
        self.p3 = QPointF(p3)
        self.line1_item = line1_item
        self.line2_item = line2_item
        self.text_item = text_item
        self.angle_degrees = interior_angle_at_vertex_degrees(self.p1, self.p2, self.p3)
        self.angle_formatted = format_angle_label(self.angle_degrees)
        self.text_offset_viewport = QPointF(0, -30)
        self.text_offset = QPointF(0, 0)

        self.addToGroup(line1_item)
        self.addToGroup(line2_item)
        line1_item.setZValue(150)
        line2_item.setZValue(150)

        line_pen = line1_item.pen()
        line_color = line_pen.color() if line_pen.color().isValid() else QColor(0, 255, 0)

        self.h0 = AngleVertexHandle(self, 0, line_color)
        self.h1 = AngleVertexHandle(self, 1, line_color)
        self.h2 = AngleVertexHandle(self, 2, line_color)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

        self._updating_handles = False
        self._handle_drag_in_progress = False
        self._dragging_handle: Optional[AngleVertexHandle] = None
        self._last_drag_pos: Optional[QPointF] = None

        self.on_moved_callback: Optional[Callable[[], None]] = None
        self.on_mouse_release_callback: Optional[Callable[[], None]] = None
        self.on_handle_drag_start_callback: Optional[HandleDragStartCallback] = None
        self.on_handle_drag_move_callback: Optional[HandleDragMoveCallback] = None
        self.on_handle_drag_end_callback: Optional[HandleDragEndCallback] = None

        self.setPos(self.p2)
        self.update_angle_geometry()

    def boundingRect(self) -> QRectF:
        r1 = self.line1_item.boundingRect()
        r2 = self.line2_item.boundingRect()
        return r1.united(r2).adjusted(-2, -2, 2, 2)

    def shape(self) -> QPainterPath:
        pen = QPen(QColor(0, 255, 0), 4)
        stroker = QPainterPathStroker(pen)
        p = QPainterPath()
        ln1 = self.line1_item.line()
        p.moveTo(ln1.p1())
        p.lineTo(ln1.p2())
        ln2 = self.line2_item.line()
        p.moveTo(ln2.p1())
        p.lineTo(ln2.p2())
        return stroker.createStroke(p)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        is_selected = self.isSelected()
        original_state = option.state
        option.state = option.state & ~QStyle.StateFlag.State_Selected
        super().paint(painter, option, widget)
        option.state = original_state
        if is_selected:
            painter.save()
            selection_pen = QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine)
            painter.setPen(selection_pen)
            painter.drawLine(self.line1_item.line())
            painter.drawLine(self.line2_item.line())
            painter.restore()

    def show_handles(self) -> None:
        if getattr(self, "_handle_drag_in_progress", False):
            return
        if self.scene() is None:
            return
        for h in (self.h0, self.h1, self.h2):
            if h.scene() != self.scene():
                self.scene().addItem(h)
        self.update_handle_positions(force=True)
        self.h0.show()
        self.h1.show()
        self.h2.show()

    def hide_handles(self) -> None:
        for h in (self.h0, self.h1, self.h2):
            if h is not None and h.scene() is not None:
                h.scene().removeItem(h)

    def show_handles_after_drag(self) -> None:
        if self.h0 is not None and self.h0.scene() is not None:
            self.h0.setVisible(True)
        if self.h1 is not None and self.h1.scene() is not None:
            self.h1.setVisible(True)
        if self.h2 is not None and self.h2.scene() is not None:
            self.h2.setVisible(True)
        self.update_angle_geometry()
        self.update_handle_positions(force=True)

    def update_handle_positions(self, force: bool = False) -> None:
        if getattr(self, "_handle_drag_in_progress", False):
            return
        if self.scene() is None:
            return
        if not force and getattr(self, "_updating_handles", False):
            return
        if not self.isSelected():
            return
        was = self._updating_handles
        self._updating_handles = True
        try:
            self.h0.setPos(self.p1)
            self.h1.setPos(self.p2)
            self.h2.setPos(self.p3)
        finally:
            self._updating_handles = was

    def update_angle_geometry(self) -> None:
        """Recompute angle text and line geometry (group origin at p2)."""
        self.angle_degrees = interior_angle_at_vertex_degrees(self.p1, self.p2, self.p3)
        self.angle_formatted = format_angle_label(self.angle_degrees)
        rel1 = self.p1 - self.p2
        rel3 = self.p3 - self.p2
        if self.pos() != self.p2:
            self.setPos(self.p2)
        self.line1_item.prepareGeometryChange()
        self.line2_item.prepareGeometryChange()
        self.line1_item.setLine(QLineF(rel1, QPointF(0, 0)))
        self.line2_item.setLine(QLineF(QPointF(0, 0), rel3))
        self.line1_item.update()
        self.line2_item.update()
        self.update()

        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        viewport_to_scene_scale = (
            (1.0 / graphics_view_uniform_zoom(view)) if view is not None else 1.0
        )
        self.text_offset = QPointF(
            self.text_offset_viewport.x() * viewport_to_scene_scale,
            self.text_offset_viewport.y() * viewport_to_scene_scale,
        )
        text_pos_scene = self.p2 + self.text_offset
        if isinstance(self.text_item, DraggableAngleMeasurementText):
            self.text_item._updating_position = True
        self.text_item.setPos(text_pos_scene)
        self.text_item.setPlainText(self.angle_formatted)
        if isinstance(self.text_item, DraggableAngleMeasurementText):
            self.text_item._updating_position = False

        if not getattr(self, "_handle_drag_in_progress", False):
            self.update_handle_positions(force=True)

    def update_text_offset_for_zoom(self) -> None:
        if self.text_item is None:
            return
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        viewport_to_scene_scale = (
            (1.0 / graphics_view_uniform_zoom(view)) if view is not None else 1.0
        )
        self.text_offset = QPointF(
            self.text_offset_viewport.x() * viewport_to_scene_scale,
            self.text_offset_viewport.y() * viewport_to_scene_scale,
        )
        text_pos_scene = self.p2 + self.text_offset
        if isinstance(self.text_item, DraggableAngleMeasurementText):
            self.text_item._updating_position = True
        self.text_item.setPos(text_pos_scene)
        if isinstance(self.text_item, DraggableAngleMeasurementText):
            self.text_item._updating_position = False

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        self._last_drag_pos = self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if getattr(self, "_dragging_handle", None) is not None:
            return
        current_pos = self.pos()
        if self._last_drag_pos is not None:
            delta = current_pos - self._last_drag_pos
            if delta.x() != 0 or delta.y() != 0:
                self.p1 += delta
                self.p2 += delta
                self.p3 += delta
                self.update_angle_geometry()
                self._last_drag_pos = current_pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if getattr(self, "_dragging_handle", None) is not None:
            return
        if self.on_mouse_release_callback:
            try:
                self.on_mouse_release_callback()
            except Exception:
                pass
        self._last_drag_pos = None
        super().mouseReleaseEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: object) -> object:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if getattr(self, "_updating_handles", False):
                return value
            if getattr(self, "_handle_drag_in_progress", False):
                return self.pos()
            return value

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self._last_drag_pos is not None:
                return value
            if self.on_moved_callback:
                try:
                    self.on_moved_callback()
                except Exception:
                    pass
            if self._last_drag_pos is None:
                if getattr(self, "_updating_handles", False):
                    return value
                if getattr(self, "_handle_drag_in_progress", False):
                    return value
                current_pos = self.pos()
                if current_pos != self.p2:
                    delta = current_pos - self.p2
                    self.p1 += delta
                    self.p2 += delta
                    self.p3 += delta
                    self.update_angle_geometry()

        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if value:
                if getattr(self, "_handle_drag_in_progress", False):
                    return value
                self.show_handles()
            else:
                self._handle_drag_in_progress = False
                self._dragging_handle = None
                self.hide_handles()
            self.update()

        elif change == QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged:
            if value is not None:
                self.update_text_offset_for_zoom()
            return value

        return super().itemChange(change, value)
