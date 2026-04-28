"""
ROI Manager

This module handles drawing and management of Regions of Interest (ROIs)
including elliptical and rectangular shapes, with statistics calculation.

Inputs:
    - User mouse interactions for drawing
    - ROI shape type (ellipse, rectangle)
    - Pixel array data for statistics
    
Outputs:
    - ROI graphics items
    - ROI statistics (mean, std dev, etc.)
    
Requirements:
    - PySide6 for graphics items
    - numpy for statistics calculations

Clipboard-oriented JSON dicts for copy/paste are built in ``tools.roi_persistence``
(Phase 5B); ``utils.annotation_clipboard`` imports that module.
"""

import logging
import math

from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsItem,
                               QGraphicsTextItem, QGraphicsSceneMouseEvent, QGraphicsScene)
from PySide6.QtCore import Qt, QRectF, QPointF
from shiboken6 import isValid
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QTransform,
)
from typing import List, Optional, Tuple, Dict, Set, Callable
import numpy as np
from pydicom.dataset import Dataset

from core.dicom_color import multichannel_axis_labels
from utils.bundled_fonts import make_qfont
from utils.config_manager import ConfigManager
from gui.view_transform_helpers import graphics_view_uniform_zoom
from utils.log_sanitizer import sanitized_format_exc

_logger = logging.getLogger(__name__)

# Statistics payloads use int for pixel counts and None for optional area in mm².
RoiStatisticsMap = dict[str, float | int | None]


class ROIGraphicsEllipseItem(QGraphicsEllipseItem):
    """
    Custom QGraphicsEllipseItem that detects position changes for ROI movement.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_moved_callback: Optional[Callable[[], None]] = None
        self._last_callback_pos: Optional[QPointF] = None  # Track last position where callback was triggered
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """Handle item changes, particularly position changes."""
        # For rectangles/ellipses, when ItemIsMovable is set, Qt moves them by changing position
        # ItemPositionHasChanged fires after the position has changed
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # print("[DEBUG-ROI] ROIGraphicsEllipseItem position changed")
            if self.on_moved_callback:
                try:
                    self.on_moved_callback()
                except Exception as e:
                    # print(f"[DEBUG-ROI] Error in ROI movement callback: {e}")
                    pass
        return super().itemChange(change, value)
    
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse move to detect dragging."""
        # Call parent to handle the move
        super().mouseMoveEvent(event)
        # If item is being dragged (left button pressed), check if position changed significantly
        if event.buttons() & Qt.MouseButton.LeftButton:
            current_pos = self.pos()
            # Only trigger callback if position changed significantly (more than 1 pixel)
            if self._last_callback_pos is None or (current_pos - self._last_callback_pos).manhattanLength() > 1.0:
                if self.on_moved_callback:
                    try:
                        # print("[DEBUG-ROI] ROIGraphicsEllipseItem mouseMoveEvent - triggering callback")
                        self.on_moved_callback()
                        self._last_callback_pos = current_pos
                    except Exception as e:
                        # print(f"[DEBUG-ROI] Error in ROI movement callback from mouseMoveEvent: {e}")
                        pass

    def shape(self) -> QPainterPath:
        """Return shape for hit testing - ellipse boundary plus tolerance, not filled interior.

        Overrides the default (filled ellipse) so that clicks inside the ellipse interior
        do not register as hits on this item. Only the outline region (stroke + tolerance)
        is hit-testable, allowing users to draw or interact with items inside a large ellipse.
        """
        path = QPainterPath()
        path.addEllipse(self.rect())
        tolerance = max(self.pen().widthF(), 1.0) + 5.0
        pen = QPen(Qt.PenStyle.SolidLine)
        pen.setWidthF(tolerance)
        stroker = QPainterPathStroker(pen)
        return stroker.createStroke(path)


class ROIGraphicsRectItem(QGraphicsRectItem):
    """
    Custom QGraphicsRectItem that detects position changes for ROI movement.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_moved_callback: Optional[Callable[[], None]] = None
        self._last_callback_pos: Optional[QPointF] = None  # Track last position where callback was triggered
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """Handle item changes, particularly position changes."""
        # For rectangles/ellipses, when ItemIsMovable is set, Qt moves them by changing position
        # ItemPositionHasChanged fires after the position has changed
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            # print("[DEBUG-ROI] ROIGraphicsRectItem position changed")
            if self.on_moved_callback:
                try:
                    self.on_moved_callback()
                except Exception as e:
                    # print(f"[DEBUG-ROI] Error in ROI movement callback: {e}")
                    pass
        return super().itemChange(change, value)
    
    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse move to detect dragging."""
        # Call parent to handle the move
        super().mouseMoveEvent(event)
        # If item is being dragged (left button pressed), check if position changed significantly
        if event.buttons() & Qt.MouseButton.LeftButton:
            current_pos = self.pos()
            # Only trigger callback if position changed significantly (more than 1 pixel)
            if self._last_callback_pos is None or (current_pos - self._last_callback_pos).manhattanLength() > 1.0:
                if self.on_moved_callback:
                    try:
                        # print("[DEBUG-ROI] ROIGraphicsRectItem mouseMoveEvent - triggering callback")
                        self.on_moved_callback()
                        self._last_callback_pos = current_pos
                    except Exception as e:
                        # print(f"[DEBUG-ROI] Error in ROI movement callback from mouseMoveEvent: {e}")
                        pass

    def shape(self) -> QPainterPath:
        """Return shape for hit testing - rectangle boundary plus tolerance, not filled interior.

        Overrides the default (filled rectangle) so that clicks inside the rectangle interior
        do not register as hits on this item. Only the outline region (stroke + tolerance)
        is hit-testable, allowing users to draw or interact with items inside a large rectangle.
        """
        path = QPainterPath()
        path.addRect(self.rect())
        tolerance = max(self.pen().widthF(), 1.0) + 5.0
        pen = QPen(Qt.PenStyle.SolidLine)
        pen.setWidthF(tolerance)
        stroker = QPainterPathStroker(pen)
        return stroker.createStroke(path)


ROI_RESIZE_HANDLE_IDS: Tuple[str, ...] = ("tl", "tm", "tr", "mr", "br", "bm", "bl", "ml")

_CURSOR_FOR_RESIZE_HANDLE: Dict[str, Qt.CursorShape] = {
    "tl": Qt.CursorShape.SizeFDiagCursor,
    "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor,
    "bl": Qt.CursorShape.SizeBDiagCursor,
    "tm": Qt.CursorShape.SizeVerCursor,
    "bm": Qt.CursorShape.SizeVerCursor,
    "ml": Qt.CursorShape.SizeHorCursor,
    "mr": Qt.CursorShape.SizeHorCursor,
}


