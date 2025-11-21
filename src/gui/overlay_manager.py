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
from core.multiframe_handler import is_multiframe, get_frame_count


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
        self.visibility_state = 0  # 0=show all, 1=hide corner text, 2=hide all text
        self.custom_fields: List[str] = []
        self.overlay_items: List[QGraphicsTextItem] = []
        self.font_size = font_size
        self.font_color = font_color
        self.config_manager = config_manager
        
        # Store current parser and scene for updating positions
        self.current_parser: Optional[DICOMParser] = None
        self.current_scene = None
        
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
        
        # Clear existing items and corner mapping
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
    
    def clear_overlay_items(self, scene) -> None:
        """
        Clear overlay items from scene.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
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
        
        Args:
            scene: QGraphicsScene containing overlay items
        """
        if not self.overlay_items or self.current_parser is None:
            return
        
        # Get view for coordinate conversion
        view = scene.views()[0] if scene.views() else None
        if view is None:
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
        
        # Add detailed debug logging
        view_type = type(view).__name__
        parent_type = type(view.parent()).__name__ if view.parent() else "None"
        found_container = subwindow_container is not None
        is_focused = subwindow_container.is_focused if subwindow_container else None
        
        print(f"[DEBUG-OVERLAY] update_overlay_positions: view={view_type}, parent={parent_type}, "
              f"found_container={found_container}, is_focused={is_focused}")
        
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
            if not items:
                continue
            
            # Check if items are still valid (not deleted)
            valid_items = [item for item in items if item is not None and item.scene() == scene]
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
                            item.setPos(left_edge_x, text_y)
            else:
                # Left-aligned: single item (may be multi-line)
                if valid_items:
                    item = valid_items[0]
                    if item is not None:
                        item.setPos(x, y)
                        
                        # Adjust y position for bottom alignment
                        if alignment & Qt.AlignmentFlag.AlignBottom:
                            text_height_viewport = item.boundingRect().height()
                            text_height_scene = text_height_viewport * viewport_to_scene_scale
                            item.setPos(item.pos().x(), y - text_height_scene)

