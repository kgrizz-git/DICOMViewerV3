"""
Image Viewer Widget

This module implements the image display widget with zoom, pan, and
resizable display capabilities using QGraphicsView.

Inputs:
    - PIL Image objects or NumPy arrays
    - Zoom/pan user interactions
    - Window resize events
    
Outputs:
    - Displayed DICOM images
    - Zoom/pan state
    
Requirements:
    - PySide6 for graphics view
    - PIL/Pillow for image handling
    - numpy for array operations
"""

from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                                QWidget, QVBoxLayout, QMenu)
from PySide6.QtCore import Qt, QRectF, Signal, QPointF, QTimer
from PySide6.QtGui import (QPixmap, QImage, QWheelEvent, QKeyEvent, QMouseEvent,
                          QPainter, QColor, QTransform)
from PIL import Image
import numpy as np
from typing import Optional


class ImageViewer(QGraphicsView):
    """
    Image viewer widget with zoom and pan capabilities.
    
    Features:
    - Display DICOM images
    - Zoom with mouse wheel or gestures
    - Pan by dragging
    - Fit to window
    - Resizable display area
    """
    
    # Signals
    zoom_changed = Signal(float)  # Emitted when zoom level changes
    transform_changed = Signal()  # Emitted when view transform changes (zoom/pan)
    image_clicked = Signal(QPointF)  # Emitted when image is clicked
    roi_drawing_started = Signal(QPointF)  # Emitted when ROI drawing starts
    roi_drawing_updated = Signal(QPointF)  # Emitted when ROI drawing updates
    roi_drawing_finished = Signal()  # Emitted when ROI drawing finishes
    wheel_event_for_slice = Signal(int)  # Emitted when wheel event should navigate slices
    arrow_key_pressed = Signal(int)  # Emitted when arrow key is pressed (1 = up, -1 = down)
    roi_clicked = Signal(object)  # Emitted when ROI is clicked (ROIItem)
    roi_delete_requested = Signal(object)  # Emitted when ROI deletion is requested (QGraphicsItem)
    reset_view_requested = Signal()  # Emitted when reset view is requested from context menu
    context_menu_mouse_mode_changed = Signal(str)  # Emitted when mouse mode is changed from context menu
    context_menu_scroll_wheel_mode_changed = Signal(str)  # Emitted when scroll wheel mode is changed from context menu
    context_menu_rescale_toggle_changed = Signal(bool)  # Emitted when rescale toggle is changed from context menu
    window_level_drag_changed = Signal(float, float)  # Emitted when window/level is adjusted via right mouse drag (center_delta, width_delta)
    right_mouse_press_for_drag = Signal()  # Emitted when right mouse is pressed (not on ROI) to request window/level values for drag
    series_navigation_requested = Signal(int)  # Emitted when series navigation is requested (-1 for left/previous, 1 for right/next)
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the image viewer.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Set transformation anchor to viewport center for consistent zoom behavior
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        
        # Create graphics scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Image item
        self.image_item: Optional[QGraphicsPixmapItem] = None
        
        # Zoom settings
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_factor = 1.1  # Reduced from 1.15 for less sensitive scroll wheel zoom
        self.current_zoom = 1.0
        
        # Mouse interaction mode
        self.mouse_mode = "pan"  # "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan"
        
        # ROI drawing mode (derived from mouse_mode)
        self.roi_drawing_mode: Optional[str] = None  # "rectangle", "ellipse", or None
        self.roi_drawing_start: Optional[QPointF] = None
        
        # Zoom mode state
        self.zoom_start_pos: Optional[QPointF] = None
        self.zoom_start_zoom: Optional[float] = None
        
        # Scroll wheel mode
        self.scroll_wheel_mode = "slice"  # "slice" or "zoom"
        
        # Rescale toggle state (for context menu)
        self.use_rescaled_values = False
        
        # Track transform for change detection
        self.last_transform = QTransform()
        
        # Track scrollbar positions for panning detection
        self.last_horizontal_scroll = 0
        self.last_vertical_scroll = 0
        
        # Right mouse drag for window/level adjustment
        self.right_mouse_drag_start_pos: Optional[QPointF] = None
        self.right_mouse_drag_start_center: Optional[float] = None
        self.right_mouse_drag_start_width: Optional[float] = None
        self.right_mouse_context_menu_shown = False  # Track if context menu was shown
        
        # Sensitivity factors for window/level adjustment (pixels to units)
        # These will be set dynamically based on current ranges
        self.window_center_sensitivity = 1.0  # pixels per unit
        self.window_width_sensitivity = 1.0  # pixels per unit
        
        # View settings
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        # Transformation anchor is already set to AnchorViewCenter above for viewport-centered zoom
        # Resize anchor is already set to AnchorViewCenter above
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Enable focus to receive key events
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # Set scrollbar policies to allow scrollbars when content fits
        # ScrollBarAsNeeded allows scrollbars to appear when needed, but we'll enable them explicitly
        # when setting custom ranges for images that fit
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Connect scrollbar signals to detect panning
        # Panning via scrollbars doesn't change the transform, so we need to track scrollbar changes
        self.horizontalScrollBar().valueChanged.connect(self._on_scrollbar_changed)
        self.verticalScrollBar().valueChanged.connect(self._on_scrollbar_changed)
        
        # Background - darker grey for better yellow text contrast
        darker_grey = QColor(64, 64, 64)
        self.setBackgroundBrush(darker_grey)
    
    def _expand_scene_rect_for_panning(self) -> None:
        """
        Expand scene rect to enable panning when ScrollHandDrag is active.
        
        This creates a virtual panning area even when image fits viewport.
        When the image is smaller than the viewport, the scene rect will be
        at least 2 times the viewport dimensions in scene coordinates.
        """
        if self.image_item is None:
            return
        
        image_rect = self.image_item.boundingRect()
        if image_rect.isEmpty():
            return
        
        # Get viewport size in scene coordinates (at current zoom)
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        
        # Calculate viewport size in scene coordinates
        zoom = self.current_zoom if self.current_zoom > 0 else 1.0
        viewport_width_scene = viewport_width / zoom
        viewport_height_scene = viewport_height / zoom
        
        image_width = image_rect.width()
        image_height = image_rect.height()
        
        # Calculate the multiple: how many times larger is viewport than image?
        width_multiple = viewport_width_scene / image_width if image_width > 0 else 1.0
        height_multiple = viewport_height_scene / image_height if image_height > 0 else 1.0
        
        # Use the larger multiple
        target_multiple = max(width_multiple, height_multiple, 1.0)
        
        # When image is smaller than viewport (target_multiple > 1.0),
        # make scene rect at least 2x the viewport dimensions
        # This means scene rect = target_multiple * 2.0 times the image size
        if target_multiple > 1.0:
            # Image is smaller than viewport - scene rect should be 2x viewport
            scene_multiple = target_multiple * 2.0
        else:
            # Image is larger than or equal to viewport - use minimum 2x image size
            scene_multiple = 2.0
        
        # Calculate margins to make scene rect scene_multiple times the image size
        margin_x = image_width * (scene_multiple - 1.0) / 2.0
        margin_y = image_height * (scene_multiple - 1.0) / 2.0
        
        expanded_rect = QRectF(
            image_rect.x() - margin_x,
            image_rect.y() - margin_y,
            image_rect.width() + 2 * margin_x,
            image_rect.height() + 2 * margin_y
        )
        self.scene.setSceneRect(expanded_rect)
    
    def set_image(self, image: Image.Image, preserve_view: bool = False) -> None:
        """
        Set the image to display.
        
        Preserves existing ROIs and overlay items when changing images.
        
        Args:
            image: PIL Image to display
            preserve_view: If True, preserve current zoom and pan position
        """
        # Store current view state if preserving
        if preserve_view and self.image_item is not None:
            saved_zoom = self.current_zoom
            # Calculate viewport center in scene coordinates BEFORE changing anything
            viewport_center_viewport = QPointF(self.viewport().width() / 2.0, self.viewport().height() / 2.0)
            saved_scene_center = self.mapToScene(viewport_center_viewport.toPoint())
        else:
            saved_zoom = None
            saved_scene_center = None
        
        # Convert PIL Image to QPixmap
        if image.mode == 'L':
            # Grayscale
            qimage = QImage(image.tobytes(), image.width, image.height, 
                          QImage.Format.Format_Grayscale8)
        elif image.mode == 'RGB':
            # RGB
            qimage = QImage(image.tobytes(), image.width, image.height, 
                          QImage.Format.Format_RGB888)
        else:
            # Convert to RGB
            image = image.convert('RGB')
            qimage = QImage(image.tobytes(), image.width, image.height, 
                          QImage.Format.Format_RGB888)
        
        pixmap = QPixmap.fromImage(qimage)
        
        # Remove old image item only
        # Note: ROIs and overlays will be preserved and re-added by their managers
        if self.image_item is not None:
            self.scene.removeItem(self.image_item)
        
        # Create new image item
        self.image_item = QGraphicsPixmapItem(pixmap)
        # Set image item to lowest Z-value so other items appear on top
        self.image_item.setZValue(0)
        self.scene.addItem(self.image_item)
        
        # Set scene rect to image dimensions to ensure proper overlay positioning
        image_rect = self.image_item.boundingRect()
        
        # For ScrollHandDrag to work when image fits viewport, expand the scene rect
        # This creates a "virtual" panning area even when image fits viewport
        if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
            self._expand_scene_rect_for_panning()
        else:
            self.scene.setSceneRect(image_rect)
        
        if preserve_view and saved_zoom is not None:
            # Restore zoom and pan
            # First, reset transform and set zoom
            self.resetTransform()
            self.scale(saved_zoom, saved_zoom)
            self.current_zoom = saved_zoom
            
            # Update scrollbar ranges first (synchronously)
            self._update_scrollbar_ranges()
            
            # Restore viewport center using centerOn() with saved scene coordinates
            # This maintains the same visual position regardless of scene rect changes
            if saved_scene_center is not None:
                self.centerOn(saved_scene_center)
            
            self.last_transform = self.transform()
            self.zoom_changed.emit(self.current_zoom)
        else:
            # Reset zoom and fit to view
            self.current_zoom = 1.0
            self.fit_to_view()
            # fit_to_view() already calls _update_scrollbar_ranges() synchronously,
            # so no need to call it again here
    
    def fit_to_view(self) -> None:
        """Fit the image to the current view size."""
        if self.image_item is None:
            return
        
        # Get scene rect
        scene_rect = self.image_item.boundingRect()
        if scene_rect.isEmpty():
            return
        
        # Fit in view
        self.fitInView(scene_rect, Qt.AspectRatioMode.KeepAspectRatio)
        
        # Update zoom level
        transform = self.transform()
        self.current_zoom = transform.m11()
        self.last_transform = transform
        self.zoom_changed.emit(self.current_zoom)
        
        # If ScrollHandDrag is active, re-expand scene rect after fit_to_view
        # (fitInView doesn't change scene rect, but we want to ensure it's expanded)
        if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
            self._expand_scene_rect_for_panning()
        
        # Update scrollbar ranges to allow panning even when image fits
        # Center the image when fitting to view
        self._update_scrollbar_ranges(center_image=True)
    
    def zoom_in(self) -> None:
        """Zoom in on the image, centered on viewport center."""
        if self.image_item is None:
            return
        
        # Get viewport center
        viewport_center = QPointF(self.viewport().width() / 2.0, self.viewport().height() / 2.0)
        
        # Map viewport center to scene coordinates before zoom
        scene_center = self.mapToScene(viewport_center.toPoint())
        
        # Apply zoom
        self.scale(self.zoom_factor, self.zoom_factor)
        self.current_zoom *= self.zoom_factor
        if self.current_zoom > self.max_zoom:
            self.current_zoom = self.max_zoom
            # Recalculate if we hit max zoom
            current_scale = self.transform().m11()
            target_scale = self.max_zoom
            scale_factor = target_scale / current_scale
            self.scale(scale_factor, scale_factor)
        
        # Map viewport center to scene coordinates after zoom
        new_scene_center = self.mapToScene(viewport_center.toPoint())
        
        # Calculate translation needed to keep the same point under viewport center
        delta = scene_center - new_scene_center
        
        # Translate to maintain viewport center
        self.translate(delta.x(), delta.y())
        
        self.zoom_changed.emit(self.current_zoom)
        self._check_transform_changed()
        # Re-expand scene rect if ScrollHandDrag is active (viewport size in scene coords changed)
        if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
            self._expand_scene_rect_for_panning()
        # Update scrollbar ranges after zoom
        QTimer.singleShot(10, self._update_scrollbar_ranges)
    
    def zoom_out(self) -> None:
        """Zoom out from the image, centered on viewport center."""
        if self.image_item is None:
            return
        
        # Get viewport center
        viewport_center = QPointF(self.viewport().width() / 2.0, self.viewport().height() / 2.0)
        
        # Map viewport center to scene coordinates before zoom
        scene_center = self.mapToScene(viewport_center.toPoint())
        
        # Apply zoom
        self.scale(1.0 / self.zoom_factor, 1.0 / self.zoom_factor)
        self.current_zoom /= self.zoom_factor
        if self.current_zoom < self.min_zoom:
            self.current_zoom = self.min_zoom
            # Recalculate if we hit min zoom
            current_scale = self.transform().m11()
            target_scale = self.min_zoom
            scale_factor = target_scale / current_scale
            self.scale(scale_factor, scale_factor)
        
        # Map viewport center to scene coordinates after zoom
        new_scene_center = self.mapToScene(viewport_center.toPoint())
        
        # Calculate translation needed to keep the same point under viewport center
        delta = scene_center - new_scene_center
        
        # Translate to maintain viewport center
        self.translate(delta.x(), delta.y())
        
        self.zoom_changed.emit(self.current_zoom)
        self._check_transform_changed()
        # Re-expand scene rect if ScrollHandDrag is active (viewport size in scene coords changed)
        if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
            self._expand_scene_rect_for_panning()
        # Update scrollbar ranges after zoom
        QTimer.singleShot(10, self._update_scrollbar_ranges)
    
    def reset_zoom(self) -> None:
        """Reset zoom to 1:1."""
        self.resetTransform()
        self.current_zoom = 1.0
        self.zoom_changed.emit(self.current_zoom)
        self._check_transform_changed()
        # Re-expand scene rect if ScrollHandDrag is active (viewport size in scene coords changed)
        if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
            self._expand_scene_rect_for_panning()
    
    def set_scroll_wheel_mode(self, mode: str) -> None:
        """
        Set scroll wheel mode.
        
        Args:
            mode: "slice" or "zoom"
        """
        if mode in ["slice", "zoom"]:
            self.scroll_wheel_mode = mode
    
    def set_rescale_toggle_state(self, checked: bool) -> None:
        """
        Set the rescale toggle state (for context menu).
        
        Args:
            checked: True to use rescaled values, False to use raw values
        """
        self.use_rescaled_values = checked
    
    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Handle mouse wheel events for zooming or slice navigation.
        
        Args:
            event: Wheel event
        """
        # Use scroll wheel mode to determine behavior
        if self.scroll_wheel_mode == "zoom":
            # Zoom mode
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            # Slice navigation mode - emit signal for slice navigator
            self.wheel_event_for_slice.emit(event.angleDelta().y())
        
        event.accept()
    
    def set_mouse_mode(self, mode: str) -> None:
        """
        Set mouse interaction mode.
        
        Args:
            mode: "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", or "auto_window_level"
        """
        self.mouse_mode = mode
        
        # Update ROI drawing mode based on mouse mode
        if mode == "roi_ellipse":
            self.roi_drawing_mode = "ellipse"
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "roi_rectangle":
            self.roi_drawing_mode = "rectangle"
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "auto_window_level":
            # Auto window/level mode - use rectangle ROI drawing
            self.roi_drawing_mode = "rectangle"
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "measure":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)  # Could use different cursor
        elif mode == "zoom":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            # Store zoom start position for click-to-zoom
            self.zoom_start_pos: Optional[QPointF] = None
        else:  # pan
            self.roi_drawing_mode = None
            # Use ScrollHandDrag for panning - this works even when image fits viewport
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            # Ensure scrollbars are enabled for ScrollHandDrag to work
            self.horizontalScrollBar().setEnabled(True)
            self.verticalScrollBar().setEnabled(True)
            # Expand scene rect if image is loaded - this is critical for ScrollHandDrag to work
            # when image fits viewport. We need to do this here because set_image() might have
            # been called before pan mode was activated.
            self._expand_scene_rect_for_panning()
    
    def set_roi_drawing_mode(self, mode: Optional[str]) -> None:
        """
        Set ROI drawing mode (legacy method for backward compatibility).
        
        Args:
            mode: "rectangle", "ellipse", or None to disable
        """
        self.roi_drawing_mode = mode
        if mode:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse press events for panning or ROI drawing.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            # If ScrollHandDrag is active (pan mode), let Qt handle it unless clicking on ROI
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                # Check if clicking on ROI item first
                scene_pos = self.mapToScene(event.position().toPoint())
                item = self.scene.itemAt(scene_pos, self.transform())
                
                from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
                is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
                
                if is_roi_item:
                    # Clicking on ROI - disable ScrollHandDrag temporarily
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                    self.roi_clicked.emit(item)
                    return
                else:
                    # Not clicking on ROI - let ScrollHandDrag handle panning
                    # This is critical: we must let Qt handle the event for ScrollHandDrag to work
                    super().mousePressEvent(event)
                    return
            
            # For other modes, handle normally
            # First check if clicking on existing ROI item
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.transform())
            
            # Check if it's a ROI item (QGraphicsRectItem or QGraphicsEllipseItem)
            from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
            is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
            
            if is_roi_item:
                # Clicking on existing ROI - emit signal for ROI click
                self.roi_clicked.emit(item)
            elif self.mouse_mode == "zoom":
                # Zoom mode - start zoom operation
                self.zoom_start_pos = scene_pos
                self.zoom_start_zoom = self.current_zoom
            elif self.roi_drawing_mode:
                # Start ROI drawing only if not clicking on existing ROI
                self.roi_drawing_start = scene_pos
                self.roi_drawing_started.emit(scene_pos)
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click - prepare for potential drag or context menu
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.transform())
            
            # Check if it's a ROI item
            from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
            is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
            
            if is_roi_item:
                # Show context menu for ROI immediately
                context_menu = QMenu(self)
                delete_action = context_menu.addAction("Delete ROI")
                delete_action.triggered.connect(lambda: self.roi_delete_requested.emit(item))
                context_menu.exec(event.globalPosition().toPoint())
                self.right_mouse_context_menu_shown = True
                return
            else:
                # Not clicking on ROI - prepare for drag or context menu
                # Store initial position for potential drag
                self.right_mouse_drag_start_pos = event.position()
                self.right_mouse_context_menu_shown = False
                # Request window/level values from main.py
                self.right_mouse_press_for_drag.emit()
                return
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events for panning, ROI drawing, or zooming.
        
        Args:
            event: Mouse event
        """
        if self.mouse_mode == "zoom" and self.zoom_start_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            # Zoom mode - adjust zoom based on vertical drag distance
            # Ensure ScrollHandDrag is disabled for zoom mode
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            
            current_pos = event.position()
            start_pos = self.zoom_start_pos
            
            # Calculate vertical distance moved (in viewport coordinates)
            delta_y = current_pos.y() - start_pos.y()
            
            # Convert to zoom factor (negative delta = zoom in, positive = zoom out)
            zoom_delta = -delta_y / 300.0  # Reduced sensitivity (was 100.0)
            new_zoom = self.zoom_start_zoom * (1.0 + zoom_delta)
            
            # Clamp zoom
            new_zoom = max(self.min_zoom, min(self.max_zoom, new_zoom))
            
            # Apply zoom - AnchorViewCenter will automatically center on viewport center
            zoom_factor = new_zoom / self.current_zoom
            self.scale(zoom_factor, zoom_factor)
            self.current_zoom = new_zoom
            
            self.zoom_changed.emit(self.current_zoom)
            self._check_transform_changed()
            # Re-expand scene rect if ScrollHandDrag is active (viewport size in scene coords changed)
            # Note: ScrollHandDrag is disabled during zoom mode, but we check anyway for safety
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self._expand_scene_rect_for_panning()
        elif self.roi_drawing_mode and self.roi_drawing_start is not None:
            # ROI drawing mode - ensure ScrollHandDrag is disabled
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            
            if event.buttons() & Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                self.roi_drawing_updated.emit(scene_pos)
        elif event.buttons() & Qt.MouseButton.RightButton and self.right_mouse_drag_start_pos is not None:
            # Right mouse drag for window/level adjustment
            # Only if we have initial window/level values and context menu wasn't shown
            if (self.right_mouse_drag_start_center is not None and 
                self.right_mouse_drag_start_width is not None and
                not self.right_mouse_context_menu_shown):
                
                current_pos = event.position()
                start_pos = self.right_mouse_drag_start_pos
                
                # Calculate deltas (in viewport pixels)
                delta_x = current_pos.x() - start_pos.x()  # Horizontal: positive = right (wider), negative = left (narrower)
                delta_y = start_pos.y() - current_pos.y()  # Vertical: positive = up (higher center), negative = down (lower center)
                
                # Convert to window/level units using sensitivity
                center_delta = delta_y * self.window_center_sensitivity
                width_delta = delta_x * self.window_width_sensitivity
                
                # Emit signal with deltas
                self.window_level_drag_changed.emit(center_delta, width_delta)
        # Pan mode is handled automatically by ScrollHandDrag, no manual code needed
        # But we need to emit transform_changed signal when panning occurs
        # This is handled by connecting to scrollbar valueChanged signals
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse release events.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mouse_mode == "zoom" and self.zoom_start_pos is not None:
                # Finish zoom operation
                self.zoom_start_pos = None
                self.zoom_start_zoom = None
                # Restore ScrollHandDrag if we're in pan mode
                if self.mouse_mode == "pan":
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            elif self.roi_drawing_mode and self.roi_drawing_start is not None:
                # Finish ROI drawing
                self.roi_drawing_finished.emit()
                self.roi_drawing_start = None
                # Restore ScrollHandDrag if we're in pan mode
                if self.mouse_mode == "pan":
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            # Pan mode is handled automatically by ScrollHandDrag, no cleanup needed
        elif event.button() == Qt.MouseButton.RightButton:
            # Right mouse release - check if we were dragging or should show context menu
            if (self.right_mouse_drag_start_pos is not None and 
                not self.right_mouse_context_menu_shown):
                
                # Check if mouse moved significantly (drag threshold: 5 pixels)
                current_pos = event.position()
                start_pos = self.right_mouse_drag_start_pos
                drag_distance = ((current_pos.x() - start_pos.x()) ** 2 + 
                               (current_pos.y() - start_pos.y()) ** 2) ** 0.5
                
                if drag_distance < 5.0:
                    # Mouse didn't move much - show context menu
                    scene_pos = self.mapToScene(event.position().toPoint())
                    item = self.scene.itemAt(scene_pos, self.transform())
                    
                    from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
                    is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
                    
                    if not is_roi_item:
                        # Show context menu for image (not on ROI)
                        context_menu = QMenu(self)
                        
                        # Reset View action
                        reset_action = context_menu.addAction("Reset View")
                        reset_action.triggered.connect(self.reset_view_requested.emit)
                        
                        context_menu.addSeparator()
                        
                        # Series navigation actions
                        prev_series_action = context_menu.addAction("Prev Series")
                        prev_series_action.triggered.connect(lambda: self.series_navigation_requested.emit(-1))
                        
                        next_series_action = context_menu.addAction("Next Series")
                        next_series_action.triggered.connect(lambda: self.series_navigation_requested.emit(1))
                        
                        context_menu.addSeparator()
                        
                        # Left Mouse Button submenu
                        left_mouse_menu = context_menu.addMenu("Left Mouse Button")
                        left_mouse_actions = {
                            "Ellipse ROI": "roi_ellipse",
                            "Rectangle ROI": "roi_rectangle",
                            "Measure": "measure",
                            "Zoom": "zoom",
                            "Pan": "pan",
                            "Auto Window/Level": "auto_window_level"
                        }
                        for action_text, mode in left_mouse_actions.items():
                            action = left_mouse_menu.addAction(action_text)
                            action.setCheckable(True)
                            # Check the current mode
                            if self.mouse_mode == mode:
                                action.setChecked(True)
                            action.triggered.connect(
                                lambda checked, m=mode: self.context_menu_mouse_mode_changed.emit(m)
                            )
                        
                        context_menu.addSeparator()
                        
                        # Scroll Wheel Mode submenu
                        scroll_wheel_menu = context_menu.addMenu("Scroll Wheel Mode")
                        slice_action = scroll_wheel_menu.addAction("Slice")
                        slice_action.setCheckable(True)
                        if self.scroll_wheel_mode == "slice":
                            slice_action.setChecked(True)
                        slice_action.triggered.connect(
                            lambda: self.context_menu_scroll_wheel_mode_changed.emit("slice")
                        )
                        
                        zoom_action = scroll_wheel_menu.addAction("Zoom")
                        zoom_action.setCheckable(True)
                        if self.scroll_wheel_mode == "zoom":
                            zoom_action.setChecked(True)
                        zoom_action.triggered.connect(
                            lambda: self.context_menu_scroll_wheel_mode_changed.emit("zoom")
                        )
                        
                        context_menu.addSeparator()
                        
                        # Use Raw Pixel Values action
                        use_raw_action = context_menu.addAction("Use Raw Pixel Values")
                        use_raw_action.setCheckable(True)
                        use_raw_action.setChecked(not self.use_rescaled_values)  # Checked when using raw values
                        use_raw_action.triggered.connect(
                            lambda: self.context_menu_rescale_toggle_changed.emit(False)
                        )
                        
                        # Use Rescaled Values action
                        use_rescaled_action = context_menu.addAction("Use Rescaled Values")
                        use_rescaled_action.setCheckable(True)
                        use_rescaled_action.setChecked(self.use_rescaled_values)  # Checked when using rescaled values
                        use_rescaled_action.triggered.connect(
                            lambda: self.context_menu_rescale_toggle_changed.emit(True)
                        )
                        
                        context_menu.exec(event.globalPosition().toPoint())
            
            # Reset right mouse drag tracking
            self.right_mouse_drag_start_pos = None
            self.right_mouse_drag_start_center = None
            self.right_mouse_drag_start_width = None
            self.right_mouse_context_menu_shown = False
        
        super().mouseReleaseEvent(event)
    
    def keyPressEvent(self, event: QKeyEvent) -> None:
        """
        Handle key press events for arrow key navigation.
        
        Args:
            event: Key event
        """
        if event.key() == Qt.Key.Key_Up:
            # Up arrow: next slice
            self.arrow_key_pressed.emit(1)
            event.accept()
        elif event.key() == Qt.Key.Key_Down:
            # Down arrow: previous slice
            self.arrow_key_pressed.emit(-1)
            event.accept()
        elif event.key() == Qt.Key.Key_Left:
            # Left arrow: previous series
            self.series_navigation_requested.emit(-1)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            # Right arrow: next series
            self.series_navigation_requested.emit(1)
            event.accept()
        else:
            super().keyPressEvent(event)
    
    def set_window_level_for_drag(self, center: float, width: float, 
                                   center_range: tuple, width_range: tuple) -> None:
        """
        Set window/level values for right mouse drag adjustment.
        Also updates sensitivity based on ranges.
        
        Args:
            center: Current window center value
            width: Current window width value
            center_range: (min, max) range for window center
            width_range: (min, max) range for window width
        """
        self.right_mouse_drag_start_center = center
        self.right_mouse_drag_start_width = width
        
        # Calculate sensitivity based on ranges
        # Sensitivity: pixels per unit
        # Use a reasonable default: 1 pixel = 1% of range
        center_range_size = center_range[1] - center_range[0]
        width_range_size = width_range[1] - width_range[0]
        
        if center_range_size > 0:
            # 100 pixels of movement = 10% of range
            self.window_center_sensitivity = center_range_size / 1000.0
        else:
            self.window_center_sensitivity = 1.0
        
        if width_range_size > 0:
            # 100 pixels of movement = 10% of range
            self.window_width_sensitivity = width_range_size / 1000.0
        else:
            self.window_width_sensitivity = 1.0
    
    def _check_transform_changed(self) -> None:
        """
        Check if transform has changed and emit signal if so.
        
        Uses QTimer to delay signal emission slightly to ensure transform is fully applied.
        """
        current_transform = self.transform()
        if current_transform != self.last_transform:
            self.last_transform = current_transform
            # Use QTimer to delay signal emission slightly, ensuring transform is fully applied
            QTimer.singleShot(10, lambda: self.transform_changed.emit())
    
    def _update_scrollbar_ranges(self, center_image: bool = False) -> None:
        """
        Update scrollbar ranges to allow panning even when image fully fits in viewport.
        
        Ensures at least one pixel of the image remains visible when panning.
        Scrollbars are calculated so that when at the center of their range, the image center
        aligns with the viewport center.
        QGraphicsView scrollbars work in scene coordinates.
        
        NOTE: This method should NOT be called when ScrollHandDrag is active,
        as Qt manages scrollbars automatically in that mode. Calling this method
        when ScrollHandDrag is active causes conflicts, leading to jittering and
        panning failures.
        
        Args:
            center_image: If True, center the scrollbars to align image center with viewport center
        """
        # Skip custom scrollbar range management when ScrollHandDrag is active
        # Qt handles scrollbars automatically in ScrollHandDrag mode, and our
        # custom range updates interfere with Qt's management, causing jittering
        # and preventing panning from working properly.
        if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
            return
        
        if self.image_item is None:
            return
        
        # Get scene rect (image bounds)
        scene_rect = self.image_item.boundingRect()
        if scene_rect.isEmpty():
            return
        
        scene_width = scene_rect.width()
        scene_height = scene_rect.height()
        
        # Get viewport size
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        
        # Get current zoom level
        zoom = self.current_zoom
        
        # Calculate scaled image size (in viewport pixels)
        scaled_width = scene_width * zoom
        scaled_height = scene_height * zoom
        
        # Calculate viewport size in scene coordinates
        viewport_width_scene = viewport_width / zoom if zoom > 0 else viewport_width
        viewport_height_scene = viewport_height / zoom if zoom > 0 else viewport_height
        
        # Image center in scene coordinates
        image_center_x = scene_width / 2.0
        image_center_y = scene_height / 2.0
        
        # Viewport center in scene coordinates
        viewport_center_x = viewport_width_scene / 2.0
        viewport_center_y = viewport_height_scene / 2.0
        
        # Update horizontal scrollbar range
        if scaled_width > viewport_width:
            # Image is larger than viewport - QGraphicsView handles range automatically
            # But we can still ensure centering works by not interfering
            pass
        else:
            # Image fits horizontally - calculate symmetric range based on actual panning limits
            # The scrollbar value represents the scene position of the viewport's left edge
            # 1 pixel in viewport = 1/zoom in scene coords
            min_pixel_size = 1.0 / zoom if zoom > 0 else 1.0
            
            # Calculate panning limits:
            # Minimum scrollbar value: pan right until 1 pixel visible at left edge
            # Viewport left edge at: min_pixel_size
            h_min = int(min_pixel_size)
            
            # Maximum scrollbar value: pan left until 1 pixel visible at right edge
            # Viewport right edge at: scene_width - min_pixel_size
            # Viewport left edge at: scene_width - min_pixel_size - viewport_width_scene
            h_max = int(scene_width - viewport_width_scene - min_pixel_size)
            
            # Ensure valid range
            if h_max < h_min:
                # If image is very small, ensure at least some range
                h_max = h_min + 1
            
            # Center value: when image center aligns with viewport center
            # This should be at the midpoint of the range
            center_value = (scene_width - viewport_width_scene) / 2.0
            
            # Verify center is at midpoint (should always be true with correct calculation)
            # center_value should equal (h_min + h_max) / 2
            
            # Store current scrollbar value and old range before changing range
            current_h_value = self.horizontalScrollBar().value()
            old_h_min = self.horizontalScrollBar().minimum()
            old_h_max = self.horizontalScrollBar().maximum()
            old_h_range = old_h_max - old_h_min
            
            self.horizontalScrollBar().setRange(h_min, h_max)
            # Set page step to viewport width in scene coordinates
            self.horizontalScrollBar().setPageStep(int(viewport_width_scene))
            
            # Set scrollbar value: center if requested, otherwise preserve relative position
            if center_image:
                # Center the scrollbar to align image center with viewport center
                center_scrollbar_value = int(center_value)
                # Clamp to range
                center_scrollbar_value = max(h_min, min(h_max, center_scrollbar_value))
                self.horizontalScrollBar().setValue(center_scrollbar_value)
            else:
                # Preserve relative position in the new range
                if old_h_range > 0:
                    # Calculate relative position (0.0 to 1.0) in old range
                    relative_pos = (current_h_value - old_h_min) / old_h_range
                    # Map to new range
                    new_value = h_min + int(relative_pos * (h_max - h_min))
                    new_value = max(h_min, min(h_max, new_value))
                    self.horizontalScrollBar().setValue(new_value)
                else:
                    # No previous range, center it
                    center_scrollbar_value = int(center_value)
                    center_scrollbar_value = max(h_min, min(h_max, center_scrollbar_value))
                    self.horizontalScrollBar().setValue(center_scrollbar_value)
            
            # Explicitly enable scrollbar to allow panning even when image fits
            # QGraphicsView may disable scrollbars when content fits, so we force enable
            self.horizontalScrollBar().setEnabled(True)
            # Ensure scrollbar is visible and functional immediately
            self.horizontalScrollBar().show()
            self.horizontalScrollBar().update()
        
        # Update vertical scrollbar range
        if scaled_height > viewport_height:
            # Image is larger than viewport - QGraphicsView handles range automatically
            pass
        else:
            # Image fits vertically - calculate symmetric range based on actual panning limits
            # The scrollbar value represents the scene position of the viewport's top edge
            # 1 pixel in viewport = 1/zoom in scene coords
            min_pixel_size = 1.0 / zoom if zoom > 0 else 1.0
            
            # Calculate panning limits:
            # Minimum scrollbar value: pan down until 1 pixel visible at top edge
            # Viewport top edge at: min_pixel_size
            v_min = int(min_pixel_size)
            
            # Maximum scrollbar value: pan up until 1 pixel visible at bottom edge
            # Viewport bottom edge at: scene_height - min_pixel_size
            # Viewport top edge at: scene_height - min_pixel_size - viewport_height_scene
            v_max = int(scene_height - viewport_height_scene - min_pixel_size)
            
            # Ensure valid range
            if v_max < v_min:
                # If image is very small, ensure at least some range
                v_max = v_min + 1
            
            # Center value: when image center aligns with viewport center
            # This should be at the midpoint of the range
            center_value = (scene_height - viewport_height_scene) / 2.0
            
            # Verify center is at midpoint (should always be true with correct calculation)
            # center_value should equal (v_min + v_max) / 2
            
            # Store current scrollbar value and old range before changing range
            current_v_value = self.verticalScrollBar().value()
            old_v_min = self.verticalScrollBar().minimum()
            old_v_max = self.verticalScrollBar().maximum()
            old_v_range = old_v_max - old_v_min
            
            self.verticalScrollBar().setRange(v_min, v_max)
            # Set page step to viewport height in scene coordinates
            self.verticalScrollBar().setPageStep(int(viewport_height_scene))
            
            # Set scrollbar value: center if requested, otherwise preserve relative position
            if center_image:
                # Center the scrollbar to align image center with viewport center
                center_scrollbar_value = int(center_value)
                # Clamp to range
                center_scrollbar_value = max(v_min, min(v_max, center_scrollbar_value))
                self.verticalScrollBar().setValue(center_scrollbar_value)
            else:
                # Preserve relative position in the new range
                if old_v_range > 0:
                    # Calculate relative position (0.0 to 1.0) in old range
                    relative_pos = (current_v_value - old_v_min) / old_v_range
                    # Map to new range
                    new_value = v_min + int(relative_pos * (v_max - v_min))
                    new_value = max(v_min, min(v_max, new_value))
                    self.verticalScrollBar().setValue(new_value)
                else:
                    # No previous range, center it
                    center_scrollbar_value = int(center_value)
                    center_scrollbar_value = max(v_min, min(v_max, center_scrollbar_value))
                    self.verticalScrollBar().setValue(center_scrollbar_value)
            
            # Explicitly enable scrollbar to allow panning even when image fits
            # QGraphicsView may disable scrollbars when content fits, so we force enable
            self.verticalScrollBar().setEnabled(True)
            # Ensure scrollbar is visible and functional immediately
            self.verticalScrollBar().show()
            self.verticalScrollBar().update()
    
    def _on_scrollbar_changed(self) -> None:
        """
        Handle scrollbar value changes (panning).
        
        When panning via scrollbars, the view's transform doesn't change,
        but the viewport-to-scene mapping does change. We need to update
        overlay positions to keep them anchored to viewport edges.
        """
        # Check if scrollbar values actually changed
        current_h = self.horizontalScrollBar().value()
        current_v = self.verticalScrollBar().value()
        
        if current_h != self.last_horizontal_scroll or current_v != self.last_vertical_scroll:
            self.last_horizontal_scroll = current_h
            self.last_vertical_scroll = current_v
            # Emit transform_changed signal to update overlay positions
            # Use QTimer to batch rapid scrollbar changes
            QTimer.singleShot(10, lambda: self.transform_changed.emit())
    
    def resizeEvent(self, event) -> None:
        """
        Handle resize events.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        # Update scrollbar ranges after resize
        QTimer.singleShot(10, self._update_scrollbar_ranges)
        # Emit transform_changed signal to update overlay positions
        # Viewport size change affects overlay positioning
        QTimer.singleShot(10, lambda: self.transform_changed.emit())
        # Optionally auto-fit on resize
        # self.fit_to_view()

