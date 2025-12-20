"""
Arrow Annotation Tool

This module provides arrow annotation functionality for adding arrows to images.

Inputs:
    - User mouse clicks and drags for arrow placement
    - Arrow styling preferences
    
Outputs:
    - Arrow annotation graphics items with filled arrowheads
    
Requirements:
    - PySide6 for graphics
    - ConfigManager for annotation settings
"""

from PySide6.QtWidgets import QGraphicsItemGroup, QGraphicsLineItem, QGraphicsPathItem, QGraphicsItem, QGraphicsEllipseItem, QGraphicsSceneMouseEvent
from PySide6.QtCore import Qt, QPointF, QLineF, QRectF
from PySide6.QtGui import QPen, QColor, QBrush, QPainterPath
from typing import List, Optional, Tuple, Dict
import math
from utils.config_manager import ConfigManager


class ArrowHeadItem(QGraphicsPathItem):
    """
    Custom QGraphicsPathItem for filled arrowhead.
    """
    
    def __init__(self, start_point: QPointF, end_point: QPointF, color: QColor, size: float = 12.0):
        """
        Initialize arrowhead item.
        
        Args:
            start_point: Start point of arrow line
            end_point: End point of arrow line (where arrowhead points)
            color: Color for arrowhead
            size: Size of arrowhead in pixels
        """
        super().__init__()
        
        self.start_point = start_point
        self.end_point = end_point
        self.arrow_size = size
        self._color = color
        
        # Create filled triangle path
        self._update_path()
        
        # Set styling
        pen = QPen(color, 1)
        brush = QBrush(color)
        self.setPen(pen)
        self.setBrush(brush)
        
        # Set z-value above line
        self.setZValue(161)
    
    def _update_path(self) -> None:
        """Update arrowhead path based on current endpoints."""
        # Calculate angle of line
        dx = self.end_point.x() - self.start_point.x()
        dy = self.end_point.y() - self.start_point.y()
        angle = math.atan2(dy, dx)
        
        # Arrowhead dimensions
        base_width = self.arrow_size * 0.8  # Base width of triangle
        height = self.arrow_size  # Height of triangle
        
        # Create triangle path
        path = QPainterPath()
        
        # Tip of arrow at end_point
        tip = self.end_point
        
        # Calculate perpendicular direction for base
        perp_angle = angle + math.pi / 2
        base_offset_x = math.cos(perp_angle) * (base_width / 2)
        base_offset_y = math.sin(perp_angle) * (base_width / 2)
        
        # Base center point (behind tip)
        base_center_x = tip.x() - math.cos(angle) * height
        base_center_y = tip.y() - math.sin(angle) * height
        
        # Three points of triangle
        point1 = tip  # Tip
        point2 = QPointF(base_center_x + base_offset_x, base_center_y + base_offset_y)  # Base left
        point3 = QPointF(base_center_x - base_offset_x, base_center_y - base_offset_y)  # Base right
        
        # Draw triangle
        path.moveTo(point1)
        path.lineTo(point2)
        path.lineTo(point3)
        path.closeSubpath()
        
        self.setPath(path)
    
    def update_endpoints(self, start_point: QPointF, end_point: QPointF) -> None:
        """
        Update arrowhead position and rotation.
        
        Args:
            start_point: New start point
            end_point: New end point
        """
        self.start_point = start_point
        self.end_point = end_point
        self._update_path()
    
    def set_color(self, color: QColor) -> None:
        """
        Update arrowhead color.
        
        Args:
            color: New color
        """
        self._color = color
        pen = QPen(color, 1)
        brush = QBrush(color)
        self.setPen(pen)
        self.setBrush(brush)


