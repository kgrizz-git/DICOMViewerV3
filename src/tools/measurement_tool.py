"""
Measurement Tool

This module provides distance measurement functionality with automatic
conversion from pixels to mm/cm based on DICOM metadata. It hosts
MeasurementTool and re-exports the graphics item classes from
measurement_items for backward compatibility.

Inputs:
    - User mouse clicks for measurement points
    - DICOM pixel spacing information

Outputs:
    - Distance measurements with units
    - Measurement graphics items (via re-export from tools.measurement_items)

Requirements:
    - PySide6 for graphics
    - dicom_utils for distance conversion
    - tools.measurement_items for DraggableMeasurementText, MeasurementHandle, MeasurementItem
"""

from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsTextItem, QGraphicsItemGroup, QGraphicsItem, QGraphicsEllipseItem, QGraphicsSceneMouseEvent
from PySide6.QtCore import Qt, QPointF, QLineF, QRectF
from PySide6.QtGui import QPen, QColor, QFont, QBrush, QPainter, QPainterPath, QPainterPathStroker
from typing import List, Optional, Tuple, Dict, Callable
import math

from utils.dicom_utils import format_distance, get_pixel_spacing
from tools.measurement_items import DraggableMeasurementText, MeasurementHandle, MeasurementItem

# Re-export for backward compatibility (existing imports from tools.measurement_tool still work)
__all__ = ["MeasurementTool", "DraggableMeasurementText", "MeasurementHandle", "MeasurementItem"]


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

