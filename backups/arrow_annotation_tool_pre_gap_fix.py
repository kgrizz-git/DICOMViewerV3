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
from utils.debug_log import debug_log

# Arrowhead is drawn larger than line thickness so it stays visually balanced
ARROWHEAD_SIZE_MULTIPLIER = 3.5


class ArrowHeadItem(QGraphicsPathItem):
    """
    Custom QGraphicsPathItem for filled arrowhead.
    Uses ItemIgnoresTransformations so size stays fixed in viewport (matches cosmetic line).
    Path is in item coordinates (1 unit = 1 viewport pixel); tip at (0,0), triangle along +x.
    """
    
    def __init__(self, start_point: QPointF, end_point: QPointF, color: QColor, size: float = 12.0):
        """
        Initialize arrowhead item.
        
        Args:
            start_point: Start point of arrow line (group coords)
            end_point: End point of arrow line / tip (group coords)
            color: Color for arrowhead
            size: Size of arrowhead in viewport pixels
        """
        super().__init__()
        
        self.start_point = start_point
        self.end_point = end_point
        self.arrow_size = size
        self._color = color
        
        # Viewport-relative: same apparent size at any zoom (matches cosmetic line)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        
        # Path in item coords: tip at (0,0), triangle along +x (1 unit = 1 viewport pixel)
        self._update_path()
        
        # Position so tip (0,0) is at end_point in group coords; rotate so +x points along arrow
        self._update_position_and_rotation()
        
        # Cosmetic pen so outline doesn't scale
        pen = QPen(color, 1)
        pen.setCosmetic(True)
        brush = QBrush(color)
        self.setPen(pen)
        self.setBrush(brush)
        
        self.setZValue(161)
    
    def _update_path(self) -> None:
        """Build triangle path in item coords: tip (0,0), base at (-arrow_size, 0), width arrow_size*0.8."""
        path = QPainterPath()
        tip = QPointF(0, 0)
        height = self.arrow_size
        half_base = self.arrow_size * 0.4  # 0.8/2
        path.moveTo(tip)
        path.lineTo(-height, half_base)
        path.lineTo(-height, -half_base)
        path.closeSubpath()
        self.setPath(path)
    
    def _update_position_and_rotation(self) -> None:
        """Set position to tip (end_point) and rotation so triangle points along arrow direction."""
        dx = self.end_point.x() - self.start_point.x()
        dy = self.end_point.y() - self.start_point.y()
        angle_rad = math.atan2(dy, dx)
        self.setPos(self.end_point)
        self.setRotation(math.degrees(angle_rad))
    
    def update_endpoints(self, start_point: QPointF, end_point: QPointF) -> None:
        """
        Update arrowhead position and rotation when arrow endpoints change.
        """
        self.start_point = start_point
        self.end_point = end_point
        self._update_path()
        self._update_position_and_rotation()
    
    def set_color(self, color: QColor) -> None:
        """
        Update arrowhead color.
        """
        self._color = color
        pen = QPen(color, 1)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setBrush(QBrush(color))


