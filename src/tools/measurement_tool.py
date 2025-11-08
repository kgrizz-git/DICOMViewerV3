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

from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsTextItem, QGraphicsItemGroup, QGraphicsItem, QGraphicsEllipseItem
from PySide6.QtCore import Qt, QPointF, QLineF, QRectF
from PySide6.QtGui import QPen, QColor, QFont, QBrush, QPainter, QPainterPath
from typing import List, Optional, Tuple, Dict
import numpy as np
import math

from utils.dicom_utils import format_distance, get_pixel_spacing


class MeasurementHandle(QGraphicsEllipseItem):
    """
    Handle for editing measurement endpoints.
    """
    
    def __init__(self, parent: 'MeasurementItem', is_start: bool):
        """
        Initialize handle.
        
        Args:
            parent: Parent MeasurementItem
            is_start: True if this is the start handle, False for end handle
        """
        handle_size = 6.0
        super().__init__(-handle_size, -handle_size, handle_size * 2, handle_size * 2, parent)
        self.parent_measurement = parent
        self.is_start = is_start
        
        handle_pen = QPen(QColor(0, 255, 0), 2)  # Green outline
        handle_brush = QBrush(QColor(0, 255, 0, 128))  # Semi-transparent green fill
        self.setPen(handle_pen)
        self.setBrush(handle_brush)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setZValue(152)  # Above line and text
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """
        Handle position changes to update parent measurement.
        
        Args:
            change: Type of change
            value: New value
            
        Returns:
            Modified value
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # Notify parent of handle movement
            if self.parent_measurement is not None:
                handle_pos = value
                # Convert handle position (relative to group) to scene coordinates
                scene_pos = self.parent_measurement.mapToScene(handle_pos)
                
                if self.is_start:
                    # Update start point
                    self.parent_measurement.start_point = scene_pos
                    # Update group position to new start point
                    self.parent_measurement.setPos(self.parent_measurement.start_point)
                else:
                    # Update end point
                    self.parent_measurement.end_point = scene_pos
                
                # Recalculate distance
                self.parent_measurement.update_distance()
        
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
        
        # Create endpoint handles (small circles)
        # Create without parent, then add to group to ensure proper coordinate system
        # Start point handle (at group origin, so (0, 0) relative to group)
        self.start_handle = MeasurementHandle(None, is_start=True)
        self.start_handle.parent_measurement = self  # Set parent reference manually
        self.addToGroup(self.start_handle)
        self.start_handle.setPos(QPointF(0, 0))  # At group origin
        
        # End point handle (relative to group) - use stored end_relative
        self.end_handle = MeasurementHandle(None, is_start=False)
        self.end_handle.parent_measurement = self  # Set parent reference manually
        self.addToGroup(self.end_handle)
        # Set position AFTER adding to group
        self.end_handle.setPos(self.end_relative)
        
        # Make the group selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        
        # Calculate initial distance
        self.update_distance()
    
    def boundingRect(self) -> QRectF:
        """
        Return bounding rectangle for the measurement.
        
        Returns:
            Bounding rectangle that includes line, text, and handles
        """
        # Get line bounding rect (relative to group)
        line_rect = self.line_item.boundingRect()
        
        # Get text bounding rect (relative to group)
        text_rect = self.text_item.boundingRect()
        text_pos = self.text_item.pos()
        text_rect.translate(text_pos)
        
        # Get handle bounding rects (relative to group)
        handle_size = 6.0
        start_handle_rect = QRectF(-handle_size, -handle_size, handle_size * 2, handle_size * 2)
        # Use stored end_relative (group-relative coordinates)
        end_handle_rect = QRectF(
            self.end_relative.x() - handle_size, self.end_relative.y() - handle_size,
            handle_size * 2, handle_size * 2
        )
        
        # Combine all rects
        combined_rect = line_rect
        combined_rect = combined_rect.united(text_rect)
        combined_rect = combined_rect.united(start_handle_rect)
        combined_rect = combined_rect.united(end_handle_rect)
        
        # Add some padding for selection outline
        padding = 5.0
        combined_rect.adjust(-padding, -padding, padding, padding)
        
        return combined_rect
    
    def shape(self) -> QPainterPath:
        """
        Return shape for hit testing.
        
        Returns:
            QPainterPath that includes line and handles for accurate clicking
        """
        path = QPainterPath()
        
        # Add line to path
        line = self.line_item.line()
        path.moveTo(line.p1())
        path.lineTo(line.p2())
        
        # Add handles to path (make them clickable)
        handle_size = 6.0
        handle_radius = handle_size
        
        # Start handle
        start_handle_path = QPainterPath()
        start_handle_path.addEllipse(-handle_radius, -handle_radius, handle_radius * 2, handle_radius * 2)
        path.addPath(start_handle_path)
        
        # End handle - use stored end_relative (group-relative coordinates)
        end_handle_path = QPainterPath()
        end_handle_path.addEllipse(
            self.end_relative.x() - handle_radius, self.end_relative.y() - handle_radius,
            handle_radius * 2, handle_radius * 2
        )
        path.addPath(end_handle_path)
        
        # Create a stroke path for the line (wider hit area)
        stroke_path = QPainterPath()
        line = self.line_item.line()
        stroke_path.moveTo(line.p1())
        stroke_path.lineTo(line.p2())
        
        # Create a stroked path with width for easier clicking
        pen = QPen(QColor(0, 255, 0), 8)  # Wider stroke for hit testing
        stroked_path = QPainterPath()
        stroked_path.addPath(stroke_path)
        
        # Combine with handles
        path.addPath(stroked_path)
        
        return path
    
    def paint(self, painter: QPainter, option, widget=None) -> None:
        """
        Paint selection indicator when item is selected.
        
        Args:
            painter: QPainter to draw with
            option: Style option
            widget: Optional widget
        """
        if self.isSelected():
            # Draw selection indicator (dashed line along the measurement)
            painter.save()
            
            # Set pen for selection indicator
            selection_pen = QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine)  # Yellow dashed
            painter.setPen(selection_pen)
            
            # Draw dashed line along the measurement line
            line = self.line_item.line()
            painter.drawLine(line)
            
            # Draw selection outline around handles
            handle_size = 6.0
            handle_pen = QPen(QColor(255, 255, 0), 2, Qt.PenStyle.DashLine)
            painter.setPen(handle_pen)
            
            # Start handle
            painter.drawEllipse(QRectF(-handle_size, -handle_size, handle_size * 2, handle_size * 2))
            
            # End handle - use stored end_relative (group-relative coordinates)
            painter.drawEllipse(QRectF(
                self.end_relative.x() - handle_size, self.end_relative.y() - handle_size,
                handle_size * 2, handle_size * 2
            ))
            
            painter.restore()
        
        # Call parent paint to draw children
        super().paint(painter, option, widget)
    
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
        
        # Calculate pixel distance
        dx = self.end_point.x() - self.start_point.x()
        dy = self.end_point.y() - self.start_point.y()
        self.distance_pixels = math.sqrt(dx * dx + dy * dy)
        
        # Format distance
        # Use average pixel spacing for diagonal measurements
        if spacing:
            avg_spacing = (spacing[0] + spacing[1]) / 2.0
            spacing_for_format = (avg_spacing, avg_spacing)
        else:
            spacing_for_format = None
        
        self.distance_formatted = format_distance(self.distance_pixels, spacing_for_format, 0)
        
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
        self.text_item.setPos(mid_point_relative)
        self.text_item.setPlainText(self.distance_formatted)
        
        # Update endpoint handles
        handle_size = 6.0
        # Start handle is at (0, 0) relative to group
        self.start_handle.setRect(-handle_size, -handle_size, handle_size * 2, handle_size * 2)
        # End handle is at end_relative
        self.end_handle.setRect(
            self.end_relative.x() - handle_size, self.end_relative.y() - handle_size,
            handle_size * 2, handle_size * 2
        )
        self.end_handle.setPos(self.end_relative)
        
        # Update group position to start_point
        self.setPos(self.start_point)
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """
        Handle item changes (e.g., position changes when moved).
        
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
            self.text_item.setPos(mid_point_relative)
            
            # Update endpoint handles
            handle_size = 6.0
            self.start_handle.setRect(-handle_size, -handle_size, handle_size * 2, handle_size * 2)
            self.end_handle.setRect(
                self.end_relative.x() - handle_size, self.end_relative.y() - handle_size,
                handle_size * 2, handle_size * 2
            )
            self.end_handle.setPos(self.end_relative)
            
            # Update group position to new start point
            return self.start_point
        
        return super().itemChange(change, value)


