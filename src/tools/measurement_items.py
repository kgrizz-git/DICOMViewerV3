"""
Measurement Items – graphics classes for the measurement tool.

This module provides the Qt graphics item classes used to display and edit
distance measurements: draggable text label, resize handles, and the
measurement group (line + text + handles).

Purpose:
    - Host DraggableMeasurementText, MeasurementHandle, and MeasurementItem
    - Used by measurement_tool.MeasurementTool to create and manage measurements

Inputs:
    - Scene coordinates (QPointF), pixel spacing, line/text items from MeasurementTool

Outputs:
    - Graphics items that can be added to a QGraphicsScene

Requirements:
    - PySide6 (QtWidgets, QtCore, QtGui)
    - typing, math
"""

from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsTextItem,
    QGraphicsItemGroup,
    QGraphicsItem,
    QGraphicsEllipseItem,
    QGraphicsSceneMouseEvent,
    QStyle,
)
from PySide6.QtCore import Qt, QPointF, QLineF, QRectF
from PySide6.QtGui import QPen, QColor, QBrush, QPainter, QPainterPath, QPainterPathStroker
from typing import Optional, Tuple, Callable
import math


class DraggableMeasurementText(QGraphicsTextItem):
    """
    Custom QGraphicsTextItem for measurement text overlays that tracks position changes.
    """

    def __init__(self, measurement: Optional['MeasurementItem'], offset_update_callback: Callable[[QPointF], None]):
        """
        Initialize draggable measurement text.

        Args:
            measurement: MeasurementItem this text belongs to (can be None initially)
            offset_update_callback: Callback to update offset when text is moved
        """
        super().__init__()
        self.measurement = measurement
        self.offset_update_callback = offset_update_callback
        self._updating_position = False  # Flag to prevent recursive updates
        # Make text item selectable and movable so it can be moved independently
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """
        Handle item changes, particularly position changes.

        Args:
            change: Type of change
            value: New value

        Returns:
            Modified value
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and not self._updating_position:
            # Text was moved by user - calculate new offset relative to measurement midpoint
            if self.measurement is not None:
                # Position is in scene coordinates (text is not a child of group)
                text_pos_scene = self.pos()
                # Calculate midpoint of measurement line in scene coordinates
                mid_point_scene = QPointF(
                    (self.measurement.start_point.x() + self.measurement.end_point.x()) / 2.0,
                    (self.measurement.start_point.y() + self.measurement.end_point.y()) / 2.0
                )
                # Calculate offset from midpoint in scene coordinates
                offset_scene = text_pos_scene - mid_point_scene

                # Convert scene offset to viewport pixels for storage
                # Get view for coordinate conversion
                view = self.scene().views()[0] if self.scene() and self.scene().views() else None
                if view is not None:
                    view_scale = view.transform().m11()
                    if view_scale > 0:
                        scene_to_viewport_scale = view_scale
                    else:
                        scene_to_viewport_scale = 1.0
                else:
                    scene_to_viewport_scale = 1.0

                # Convert to viewport pixels
                offset_viewport = QPointF(
                    offset_scene.x() * scene_to_viewport_scale,
                    offset_scene.y() * scene_to_viewport_scale
                )

                # Update stored offset in viewport pixels
                self.measurement.text_offset_viewport = offset_viewport

                # Update stored offset (for backward compatibility)
                if self.offset_update_callback:
                    self.offset_update_callback(offset_scene)

        return super().itemChange(change, value)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """
        Handle mouse press to allow independent selection/dragging.

        Accepts the event to prevent parent group from handling it,
        allowing the text to be selected and moved independently.

        Args:
            event: Mouse event
        """
        event.accept()  # Accept to prevent parent group from handling it

        # Deselect measurement group if it's selected (text is not a child, so check via measurement reference)
        # This prevents Qt from moving both the text and measurement together when both are selected
        if self.measurement is not None and self.measurement.isSelected():
            self.measurement.setSelected(False)

        # Select this text item
        self.setSelected(True)

        super().mousePressEvent(event)


class MeasurementHandle(QGraphicsEllipseItem):
    """
    Handle for editing measurement endpoints.

    Child of MeasurementItem group for automatic movement and lifecycle management.
    """

    def __init__(self, measurement: 'MeasurementItem', is_start: bool, color: Optional[QColor] = None):
        """
        Initialize handle as separate scene item (not a child).

        Args:
            measurement: Parent MeasurementItem (reference only, not Qt parent)
            is_start: True if this is the start handle, False for end handle
            color: Optional QColor for handle (defaults to green if None)
        """
        handle_size = 6.0  # Smaller handle size
        # Don't pass measurement as Qt parent - handle is independent scene item
        super().__init__(-handle_size, -handle_size, handle_size * 2, handle_size * 2)
        self.parent_measurement = measurement
        self.is_start = is_start
        self._parent_was_movable = False  # Track parent's original movability state

        # Styling - use provided color or default to green
        handle_color = color if color is not None else QColor(0, 255, 0)
        handle_pen = QPen(handle_color, 2)
        # Create color with alpha for brush
        handle_color_with_alpha = QColor(handle_color.red(), handle_color.green(), handle_color.blue(), 180)
        handle_brush = QBrush(handle_color_with_alpha)
        self.setPen(handle_pen)
        self.setBrush(handle_brush)

        # Flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)  # CRITICAL: Enable itemChange() notifications
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)  # Keep handle size fixed on screen
        self.setZValue(200)  # Above measurement (150) for priority selection

        # Cursor for better UX
        self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """
        Handle mouse press to keep measurement selected and set drag flag.

        Args:
            event: Mouse press event
        """
        event.accept()

        # Set flag on parent to indicate handle drag is in progress
        if self.parent_measurement is not None:
            if not self.parent_measurement.isSelected():
                self.parent_measurement.setSelected(True)

            self.parent_measurement._handle_drag_in_progress = True
            self.parent_measurement._dragging_handle = self

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """Handle mouse move during drag."""
        event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """Handle mouse release after drag."""
        event.accept()

        if self.parent_measurement is not None:
            if hasattr(self.parent_measurement, '_handle_drag_in_progress'):
                self.parent_measurement._handle_drag_in_progress = False
            if hasattr(self.parent_measurement, '_dragging_handle'):
                self.parent_measurement._dragging_handle = None

        super().mouseReleaseEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """
        Handle position changes to update parent measurement.

        Args:
            change: Type of change
            value: New value (scene coordinates since handle is a separate item)

        Returns:
            Modified value
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            return value

        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.parent_measurement is not None:
                if self.parent_measurement.scene() is None:
                    return value

                if hasattr(self.parent_measurement, '_updating_handles'):
                    if self.parent_measurement._updating_handles:
                        return value

                scene_pos = self.pos()

                self.parent_measurement._updating_handles = True

                try:
                    if self.is_start:
                        original_end_point = self.parent_measurement.end_point
                        original_start_point = self.parent_measurement.start_point

                        self.parent_measurement.start_point = scene_pos
                        self.parent_measurement.setPos(self.parent_measurement.start_point)
                        self.parent_measurement.end_point = original_end_point
                        self.parent_measurement.end_relative = (
                            self.parent_measurement.end_point -
                            self.parent_measurement.start_point
                        )
                        self.parent_measurement.update_distance()
                        self.parent_measurement.line_item.update()
                        self.parent_measurement.update()

                        if self.parent_measurement.scene() is not None:
                            line_rect = self.parent_measurement.line_item.boundingRect()
                            line_scene_rect = self.parent_measurement.line_item.mapRectToScene(line_rect)
                            self.parent_measurement.scene().update(line_scene_rect)
                    else:
                        original_end_point = self.parent_measurement.end_point
                        original_start_point = self.parent_measurement.start_point

                        self.parent_measurement.end_point = scene_pos
                        self.parent_measurement.end_relative = (
                            self.parent_measurement.end_point -
                            self.parent_measurement.start_point
                        )
                        self.parent_measurement.update_distance()
                        self.parent_measurement.line_item.update()
                        self.parent_measurement.update()

                        if self.parent_measurement.scene() is not None:
                            line_rect = self.parent_measurement.line_item.boundingRect()
                            line_scene_rect = self.parent_measurement.line_item.mapRectToScene(line_rect)
                            self.parent_measurement.scene().update(line_scene_rect)
                finally:
                    self.parent_measurement._updating_handles = False

                if self.parent_measurement.on_moved_callback:
                    try:
                        self.parent_measurement.on_moved_callback()
                    except Exception:
                        pass

        return super().itemChange(change, value)


