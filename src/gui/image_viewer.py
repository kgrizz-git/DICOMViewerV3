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
    image_clicked_no_roi = Signal()  # Emitted when image is clicked but not on an ROI (for deselection)
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
    measurement_started = Signal(QPointF)  # Emitted when measurement starts (start position)
    measurement_updated = Signal(QPointF)  # Emitted when measurement is updated (current position)
    measurement_finished = Signal()  # Emitted when measurement is finished
    measurement_delete_requested = Signal(object)  # Emitted when measurement deletion is requested (MeasurementItem)
    clear_measurements_requested = Signal()  # Emitted when clear measurements is requested
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the image viewer.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Set transformation anchor to viewport center for consistent zoom behavior
        # This anchor should remain constant - when set, scale() automatically centers zooming on viewport center
        # No manual translation is needed when using scale() with AnchorViewCenter
        self.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        # Set alignment to center the scene when it's smaller than viewport
        # This ensures small images are centered, not positioned at top-left
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
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
        
        # Measurement state
        self.measuring = False
        self.measurement_start_pos: Optional[QPointF] = None
        
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
        
        # Calculate fixed scene rect size that accommodates:
        # - Image size with 5x multiplier for margin
        # - Viewport size at minimum zoom with 2x multiplier for margin
        # This ensures mapToScene() accuracy at all zoom levels without recalculation
        image_width = image_rect.width()
        image_height = image_rect.height()
        
        # Calculate viewport size in scene coordinates at minimum zoom
        viewport_width = self.viewport().width()
        viewport_height = self.viewport().height()
        viewport_at_min_zoom_width = viewport_width / self.min_zoom if self.min_zoom > 0 else viewport_width
        viewport_at_min_zoom_height = viewport_height / self.min_zoom if self.min_zoom > 0 else viewport_height
        
        # Scene rect should be at least 5x image size, or 2x viewport at min zoom, whichever is larger
        scene_width = max(image_width * 5.0, viewport_at_min_zoom_width * 2.0)
        scene_height = max(image_height * 5.0, viewport_at_min_zoom_height * 2.0)
        
        # Calculate margins to center the image in the expanded scene rect
        margin_x = (scene_width - image_width) / 2.0
        margin_y = (scene_height - image_height) / 2.0
        
        expanded_rect = QRectF(
            image_rect.x() - margin_x,
            image_rect.y() - margin_y,
            scene_width,
            scene_height
        )
        self.scene.setSceneRect(expanded_rect)
        
        # Centering is now handled by fit_to_view() when appropriate
        # Don't center here as fit_to_view() will be called and may override it
        
        if preserve_view and saved_zoom is not None:
            # Restore zoom and pan
            # First, reset transform and set zoom
            self.resetTransform()
            self.scale(saved_zoom, saved_zoom)
            self.current_zoom = saved_zoom
            
            # Restore viewport center using centerOn() with saved scene coordinates
            # This maintains the same visual position regardless of scene rect changes
            if saved_scene_center is not None:
                self.centerOn(saved_scene_center)
            
            self.last_transform = self.transform()
            self.zoom_changed.emit(self.current_zoom)
        else:
            # Reset zoom and fit to view
            # Don't center here - centering should only happen when initializing new series or resetting view
            self.current_zoom = 1.0
            self.fit_to_view(center_image=False)
    
    def fit_to_view(self, center_image: bool = False) -> None:
        """
        Fit the image to the current view size.
        
        Args:
            center_image: If True, center the image in the viewport (for initialization/reset).
                         If False, preserve current view position.
        """
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
        
        # If image is smaller than viewport and center_image is True, manually center it
        # fitInView() may not center properly with AnchorViewCenter when image is smaller
        if center_image:
            viewport_width = self.viewport().width()
            viewport_height = self.viewport().height()
            scaled_width = scene_rect.width() * self.current_zoom
            scaled_height = scene_rect.height() * self.current_zoom
            
            if scaled_width < viewport_width or scaled_height < viewport_height:
                # Image is smaller than viewport - center it
                image_center = scene_rect.center()
                self.centerOn(image_center)
    
    def zoom_in(self) -> None:
        """Zoom in on the image, centered on viewport center."""
        if self.image_item is None:
            return
        
        # AnchorViewCenter is set in __init__ and should remain constant
        # When AnchorViewCenter is set, scale() automatically centers zooming on viewport center
        # No manual translation is needed
        
        # Calculate new zoom level
        new_zoom = self.current_zoom * self.zoom_factor
        
        # Clamp to max zoom
        if new_zoom > self.max_zoom:
            new_zoom = self.max_zoom
        
        # Calculate scale factor needed to reach target zoom
        current_scale = self.transform().m11()
        scale_factor = new_zoom / current_scale
        
        # Apply zoom - AnchorViewCenter ensures it's centered on viewport center
        self.scale(scale_factor, scale_factor)
        self.current_zoom = new_zoom
        
        self.zoom_changed.emit(self.current_zoom)
        self._check_transform_changed()
    
    def zoom_out(self) -> None:
        """Zoom out from the image, centered on viewport center."""
        if self.image_item is None:
            return
        
        # AnchorViewCenter is set in __init__ and should remain constant
        # When AnchorViewCenter is set, scale() automatically centers zooming on viewport center
        # No manual translation is needed
        
        # Calculate new zoom level
        new_zoom = self.current_zoom / self.zoom_factor
        
        # Clamp to min zoom
        if new_zoom < self.min_zoom:
            new_zoom = self.min_zoom
        
        # Calculate scale factor needed to reach target zoom
        current_scale = self.transform().m11()
        scale_factor = new_zoom / current_scale
        
        # Apply zoom - AnchorViewCenter ensures it's centered on viewport center
        self.scale(scale_factor, scale_factor)
        self.current_zoom = new_zoom
        
        self.zoom_changed.emit(self.current_zoom)
        self._check_transform_changed()
    
    def reset_zoom(self) -> None:
        """Reset zoom to 1:1."""
        self.resetTransform()
        self.current_zoom = 1.0
        self.zoom_changed.emit(self.current_zoom)
        self._check_transform_changed()
    
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
            # Perform zoom - AnchorViewCenter is set in __init__ and ensures zooming is centered on viewport center
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
            mode: "select", "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan", or "auto_window_level"
        """
        self.mouse_mode = mode
        
        # Update ROI drawing mode based on mouse mode
        if mode == "select":
            # Select mode - allow clicking on ROIs and measurements to select them
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif mode == "roi_ellipse":
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
            # Reset measurement state when switching to measure mode
            self.measuring = False
            self.measurement_start_pos = None
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
            # Handle select mode - allow default Qt selection behavior
            if self.mouse_mode == "select":
                # Let Qt handle selection of ROIs and measurements
                super().mousePressEvent(event)
                return
            
            # If ScrollHandDrag is active (pan mode), let Qt handle it unless clicking on ROI
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                # Check if clicking on ROI item first
                scene_pos = self.mapToScene(event.position().toPoint())
                item = self.scene.itemAt(scene_pos, self.transform())
                
                from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
                # Check if item is an ROI item (but not the image item)
                is_roi_item = (item is not None and 
                              item != self.image_item and
                              isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)))
                
                if is_roi_item:
                    # Clicking on ROI - disable ScrollHandDrag temporarily
                    self.setDragMode(QGraphicsView.DragMode.NoDrag)
                    self.roi_clicked.emit(item)
                    return
                else:
                    # Not clicking on ROI (clicking on image item, empty space, or other items) - emit signal for deselection
                    # Emit before calling super() to ensure signal is processed
                    self.image_clicked_no_roi.emit()
                    # This is critical: we must let Qt handle the event for ScrollHandDrag to work
                    super().mousePressEvent(event)
                    return
            
            # For other modes, handle normally
            # First check if clicking on existing ROI item
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.transform())
            
            # Check if it's a ROI item (QGraphicsRectItem or QGraphicsEllipseItem) but not the image item
            from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
            is_roi_item = (item is not None and 
                          item != self.image_item and
                          isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)))
            
            if is_roi_item:
                # Clicking on existing ROI - emit signal for ROI click
                self.roi_clicked.emit(item)
            elif item is None or item == self.image_item:
                # Clicking on empty space or image item - emit deselection signal
                self.image_clicked_no_roi.emit()
                # Continue with mode-specific handling
                if self.mouse_mode == "zoom":
                    # Zoom mode - start zoom operation
                    self.zoom_start_pos = scene_pos
                    self.zoom_start_zoom = self.current_zoom
                elif self.mouse_mode == "measure":
                    # Measurement mode - start or finish measurement
                    if not self.measuring:
                        # Start new measurement
                        self.measuring = True
                        self.measurement_start_pos = scene_pos
                        self.measurement_started.emit(scene_pos)
                    else:
                        # Finish current measurement
                        self.measuring = False
                        self.measurement_start_pos = None
                        self.measurement_finished.emit()
                elif self.roi_drawing_mode:
                    # Start ROI drawing
                    self.roi_drawing_start = scene_pos
                    self.roi_drawing_started.emit(scene_pos)
            elif self.mouse_mode == "zoom":
                # Zoom mode - start zoom operation (clicking on overlay or other items)
                self.zoom_start_pos = scene_pos
                self.zoom_start_zoom = self.current_zoom
                # Emit signal for clicking on image (not ROI) to allow deselection
                self.image_clicked_no_roi.emit()
            elif self.mouse_mode == "measure":
                # Measurement mode - start or finish measurement
                if not self.measuring:
                    # Start new measurement
                    self.measuring = True
                    self.measurement_start_pos = scene_pos
                    self.measurement_started.emit(scene_pos)
                else:
                    # Finish current measurement
                    self.measuring = False
                    self.measurement_start_pos = None
                    self.measurement_finished.emit()
            elif self.roi_drawing_mode:
                # Start ROI drawing only if not clicking on existing ROI
                self.roi_drawing_start = scene_pos
                self.roi_drawing_started.emit(scene_pos)
            else:
                # Clicking on other items (overlay, etc.) but not on ROI - allow deselection
                self.image_clicked_no_roi.emit()
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click - prepare for potential drag or context menu
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.transform())
            
            # Check if it's a ROI item or measurement item
            from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
            from tools.measurement_tool import MeasurementItem
            is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
            is_measurement_item = isinstance(item, MeasurementItem)
            
            if is_roi_item:
                # Show context menu for ROI immediately
                context_menu = QMenu(self)
                delete_action = context_menu.addAction("Delete ROI")
                delete_action.triggered.connect(lambda: self.roi_delete_requested.emit(item))
                context_menu.exec(event.globalPosition().toPoint())
                self.right_mouse_context_menu_shown = True
                return
            elif is_measurement_item:
                # Show context menu for measurement immediately
                context_menu = QMenu(self)
                delete_action = context_menu.addAction("Delete measurement")
                delete_action.triggered.connect(lambda: self.measurement_delete_requested.emit(item))
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
        # In select mode, allow default Qt behavior (selection dragging, etc.)
        if self.mouse_mode == "select":
            super().mouseMoveEvent(event)
            return
        
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
            
            # Apply zoom - AnchorViewCenter is set in __init__ and ensures zooming is centered on viewport center
            # Calculate scale factor from current transform for consistency with zoom_in/zoom_out
            current_scale = self.transform().m11()
            scale_factor = new_zoom / current_scale
            self.scale(scale_factor, scale_factor)
            self.current_zoom = new_zoom
            
            self.zoom_changed.emit(self.current_zoom)
            self._check_transform_changed()
        elif self.mouse_mode == "measure" and self.measuring and self.measurement_start_pos is not None:
            # Measurement mode - update measurement while dragging
            if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
            
            if event.buttons() & Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                self.measurement_updated.emit(scene_pos)
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
        # In select mode, allow default Qt behavior
        if self.mouse_mode == "select":
            super().mouseReleaseEvent(event)
            return
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mouse_mode == "zoom" and self.zoom_start_pos is not None:
                # Finish zoom operation
                self.zoom_start_pos = None
                self.zoom_start_zoom = None
                # Restore ScrollHandDrag if we're in pan mode
                if self.mouse_mode == "pan":
                    self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            elif self.mouse_mode == "measure" and self.measuring:
                # Finish measurement (if not already finished by second click)
                self.measuring = False
                self.measurement_start_pos = None
                self.measurement_finished.emit()
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
                    from tools.measurement_tool import MeasurementItem
                    is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
                    is_measurement_item = isinstance(item, MeasurementItem)
                    
                    if not is_roi_item and not is_measurement_item:
                        # Show context menu for image (not on ROI)
                        context_menu = QMenu(self)
                        
                        # Reset View action
                        reset_action = context_menu.addAction("Reset View")
                        reset_action.triggered.connect(self.reset_view_requested.emit)
                        
                        # Clear Measurements action
                        clear_measurements_action = context_menu.addAction("Clear Measurements")
                        clear_measurements_action.triggered.connect(self.clear_measurements_requested.emit)
                        
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
                            "Select": "select",
                            "Ellipse ROI": "roi_ellipse",
                            "Rectangle ROI": "roi_rectangle",
                            "Measure": "measure",
                            "Zoom": "zoom",
                            "Pan": "pan",
                            "Window/Level ROI": "auto_window_level"
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
        # Emit transform_changed signal to update overlay positions
        # Viewport size change affects overlay positioning
        QTimer.singleShot(10, lambda: self.transform_changed.emit())
        # Optionally auto-fit on resize
        # self.fit_to_view()