class MeasurementTool:
    """
    Manages distance measurements on images.
    
    Features:
    - Draw measurement lines
    - Calculate distances in pixels, mm, or cm
    - Display measurement labels
    """
    
    def __init__(self):
        """Initialize the measurement tool."""
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
        pen = QPen(QColor(0, 255, 0), 2)  # Green, 2px
        self.current_line_item.setPen(pen)
        scene.addItem(self.current_line_item)
        
        # Calculate distance
        dx = pos.x() - self.start_point.x()
        dy = pos.y() - self.start_point.y()
        distance_pixels = math.sqrt(dx * dx + dy * dy)
        
        # Format distance - use average pixel spacing for diagonal measurements
        spacing_for_format = None
        if self.pixel_spacing:
            avg_spacing = (self.pixel_spacing[0] + self.pixel_spacing[1]) / 2.0
            spacing_for_format = (avg_spacing, avg_spacing)
        distance_formatted = format_distance(distance_pixels, spacing_for_format, 0)
        
        # Create text label
        # Text position in scene coordinates (midpoint of line)
        mid_point = QPointF(
            (self.start_point.x() + pos.x()) / 2.0,
            (self.start_point.y() + pos.y()) / 2.0
        )
        self.current_text_item = QGraphicsTextItem(distance_formatted)
        self.current_text_item.setDefaultTextColor(QColor(0, 255, 0))  # Green text
        font = QFont("Arial", 10)
        font.setBold(True)
        self.current_text_item.setFont(font)
        self.current_text_item.setPos(mid_point)
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
        
        measurement = MeasurementItem(
            start_point,
            end_point,
            self.current_line_item,
            self.current_text_item,
            pixel_spacing=self.pixel_spacing
        )
        # Distance already calculated in __init__, but ensure it's updated
        measurement.update_distance()
        
        # Add the group (not individual items) to the scene
        scene.addItem(measurement)
        measurement.setZValue(150)  # Above image and ROIs but below overlay
        
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
                    scene.removeItem(measurement)
            del self.measurements[key]
    
    def delete_measurement(self, measurement: MeasurementItem, scene) -> None:
        """
        Delete a specific measurement.
        
        Args:
            measurement: MeasurementItem to delete
            scene: QGraphicsScene to remove item from
        """
        # Remove from scene
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
                    scene.removeItem(measurement)
        self.measurements.clear()