class MeasurementItem(QGraphicsItemGroup):
    """
    Represents a single distance measurement.

    Inherits from QGraphicsItemGroup to treat line and text as a single selectable/movable entity.
    """

    def __init__(self, start_point: QPointF, end_point: QPointF,
                 line_item: QGraphicsLineItem, text_item: QGraphicsTextItem,
                 pixel_spacing: Optional[Tuple[float, float]] = None):
        """
        Initialize measurement item.

        Args:
            start_point: Start point of measurement
            end_point: End point of measurement
            line_item: Graphics line item
            text_item: Graphics text item for label
            pixel_spacing: Optional pixel spacing for distance calculation
        """
        super().__init__()

        self.start_point = start_point
        self.end_point = end_point
        self.line_item = line_item
        self.text_item = text_item
        self.pixel_spacing = pixel_spacing
        self.distance_pixels = 0.0
        self.distance_formatted = ""
        self.text_offset_viewport = QPointF(0, -30)
        self.text_offset = QPointF(0, 0)

        self.end_relative = end_point - start_point

        line_scene_pos = line_item.pos()
        text_scene_pos = text_item.pos()

        self.addToGroup(line_item)

        line_item.setZValue(150)
        text_item.setZValue(151)

        line_pen = line_item.pen()
        line_color = line_pen.color() if line_pen.color().isValid() else QColor(0, 255, 0)

        self.setPos(start_point)
        line_item.setPos(QPointF(0, 0))

        self.start_handle = MeasurementHandle(self, is_start=True, color=line_color)
        self.end_handle = MeasurementHandle(self, is_start=False, color=line_color)

        self.start_handle.setZValue(200)
        self.end_handle.setZValue(200)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)

        self._updating_handles = False
        self._handle_drag_in_progress = False
        self._dragging_handle: Optional[MeasurementHandle] = None
        self._last_drag_pos: Optional[QPointF] = None

        self.on_moved_callback: Optional[Callable[[], None]] = None
        self.on_mouse_release_callback: Optional[Callable[[], None]] = None

        self.update_distance()

    def boundingRect(self) -> QRectF:
        """Return bounding rectangle for the measurement (line and text only; handles are separate)."""
        line_rect = self.line_item.boundingRect()
        text_rect = self.text_item.boundingRect()
        text_pos = self.text_item.pos()
        text_rect.translate(text_pos)
        combined_rect = line_rect.united(text_rect)
        padding = 2.0
        combined_rect.adjust(-padding, -padding, padding, padding)
        return combined_rect

    def shape(self) -> QPainterPath:
        """Return shape for hit testing - stroked line only."""
        line = self.line_item.line()
        line_path = QPainterPath()
        line_path.moveTo(line.p1())
        line_path.lineTo(line.p2())
        pen = QPen(QColor(0, 255, 0), 4)
        stroker = QPainterPathStroker(pen)
        return stroker.createStroke(line_path)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        """Paint selection indicator when item is selected (yellow dashed line)."""
        is_selected = self.isSelected()
        original_state = option.state
        option.state = option.state & ~QStyle.StateFlag.State_Selected

        super().paint(painter, option, widget)

        option.state = original_state

        if is_selected:
            painter.save()
            selection_pen = QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine)
            painter.setPen(selection_pen)
            line = self.line_item.line()
            painter.drawLine(line)
            painter.restore()

    def show_handles(self) -> None:
        """Show handles when measurement is selected (add to scene and position)."""
        if self.scene() is None:
            return
        if self.start_handle is None or self.end_handle is None:
            return
        if self.start_handle.scene() != self.scene():
            self.scene().addItem(self.start_handle)
        if self.end_handle.scene() != self.scene():
            self.scene().addItem(self.end_handle)
        self.update_handle_positions()
        self.start_handle.show()
        self.end_handle.show()

    def hide_handles(self) -> None:
        """Hide handles when measurement is deselected (remove from scene)."""
        if self.start_handle is not None and self.start_handle.scene() is not None:
            self.start_handle.scene().removeItem(self.start_handle)
        if self.end_handle is not None and self.end_handle.scene() is not None:
            self.end_handle.scene().removeItem(self.end_handle)

    def update_handle_positions(self, force: bool = False) -> None:
        """Update handle positions in scene coordinates."""
        if self.scene() is None or self.start_handle is None or self.end_handle is None:
            return
        if not force and hasattr(self, '_updating_handles') and self._updating_handles:
            return
        if self.isSelected():
            if self.start_handle.scene() != self.scene():
                self.scene().addItem(self.start_handle)
            if self.end_handle.scene() != self.scene():
                self.scene().addItem(self.end_handle)
        if self.start_handle.scene() is None or self.end_handle.scene() is None:
            return
        was_updating = getattr(self, '_updating_handles', False)
        self._updating_handles = True
        try:
            self.start_handle.setPos(self.start_point)
            self.end_handle.setPos(self.end_point)
        finally:
            self._updating_handles = was_updating

    def update_distance(self, pixel_spacing: Optional[Tuple[float, float]] = None) -> None:
        """Update distance calculation and label; refresh line, text, and handle positions."""
        spacing = pixel_spacing if pixel_spacing is not None else self.pixel_spacing
        if spacing is not None:
            self.pixel_spacing = spacing

        dx = self.end_point.x() - self.start_point.x()
        dy = self.end_point.y() - self.start_point.y()

        if spacing:
            dx_scaled = dx * spacing[1]
            dy_scaled = dy * spacing[0]
            distance_mm = math.sqrt(dx_scaled * dx_scaled + dy_scaled * dy_scaled)
            self.distance_pixels = math.sqrt(dx * dx + dy * dy)
            self.distance_formatted = f"{distance_mm:.1f} mm" if distance_mm >= 10 else f"{distance_mm:.2f} mm"
        else:
            self.distance_pixels = math.sqrt(dx * dx + dy * dy)
            self.distance_formatted = f"{self.distance_pixels:.1f} pixels"

        self.end_relative = self.end_point - self.start_point

        line = QLineF(QPointF(0, 0), self.end_relative)
        self.line_item.prepareGeometryChange()
        if self.scene() is not None:
            old_line_rect = self.line_item.boundingRect()
            old_line_scene_rect = self.line_item.mapRectToScene(old_line_rect)
            self.scene().invalidate(old_line_scene_rect)
        self.line_item.setLine(line)
        if self.scene() is not None:
            new_line_rect = self.line_item.boundingRect()
            new_line_scene_rect = self.line_item.mapRectToScene(new_line_rect)
            self.scene().invalidate(new_line_scene_rect)
            group_rect = self.boundingRect()
            group_scene_rect = self.mapRectToScene(group_rect)
            self.scene().invalidate(group_scene_rect)
        self.line_item.update()
        self.update()

        mid_point_scene = QPointF(
            (self.start_point.x() + self.end_point.x()) / 2.0,
            (self.start_point.y() + self.end_point.y()) / 2.0
        )
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view is not None:
            view_scale = view.transform().m11()
            viewport_to_scene_scale = 1.0 / view_scale if view_scale > 0 else 1.0
        else:
            viewport_to_scene_scale = 1.0
        self.text_offset = QPointF(
            self.text_offset_viewport.x() * viewport_to_scene_scale,
            self.text_offset_viewport.y() * viewport_to_scene_scale
        )
        text_pos_scene = mid_point_scene + self.text_offset

        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = True
        self.text_item.setPos(text_pos_scene)
        self.text_item.setPlainText(self.distance_formatted)
        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = False

        current_group_pos = self.pos()
        if current_group_pos != self.start_point:
            self.setPos(self.start_point)

        self.update_handle_positions(force=True)

    def update_text_offset_for_zoom(self) -> None:
        """Recalculate text offset when zoom changes (viewport pixel offset -> scene)."""
        if self.text_item is None:
            return
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view is not None:
            view_scale = view.transform().m11()
            viewport_to_scene_scale = 1.0 / view_scale if view_scale > 0 else 1.0
        else:
            viewport_to_scene_scale = 1.0
        self.text_offset = QPointF(
            self.text_offset_viewport.x() * viewport_to_scene_scale,
            self.text_offset_viewport.y() * viewport_to_scene_scale
        )
        mid_point_scene = QPointF(
            (self.start_point.x() + self.end_point.x()) / 2.0,
            (self.start_point.y() + self.end_point.y()) / 2.0
        )
        text_pos_scene = mid_point_scene + self.text_offset
        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = True
        self.text_item.setPos(text_pos_scene)
        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = False

    def mousePressEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """Store drag start position; let handles receive their own events."""
        self._last_drag_pos = self.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """Update line/text/handles when dragging the measurement line; ignore if handle is dragging."""
        if hasattr(self, '_dragging_handle') and self._dragging_handle is not None:
            return
        current_pos = self.pos()
        if self._last_drag_pos is not None:
            delta = current_pos - self._last_drag_pos
            if delta.x() != 0 or delta.y() != 0:
                self.start_point += delta
                self.end_point += delta
                self.end_relative = self.end_point - self.start_point
                self.line_item.prepareGeometryChange()
                if self.scene() is not None:
                    old_line_rect = self.line_item.boundingRect()
                    self.scene().invalidate(self.line_item.mapRectToScene(old_line_rect))
                self.line_item.setLine(QLineF(QPointF(0, 0), self.end_relative))
                if self.scene() is not None:
                    new_line_rect = self.line_item.boundingRect()
                    self.scene().invalidate(self.line_item.mapRectToScene(new_line_rect))
                    self.scene().invalidate(self.mapRectToScene(self.boundingRect()))
                self.line_item.update()
                self.update()
                mid_point_scene = QPointF(
                    (self.start_point.x() + self.end_point.x()) / 2.0,
                    (self.start_point.y() + self.end_point.y()) / 2.0
                )
                view = self.scene().views()[0] if self.scene() and self.scene().views() else None
                viewport_to_scene_scale = (1.0 / view.transform().m11()) if view and view.transform().m11() > 0 else 1.0
                self.text_offset = QPointF(
                    self.text_offset_viewport.x() * viewport_to_scene_scale,
                    self.text_offset_viewport.y() * viewport_to_scene_scale
                )
                text_pos_scene = mid_point_scene + self.text_offset
                if isinstance(self.text_item, DraggableMeasurementText):
                    self.text_item._updating_position = True
                self.text_item.setPos(text_pos_scene)
                if isinstance(self.text_item, DraggableMeasurementText):
                    self.text_item._updating_position = False
                self.update_handle_positions(force=True)
                self._last_drag_pos = current_pos
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """Run move callback and clear drag tracking; ignore if handle is dragging."""
        if hasattr(self, '_dragging_handle') and self._dragging_handle is not None:
            return
        if self.on_mouse_release_callback:
            try:
                self.on_mouse_release_callback()
            except Exception:
                pass
        self._last_drag_pos = None
        super().mouseReleaseEvent(event)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """Handle position/selection/scene changes: sync points, show/hide handles, zoom text offset."""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if hasattr(self, '_updating_handles') and self._updating_handles:
                return value
            new_pos = value
            old_pos = self.pos()
            delta = new_pos - old_pos
            self.start_point += delta
            self.end_point += delta
            self.end_relative = self.end_point - self.start_point
            self.line_item.prepareGeometryChange()
            if self.scene() is not None:
                self.scene().invalidate(self.line_item.mapRectToScene(self.line_item.boundingRect()))
            self.line_item.setLine(QLineF(QPointF(0, 0), self.end_relative))
            if self.scene() is not None:
                self.scene().invalidate(self.line_item.mapRectToScene(self.line_item.boundingRect()))
                self.scene().invalidate(self.mapRectToScene(self.boundingRect()))
            self.line_item.update()
            self.update()
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            viewport_to_scene_scale = (1.0 / view.transform().m11()) if view and view.transform().m11() > 0 else 1.0
            self.text_offset = QPointF(
                self.text_offset_viewport.x() * viewport_to_scene_scale,
                self.text_offset_viewport.y() * viewport_to_scene_scale
            )
            mid_point_scene = QPointF(
                (self.start_point.x() + self.end_point.x()) / 2.0,
                (self.start_point.y() + self.end_point.y()) / 2.0
            )
            text_pos_scene = mid_point_scene + self.text_offset
            if isinstance(self.text_item, DraggableMeasurementText):
                self.text_item._updating_position = True
            self.text_item.setPos(text_pos_scene)
            if isinstance(self.text_item, DraggableMeasurementText):
                self.text_item._updating_position = False
            self.update_handle_positions(force=True)
            return self.start_point

        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.on_moved_callback:
                try:
                    self.on_moved_callback()
                except Exception:
                    pass
            if self._last_drag_pos is None:
                if hasattr(self, '_updating_handles') and self._updating_handles:
                    return value
                current_pos = self.pos()
                if current_pos != self.start_point:
                    delta = current_pos - self.start_point
                    self.start_point += delta
                    self.end_point += delta
                    self.end_relative = self.end_point - self.start_point
                    self.line_item.prepareGeometryChange()
                    if self.scene() is not None:
                        self.scene().invalidate(self.line_item.mapRectToScene(self.line_item.boundingRect()))
                    self.line_item.setLine(QLineF(QPointF(0, 0), self.end_relative))
                    if self.scene() is not None:
                        self.scene().invalidate(self.line_item.mapRectToScene(self.line_item.boundingRect()))
                        self.scene().invalidate(self.mapRectToScene(self.boundingRect()))
                    self.line_item.update()
                    self.update()
                    mid_point_scene = QPointF(
                        (self.start_point.x() + self.end_point.x()) / 2.0,
                        (self.start_point.y() + self.end_point.y()) / 2.0
                    )
                    view = self.scene().views()[0] if self.scene() and self.scene().views() else None
                    viewport_to_scene_scale = (1.0 / view.transform().m11()) if view and view.transform().m11() > 0 else 1.0
                    self.text_offset = QPointF(
                        self.text_offset_viewport.x() * viewport_to_scene_scale,
                        self.text_offset_viewport.y() * viewport_to_scene_scale
                    )
                    text_pos_scene = mid_point_scene + self.text_offset
                    if isinstance(self.text_item, DraggableMeasurementText):
                        self.text_item._updating_position = True
                    self.text_item.setPos(text_pos_scene)
                    if isinstance(self.text_item, DraggableMeasurementText):
                        self.text_item._updating_position = False
                    self.update_handle_positions(force=True)

        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            if hasattr(self, '_handle_drag_in_progress') and self._handle_drag_in_progress:
                return value
            if value:
                self.show_handles()
            else:
                self.hide_handles()
            self.update()

        elif change == QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged:
            if value is not None:
                self.update_text_offset_for_zoom()
            return value

        return super().itemChange(change, value)