class ArrowAnnotationItem(QGraphicsItemGroup):
    """
    Represents a single arrow annotation.
    
    Contains a line (shaft) and an arrowhead.
    """
    
    def __init__(self, start_point: QPointF, end_point: QPointF,
                 line_item: QGraphicsLineItem, arrowhead_item: ArrowHeadItem,
                 color: QColor):
        """
        Initialize arrow annotation item.
        
        Args:
            start_point: Start point of arrow
            end_point: End point of arrow
            line_item: Graphics line item (shaft)
            arrowhead_item: Arrowhead item
            color: Color for arrow
        """
        super().__init__()
        
        self.start_point = start_point
        self.end_point = end_point
        self.line_item = line_item
        self.arrowhead_item = arrowhead_item
        self.color = color
        self._updating_position = False  # Flag to prevent recursive updates
        self.on_moved_callback = None  # Callback for move tracking
        self.on_mouse_release_callback = None  # Callback for mouse release (to finalize drag)
        self._drag_in_progress = False  # Flag to track if drag is in progress
        
        # Add items to group
        self.addToGroup(line_item)
        self.addToGroup(arrowhead_item)
        
        # Set z-value
        self.setZValue(160)
        
        # Make group selectable and movable
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
    
    def update_endpoints(self, start_point: QPointF, end_point: QPointF) -> None:
        """
        Update arrow endpoints.
        
        Args:
            start_point: New start point (scene coordinates)
            end_point: New end point (scene coordinates)
        """
        self.start_point = start_point
        self.end_point = end_point
        
        # Update group position to start_point
        self.setPos(start_point)
        
        # Update line (relative to group: from (0,0) to (end_point - start_point))
        from PySide6.QtCore import QPointF
        relative_end = end_point - start_point
        line = QLineF(QPointF(0, 0), relative_end)
        self.line_item.setLine(line)
        
        # Update arrowhead (relative to group)
        self.arrowhead_item.update_endpoints(QPointF(0, 0), relative_end)
    
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
            # When group is moved, update start and end points
            if not self._updating_position:
                new_pos = value
                old_pos = self.pos()
                delta = new_pos - old_pos
                
                # Capture positions BEFORE updating (for move tracking)
                # Store COPIES in temporary attributes that the callback can access
                from PySide6.QtCore import QPointF
                self._pre_move_start_point = QPointF(self.start_point)  # Create copy, not reference
                self._pre_move_end_point = QPointF(self.end_point)  # Create copy, not reference
                
                # #region agent log
                with open('/Users/kevingrizzard/Documents/GitHub/DICOMViewerV3/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"arrow_annotation_tool.py:199","message":"ItemPositionChange: BEFORE updating positions","data":{"old_pos":str(old_pos),"new_pos":str(new_pos),"delta":str(delta),"start_point_before":str(self.start_point),"end_point_before":str(self.end_point),"pre_move_start":str(self._pre_move_start_point),"pre_move_end":str(self._pre_move_end_point),"has_callback":self.on_moved_callback is not None},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                # #endregion
                
                # Update start and end points (they track the group's position)
                self.start_point = QPointF(new_pos)  # Group position is start_point
                self.end_point = QPointF(new_pos + (self.end_point - self._pre_move_start_point))  # Maintain relative offset
                
                # #region agent log
                with open('/Users/kevingrizzard/Documents/GitHub/DICOMViewerV3/.cursor/debug.log', 'a') as f:
                    import json
                    f.write(json.dumps({"sessionId":"debug-session","runId":"run1","hypothesisId":"A","location":"arrow_annotation_tool.py:211","message":"ItemPositionChange: AFTER updating positions","data":{"start_point_after":str(self.start_point),"end_point_after":str(self.end_point)},"timestamp":int(__import__('time').time()*1000)}) + '\n')
                # #endregion
                
                # Update line and arrowhead (they're relative to group, so no change needed)
                # Line goes from (0,0) to (end_point - start_point) relative to group
                relative_end = self.end_point - self.start_point
                line = QLineF(QPointF(0, 0), relative_end)
                self.line_item.setLine(line)
                self.arrowhead_item.update_endpoints(QPointF(0, 0), relative_end)
            
            # Return new position
            return value
        elif change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # Call movement callback if set (for undo/redo tracking)
            # Only track moves during active drag (not programmatic updates)
            if self.on_moved_callback and not self._updating_position and self._drag_in_progress:
                try:
                    self.on_moved_callback(self)
                except Exception:
                    pass
        
        return super().itemChange(change, value)
    
    def mousePressEvent(self, event) -> None:
        """
        Handle mouse press to start drag tracking.
        
        Args:
            event: Mouse press event
        """
        # Mark that drag is starting
        self._drag_in_progress = True
        # Capture initial position BEFORE drag starts (for move tracking)
        from PySide6.QtCore import QPointF
        self._pre_drag_start_point = QPointF(self.start_point)
        self._pre_drag_end_point = QPointF(self.end_point)
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event) -> None:
        """
        Handle mouse release to finalize drag.
        
        Args:
            event: Mouse release event
        """
        # Finalize move immediately on mouse release
        if self.on_mouse_release_callback:
            try:
                self.on_mouse_release_callback(self)
            except Exception:
                pass
        
        # Clear drag flag
        self._drag_in_progress = False
        super().mouseReleaseEvent(event)


