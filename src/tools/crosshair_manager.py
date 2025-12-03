"""
Crosshair Manager

This module manages crosshair annotations that display pixel values and coordinates
at clicked points on DICOM images.

Inputs:
    - Click positions
    - Pixel values and coordinates
    
Outputs:
    - Crosshair graphics items with annotations
    
Requirements:
    - PySide6 for graphics components
    - ConfigManager for annotation settings
"""

from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsLineItem, QGraphicsTextItem, QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPen, QColor, QFont, QPainter, QTransform
from typing import Optional, Dict, List, Tuple, Callable
from utils.config_manager import ConfigManager


class DraggableCrosshairText(QGraphicsTextItem):
    """
    Custom QGraphicsTextItem for crosshair text that can be dragged independently.
    Similar to DraggableStatisticsOverlay for ROI statistics.
    """
    
    def __init__(self, crosshair_item: 'CrosshairItem', offset_update_callback: Callable[[float, float], None]):
        """
        Initialize draggable crosshair text.
        
        Args:
            crosshair_item: CrosshairItem this text belongs to
            offset_update_callback: Callback to update offset when text is moved
        """
        super().__init__()
        self.crosshair_item = crosshair_item
        self.offset_update_callback = offset_update_callback
        self._updating_position = False
        self._is_deleted = False
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """Handle item changes, particularly position changes."""
        if self._is_deleted:
            return super().itemChange(change, value)
        
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and not self._updating_position:
            try:
                if self.crosshair_item is None or self.scene() is None:
                    return super().itemChange(change, value)
                
                view = self.scene().views()[0] if self.scene().views() else None
                if view is not None:
                    crosshair_pos = self.crosshair_item.pos()
                    text_pos = self.pos()
                    
                    # Convert scene coordinates to viewport pixels
                    view_scale = view.transform().m11()
                    scene_to_viewport_scale = view_scale if view_scale > 0 else 1.0
                    
                    # Calculate offset from crosshair position in viewport pixels
                    offset_x = (text_pos.x() - crosshair_pos.x()) * scene_to_viewport_scale
                    offset_y = (text_pos.y() - crosshair_pos.y()) * scene_to_viewport_scale
                    
                    # Update stored offset
                    if self.offset_update_callback:
                        self.offset_update_callback(offset_x, offset_y)
            except Exception:
                pass
        
        return super().itemChange(change, value)
    
    def mark_deleted(self) -> None:
        """Mark text as deleted to short-circuit event handling."""
        self._is_deleted = True


