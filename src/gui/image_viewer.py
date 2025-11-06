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
                                QWidget, QVBoxLayout)
from PySide6.QtCore import Qt, QRectF, Signal, QPointF
from PySide6.QtGui import (QPixmap, QImage, QWheelEvent, QKeyEvent, QMouseEvent,
                          QPainter)
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
    image_clicked = Signal(QPointF)  # Emitted when image is clicked
    roi_drawing_started = Signal(QPointF)  # Emitted when ROI drawing starts
    roi_drawing_updated = Signal(QPointF)  # Emitted when ROI drawing updates
    roi_drawing_finished = Signal()  # Emitted when ROI drawing finishes
    wheel_event_for_slice = Signal(int)  # Emitted when wheel event should navigate slices
    roi_clicked = Signal(object)  # Emitted when ROI is clicked (ROIItem)
    
    def __init__(self, parent: Optional[QWidget] = None):
        """
        Initialize the image viewer.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Create graphics scene
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Image item
        self.image_item: Optional[QGraphicsPixmapItem] = None
        
        # Zoom settings
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_factor = 1.15
        self.current_zoom = 1.0
        
        # Pan settings
        self.pan_start_pos = QPointF()
        self.panning = False
        
        # Mouse interaction mode
        self.mouse_mode = "pan"  # "roi_ellipse", "roi_rectangle", "measure", "zoom", "pan"
        
        # ROI drawing mode (derived from mouse_mode)
        self.roi_drawing_mode: Optional[str] = None  # "rectangle", "ellipse", or None
        self.roi_drawing_start: Optional[QPointF] = None
        
        # Scroll wheel mode
        self.scroll_wheel_mode = "slice"  # "slice" or "zoom"
        
        # View settings
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Background
        self.setBackgroundBrush(Qt.GlobalColor.darkGray)
    
    def set_image(self, image: Image.Image) -> None:
        """
        Set the image to display.
        
        Preserves existing ROIs and overlay items when changing images.
        
        Args:
            image: PIL Image to display
        """
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
        
        # Reset zoom and fit to view
        self.current_zoom = 1.0
        self.fit_to_view()
    
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
        self.zoom_changed.emit(self.current_zoom)
    
    def zoom_in(self) -> None:
        """Zoom in on the image."""
        self.scale(self.zoom_factor, self.zoom_factor)
        self.current_zoom *= self.zoom_factor
        if self.current_zoom > self.max_zoom:
            self.current_zoom = self.max_zoom
        self.zoom_changed.emit(self.current_zoom)
    
    def zoom_out(self) -> None:
        """Zoom out from the image."""
        self.scale(1.0 / self.zoom_factor, 1.0 / self.zoom_factor)
        self.current_zoom /= self.zoom_factor
        if self.current_zoom < self.min_zoom:
            self.current_zoom = self.min_zoom
        self.zoom_changed.emit(self.current_zoom)
    
    def reset_zoom(self) -> None:
        """Reset zoom to 1:1."""
        self.resetTransform()
        self.current_zoom = 1.0
        self.zoom_changed.emit(self.current_zoom)
    
    def set_scroll_wheel_mode(self, mode: str) -> None:
        """
        Set scroll wheel mode.
        
        Args:
            mode: "slice" or "zoom"
        """
        if mode in ["slice", "zoom"]:
            self.scroll_wheel_mode = mode
    
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
            mode: "roi_ellipse", "roi_rectangle", "measure", "zoom", or "pan"
        """
        self.mouse_mode = mode
        
        # Update ROI drawing mode based on mouse mode
        if mode == "roi_ellipse":
            self.roi_drawing_mode = "ellipse"
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "roi_rectangle":
            self.roi_drawing_mode = "rectangle"
            self.setCursor(Qt.CursorShape.CrossCursor)
        elif mode == "measure":
            self.roi_drawing_mode = None
            self.setCursor(Qt.CursorShape.CrossCursor)  # Could use different cursor
        elif mode == "zoom":
            self.roi_drawing_mode = None
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:  # pan
            self.roi_drawing_mode = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
    
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
            # First check if clicking on existing ROI item
            scene_pos = self.mapToScene(event.position().toPoint())
            item = self.scene.itemAt(scene_pos, self.transform())
            
            # Check if it's a ROI item (QGraphicsRectItem or QGraphicsEllipseItem)
            from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
            is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
            
            if is_roi_item:
                # Clicking on existing ROI - emit signal for ROI click
                # This allows ROI selection/movement without starting new drawing
                self.roi_clicked.emit(item)
            elif self.roi_drawing_mode:
                # Start ROI drawing only if not clicking on existing ROI
                self.roi_drawing_start = scene_pos
                self.roi_drawing_started.emit(scene_pos)
            else:
                # Pan mode
                self.pan_start_pos = event.position()
                self.panning = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() == Qt.MouseButton.RightButton:
            # Right click for context menu or other actions
            pass
        
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events for panning or ROI drawing.
        
        Args:
            event: Mouse event
        """
        if self.roi_drawing_mode and self.roi_drawing_start is not None:
            # ROI drawing mode
            if event.buttons() & Qt.MouseButton.LeftButton:
                scene_pos = self.mapToScene(event.position().toPoint())
                self.roi_drawing_updated.emit(scene_pos)
        elif self.panning and event.buttons() & Qt.MouseButton.LeftButton:
            # Pan mode
            # Calculate pan delta
            delta = event.position() - self.pan_start_pos
            self.pan_start_pos = event.position()
            
            # Translate view
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
        
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse release events.
        
        Args:
            event: Mouse event
        """
        if event.button() == Qt.MouseButton.LeftButton:
            if self.roi_drawing_mode and self.roi_drawing_start is not None:
                # Finish ROI drawing
                self.roi_drawing_finished.emit()
                self.roi_drawing_start = None
            else:
                # Pan mode
                self.panning = False
                if not self.roi_drawing_mode:
                    self.setCursor(Qt.CursorShape.ArrowCursor)
        
        super().mouseReleaseEvent(event)
    
    def resizeEvent(self, event) -> None:
        """
        Handle resize events.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        # Optionally auto-fit on resize
        # self.fit_to_view()

