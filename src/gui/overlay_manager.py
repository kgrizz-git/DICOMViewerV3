"""
Metadata Overlay Manager

This module manages the display of DICOM metadata overlays on images
with customizable fields and display modes (minimal, detailed, hidden).

Inputs:
    - DICOM metadata
    - Overlay configuration
    - Display mode selection
    
Outputs:
    - Overlay text to display on images
    - Overlay rendering
    
Requirements:
    - PySide6 for graphics
    - DICOMParser for metadata
"""

from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor
from typing import List, Dict, Optional
import pydicom
from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser


class OverlayManager:
    """
    Manages metadata overlays on DICOM images.
    
    Features:
    - Customizable overlay fields
    - Multiple display modes (minimal, detailed, hidden)
    - Text positioning and styling
    - Customizable font size and color
    """
    
    def __init__(self, font_size: int = 8, font_color: tuple = (255, 255, 0)):
        """
        Initialize the overlay manager.
        
        Args:
            font_size: Default font size in points
            font_color: Default font color as (r, g, b) tuple
        """
        self.mode = "minimal"  # minimal, detailed, hidden
        self.custom_fields: List[str] = []
        self.overlay_items: List[QGraphicsTextItem] = []
        self.font_size = font_size
        self.font_color = font_color
        
        # Default fields for minimal mode
        self.minimal_fields = [
            "PatientName",
            "StudyDate",
            "SeriesDescription",
            "InstanceNumber",
        ]
        
        # Default fields for detailed mode
        self.detailed_fields = [
            "PatientName",
            "PatientID",
            "StudyDate",
            "StudyTime",
            "StudyDescription",
            "SeriesNumber",
            "SeriesDescription",
            "Modality",
            "InstanceNumber",
            "SliceLocation",
            "WindowCenter",
            "WindowWidth",
        ]
    
    def set_mode(self, mode: str) -> None:
        """
        Set the overlay display mode.
        
        Args:
            mode: Display mode ("minimal", "detailed", or "hidden")
        """
        if mode in ["minimal", "detailed", "hidden"]:
            self.mode = mode
    
    def set_custom_fields(self, fields: List[str]) -> None:
        """
        Set custom overlay fields.
        
        Args:
            fields: List of DICOM tag keywords
        """
        self.custom_fields = fields
    
    def set_font_size(self, size: int) -> None:
        """
        Set overlay font size.
        
        Args:
            size: Font size in points
        """
        if size > 0:
            self.font_size = size
    
    def set_font_color(self, r: int, g: int, b: int) -> None:
        """
        Set overlay font color.
        
        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        self.font_color = (r, g, b)
    
    def get_overlay_text(self, parser: DICOMParser) -> str:
        """
        Get overlay text for a dataset.
        
        Args:
            parser: DICOMParser instance with dataset set
            
        Returns:
            Formatted overlay text
        """
        if self.mode == "hidden":
            return ""
        
        # Determine which fields to show
        if self.mode == "minimal":
            fields = self.minimal_fields
        elif self.mode == "detailed":
            fields = self.detailed_fields
        else:
            fields = self.custom_fields
        
        # Get values for each field
        lines = []
        for field in fields:
            value = parser.get_tag_by_keyword(field)
            if value is not None and value != "":
                # Format the value
                if isinstance(value, (list, tuple)):
                    value_str = ", ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                lines.append(f"{field}: {value_str}")
        
        return "\n".join(lines)
    
    def create_overlay_items(self, scene, parser: DICOMParser, 
                            position: tuple = (10, 10)) -> List[QGraphicsTextItem]:
        """
        Create overlay text items for a graphics scene.
        
        Args:
            scene: QGraphicsScene to add items to
            parser: DICOMParser instance
            position: (x, y) position for overlay
            
        Returns:
            List of overlay text items
        """
        # Clear existing items
        self.clear_overlay_items(scene)
        
        if self.mode == "hidden":
            return []
        
        # Get overlay text
        text = self.get_overlay_text(parser)
        if not text:
            return []
        
        # Create text item
        text_item = QGraphicsTextItem(text)
        # Use configured font color (default yellow)
        text_item.setDefaultTextColor(QColor(*self.font_color))
        text_item.setPos(position[0], position[1])
        
        # Set font with configured size (default 8)
        font = QFont("Arial", self.font_size)
        font.setBold(True)
        text_item.setFont(font)
        
        # Set Z-value to ensure overlay stays on top
        text_item.setZValue(1000)  # High Z-value to stay above image
        
        # Add to scene
        scene.addItem(text_item)
        self.overlay_items.append(text_item)
        
        return self.overlay_items
    
    def clear_overlay_items(self, scene) -> None:
        """
        Clear overlay items from scene.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        for item in self.overlay_items:
            scene.removeItem(item)
        self.overlay_items.clear()