class CrosshairItem(QGraphicsItemGroup):
    """
    Represents a single crosshair annotation with pixel value and coordinates.
    
    Features:
    - Crosshair lines (horizontal and vertical)
    - Text label showing pixel value and coordinates
    - Styling from config manager
    """
    
    def __init__(
        self,
        pos: QPointF,
        pixel_value_str: str,
        x: int,
        y: int,
        z: int,
        config_manager: Optional[ConfigManager] = None,
        privacy_mode: bool = False
    ):
        """
        Initialize crosshair item.
        
        Args:
            pos: Position in scene coordinates
            pixel_value_str: Formatted pixel value string
            x: X coordinate (column)
            y: Y coordinate (row)
            z: Z coordinate (slice index)
            config_manager: Optional ConfigManager for annotation settings
            privacy_mode: Whether privacy mode is enabled (hides pixel values)
        """
        super().__init__()
        
        self.position = pos
        self.pixel_value_str = pixel_value_str
        self.x_coord = x
        self.y_coord = y
        self.z_coord = z
        self.config_manager = config_manager
        self.privacy_mode = privacy_mode
        
        # Get ROI settings from config (for consistency with ROI annotations)
        if config_manager:
            line_thickness = config_manager.get_roi_line_thickness()
            line_color = config_manager.get_roi_line_color()
            font_size = config_manager.get_roi_font_size()
            font_color = config_manager.get_roi_font_color()
        else:
            line_thickness = 2
            line_color = (255, 0, 0)  # Red (default ROI color)
            font_size = 14
            font_color = (255, 255, 0)  # Yellow (default ROI font color)
        
        # Crosshair size is 3x line thickness in viewport pixels
        # Since we use cosmetic pen, we work in viewport pixels
        line_length_viewport = 3 * line_thickness
        
        # Create crosshair lines with cosmetic pen (fixed size in viewport)
        line_pen = QPen(QColor(*line_color), line_thickness)
        line_pen.setCosmetic(True)  # Makes pen width viewport-relative (independent of zoom)
        
        # Horizontal line - use viewport-relative size
        # Set ItemIgnoresTransformations to make line length viewport-relative (not affected by zoom)
        h_line = QGraphicsLineItem(-line_length_viewport, 0, line_length_viewport, 0)
        h_line.setPen(line_pen)
        h_line.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.addToGroup(h_line)
        
        # Vertical line - use viewport-relative size
        # Set ItemIgnoresTransformations to make line length viewport-relative (not affected by zoom)
        v_line = QGraphicsLineItem(0, -line_length_viewport, 0, line_length_viewport)
        v_line.setPen(line_pen)
        v_line.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.addToGroup(v_line)
        
        # Create text label (draggable, independent of crosshair)
        if privacy_mode:
            text = f"({x}, {y}, {z})"
        else:
            text = f"Pixel Value: {pixel_value_str}\n({x}, {y}, {z})"
        
        # Create draggable text item (not added to group - independent item)
        def update_offset(offset_x: float, offset_y: float) -> None:
            """Update text offset when dragged."""
            self.text_offset_viewport = (offset_x, offset_y)
        
        text_item = DraggableCrosshairText(self, update_offset)
        text_item.setDefaultTextColor(QColor(*font_color))
        
        # Set font - use absolute pixel size
        if font_size < 6:
            font = QFont("Arial", 6)
            scale_factor = font_size / 6.0
            transform = QTransform()
            transform.scale(scale_factor, scale_factor)
            text_item.setTransform(transform)
        else:
            font = QFont("Arial", font_size)
        
        font.setBold(True)
        text_item.setFont(font)
        text_item.setPlainText(text)
        
        # Set flag to ignore parent transformations (keeps font size consistent in viewport)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        # Make text draggable
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        
        # Store text item and initial offset
        self.text_item = text_item
        self.text_offset_viewport = (5.0, 5.0)  # Initial offset in viewport pixels (to right and down)
        
        # Callback for when crosshair is moved
        self.on_moved_callback: Optional[Callable[[], None]] = None
        self._move_start_position: Optional[QPointF] = None
        
        # Position the group at the click location
        self.setPos(pos)
        
        # Set z-value above image and ROIs, below overlay
        self.setZValue(160)
        text_item.setZValue(161)  # Text above crosshair lines
        
        # Make crosshair selectable and movable
        self.setFlag(QGraphicsItemGroup.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItemGroup.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItemGroup.GraphicsItemFlag.ItemSendsGeometryChanges, True)
    
    def update_text_position(self, view) -> None:
        """
        Update text position based on stored offset.
        Should be called when view transform changes.
        
        Args:
            view: QGraphicsView to get transform from
        """
        if self.text_item is None or view is None:
            return
        
        # Convert viewport offset to scene coordinates
        view_scale = view.transform().m11()
        scene_to_viewport_scale = view_scale if view_scale > 0 else 1.0
        viewport_to_scene_scale = 1.0 / scene_to_viewport_scale if scene_to_viewport_scale > 0 else 1.0
        
        offset_x_scene = self.text_offset_viewport[0] * viewport_to_scene_scale
        offset_y_scene = self.text_offset_viewport[1] * viewport_to_scene_scale
        
        # Position text relative to crosshair
        text_pos = self.pos() + QPointF(offset_x_scene, offset_y_scene)
        self.text_item.setPos(text_pos)
    
    def update_privacy_mode(self, privacy_mode: bool) -> None:
        """
        Update privacy mode and refresh text.
        
        Args:
            privacy_mode: New privacy mode state
        """
        if self.privacy_mode == privacy_mode:
            return
        
        self.privacy_mode = privacy_mode
        
        # Update text content
        if self.text_item is not None:
            if privacy_mode:
                text = f"({self.x_coord}, {self.y_coord}, {self.z_coord})"
            else:
                text = f"{self.pixel_value_str}\n({self.x_coord}, {self.y_coord}, {self.z_coord})"
            self.text_item.setPlainText(text)
    
    def update_pixel_values(self, pixel_value_str: str, x: int, y: int, z: int) -> None:
        """
        Update pixel values and coordinates for the crosshair.
        
        Args:
            pixel_value_str: Formatted pixel value string (may include patient coordinates)
            x: X coordinate (column)
            y: Y coordinate (row)
            z: Z coordinate (slice index)
        """
        self.pixel_value_str = pixel_value_str
        self.x_coord = x
        self.y_coord = y
        self.z_coord = z
        
        # Update text display based on privacy mode
        if self.text_item is not None:
            if self.privacy_mode:
                text = f"({x}, {y}, {z})"
            else:
                text = f"Pixel Value: {pixel_value_str}\n({x}, {y}, {z})"
            self.text_item.setPlainText(text)
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """
        Handle item changes, particularly position changes.
        
        Args:
            change: Type of change
            value: New value
            
        Returns:
            Modified value
        """
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Store initial position on first movement if not already set
            if self._move_start_position is None:
                self._move_start_position = self.pos()
            
            # Call movement callback if set
            if self.on_moved_callback:
                try:
                    self.on_moved_callback()
                except Exception:
                    pass
        
        return super().itemChange(change, value)