def compute_resized_scene_rect_from_handle(
    anchor: QRectF, handle: str, p: QPointF, min_size: float = 2.0
) -> QRectF:
    """
    Compute a new axis-aligned scene rectangle by dragging one handle of ``anchor``
    toward scene point ``p``. Opposite edges stay fixed per handle semantics.
    """
    L, T, R, B = anchor.left(), anchor.top(), anchor.right(), anchor.bottom()
    x, y = p.x(), p.y()
    ms = min_size

    def clamp_w(nl: float, nr: float) -> Tuple[float, float]:
        if nr - nl < ms:
            c = (nl + nr) * 0.5
            return c - ms / 2.0, c + ms / 2.0
        return nl, nr

    def clamp_h(nt: float, nb: float) -> Tuple[float, float]:
        if nb - nt < ms:
            c = (nt + nb) * 0.5
            return c - ms / 2.0, c + ms / 2.0
        return nt, nb

    if handle == "br":
        nl, nt = L, T
        nr, nb = max(x, L + ms), max(y, T + ms)
        nl, nr = clamp_w(nl, nr)
        nt, nb = clamp_h(nt, nb)
        return QRectF(nl, nt, nr - nl, nb - nt).normalized()
    if handle == "tl":
        nr, nb = R, B
        nl, nt = min(x, nr - ms), min(y, nb - ms)
        nl, nr = clamp_w(nl, nr)
        nt, nb = clamp_h(nt, nb)
        return QRectF(nl, nt, nr - nl, nb - nt).normalized()
    if handle == "tr":
        nl, nb = L, B
        nr, nt = max(x, nl + ms), min(y, nb - ms)
        nl, nr = clamp_w(nl, nr)
        nt, nb = clamp_h(nt, nb)
        return QRectF(nl, nt, nr - nl, nb - nt).normalized()
    if handle == "bl":
        nr, nt = R, T
        nl, nb = min(x, nr - ms), max(y, nt + ms)
        nl, nr = clamp_w(nl, nr)
        nt, nb = clamp_h(nt, nb)
        return QRectF(nl, nt, nr - nl, nb - nt).normalized()
    if handle == "mr":
        nl, nt, nb = L, T, B
        nr = max(x, nl + ms)
        nl, nr = clamp_w(nl, nr)
        nt, nb = clamp_h(nt, nb)
        return QRectF(nl, nt, nr - nl, nb - nt).normalized()
    if handle == "ml":
        nr, nt, nb = R, T, B
        nl = min(x, nr - ms)
        nl, nr = clamp_w(nl, nr)
        nt, nb = clamp_h(nt, nb)
        return QRectF(nl, nt, nr - nl, nb - nt).normalized()
    if handle == "tm":
        nl, nr, nb = L, R, B
        nt = min(y, nb - ms)
        nl, nr = clamp_w(nl, nr)
        nt, nb = clamp_h(nt, nb)
        return QRectF(nl, nt, nr - nl, nb - nt).normalized()
    if handle == "bm":
        nl, nr, nt = L, R, T
        nb = max(y, nt + ms)
        nl, nr = clamp_w(nl, nr)
        nt, nb = clamp_h(nt, nb)
        return QRectF(nl, nt, nr - nl, nb - nt).normalized()
    return anchor.normalized()


def apply_roi_scene_bounding_rect(roi: "ROIItem", rect: QRectF) -> None:
    """Apply a scene-axis-aligned bounding box to the ROI's graphics item (pos + local rect)."""
    rect = rect.normalized()
    roi.item.setPos(rect.topLeft())
    roi.item.setRect(0.0, 0.0, rect.width(), rect.height())
    handles = getattr(roi, "_resize_handles", None)
    if handles:
        roi.update_resize_handle_positions()


def roi_scene_bounding_rect(roi: "ROIItem") -> QRectF:
    """Current scene bounding rect of the ROI shape (same as ``sceneBoundingRect`` of the item)."""
    return roi.item.mapRectToScene(roi.item.rect())


