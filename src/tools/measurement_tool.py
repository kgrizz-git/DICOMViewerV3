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
        # Make text item selectable so it can be moved independently
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
    
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
            if self.parentItem() is not None and self.measurement is not None:
                # Position is relative to parent (MeasurementItem group)
                text_pos = self.pos()
                # Calculate midpoint of measurement line relative to group
                mid_point_relative = QPointF(
                    self.measurement.end_relative.x() / 2.0,
                    self.measurement.end_relative.y() / 2.0
                )
                # Calculate offset from midpoint
                offset = text_pos - mid_point_relative
                
                # Update stored offset
                if self.offset_update_callback:
                    self.offset_update_callback(offset)
        
        return super().itemChange(change, value)


class MeasurementHandle(QGraphicsEllipseItem):
    """
    Handle for editing measurement endpoints.
    
    Child of MeasurementItem group for automatic movement and lifecycle management.
    """
    
    def __init__(self, measurement: 'MeasurementItem', is_start: bool):
        """
        Initialize handle as child of measurement item.
        
        Args:
            measurement: Parent MeasurementItem (Qt parent)
            is_start: True if this is the start handle, False for end handle
        """
        handle_size = 8.0  # Larger for easier clicking
        # Pass measurement as Qt parent so handle is a child of the group
        super().__init__(-handle_size, -handle_size, handle_size * 2, handle_size * 2, measurement)
        self.parent_measurement = measurement
        self.is_start = is_start
        
        # Styling - more opaque for better visibility
        handle_pen = QPen(QColor(0, 255, 0), 2)  # Green outline
        handle_brush = QBrush(QColor(0, 255, 0, 180))  # More opaque green fill
        self.setPen(handle_pen)
        self.setBrush(handle_brush)
        
        # Flags
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(200)  # Above measurement (150) for priority selection
        
        # Cursor for better UX
        self.setCursor(Qt.CursorShape.SizeAllCursor)
    
    def mousePressEvent(self, event: 'QGraphicsSceneMouseEvent') -> None:
        """
        Handle mouse press to keep measurement selected.
        
        Args:
            event: Mouse press event
        """
        # Keep parent measurement selected when clicking handle
        if self.parent_measurement is not None:
            if not self.parent_measurement.isSelected():
                self.parent_measurement.setSelected(True)
        
        # Call parent to handle the drag
        super().mousePressEvent(event)
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """
        Handle position changes to update parent measurement.
        
        Args:
            change: Type of change
            value: New value (parent-relative coordinates since handle is a child)
            
        Returns:
            Modified value
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Handle position is now in parent-relative coordinates (group coordinates)
            if self.parent_measurement is not None:
                # Check if measurement is still valid (hasn't been deleted)
                if self.parent_measurement.scene() is None:
                    return value  # Measurement deleted, don't update
                
                # Prevent recursive updates
                if hasattr(self.parent_measurement, '_updating_handles'):
                    if self.parent_measurement._updating_handles:
                        return value
                
                # Value is in parent-relative coordinates (group coordinates)
                parent_relative_pos = value
                # Convert to scene coordinates
                scene_pos = self.parent_measurement.mapToScene(parent_relative_pos)
                
                self.parent_measurement._updating_handles = True
                
                try:
                    if self.is_start:
                        # Update start point in scene coordinates
                        self.parent_measurement.start_point = scene_pos
                        # Update group position to new start point
                        self.parent_measurement.setPos(self.parent_measurement.start_point)
                        # Recalculate distance (this already calls update_handle_positions())
                        self.parent_measurement.update_distance()
                        # Handle position should be at (0, 0) relative to group
                        return QPointF(0, 0)
                    else:
                        # Update end point in scene coordinates
                        self.parent_measurement.end_point = scene_pos
                        # Recalculate distance (this already calls update_handle_positions())
                        self.parent_measurement.update_distance()
                        # Update end_relative and return new position in group coordinates
                        self.parent_measurement.end_relative = (
                            self.parent_measurement.end_point - 
                            self.parent_measurement.start_point
                        )
                        return self.parent_measurement.end_relative
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
        self.text_offset = QPointF(0, 0)  # Offset from midpoint for text position
        
        # Calculate end_relative BEFORE positioning the group
        # This is the offset from start_point to end_point in scene coordinates
        # After the group is positioned at start_point, this becomes the group-relative position
        self.end_relative = end_point - start_point
        
        # Store original scene positions before adding to group
        # (items will be positioned relative to group after adding)
        line_scene_pos = line_item.pos()
        text_scene_pos = text_item.pos()
        
        # Add line and text items to the group
        self.addToGroup(line_item)
        self.addToGroup(text_item)
        
        # Adjust positions to be relative to group
        # Set group position to start_point so line starts at (0,0) relative to group
        self.setPos(start_point)
        line_item.setPos(QPointF(0, 0))  # Line starts at group origin
        # Text position relative to group
        text_item.setPos(text_scene_pos - start_point)
        
        # Create handles as children of this group
        # They will be positioned in group-relative coordinates
        self.start_handle = MeasurementHandle(self, is_start=True)
        self.end_handle = MeasurementHandle(self, is_start=False)
        
        # Initially hide handles (they'll be shown when measurement is selected)
        self.start_handle.hide()
        self.end_handle.hide()
        
        # Make the group selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        # Disable Qt's default selection rectangle - we'll draw our own
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemUsesExtendedStyleOption, True)
        
        # Initialize flag to prevent recursive handle updates
        self._updating_handles = False
        
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
        
        Since handles are children, they're automatically in the scene.
        Just update positions and show them.
        """
        if self.scene() is None:
            return
        
        if self.start_handle is None or self.end_handle is None:
            return
        
        # Update handle positions (in group-relative coordinates)
        self.update_handle_positions()
        
        # Show handles
        self.start_handle.show()
        self.end_handle.show()
    
    def hide_handles(self) -> None:
        """
        Hide handles when measurement is deselected.
        
        Since handles are children, they stay in the scene but are hidden.
        """
        if self.start_handle is not None:
            self.start_handle.hide()
        if self.end_handle is not None:
            self.end_handle.hide()
    
    def update_handle_positions(self, force: bool = False) -> None:
        """
        Update handle positions in group-relative coordinates.
        
        Called when measurement endpoints change or measurement is moved.
        Since handles are children, they use group-relative coordinates.
        
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
        
        # Set flag to indicate we're programmatically updating handles
        # This prevents handle's itemChange from triggering updates
        was_updating = getattr(self, '_updating_handles', False)
        self._updating_handles = True
        
        try:
            # Start handle at (0, 0) relative to group (group position is at start_point)
            self.start_handle.setPos(QPointF(0, 0))
            
            # End handle at end_relative (group-relative coordinates)
            self.end_handle.setPos(self.end_relative)
        finally:
            # Restore original flag state
            self._updating_handles = was_updating
    
    def update_distance(self, pixel_spacing: Optional[Tuple[float, float]] = None) -> None:
        """
        Update distance calculation and label.
        
        Args:
            pixel_spacing: Optional pixel spacing tuple (if None, uses stored pixel_spacing)
        """
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
        
        # Update line item (relative to group position)
        # Group position is at start_point, so line goes from (0,0) to end_relative
        line = QLineF(QPointF(0, 0), self.end_relative)
        self.line_item.setLine(line)
        
        # Update text item position (relative to group) and text
        mid_point_relative = QPointF(
            self.end_relative.x() / 2.0,
            self.end_relative.y() / 2.0
        )
        # Use stored offset
        text_pos = mid_point_relative + self.text_offset
        
        # Set updating flag if it's a draggable text item
        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = True
        
        self.text_item.setPos(text_pos)
        self.text_item.setPlainText(self.distance_formatted)
        
        # Clear updating flag
        if isinstance(self.text_item, DraggableMeasurementText):
            self.text_item._updating_position = False
        
        # Update group position to start_point
        self.setPos(self.start_point)
        
        # Update handle positions in scene coordinates (handles are separate items)
        # Force update to bypass recursion check since we're updating from distance calculation
        self.update_handle_positions(force=True)
    
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
            
            # Update line item to reflect new end point (relative to group)
            self.line_item.setLine(QLineF(QPointF(0, 0), self.end_relative))
            
            # Update text position (relative to group)
            mid_point_relative = QPointF(
                self.end_relative.x() / 2.0,
                self.end_relative.y() / 2.0
            )
            # Use stored offset
            text_pos = mid_point_relative + self.text_offset
            
            # Set updating flag if it's a draggable text item
            if isinstance(self.text_item, DraggableMeasurementText):
                self.text_item._updating_position = True
            
            self.text_item.setPos(text_pos)
            
            # Clear updating flag
            if isinstance(self.text_item, DraggableMeasurementText):
                self.text_item._updating_position = False
            
            # Update handle positions in scene coordinates (handles are separate items)
            # Use force=True to ensure handles are updated even if _updating_handles flag is set
            # (though it shouldn't be when moving the measurement line itself)
            self.update_handle_positions(force=True)
            
            # Update group position to new start point
            return self.start_point
        
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            # Show/hide handles based on selection state
            if value:  # Selected
                self.show_handles()
            else:  # Deselected
                self.hide_handles()
            
            # Force update to redraw selection indicator (yellow dashed line)
            self.update()
        
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
                temp_measurement_ref['measurement'].text_offset = offset
        
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
        
        # Distance already calculated, but ensure it's updated
        measurement.update_distance()
        
        # Add the group (not individual items) to the scene
        # Handles are already children of the group, so they're automatically added
        scene.addItem(measurement)
        measurement.setZValue(150)  # Above image and ROIs but below overlay
        
        # Handles are already created as children in MeasurementItem.__init__()
        # They're already hidden initially, and will be shown when measurement is selected
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
                    # Handles are children, so they're automatically removed with the item
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
            
            # Ensure measurement is visible
            measurement.show()
    
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
                    # Handles are children, so they're automatically removed with the item
                    scene.removeItem(measurement)
            del self.measurements[key]
    
    def delete_measurement(self, measurement: MeasurementItem, scene) -> None:
        """
        Delete a specific measurement.
        
        Args:
            measurement: MeasurementItem to delete
            scene: QGraphicsScene to remove item from
        """
        # Remove from scene (handles are children, so they're automatically removed)
        if measurement.scene() == scene:
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
                    # Handles are children, so they're automatically removed with the item
                    scene.removeItem(measurement)
        self.measurements.clear()