class CrosshairManager:
    """
    Manages crosshair annotations on images.
    
    Features:
    - Store crosshairs per slice
    - Create crosshair annotations
    - Delete crosshairs
    - Clear crosshairs for slice
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the crosshair manager.
        
        Args:
            config_manager: Optional ConfigManager for annotation settings
        """
        # Key format: (StudyInstanceUID, SeriesInstanceUID, instance_identifier)
        self.crosshairs: Dict[Tuple[str, str, int], List[CrosshairItem]] = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_instance_identifier = 0
        self.config_manager = config_manager
        self.privacy_mode: bool = False
    
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
        if key not in self.crosshairs:
            self.crosshairs[key] = []
    
    def set_privacy_mode(self, privacy_mode: bool) -> None:
        """
        Set privacy mode and update all crosshairs.
        
        Args:
            privacy_mode: Whether privacy mode is enabled
        """
        if self.privacy_mode == privacy_mode:
            return
        
        self.privacy_mode = privacy_mode
        
        # Update all crosshairs
        for crosshair_list in self.crosshairs.values():
            for crosshair in crosshair_list:
                crosshair.update_privacy_mode(privacy_mode)
    
    def create_crosshair(
        self,
        pos: QPointF,
        pixel_value_str: str,
        x: int,
        y: int,
        z: int,
        scene
    ) -> CrosshairItem:
        """
        Create a new crosshair annotation.
        
        Args:
            pos: Position in scene coordinates
            pixel_value_str: Formatted pixel value string
            x: X coordinate (column)
            y: Y coordinate (row)
            z: Z coordinate (slice index)
            scene: QGraphicsScene to add item to
            
        Returns:
            Created CrosshairItem
        """
        crosshair = CrosshairItem(
            pos,
            pixel_value_str,
            x,
            y,
            z,
            self.config_manager,
            self.privacy_mode
        )
        
        # Add crosshair group to scene
        scene.addItem(crosshair)
        
        # Add text item separately to scene (not as child of group)
        if crosshair.text_item is not None:
            text_scene = crosshair.text_item.scene()
            if text_scene is not None:
                print(f"[DEBUG-CROSSHAIR] Warning: Text item already in scene {text_scene} before adding to {scene}")
                # Don't add if already in this scene
                if text_scene == scene:
                    print(f"[DEBUG-CROSSHAIR] Text item already in correct scene, skipping add")
                else:
                    # Remove from old scene first
                    text_scene.removeItem(crosshair.text_item)
                    scene.addItem(crosshair.text_item)
                    print(f"[DEBUG-CROSSHAIR] Moved text item from {text_scene} to {scene}")
            else:
                scene.addItem(crosshair.text_item)
                print(f"[DEBUG-CROSSHAIR] Added text item to scene. Text item scene: {crosshair.text_item.scene()}, Crosshair scene: {crosshair.scene()}")
            # Position text initially
            view = scene.views()[0] if scene.views() else None
            if view is not None:
                crosshair.update_text_position(view)
        
        # Store in per-slice dictionary
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        if key not in self.crosshairs:
            self.crosshairs[key] = []
        self.crosshairs[key].append(crosshair)
        
        return crosshair
    
    def delete_crosshair(self, crosshair_item: CrosshairItem, scene) -> None:
        """
        Delete a crosshair annotation.
        
        Args:
            crosshair_item: CrosshairItem to delete
            scene: QGraphicsScene to remove item from
        """
        # Remove text item from scene
        if crosshair_item.text_item is not None:
            text_scene = crosshair_item.text_item.scene()
            print(f"[DEBUG-CROSSHAIR] Deleting text item from scene: {text_scene}")
            if hasattr(crosshair_item.text_item, 'mark_deleted'):
                crosshair_item.text_item.mark_deleted()
            scene.removeItem(crosshair_item.text_item)
            print(f"[DEBUG-CROSSHAIR] Text item removed. Text item scene after removal: {crosshair_item.text_item.scene()}")
        
        # Remove crosshair from scene
        scene.removeItem(crosshair_item)
        
        # Remove from storage
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        if key in self.crosshairs:
            if crosshair_item in self.crosshairs[key]:
                self.crosshairs[key].remove(crosshair_item)
    
    def clear_crosshairs_for_slice(self, scene) -> None:
        """
        Clear all crosshairs for the current slice.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        if key in self.crosshairs:
            for crosshair in self.crosshairs[key]:
                # Remove text item
                if crosshair.text_item is not None:
                    if hasattr(crosshair.text_item, 'mark_deleted'):
                        crosshair.text_item.mark_deleted()
                    scene.removeItem(crosshair.text_item)
                # Remove crosshair
                scene.removeItem(crosshair)
            self.crosshairs[key].clear()
    
    def get_crosshairs_for_slice(self) -> List[CrosshairItem]:
        """
        Get all crosshairs for the current slice.
        
        Returns:
            List of CrosshairItem objects
        """
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        return self.crosshairs.get(key, [])
    
    def display_crosshairs_for_slice(self, scene) -> None:
        """
        Display all crosshairs for the current slice.
        
        This method ensures crosshairs are visible in the scene when switching slices.
        Crosshairs from other slices are hidden.
        
        Args:
            scene: QGraphicsScene to add items to
        """
        current_key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        
        # First, hide all crosshairs from all slices
        # Use list() to create a copy since we may modify the dictionary during iteration
        keys_to_clean = []
        for key, crosshair_list in list(self.crosshairs.items()):
            # Create a copy of the list since we may modify it during iteration
            crosshairs_to_remove = []
            for crosshair in crosshair_list:
                try:
                    # Check if crosshair's C++ object is still valid
                    crosshair_scene = crosshair.scene()
                    if crosshair_scene == scene:
                        crosshair.setVisible(False)
                    # Hide text item if it exists and is valid
                    if crosshair.text_item is not None:
                        try:
                            if crosshair.text_item.scene() == scene:
                                crosshair.text_item.setVisible(False)
                        except RuntimeError:
                            # Text item's C++ object was deleted, mark for removal
                            crosshair.text_item = None
                except RuntimeError:
                    # Crosshair's C++ object was deleted (e.g., scene was cleared)
                    # Mark this crosshair for removal from the list
                    crosshairs_to_remove.append(crosshair)
            
            # Remove deleted crosshairs from the list
            for crosshair in crosshairs_to_remove:
                crosshair_list.remove(crosshair)
            
            # If the list is now empty, mark the key for removal
            if not crosshair_list:
                keys_to_clean.append(key)
        
        # Remove empty keys from the dictionary
        for key in keys_to_clean:
            del self.crosshairs[key]
        
        # Then, show only crosshairs for the current slice
        if current_key in self.crosshairs:
            view = scene.views()[0] if scene.views() else None
            # Create a copy of the list since we may modify it during iteration
            crosshairs_to_remove = []
            for crosshair in self.crosshairs[current_key]:
                try:
                    # Ensure crosshair is in scene
                    crosshair_scene = crosshair.scene()
                    if crosshair_scene != scene:
                        scene.addItem(crosshair)
                    # Show crosshair
                    crosshair.setVisible(True)
                    
                    # Ensure text item is also in scene and positioned correctly
                    if crosshair.text_item is not None:
                        try:
                            text_scene = crosshair.text_item.scene()
                            if text_scene is None:
                                scene.addItem(crosshair.text_item)
                            elif text_scene != scene:
                                # Remove from old scene first
                                old_scene = crosshair.text_item.scene()
                                old_scene.removeItem(crosshair.text_item)
                                scene.addItem(crosshair.text_item)
                            # Show text item
                            crosshair.text_item.setVisible(True)
                            # Update text position based on current view transform
                            if view is not None:
                                crosshair.update_text_position(view)
                        except RuntimeError:
                            # Text item's C++ object was deleted, mark for removal
                            crosshair.text_item = None
                except RuntimeError:
                    # Crosshair's C++ object was deleted, mark for removal
                    crosshairs_to_remove.append(crosshair)
            
            # Remove deleted crosshairs from the list
            for crosshair in crosshairs_to_remove:
                self.crosshairs[current_key].remove(crosshair)
            
            # Remove the key if the list is now empty
            if not self.crosshairs[current_key]:
                del self.crosshairs[current_key]

