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
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFont, QColor, QTransform
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
    
    def __init__(self, font_size: int = 6, font_color: tuple = (255, 255, 0), 
                 config_manager=None):
        """
        Initialize the overlay manager.
        
        Args:
            font_size: Default font size in points
            font_color: Default font color as (r, g, b) tuple
            config_manager: Optional ConfigManager instance for overlay tag configuration
        """
        self.mode = "minimal"  # minimal, detailed, hidden (kept for backward compatibility)
        self.custom_fields: List[str] = []
        self.overlay_items: List[QGraphicsTextItem] = []
        self.font_size = font_size
        self.font_color = font_color
        self.config_manager = config_manager
        
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
    
    def _get_modality(self, parser: DICOMParser) -> str:
        """
        Get modality from DICOM dataset.
        
        Args:
            parser: DICOMParser instance
            
        Returns:
            Modality string (e.g., "CT", "MR") or "default"
        """
        modality = parser.get_tag_by_keyword("Modality")
        if modality is None or modality == "":
            return "default"
        return str(modality).strip()
    
    def _get_corner_text(self, parser: DICOMParser, tags: List[str]) -> str:
        """
        Get overlay text for a corner from a list of tags.
        
        Args:
            parser: DICOMParser instance
            tags: List of tag keywords
            
        Returns:
            Formatted text string
        """
        lines = []
        for tag in tags:
            value = parser.get_tag_by_keyword(tag)
            if value is not None and value != "":
                # Format the value
                if isinstance(value, (list, tuple)):
                    value_str = ", ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                lines.append(f"{tag}: {value_str}")
        return "\n".join(lines)
    
    def _create_text_item(self, text: str, x: float, y: float) -> QGraphicsTextItem:
        """
        Create a text item with proper font and styling.
        
        Args:
            text: Text to display
            x: X position
            y: Y position
            
        Returns:
            QGraphicsTextItem
        """
        text_item = QGraphicsTextItem(text)
        text_item.setDefaultTextColor(QColor(*self.font_color))
        text_item.setPos(x, y)
        
        # Set font - use 6pt minimum, scale if smaller
        if self.font_size < 6:
            # Use 6pt font and scale down with transform
            font = QFont("Arial", 6)
            scale_factor = self.font_size / 6.0
            transform = QTransform()
            transform.scale(scale_factor, scale_factor)
            text_item.setTransform(transform)
        else:
            # Use actual font size
            font = QFont("Arial", self.font_size)
        
        font.setBold(True)
        text_item.setFont(font)
        text_item.setZValue(1000)  # High Z-value to stay above image
        
        return text_item
    
    def create_overlay_items(self, scene, parser: DICOMParser, 
                            position: tuple = (10, 10)) -> List[QGraphicsTextItem]:
        """
        Create overlay text items for a graphics scene (4 corners).
        
        Args:
            scene: QGraphicsScene to add items to
            parser: DICOMParser instance
            position: (x, y) position - ignored, using 4 corners instead
            
        Returns:
            List of overlay text items
        """
        # Clear existing items
        self.clear_overlay_items(scene)
        
        if self.mode == "hidden":
            return []
        
        # Get modality and corner tags
        modality = self._get_modality(parser)
        
        # Get tags for each corner from config manager
        if self.config_manager is not None:
            corner_tags = self.config_manager.get_overlay_tags(modality)
        else:
            # Fallback to old behavior: use minimal fields in upper-left
            corner_tags = {
                "upper_left": self.minimal_fields,
                "upper_right": [],
                "lower_left": [],
                "lower_right": []
            }
        
        # Get scene dimensions for positioning
        # Try to get from scene rect, or use image item if available
        scene_rect = scene.sceneRect()
        if scene_rect.width() > 0 and scene_rect.height() > 0:
            scene_width = scene_rect.width()
            scene_height = scene_rect.height()
        else:
            # Try to get from items in scene (e.g., image item)
            items = scene.items()
            if items:
                # Find the largest item (likely the image)
                max_rect = QRectF()
                for item in items:
                    if hasattr(item, 'boundingRect'):
                        item_rect = item.boundingRect()
                        if item_rect.width() * item_rect.height() > max_rect.width() * max_rect.height():
                            max_rect = item_rect
                if max_rect.width() > 0 and max_rect.height() > 0:
                    scene_width = max_rect.width()
                    scene_height = max_rect.height()
                else:
                    scene_width = 800
                    scene_height = 600
            else:
                scene_width = 800
                scene_height = 600
        
        margin = 10
        
        # Create overlay for each corner
        corners = [
            ("upper_left", margin, margin, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            ("upper_right", scene_width - margin, margin, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            ("lower_left", margin, scene_height - margin, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
            ("lower_right", scene_width - margin, scene_height - margin, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        ]
        
        for corner_key, x, y, alignment in corners:
            tags = corner_tags.get(corner_key, [])
            if tags:
                text = self._get_corner_text(parser, tags)
                if text:
                    text_item = self._create_text_item(text, x, y)
                    
                    # Adjust position based on alignment
                    if alignment & Qt.AlignmentFlag.AlignRight:
                        # Right align: adjust x position based on text width
                        text_item.setPos(x - text_item.boundingRect().width(), y)
                    if alignment & Qt.AlignmentFlag.AlignBottom:
                        # Bottom align: adjust y position based on text height
                        text_item.setPos(text_item.pos().x(), y - text_item.boundingRect().height())
                    
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

