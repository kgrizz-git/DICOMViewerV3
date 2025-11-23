"""
Measurement Tool

This module provides distance measurement functionality with automatic
conversion from pixels to mm/cm based on DICOM metadata.

Inputs:
    - User mouse clicks for measurement points
    - DICOM pixel spacing information
    
Outputs:
    - Distance measurements with units
    - Measurement graphics items
    
Requirements:
    - PySide6 for graphics
    - dicom_utils for distance conversion
"""

from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsTextItem, QGraphicsItemGroup, QGraphicsItem, QGraphicsEllipseItem, QGraphicsSceneMouseEvent
from PySide6.QtCore import Qt, QPointF, QLineF, QRectF
from PySide6.QtGui import QPen, QColor, QFont, QBrush, QPainter, QPainterPath, QPainterPathStroker
from typing import List, Optional, Tuple, Dict, Callable
import numpy as np
import math

from utils.dicom_utils import format_distance, get_pixel_spacing


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
                
                # print(f"[OFFSET] itemChange - offset_scene: {offset_scene}, view_scale: {view_scale if view is not None else 'None'}")
                
                # Convert to viewport pixels
                offset_viewport = QPointF(
                    offset_scene.x() * scene_to_viewport_scale,
                    offset_scene.y() * scene_to_viewport_scale
                )
                
                # print(f"[OFFSET] itemChange - offset_viewport: {offset_viewport}")
                
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
        print(f"[TEXT-SELECT] DraggableMeasurementText.mousePressEvent called")
        print(f"[TEXT-SELECT] Event pos: {event.pos()}, scenePos: {event.scenePos()}")
        print(f"[TEXT-SELECT] Event accepted before: {event.isAccepted()}")
        
        event.accept()  # Accept to prevent parent group from handling it
        print(f"[TEXT-SELECT] Event accepted after: {event.isAccepted()}")
        
        # Deselect parent measurement group if it's selected
        parent = self.parentItem()
        print(f"[TEXT-SELECT] Parent item: {parent}, is selected: {parent.isSelected() if parent else None}")
        if parent is not None and parent.isSelected():
            parent.setSelected(False)
            print(f"[TEXT-SELECT] Parent deselected: True")
        else:
            print(f"[TEXT-SELECT] Parent deselected: False")
        
        # Select this text item
        self.setSelected(True)
        print(f"[TEXT-SELECT] Text item selected: {self.isSelected()}")
        print(f"[TEXT-SELECT] Text item flags: ItemIsSelectable={self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable}, ItemIsMovable={self.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable}")
        
        super().mousePressEvent(event)
        print(f"[TEXT-SELECT] After super().mousePressEvent(), text selected: {self.isSelected()}")


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
        # print(f"[Handle {self.is_start}] mousePressEvent - pos: {event.pos()}, scenePos: {event.scenePos()}")
        
        # Accept the event early to prevent it from propagating to scene selection mechanism
        # This prevents Qt's default selection behavior from deselecting the measurement
        event.accept()
        
        # Set flag on parent to indicate handle drag is in progress
        # This allows parent to ignore move/release events during handle drag
        if self.parent_measurement is not None:
            # Explicitly keep parent measurement selected when clicking handle
            # Do this BEFORE setting flags to ensure selection state is maintained
            if not self.parent_measurement.isSelected():
                # print(f"[Handle {self.is_start}] Keeping parent measurement selected")
                self.parent_measurement.setSelected(True)
            
            # Set flag to indicate handle drag is in progress
            self.parent_measurement._handle_drag_in_progress = True
            # Store reference to this handle
            self.parent_measurement._dragging_handle = self
        
        # Call parent to handle the drag
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """
        Handle mouse move during drag.
        
        Args:
            event: Mouse move event
        """
        # print(f"[Handle {self.is_start}] mouseMoveEvent - pos: {event.pos()}, scenePos: {event.scenePos()}")
        # Accept the event to prevent parent from handling it
        event.accept()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """
        Handle mouse release after drag.
        
        Args:
            event: Mouse release event
        """
        # print(f"[Handle {self.is_start}] mouseReleaseEvent")
        # Accept the event to prevent parent from handling it
        event.accept()
        
        # Clear handle drag flag and reference after handle drag is complete
        if self.parent_measurement is not None:
            # Clear handle drag flag and reference
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
            # print(f"[Handle {self.is_start}] ItemPositionChange - value: {value}, current pos: {self.pos()}")
            # Allow position change to proceed during drag
            return value
        
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # print(f"[Handle {self.is_start}] ItemPositionHasChanged - pos: {self.pos()}, parent valid: {self.parent_measurement is not None}")
            # Use ItemPositionHasChanged - called AFTER position change is complete
            # This allows the handle to be dragged freely, then we update the measurement
            if self.parent_measurement is not None:
                # Check if measurement is still valid (hasn't been deleted)
                if self.parent_measurement.scene() is None:
                    return value  # Measurement deleted, don't update
                
                # Prevent recursive updates
                if hasattr(self.parent_measurement, '_updating_handles'):
                    if self.parent_measurement._updating_handles:
                        return value
                
                # Get current position in scene coordinates (handles are separate items)
                scene_pos = self.pos()
                
                self.parent_measurement._updating_handles = True
                
                try:
                    if self.is_start:
                        # Store end_point BEFORE moving group (to keep it fixed)
                        original_end_point = self.parent_measurement.end_point
                        original_start_point = self.parent_measurement.start_point
                        
                        # print(f"[Handle {self.is_start}] Before update - start: {original_start_point}, end: {original_end_point}, handle pos: {scene_pos}")
                        
                        # Update start point in scene coordinates
                        self.parent_measurement.start_point = scene_pos
                        
                        # Move group to new start point
                        self.parent_measurement.setPos(self.parent_measurement.start_point)
                        
                        # Restore end_point to keep it fixed in scene coordinates
                        self.parent_measurement.end_point = original_end_point
                        
                        # Recalculate end_relative based on new positions
                        self.parent_measurement.end_relative = (
                            self.parent_measurement.end_point - 
                            self.parent_measurement.start_point
                        )
                        
                        # print(f"[Handle {self.is_start}] After point update - start: {self.parent_measurement.start_point}, end: {self.parent_measurement.end_point}, end_relative: {self.parent_measurement.end_relative}")
                        
                        # Recalculate distance (this will update line, text, and handle positions)
                        # print(f"[Handle {self.is_start}] Calling update_distance()...")
                        self.parent_measurement.update_distance()
                        # print(f"[Handle {self.is_start}] update_distance() completed")
                        
                        # Verify stored points are still correct after update_distance()
                        # print(f"[Handle {self.is_start}] After update_distance() - start: {self.parent_measurement.start_point}, end: {self.parent_measurement.end_point}")
                        
                        # Force visual update to ensure line is redrawn
                        self.parent_measurement.line_item.update()
                        self.parent_measurement.update()
                        
                        # Force scene update to ensure visual refresh
                        if self.parent_measurement.scene() is not None:
                            # Update the bounding rect area of the line
                            line_rect = self.parent_measurement.line_item.boundingRect()
                            line_scene_rect = self.parent_measurement.line_item.mapRectToScene(line_rect)
                            self.parent_measurement.scene().update(line_scene_rect)
                        
                        # print(f"[Handle {self.is_start}] Updated start point to {scene_pos}, end point: {self.parent_measurement.end_point}")
                    else:
                        # Store original values for debugging
                        original_end_point = self.parent_measurement.end_point
                        original_start_point = self.parent_measurement.start_point
                        
                        # print(f"[Handle {self.is_start}] Before update - start: {original_start_point}, end: {original_end_point}, handle pos: {scene_pos}")
                        
                        # Update end point in scene coordinates
                        self.parent_measurement.end_point = scene_pos
                        
                        # Recalculate end_relative (group position stays the same)
                        self.parent_measurement.end_relative = (
                            self.parent_measurement.end_point - 
                            self.parent_measurement.start_point
                        )
                        
                        # print(f"[Handle {self.is_start}] After point update - start: {self.parent_measurement.start_point}, end: {self.parent_measurement.end_point}, end_relative: {self.parent_measurement.end_relative}")
                        
                        # Recalculate distance (this will update line, text, and handle positions)
                        # print(f"[Handle {self.is_start}] Calling update_distance()...")
                        self.parent_measurement.update_distance()
                        # print(f"[Handle {self.is_start}] update_distance() completed")
                        
                        # Verify stored points are still correct after update_distance()
                        # print(f"[Handle {self.is_start}] After update_distance() - start: {self.parent_measurement.start_point}, end: {self.parent_measurement.end_point}")
                        
                        # Force visual update to ensure line is redrawn
                        self.parent_measurement.line_item.update()
                        self.parent_measurement.update()
                        
                        # Force scene update to ensure visual refresh
                        if self.parent_measurement.scene() is not None:
                            # Update the bounding rect area of the line
                            line_rect = self.parent_measurement.line_item.boundingRect()
                            line_scene_rect = self.parent_measurement.line_item.mapRectToScene(line_rect)
                            self.parent_measurement.scene().update(line_scene_rect)
                        
                        # print(f"[Handle {self.is_start}] Updated end point to {scene_pos}, start point: {self.parent_measurement.start_point}")
                finally:
                    self.parent_measurement._updating_handles = False
        
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
        # Store offset in viewport pixels (since text has ItemIgnoresTransformations)
        # This will be converted to scene coordinates when positioning
        self.text_offset_viewport = QPointF(0, -30)  # Initial offset in viewport pixels (increased from -20)
        self.text_offset = QPointF(0, 0)  # Will be calculated from viewport offset
        
        # Calculate end_relative BEFORE positioning the group
        # This is the offset from start_point to end_point in scene coordinates
        # After the group is positioned at start_point, this becomes the group-relative position
        self.end_relative = end_point - start_point
        
        # Store original scene positions before adding to group
        # (items will be positioned relative to group after adding)
        line_scene_pos = line_item.pos()
        text_scene_pos = text_item.pos()
        
        # Add line item to the group (text item will be managed separately, not as a child)
        self.addToGroup(line_item)
        # Don't add text_item to group - it will be added directly to scene for independent selection
        
        # Set z-values: text should be above line for easier selection
        line_item.setZValue(150)
        text_item.setZValue(151)  # Higher z-value than line for priority selection
        
        # Get line color from pen for handles
        line_pen = line_item.pen()
        line_color = line_pen.color() if line_pen.color().isValid() else QColor(0, 255, 0)
        
        # Adjust positions to be relative to group
        # Set group position to start_point so line starts at (0,0) relative to group
        self.setPos(start_point)
        line_item.setPos(QPointF(0, 0))  # Line starts at group origin
        # Text item is not a child of group, so we'll position it in scene coordinates later
        # Store initial text position for reference (will be recalculated in update_distance)
        
        # Create handles as separate scene items (not children) with matching line color
        # They will be positioned in scene coordinates
        self.start_handle = MeasurementHandle(self, is_start=True, color=line_color)
        self.end_handle = MeasurementHandle(self, is_start=False, color=line_color)
        
        # Handles are not yet in scene - they'll be added when measurement is selected
        # Set z-value to ensure handles appear above measurement when added
        self.start_handle.setZValue(200)
        self.end_handle.setZValue(200)
        
        # Make the group selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        # Disable Qt's default selection rectangle - we'll draw our own
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        
        # Initialize flag to prevent recursive handle updates
        self._updating_handles = False
        # Initialize flag to track handle drag state
        self._handle_drag_in_progress = False
        # Track which handle is currently being dragged
        self._dragging_handle: Optional[MeasurementHandle] = None
        # Track position during drag to update handles when line is moved
        self._last_drag_pos: Optional[QPointF] = None
        
        # Calculate initial distance
        self.update_distance()
    
    def boundingRect(self) -> QRectF:
        """
        Return bounding rectangle for the measurement.
        
        Handles are separate items, so they're not included in this bounding rect.
        
        Returns:
            Bounding rectangle that includes line and text only
        """
        # Get line bounding rect (relative to group)
        line_rect = self.line_item.boundingRect()
        
        # Get text bounding rect (relative to group)
        text_rect = self.text_item.boundingRect()
        text_pos = self.text_item.pos()
        text_rect.translate(text_pos)
        
        # Combine line and text rects
        combined_rect = line_rect
        combined_rect = combined_rect.united(text_rect)
        
        # Minimal padding for selection outline (reduced from 5.0 to 2.0)
        padding = 2.0
        combined_rect.adjust(-padding, -padding, padding, padding)
        
        return combined_rect
    
    def shape(self) -> QPainterPath:
        """
        Return shape for hit testing - only line stroke, no handles.
        
        Handles are separate items with their own shape() for hit testing.
        
        Returns:
            QPainterPath with stroked line for accurate clicking
        """
        # Create line path
        line = self.line_item.line()
        line_path = QPainterPath()
        line_path.moveTo(line.p1())
        line_path.lineTo(line.p2())
        
        # Create stroked path with 4px width for hit testing (reduced from 8px)
        pen = QPen(QColor(0, 255, 0), 4)
        stroker = QPainterPathStroker(pen)
        stroked_path = stroker.createStroke(line_path)
        
        return stroked_path
    
    def paint(self, painter: QPainter, option, widget=None) -> None:
        """
        Paint selection indicator when item is selected.
        
        Handles are separate items, so they handle their own selection indicators.
        
        Args:
            painter: QPainter to draw with
            option: Style option
            widget: Optional widget
        """
        # Check selection state FIRST before modifying option
        is_selected = self.isSelected()
        
        # Suppress Qt's default selection rectangle by clearing the selected state
        # before calling parent paint
        from PySide6.QtWidgets import QStyle
        original_state = option.state
        option.state = option.state & ~QStyle.StateFlag.State_Selected
        
        # Call parent paint first to draw children (line and text)
        super().paint(painter, option, widget)
        
        # Restore original state
        option.state = original_state
        
        # Draw our custom selection indicator (yellow dashed line)
        if is_selected:
            painter.save()
            
            # Set pen for selection indicator
            selection_pen = QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine)  # Yellow dashed
            painter.setPen(selection_pen)
            
            # Draw dashed line along the measurement line
            line = self.line_item.line()
            painter.drawLine(line)
            
            # Note: Handles are separate items and will show their own selection indicators
            
            painter.restore()
    
    def show_handles(self) -> None:
        """
        Show handles when measurement is selected.
        
        Handles are separate scene items, so we need to add them to the scene.
        """
        if self.scene() is None:
            return
        
        if self.start_handle is None or self.end_handle is None:
            return
        
        # Add handles to scene if not already present
        # Safety check: ensure handles are always in scene when measurement is selected
        if self.start_handle.scene() != self.scene():
            # print(f"[MeasurementItem] show_handles - adding start_handle to scene")
            self.scene().addItem(self.start_handle)
        if self.end_handle.scene() != self.scene():
            # print(f"[MeasurementItem] show_handles - adding end_handle to scene")
            self.scene().addItem(self.end_handle)
        
        # Update handle positions in scene coordinates
        # This ensures handles are positioned correctly even if they were just added
        self.update_handle_positions()
        
        # Show handles (make them visible)
        self.start_handle.show()
        self.end_handle.show()
        
        # print(f"[MeasurementItem] show_handles - handles shown, start in scene: {self.start_handle.scene() is not None}, end in scene: {self.end_handle.scene() is not None}")
    
    def hide_handles(self) -> None:
        """
        Hide handles when measurement is deselected.
        
        Handles are separate scene items, so we remove them from the scene.
        """
        if self.start_handle is not None:
            if self.start_handle.scene() is not None:
                self.start_handle.scene().removeItem(self.start_handle)
        if self.end_handle is not None:
            if self.end_handle.scene() is not None:
                self.end_handle.scene().removeItem(self.end_handle)
    
    def update_handle_positions(self, force: bool = False) -> None:
        """
        Update handle positions in scene coordinates.
        
        Called when measurement endpoints change or measurement is moved.
        Since handles are separate scene items, they use scene coordinates directly.
        
        Args:
            force: If True, bypasses recursion check (used when called from update_distance())
        """
        if self.scene() is None:
            return
        
        if self.start_handle is None or self.end_handle is None:
            return
        
        # Allow updates if forced (called from update_distance) or not currently updating
        if not force and hasattr(self, '_updating_handles') and self._updating_handles:
            return
        
        # If measurement is selected, ensure handles are in the scene
        # This ensures handles are visible and can be positioned correctly
        if self.isSelected():
            # Ensure handles are in scene (they should be, but check to be safe)
            if self.start_handle.scene() != self.scene():
                self.scene().addItem(self.start_handle)
            if self.end_handle.scene() != self.scene():
                self.scene().addItem(self.end_handle)
        
        # Only update positions if handles are actually in the scene
        if self.start_handle.scene() is None or self.end_handle.scene() is None:
            # print(f"[MeasurementItem] update_handle_positions - handles not in scene, skipping update")
            return
        
        # Set flag to indicate we're programmatically updating handles
        # This prevents handle's itemChange from triggering updates
        was_updating = getattr(self, '_updating_handles', False)
        self._updating_handles = True
        
        try:
            # print(f"[MeasurementItem] update_handle_positions - updating handles to start: {self.start_point}, end: {self.end_point}")
            # Start handle at start_point in scene coordinates
            self.start_handle.setPos(self.start_point)
            
            # End handle at end_point in scene coordinates
            self.end_handle.setPos(self.end_point)
        finally:
            # Restore original flag state
            self._updating_handles = was_updating
    
    def update_distance(self, pixel_spacing: Optional[Tuple[float, float]] = None) -> None:
        """
        Update distance calculation and label.
        
        Args:
            pixel_spacing: Optional pixel spacing tuple (if None, uses stored pixel_spacing)
        """
        # print(f"[MeasurementItem] update_distance() called - start: {self.start_point}, end: {self.end_point}, _updating_handles: {getattr(self, '_updating_handles', False)}")
        
        # Use provided pixel_spacing or stored one
        spacing = pixel_spacing if pixel_spacing is not None else self.pixel_spacing
        if spacing is not None:
            self.pixel_spacing = spacing
        
        # Calculate pixel differences
        dx = self.end_point.x() - self.start_point.x()  # X direction (columns)
        dy = self.end_point.y() - self.start_point.y()  # Y direction (rows)
        
        # Calculate distance using correct formula:
        # distance = sqrt( (dx * pixel_spacing_x)^2 + (dy * pixel_spacing_y)^2 )
        if spacing:
            # pixel_spacing[1] = column spacing (X direction)
            # pixel_spacing[0] = row spacing (Y direction)
            dx_scaled = dx * spacing[1]  # X component in mm
            dy_scaled = dy * spacing[0]  # Y component in mm
            distance_mm = math.sqrt(dx_scaled * dx_scaled + dy_scaled * dy_scaled)
            
            # Store pixel distance for reference
            self.distance_pixels = math.sqrt(dx * dx + dy * dy)
            
            # Format distance in mm
            if distance_mm >= 10:
                self.distance_formatted = f"{distance_mm:.1f} mm"
            else:
                self.distance_formatted = f"{distance_mm:.2f} mm"
        else:
            # No pixel spacing - just use pixel distance
            self.distance_pixels = math.sqrt(dx * dx + dy * dy)
            self.distance_formatted = f"{self.distance_pixels:.1f} pixels"
        
        # Update end_relative from stored start_point and end_point (scene coordinates)
        # This ensures consistency when distance is recalculated
        self.end_relative = self.end_point - self.start_point
        
        # print(f"[MeasurementItem] update_distance() - calculated end_relative: {self.end_relative}, distance: {self.distance_formatted}")
        
        # Update line item (relative to group position)
        # Group position is at start_point, so line goes from (0,0) to end_relative
        line = QLineF(QPointF(0, 0), self.end_relative)
        
        # print(f"[MeasurementItem] update_distance() - About to update line from (0,0) to {self.end_relative}")
        # print(f"[MeasurementItem] update_distance() - Current line: {self.line_item.line()}")
        # print(f"[MeasurementItem] update_distance() - Line item scene: {self.line_item.scene() is not None}, Group scene: {self.scene() is not None}")
        
        # CRITICAL: Call prepareGeometryChange() before changing line geometry
        # This notifies Qt that the bounding rect is about to change
        # print(f"[MeasurementItem] update_distance() - Calling prepareGeometryChange() on line_item")
        self.line_item.prepareGeometryChange()
        
        # Invalidate old bounding rect area before changing
        if self.scene() is not None:
            old_line_rect = self.line_item.boundingRect()
            old_line_scene_rect = self.line_item.mapRectToScene(old_line_rect)
            # print(f"[MeasurementItem] update_distance() - Invalidating old line rect: {old_line_scene_rect}")
            self.scene().invalidate(old_line_scene_rect)
        
        # Now update the line
        # print(f"[MeasurementItem] update_distance() - Calling setLine() with {line}")
        self.line_item.setLine(line)
        # print(f"[MeasurementItem] update_distance() - setLine() completed, new line: {self.line_item.line()}")
        
        # Invalidate new bounding rect area after changing
        if self.scene() is not None:
            new_line_rect = self.line_item.boundingRect()
            new_line_scene_rect = self.line_item.mapRectToScene(new_line_rect)
            # print(f"[MeasurementItem] update_distance() - Invalidating new line rect: {new_line_scene_rect}")
            self.scene().invalidate(new_line_scene_rect)
            # Also invalidate group's bounding rect since it contains the line
            group_rect = self.boundingRect()
            group_scene_rect = self.mapRectToScene(group_rect)
            # print(f"[MeasurementItem] update_distance() - Invalidating group rect: {group_scene_rect}")
            self.scene().invalidate(group_scene_rect)
        
        # Force update on line item and group
        # print(f"[MeasurementItem] update_distance() - Calling update() on line_item and group")
        self.line_item.update()
        self.update()
        # print(f"[MeasurementItem] update_distance() - All updates completed")
        
        # Update text item position in scene coordinates (text is not a child of group)
        # Calculate midpoint of line in scene coordinates
        mid_point_scene = QPointF(
            (self.start_point.x() + self.end_point.x()) / 2.0,
            (self.start_point.y() + self.end_point.y()) / 2.0
        )
        
        # Convert viewport pixel offset to scene coordinates
        # Get view for coordinate conversion (needed for ItemIgnoresTransformations)
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view is not None:
            # Get the scale factor from the view's transform
            view_scale = view.transform().m11()
            if view_scale > 0:
                # Convert viewport pixels to scene coordinates
                # If view is zoomed 2x, 1 viewport pixel = 0.5 scene units
                viewport_to_scene_scale = 1.0 / view_scale
            else:
                viewport_to_scene_scale = 1.0
        else:
            viewport_to_scene_scale = 1.0
        
        # print(f"[OFFSET] update_distance() - view_scale: {view_scale if view is not None else 'None'}, viewport_to_scene_scale: {viewport_to_scene_scale}")
        # print(f"[OFFSET] text_offset_viewport: {self.text_offset_viewport}, text_offset (before): {self.text_offset}")
        
        # Convert viewport offset to scene coordinates
        self.text_offset = QPointF(
            self.text_offset_viewport.x() * viewport_to_scene_scale,
            self.text_offset_viewport.y() * viewport_to_scene_scale
        )
        
        # print(f"[OFFSET] text_offset (after): {self.text_offset}")
        # print(f"[OFFSET] mid_point_scene: {mid_point_scene}, text_pos_scene: {mid_point_scene + self.text_offset}")
        
        # Calculate text position in scene coordinates
        text_pos_scene = mid_point_scene + self.text_offset
        
        # Set updating flag if it's a draggable text item
        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = True
        
        # Position text in scene coordinates (not relative to group)
        self.text_item.setPos(text_pos_scene)
        self.text_item.setPlainText(self.distance_formatted)
        
        # Clear updating flag
        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = False
        
        # Update group position to start_point
        # Only set position if it's different to avoid triggering unnecessary position change events
        current_group_pos = self.pos()
        if current_group_pos != self.start_point:
            # print(f"[MeasurementItem] update_distance() - moving group from {current_group_pos} to {self.start_point}")
            self.setPos(self.start_point)
        else:
            # print(f"[MeasurementItem] update_distance() - group already at start_point, not moving")
            pass
        
        # Update handle positions in scene coordinates (handles are separate items)
        # Force update to bypass recursion check since we're updating from distance calculation
        # This will sync handles to the stored start_point and end_point
        # print(f"[MeasurementItem] update_distance() - calling update_handle_positions(force=True)")
        self.update_handle_positions(force=True)
        
        # Verify stored points are still correct after all updates
        # print(f"[MeasurementItem] update_distance() - final start: {self.start_point}, end: {self.end_point}")
    
    def update_text_offset_for_zoom(self) -> None:
        """
        Recalculate text offset when zoom changes.
        
        Converts viewport pixel offset to scene coordinates based on current view scale.
        """
        if self.text_item is None:
            return
        
        # Get current view and scale
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if view is not None:
            view_scale = view.transform().m11()
            if view_scale > 0:
                viewport_to_scene_scale = 1.0 / view_scale
            else:
                viewport_to_scene_scale = 1.0
        else:
            viewport_to_scene_scale = 1.0
        
        # print(f"[OFFSET] update_text_offset_for_zoom() - view_scale: {view_scale if view is not None else 'None'}, viewport_to_scene_scale: {viewport_to_scene_scale}")
        
        # Recalculate text_offset from text_offset_viewport
        self.text_offset = QPointF(
            self.text_offset_viewport.x() * viewport_to_scene_scale,
            self.text_offset_viewport.y() * viewport_to_scene_scale
        )
        
        # print(f"[OFFSET] update_text_offset_for_zoom() - text_offset_viewport: {self.text_offset_viewport}, text_offset: {self.text_offset}")
        
        # Calculate midpoint of line in scene coordinates
        mid_point_scene = QPointF(
            (self.start_point.x() + self.end_point.x()) / 2.0,
            (self.start_point.y() + self.end_point.y()) / 2.0
        )
        text_pos_scene = mid_point_scene + self.text_offset
        
        # print(f"[OFFSET] update_text_offset_for_zoom() - mid_point_scene: {mid_point_scene}, text_pos_scene: {text_pos_scene}")
        
        # Set updating flag if it's a draggable text item
        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = True
        
        # Position text in scene coordinates (not relative to group)
        self.text_item.setPos(text_pos_scene)
        
        # Clear updating flag
        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = False
    
    def mousePressEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """
        Handle mouse press - text item is now separate, so it will receive events directly.
        
        The handle will receive the event first (as a child with higher z-value)
        and set _dragging_handle on this parent if needed.
        
        Args:
            event: Mouse press event
        """
        # Text item is no longer a child of the group, so it will receive events directly
        # No need to check for text item clicks here - it handles its own events
        
        # Store current position to track drag start
        # This allows us to update handles when the line is dragged
        self._last_drag_pos = self.pos()
        
        # Always call super() to allow normal event propagation
        # If a handle is clicked, it will receive the event first and set _dragging_handle
        # If the line is clicked, we process it normally
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """
        Handle mouse move during drag - ignore if handle drag is in progress.
        
        Args:
            event: Mouse move event
        """
        # If a handle is being dragged, ignore this event
        # Let Qt deliver the event directly to the handle through normal propagation
        if hasattr(self, '_dragging_handle') and self._dragging_handle is not None:
            # print(f"[MeasurementItem] Ignoring mouseMoveEvent - handle {self._dragging_handle.is_start} is being dragged")
            return
        
        # Normal drag of the measurement line itself
        # Track position changes to update handles
        current_pos = self.pos()
        if self._last_drag_pos is not None:
            # Calculate delta from last position
            delta = current_pos - self._last_drag_pos
            if delta.x() != 0 or delta.y() != 0:
                # print(f"[MeasurementItem] mouseMoveEvent - delta: {delta}, updating handles")
                
                # Update start and end points
                self.start_point += delta
                self.end_point += delta
                
                # Update end_relative (group-relative coordinates remain the same when group moves)
                # end_relative doesn't change because both start_point and end_point move by the same delta
                # But we recalculate to ensure consistency
                self.end_relative = self.end_point - self.start_point
                
                # CRITICAL: Call prepareGeometryChange() before changing line geometry
                self.line_item.prepareGeometryChange()
                
                # Invalidate old bounding rect area
                if self.scene() is not None:
                    old_line_rect = self.line_item.boundingRect()
                    old_line_scene_rect = self.line_item.mapRectToScene(old_line_rect)
                    self.scene().invalidate(old_line_scene_rect)
                
                # Update line item to reflect new end point (relative to group)
                self.line_item.setLine(QLineF(QPointF(0, 0), self.end_relative))
                
                # Invalidate new bounding rect area and update
                if self.scene() is not None:
                    new_line_rect = self.line_item.boundingRect()
                    new_line_scene_rect = self.line_item.mapRectToScene(new_line_rect)
                    self.scene().invalidate(new_line_scene_rect)
                    group_rect = self.boundingRect()
                    group_scene_rect = self.mapRectToScene(group_rect)
                    self.scene().invalidate(group_scene_rect)
                
                self.line_item.update()
                self.update()
                
                # Update text position (relative to group)
                mid_point_relative = QPointF(
                    self.end_relative.x() / 2.0,
                    self.end_relative.y() / 2.0
                )
                
                # Convert viewport pixel offset to scene coordinates
                view = self.scene().views()[0] if self.scene() and self.scene().views() else None
                if view is not None:
                    view_scale = view.transform().m11()
                    if view_scale > 0:
                        viewport_to_scene_scale = 1.0 / view_scale
                    else:
                        viewport_to_scene_scale = 1.0
                else:
                    viewport_to_scene_scale = 1.0
                
                # Convert viewport offset to scene coordinates
                self.text_offset = QPointF(
                    self.text_offset_viewport.x() * viewport_to_scene_scale,
                    self.text_offset_viewport.y() * viewport_to_scene_scale
                )
                
                # Use converted offset
                text_pos = mid_point_relative + self.text_offset
                
                # Set updating flag if it's a draggable text item
                if isinstance(self.text_item, DraggableMeasurementText):
                    self.text_item._updating_position = True
                
                self.text_item.setPos(text_pos)
                
                # Clear updating flag
                if isinstance(self.text_item, DraggableMeasurementText):
                    self.text_item._updating_position = False
                
                # Update handle positions in scene coordinates (handles are separate items)
                # Use force=True to ensure handles are updated
                self.update_handle_positions(force=True)
                
                # Update tracking position for next move event
                self._last_drag_pos = current_pos
        
        # print(f"[MeasurementItem] mouseMoveEvent - scenePos: {event.scenePos()}")
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """
        Handle mouse release after drag - ignore if handle drag is in progress.
        
        Args:
            event: Mouse release event
        """
        # If a handle is being dragged, clear the reference and ignore this event
        # Let Qt deliver the event directly to the handle through normal propagation
        # The handle will clear _dragging_handle in its own mouseReleaseEvent
        if hasattr(self, '_dragging_handle') and self._dragging_handle is not None:
            # print(f"[MeasurementItem] Ignoring mouseReleaseEvent - handle {self._dragging_handle.is_start} is being dragged")
            # Note: Don't clear _dragging_handle here - let the handle do it in its mouseReleaseEvent
            return
        
        # Clear drag tracking when drag ends
        self._last_drag_pos = None
        # print("[MeasurementItem] mouseReleaseEvent - cleared drag tracking")
        
        # Normal release after dragging the measurement line itself
        super().mouseReleaseEvent(event)
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """
        Handle item changes (e.g., position changes when moved, selection changes).
        
        Args:
            change: Type of change
            value: New value
            
        Returns:
            Modified value
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # print(f"[MeasurementItem] ItemPositionChange - value: {value}, _updating_handles: {getattr(self, '_updating_handles', False)}")
            
            # Skip automatic updates if a handle is being dragged
            # Let handle drag logic handle the update instead
            if hasattr(self, '_updating_handles') and self._updating_handles:
                # print("[MeasurementItem] Skipping update - handle is being dragged")
                return value  # Let handle drag logic handle the update
            
            # When the group is moved, update start and end points
            new_pos = value
            old_pos = self.pos()
            delta = new_pos - old_pos
            
            # Update start and end points
            self.start_point += delta
            self.end_point += delta
            
            # Update end_relative (group-relative coordinates remain the same when group moves)
            # end_relative doesn't change because both start_point and end_point move by the same delta
            # But we recalculate to ensure consistency
            self.end_relative = self.end_point - self.start_point
            
            # CRITICAL: Call prepareGeometryChange() before changing line geometry
            self.line_item.prepareGeometryChange()
            
            # Invalidate old bounding rect area
            if self.scene() is not None:
                old_line_rect = self.line_item.boundingRect()
                old_line_scene_rect = self.line_item.mapRectToScene(old_line_rect)
                self.scene().invalidate(old_line_scene_rect)
            
            # Update line item to reflect new end point (relative to group)
            self.line_item.setLine(QLineF(QPointF(0, 0), self.end_relative))
            
            # Invalidate new bounding rect area and update
            if self.scene() is not None:
                new_line_rect = self.line_item.boundingRect()
                new_line_scene_rect = self.line_item.mapRectToScene(new_line_rect)
                self.scene().invalidate(new_line_scene_rect)
                group_rect = self.boundingRect()
                group_scene_rect = self.mapRectToScene(group_rect)
                self.scene().invalidate(group_scene_rect)
            
            self.line_item.update()
            self.update()
            
            # Update text position (relative to group)
            mid_point_relative = QPointF(
                self.end_relative.x() / 2.0,
                self.end_relative.y() / 2.0
            )
            
            # Convert viewport pixel offset to scene coordinates
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view is not None:
                view_scale = view.transform().m11()
                if view_scale > 0:
                    viewport_to_scene_scale = 1.0 / view_scale
                else:
                    viewport_to_scene_scale = 1.0
            else:
                viewport_to_scene_scale = 1.0
            
            # Convert viewport offset to scene coordinates
            self.text_offset = QPointF(
                self.text_offset_viewport.x() * viewport_to_scene_scale,
                self.text_offset_viewport.y() * viewport_to_scene_scale
            )
            
            # Use converted offset
            text_pos = mid_point_relative + self.text_offset
            
            # Set updating flag if it's a draggable text item
            if isinstance(self.text_item, DraggableMeasurementText):
                self.text_item._updating_position = True
            
            self.text_item.setPos(text_pos)
            
            # Clear updating flag
            if isinstance(self.text_item, DraggableMeasurementText):
                self.text_item._updating_position = False
            
            # Update text position in scene coordinates (text is not a child of group)
            mid_point_scene = QPointF(
                (self.start_point.x() + self.end_point.x()) / 2.0,
                (self.start_point.y() + self.end_point.y()) / 2.0
            )
            
            # Convert viewport pixel offset to scene coordinates
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view is not None:
                view_scale = view.transform().m11()
                if view_scale > 0:
                    viewport_to_scene_scale = 1.0 / view_scale
                else:
                    viewport_to_scene_scale = 1.0
            else:
                viewport_to_scene_scale = 1.0
            
            # Convert viewport offset to scene coordinates
            self.text_offset = QPointF(
                self.text_offset_viewport.x() * viewport_to_scene_scale,
                self.text_offset_viewport.y() * viewport_to_scene_scale
            )
            
            # Calculate text position in scene coordinates
            text_pos_scene = mid_point_scene + self.text_offset
            
            # Set updating flag if it's a draggable text item
            if isinstance(self.text_item, DraggableMeasurementText):
                self.text_item._updating_position = True
            
            # Position text in scene coordinates (not relative to group)
            self.text_item.setPos(text_pos_scene)
            
            # Clear updating flag
            if isinstance(self.text_item, DraggableMeasurementText):
                self.text_item._updating_position = False
            
            # Update handle positions in scene coordinates (handles are separate items)
            # Use force=True to ensure handles are updated even if _updating_handles flag is set
            # (though it shouldn't be when moving the measurement line itself)
            self.update_handle_positions(force=True)
            
            # Update group position to new start point
            return self.start_point
        
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Backup handler for position changes (in case ItemPositionChange isn't triggered)
            # Only process if we're not currently tracking via mouseMoveEvent
            if self._last_drag_pos is None:
                # print(f"[MeasurementItem] ItemPositionHasChanged - pos: {self.pos()}, _updating_handles: {getattr(self, '_updating_handles', False)}")
                
                # Skip automatic updates if a handle is being dragged
                if hasattr(self, '_updating_handles') and self._updating_handles:
                    print("[MeasurementItem] ItemPositionHasChanged - skipping update - handle is being dragged")
                    return value
                
                # Get current and previous positions
                current_pos = self.pos()
                # Try to get previous position from stored start_point
                # If group position changed, update start and end points
                if current_pos != self.start_point:
                    delta = current_pos - self.start_point
                    
                    # Update start and end points
                    self.start_point += delta
                    self.end_point += delta
                    
                    # Update end_relative
                    self.end_relative = self.end_point - self.start_point
                    
                    # CRITICAL: Call prepareGeometryChange() before changing line geometry
                    self.line_item.prepareGeometryChange()
                    
                    # Invalidate old bounding rect area
                    if self.scene() is not None:
                        old_line_rect = self.line_item.boundingRect()
                        old_line_scene_rect = self.line_item.mapRectToScene(old_line_rect)
                        self.scene().invalidate(old_line_scene_rect)
                    
                    # Update line item
                    self.line_item.setLine(QLineF(QPointF(0, 0), self.end_relative))
                    
                    # Invalidate new bounding rect area and update
                    if self.scene() is not None:
                        new_line_rect = self.line_item.boundingRect()
                        new_line_scene_rect = self.line_item.mapRectToScene(new_line_rect)
                        self.scene().invalidate(new_line_scene_rect)
                        group_rect = self.boundingRect()
                        group_scene_rect = self.mapRectToScene(group_rect)
                        self.scene().invalidate(group_scene_rect)
                    
                    self.line_item.update()
                    self.update()
                    
                    # Update text position in scene coordinates (text is not a child of group)
                    mid_point_scene = QPointF(
                        (self.start_point.x() + self.end_point.x()) / 2.0,
                        (self.start_point.y() + self.end_point.y()) / 2.0
                    )
                    
                    # Convert viewport pixel offset to scene coordinates
                    view = self.scene().views()[0] if self.scene() and self.scene().views() else None
                    if view is not None:
                        view_scale = view.transform().m11()
                        if view_scale > 0:
                            viewport_to_scene_scale = 1.0 / view_scale
                        else:
                            viewport_to_scene_scale = 1.0
                    else:
                        viewport_to_scene_scale = 1.0
                    
                    # Convert viewport offset to scene coordinates
                    self.text_offset = QPointF(
                        self.text_offset_viewport.x() * viewport_to_scene_scale,
                        self.text_offset_viewport.y() * viewport_to_scene_scale
                    )
                    
                    # Calculate text position in scene coordinates
                    text_pos_scene = mid_point_scene + self.text_offset
                    
                    if isinstance(self.text_item, DraggableMeasurementText):
                        self.text_item._updating_position = True
                    
                    # Position text in scene coordinates (not relative to group)
                    self.text_item.setPos(text_pos_scene)
                    
                    if isinstance(self.text_item, DraggableMeasurementText):
                        self.text_item._updating_position = False
                    
                    # Update handle positions
                    self.update_handle_positions(force=True)
        
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            # Check if handle drag is in progress before hiding handles
            # This prevents handles from disappearing during drag
            if hasattr(self, '_handle_drag_in_progress') and self._handle_drag_in_progress:
                # print(f"[MeasurementItem] ItemSelectedHasChanged - handle drag in progress, not hiding handles")
                # Don't hide handles if a handle is being dragged
                # The handle will ensure measurement stays selected
                return value
            
            # Show/hide handles based on selection state
            if value:  # Selected
                self.show_handles()
            else:  # Deselected
                self.hide_handles()
            
            # Force update to redraw selection indicator (yellow dashed line)
            self.update()
        
        elif change == QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged:
            # Measurement was added to or removed from a scene
            # If added to a scene, recalculate text offset with correct view scale
            if value is not None:  # Added to scene
                # Recalculate text offset now that we have access to the scene/view
                # This ensures correct viewport-to-scene conversion on initial creation
                self.update_text_offset_for_zoom()
            return value
        
        return super().itemChange(change, value)


class MeasurementTool:
    """
    Manages distance measurements on images.
    
    Features:
    - Draw measurement lines
    - Calculate distances in pixels, mm, or cm
    - Display measurement labels
    """
    
    def __init__(self, config_manager=None):
        """
        Initialize the measurement tool.
        
        Args:
            config_manager: Optional ConfigManager for annotation settings
        """
        # Key format: (StudyInstanceUID, SeriesInstanceUID, instance_identifier)
        # instance_identifier can be InstanceNumber from DICOM or slice_index as fallback
        self.measurements: Dict[Tuple[str, str, int], List[MeasurementItem]] = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_instance_identifier = 0
        self.measuring = False
        self.start_point: Optional[QPointF] = None
        self.current_end_point: Optional[QPointF] = None  # Track last mouse position during measurement
        self.current_line_item: Optional[QGraphicsLineItem] = None
        self.current_text_item: Optional[QGraphicsTextItem] = None
        self.pixel_spacing: Optional[Tuple[float, float]] = None
        self.config_manager = config_manager
    
    def set_current_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> None:
        """
        Set the current slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
        """
        self.current_study_uid = study_uid
        self.current_series_uid = series_uid
        self.current_instance_identifier = instance_identifier
        key = (study_uid, series_uid, instance_identifier)
        if key not in self.measurements:
            self.measurements[key] = []
    
    def set_pixel_spacing(self, pixel_spacing: Optional[Tuple[float, float]]) -> None:
        """
        Set pixel spacing for distance calculations.
        
        Args:
            pixel_spacing: Pixel spacing tuple (row, col) in mm
        """
        self.pixel_spacing = pixel_spacing
        # Update all existing measurements across all slices
        for measurement_list in self.measurements.values():
            for measurement in measurement_list:
                measurement.update_distance(pixel_spacing)
                # Also update stored pixel spacing in measurement
                measurement.pixel_spacing = pixel_spacing
    
    def start_measurement(self, pos: QPointF) -> None:
        """
        Start a new measurement.
        
        Args:
            pos: Starting position
        """
        self.measuring = True
        self.start_point = pos
    
    def update_measurement(self, pos: QPointF, scene) -> None:
        """
        Update measurement while drawing.
        
        Args:
            pos: Current mouse position (in scene coordinates)
            scene: QGraphicsScene to add items to
        """
        if not self.measuring or self.start_point is None:
            return
        
        # Track the current mouse position for end point calculation
        self.current_end_point = pos
        
        # Remove old items
        if self.current_line_item is not None:
            scene.removeItem(self.current_line_item)
        if self.current_text_item is not None:
            scene.removeItem(self.current_text_item)
        
        # Create line in item coordinates (relative to start_point)
        # Line goes from (0,0) to (pos - start_point) in item coordinates
        line_end_relative = pos - self.start_point
        line = QLineF(QPointF(0, 0), line_end_relative)
        self.current_line_item = QGraphicsLineItem(line)
        # Position line item at start_point in scene coordinates
        self.current_line_item.setPos(self.start_point)
        
        # Get pen settings from config
        pen_width = 2  # Default
        pen_color = (0, 255, 0)  # Default green
        if self.config_manager:
            pen_width = self.config_manager.get_measurement_line_thickness()
            pen_color = self.config_manager.get_measurement_line_color()
        
        pen = QPen(QColor(*pen_color), pen_width)
        pen.setCosmetic(True)  # Makes pen width viewport-relative (independent of zoom)
        self.current_line_item.setPen(pen)
        scene.addItem(self.current_line_item)
        
        # Calculate pixel differences
        dx = pos.x() - self.start_point.x()  # X direction (columns)
        dy = pos.y() - self.start_point.y()  # Y direction (rows)
        
        # Calculate distance using correct formula
        if self.pixel_spacing:
            # pixel_spacing[1] = column spacing (X direction)
            # pixel_spacing[0] = row spacing (Y direction)
            dx_scaled = dx * self.pixel_spacing[1]  # X component in mm
            dy_scaled = dy * self.pixel_spacing[0]  # Y component in mm
            distance_mm = math.sqrt(dx_scaled * dx_scaled + dy_scaled * dy_scaled)
            
            # Format distance in mm
            if distance_mm >= 10:
                distance_formatted = f"{distance_mm:.1f} mm"
            else:
                distance_formatted = f"{distance_mm:.2f} mm"
        else:
            # No pixel spacing - just use pixel distance
            distance_pixels = math.sqrt(dx * dx + dy * dy)
            distance_formatted = f"{distance_pixels:.1f} pixels"
        
        # Create text label
        # Text position in scene coordinates (midpoint of line)
        mid_point = QPointF(
            (self.start_point.x() + pos.x()) / 2.0,
            (self.start_point.y() + pos.y()) / 2.0
        )
        
        # Get font settings from config
        font_size = 10  # Default
        font_color = (0, 255, 0)  # Default green
        if self.config_manager:
            font_size = self.config_manager.get_measurement_font_size()
            font_color = self.config_manager.get_measurement_font_color()
        
        # Create temporary text item (not draggable during drawing)
        self.current_text_item = QGraphicsTextItem(distance_formatted)
        self.current_text_item.setDefaultTextColor(QColor(*font_color))
        font = QFont("Arial", font_size)
        font.setBold(True)
        self.current_text_item.setFont(font)
        self.current_text_item.setPos(mid_point)
        # Set flag to ignore parent transformations (keeps font size consistent)
        self.current_text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        scene.addItem(self.current_text_item)
    
    def finish_measurement(self, scene) -> Optional[MeasurementItem]:
        """
        Finish current measurement.
        
        Args:
            scene: QGraphicsScene to add measurement to
        
        Returns:
            Created measurement item or None
        """
        if not self.measuring or self.start_point is None:
            return None
        
        if self.current_line_item is None or self.current_text_item is None:
            self.measuring = False
            return None
        
        # Get end point in scene coordinates
        # Calculate from the line item's actual coordinates - this is the authoritative source
        # The line item's position is at start_point in scene coordinates
        # The line item's line().p2() is at (pos - start_point) in item coordinates
        # So the actual end point in scene coordinates is: start_point + line_item.line().p2()
        line_end_item_coords = self.current_line_item.line().p2()
        end_point = self.start_point + line_end_item_coords
        
        start_point = self.start_point
        
        # Remove items from scene before adding to group
        if self.current_line_item.scene() is not None:
            self.current_line_item.scene().removeItem(self.current_line_item)
        if self.current_text_item.scene() is not None:
            self.current_text_item.scene().removeItem(self.current_text_item)
        
        # Calculate distance first to get formatted text
        dx = end_point.x() - start_point.x()
        dy = end_point.y() - start_point.y()
        if self.pixel_spacing:
            dx_scaled = dx * self.pixel_spacing[1]
            dy_scaled = dy * self.pixel_spacing[0]
            distance_mm = math.sqrt(dx_scaled * dx_scaled + dy_scaled * dy_scaled)
            if distance_mm >= 10:
                distance_formatted = f"{distance_mm:.1f} mm"
            else:
                distance_formatted = f"{distance_mm:.2f} mm"
        else:
            distance_pixels = math.sqrt(dx * dx + dy * dy)
            distance_formatted = f"{distance_pixels:.1f} pixels"
        
        # Create draggable text item
        # Get font settings from config
        font_size = 10  # Default
        font_color = (0, 255, 0)  # Default green
        if self.config_manager:
            font_size = self.config_manager.get_measurement_font_size()
            font_color = self.config_manager.get_measurement_font_color()
        
        # Create a temporary measurement to get callback reference
        # We'll update the reference after creating the actual measurement
        temp_measurement_ref = {'measurement': None}
        
        def update_text_offset(offset: QPointF) -> None:
            """Update stored text offset when text is moved."""
            if temp_measurement_ref['measurement']:
                # Offset is in scene coordinates, convert to viewport pixels for storage
                view = temp_measurement_ref['measurement'].scene().views()[0] if temp_measurement_ref['measurement'].scene() and temp_measurement_ref['measurement'].scene().views() else None
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
                    offset.x() * scene_to_viewport_scale,
                    offset.y() * scene_to_viewport_scale
                )
                temp_measurement_ref['measurement'].text_offset_viewport = offset_viewport
                temp_measurement_ref['measurement'].text_offset = offset  # Keep for backward compatibility
        
        draggable_text = DraggableMeasurementText(None, update_text_offset)  # Will set measurement after creation
        draggable_text.setDefaultTextColor(QColor(*font_color))
        font = QFont("Arial", font_size)
        font.setBold(True)
        draggable_text.setFont(font)
        draggable_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        draggable_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        draggable_text.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        draggable_text.setPlainText(distance_formatted)
        
        # Create measurement with draggable text
        measurement = MeasurementItem(
            start_point,
            end_point,
            self.current_line_item,
            draggable_text,
            pixel_spacing=self.pixel_spacing
        )
        # Update draggable text's measurement reference
        draggable_text.measurement = measurement
        temp_measurement_ref['measurement'] = measurement
        
        # Add the group (not individual items) to the scene FIRST
        # This ensures scene() is available when update_distance() is called
        scene.addItem(measurement)
        measurement.setZValue(150)  # Above image and ROIs but below overlay
        
        # Now update distance - this will have access to scene/view for proper scale conversion
        measurement.update_distance()
        
        # Add text item directly to scene (not as a child of group) for independent selection
        # Set z-value higher than measurement group for priority selection
        draggable_text.setZValue(151)  # Above measurement (150) for priority selection
        scene.addItem(draggable_text)
        
        # Handles are created as separate scene items in MeasurementItem.__init__()
        # They're not yet in the scene and will be added when measurement is selected
        # update_handle_positions() is already called in update_distance()
        
        # Store measurement in per-slice dictionary
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        if key not in self.measurements:
            self.measurements[key] = []
        self.measurements[key].append(measurement)
        
        self.measuring = False
        self.start_point = None
        self.current_end_point = None  # Clear tracked end point
        self.current_line_item = None
        self.current_text_item = None
        
        return measurement
    
    def cancel_measurement(self, scene) -> None:
        """
        Cancel current measurement.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        if self.current_line_item is not None:
            scene.removeItem(self.current_line_item)
            self.current_line_item = None
        if self.current_text_item is not None:
            scene.removeItem(self.current_text_item)
            self.current_text_item = None
        
        self.measuring = False
        self.start_point = None
        self.current_end_point = None  # Clear tracked end point
    
    def get_measurements_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> List[MeasurementItem]:
        """
        Get all measurements for a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            
        Returns:
            List of measurement items
        """
        key = (study_uid, series_uid, instance_identifier)
        return self.measurements.get(key, [])
    
    def clear_measurements_from_other_slices(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Clear measurements from other slices (not the current one) from the scene.
        
        Args:
            study_uid: StudyInstanceUID of current slice
            series_uid: SeriesInstanceUID of current slice
            instance_identifier: InstanceNumber of current slice
            scene: QGraphicsScene to remove items from
        """
        current_key = (study_uid, series_uid, instance_identifier)
        
        # Get all measurements currently in the scene
        scene_items = list(scene.items())
        for item in scene_items:
            # Check if this is a measurement item
            if isinstance(item, MeasurementItem):
                # Check if this measurement belongs to a different slice
                belongs_to_current = False
                for key, measurement_list in self.measurements.items():
                    if item in measurement_list:
                        if key == current_key:
                            belongs_to_current = True
                        break
                
                # Remove from scene if it doesn't belong to current slice
                if not belongs_to_current and item.scene() == scene:
                    # Remove text item from scene (it's not a child of the group)
                    if item.text_item is not None and item.text_item.scene() == scene:
                        scene.removeItem(item.text_item)
                    # Remove handles first (they're separate scene items)
                    item.hide_handles()
                    # Then remove the measurement item
                    scene.removeItem(item)
    
    def display_measurements_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Display measurements for a slice.
        
        Ensures all measurements for the current slice are visible in the scene.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            scene: QGraphicsScene to add items to
        """
        key = (study_uid, series_uid, instance_identifier)
        measurements = self.measurements.get(key, [])
        
        for measurement in measurements:
            # Add measurement group if not already in scene
            if measurement.scene() != scene:
                scene.addItem(measurement)
                measurement.setZValue(150)  # Above image and ROIs but below overlay
            
            # Add text item if not already in scene
            if measurement.text_item is not None and measurement.text_item.scene() != scene:
                measurement.text_item.setZValue(151)  # Above measurement (150) for priority selection
                scene.addItem(measurement.text_item)
            
            # Ensure measurement is visible
            measurement.show()
            if measurement.text_item is not None:
                measurement.text_item.show()
    
    def clear_slice_measurements(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Clear all measurements from a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            scene: QGraphicsScene to remove items from
        """
        key = (study_uid, series_uid, instance_identifier)
        if key in self.measurements:
            for measurement in self.measurements[key]:
                # Only remove if item actually belongs to this scene
                if measurement.scene() == scene:
                    # Remove text item from scene (it's not a child of the group)
                    if measurement.text_item is not None and measurement.text_item.scene() == scene:
                        scene.removeItem(measurement.text_item)
                    # Remove handles first (they're separate scene items)
                    measurement.hide_handles()
                    # Then remove the measurement item
                    scene.removeItem(measurement)
            del self.measurements[key]
    
    def delete_measurement(self, measurement: MeasurementItem, scene) -> None:
        """
        Delete a specific measurement.
        
        Args:
            measurement: MeasurementItem to delete
            scene: QGraphicsScene to remove item from
        """
        # Remove from scene (handles and text are separate items, so remove them first)
        if measurement.scene() == scene:
            # Remove text item from scene (it's not a child of the group)
            if measurement.text_item is not None and measurement.text_item.scene() == scene:
                scene.removeItem(measurement.text_item)
            # Remove handles first (they're separate scene items)
            measurement.hide_handles()
            # Then remove the measurement item
            scene.removeItem(measurement)
        
        # Remove from storage
        for key, measurement_list in list(self.measurements.items()):
            if measurement in measurement_list:
                measurement_list.remove(measurement)
                # If list is empty, remove the key
                if not measurement_list:
                    del self.measurements[key]
                break
    
    def clear_measurements(self, scene) -> None:
        """
        Clear all measurements from all slices.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        for measurement_list in self.measurements.values():
            for measurement in measurement_list:
                # Only remove if item actually belongs to this scene
                if measurement.scene() == scene:
                    # Remove text item from scene (it's not a child of the group)
                    if measurement.text_item is not None and measurement.text_item.scene() == scene:
                        scene.removeItem(measurement.text_item)
                    # Remove handles first (they're separate scene items)
                    measurement.hide_handles()
                    # Then remove the measurement item
                    scene.removeItem(measurement)
        self.measurements.clear()
    
    def update_all_measurement_text_offsets(self) -> None:
        """
        Update text offset for all measurements when zoom changes.
        
        Recalculates text positions based on current view scale to maintain
        constant viewport pixel offset regardless of zoom level.
        """
        for key, measurement_list in self.measurements.items():
            for measurement in measurement_list:
                if measurement.scene() is not None:
                    measurement.update_text_offset_for_zoom()
    
    def update_all_measurement_styles(self, config_manager) -> None:
        """
        Update styles (line color, thickness, font size, font color) for all existing measurements.
        
        Args:
            config_manager: ConfigManager instance to get current settings
        """
        if config_manager is None:
            return
        
        # Get new settings from config
        pen_width = config_manager.get_measurement_line_thickness()
        pen_color = config_manager.get_measurement_line_color()
        font_size = config_manager.get_measurement_font_size()
        font_color = config_manager.get_measurement_font_color()
        
        # Create new pen with updated settings
        pen = QPen(QColor(*pen_color), pen_width)
        pen.setCosmetic(True)  # Makes pen width viewport-relative (independent of zoom)
        
        # Update all measurements
        for key, measurement_list in self.measurements.items():
            for measurement in measurement_list:
                # Update measurement line pen
                measurement.line_item.setPen(pen)
                
                # Update handle colors to match line color
                handle_color = QColor(*pen_color)
                handle_color_with_alpha = QColor(handle_color.red(), handle_color.green(), handle_color.blue(), 180)
                measurement.start_handle.setPen(QPen(handle_color, 2))
                measurement.start_handle.setBrush(QBrush(handle_color_with_alpha))
                measurement.end_handle.setPen(QPen(handle_color, 2))
                measurement.end_handle.setBrush(QBrush(handle_color_with_alpha))
                
                # Update text item font and color
                if measurement.text_item is not None:
                    measurement.text_item.setDefaultTextColor(QColor(*font_color))
                    font = QFont("Arial", font_size)
                    font.setBold(True)
                    measurement.text_item.setFont(font)