class ROIResizeHandleItem(QGraphicsRectItem):
    """
    Small square handle for resizing a finished rectangle or ellipse ROI.
    Lives in scene coordinates; ignores view zoom so it stays readable.
    """

    HANDLE_HALF = 4.0

    def __init__(self, roi_item: "ROIItem", handle_id: str) -> None:
        s = self.HANDLE_HALF * 2.0
        super().__init__(-self.HANDLE_HALF, -self.HANDLE_HALF, s, s)
        self._roi_item = roi_item
        self._handle_id = handle_id
        self._dragging = False
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(QColor(255, 255, 255), 1))
        self.setBrush(QBrush(QColor(0, 200, 255, 200)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(120)
        cur = _CURSOR_FOR_RESIZE_HANDLE.get(handle_id, Qt.CursorShape.ArrowCursor)
        self.setCursor(QCursor(cur))

    def handle_id(self) -> str:
        return self._handle_id

    def roi_graphics_shape_item(self) -> QGraphicsEllipseItem | QGraphicsRectItem:
        return self._roi_item.item

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._roi_item.begin_resize_handle_drag(self._handle_id, event.scenePos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self._roi_item.continue_resize_handle_drag(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._roi_item.finish_resize_handle_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class DraggableStatisticsOverlay(QGraphicsTextItem):
    """
    Custom QGraphicsTextItem for ROI statistics overlays that tracks position changes.
    """
    
    def __init__(self, roi: 'ROIItem', offset_update_callback: Callable[[float, float], None]):
        """
        Initialize draggable statistics overlay.
        
        Args:
            roi: ROI item this overlay belongs to
            offset_update_callback: Callback to update offset when overlay is moved
        """
        super().__init__()
        self.roi: ROIItem | None = roi
        self.offset_update_callback = offset_update_callback
        self._updating_position = False  # Flag to prevent recursive updates
        self._is_deleted = False  # Guard against events after removal
    
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        """
        Handle item changes, particularly position changes.
        
        Args:
            change: Type of change
            value: New value
            
        Returns:
            Modified value
        """
        if self._is_deleted:
            return super().itemChange(change, value)
        
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and not self._updating_position:
            # Overlay was moved by user - calculate new offset relative to ROI bounds
            try:
                # Check if ROI still exists and is valid
                if self.roi is None:
                    # print("[DEBUG-OVERLAY] ROI is None in overlay itemChange")
                    return super().itemChange(change, value)
                
                # Check if ROI item still exists and is in scene
                if not hasattr(self.roi, 'item') or self.roi.item is None:
                    # print("[DEBUG-OVERLAY] ROI item is None")
                    return super().itemChange(change, value)
                
                if self.roi.item.scene() is None:
                    # print("[DEBUG-OVERLAY] ROI item not in scene")
                    return super().itemChange(change, value)
                
                if self.scene() is None:
                    # print("[DEBUG-OVERLAY] Overlay not in scene")
                    return super().itemChange(change, value)
                
                view = self.scene().views()[0] if self.scene().views() else None
                if view is not None:
                    bounds = self.roi.get_bounds()
                    overlay_pos = self.pos()
                    
                    # Convert scene coordinates to viewport pixels
                    view_scale = graphics_view_uniform_zoom(view)
                    scene_to_viewport_scale = view_scale
                    
                    # Calculate offset from ROI bounds in viewport pixels
                    offset_x = (overlay_pos.x() - bounds.right()) * scene_to_viewport_scale
                    offset_y = (overlay_pos.y() - bounds.top()) * scene_to_viewport_scale
                    
                    # Update stored offset
                    if self.offset_update_callback:
                        self.offset_update_callback(offset_x, offset_y)
            except Exception as e:
                # print(f"[DEBUG-OVERLAY] Error in overlay itemChange: {e}")
                pass
                _logger.debug("%s", sanitized_format_exc())

        return super().itemChange(change, value)
    
    def mark_deleted(self) -> None:
        """Mark overlay as deleted to short-circuit event handling."""
        self._is_deleted = True

    def clear_deleted_flag(self) -> None:
        """Reset deleted guard when reusing an overlay in a new scene."""
        self._is_deleted = False

    def set_updating_position(self, updating: bool) -> None:
        """Set flag to suppress offset callbacks during programmatic moves."""
        self._updating_position = updating


class ROIItem:
    """
    Base class for ROI items.
    """
    
    def __init__(self, shape_type: str, item: QGraphicsEllipseItem | QGraphicsRectItem,
                 pen_width: int = 2, pen_color: Tuple[int, int, int] = (255, 0, 0),
                 default_visible_statistics: Optional[Set[str]] = None):
        """
        Initialize ROI item.
        
        Args:
            shape_type: "ellipse" or "rectangle"
            item: Graphics item (should be ROIGraphicsEllipseItem or ROIGraphicsRectItem)
            pen_width: Pen width in viewport pixels (default: 2)
            pen_color: Pen color as (r, g, b) tuple (default: red)
            default_visible_statistics: Optional set of statistics to show by default
        """
        self.shape_type = shape_type
        self.item = item
        self.id = id(self)
        
        # Set pen style - use cosmetic pen for viewport-relative width
        pen = QPen(QColor(*pen_color), pen_width)
        pen.setCosmetic(True)  # Makes pen width viewport-relative (independent of zoom)
        pen.setStyle(Qt.PenStyle.DashLine)
        self.item.setPen(pen)
        self.item.setBrush(Qt.BrushStyle.NoBrush)
        
        # Make item selectable and movable
        self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        
        # Store callback for when ROI is moved (no-arg; coordinators may use
        # lambda defaults to pass the ROIItem, matching _on_item_moved()).
        self.on_moved_callback: Optional[Callable[[], None]] = None
        
        # Position tracking for move operations
        self._move_start_position: Optional[QPointF] = None
        self._is_being_moved: bool = False
        
        # Statistics overlay properties
        self.statistics_overlay_visible = True  # Default: show overlay
        self.visible_statistics: Set[str] = (
            default_visible_statistics.copy()
            if default_visible_statistics is not None
            else {"mean", "std", "min", "max", "count", "area"}
        )
        self.statistics_overlay_item: DraggableStatisticsOverlay | None = None
        self.statistics: RoiStatisticsMap | None = None
        self.statistics_overlay_offset: Tuple[float, float] = (5.0, 5.0)  # Offset from ROI bounds (viewport pixels)

        # Resize-handle edit mode (see ROIManager.enter_roi_geometry_edit_mode)
        self._resize_handles: List[ROIResizeHandleItem] = []
        self._resize_anchor_scene_rect: Optional[QRectF] = None
        self._resize_initial_scene_rect: Optional[QRectF] = None
        self._active_resize_handle: Optional[str] = None
        self._resize_drag_active: bool = False
        self._on_resize_gesture_committed: Optional[Callable[[QRectF, QRectF], None]] = None
        
        # Set up movement detection callback on the graphics item
        if isinstance(item, (ROIGraphicsEllipseItem, ROIGraphicsRectItem)):
            item.on_moved_callback = lambda: self._on_item_moved()
    
    def _on_item_moved(self) -> None:
        """Handle ROI item movement - call callback if set."""
        if not self._resize_drag_active:
            # Store initial position on first movement if not already set
            if self._move_start_position is None and self.item is not None:
                self._move_start_position = self.item.pos()
            self._is_being_moved = True
        
        if self.on_moved_callback:
            self.on_moved_callback()
        if self._resize_handles:
            self.update_resize_handle_positions()
    
    def show_resize_handles(
        self,
        scene: QGraphicsScene,
        on_commit: Optional[Callable[[QRectF, QRectF], None]] = None,
    ) -> None:
        """Show corner/edge resize handles on ``scene`` and optionally report committed resizes."""
        self.hide_resize_handles(scene)
        self._on_resize_gesture_committed = on_commit
        for hid in ROI_RESIZE_HANDLE_IDS:
            h = ROIResizeHandleItem(self, hid)
            scene.addItem(h)
            self._resize_handles.append(h)
        self.update_resize_handle_positions()

    def hide_resize_handles(self, scene: QGraphicsScene) -> None:
        """Remove resize handles from ``scene``."""
        for h in list(self._resize_handles):
            try:
                if h.scene() == scene:
                    scene.removeItem(h)
            except RuntimeError:
                pass
        self._resize_handles.clear()
        self._on_resize_gesture_committed = None
        if self._resize_drag_active:
            self._resize_drag_active = False
            self._active_resize_handle = None
            self._resize_anchor_scene_rect = None
            self._resize_initial_scene_rect = None
            if self.item is not None and isValid(self.item):
                self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    def update_resize_handle_positions(self) -> None:
        """Reposition handles on the current scene bounding rect of this ROI."""
        if not self._resize_handles or self.item is None or not isValid(self.item):
            return
        br = roi_scene_bounding_rect(self)
        cx = (br.left() + br.right()) * 0.5
        cy = (br.top() + br.bottom()) * 0.5
        corners: Dict[str, QPointF] = {
            "tl": QPointF(br.left(), br.top()),
            "tm": QPointF(cx, br.top()),
            "tr": QPointF(br.right(), br.top()),
            "mr": QPointF(br.right(), cy),
            "br": QPointF(br.right(), br.bottom()),
            "bm": QPointF(cx, br.bottom()),
            "bl": QPointF(br.left(), br.bottom()),
            "ml": QPointF(br.left(), cy),
        }
        for h in self._resize_handles:
            pt = corners.get(h.handle_id())
            if pt is not None:
                h.setPos(pt)

    def begin_resize_handle_drag(self, handle_id: str, scene_pos: QPointF) -> None:
        """Begin a resize gesture from handle ``handle_id`` (scene coordinates)."""
        _ = scene_pos
        self._resize_anchor_scene_rect = QRectF(roi_scene_bounding_rect(self))
        self._resize_initial_scene_rect = QRectF(self._resize_anchor_scene_rect)
        self._active_resize_handle = handle_id
        self._resize_drag_active = True
        if self.item is not None and isValid(self.item):
            self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)

    def continue_resize_handle_drag(self, scene_pos: QPointF) -> None:
        """Update geometry while dragging a resize handle."""
        if (
            not self._resize_drag_active
            or self._active_resize_handle is None
            or self._resize_anchor_scene_rect is None
        ):
            return
        new_r = compute_resized_scene_rect_from_handle(
            self._resize_anchor_scene_rect, self._active_resize_handle, scene_pos
        )
        apply_roi_scene_bounding_rect(self, new_r)
        self.update_resize_handle_positions()
        if self.on_moved_callback:
            self.on_moved_callback()

    def finish_resize_handle_drag(self) -> None:
        """End resize gesture; invoke commit callback if the rect changed."""
        if self.item is not None and isValid(self.item):
            self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self._resize_drag_active = False
        self._active_resize_handle = None
        self._resize_anchor_scene_rect = None
        initial = self._resize_initial_scene_rect
        self._resize_initial_scene_rect = None
        if initial is not None and self._on_resize_gesture_committed is not None:
            final = QRectF(roi_scene_bounding_rect(self))
            if initial != final:
                self._on_resize_gesture_committed(initial, final)
    
    def get_move_start_position(self) -> Optional[QPointF]:
        """Get the position where movement started."""
        return self._move_start_position
    
    def clear_move_tracking(self) -> None:
        """Clear move tracking state."""
        self._move_start_position = None
        self._is_being_moved = False
    
    def get_bounds(self) -> QRectF:
        """
        Get bounding rectangle of ROI.
        
        Returns:
            Bounding rectangle
        """
        if self.item.scene() is not None:
            return self.item.sceneBoundingRect()
        return self.item.rect()
    
    def get_mask(self, width: int, height: int) -> np.ndarray:
        """
        Get binary mask for ROI.
        
        Args:
            width: Image width
            height: Image height
            
        Returns:
            Binary mask array
        """
        mask = np.zeros((height, width), dtype=bool)
        bounds = self.get_bounds()
        
        left = min(bounds.left(), bounds.right())
        right = max(bounds.left(), bounds.right())
        top = min(bounds.top(), bounds.bottom())
        bottom = max(bounds.top(), bounds.bottom())
        
        left = max(0.0, min(float(width), left))
        right = max(0.0, min(float(width), right))
        top = max(0.0, min(float(height), top))
        bottom = max(0.0, min(float(height), bottom))
        
        x1 = int(math.floor(left))
        y1 = int(math.floor(top))
        x2 = int(math.ceil(right))
        y2 = int(math.ceil(bottom))
        
        if x1 >= x2 or y1 >= y2:
            return mask
        
        if self.shape_type == "rectangle":
            mask[y1:y2, x1:x2] = True
        elif self.shape_type == "ellipse":
            # Create ellipse mask constrained to actual bounds
            center_x = (left + right) / 2.0
            center_y = (top + bottom) / 2.0
            radius_x = max(0.5, (right - left) / 2.0)
            radius_y = max(0.5, (bottom - top) / 2.0)
            
            y_indices, x_indices = np.ogrid[:height, :width]
            ellipse_mask = ((x_indices - center_x) / radius_x) ** 2 + ((y_indices - center_y) / radius_y) ** 2 <= 1
            
            # Limit ellipse mask to bounding box to avoid stray pixels
            bbox_mask = (
                (x_indices >= x1) & (x_indices < x2) &
                (y_indices >= y1) & (y_indices < y2)
            )
            mask = ellipse_mask & bbox_mask
        
        return mask


class ROIManager:
    """
    Manages ROIs on images.
    
    Features:
    - Draw elliptical and rectangular ROIs
    - Calculate statistics within ROIs
    - Clear ROIs from slice or dataset
    """
    
    def __init__(self, config_manager: ConfigManager | None = None) -> None:
        """
        Initialize the ROI manager.
        
        Args:
            config_manager: Optional ConfigManager for annotation settings
        """
        # Key format: (StudyInstanceUID, SeriesInstanceUID, instance_identifier)
        # instance_identifier can be InstanceNumber from DICOM or slice_index as fallback
        self.rois: Dict[Tuple[str, str, int], List[ROIItem]] = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_instance_identifier = 0
        self.drawing = False
        self.drawing_start_pos: Optional[QPointF] = None
        self.current_roi_item: Optional[ROIItem] = None
        self.current_shape_type = "rectangle"  # "rectangle" or "ellipse"
        self.selected_roi: Optional[ROIItem] = None  # Currently selected ROI
        self.config_manager: ConfigManager | None = config_manager
        # Geometry edit mode (resize handles) — see enter_roi_geometry_edit_mode
        self._editing_roi: Optional[ROIItem] = None
        self._geometry_edit_scene: Optional[QGraphicsScene] = None

    def exit_roi_geometry_edit_mode(self) -> bool:
        """Hide resize handles and leave geometry-edit mode. Returns True if mode was active."""
        if self._editing_roi is None or self._geometry_edit_scene is None:
            self._editing_roi = None
            self._geometry_edit_scene = None
            return False
        try:
            self._editing_roi.hide_resize_handles(self._geometry_edit_scene)
        except RuntimeError:
            pass
        self._editing_roi = None
        self._geometry_edit_scene = None
        return True

    def enter_roi_geometry_edit_mode(
        self,
        roi: ROIItem,
        scene: QGraphicsScene,
        on_commit: Callable[[ROIItem, QRectF, QRectF], None],
    ) -> None:
        """
        Show resize handles for ``roi`` and route committed resizes to ``on_commit(roi, old_rect, new_rect)``.
        """
        if roi.shape_type not in ("rectangle", "ellipse"):
            return

        def _wrapped(old_r: QRectF, new_r: QRectF) -> None:
            on_commit(roi, old_r, new_r)

        if (
            self._editing_roi == roi
            and self._geometry_edit_scene == scene
            and roi._resize_handles
        ):
            roi._on_resize_gesture_committed = _wrapped
            return

        self.exit_roi_geometry_edit_mode()

        roi.show_resize_handles(scene, on_commit=_wrapped)
        self._editing_roi = roi
        self._geometry_edit_scene = scene
    
    def set_current_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> None:
        """
        Set the current slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
        """
        # print(f"[ROI DEBUG] set_current_slice called with instance_identifier={instance_identifier}")
        old_key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        new_key = (study_uid, series_uid, instance_identifier)
        if old_key != new_key:
            self.exit_roi_geometry_edit_mode()
        self.current_study_uid = study_uid
        self.current_series_uid = series_uid
        self.current_instance_identifier = instance_identifier
        key = (study_uid, series_uid, instance_identifier)
        if key not in self.rois:
            self.rois[key] = []
    
    def start_drawing(self, pos: QPointF, shape_type: str = "rectangle") -> None:
        """
        Start drawing a new ROI.
        
        Args:
            pos: Starting position
            shape_type: "rectangle" or "ellipse"
        """
        self.exit_roi_geometry_edit_mode()
        self.drawing = True
        self.drawing_start_pos = pos
        self.current_shape_type = shape_type
        self.current_roi_item = None
    
    def update_drawing(self, pos: QPointF, scene: QGraphicsScene) -> None:
        """
        Update ROI while drawing.
        
        Args:
            pos: Current mouse position
            scene: QGraphicsScene to add items to
        """
        if not self.drawing or self.drawing_start_pos is None:
            return
        
        # Calculate bounds
        x1 = min(self.drawing_start_pos.x(), pos.x())
        y1 = min(self.drawing_start_pos.y(), pos.y())
        x2 = max(self.drawing_start_pos.x(), pos.x())
        y2 = max(self.drawing_start_pos.y(), pos.y())
        
        rect = QRectF(x1, y1, x2 - x1, y2 - y1)
        
        # Remove old item if exists
        if self.current_roi_item is not None:
            # Only remove if item actually belongs to this scene
            if self.current_roi_item.item.scene() == scene:
                scene.removeItem(self.current_roi_item.item)
        
        # Create new item using custom classes that detect movement
        if self.current_shape_type == "rectangle":
            item = ROIGraphicsRectItem(rect)
        else:  # ellipse
            item = ROIGraphicsEllipseItem(rect)
        
        # Get pen settings from config
        pen_width = 2  # Default
        pen_color = (255, 0, 0)  # Default red
        if self.config_manager:
            pen_width = self.config_manager.get_roi_line_thickness()
            pen_color = self.config_manager.get_roi_line_color()
        
        # Get default visible statistics from config if available
        default_stats = None
        if self.config_manager:
            default_stats_list = self.config_manager.get_roi_default_visible_statistics()
            default_stats = set(default_stats_list)
        
        self.current_roi_item = ROIItem(self.current_shape_type, item, pen_width=pen_width, pen_color=pen_color,
                                        default_visible_statistics=default_stats)
        # Don't make drawing ROI selectable/movable yet (will be enabled when finished)
        self.current_roi_item.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.current_roi_item.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        scene.addItem(item)
    
    def finish_drawing(self) -> Optional[ROIItem]:
        """
        Finish drawing ROI.
        
        Returns:
            Created ROI item or None
        """
        if not self.drawing or self.current_roi_item is None:
            self.drawing = False
            return None
        
        # Add to current slice using composite key
        key = (self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
        # print(f"[ROI DEBUG] finish_drawing storing ROI with key={key}, instance_identifier={self.current_instance_identifier}")
        if key not in self.rois:
            self.rois[key] = []
        
        self.rois[key].append(self.current_roi_item)
        # print(f"[ROI DEBUG] Total ROIs for key {key}: {len(self.rois[key])}")
        # print(f"[ROI DEBUG] All keys in rois dict: {list(self.rois.keys())}")
        
        # Enable selectable/movable now that drawing is finished
        self.current_roi_item.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.current_roi_item.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        
        # Select the newly created ROI
        self.select_roi(self.current_roi_item)
        
        self.drawing = False
        self.drawing_start_pos = None
        roi = self.current_roi_item
        self.current_roi_item = None
        
        return roi
    
    def select_roi(self, roi: Optional[ROIItem]) -> None:
        """
        Select a ROI.
        
        Args:
            roi: ROI item to select, or None to deselect
        """
        if self._editing_roi is not None and self._editing_roi != roi:
            self.exit_roi_geometry_edit_mode()
        # Deselect previous ROI
        if self.selected_roi is not None:
            prev = self.selected_roi
            prev_item = prev.item if prev is not None else None
            if prev_item is not None and isValid(prev_item):
                try:
                    prev_item.setSelected(False)
                    roi_scene = prev_item.scene()
                    if roi_scene is not None:
                        roi_scene.clearSelection()
                except RuntimeError:
                    pass

        # Select new ROI
        # print(f"[DEBUG-OVERLAY] select_roi: roi_manager={id(self)}, selecting ROI {id(roi) if roi else None}")
        self.selected_roi = roi
        if roi is None:
            pass
        elif roi.item is None or not isValid(roi.item):
            self.selected_roi = None
        else:
            try:
                roi.item.setSelected(True)
            except RuntimeError:
                self.selected_roi = None
    
    def get_selected_roi(self) -> Optional[ROIItem]:
        """
        Get currently selected ROI.
        
        Returns:
            Selected ROI item or None
        """
        if self.selected_roi is not None:
            it = self.selected_roi.item
            if it is None or not isValid(it):
                self.selected_roi = None
        return self.selected_roi
    
    def find_roi_by_item(self, item) -> Optional[ROIItem]:
        """
        Find ROI item by graphics item.
        
        Args:
            item: QGraphicsItem
            
        Returns:
            ROIItem or None
        """
        for roi_list in self.rois.values():
            for roi in roi_list:
                if roi.item == item:
                    return roi
        return None
    
    def delete_roi(self, roi: ROIItem, scene: QGraphicsScene) -> bool:
        """
        Delete a ROI.
        
        Args:
            roi: ROI item to delete
            scene: QGraphicsScene to remove item from
            
        Returns:
            True if deleted, False otherwise
        """
        # print(f"[DEBUG-ROI] delete_roi called for ROI {id(roi)}")
        if self._editing_roi == roi:
            self.exit_roi_geometry_edit_mode()
        # Find and remove from rois dict
        for roi_list in self.rois.values():
            if roi in roi_list:
                # print(f"[DEBUG-ROI] Found ROI in list, removing")
                roi_list.remove(roi)
                # Remove statistics overlay BEFORE removing ROI item from scene
                # This ensures the overlay is properly removed
                self.remove_statistics_overlay(roi, scene)
                roi.statistics_overlay_visible = False
                roi.statistics = None
                if roi.item and isValid(roi.item):
                    try:
                        if scene and roi.item.scene() == scene:
                            scene.removeItem(roi.item)
                    except RuntimeError:
                        pass
                
                # Deselect if this was the selected ROI
                if self.selected_roi == roi:
                    # print(f"[DEBUG-ROI] Deselecting deleted ROI")
                    self.selected_roi = None
                
                # print(f"[DEBUG-ROI] ROI deletion complete")
                return True
        # print(f"[DEBUG-ROI] ROI not found in lists")
        return False
    
    def get_rois_for_slice(self, study_uid: str, series_uid: str, instance_identifier: int) -> List[ROIItem]:
        """
        Get all ROIs for a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            
        Returns:
            List of ROI items
        """
        key = (study_uid, series_uid, instance_identifier)
        return self.rois.get(key, [])
    
    def clear_slice_rois(self, study_uid: str, series_uid: str, instance_identifier: int,
                         scene: QGraphicsScene) -> None:
        """
        Clear all ROIs from a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            scene: QGraphicsScene to remove items from
        """
        key = (study_uid, series_uid, instance_identifier)
        if key in self.rois:
            self.exit_roi_geometry_edit_mode()
            if self.selected_roi is not None and self.selected_roi in self.rois[key]:
                self.selected_roi = None
            for roi in self.rois[key]:
                # Remove statistics overlay if present
                self.remove_statistics_overlay(roi, scene)
                # Remove item from scene if it exists (guard: scene.clear() may have deleted the C++ item)
                if roi.item and isValid(roi.item) and scene:
                    try:
                        if roi.item.scene() == scene:
                            scene.removeItem(roi.item)
                    except RuntimeError:
                        pass
                roi.statistics_overlay_visible = False
                roi.statistics = None
            del self.rois[key]
    
    def clear_all_rois(self, scene: QGraphicsScene) -> None:
        """
        Clear all ROIs from all slices.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        self.exit_roi_geometry_edit_mode()
        for slice_index, roi_list in self.rois.items():
            for roi in roi_list:
                # Remove statistics overlay if present
                self.remove_statistics_overlay(roi, scene)
                # Only remove if item still exists and belongs to this scene (e.g. clear_mpr may have scene.clear()'d first)
                if roi.item and isValid(roi.item):
                    try:
                        if scene and roi.item.scene() == scene:
                            scene.removeItem(roi.item)
                    except RuntimeError:
                        pass
                roi.statistics_overlay_visible = False
                roi.statistics = None
        self.rois.clear()
        self.selected_roi = None
        self.current_roi_item = None
        self.drawing = False
        self.drawing_start_pos = None

    def update_all_roi_styles(self, config_manager: ConfigManager | None) -> None:
        """
        Update styles (pen color, thickness, font size, font color) for all existing ROIs.
        
        Args:
            config_manager: ConfigManager instance to get current settings
        """
        if config_manager is None:
            return
        
        # Get new settings from config
        pen_width = config_manager.get_roi_line_thickness()
        pen_color = config_manager.get_roi_line_color()
        font_size = config_manager.get_roi_font_size()
        font_color = config_manager.get_roi_font_color()
        font_family = config_manager.get_roi_font_family()
        font_variant = config_manager.get_roi_font_variant()
        
        # Create new pen with updated settings
        pen = QPen(QColor(*pen_color), pen_width)
        pen.setCosmetic(True)  # Makes pen width viewport-relative (independent of zoom)
        pen.setStyle(Qt.PenStyle.DashLine)
        
        # Update all ROIs
        for key, roi_list in self.rois.items():
            for roi in roi_list:
                # Update ROI line pen
                roi.item.setPen(pen)
                
                # Update statistics overlay if it exists
                if roi.statistics_overlay_item is not None:
                    text_item = roi.statistics_overlay_item
                    text_item.setDefaultTextColor(QColor(*font_color))
                    
                    # Update font size
                    if font_size < 6:
                        font = make_qfont(font_family, font_variant, 6)
                        scale_factor = font_size / 6.0
                        transform = QTransform()
                        transform.scale(scale_factor, scale_factor)
                        text_item.setTransform(transform)
                    else:
                        font = make_qfont(font_family, font_variant, font_size)
                        # Reset transform if font size is >= 6
                        text_item.setTransform(QTransform())
                    
                    text_item.setFont(font)

                if getattr(roi, "_resize_handles", None):
                    roi.update_resize_handle_positions()
    
    def calculate_statistics(
        self,
        roi: ROIItem,
        pixel_array: np.ndarray,
        rescale_slope: Optional[float] = None,
        rescale_intercept: Optional[float] = None,
        pixel_spacing: Optional[Tuple[float, float]] = None,
        dataset: Optional[Dataset] = None,
    ) -> RoiStatisticsMap:
        """
        Calculate statistics for an ROI.

        Args:
            roi: ROI item
            pixel_array: Image pixel array
            rescale_slope: Optional rescale slope to apply to pixel values
            rescale_intercept: Optional rescale intercept to apply to pixel values
            pixel_spacing: Optional pixel spacing tuple (row_spacing, col_spacing) in mm for area calculation
            dataset: Optional DICOM dataset for ``PhotometricInterpretation``-based ``channel_labels``

        Returns:
            Dictionary with statistics (mean, std, min, max, count, area_pixels, area_mm2);
            multichannel runs may include ``channel_labels`` (tuple of short names per channel).
        """
        height, width = pixel_array.shape[:2]
        
        # Get ROI bounds in scene coordinates
        bounds = roi.get_bounds()
        
        # Convert scene coordinates to pixel coordinates
        # Note: This assumes 1:1 mapping - may need adjustment based on image scaling
        left = min(bounds.left(), bounds.right())
        right = max(bounds.left(), bounds.right())
        top = min(bounds.top(), bounds.bottom())
        bottom = max(bounds.top(), bounds.bottom())
        
        left = max(0.0, min(float(width), left))
        right = max(0.0, min(float(width), right))
        top = max(0.0, min(float(height), top))
        bottom = max(0.0, min(float(height), bottom))
        
        x1 = int(math.floor(left))
        y1 = int(math.floor(top))
        x2 = int(math.ceil(right))
        y2 = int(math.ceil(bottom))
        
        if x2 <= x1 or y2 <= y1:
            stats = {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0,
                "area_pixels": 0.0,
                "area_mm2": None
            }
            roi.statistics = stats
            return stats
        
        # Get mask for ROI shape
        mask = roi.get_mask(width, height)
        
        # Calculate area in pixels
        area_pixels = float(np.sum(mask))
        
        # Calculate area in mm² if pixel spacing is available
        area_mm2 = None
        if pixel_spacing is not None and len(pixel_spacing) >= 2:
            row_spacing = pixel_spacing[0]  # mm per pixel in row direction
            col_spacing = pixel_spacing[1]  # mm per pixel in column direction
            # Area in mm² = area in pixels * (row_spacing * col_spacing)
            area_mm2 = area_pixels * row_spacing * col_spacing
        
        # Get pixels within ROI
        roi_pixels = pixel_array[mask]
        
        if len(roi_pixels) == 0:
            stats = {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0,
                "area_pixels": area_pixels,
                "area_mm2": area_mm2
            }
            roi.statistics = stats
            return stats
        
        # Apply rescale if parameters provided
        if rescale_slope is not None and rescale_intercept is not None:
            roi_pixels = roi_pixels.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
        
        stats = {
            "mean": float(np.mean(roi_pixels)),
            "std": float(np.std(roi_pixels)),
            "min": float(np.min(roi_pixels)),
            "max": float(np.max(roi_pixels)),
            "count": int(len(roi_pixels)),
            "area_pixels": area_pixels,
            "area_mm2": area_mm2,
        }

        show_pc = (
            self.config_manager is not None
            and self.config_manager.get_roi_show_per_channel_statistics()
        )
        if show_pc and pixel_array.ndim == 3 and pixel_array.shape[2] >= 2:
            nc = int(pixel_array.shape[2])
            stats["multichannel_count"] = nc
            for c in range(nc):
                ch_raw = pixel_array[:, :, c][mask]
                if len(ch_raw) == 0:
                    continue
                ch = ch_raw.astype(np.float32)
                if rescale_slope is not None and rescale_intercept is not None:
                    ch = ch * float(rescale_slope) + float(rescale_intercept)
                stats[f"mean_ch{c}"] = float(np.mean(ch))
                stats[f"std_ch{c}"] = float(np.std(ch))
                stats[f"min_ch{c}"] = float(np.min(ch))
                stats[f"max_ch{c}"] = float(np.max(ch))
            stats["channel_labels"] = tuple(multichannel_axis_labels(dataset, nc))

        # Store statistics in ROI item
        roi.statistics = stats

        return stats
    
    def create_statistics_overlay(self, roi: ROIItem, statistics: RoiStatisticsMap,
                                  scene: QGraphicsScene, font_size: Optional[int] = None,
                                  font_color: Optional[Tuple[int, int, int]] = None,
                                  rescale_type: Optional[str] = None) -> None:
        """
        Create or update statistics overlay text item for an ROI.
        
        Args:
            roi: ROI item
            statistics: Statistics dictionary
            scene: QGraphicsScene to add item to
            font_size: Font size in points (if None, uses config value)
            font_color: Font color as (r, g, b) tuple (if None, uses config value)
            rescale_type: Optional rescale type (e.g., "HU") to append to values
        """
        # Get font size and color from config if not provided
        if font_size is None:
            if self.config_manager is not None:
                resolved_font_size: int = self.config_manager.get_roi_font_size()
            else:
                resolved_font_size = 6  # Default
        else:
            resolved_font_size = font_size

        if font_color is None:
            if self.config_manager:
                font_color = self.config_manager.get_roi_font_color()
            else:
                font_color = (255, 255, 0)  # Default yellow
        font_family = self.config_manager.get_roi_font_family() if self.config_manager else "IBM Plex Sans"
        font_variant = self.config_manager.get_roi_font_variant() if self.config_manager else "Bold"
        # Format statistics text based on visible_statistics
        lines = []
        unit_suffix = f" {rescale_type}" if rescale_type else ""
        
        if "mean" in roi.visible_statistics and "mean" in statistics:
            lines.append(f"Mean: {statistics['mean']:.2f}{unit_suffix}")
        if "std" in roi.visible_statistics and "std" in statistics:
            lines.append(f"Std Dev: {statistics['std']:.2f}{unit_suffix}")
        if "min" in roi.visible_statistics and "min" in statistics:
            lines.append(f"Min: {statistics['min']:.2f}{unit_suffix}")
        if "max" in roi.visible_statistics and "max" in statistics:
            lines.append(f"Max: {statistics['max']:.2f}{unit_suffix}")
        mc = int(statistics.get("multichannel_count") or 0)
        if mc >= 2:
            raw_lbl = statistics.get("channel_labels")
            if isinstance(raw_lbl, (list, tuple)) and len(raw_lbl) == mc:
                labels = tuple(str(x) for x in raw_lbl)
            else:
                labels = tuple(f"Ch{i}" for i in range(mc))
            if "mean" in roi.visible_statistics:
                bits: list[str] = []
                for c in range(mc):
                    mk = f"mean_ch{c}"
                    if mk in statistics:
                        lab = labels[c] if c < len(labels) else str(c)
                        bits.append(f"{lab} μ={statistics[mk]:.2f}{unit_suffix}")
                if bits:
                    lines.append("Ch mean: " + "  ".join(bits))
            if "std" in roi.visible_statistics:
                bits_std: list[str] = []
                for c in range(mc):
                    sk = f"std_ch{c}"
                    if sk in statistics:
                        lab = labels[c] if c < len(labels) else str(c)
                        bits_std.append(f"{lab} σ={statistics[sk]:.2f}{unit_suffix}")
                if bits_std:
                    lines.append("Ch std: " + "  ".join(bits_std))
            if "min" in roi.visible_statistics:
                bits_min: list[str] = []
                for c in range(mc):
                    nk = f"min_ch{c}"
                    if nk in statistics:
                        lab = labels[c] if c < len(labels) else str(c)
                        bits_min.append(f"{lab} min={statistics[nk]:.2f}{unit_suffix}")
                if bits_min:
                    lines.append("Ch min: " + "  ".join(bits_min))
            if "max" in roi.visible_statistics:
                bits_max: list[str] = []
                for c in range(mc):
                    xk = f"max_ch{c}"
                    if xk in statistics:
                        lab = labels[c] if c < len(labels) else str(c)
                        bits_max.append(f"{lab} max={statistics[xk]:.2f}{unit_suffix}")
                if bits_max:
                    lines.append("Ch max: " + "  ".join(bits_max))
        if "count" in roi.visible_statistics and "count" in statistics:
            lines.append(f"Pixels: {statistics['count']}")
        if "area" in roi.visible_statistics:
            area_mm2 = statistics.get('area_mm2')
            if area_mm2 is not None:
                if area_mm2 >= 100:
                    lines.append(f"Area: {area_mm2/100:.2f} cm²")
                else:
                    lines.append(f"Area: {area_mm2:.2f} mm²")
            else:
                area_pixels = statistics.get('area_pixels', 0.0)
                lines.append(f"Area: {area_pixels:.1f} px")
        
        if not lines:
            return
        
        text = "\n".join(lines)
        
        # Create or reuse draggable text item
        def update_offset(offset_x: float, offset_y: float) -> None:
            """Update stored offset when overlay is moved."""
            roi.statistics_overlay_offset = (offset_x, offset_y)
        
        text_item = roi.statistics_overlay_item
        if text_item is None:
            text_item = DraggableStatisticsOverlay(roi, update_offset)
            # print(f"[DEBUG-OVERLAY] create_statistics_overlay: Created NEW overlay for ROI {id(roi)} in scene {id(scene)}")
        else:
            # Reuse existing overlay item, but ensure it's removed from any other scene first
            # This prevents overlays from appearing in multiple subwindows
            old_scene = text_item.scene()
            # print(f"[DEBUG-OVERLAY] create_statistics_overlay: REUSING overlay for ROI {id(roi)}, "
            #       f"old_scene={id(old_scene) if old_scene else None}, new_scene={id(scene)}")
            if old_scene is not None and old_scene != scene:
                # print(f"[DEBUG-OVERLAY]   WARNING: Overlay is in different scene! Removing from old scene {id(old_scene)}")
                old_scene.removeItem(text_item)
            text_item.roi = roi
            text_item.offset_update_callback = update_offset
            text_item.clear_deleted_flag()
        text_item.setDefaultTextColor(QColor(*font_color))
        
        # Set font - use absolute pixel size
        if resolved_font_size < 6:
            font = make_qfont(font_family, font_variant, 6)
            scale_factor = resolved_font_size / 6.0
            transform = QTransform()
            transform.scale(scale_factor, scale_factor)
            text_item.setTransform(transform)
        else:
            font = make_qfont(font_family, font_variant, resolved_font_size)
        
        text_item.setFont(font)
        text_item.setPlainText(text)
        
        # Set flag to ignore parent transformations (keeps font size consistent)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        # Make overlay draggable
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        text_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        text_item.setZValue(1001)  # Above ROI but below other overlays
        
        # Store reference to ROI in text item for position updates
        text_item.setData(0, id(roi))  # Store ROI id as user data
        
        # Position overlay near top-right corner of ROI bounds
        bounds = roi.get_bounds()
        # Use stored offset if available, otherwise use default
        offset_x, offset_y = roi.statistics_overlay_offset
        
        # Get view for coordinate conversion (needed for ItemIgnoresTransformations)
        view = scene.views()[0] if scene.views() else None
        if view is not None:
            view_scale = graphics_view_uniform_zoom(view)
            viewport_to_scene_scale = 1.0 / view_scale
            
            # Position at top-right corner of ROI bounds
            x_pos = bounds.right() + (offset_x * viewport_to_scene_scale)
            y_pos = bounds.top() + (offset_y * viewport_to_scene_scale)
        else:
            # Fallback: use scene coordinates directly
            x_pos = bounds.right() + offset_x
            y_pos = bounds.top() + offset_y
        
        text_item.setPos(x_pos, y_pos)
        
        # Connect to itemChange to track when overlay is moved
        # We'll handle this in update_statistics_overlay_position
        
        # Only add to scene if overlay is visible
        if roi.statistics_overlay_visible:
            # Ensure overlay is removed from any other scene first
            # This prevents overlays from appearing in multiple subwindows
            current_scene = text_item.scene()
            if current_scene is not None and current_scene != scene:
                # print(f"[DEBUG-OVERLAY]   Removing overlay from scene {id(current_scene)} before adding to scene {id(scene)}")
                current_scene.removeItem(text_item)
            # Now safe to add to new scene
            if text_item.scene() != scene:
                # print(f"[DEBUG-OVERLAY]   Adding overlay to scene {id(scene)}")
                scene.addItem(text_item)
            else:
                # print(f"[DEBUG-OVERLAY]   Overlay already in scene {id(scene)}")
                pass
            text_item.show()
        else:
            text_item.hide()
        
        roi.statistics_overlay_item = text_item
        # print(f"[DEBUG-OVERLAY]   Final state: overlay.scene()={id(text_item.scene()) if text_item.scene() else None}")
    
    def update_statistics_overlay(self, roi: ROIItem, statistics: RoiStatisticsMap,
                                 scene: QGraphicsScene, font_size: Optional[int] = None,
                                 font_color: Optional[Tuple[int, int, int]] = None,
                                 rescale_type: Optional[str] = None) -> None:
        """
        Update existing statistics overlay with new statistics.
        
        Args:
            roi: ROI item
            statistics: Statistics dictionary
            scene: QGraphicsScene
            font_size: Font size in points
            font_color: Font color as (r, g, b) tuple
            rescale_type: Optional rescale type (e.g., "HU") to append to values
        """
        # Recreate overlay with new statistics
        self.create_statistics_overlay(roi, statistics, scene, font_size, font_color, rescale_type)
    
    def update_statistics_overlay_position(self, roi: ROIItem, scene: QGraphicsScene) -> None:
        """
        Update statistics overlay position when ROI moves.
        
        Args:
            roi: ROI item
            scene: QGraphicsScene
        """
        if roi.statistics_overlay_item is None or roi.statistics is None:
            return
        
        # Get view for coordinate conversion
        view = scene.views()[0] if scene.views() else None
        bounds = roi.get_bounds()
        # Use stored offset
        offset_x, offset_y = roi.statistics_overlay_offset
        
        # Set updating flag to prevent recursive updates
        roi.statistics_overlay_item.set_updating_position(True)

        if view is not None:
            view_scale = graphics_view_uniform_zoom(view)
            viewport_to_scene_scale = 1.0 / view_scale
            
            x_pos = bounds.right() + (offset_x * viewport_to_scene_scale)
            y_pos = bounds.top() + (offset_y * viewport_to_scene_scale)
        else:
            x_pos = bounds.right() + offset_x
            y_pos = bounds.top() + offset_y
        
        roi.statistics_overlay_item.setPos(x_pos, y_pos)
        
        # Clear updating flag
        roi.statistics_overlay_item.set_updating_position(False)
    
    def remove_statistics_overlay(self, roi: ROIItem, scene: QGraphicsScene) -> None:
        """
        Remove statistics overlay from scene.
        
        Args:
            roi: ROI item
            scene: QGraphicsScene to remove item from
        """
        # print(f"[DEBUG-OVERLAY] remove_statistics_overlay called for ROI {id(roi)}")
        removed_any = False
        if roi.statistics_overlay_item is not None:
            overlay_item = roi.statistics_overlay_item
            # print(f"[DEBUG-OVERLAY] Removing overlay item {id(overlay_item)}")
            # Clear reference FIRST to prevent re-access
            roi.statistics_overlay_item = None
            # Disconnect overlay from ROI to prevent crashes
            if hasattr(overlay_item, 'roi'):
                overlay_item.roi = None
            if hasattr(overlay_item, 'mark_deleted'):
                overlay_item.mark_deleted()
            # Remove from scene if it's in the scene.
            # Guard against RuntimeError if the C++ object was already destroyed
            # (e.g. when scene.clear() was called externally before this method).
            try:
                if scene and overlay_item.scene() == scene:
                    scene.removeItem(overlay_item)
                    removed_any = True
            except RuntimeError:
                # C++ object already deleted; nothing left to remove
                pass
        else:
            # print(f"[DEBUG-OVERLAY] No overlay item reference to remove")
            pass
        
        # Fallback: search the scene for any text items tagged with this ROI id
        if scene is not None:
            items_to_remove = []
            for item in scene.items():
                if isinstance(item, QGraphicsTextItem):
                    if item.data(0) == id(roi):
                        items_to_remove.append(item)
            if items_to_remove:
                # print(f"[DEBUG-OVERLAY] Removing {len(items_to_remove)} orphan overlay items for ROI {id(roi)}")
                pass
            for item in items_to_remove:
                if hasattr(item, 'roi'):
                    item.roi = None
                if hasattr(item, 'mark_deleted'):
                    item.mark_deleted()
                scene.removeItem(item)
                removed_any = True
        
        if scene is not None and removed_any:
            scene.update()
            # print(f"[DEBUG-OVERLAY] Scene updated after overlay removal")
    
    def remove_all_statistics_overlays_from_scene(self, scene: QGraphicsScene) -> None:
        """
        Remove all statistics overlay items from the scene.
        This ensures orphaned overlays from previous slices are removed.
        
        CRITICAL: This method removes ALL statistics overlay items from the scene,
        regardless of which manager's ROIs they belong to. This prevents overlays
        from one subwindow appearing in another subwindow when focus changes.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        # print(f"[DEBUG-OVERLAY] remove_all_statistics_overlays_from_scene: scene={id(scene)}, roi_manager={id(self)}")
        
        # First, clear references in our own ROIs to prevent dangling references
        cleared_count = 0
        for roi_list in self.rois.values():
            for roi in roi_list:
                if roi.statistics_overlay_item is not None:
                    overlay_item = roi.statistics_overlay_item
                    overlay_scene = overlay_item.scene()
                    # Only clear the reference if the overlay is in the target scene
                    # This prevents clearing references to overlays in other scenes
                    if overlay_scene == scene:
                        # print(f"  Clearing reference for ROI {id(roi)} overlay (overlay in target scene)")
                        if hasattr(overlay_item, 'roi'):
                            overlay_item.roi = None
                        if hasattr(overlay_item, 'mark_deleted'):
                            overlay_item.mark_deleted()
                        cleared_count += 1
                    else:
                        # print(f"  Keeping reference for ROI {id(roi)} overlay (overlay in different scene {id(overlay_scene)})")
                        pass
                    roi.statistics_overlay_item = None
        # print(f"  Cleared {cleared_count} overlay references from ROIs in this manager")
        
        # Remove ALL statistics overlay items from the scene, regardless of which manager's ROIs they belong to
        # This is critical to prevent overlays from one subwindow appearing in another
        items_to_remove = []
        for item in scene.items():
            if isinstance(item, QGraphicsTextItem):
                # Check if this text item is a statistics overlay
                # Statistics overlays have ZValue 1001 and ItemIgnoresTransformations flag
                if (item.zValue() == 1001 and 
                    item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations):
                    items_to_remove.append(item)
        
        # print(f"  Found {len(items_to_remove)} statistics overlay items in scene to remove")
        
        # Remove all statistics overlay items found in the scene
        for item in items_to_remove:
            # Disconnect from any ROI reference
            roi_id = None
            if hasattr(item, 'roi') and item.roi:
                roi_id = id(item.roi)
            # print(f"  Removing overlay item {id(item)} (associated with ROI {roi_id})")
            if hasattr(item, 'roi'):
                item.roi = None
            if hasattr(item, 'mark_deleted'):
                item.mark_deleted()
            scene.removeItem(item)

        scene.update()
        # print(f"[DEBUG-OVERLAY] Finished removing overlays from scene {id(scene)}")
    
    def hide_all_statistics_overlays(self, scene: QGraphicsScene, hide: bool) -> None:
        """
        Hide or show all statistics overlays.
        
        Args:
            scene: QGraphicsScene
            hide: True to hide overlays, False to show them
        """
        for roi_list in self.rois.values():
            for roi in roi_list:
                if roi.statistics_overlay_item is not None:
                    if hide:
                        if roi.statistics_overlay_item.scene() == scene:
                            scene.removeItem(roi.statistics_overlay_item)
                    else:
                        # Show overlay if ROI has overlay enabled
                        if roi.statistics_overlay_visible and roi.statistics_overlay_item.scene() != scene:
                            scene.addItem(roi.statistics_overlay_item)

