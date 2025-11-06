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

from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsTextItem
from PySide6.QtCore import Qt, QPointF, QLineF
from PySide6.QtGui import QPen, QColor, QFont
from typing import List, Optional, Tuple
import numpy as np
import math

from utils.dicom_utils import format_distance, get_pixel_spacing


class MeasurementItem:
    """
    Represents a single distance measurement.
    """
    
    def __init__(self, start_point: QPointF, end_point: QPointF,
                 line_item: QGraphicsLineItem, text_item: QGraphicsTextItem):
        """
        Initialize measurement item.
        
        Args:
            start_point: Start point of measurement
            end_point: End point of measurement
            line_item: Graphics line item
            text_item: Graphics text item for label
        """
        self.start_point = start_point
        self.end_point = end_point
        self.line_item = line_item
        self.text_item = text_item
        self.distance_pixels = 0.0
        self.distance_formatted = ""
    
    def update_distance(self, pixel_spacing: Optional[Tuple[float, float]] = None) -> None:
        """
        Update distance calculation and label.
        
        Args:
            pixel_spacing: Optional pixel spacing tuple
        """
        # Calculate pixel distance
        dx = self.end_point.x() - self.start_point.x()
        dy = self.end_point.y() - self.start_point.y()
        self.distance_pixels = math.sqrt(dx * dx + dy * dy)
        
        # Format distance
        # Use average pixel spacing for diagonal measurements
        if pixel_spacing:
            avg_spacing = (pixel_spacing[0] + pixel_spacing[1]) / 2.0
            spacing = (avg_spacing, avg_spacing)
        else:
            spacing = None
        
        self.distance_formatted = format_distance(self.distance_pixels, spacing, 0)
        
        # Update text item
        mid_point = QPointF(
            (self.start_point.x() + self.end_point.x()) / 2.0,
            (self.start_point.y() + self.end_point.y()) / 2.0
        )
        self.text_item.setPos(mid_point)
        self.text_item.setPlainText(self.distance_formatted)


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
        self.measurements: List[MeasurementItem] = []
        self.measuring = False
        self.start_point: Optional[QPointF] = None
        self.current_line_item: Optional[QGraphicsLineItem] = None
        self.current_text_item: Optional[QGraphicsTextItem] = None
        self.pixel_spacing: Optional[Tuple[float, float]] = None
    
    def set_pixel_spacing(self, pixel_spacing: Optional[Tuple[float, float]]) -> None:
        """
        Set pixel spacing for distance calculations.
        
        Args:
            pixel_spacing: Pixel spacing tuple (row, col) in mm
        """
        self.pixel_spacing = pixel_spacing
        # Update all existing measurements
        for measurement in self.measurements:
            measurement.update_distance(pixel_spacing)
    
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
            pos: Current mouse position
            scene: QGraphicsScene to add items to
        """
        if not self.measuring or self.start_point is None:
            return
        
        # Remove old items
        if self.current_line_item is not None:
            scene.removeItem(self.current_line_item)
        if self.current_text_item is not None:
            scene.removeItem(self.current_text_item)
        
        # Create line
        line = QLineF(self.start_point, pos)
        self.current_line_item = QGraphicsLineItem(line)
        pen = QPen(QColor(0, 255, 0), 2)  # Green, 2px
        self.current_line_item.setPen(pen)
        scene.addItem(self.current_line_item)
        
        # Calculate distance
        dx = pos.x() - self.start_point.x()
        dy = pos.y() - self.start_point.y()
        distance_pixels = math.sqrt(dx * dx + dy * dy)
        
        # Format distance
        distance_formatted = format_distance(distance_pixels, self.pixel_spacing, 0)
        
        # Create text label
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
    
    def finish_measurement(self) -> Optional[MeasurementItem]:
        """
        Finish current measurement.
        
        Returns:
            Created measurement item or None
        """
        if not self.measuring or self.start_point is None:
            return None
        
        if self.current_line_item is None or self.current_text_item is None:
            self.measuring = False
            return None
        
        # Create measurement item
        end_point = QPointF(
            self.current_line_item.line().p2().x(),
            self.current_line_item.line().p2().y()
        )
        
        measurement = MeasurementItem(
            self.start_point,
            end_point,
            self.current_line_item,
            self.current_text_item
        )
        measurement.update_distance(self.pixel_spacing)
        
        self.measurements.append(measurement)
        
        self.measuring = False
        self.start_point = None
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
    
    def clear_measurements(self, scene) -> None:
        """
        Clear all measurements.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        for measurement in self.measurements:
            scene.removeItem(measurement.line_item)
            scene.removeItem(measurement.text_item)
        self.measurements.clear()