class ArrowAnnotationTool:
    """
    Manages arrow annotations on images.
    
    Features:
    - Create arrow annotations
    - Delete arrow annotations
    - Per-slice storage
    """
    
    def __init__(self, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the arrow annotation tool.
        
        Args:
            config_manager: Optional ConfigManager for annotation settings
        """
        # Key format: (StudyInstanceUID, SeriesInstanceUID, instance_identifier)
        self.arrows: Dict[Tuple[str, str, int], List[ArrowAnnotationItem]] = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_instance_identifier = 0
        self.drawing = False
        self.start_point: Optional[QPointF] = None
        self.current_end_point: Optional[QPointF] = None
        self.current_arrow_item: Optional[ArrowAnnotationItem] = None
        self.config_manager = config_manager
        self.arrowhead_size = 12.0  # Default arrowhead size
    
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
        if key not in self.arrows:
            self.arrows[key] = []
    
    def start_arrow(self, pos: QPointF) -> None:
        """
        Start drawing a new arrow.
        
        Args:
            pos: Starting position
        """
        self.drawing = True
        self.start_point = pos
        self.current_end_point = pos
    
    def update_arrow(self, pos: QPointF, scene) -> None:
        """
        Update arrow while drawing (preview).
        
        Args:
            pos: Current mouse position
            scene: QGraphicsScene to add items to
        """
        if not self.drawing or self.start_point is None:
            return
        
        self.current_end_point = pos
        
        # Remove old preview item
        if self.current_arrow_item is not None:
            if self.current_arrow_item.scene() == scene:
                scene.removeItem(self.current_arrow_item)
        
        # Create preview arrow
        self.current_arrow_item = self._create_arrow_item(self.start_point, pos)
        
        # Add to scene
        if self.current_arrow_item.scene() != scene:
            scene.addItem(self.current_arrow_item)
    
    def _create_arrow_item(self, start_point: QPointF, end_point: QPointF) -> ArrowAnnotationItem:
        """
        Create an arrow item from start and end points.
        
        Args:
            start_point: Start point
            end_point: End point
            
        Returns:
            ArrowAnnotationItem
        """
        # Get pen settings from config
        pen_width = 2  # Default
        pen_color = (255, 255, 0)  # Default yellow
        if self.config_manager:
            pen_width = self.config_manager.get_measurement_line_thickness()  # Use measurement line thickness for now
            pen_color = self.config_manager.get_arrow_annotation_color()  # Use arrow-specific color
        
        color = QColor(*pen_color)
        
        # Create line item - position relative to group (group will be at start_point)
        # Line goes from (0, 0) relative to group to (end_point - start_point)
        from PySide6.QtCore import QPointF
        relative_end = end_point - start_point
        line = QLineF(QPointF(0, 0), relative_end)
        line_item = QGraphicsLineItem(line)
        pen = QPen(color, pen_width)
        pen.setCosmetic(True)  # Makes pen width viewport-relative
        line_item.setPen(pen)
        line_item.setZValue(160)
        
        # Create arrowhead - also relative to group
        arrowhead = ArrowHeadItem(QPointF(0, 0), relative_end, color, self.arrowhead_size)
        
        # Create arrow group
        arrow_item = ArrowAnnotationItem(start_point, end_point, line_item, arrowhead, color)
        
        # Set group position to start_point so line and arrowhead are positioned correctly
        arrow_item.setPos(start_point)
        
        return arrow_item
    
    def finish_arrow(self, scene) -> Optional[ArrowAnnotationItem]:
        """
        Finish current arrow.
        
        Args:
            scene: QGraphicsScene to add arrow to
        
        Returns:
            Created arrow item or None
        """
        if not self.drawing or self.start_point is None or self.current_end_point is None:
            return None
        
        if self.current_arrow_item is None:
            return None
        
        # Check if arrow has minimum length (at least a few pixels)
        dx = self.current_end_point.x() - self.start_point.x()
        dy = self.current_end_point.y() - self.start_point.y()
        length = math.sqrt(dx * dx + dy * dy)
        
        if length < 5.0:  # Minimum arrow length
            # Cancel arrow if too short
            if self.current_arrow_item.scene() == scene:
                scene.removeItem(self.current_arrow_item)
            self.current_arrow_item = None
            self.drawing = False
            self.start_point = None
            self.current_end_point = None
            return None
        
        # Store arrow
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        if key not in self.arrows:
            self.arrows[key] = []
        self.arrows[key].append(self.current_arrow_item)
        
        item = self.current_arrow_item
        self.current_arrow_item = None
        self.drawing = False
        self.start_point = None
        self.current_end_point = None
        
        return item
    
    def cancel_arrow(self, scene) -> None:
        """
        Cancel current arrow.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        if self.current_arrow_item is not None:
            if self.current_arrow_item.scene() == scene:
                scene.removeItem(self.current_arrow_item)
            self.current_arrow_item = None
        
        self.drawing = False
        self.start_point = None
        self.current_end_point = None
    
    def delete_arrow(self, item: ArrowAnnotationItem, scene) -> None:
        """
        Delete an arrow annotation.
        
        Args:
            item: ArrowAnnotationItem to delete
            scene: QGraphicsScene to remove item from
        """
        # Remove from scene
        if item.scene() == scene:
            scene.removeItem(item)
        
        # Remove from storage
        for key, arrow_list in list(self.arrows.items()):
            if item in arrow_list:
                arrow_list.remove(item)
                # If list is empty, remove the key
                if not arrow_list:
                    del self.arrows[key]
                break
    
    def get_arrows_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> List[ArrowAnnotationItem]:
        """
        Get all arrows for a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            
        Returns:
            List of arrow items
        """
        key = (study_uid, series_uid, instance_identifier)
        return self.arrows.get(key, [])
    
    def clear_arrows_from_other_slices(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Clear arrows from other slices (not the current one) from the scene.
        
        Args:
            study_uid: StudyInstanceUID of current slice
            series_uid: SeriesInstanceUID of current slice
            instance_identifier: InstanceNumber of current slice
            scene: QGraphicsScene to remove items from
        """
        current_key = (study_uid, series_uid, instance_identifier)
        
        # Get all arrows currently in the scene
        scene_items = list(scene.items())
        for item in scene_items:
            # Check if this is an arrow annotation item
            if isinstance(item, ArrowAnnotationItem):
                # Check if this arrow belongs to a different slice
                belongs_to_current = False
                for key, arrow_list in self.arrows.items():
                    if item in arrow_list:
                        if key == current_key:
                            belongs_to_current = True
                        break
                
                # Remove from scene if it doesn't belong to current slice
                if not belongs_to_current and item.scene() == scene:
                    scene.removeItem(item)
    
    def display_arrows_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Display arrows for a slice.
        
        Ensures all arrows for the current slice are visible in the scene.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            scene: QGraphicsScene to add items to
        """
        key = (study_uid, series_uid, instance_identifier)
        arrows = self.arrows.get(key, [])
        
        for arrow in arrows:
            # Add arrow if not already in scene
            if arrow.scene() != scene:
                scene.addItem(arrow)
                arrow.setZValue(160)
            
            # Ensure arrow is visible
            arrow.show()
    
    def clear_slice_arrows(self, study_uid: str, series_uid: str, instance_identifier: int, scene) -> None:
        """
        Clear all arrows from a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            scene: QGraphicsScene to remove items from
        """
        key = (study_uid, series_uid, instance_identifier)
        if key in self.arrows:
            for arrow in self.arrows[key]:
                # Only remove if item actually belongs to this scene
                if arrow.scene() == scene:
                    scene.removeItem(arrow)
            del self.arrows[key]
    
    def clear_arrows(self, scene) -> None:
        """
        Clear all arrows from all slices.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        for arrow_list in self.arrows.values():
            for arrow in arrow_list:
                # Only remove if item actually belongs to this scene
                if arrow.scene() == scene:
                    scene.removeItem(arrow)
        self.arrows.clear()
    
    def update_all_arrow_styles(self, config_manager: ConfigManager) -> None:
        """
        Update styles (line thickness, color) for all existing arrows.
        
        Args:
            config_manager: ConfigManager instance to get current settings
        """
        if config_manager is None:
            return
        
        # Get new settings from config (arrow-specific color, measurement line thickness for now)
        pen_width = config_manager.get_measurement_line_thickness()  # Use measurement line thickness for now
        pen_color = config_manager.get_arrow_annotation_color()  # Use arrow-specific color
        
        color = QColor(*pen_color)
        pen = QPen(color, pen_width)
        pen.setCosmetic(True)
        
        # Update all arrows
        for key, arrow_list in self.arrows.items():
            for arrow in arrow_list:
                # Update line pen
                arrow.line_item.setPen(pen)
                
                # Update arrowhead color
                arrow.arrowhead_item.set_color(color)
                arrow.color = color
