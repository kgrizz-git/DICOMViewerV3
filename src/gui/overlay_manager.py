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

from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsItem, QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QFont, QColor, QTransform, QTextDocument, QTextOption
from typing import List, Dict, Optional
import pydicom
from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser
from core.multiframe_handler import is_multiframe, get_frame_count
from utils.dicom_utils import get_patient_tag_keywords


class ViewportOverlayWidget(QWidget):
    """
    Widget container for viewport-based overlay labels.
    
    Manages QLabel widgets positioned at viewport corners (not scene coordinates).
    These widgets stay fixed at viewport positions regardless of zoom/pan.
    
    Features:
    - Four corner labels (upper_left, upper_right, lower_left, lower_right)
    - Viewport pixel-based positioning (no scene coordinate conversion needed)
    - Automatic position updates on viewport resize
    - Same styling as QGraphicsItem overlays
    """
    
    def __init__(self, parent: Optional[QWidget] = None, font_size: int = 6, 
                 font_color: tuple = (255, 255, 0)):
        """
        Initialize the viewport overlay widget.
        
        Args:
            parent: Parent widget (should be ImageViewer's viewport)
            font_size: Font size in points
            font_color: Font color as (r, g, b) tuple
        """
        super().__init__(parent)
        self.font_size = font_size
        self.font_color = font_color
        
        # Set widget to be transparent and not interfere with mouse events
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")
        
        # Ensure widget stays fixed at viewport coordinates
        # Set widget to use absolute positioning relative to viewport
        # This prevents the widget from being affected by parent transforms
        if parent:
            # Set geometry immediately to ensure widget is positioned correctly
            self.setGeometry(0, 0, parent.width(), parent.height())
        
        # Create labels for each corner
        self.corner_labels: Dict[str, QLabel] = {
            "upper_left": QLabel(self),
            "upper_right": QLabel(self),
            "lower_left": QLabel(self),
            "lower_right": QLabel(self)
        }
        
        # Configure labels
        font = QFont("Arial", font_size)
        font.setBold(True)
        color = QColor(*font_color)
        
        for label in self.corner_labels.values():
            label.setFont(font)
            label.setStyleSheet(f"color: rgb({font_color[0]}, {font_color[1]}, {font_color[2]}); background: transparent;")
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            label.hide()  # Hide by default until content is set
        
        # Margin in viewport pixels
        self.margin = 10
    
    def resizeEvent(self, event) -> None:
        """
        Handle resize events to update label positions.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        # Update label positions when widget resizes
        # This is the ONLY place where label positions should be updated
        # (not during zoom/pan operations)
        # Debug logging commented out to reduce noise (uncomment if debugging overlay resize issues)
        # print(f"[DEBUG-WIDGET] resizeEvent: widget resized to {event.size().width()}x{event.size().height()}")
        self.update_positions(event.size().width(), event.size().height())
    
    def set_corner_text(self, corner_key: str, text: str, alignment: Qt.AlignmentFlag) -> None:
        """
        Set text for a corner label.
        
        Args:
            corner_key: Corner identifier ("upper_left", "upper_right", "lower_left", "lower_right")
            text: Text to display
            alignment: Text alignment (AlignLeft, AlignRight, etc.)
        """
        if corner_key not in self.corner_labels:
            return
        
        label = self.corner_labels[corner_key]
        
        if text:
            label.setText(text)
            label.setAlignment(alignment)
            label.show()
        else:
            label.hide()
    
    def update_positions(self, viewport_width: int, viewport_height: int) -> None:
        """
        Update label positions based on viewport size.
        
        Args:
            viewport_width: Viewport width in pixels
            viewport_height: Viewport height in pixels
        """
        margin = self.margin
        
        # Upper left
        upper_left_label = self.corner_labels["upper_left"]
        if upper_left_label.isVisible():
            upper_left_label.move(margin, margin)
            upper_left_label.adjustSize()
        
        # Upper right
        upper_right_label = self.corner_labels["upper_right"]
        if upper_right_label.isVisible():
            upper_right_label.adjustSize()
            label_width = upper_right_label.width()
            upper_right_label.move(viewport_width - label_width - margin, margin)
        
        # Lower left
        lower_left_label = self.corner_labels["lower_left"]
        if lower_left_label.isVisible():
            lower_left_label.adjustSize()
            label_height = lower_left_label.height()
            lower_left_label.move(margin, viewport_height - label_height - margin)
        
        # Lower right
        lower_right_label = self.corner_labels["lower_right"]
        if lower_right_label.isVisible():
            lower_right_label.adjustSize()
            label_width = lower_right_label.width()
            label_height = lower_right_label.height()
            lower_right_label.move(viewport_width - label_width - margin, 
                                  viewport_height - label_height - margin)
    
    def set_font_size(self, font_size: int) -> None:
        """
        Update font size for all labels.
        
        Args:
            font_size: New font size in points
        """
        self.font_size = font_size
        font = QFont("Arial", font_size)
        font.setBold(True)
        for label in self.corner_labels.values():
            label.setFont(font)
    
    def set_font_color(self, font_color: tuple) -> None:
        """
        Update font color for all labels.
        
        Args:
            font_color: Font color as (r, g, b) tuple
        """
        self.font_color = font_color
        style = f"color: rgb({font_color[0]}, {font_color[1]}, {font_color[2]}); background: transparent;"
        for label in self.corner_labels.values():
            label.setStyleSheet(style)
    
    def clear_all(self) -> None:
        """Clear all corner labels."""
        for label in self.corner_labels.values():
            label.clear()
            label.hide()


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
                 config_manager=None, use_widget_overlays: bool = True):
        """
        Initialize the overlay manager.
        
        Args:
            font_size: Default font size in points
            font_color: Default font color as (r, g, b) tuple
            config_manager: Optional ConfigManager instance for overlay tag configuration
            use_widget_overlays: If True, use QWidget viewport overlays instead of QGraphicsItem overlays
        """
        self.mode = "minimal"  # minimal, detailed, hidden (kept for backward compatibility)
        self.visibility_state = 0  # 0=show all, 1=hide corner text, 2=hide all text
        self.custom_fields: List[str] = []
        self.overlay_items: List[QGraphicsTextItem] = []
        self.font_size = font_size
        self.font_color = font_color
        self.config_manager = config_manager
        self.use_widget_overlays = use_widget_overlays  # Flag to switch between approaches
        self.privacy_mode: bool = False
        
        # Store current parser and scene for updating positions
        self.current_parser: Optional[DICOMParser] = None
        self.current_scene = None
        
        # QWidget overlay widget (viewport-based)
        self.viewport_overlay_widget: Optional[ViewportOverlayWidget] = None
        
        # Track which items belong to which corner for position updates
        self.corner_item_map: Dict[str, List[QGraphicsTextItem]] = {
            "upper_left": [],
            "upper_right": [],
            "lower_left": [],
            "lower_right": []
        }
        
        # Cache maximum text widths for right-aligned corners (prevents jitter during cine playback)
        # Stores max width in viewport pixels for each right-aligned corner
        self.corner_max_width_map: Dict[str, float] = {}
        
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
    
    def toggle_overlay_visibility(self) -> int:
        """
        Toggle overlay visibility state through 3 states.
        
        State 0: Show all overlays (default)
        State 1: Hide corner text overlays only
        State 2: Hide corner text + measurements/annotations
        
        Returns:
            Current visibility state after toggle (0, 1, or 2)
        """
        self.visibility_state = (self.visibility_state + 1) % 3
        return self.visibility_state
    
    def set_visibility_state(self, state: int) -> None:
        """
        Set the overlay visibility state.
        
        Args:
            state: Visibility state (0=show all, 1=hide corner text, 2=hide all text)
        """
        if state in [0, 1, 2]:
            self.visibility_state = state
    
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
    
    def set_privacy_mode(self, enabled: bool) -> None:
        """
        Set privacy mode for masking patient tags in overlays.
        
        Args:
            enabled: True to enable privacy mode, False to disable
        """
        self.privacy_mode = enabled
    
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
    
    def _get_corner_text(self, parser: DICOMParser, tags: List[str], total_slices: Optional[int] = None,
                        projection_enabled: bool = False, projection_start_slice: Optional[int] = None,
                        projection_end_slice: Optional[int] = None, projection_total_thickness: Optional[float] = None,
                        projection_type: Optional[str] = None) -> str:
        """
        Get overlay text for a corner from a list of tags.
        
        Args:
            parser: DICOMParser instance
            tags: List of tag keywords
            total_slices: Total number of slices in the series (for formatting InstanceNumber)
            projection_enabled: Whether Combine Slices projection is enabled
            projection_start_slice: Start slice index (0-based) of the projection range
            projection_end_slice: End slice index (0-based) of the projection range
            projection_total_thickness: Total thickness of combined slices in mm
            projection_type: Projection type ("aip", "mip", or "minip")
            
        Returns:
            Formatted text string
        """
        lines = []
        
        # Check if this is a multi-frame dataset (FrameDatasetWrapper)
        dataset = parser.dataset
        frame_index = None
        total_frames = None
        is_multiframe_dataset = False
        
        if dataset is not None:
            # Check if dataset is a FrameDatasetWrapper (has _frame_index attribute)
            if hasattr(dataset, '_frame_index') and hasattr(dataset, '_original_dataset'):
                is_multiframe_dataset = True
                frame_index = dataset._frame_index  # 0-based
                original_dataset = dataset._original_dataset
                # Get total frames from original dataset
                if is_multiframe(original_dataset):
                    total_frames = get_frame_count(original_dataset)
        
        for tag in tags:
            value = parser.get_tag_by_keyword(tag)
            if value is not None and value != "":
                # Format the value
                if isinstance(value, (list, tuple)):
                    value_str = ", ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                
                # Apply privacy mode masking for patient tags
                if self.privacy_mode and tag in get_patient_tag_keywords():
                    value_str = "PRIVACY MODE"
                
                # Special formatting for InstanceNumber: show as "Slice X/Y" if total_slices is provided
                if tag == "InstanceNumber" and total_slices is not None:
                    try:
                        instance_num = int(value_str)
                        # Build the base slice display string
                        slice_display = f"Slice {instance_num}/{total_slices}"
                        
                        # Add projection range if enabled
                        if projection_enabled and projection_start_slice is not None and projection_end_slice is not None:
                            # Convert to 1-based for display
                            start_display = projection_start_slice + 1
                            end_display = projection_end_slice + 1
                            # Map projection type to display format
                            projection_type_display = ""
                            if projection_type:
                                type_map = {
                                    "aip": "AIP",
                                    "mip": "MIP",
                                    "minip": "MinIP"
                                }
                                projection_type_display = type_map.get(projection_type.lower(), projection_type.upper())
                            if projection_type_display:
                                slice_display += f" ({start_display}-{end_display} {projection_type_display})"
                            else:
                                slice_display += f" ({start_display}-{end_display})"
                        
                        # For multi-frame datasets, also show frame information
                        if is_multiframe_dataset and total_frames is not None:
                            # Display as "Slice X/Y (Frame A/B)" or "Slice X/Y (1-4) (Frame A/B)"
                            frame_display = frame_index + 1  # Convert to 1-based for display
                            lines.append(f"{slice_display} (Frame {frame_display}/{total_frames})")
                        else:
                            lines.append(slice_display)
                    except (ValueError, TypeError):
                        # If InstanceNumber is not a valid integer, show as-is
                        lines.append(f"{tag}: {value_str}")
                # Special formatting for SliceThickness: show total thickness when projection is enabled
                elif tag == "SliceThickness" and projection_enabled and projection_total_thickness is not None:
                    try:
                        single_thickness = float(value_str)
                        # Display as "Slice Thickness: X (Y)" where X is single slice and Y is total
                        lines.append(f"Slice Thickness: {single_thickness} ({projection_total_thickness})")
                    except (ValueError, TypeError):
                        # If SliceThickness is not a valid number, show as-is
                        lines.append(f"{tag}: {value_str}")
                else:
                    lines.append(f"{tag}: {value_str}")
        
        # If multi-frame and frame info not already shown with InstanceNumber, add it separately
        # Only add frame info to corners that have InstanceNumber to avoid duplicating in all corners
        if is_multiframe_dataset and total_frames is not None:
            # Check if InstanceNumber was in the tags
            instance_in_tags = "InstanceNumber" in tags
            # Only add frame info if InstanceNumber is in this corner's tags
            # and it wasn't already included with InstanceNumber formatting (i.e., total_slices is None)
            if instance_in_tags and total_slices is None:
                # Add frame information as a separate line
                frame_display = frame_index + 1  # Convert to 1-based for display
                lines.append(f"Frame: {frame_display}/{total_frames}")
        
        return "\n".join(lines)
    
    def _create_text_item(self, text: str, x: float, y: float, alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft, text_width: Optional[float] = None) -> QGraphicsTextItem:
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
        # Remove default margins to get accurate bounding rect and tighter spacing
        document.setDocumentMargin(0)
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
        # For right-aligned text, set a fixed width if provided
        # This ensures all lines in a corner have the same width and align properly
        if text_width is not None and (alignment & Qt.AlignmentFlag.AlignRight):
            document.setTextWidth(text_width)
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
                            position: tuple = (10, 10), total_slices: Optional[int] = None,
                            projection_enabled: bool = False, projection_start_slice: Optional[int] = None,
                            projection_end_slice: Optional[int] = None, projection_total_thickness: Optional[float] = None,
                            projection_type: Optional[str] = None) -> List[QGraphicsTextItem]:
        """
        Create overlay text items for a graphics scene (4 corners).
        
        Args:
            scene: QGraphicsScene to add items to
            parser: DICOMParser instance
            position: (x, y) position - ignored, using 4 corners instead
            total_slices: Total number of slices in the series (for formatting InstanceNumber as "Slice X/Y")
            projection_enabled: Whether Combine Slices projection is enabled
            projection_start_slice: Start slice index (0-based) of the projection range
            projection_end_slice: End slice index (0-based) of the projection range
            projection_total_thickness: Total thickness of combined slices in mm
            projection_type: Projection type ("aip", "mip", or "minip")
            
        Returns:
            List of overlay text items
        """
        # Store current parser and scene for position updates
        self.current_parser = parser
        self.current_scene = scene
        # Store total_slices for position updates
        if total_slices is not None:
            self.current_total_slices = total_slices
        
        # Get view for QWidget overlay creation
        view = scene.views()[0] if scene.views() else None
        
        # Use QWidget overlays if enabled
        if self.use_widget_overlays and view is not None:
            return self._create_widget_overlays(view, parser, total_slices, projection_enabled,
                                                projection_start_slice, projection_end_slice,
                                                projection_total_thickness, projection_type)
        
        # Clear existing items and corner mapping (QGraphicsItem approach)
        self.clear_overlay_items(scene)
        # Reset corner mapping
        for corner_key in self.corner_item_map:
            self.corner_item_map[corner_key].clear()
        
        # Hide overlays based on visibility state
        # State 1 and 2 hide corner text overlays
        if self.visibility_state in [1, 2]:
            return []
        
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
        
        margin = 10  # Margin in viewport pixels
        
        # Get view for coordinate conversion (needed for ItemIgnoresTransformations)
        view = scene.views()[0] if scene.views() else None
        
        # Calculate viewport-to-scene scale factor first
        # This is needed for converting viewport pixel dimensions to scene coordinates
        # when using ItemIgnoresTransformations
        if view is not None:
            # Get the scale factor from the view's transform
            # m11() gives the horizontal scale factor
            view_scale = view.transform().m11()
            if view_scale > 0:
                # Convert viewport pixels to scene coordinates
                # If view is zoomed 2x, 1 viewport pixel = 0.5 scene units
                viewport_to_scene_scale = 1.0 / view_scale
            else:
                viewport_to_scene_scale = 1.0
        else:
            viewport_to_scene_scale = 1.0
        
        # Convert margin from viewport pixels to scene coordinates
        margin_scene = margin * viewport_to_scene_scale
        
        # Create overlay for each corner (fallback for when view is None)
        corners = [
            ("upper_left", margin, margin, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            ("upper_right", scene_width - margin, margin, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            ("lower_left", margin, scene_height - margin, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
            ("lower_right", scene_width - margin, scene_height - margin, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        ]
        
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
            # Use margin_scene (converted to scene coordinates) instead of margin
            # For right-aligned corners, use the actual right edge (top_right_scene.x()) without subtracting margin
            # This ensures text is flush with the viewport right edge, matching left-aligned text behavior
            corners = [
                ("upper_left", top_left_scene.x() + margin_scene, top_left_scene.y() + margin_scene, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
                ("upper_right", top_right_scene.x(), top_right_scene.y() + margin_scene, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
                ("lower_left", bottom_left_scene.x() + margin_scene, bottom_left_scene.y() - margin_scene, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
                ("lower_right", bottom_right_scene.x(), bottom_left_scene.y() - margin_scene, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
            ]
        
        for corner_key, x, y, alignment in corners:
            tags = corner_tags.get(corner_key, [])
            if tags:
                text = self._get_corner_text(parser, tags, total_slices, projection_enabled,
                                            projection_start_slice, projection_end_slice, projection_total_thickness,
                                            projection_type)
                if text:
                    # For right-aligned corners, create separate text items for each line
                    # so each row can be individually right-aligned
                    is_right_aligned = bool(alignment & Qt.AlignmentFlag.AlignRight)
                    
                    if is_right_aligned:
                        # Split text into lines and create separate items for each
                        lines = [line for line in text.split('\n') if line.strip()]  # Filter empty lines
                        
                        # First pass: calculate maximum text width for all lines in viewport pixels
                        # With ItemIgnoresTransformations, text renders at fixed viewport size
                        # so we need to calculate width in viewport pixels, then convert to scene coords
                        max_text_width_viewport = 0
                        temp_items = []
                        for line in lines:
                            temp_item = self._create_text_item(line, 0, 0, alignment)
                            # Get width in viewport pixels (ItemIgnoresTransformations renders at fixed size)
                            temp_width = temp_item.boundingRect().width()
                            max_text_width_viewport = max(max_text_width_viewport, temp_width)
                            temp_items.append(temp_item)
                        
                        # Clean up temp items
                        for item in temp_items:
                            del item
                        
                        # Add some padding to max width for better appearance
                        max_text_width_viewport += 5
                        
                        # Cache the max width for this corner to prevent jitter during cine playback
                        # This ensures consistent positioning even when text content changes between slices
                        self.corner_max_width_map[corner_key] = max_text_width_viewport
                        
                        # Convert viewport pixel width to scene coordinates
                        # viewport_to_scene_scale is already calculated above for all corners
                        max_text_width_scene = max_text_width_viewport * viewport_to_scene_scale
                        
                        # Position: right edge should be at (x - margin_scene) in scene coordinates
                        # where x is the viewport right edge in scene coords
                        # So left edge is at (x - margin_scene - max_text_width_scene)
                        # Use margin_scene (converted to scene coordinates) instead of margin
                        right_edge_x = x - margin_scene  # x is viewport right edge in scene coords
                        left_edge_x = right_edge_x - max_text_width_scene
                        
                        line_height_viewport = None
                        
                        for line_idx, line in enumerate(lines):
                            # Create text item with fixed width for right alignment
                            # Use viewport pixel width for the document
                            text_item = self._create_text_item(line, 0, 0, alignment, text_width=max_text_width_viewport)
                            
                            # Get line height from first line (in viewport pixels)
                            if line_height_viewport is None:
                                line_height_viewport = text_item.boundingRect().height()
                            
                            # Convert line height from viewport pixels to scene coordinates
                            # This ensures spacing remains constant when zooming
                            line_height_scene = line_height_viewport * viewport_to_scene_scale
                            
                            # Calculate vertical position based on line index
                            # Use tighter spacing (0.9) for minimal gaps between lines
                            # This ensures consistent spacing across all modalities
                            line_spacing = line_height_scene * 0.9
                            if alignment & Qt.AlignmentFlag.AlignBottom:
                                # Bottom alignment: stack from bottom
                                # y is already the bottom edge position from viewport mapping
                                text_y = y - (len(lines) - line_idx) * line_spacing
                            else:
                                # Top alignment: stack from top
                                # y is already the top edge position from viewport mapping
                                text_y = y + line_idx * line_spacing
                            
                            # Position at left edge (right edge will align at right_edge_x)
                            text_item.setPos(left_edge_x, text_y)
                            
                            scene.addItem(text_item)
                            self.overlay_items.append(text_item)
                            # Track this item for this corner
                            self.corner_item_map[corner_key].append(text_item)
                    else:
                        # Left-aligned corners: create single multi-line text item
                        text_item = self._create_text_item(text, x, y, alignment)
                        
                        # Position: for left-aligned, use viewport edge positions (mapped to scene)
                        # With ItemIgnoresTransformations, position is in scene coordinates
                        # x and y are already set from viewport-to-scene mapping
                        text_item.setPos(x, y)
                        
                        # Adjust y position for bottom alignment
                        if alignment & Qt.AlignmentFlag.AlignBottom:
                            # Get text height in viewport pixels (ItemIgnoresTransformations renders at fixed size)
                            text_height_viewport = text_item.boundingRect().height()
                            # Convert from viewport pixels to scene coordinates
                            # This ensures the text stays anchored when zooming
                            text_height_scene = text_height_viewport * viewport_to_scene_scale
                            text_item.setPos(text_item.pos().x(), y - text_height_scene)
                        
                        scene.addItem(text_item)
                        self.overlay_items.append(text_item)
                        # Track this item for this corner
                        self.corner_item_map[corner_key].append(text_item)
        
        return self.overlay_items
    
    def _create_widget_overlays(self, view, parser: DICOMParser, 
                                total_slices: Optional[int] = None,
                                projection_enabled: bool = False,
                                projection_start_slice: Optional[int] = None,
                                projection_end_slice: Optional[int] = None,
                                projection_total_thickness: Optional[float] = None,
                                projection_type: Optional[str] = None) -> List[QGraphicsTextItem]:
        """
        Create QWidget-based viewport overlays.
        
        Args:
            view: QGraphicsView to add overlays to
            parser: DICOMParser instance
            total_slices: Total number of slices in the series
            projection_enabled: Whether Combine Slices projection is enabled
            projection_start_slice: Start slice index (0-based) of the projection range
            projection_end_slice: End slice index (0-based) of the projection range
            projection_total_thickness: Total thickness of combined slices in mm
            projection_type: Projection type ("aip", "mip", or "minip")
            
        Returns:
            Empty list (for compatibility with QGraphicsItem approach)
        """
        # Hide overlays based on visibility state
        if self.visibility_state in [1, 2]:
            if self.viewport_overlay_widget:
                self.viewport_overlay_widget.clear_all()
            return []
        
        if self.mode == "hidden":
            if self.viewport_overlay_widget:
                self.viewport_overlay_widget.clear_all()
            return []
        
        # Get viewport
        viewport = view.viewport()
        if viewport is None:
            return []
        
        # Create or get existing overlay widget
        if self.viewport_overlay_widget is None:
            self.viewport_overlay_widget = ViewportOverlayWidget(
                viewport, 
                font_size=self.font_size,
                font_color=self.font_color
            )
            # Make widget fill the viewport and raise it above other widgets
            # Widget must stay at (0,0) and match viewport size to remain fixed during pan/zoom
            self.viewport_overlay_widget.setGeometry(0, 0, viewport.width(), viewport.height())
            self.viewport_overlay_widget.raise_()  # Raise above other widgets
            self.viewport_overlay_widget.show()
        else:
            # Update font size and color if changed
            self.viewport_overlay_widget.set_font_size(self.font_size)
            self.viewport_overlay_widget.set_font_color(self.font_color)
            # Ensure widget fills viewport and stays at (0,0) (in case viewport was resized)
            # This ensures widget stays fixed during pan/zoom operations
            current_geometry = self.viewport_overlay_widget.geometry()
            if (current_geometry.x() != 0 or current_geometry.y() != 0 or
                current_geometry.width() != viewport.width() or 
                current_geometry.height() != viewport.height()):
                self.viewport_overlay_widget.setGeometry(0, 0, viewport.width(), viewport.height())
        
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
        
        # Generate text for each corner
        corners = [
            ("upper_left", Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            ("upper_right", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            ("lower_left", Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
            ("lower_right", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        ]
        
        for corner_key, alignment in corners:
            tags = corner_tags.get(corner_key, [])
            if tags:
                text = self._get_corner_text(parser, tags, total_slices, projection_enabled,
                                            projection_start_slice, projection_end_slice,
                                            projection_total_thickness, projection_type)
                if text:
                    self.viewport_overlay_widget.set_corner_text(corner_key, text, alignment)
                else:
                    self.viewport_overlay_widget.set_corner_text(corner_key, "", alignment)
            else:
                self.viewport_overlay_widget.set_corner_text(corner_key, "", alignment)
        
        # Update positions based on current viewport size
        self.viewport_overlay_widget.update_positions(viewport.width(), viewport.height())
        
        # Return empty list for compatibility (QWidget overlays don't return QGraphicsItems)
        return []
    
    def clear_overlay_items(self, scene) -> None:
        """
        Clear overlay items from scene.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        # Clear QWidget overlays if they exist
        if self.viewport_overlay_widget:
            self.viewport_overlay_widget.clear_all()
            self.viewport_overlay_widget = None
        
        # Check if items are still valid before trying to remove them
        # Items may have already been deleted by scene.clear() or other operations
        for item in self.overlay_items:
            try:
                # Check if item is still valid and in the scene
                if item is not None and item.scene() == scene:
                    scene.removeItem(item)
            except RuntimeError:
                # Item's C++ object has already been deleted, skip it
                pass
            except Exception:
                # Any other error, skip this item
                pass
        self.overlay_items.clear()
        
        # Clear width cache when items are cleared
        self.corner_max_width_map.clear()
    
    def update_overlay_positions(self, scene) -> None:
        """
        Update overlay item positions when view transform changes (zoom/pan).
        
        This ensures text stays anchored to viewport edges when zooming/panning.
        Updates existing items instead of recreating them to prevent jitter.
        
        For QWidget overlays, only updates on viewport resize (not zoom/pan).
        
        Args:
            scene: QGraphicsScene containing overlay items
        """
        # Get view for coordinate conversion
        view = scene.views()[0] if scene.views() else None
        if view is None:
            return
        
        # Handle QWidget overlays - only update on viewport resize, not zoom/pan
        # Position updates for QWidget overlays are handled by ViewportOverlayWidget.resizeEvent()
        # when the viewport actually resizes. We should NOT update positions here during
        # transform changes (zoom/pan) because the viewport size hasn't changed.
        if self.use_widget_overlays:
            # Just ensure widget geometry matches viewport and stays at (0,0)
            # but don't update label positions - that's handled by resizeEvent
            if self.viewport_overlay_widget:
                viewport = view.viewport()
                if viewport:
                    # Check if widget position or size needs updating
                    current_geometry = self.viewport_overlay_widget.geometry()
                    view_transform = view.transform()
                    translation_x = view_transform.m31()
                    translation_y = view_transform.m32()
                    
                    # Debug: Only log during panning (when translation is non-zero)
                    if abs(translation_x) > 0.01 or abs(translation_y) > 0.01:
                        widget_pos = (current_geometry.x(), current_geometry.y())
                        widget_size = (current_geometry.width(), current_geometry.height())
                        viewport_size = (viewport.width(), viewport.height())
                        print(f"[DEBUG-WIDGET-PAN] PAN detected: widget_pos={widget_pos}, widget_size={widget_size}, "
                              f"viewport_size={viewport_size}, transform_translation=({translation_x:.2f}, {translation_y:.2f})")
                        
                        # Log label positions to see if they're moving
                        for corner_key, label in self.viewport_overlay_widget.corner_labels.items():
                            if label.isVisible():
                                label_pos = label.pos()
                                print(f"[DEBUG-WIDGET-PAN] {corner_key} label position: {label_pos}")
                    
                    # Ensure widget stays at (0,0) and matches viewport size
                    if (current_geometry.x() != 0 or current_geometry.y() != 0 or
                        current_geometry.width() != viewport.width() or 
                        current_geometry.height() != viewport.height()):
                        if abs(translation_x) > 0.01 or abs(translation_y) > 0.01:
                            print(f"[DEBUG-WIDGET-PAN] Correcting widget geometry: {current_geometry} -> (0, 0, {viewport.width()}, {viewport.height()})")
                        self.viewport_overlay_widget.setGeometry(0, 0, viewport.width(), viewport.height())
            return
        
        # QGraphicsItem approach - update positions on zoom/pan
        if not self.overlay_items or self.current_parser is None:
            return
        
        # Verify this view is associated with the scene
        if view.scene != scene:
            # print(f"[DEBUG-OVERLAY] WARNING: View's scene doesn't match! view.scene={view.scene}, scene={scene}")
            # Try to find the correct view
            views = scene.views()
            if views:
                view = views[0]
            else:
                return
        
        # Check if this view belongs to a subwindow and if it's focused
        # We need to traverse the widget hierarchy to find the SubWindowContainer
        # View -> (may have layout parent) -> SubWindowContainer
        from gui.sub_window_container import SubWindowContainer
        
        # Traverse up the widget hierarchy to find SubWindowContainer
        subwindow_container = None
        current_widget = view
        max_depth = 5  # Safety limit to avoid infinite loops
        depth = 0
        
        while current_widget is not None and depth < max_depth:
            parent = current_widget.parent()
            if isinstance(parent, SubWindowContainer):
                subwindow_container = parent
                break
            current_widget = parent
            depth += 1
        
        # Debug logging (commented out - only needed for QGraphicsItem approach)
        # view_type = type(view).__name__
        # parent_type = type(view.parent()).__name__ if view.parent() else "None"
        # found_container = subwindow_container is not None
        # is_focused = subwindow_container.is_focused if subwindow_container else None
        # 
        # # Diagnostic logging: View transform state
        # view_transform = view.transform()
        # view_scale = view_transform.m11()
        # view_translation_x = view_transform.m31()
        # view_translation_y = view_transform.m32()
        # 
        # print(f"[DEBUG-OVERLAY] update_overlay_positions: view={view_type}, parent={parent_type}, "
        #       f"found_container={found_container}, is_focused={is_focused}")
        # print(f"[DEBUG-DIAG] View transform: scale={view_scale:.6f}, translation=({view_translation_x:.2f}, {view_translation_y:.2f})")
        # 
        # # Diagnostic logging: Check if this is a focus change event
        # if subwindow_container:
        #     # Log focus state change if we can detect it
        #     if hasattr(self, '_last_focus_state'):
        #         if self._last_focus_state != is_focused:
        #             print(f"[DEBUG-DIAG] FOCUS CHANGE DETECTED: {self._last_focus_state} -> {is_focused}")
        #     self._last_focus_state = is_focused
        
        # IMPORTANT: We ALWAYS update overlay positions, regardless of focus state
        # This ensures overlays stay fixed relative to the viewport, not the image
        # When zooming unfocused subwindows, we still need to update positions
        # so the overlay stays at viewport edges (not moving with the image)
        
        # Get scene dimensions
        scene_rect = scene.sceneRect()
        if scene_rect.width() <= 0 or scene_rect.height() <= 0:
            return
        
        margin = 10  # Margin in viewport pixels
        
        # Calculate viewport-to-scene scale factor
        view_scale = view.transform().m11()
        if view_scale > 0:
            viewport_to_scene_scale = 1.0 / view_scale
        else:
            viewport_to_scene_scale = 1.0
        
        # Convert margin from viewport pixels to scene coordinates
        margin_scene = margin * viewport_to_scene_scale
        
        # Map viewport edges to scene coordinates
        viewport_width = view.viewport().width()
        viewport_height = view.viewport().height()
        
        top_left_scene = view.mapToScene(0, 0)
        top_right_scene = view.mapToScene(viewport_width, 0)
        bottom_left_scene = view.mapToScene(0, viewport_height)
        bottom_right_scene = view.mapToScene(viewport_width, viewport_height)
        
        # Diagnostic logging: mapToScene results and coordinate calculations (commented out - only for QGraphicsItem approach)
        # if subwindow_container and not subwindow_container.is_focused:
        #     print(f"[DEBUG-OVERLAY] Unfocused subwindow - viewport: {viewport_width}x{viewport_height}, "
        #           f"view_scale: {view_scale:.3f}, viewport_to_scene_scale: {viewport_to_scene_scale:.6f}, "
        #           f"top_left_scene: ({top_left_scene.x():.1f}, {top_left_scene.y():.1f}), "
        #           f"top_right_scene: ({top_right_scene.x():.1f}, {top_right_scene.y():.1f})")
        #     print(f"[DEBUG-DIAG] mapToScene(0,0)={top_left_scene}, mapToScene({viewport_width},0)={top_right_scene}")
        #     print(f"[DEBUG-DIAG] mapToScene(0,{viewport_height})={bottom_left_scene}, mapToScene({viewport_width},{viewport_height})={bottom_right_scene}")
        
        # Define corner positions and alignments
        corners = [
            ("upper_left", top_left_scene.x() + margin_scene, top_left_scene.y() + margin_scene, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            ("upper_right", top_right_scene.x(), top_right_scene.y() + margin_scene, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            ("lower_left", bottom_left_scene.x() + margin_scene, bottom_left_scene.y() - margin_scene, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
            ("lower_right", bottom_right_scene.x(), bottom_left_scene.y() - margin_scene, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        ]
        
        # Update positions for each corner's items
        for corner_key, x, y, alignment in corners:
            items = self.corner_item_map.get(corner_key, [])
            
            # Debug: Log calculated corner position for unfocused subwindows (commented out - only for QGraphicsItem approach)
            # if subwindow_container and not subwindow_container.is_focused:
            #     print(f"[DEBUG-OVERLAY] {corner_key} calculated position: x={x:.1f}, y={y:.1f}, alignment={alignment}")
            #     print(f"[DEBUG-OVERLAY] Checking {corner_key}: found {len(items)} items in corner_item_map")
            
            if not items:
                continue
            
            # Check if items are still valid (not deleted)
            valid_items = [item for item in items if item is not None and item.scene() == scene]
            
            # Debug: Log validation results for unfocused subwindows (commented out - only for QGraphicsItem approach)
            # if subwindow_container and not subwindow_container.is_focused:
            #     print(f"[DEBUG-OVERLAY] {corner_key}: {len(items)} total items, {len(valid_items)} valid items (scene match)")
            #     # Verify ItemIgnoresTransformations flag and parent relationship
            #     for item_idx, item in enumerate(valid_items[:1]):  # Check first item only
            #         if item is not None:
            #             flags = item.flags()
            #             has_ignore_flag = bool(flags & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
            #             parent_item = item.parentItem()
            #             is_direct_child = parent_item is None
            #             item_pos = item.pos()
            #             item_bounding_rect = item.boundingRect()
            #             item_scene_pos = item.scenePos()
            #             print(f"[DEBUG-OVERLAY] {corner_key} item {item_idx}: ItemIgnoresTransformations={has_ignore_flag}, parent_item={parent_item}, is_direct_child={is_direct_child}")
            #             print(f"[DEBUG-DIAG] {corner_key} item {item_idx}: pos={item_pos}, scenePos={item_scene_pos}, boundingRect={item_bounding_rect}")
            
            if len(valid_items) != len(items):
                # Some items were deleted, need to recreate
                total_slices = getattr(self, 'current_total_slices', None)
                self.create_overlay_items(scene, self.current_parser, total_slices=total_slices)
                return
            
            is_right_aligned = bool(alignment & Qt.AlignmentFlag.AlignRight)
            
            if is_right_aligned:
                # Right-aligned: multiple items (one per line)
                # Use cached max width to prevent jitter during cine playback
                # The width is cached when items are created and only changes when items are recreated
                max_text_width_viewport = self.corner_max_width_map.get(corner_key, 0)
                
                # Fallback: if cache is missing (shouldn't happen), recalculate from items
                if max_text_width_viewport == 0:
                    for item in valid_items:
                        if item is not None:
                            item_width = item.boundingRect().width()
                            max_text_width_viewport = max(max_text_width_viewport, item_width)
                    max_text_width_viewport += 5  # Add padding
                    # Cache it for future use
                    if max_text_width_viewport > 0:
                        self.corner_max_width_map[corner_key] = max_text_width_viewport
                
                max_text_width_scene = max_text_width_viewport * viewport_to_scene_scale
                
                # Calculate right edge position
                right_edge_x = x - margin_scene
                left_edge_x = right_edge_x - max_text_width_scene
                
                # Get line height from first item
                if valid_items:
                    line_height_viewport = valid_items[0].boundingRect().height()
                    line_height_scene = line_height_viewport * viewport_to_scene_scale
                    line_spacing = line_height_scene * 0.9
                    
                    # Update positions for each line
                    for line_idx, item in enumerate(valid_items):
                        if item is not None:
                            if alignment & Qt.AlignmentFlag.AlignBottom:
                                text_y = y - (len(valid_items) - line_idx) * line_spacing
                            else:
                                text_y = y + line_idx * line_spacing
                            old_pos = item.pos()
                            
                            # Verify flag before update
                            flags_before = item.flags()
                            has_flag_before = bool(flags_before & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                            
                            # Notify Qt that geometry is changing - required for ItemIgnoresTransformations items
                            item.prepareGeometryChange()
                            
                            # Invalidate old position area before moving
                            old_rect = item.boundingRect().translated(old_pos)
                            scene.invalidate(old_rect)
                            
                            item.setPos(left_edge_x, text_y)
                            
                            # Re-apply flag if needed (shouldn't be necessary, but ensure it's set)
                            if not has_flag_before:
                                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                                # print(f"[DEBUG-OVERLAY] WARNING: {corner_key} item {line_idx} lost ItemIgnoresTransformations flag, re-applied")
                            
                            # Invalidate new position area after moving
                            new_rect = item.boundingRect().translated(item.pos())
                            scene.invalidate(new_rect)
                            
                            # Force item update to ensure Qt refreshes the item
                            item.update()
                            
                            # Verify flag after update
                            flags_after = item.flags()
                            has_flag_after = bool(flags_after & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                            
                            # Verify transform is correct (should be identity for ItemIgnoresTransformations items)
                            item_transform = item.transform()
                            is_identity_transform = item_transform.isIdentity()
                            
                            # Debug: Log position changes for unfocused subwindows (commented out - only for QGraphicsItem approach)
                            # if subwindow_container and not subwindow_container.is_focused and line_idx == 0:
                            #     print(f"[DEBUG-OVERLAY] Updated {corner_key} item {line_idx}: old_pos=({old_pos.x():.1f}, {old_pos.y():.1f}), new_pos=({left_edge_x:.1f}, {text_y:.1f}), flag_before={has_flag_before}, flag_after={has_flag_after}, transform_identity={is_identity_transform}")
            else:
                # Left-aligned: single item (may be multi-line)
                if valid_items:
                    item = valid_items[0]
                    if item is not None:
                        old_pos = item.pos()
                        
                        # Verify flag before update
                        flags_before = item.flags()
                        has_flag_before = bool(flags_before & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                        
                        # Notify Qt that geometry is changing - required for ItemIgnoresTransformations items
                        item.prepareGeometryChange()
                        
                        # Invalidate old position area before moving
                        old_rect = item.boundingRect().translated(old_pos)
                        scene.invalidate(old_rect)
                        
                        item.setPos(x, y)
                        
                        # Adjust y position for bottom alignment
                        if alignment & Qt.AlignmentFlag.AlignBottom:
                            text_height_viewport = item.boundingRect().height()
                            text_height_scene = text_height_viewport * viewport_to_scene_scale
                            # Notify Qt again before second position change
                            item.prepareGeometryChange()
                            # Invalidate intermediate position
                            intermediate_rect = item.boundingRect().translated(item.pos())
                            scene.invalidate(intermediate_rect)
                            item.setPos(item.pos().x(), y - text_height_scene)
                        
                        # Re-apply flag if needed (shouldn't be necessary, but ensure it's set)
                        if not has_flag_before:
                            item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                            # print(f"[DEBUG-OVERLAY] WARNING: {corner_key} item lost ItemIgnoresTransformations flag, re-applied")
                        
                        # Invalidate new position area after moving
                        new_rect = item.boundingRect().translated(item.pos())
                        scene.invalidate(new_rect)
                        
                        # Force item update to ensure Qt refreshes the item
                        item.update()
                        
                        # Verify flag after update
                        flags_after = item.flags()
                        has_flag_after = bool(flags_after & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                        
                        # Verify transform is correct (should be identity for ItemIgnoresTransformations items)
                        item_transform = item.transform()
                        is_identity_transform = item_transform.isIdentity()
                        
                        # Debug: Log position changes for unfocused subwindows (commented out - only for QGraphicsItem approach)
                        # if subwindow_container and not subwindow_container.is_focused:
                        #     new_pos = item.pos()
                        #     print(f"[DEBUG-OVERLAY] Updated {corner_key} item: old_pos=({old_pos.x():.1f}, {old_pos.y():.1f}), new_pos=({new_pos.x():.1f}, {new_pos.y():.1f}), flag_before={has_flag_before}, flag_after={has_flag_after}, transform_identity={is_identity_transform}")
        
        # Force scene invalidation and viewport update after all positions are updated
        # Use QTimer to defer update until after view transform is fully applied
        # This ensures Qt immediately repaints with new positions for ItemIgnoresTransformations items
        # Scene invalidation is needed to clear any cached rendering for these items
        if view is not None:
            # Diagnostic logging: Rendering pipeline (commented out - only for QGraphicsItem approach)
            # if subwindow_container and not subwindow_container.is_focused:
            #     print(f"[DEBUG-DIAG] Scheduling deferred scene invalidation and viewport update")
            
            # Defer update to ensure view transform is fully applied before repainting
            QTimer.singleShot(0, lambda: (
                scene.invalidate(),  # Invalidate entire scene to clear cached rendering
                view.viewport().update()  # Force immediate repaint
            ))

