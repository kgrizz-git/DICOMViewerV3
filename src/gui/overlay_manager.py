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
from PySide6.QtGui import QFont, QColor, QTransform, QTextDocument, QTextOption
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
        
        # Store current parser and scene for updating positions
        self.current_parser: Optional[DICOMParser] = None
        self.current_scene = None
        
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
    
    def _create_text_item(self, text: str, x: float, y: float, alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft) -> QGraphicsTextItem:
        """
        Create a text item with proper font and styling.
        
        Font size is set in absolute pixels, independent of image dimensions.
        Uses ItemIgnoresTransformations to keep font size constant.
        
        Args:
            text: Text to display
            x: X position
            y: Y position
            alignment: Text alignment (AlignLeft, AlignRight, etc.)
            
        Returns:
            QGraphicsTextItem
        """
        text_item = QGraphicsTextItem()
        text_item.setDefaultTextColor(QColor(*self.font_color))
        
        # Set font - use absolute pixel size
        # Use 6pt minimum, scale if smaller using QTransform
        if self.font_size < 6:
            # Use 6pt font and scale down with transform for sizes < 6pt
            font = QFont("Arial", 6)
            scale_factor = self.font_size / 6.0
            transform = QTransform()
            transform.scale(scale_factor, scale_factor)
            text_item.setTransform(transform)
        else:
            # Use actual font size in points
            font = QFont("Arial", self.font_size)
        
        font.setBold(True)
        text_item.setFont(font)
        
        # Set text with alignment using QTextDocument
        document = QTextDocument()
        document.setDefaultFont(font)
        # Set text option with proper alignment
        text_option = QTextOption()
        if alignment & Qt.AlignmentFlag.AlignRight:
            text_option.setAlignment(Qt.AlignmentFlag.AlignRight)
        elif alignment & Qt.AlignmentFlag.AlignLeft:
            text_option.setAlignment(Qt.AlignmentFlag.AlignLeft)
        else:
            text_option.setAlignment(Qt.AlignmentFlag.AlignLeft)
        document.setDefaultTextOption(text_option)
        document.setPlainText(text)
        text_item.setDocument(document)
        
        # Set flag to ignore parent transformations (keeps font size consistent)
        # This ensures font size doesn't change when view is zoomed or image size changes
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        text_item.setZValue(1000)  # High Z-value to stay above image
        
        # Set position - for right-aligned text, adjust x position
        if alignment & Qt.AlignmentFlag.AlignRight:
            # Position at x, then adjust based on text width
            text_item.setPos(x, y)
        else:
            text_item.setPos(x, y)
        
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
        # Store current parser and scene for position updates
        self.current_parser = parser
        self.current_scene = scene
        
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
        
        # Get view for coordinate conversion (needed for ItemIgnoresTransformations)
        view = scene.views()[0] if scene.views() else None
        
        # For ItemIgnoresTransformations items, we need to position based on viewport edges
        # mapped to scene coordinates, so text stays anchored to viewport when zooming
        if view is not None:
            viewport_width = view.viewport().width()
            viewport_height = view.viewport().height()
            
            # Map viewport edges to scene coordinates
            top_left_scene = view.mapToScene(0, 0)
            top_right_scene = view.mapToScene(viewport_width, 0)
            bottom_left_scene = view.mapToScene(0, viewport_height)
            bottom_right_scene = view.mapToScene(viewport_width, viewport_height)
            
            # Update corner positions based on viewport-to-scene mapping
            corners = [
                ("upper_left", top_left_scene.x() + margin, top_left_scene.y() + margin, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                ("upper_right", top_right_scene.x() - margin, top_right_scene.y() + margin, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
                ("lower_left", bottom_left_scene.x() + margin, bottom_left_scene.y() - margin, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
                ("lower_right", bottom_right_scene.x() - margin, bottom_right_scene.y() - margin, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
            ]
        
        for corner_key, x, y, alignment in corners:
            tags = corner_tags.get(corner_key, [])
            if tags:
                text = self._get_corner_text(parser, tags)
                if text:
                    # For right-aligned corners, create separate text items for each line
                    # so each row can be individually right-aligned
                    is_right_aligned = bool(alignment & Qt.AlignmentFlag.AlignRight)
                    
                    if is_right_aligned:
                        # Split text into lines and create separate items for each
                        lines = [line for line in text.split('\n') if line.strip()]  # Filter empty lines
                        line_height = None
                        
                        for line_idx, line in enumerate(lines):
                            # Create text item for this line with right alignment
                            text_item = self._create_text_item(line, x, y, alignment)
                            
                            # Get line height from first line
                            if line_height is None:
                                line_height = text_item.boundingRect().height()
                            
                            # Position: for right-aligned, position at viewport right edge (mapped to scene)
                            # With ItemIgnoresTransformations, position is in scene coordinates
                            # x is already the right edge position from viewport mapping
                            text_width = text_item.boundingRect().width()
                            
                            # Calculate vertical position based on line index
                            line_spacing = line_height * 1.2
                            if alignment & Qt.AlignmentFlag.AlignBottom:
                                # Bottom alignment: stack from bottom
                                # y is already the bottom edge position from viewport mapping
                                text_y = y - (len(lines) - line_idx) * line_spacing
                            else:
                                # Top alignment: stack from top
                                # y is already the top edge position from viewport mapping
                                text_y = y + line_idx * line_spacing
                            
                            # Position at right edge: x - text_width (x is already right edge)
                            # This ensures text aligns to the right edge of the viewport
                            text_item.setPos(x - text_width, text_y)
                            
                            scene.addItem(text_item)
                            self.overlay_items.append(text_item)
                    else:
                        # Left-aligned corners: create single multi-line text item
                        text_item = self._create_text_item(text, x, y, alignment)
                        
                        # Position: for left-aligned, use viewport edge positions (mapped to scene)
                        # With ItemIgnoresTransformations, position is in scene coordinates
                        # x and y are already set from viewport-to-scene mapping
                        text_item.setPos(x, y)
                        
                        # Adjust y position for bottom alignment
                        if alignment & Qt.AlignmentFlag.AlignBottom:
                            text_height = text_item.boundingRect().height()
                            text_item.setPos(text_item.pos().x(), y - text_height)
                        
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
    
    def update_overlay_positions(self, scene) -> None:
        """
        Update overlay item positions when view transform changes (zoom/pan).
        
        This ensures text stays anchored to viewport edges when zooming.
        
        Args:
            scene: QGraphicsScene containing overlay items
        """
        if not self.overlay_items or self.current_parser is None:
            return
        
        # Get view for coordinate conversion
        view = scene.views()[0] if scene.views() else None
        if view is None:
            return
        
        # Get scene dimensions
        scene_rect = scene.sceneRect()
        if scene_rect.width() <= 0 or scene_rect.height() <= 0:
            return
        
        scene_width = scene_rect.width()
        scene_height = scene_rect.height()
        margin = 10
        
        # Get viewport dimensions
        viewport_width = view.viewport().width()
        viewport_height = view.viewport().height()
        
        # Update positions for each overlay item
        # We need to determine which corner each item belongs to
        # For now, we'll recreate the overlay items with updated positions
        # This is simpler than tracking which item belongs to which corner
        
        # Clear and recreate with current view transform
        if self.current_parser is not None:
            self.create_overlay_items(scene, self.current_parser)