def _line_end_shortened(relative_end: QPointF, fraction: float = 0.02) -> QPointF:
    """
    Return point slightly before relative_end so the line does not stick out past the arrowhead.
    Uses a fraction of arrow length (and minimum pullback) so the gap is invisible under the head.
    """
    dx = relative_end.x()
    dy = relative_end.y()
    length = math.sqrt(dx * dx + dy * dy)
    if length <= 1e-6:
        return QPointF(0, 0)
    pullback = max(2.0, length * fraction)
    if pullback >= length:
        return QPointF(0, 0)
    unit_x = dx / length
    unit_y = dy / length
    return QPointF(dx - unit_x * pullback, dy - unit_y * pullback)


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
        
        # Update line (shortened so it does not stick out) and arrowhead position/rotation
        from PySide6.QtCore import QPointF
        relative_end = end_point - start_point
        line_end = _line_end_shortened(relative_end)
        self.line_item.setLine(QLineF(QPointF(0, 0), line_end))
        self.arrowhead_item.update_endpoints(QPointF(0, 0), relative_end)
    
    def update_line_end_for_view_scale(self, scale: Optional[float] = None) -> None:
        """
        Set line end using view scale so the line meets the arrowhead base at any zoom.
        pullback in scene units = arrowhead_size_viewport / scale so gap is eliminated.
        If scale is not provided or invalid, uses the scale from the view displaying this item's scene.
        """
        from PySide6.QtCore import QPointF
        if scale is None or scale <= 0:
            # Use scale from the view that is actually displaying this arrow
            sc = self.scene()
            if sc is not None and hasattr(sc, 'views'):
                views = sc.views()
                if views:
                    v = views[0]
                    if hasattr(v, 'viewportTransform'):
                        t = v.viewportTransform()
                        if t:
                            scale = t.m11()
                    if (scale is None or scale <= 0) and hasattr(v, 'transform'):
                        t = v.transform()
                        if t:
                            scale = t.m11()
            if scale is None or scale <= 0:
                return
        relative_end = self.end_point - self.start_point
        dx = relative_end.x()
        dy = relative_end.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length <= 1e-6:
            return
        arrowhead_size = getattr(self.arrowhead_item, 'arrow_size', 12.0)
        pullback = arrowhead_size / scale
        pullback = min(pullback, length * 0.99)
        if pullback <= 0:
            return
        unit_x = dx / length
        unit_y = dy / length
        line_end = QPointF(dx - unit_x * pullback, dy - unit_y * pullback)
        self.line_item.setLine(QLineF(QPointF(0, 0), line_end))
    
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
                debug_log("arrow_annotation_tool.py:199", "ItemPositionChange: BEFORE updating positions", {"old_pos": str(old_pos), "new_pos": str(new_pos), "delta": str(delta), "start_point_before": str(self.start_point), "end_point_before": str(self.end_point), "pre_move_start": str(self._pre_move_start_point), "pre_move_end": str(self._pre_move_end_point), "has_callback": self.on_moved_callback is not None}, hypothesis_id="A")

                # Update start and end points (they track the group's position)
                self.start_point = QPointF(new_pos)  # Group position is start_point
                self.end_point = QPointF(new_pos + (self.end_point - self._pre_move_start_point))  # Maintain relative offset
                debug_log("arrow_annotation_tool.py:211", "ItemPositionChange: AFTER updating positions", {"start_point_after": str(self.start_point), "end_point_after": str(self.end_point)}, hypothesis_id="A")

                # Update line (shortened) and arrowhead position/rotation
                relative_end = self.end_point - self.start_point
                line_end = _line_end_shortened(relative_end)
                self.line_item.setLine(QLineF(QPointF(0, 0), line_end))
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
        # Get arrow size (line thickness) and color from config; arrowhead drawn larger for balance
        size = self.config_manager.get_arrow_annotation_size() if self.config_manager else 6
        arrowhead_size = size * ARROWHEAD_SIZE_MULTIPLIER
        pen_color = self.config_manager.get_arrow_annotation_color() if self.config_manager else (255, 255, 0)
        color = QColor(*pen_color)
        
        # Create line item - end slightly before tip so line does not stick out past arrowhead
        from PySide6.QtCore import QPointF
        relative_end = end_point - start_point
        line_end = _line_end_shortened(relative_end)
        line = QLineF(QPointF(0, 0), line_end)
        line_item = QGraphicsLineItem(line)
        pen = QPen(color, size)
        pen.setCosmetic(True)  # Makes pen width viewport-relative
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)  # Line ends at tip, does not extend past arrowhead
        line_item.setPen(pen)
        line_item.setZValue(160)
        
        # Create arrowhead - also relative to group (larger than line for visual balance)
        arrowhead = ArrowHeadItem(QPointF(0, 0), relative_end, color, arrowhead_size)
        
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
        Update styles (line thickness, arrowhead size, color) for all existing arrows.
        
        Args:
            config_manager: ConfigManager instance to get current settings
        """
        if config_manager is None:
            return
        
        arrow_size = config_manager.get_arrow_annotation_size()
        arrowhead_size = arrow_size * ARROWHEAD_SIZE_MULTIPLIER
        pen_color = config_manager.get_arrow_annotation_color()
        color = QColor(*pen_color)
        pen = QPen(color, arrow_size)
        pen.setCosmetic(True)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        
        for key, arrow_list in self.arrows.items():
            for arrow in arrow_list:
                arrow.line_item.setPen(pen)
                arrow.arrowhead_item.set_color(color)
                arrow.color = color
                relative_end = arrow.end_point - arrow.start_point
                line_end = _line_end_shortened(relative_end)
                arrow.line_item.setLine(QLineF(QPointF(0, 0), line_end))
                arrow.arrowhead_item.arrow_size = arrowhead_size
                arrow.arrowhead_item.update_endpoints(QPointF(0, 0), relative_end)
