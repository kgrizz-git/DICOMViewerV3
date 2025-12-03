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
                                QWidget, QVBoxLayout, QMenu, QApplication)
from PySide6.QtCore import Qt, QRectF, Signal, QPointF, QTimer, QEvent
from PySide6.QtGui import (QPixmap, QImage, QWheelEvent, QKeyEvent, QMouseEvent,
                          QPainter, QColor, QTransform, QDragEnterEvent, QDropEvent)
from PIL import Image
import numpy as np
import os
import time
from typing import Optional, Callable, Any, List, Tuple


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
    roi_statistics_overlay_toggle_requested = Signal(object, bool)  # Emitted when ROI statistics overlay toggle is requested (ROIItem, visible)
    roi_statistics_selection_changed = Signal(object, set)  # Emitted when ROI statistics selection changes (ROIItem, statistics_set)
    reset_view_requested = Signal()  # Emitted when reset view is requested from context menu
    reset_all_views_requested = Signal()  # Emitted when reset all views is requested from context menu
    context_menu_mouse_mode_changed = Signal(str)  # Emitted when mouse mode is changed from context menu
    context_menu_scroll_wheel_mode_changed = Signal(str)  # Emitted when scroll wheel mode is changed from context menu
    context_menu_rescale_toggle_changed = Signal(bool)  # Emitted when rescale toggle is changed from context menu
    window_level_drag_changed = Signal(float, float)  # Emitted when window/level is adjusted via right mouse drag (center_delta, width_delta)
    right_mouse_press_for_drag = Signal()  # Emitted when right mouse is pressed (not on ROI) to request window/level values for drag
    series_navigation_requested = Signal(int)  # Emitted when series navigation is requested (-1 for left/previous, 1 for right/next)
    toggle_series_navigator_requested = Signal()  # Emitted when series navigator toggle is requested
    window_level_preset_selected = Signal(int)  # Emitted when preset is selected (preset_index)
    cine_play_requested = Signal()  # Emitted when cine play is requested from context menu
    cine_pause_requested = Signal()  # Emitted when cine pause is requested from context menu
    cine_stop_requested = Signal()  # Emitted when cine stop is requested from context menu
    cine_loop_toggled = Signal(bool)  # Emitted when cine loop is toggled from context menu (True = enabled)
    measurement_started = Signal(QPointF)  # Emitted when measurement starts (start position)
    measurement_updated = Signal(QPointF)  # Emitted when measurement is updated (current position)
    measurement_finished = Signal()  # Emitted when measurement is finished
    measurement_delete_requested = Signal(object)  # Emitted when measurement deletion is requested (MeasurementItem)
    crosshair_delete_requested = Signal(object)  # Emitted when crosshair deletion is requested (CrosshairItem)
    clear_measurements_requested = Signal()  # Emitted when clear measurements is requested
    toggle_overlay_requested = Signal()  # Emitted when toggle overlay is requested
    privacy_view_toggled = Signal(bool)  # Emitted when privacy view is toggled from context menu (True = enabled)
    annotation_options_requested = Signal()  # Emitted when annotation options dialog is requested
    crosshair_clicked = Signal(QPointF, str, int, int, int)  # Emitted when crosshair tool is clicked (pos, pixel_value_str, x, y, z)
    about_this_file_requested = Signal()  # Emitted when About this File is requested from context menu
    assign_series_requested = Signal(str)  # Emitted when series assignment is requested (series_uid)
    pixel_info_changed = Signal(str, int, int, int)  # Emitted when pixel info changes (pixel_value_str, x, y, z)
    files_dropped = Signal(list)  # Emitted when files/folders are dropped (list of paths)
    projection_enabled_changed = Signal(bool)  # Emitted when projection enabled state changes from context menu
    projection_type_changed = Signal(str)  # Emitted when projection type changes from context menu ("aip", "mip", "minip")
    projection_slice_count_changed = Signal(int)  # Emitted when projection slice count changes from context menu
    layout_change_requested = Signal(str)  # Emitted when layout change is requested from context menu ("1x1", "1x2", "2x1", "2x2")
    
    def __init__(self, parent: Optional[QWidget] = None, config_manager=None):
        """
        Initialize the image viewer.
        
        Args:
            parent: Parent widget
            config_manager: Optional ConfigManager instance for overlay font settings
        """
        super().__init__(parent)
        self.config_manager = config_manager
        
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
        
        # Enable mouse tracking for hover events (pixel info updates)
        self.setMouseTracking(True)
        
        # Image item
        self.image_item: Optional[QGraphicsPixmapItem] = None
        
        # Image inversion state
        self.image_inverted: bool = False
        self.original_image: Optional[Image.Image] = None  # Store original image for inversion
        
        # Callback to notify when inversion state changes (for persistence per series)
        self.inversion_state_changed_callback: Optional[Callable[[bool], None]] = None
        
        # Callbacks to get current dataset and slice index for pixel value display
        self.get_current_dataset_callback: Optional[Callable[[], Any]] = None
        self.get_current_slice_index_callback: Optional[Callable[[], int]] = None
        self.get_use_rescaled_values_callback: Optional[Callable[[], bool]] = None
        
        # Zoom settings
        self.min_zoom = 0.1
        self.max_zoom = 10.0
        self.zoom_factor = 1.08  # Reduced from 1.1 for less sensitive scroll wheel zoom
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
        self.zoom_mouse_moved = False  # Track if mouse actually moved during zoom drag
        
        # Magnifier state
        from gui.magnifier_widget import MagnifierWidget
        self.magnifier_widget: Optional[MagnifierWidget] = None
        self.magnifier_active: bool = False
        # Note: magnifier zoom is calculated dynamically as 1.5 * current_zoom
        
        # Scroll wheel mode
        self.scroll_wheel_mode = "slice"  # "slice" or "zoom"
        
        # Callback to get cine loop state (set from main.py)
        self.get_cine_loop_state_callback: Optional[Callable[[], bool]] = None
        self.get_available_series_callback: Optional[Callable[[], list]] = None  # Returns list of (series_uid, series_name) tuples
        
        # Rescale toggle state (for context menu)
        self.use_rescaled_values = False
        
        # Track transform for change detection
        self.last_transform = QTransform()
        
        # Track scrollbar positions for panning detection
        self.last_horizontal_scroll = 0
        self.last_vertical_scroll = 0
        
        # Debounced timer for panning updates (prevents jitter during rapid panning)
        self._pan_update_timer: Optional[QTimer] = None
        
        # Right mouse drag for window/level adjustment
        self.right_mouse_drag_start_pos: Optional[QPointF] = None
        self.right_mouse_drag_start_center: Optional[float] = None
        self.right_mouse_drag_start_width: Optional[float] = None
        self.right_mouse_context_menu_shown = False  # Track if context menu was shown
        self.cine_controls_enabled = False  # Track if cine controls should be enabled in context menu
        
        # Privacy view state (for context menu synchronization)
        self._privacy_view_enabled: bool = False
        
        # Callbacks for window/level presets (set from main.py)
        self.get_window_level_presets_callback: Optional[Callable[[], List[Tuple[float, float, bool, Optional[str]]]]] = None
        self.get_current_preset_index_callback: Optional[Callable[[], int]] = None
        
        # Callback to get ROI from item (set from main.py)
        self.get_roi_from_item_callback: Optional[Callable[[object], Optional[object]]] = None
        self.delete_all_rois_callback: Optional[Callable[[], None]] = None
        
        # Callbacks for projection state (set from main.py)
        self.get_projection_enabled_callback: Optional[Callable[[], bool]] = None
        self.get_projection_type_callback: Optional[Callable[[], str]] = None
        self.get_projection_slice_count_callback: Optional[Callable[[], int]] = None
        
        # Sensitivity factors for window/level adjustment (pixels to units)
        # These will be set dynamically based on current ranges
        self.window_center_sensitivity = 1.0  # pixels per unit
        self.window_width_sensitivity = 1.0  # pixels per unit
        
        # View settings
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        # Transformation anchor is already set to AnchorViewCenter above for viewport-centered zoom
        # Resize anchor is already set to AnchorViewCenter above
        
        # Enable drag-and-drop on image viewer
        self.setAcceptDrops(True)
        # Also enable drag-and-drop on viewport (the actual widget that receives mouse events)
        self.viewport().setAcceptDrops(True)
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
    
    def set_background_color(self, color: QColor) -> None:
        """
        Set the background color of the image viewer.
        
        Args:
            color: QColor for the background
        """
        self.setBackgroundBrush(color)
    
    def _apply_inversion(self, image: Image.Image) -> Image.Image:
        """
        Apply inversion to a PIL Image.
        
        Args:
            image: PIL Image to invert
            
        Returns:
            Inverted PIL Image
        """
        try:
            img_array = np.array(image)
            if image.mode == 'L':
                # Grayscale: invert each pixel value
                img_array = 255 - img_array
                return Image.fromarray(img_array, mode='L')
            elif image.mode == 'RGB':
                # RGB: invert each channel
                img_array = 255 - img_array
                return Image.fromarray(img_array, mode='RGB')
            else:
                # Convert to RGB first, then invert
                rgb_image = image.convert('RGB')
                img_array = np.array(rgb_image)
                img_array = 255 - img_array
                return Image.fromarray(img_array, mode='RGB')
        except Exception as e:
            print(f"Error inverting image: {e}")
            return image  # Return original on error
    
    def invert_image(self) -> None:
        """
        Toggle image inversion state and update display.
        """
        if self.original_image is None:
            # If no original image stored, we can't invert
            # This should not happen in normal operation as set_image stores the original
            return
        
        # Toggle inversion state FIRST
        self.image_inverted = not self.image_inverted
        
        # Notify callback of state change (for persistence per series)
        # This must happen BEFORE calling set_image to ensure state is stored
        if self.inversion_state_changed_callback:
            self.inversion_state_changed_callback(self.image_inverted)
        
        # Apply inversion to the original image and update display
        # Pass the new inversion state explicitly to ensure synchronization
        if self.image_inverted:
            display_image = self._apply_inversion(self.original_image)
        else:
            display_image = self.original_image
        
        # Update the pixmap without changing zoom/pan
        # Pass apply_inversion explicitly to ensure state synchronization
        preserve_view = True
        self.set_image(display_image, preserve_view=preserve_view, apply_inversion=self.image_inverted)
    
    def set_image(self, image: Image.Image, preserve_view: bool = False, apply_inversion: Optional[bool] = None) -> None:
        """
        Set the image to display.
        
        Preserves existing ROIs and overlay items when changing images.
        
        Args:
            image: PIL Image to display
            preserve_view: If True, preserve current zoom and pan position
            apply_inversion: Optional bool to override inversion state. If None, uses self.image_inverted
        """
        # print(f"[VIEWER] set_image called")
        # print(f"[VIEWER] Image size: {image.size}, mode: {image.mode}, preserve_view: {preserve_view}")
        # print(f"[VIEWER] Image id: {id(image)}")
        # print(f"[VIEWER] Apply inversion: {apply_inversion}")
        # print(f"[VIEWER] Current image_inverted: {self.image_inverted}")
        # print(f"[VIEWER] Current original_image id: {id(self.original_image) if self.original_image else 'None'}")
        
        # Store original image for inversion
        # When preserve_view=False: new slice, always store new original_image
        # When preserve_view=True and apply_inversion is not None: same slice, inversion toggle, preserve original_image
        # When preserve_view=True and apply_inversion is None: new slice (scrolling), store new original_image
        if not preserve_view:
            # New slice - always store new original image (non-inverted)
            # print(f"[VIEWER] Storing new original_image (preserve_view=False)")
            # print(f"[VIEWER] Before: original_image id = {id(self.original_image) if self.original_image else 'None'}")
            # print(f"[VIEWER] Image to copy id = {id(image)}")
            self.original_image = image.copy()
            # print(f"[VIEWER] After: original_image id = {id(self.original_image)}")
            
            # Update inversion state FIRST before determining if we need to invert
            # If apply_inversion is provided, use it (stored state for this series)
            # If apply_inversion is None, reset to False (no stored state for this series)
            if apply_inversion is not None:
                self.image_inverted = apply_inversion
            else:
                # No stored inversion state for this series - reset to False
                self.image_inverted = False
            
            # Determine if we need to invert the image for display
            # Use apply_inversion if provided, otherwise use current self.image_inverted state
            should_invert = apply_inversion if apply_inversion is not None else self.image_inverted
            
            # Apply inversion if needed
            if should_invert:
                image = self._apply_inversion(image)
        elif preserve_view:
            # print(f"[VIEWER] preserve_view=True branch")
            # print(f"[VIEWER] apply_inversion = {apply_inversion}")
            # Same series - might be same slice (inversion toggle) or new slice (scrolling)
            if apply_inversion is not None:
                # Same slice - inversion toggle, preserve existing original_image
                # Update inversion state to match apply_inversion
                self.image_inverted = apply_inversion
                # Apply inversion to the stored original image based on the state
                if self.original_image is not None:
                    if self.image_inverted:
                        image = self._apply_inversion(self.original_image)
                    else:
                        image = self.original_image
            else:
                # New slice (scrolling within same series) - store new original_image
                # print(f"[VIEWER] Storing new original_image (scrolling within same series)")
                # print(f"[VIEWER] Before: original_image id = {id(self.original_image) if self.original_image else 'None'}")
                # print(f"[VIEWER] Image to copy id = {id(image)}")
                self.original_image = image.copy()
                # print(f"[VIEWER] After: original_image id = {id(self.original_image)}")
                # Don't reset inversion state - preserve it for the series
                # Apply inversion if the series is currently inverted
                if self.image_inverted:
                    # print(f"[VIEWER] Applying inversion to new slice (series is inverted)")
                    image = self._apply_inversion(image)
                # If image_inverted is False, image is already non-inverted (from dataset), use as-is
        # If preserve_view is True and apply_inversion is None,
        # the image passed in is already in the correct state (inverted or not), so don't apply inversion again
        
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
        # print(f"[VIEWER] Converting PIL Image to QImage...")
        
        # IMPORTANT: Keep a reference to the bytes buffer to prevent garbage collection
        # before Qt finishes reading it. For large images, Python may GC the temporary
        # bytes object returned by image.tobytes() before QImage/QPixmap finishes,
        # causing a segfault.
        image_bytes = image.tobytes()
        
        if image.mode == 'L':
            # Grayscale - explicitly specify bytesPerLine (stride)
            # print(f"[VIEWER] Converting grayscale image...")
            bytes_per_line = image.width * 1  # 1 byte per pixel for grayscale
            # print(f"[VIEWER] Image dimensions: {image.width}x{image.height}, bytes_per_line: {bytes_per_line}")
            qimage = QImage(image_bytes, image.width, image.height, bytes_per_line,
                          QImage.Format.Format_Grayscale8)
        elif image.mode == 'RGB':
            # RGB - explicitly specify bytesPerLine (stride)
            # print(f"[VIEWER] Converting RGB image...")
            bytes_per_line = image.width * 3  # 3 bytes per pixel for RGB
            # print(f"[VIEWER] Image dimensions: {image.width}x{image.height}, bytes_per_line: {bytes_per_line}")
            qimage = QImage(image_bytes, image.width, image.height, bytes_per_line,
                          QImage.Format.Format_RGB888)
        else:
            # Convert to RGB
            # print(f"[VIEWER] Converting {image.mode} to RGB...")
            image = image.convert('RGB')
            image_bytes = image.tobytes()
            bytes_per_line = image.width * 3  # 3 bytes per pixel for RGB
            # print(f"[VIEWER] Image dimensions: {image.width}x{image.height}, bytes_per_line: {bytes_per_line}")
            qimage = QImage(image_bytes, image.width, image.height, bytes_per_line,
                          QImage.Format.Format_RGB888)
        
        # Make a deep copy of the QImage so Qt owns the data
        # This prevents crashes if the Python bytes buffer is garbage collected
        # print(f"[VIEWER] Creating QImage copy...")
        qimage = qimage.copy()
        # print(f"[VIEWER] QImage copy created successfully")
        
        # print(f"[VIEWER] QImage created, converting to QPixmap...")
        pixmap = QPixmap.fromImage(qimage)
        # print(f"[VIEWER] QPixmap created: {pixmap.width()}x{pixmap.height()}, isNull: {pixmap.isNull()}")
        # print(f"[VIEWER] Pixmap cache key: {pixmap.cacheKey() if hasattr(pixmap, 'cacheKey') else 'N/A'}")
        
        # Remove old image item only
        # Note: ROIs and overlays will be preserved and re-added by their managers
        if self.image_item is not None:
            old_pixmap = self.image_item.pixmap()
            # print(f"[VIEWER] Removing old image item, pixmap cache key: {old_pixmap.cacheKey() if old_pixmap and hasattr(old_pixmap, 'cacheKey') else 'None'}")
            self.scene.removeItem(self.image_item)
        
        # Create new image item
        # print(f"[VIEWER] Creating QGraphicsPixmapItem...")
        self.image_item = QGraphicsPixmapItem(pixmap)
        # Set image item to lowest Z-value so other items appear on top
        self.image_item.setZValue(0)
        # print(f"[VIEWER] New image item created, pixmap cache key: {self.image_item.pixmap().cacheKey() if self.image_item.pixmap() and hasattr(self.image_item.pixmap(), 'cacheKey') else 'None'}")
        # print(f"[VIEWER] Adding item to scene...")
        self.scene.addItem(self.image_item)
        # print(f"[VIEWER] Item added to scene successfully")
        
        # Force scene and viewport update to ensure display refreshes
        # print(f"[VIEWER] Forcing scene and viewport update...")
        self.scene.invalidate(self.scene.sceneRect())
        self.viewport().update()
        # print(f"[VIEWER] Scene and viewport updated")
        
        # Set scene rect to image dimensions to ensure proper overlay positioning
        # print(f"[VIEWER] Getting image bounding rect...")
        image_rect = self.image_item.boundingRect()
        # print(f"[VIEWER] Image rect: {image_rect}")
        
        # Calculate fixed scene rect size that accommodates:
        # - If image is larger than viewport: 2x image size
        # - If image is smaller than viewport: 1.0x viewport at min zoom
        # This ensures mapToScene() accuracy at all zoom levels without recalculation
        image_width = image_rect.width()  # Scene coordinates
        image_height = image_rect.height()  # Scene coordinates
        
        # Calculate viewport size in scene coordinates at zoom = 1.0
        # At zoom = 1.0, viewport pixels = scene coordinates
        viewport_width_pixels = self.viewport().width()
        viewport_height_pixels = self.viewport().height()
        viewport_width_scene = viewport_width_pixels  # At zoom = 1.0, they're equal
        viewport_height_scene = viewport_height_pixels  # At zoom = 1.0, they're equal
        
        # Calculate viewport size in scene coordinates at minimum zoom (for else case)
        viewport_at_min_zoom_width = viewport_width_pixels / self.min_zoom if self.min_zoom > 0 else viewport_width_pixels
        viewport_at_min_zoom_height = viewport_height_pixels / self.min_zoom if self.min_zoom > 0 else viewport_height_pixels
        
        # Calculate viewport size in scene coordinates at zoom = 0.5
        # At zoom = 0.5, each viewport pixel represents 2 scene coordinate units
        viewport_at_zoom_0_5_width = viewport_width_pixels / 0.5
        viewport_at_zoom_0_5_height = viewport_height_pixels / 0.5
        
        # Compare both in scene coordinates (at zoom = 1.0 for the comparison)
        # If image is larger than viewport, use 2x image size
        # Otherwise, use 3x image size + viewport at zoom 0.5
        if image_width > viewport_width_scene:
            scene_width = image_width * 2.0
            # print(f"[SCENE_RECT] Image width ({image_width:.2f}) > viewport width in scene coords ({viewport_width_scene:.2f}) - using 2x image size: {scene_width:.2f}")
        else:
            scene_width = 3.0 * image_width + viewport_at_zoom_0_5_width
            # print(f"[SCENE_RECT] Image width ({image_width:.2f}) <= viewport width in scene coords ({viewport_width_scene:.2f}) - using 3x image size + viewport at zoom 0.5: {scene_width:.2f}")
        
        if image_height > viewport_height_scene:
            scene_height = image_height * 2.0
            # print(f"[SCENE_RECT] Image height ({image_height:.2f}) > viewport height in scene coords ({viewport_height_scene:.2f}) - using 2x image size: {scene_height:.2f}")
        else:
            scene_height = 3.0 * image_height + viewport_at_zoom_0_5_height
            # print(f"[SCENE_RECT] Image height ({image_height:.2f}) <= viewport height in scene coords ({viewport_height_scene:.2f}) - using 3x image size + viewport at zoom 0.5: {scene_height:.2f}")
        
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
        # print(f"[DEBUG-FIT] fit_to_view called: center_image={center_image}")
        if self.image_item is None:
            # print(f"[DEBUG-FIT] fit_to_view: image_item is None, returning")
            return
        
        # Get scene rect
        scene_rect = self.image_item.boundingRect()
        # print(f"[DEBUG-FIT] fit_to_view: scene_rect = {scene_rect.width():.1f}x{scene_rect.height():.1f}")
        if scene_rect.isEmpty():
            # print(f"[DEBUG-FIT] fit_to_view: scene_rect is empty, returning")
            return
        
        viewport = self.viewport()
        if viewport:
            viewport_size = f"{viewport.width()}x{viewport.height()}"
        else:
            viewport_size = "None"
        # print(f"[DEBUG-FIT] fit_to_view: viewport size = {viewport_size}")
        
        # Fit in view
        # print(f"[DEBUG-FIT] fit_to_view: Calling fitInView")
        self.fitInView(scene_rect, Qt.AspectRatioMode.KeepAspectRatio)
        
        # Update zoom level
        transform = self.transform()
        self.current_zoom = transform.m11()
        self.last_transform = transform
        # print(f"[DEBUG-FIT] fit_to_view: After fitInView, zoom = {self.current_zoom:.6f}")
        self.zoom_changed.emit(self.current_zoom)
        
        # If image is smaller than viewport and center_image is True, manually center it
        # fitInView() may not center properly with AnchorViewCenter when image is smaller
        if center_image:
            viewport_width = self.viewport().width()
            viewport_height = self.viewport().height()
            scaled_width = scene_rect.width() * self.current_zoom
            scaled_height = scene_rect.height() * self.current_zoom
            
            # print(f"[DEBUG-FIT] fit_to_view: center_image=True, scaled_size={scaled_width:.1f}x{scaled_height:.1f}, viewport={viewport_width}x{viewport_height}")
            if scaled_width < viewport_width or scaled_height < viewport_height:
                # Image is smaller than viewport - center it
                image_center = scene_rect.center()
                # print(f"[DEBUG-FIT] fit_to_view: Centering on {image_center}")
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
    
    def set_zoom(self, zoom_value: float) -> None:
        """
        Set zoom to a specific value, centered on viewport center.
        
        Args:
            zoom_value: Target zoom level
        """
        if self.image_item is None:
            return
        
        # Clamp to valid range
        zoom_value = max(self.min_zoom, min(self.max_zoom, zoom_value))
        
        # Calculate scale factor needed to reach target zoom
        current_scale = self.transform().m11()
        scale_factor = zoom_value / current_scale
        
        # Apply zoom - AnchorViewCenter ensures it's centered on viewport center
        self.scale(scale_factor, scale_factor)
        self.current_zoom = zoom_value
        
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
    
    def set_cine_controls_enabled(self, enabled: bool) -> None:
        """
        Set whether cine controls should be enabled in the context menu.
        
        Args:
            enabled: True to enable cine controls in context menu, False to disable
        """
        self.cine_controls_enabled = enabled
    
    def set_privacy_view_state(self, enabled: bool) -> None:
        """
        Set the privacy view state (for context menu synchronization).
        
        Args:
            enabled: True if privacy view is enabled, False otherwise
        """
        self._privacy_view_enabled = enabled
    
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
        elif mode == "magnifier":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            # Use cross cursor for magnifier mode
            self.setCursor(Qt.CursorShape.CrossCursor)
            # Reset magnifier state when switching to magnifier mode
            if self.magnifier_widget is not None:
                self.magnifier_widget.hide()
            self.magnifier_active = False
        elif mode == "crosshair":
            self.roi_drawing_mode = None
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(Qt.CursorShape.CrossCursor)
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
        # Hybrid approach: Check if parent is a SubWindowContainer and handle focus
        # This works in conjunction with the event filter in SubWindowContainer
        from gui.sub_window_container import SubWindowContainer
        parent = self.parent()
        if isinstance(parent, SubWindowContainer):
            if not parent.is_focused:
                # Parent container is not focused - request focus first
                # This ensures single-click on unfocused subwindow sets focus
                if event.button() == Qt.MouseButton.LeftButton:
                    # print(f"[DEBUG-FOCUS] ImageViewer.mousePressEvent: Parent SubWindowContainer not focused, setting focus")
                    # Accept the event to prevent further processing
                    event.accept()
                    # Request focus change
                    parent.set_focused(True)
                    parent.focus_changed.emit(True)
                    # print(f"[DEBUG-FOCUS] ImageViewer.mousePressEvent: Focus set and signal emitted, returning early")
                    # Return early - don't process the click as pan/zoom/etc
                    # The user can click again if they want to interact
                    return
        
        if event.button() == Qt.MouseButton.LeftButton:
            # Handle select mode - allow default Qt selection behavior
            if self.mouse_mode == "select":
                # Check what item is at the click position
                scene_pos = self.mapToScene(event.position().toPoint())
                item = self.scene.itemAt(scene_pos, self.transform())
                
                # Check if clicking on empty space (image item or None)
                from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
                from tools.measurement_tool import MeasurementItem, MeasurementHandle, DraggableMeasurementText
                
                is_empty_space = (item is None or item == self.image_item)
                
                # Check if item is an ROI - use ROI manager callback for accurate detection
                is_roi_item = False
                if item is not None and hasattr(self, 'get_roi_from_item_callback') and self.get_roi_from_item_callback:
                    roi = self.get_roi_from_item_callback(item)
                    if roi is not None:
                        is_roi_item = True
                
                # Fallback: check by type if callback not available
                if not is_roi_item:
                    is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)) and item != self.image_item
                
                is_measurement_item = isinstance(item, MeasurementItem)
                is_handle = isinstance(item, MeasurementHandle)
                is_measurement_text = isinstance(item, DraggableMeasurementText)
                
                # Check if item is a child of a measurement (line or text)
                is_measurement_child = False
                if item is not None:
                    parent = item.parentItem()
                    while parent is not None:
                        if isinstance(parent, MeasurementItem):
                            is_measurement_child = True
                            break
                        parent = parent.parentItem()
                
                if is_empty_space and not (is_roi_item or is_measurement_item or is_handle or is_measurement_text or is_measurement_child):
                    # Clicking on empty space - deselect everything
                    # print(f"[DEBUG-DESELECT] Empty space click detected in Select mode")
                    # print(f"[DEBUG-DESELECT]   is_empty_space: {is_empty_space}, is_roi_item: {is_roi_item}, is_measurement_item: {is_measurement_item}")
                    
                    if self.scene is not None:
                        # First, explicitly deselect all measurements and their text labels
                        for scene_item in self.scene.items():
                            if isinstance(scene_item, (MeasurementItem, DraggableMeasurementText)):
                                scene_item.setSelected(False)
                        
                        # Clear scene selection (this will visually deselect ROIs)
                        selected_before = [item for item in self.scene.selectedItems()]
                        # print(f"[DEBUG-DESELECT]   Selected items in scene before clear: {len(selected_before)}")
                        # for item in selected_before:
                        #     print(f"[DEBUG-DESELECT]     Item: {type(item).__name__}, isSelected: {item.isSelected()}")
                        self.scene.clearSelection()
                        selected_after = [item for item in self.scene.selectedItems()]
                        # print(f"[DEBUG-DESELECT]   Selected items in scene after clear: {len(selected_after)}")
                    
                    # Emit signal to clear ROI selection - this is critical for proper ROI deselection
                    # This must happen BEFORE calling super() to prevent Qt's default behavior from interfering
                    # print(f"[DEBUG-DESELECT]   Emitting image_clicked_no_roi signal")
                    self.image_clicked_no_roi.emit()
                    
                    # Accept the event to prevent further processing
                    event.accept()
                    return
                
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
                    # Use viewport position for zoom tracking (more accurate for vertical movement)
                    self.zoom_start_pos = event.position()
                    self.zoom_start_zoom = self.current_zoom
                    self.zoom_mouse_moved = False  # Track if mouse actually moved
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
                elif self.mouse_mode == "magnifier":
                    # Magnifier mode - activate magnifier
                    if not self.magnifier_active:
                        # Create magnifier widget if it doesn't exist
                        if self.magnifier_widget is None:
                            from gui.magnifier_widget import MagnifierWidget
                            self.magnifier_widget = MagnifierWidget()
                        
                        self.magnifier_active = True
                        # Hide cursor when magnifier is active
                        self.setCursor(Qt.CursorShape.BlankCursor)
                        # Extract and show magnified region
                        # Get current zoom from view transform (most accurate)
                        current_zoom = self.transform().m11()
                        # Magnifier zoom is 2.0x the current view zoom
                        magnifier_zoom = 2.0 * current_zoom
                        # Extract region size calculation for 2.0x zoom
                        # To achieve true 2.0x zoom: we want final pixmap to be 200px (widget size)
                        # After scaling by magnifier_zoom, we need: region_size * magnifier_zoom = 200
                        # So: region_size = 200 / magnifier_zoom = 200 / (2.0 * current_zoom)
                        # This ensures the extracted region, when scaled, fills the 200px widget at 2.0x zoom
                        adjusted_region_size = 200.0 / (2.0 * current_zoom) if current_zoom > 0 else 200.0 / 2.0
                        print(f"[DEBUG-MAGNIFIER] Press: current_zoom={current_zoom:.3f}, magnifier_zoom={magnifier_zoom:.3f}, adjusted_region_size={adjusted_region_size:.3f}")
                        magnified_pixmap = self._extract_image_region(
                            scene_pos.x(), scene_pos.y(), adjusted_region_size, magnifier_zoom
                        )
                        if magnified_pixmap is not None:
                            print(f"[DEBUG-MAGNIFIER] Press: extracted_region_size=({int(adjusted_region_size):d}x{int(adjusted_region_size):d}), scaled_pixmap_size=({magnified_pixmap.width()}x{magnified_pixmap.height()})")
                        if magnified_pixmap is not None:
                            self.magnifier_widget.update_magnified_region(magnified_pixmap)
                            # Position magnifier centered on cursor
                            global_pos = self.mapToGlobal(event.position().toPoint())
                            self.magnifier_widget.show_at_position(global_pos)
                elif self.mouse_mode == "crosshair":
                    # Crosshair mode - get pixel value and coordinates, emit signal
                    if self.get_current_dataset_callback:
                        dataset = self.get_current_dataset_callback()
                        if dataset is not None:
                            # Convert scene position to image coordinates
                            x = int(scene_pos.x())
                            y = int(scene_pos.y())
                            z = 0
                            if self.get_current_slice_index_callback:
                                z = self.get_current_slice_index_callback()
                            
                            # Get pixel value
                            use_rescaled = False
                            if self.get_use_rescaled_values_callback:
                                use_rescaled = self.get_use_rescaled_values_callback()
                            
                            pixel_value_str = self._get_pixel_value_at_coords(dataset, x, y, z, use_rescaled)
                            
                            # Emit signal with crosshair information
                            self.crosshair_clicked.emit(scene_pos, pixel_value_str, x, y, z)
                elif self.roi_drawing_mode:
                    # Start ROI drawing
                    self.roi_drawing_start = scene_pos
                    self.roi_drawing_started.emit(scene_pos)
            elif self.mouse_mode == "zoom":
                # Zoom mode - start zoom operation (clicking on overlay or other items)
                # Use viewport position for zoom tracking (more accurate for vertical movement)
                self.zoom_start_pos = event.position()
                self.zoom_start_zoom = self.current_zoom
                self.zoom_mouse_moved = False  # Track if mouse actually moved
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
            
            # Check if item is directly a ROI or measurement
            is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
            is_measurement_item = isinstance(item, MeasurementItem)
            
            # If not directly a measurement, check if it's a child of a measurement
            if not is_measurement_item and item is not None:
                # Walk up parent chain to find MeasurementItem
                parent = item.parentItem()
                while parent is not None:
                    if isinstance(parent, MeasurementItem):
                        is_measurement_item = True
                        item = parent  # Use the parent MeasurementItem for the menu
                        break
                    parent = parent.parentItem()
            
            if is_roi_item:
                # Show context menu for ROI immediately
                context_menu = QMenu(self)
                
                # Delete action
                delete_action = context_menu.addAction("Delete ROI")
                delete_action.triggered.connect(lambda: self.roi_delete_requested.emit(item))
                
                # Delete all ROIs action
                delete_all_action = context_menu.addAction("Delete all ROIs (D)")
                if self.delete_all_rois_callback:
                    delete_all_action.triggered.connect(self.delete_all_rois_callback)
                
                context_menu.addSeparator()
                
                # Statistics Overlay submenu
                stats_submenu = context_menu.addMenu("Statistics Overlay")
                
                # Get ROI from item using callback
                roi = None
                if self.get_roi_from_item_callback:
                    roi = self.get_roi_from_item_callback(item)
                
                if roi is not None:
                    # Toggle overlay visibility
                    toggle_action = stats_submenu.addAction("Show Statistics Overlay")
                    toggle_action.setCheckable(True)
                    toggle_action.setChecked(roi.statistics_overlay_visible)
                    toggle_action.triggered.connect(lambda checked: self.roi_statistics_overlay_toggle_requested.emit(roi, checked))
                    
                    stats_submenu.addSeparator()
                    
                    # Statistics checkboxes
                    mean_action = stats_submenu.addAction("Show Mean")
                    mean_action.setCheckable(True)
                    mean_action.setChecked("mean" in roi.visible_statistics)
                    mean_action.triggered.connect(lambda checked: self._toggle_statistic(roi, "mean", checked))
                    
                    std_action = stats_submenu.addAction("Show Std Dev")
                    std_action.setCheckable(True)
                    std_action.setChecked("std" in roi.visible_statistics)
                    std_action.triggered.connect(lambda checked: self._toggle_statistic(roi, "std", checked))
                    
                    min_action = stats_submenu.addAction("Show Min")
                    min_action.setCheckable(True)
                    min_action.setChecked("min" in roi.visible_statistics)
                    min_action.triggered.connect(lambda checked: self._toggle_statistic(roi, "min", checked))
                    
                    max_action = stats_submenu.addAction("Show Max")
                    max_action.setCheckable(True)
                    max_action.setChecked("max" in roi.visible_statistics)
                    max_action.triggered.connect(lambda checked: self._toggle_statistic(roi, "max", checked))
                    
                    count_action = stats_submenu.addAction("Show Pixels")
                    count_action.setCheckable(True)
                    count_action.setChecked("count" in roi.visible_statistics)
                    count_action.triggered.connect(lambda checked: self._toggle_statistic(roi, "count", checked))
                    
                    area_action = stats_submenu.addAction("Show Area")
                    area_action.setCheckable(True)
                    area_action.setChecked("area" in roi.visible_statistics)
                    area_action.triggered.connect(lambda checked: self._toggle_statistic(roi, "area", checked))
                
                context_menu.addSeparator()
                
                # Annotation Options action
                annotation_options_action = context_menu.addAction("Annotation Options...")
                annotation_options_action.triggered.connect(self.annotation_options_requested.emit)
                
                context_menu.exec(event.globalPosition().toPoint())
                self.right_mouse_context_menu_shown = True
                return
            elif is_measurement_item:
                # Show context menu for measurement immediately
                context_menu = QMenu(self)
                delete_action = context_menu.addAction("Delete Measurement")
                delete_action.triggered.connect(lambda: self.measurement_delete_requested.emit(item))
                
                context_menu.addSeparator()
                
                # Annotation Options action
                annotation_options_action = context_menu.addAction("Annotation Options...")
                annotation_options_action.triggered.connect(self.annotation_options_requested.emit)
            
            # Check if clicking on crosshair item
            from tools.crosshair_manager import CrosshairItem
            is_crosshair_item = (item is not None and 
                               item != self.image_item and
                               isinstance(item, CrosshairItem))
            
            if is_crosshair_item:
                # Show context menu for crosshair immediately
                context_menu = QMenu(self)
                delete_action = context_menu.addAction("Delete Crosshair")
                delete_action.triggered.connect(lambda: self.crosshair_delete_requested.emit(item))
                
                context_menu.addSeparator()
                
                # Annotation Options action
                annotation_options_action = context_menu.addAction("Annotation Options...")
                annotation_options_action.triggered.connect(self.annotation_options_requested.emit)
                
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
    
    def _toggle_statistic(self, roi, stat_name: str, checked: bool) -> None:
        """
        Toggle a statistic in the ROI's visible_statistics set.
        
        Args:
            roi: ROI item
            stat_name: Name of statistic ("mean", "std", "min", "max", "count", "area")
            checked: True to include statistic, False to exclude
        """
        if checked:
            roi.visible_statistics.add(stat_name)
        else:
            roi.visible_statistics.discard(stat_name)
        
        # Emit signal to update overlay
        self.roi_statistics_selection_changed.emit(roi, roi.visible_statistics)
    
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events for panning, ROI drawing, or zooming.
        
        Args:
            event: Mouse event
        """
        # Track cursor position and pixel values for status bar display
        # This should happen in all mouse modes, regardless of tool selection
        self._update_pixel_info(event)
        
        # Check for right mouse drag FIRST, before any mode-specific checks
        # This allows window/level adjustment to work in all modes (Select, Pan, etc.)
        if event.buttons() & Qt.MouseButton.RightButton and self.right_mouse_drag_start_pos is not None:
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
                return  # Return early to prevent other mode handling
        
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
            
            # Only zoom if mouse moved significantly (threshold: 2 pixels)
            # This prevents zoom on just a click
            if abs(delta_y) > 2.0:
                self.zoom_mouse_moved = True
                
                # Convert to zoom factor (negative delta = zoom in, positive = zoom out)
                zoom_delta = -delta_y / 350.0  # Reduced sensitivity (was 300.0)
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
        elif self.mouse_mode == "magnifier" and self.magnifier_active:
            # Magnifier mode - update magnifier position and content
            if event.buttons() & Qt.MouseButton.LeftButton:
                # Ensure cursor stays hidden
                if self.cursor().shape() != Qt.CursorShape.BlankCursor:
                    self.setCursor(Qt.CursorShape.BlankCursor)
                scene_pos = self.mapToScene(event.position().toPoint())
                # Extract and update magnified region
                # Get current zoom from view transform (most accurate)
                current_zoom = self.transform().m11()
                # Magnifier zoom is 2.0x the current view zoom
                magnifier_zoom = 2.0 * current_zoom
                # Extract region size calculation for 2.0x zoom
                # To achieve true 2.0x zoom: we want final pixmap to be 200px (widget size)
                # After scaling by magnifier_zoom, we need: region_size * magnifier_zoom = 200
                # So: region_size = 200 / magnifier_zoom = 200 / (2.0 * current_zoom)
                # This ensures the extracted region, when scaled, fills the 200px widget at 2.0x zoom
                adjusted_region_size = 200.0 / (2.0 * current_zoom) if current_zoom > 0 else 200.0 / 2.0
                magnified_pixmap = self._extract_image_region(
                    scene_pos.x(), scene_pos.y(), adjusted_region_size, magnifier_zoom
                )
                if magnified_pixmap is not None:
                    print(f"[DEBUG-MAGNIFIER] Move: current_zoom={current_zoom:.3f}, magnifier_zoom={magnifier_zoom:.3f}, adjusted_region_size={adjusted_region_size:.3f}, scaled_pixmap_size=({magnified_pixmap.width()}x{magnified_pixmap.height()})")
                if magnified_pixmap is not None and self.magnifier_widget is not None:
                    self.magnifier_widget.update_magnified_region(magnified_pixmap)
                    # Update magnifier position (centered on cursor)
                    global_pos = self.mapToGlobal(event.position().toPoint())
                    self.magnifier_widget.show_at_position(global_pos)
        elif self.mouse_mode == "pan":
            # Pan mode - ensure ScrollHandDrag is enabled (it may have been disabled by other operations)
            if self.dragMode() != QGraphicsView.DragMode.ScrollHandDrag:
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
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
        # In select mode, allow default Qt behavior for left button
        if self.mouse_mode == "select":
            # Only use default behavior for left button
            if event.button() == Qt.MouseButton.LeftButton:
                super().mouseReleaseEvent(event)
                return
            # Fall through for right button to allow context menu
        
        if event.button() == Qt.MouseButton.LeftButton:
            if self.mouse_mode == "zoom" and self.zoom_start_pos is not None:
                # Finish zoom operation - clear state regardless of whether mouse moved
                # (zoom only happens in mouseMoveEvent if mouse actually moved)
                self.zoom_start_pos = None
                self.zoom_start_zoom = None
                self.zoom_mouse_moved = False
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
            elif self.mouse_mode == "magnifier" and self.magnifier_active:
                # Finish magnifier - hide widget and restore cursor
                self.magnifier_active = False
                if self.magnifier_widget is not None:
                    self.magnifier_widget.hide()
                # Restore cursor visibility (cross cursor for magnifier mode)
                self.setCursor(Qt.CursorShape.CrossCursor)
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
                    
                    # Check if item is directly a ROI or measurement
                    is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
                    is_measurement_item = isinstance(item, MeasurementItem)
                    
                    # If not directly a measurement, check if it's a child of a measurement
                    if not is_measurement_item and item is not None:
                        # Walk up parent chain to find MeasurementItem
                        parent = item.parentItem()
                        while parent is not None:
                            if isinstance(parent, MeasurementItem):
                                is_measurement_item = True
                                item = parent  # Use the parent MeasurementItem for the menu
                                break
                            parent = parent.parentItem()
                    
                    if not is_roi_item and not is_measurement_item:
                        # Show context menu for image (not on ROI)
                        context_menu = QMenu(self)
                        
                        # Reset View action
                        reset_action = context_menu.addAction("Reset View (V)")
                        reset_action.triggered.connect(self.reset_view_requested.emit)
                        
                        # Reset All Views action
                        if hasattr(self, 'reset_all_views_requested'):
                            reset_all_action = context_menu.addAction("Reset All Views (A)")
                            reset_all_action.triggered.connect(self.reset_all_views_requested.emit)
                        
                        # Toggle Overlay action
                        toggle_overlay_action = context_menu.addAction("Toggle Overlay (Spacebar)")
                        toggle_overlay_action.triggered.connect(self.toggle_overlay_requested.emit)
                        
                        # Privacy View action
                        privacy_view_action = context_menu.addAction("Privacy View (Cmd+P)")
                        privacy_view_action.setCheckable(True)
                        privacy_view_action.setChecked(self._privacy_view_enabled)
                        privacy_view_action.triggered.connect(lambda checked: self.privacy_view_toggled.emit(checked))
                        
                        
                        # Delete all ROIs action
                        delete_all_action = context_menu.addAction("Delete all ROIs (D)")
                        if self.delete_all_rois_callback:
                            delete_all_action.triggered.connect(self.delete_all_rois_callback)
                        
                        # Clear Measurements action
                        clear_measurements_action = context_menu.addAction("Clear Measurements (C)")
                        clear_measurements_action.triggered.connect(self.clear_measurements_requested.emit)
                        
                        context_menu.addSeparator()
                        
                        # Series navigation actions
                        prev_series_action = context_menu.addAction("Prev Series (←)")
                        prev_series_action.triggered.connect(lambda: self.series_navigation_requested.emit(-1))
                        
                        next_series_action = context_menu.addAction("Next Series (→)")
                        next_series_action.triggered.connect(lambda: self.series_navigation_requested.emit(1))
                        
                        # Series Navigator toggle action
                        # Note: Text will be updated dynamically by main window based on visibility
                        toggle_navigator_action = context_menu.addAction("Toggle Series Navigator (N)")
                        toggle_navigator_action.triggered.connect(self.toggle_series_navigator_requested.emit)
                        
                        # Assign Series submenu (for multi-window layout)
                        assign_series_menu = context_menu.addMenu("Assign Series to Focused Window")
                        if hasattr(self, 'get_available_series_callback') and self.get_available_series_callback:
                            series_list = self.get_available_series_callback()
                            if series_list:
                                for series_uid, series_name in series_list:
                                    action = assign_series_menu.addAction(series_name)
                                    action.triggered.connect(lambda checked, uid=series_uid: self.assign_series_requested.emit(uid))
                            else:
                                assign_series_menu.setEnabled(False)
                        else:
                            assign_series_menu.setEnabled(False)
                        
                        context_menu.addSeparator()
                        
                        # Layout submenu
                        layout_menu = context_menu.addMenu("Layout")
                        layout_1x1_action = layout_menu.addAction("1x1")
                        layout_1x1_action.setCheckable(True)
                        layout_1x1_action.triggered.connect(lambda: self.layout_change_requested.emit("1x1"))
                        
                        layout_1x2_action = layout_menu.addAction("1x2")
                        layout_1x2_action.setCheckable(True)
                        layout_1x2_action.triggered.connect(lambda: self.layout_change_requested.emit("1x2"))
                        
                        layout_2x1_action = layout_menu.addAction("2x1")
                        layout_2x1_action.setCheckable(True)
                        layout_2x1_action.triggered.connect(lambda: self.layout_change_requested.emit("2x1"))
                        
                        layout_2x2_action = layout_menu.addAction("2x2")
                        layout_2x2_action.setCheckable(True)
                        layout_2x2_action.triggered.connect(lambda: self.layout_change_requested.emit("2x2"))
                        
                        # Note: Checkmarks will be updated by main.py based on current layout
                        
                        context_menu.addSeparator()
                        
                        # Annotation Options action
                        annotation_options_action = context_menu.addAction("Annotation Options...")
                        annotation_options_action.triggered.connect(self.annotation_options_requested.emit)
                        
                        context_menu.addSeparator()
                        
                        # Window/Level Presets submenu (if presets available)
                        if hasattr(self, 'get_window_level_presets_callback') and self.get_window_level_presets_callback:
                            presets = self.get_window_level_presets_callback()
                            # print(f"[DEBUG-WL-PRESETS] ImageViewer context menu: callback exists, got {len(presets) if presets else 0} preset(s)")
                            if presets and len(presets) >= 1:  # Show menu even with single preset
                                preset_menu = context_menu.addMenu("Window/Level Presets")
                                current_index = 0
                                if hasattr(self, 'get_current_preset_index_callback') and self.get_current_preset_index_callback:
                                    current_index = self.get_current_preset_index_callback()
                                    # print(f"[DEBUG-WL-PRESETS] ImageViewer context menu: current preset index = {current_index}")
                                
                                for idx, (wc, ww, is_rescaled, name) in enumerate(presets):
                                    preset_name = name if name else "Default"
                                    action_text = f"{preset_name} (W={ww:.1f}, C={wc:.1f})"
                                    action = preset_menu.addAction(action_text)
                                    action.setCheckable(True)
                                    if idx == current_index:
                                        action.setChecked(True)
                                    action.triggered.connect(lambda checked, i=idx: self.window_level_preset_selected.emit(i))
                                
                                # Invert Image action (moved here, no separator before)
                                invert_action = context_menu.addAction("Invert Image (I)")
                                invert_action.setCheckable(True)
                                invert_action.setChecked(self.image_inverted)
                                invert_action.triggered.connect(self.invert_image)
                                
                                context_menu.addSeparator()
                            # else:
                            #     print(f"[DEBUG-WL-PRESETS] ImageViewer context menu: No presets to show (presets={presets}, len={len(presets) if presets else 0})")
                        # else:
                        #     print(f"[DEBUG-WL-PRESETS] ImageViewer context menu: Callback missing or not set (hasattr={hasattr(self, 'get_window_level_presets_callback')}, callback={getattr(self, 'get_window_level_presets_callback', None)})")
                        
                        # Cine playback actions (only if enabled)
                        if self.cine_controls_enabled:
                            cine_play_action = context_menu.addAction("▶ Play Cine")
                            cine_play_action.triggered.connect(self.cine_play_requested.emit)
                            
                            cine_pause_action = context_menu.addAction("⏸ Pause Cine")
                            cine_pause_action.triggered.connect(self.cine_pause_requested.emit)
                            
                            cine_stop_action = context_menu.addAction("⏹ Stop Cine")
                            cine_stop_action.triggered.connect(self.cine_stop_requested.emit)
                            
                            # Loop Cine action
                            cine_loop_action = context_menu.addAction("Loop Cine")
                            cine_loop_action.setCheckable(True)
                            # Get current loop state if callback is available
                            if self.get_cine_loop_state_callback is not None:
                                loop_enabled = self.get_cine_loop_state_callback()
                                cine_loop_action.setChecked(loop_enabled)
                            cine_loop_action.triggered.connect(
                                lambda checked: self.cine_loop_toggled.emit(checked)
                            )
                            
                            context_menu.addSeparator()
                        
                        # Left Mouse Button actions (moved to first level, grouped with separators)
                        left_mouse_actions = {
                            "Select (S)": "select",
                            "Zoom (Z)": "zoom",
                            "Pan (P)": "pan",
                            "Magnifier (G)": "magnifier",
                            "Ellipse ROI (E)": "roi_ellipse",
                            "Rectangle ROI (R)": "roi_rectangle",
                            "Crosshair ROI (H)": "crosshair",
                            "Measure (M)": "measure",
                            "Window/Level ROI (W)": "auto_window_level"
                        }
                        for action_text, mode in left_mouse_actions.items():
                            action = context_menu.addAction(action_text)
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
                        
                        # Combine Slices submenu
                        combine_menu = context_menu.addMenu("Combine...")
                        
                        # Enable/disable toggle
                        enable_action = combine_menu.addAction("Enable Combine Slices")
                        enable_action.setCheckable(True)
                        if self.get_projection_enabled_callback:
                            enable_action.setChecked(self.get_projection_enabled_callback())
                        enable_action.triggered.connect(
                            lambda checked: self.projection_enabled_changed.emit(checked)
                        )
                        
                        combine_menu.addSeparator()
                        
                        # Projection type submenu
                        projection_type_menu = combine_menu.addMenu("Projection Type")
                        from PySide6.QtGui import QActionGroup
                        projection_type_group = QActionGroup(projection_type_menu)
                        projection_type_group.setExclusive(True)
                        
                        aip_action = projection_type_menu.addAction("Average (AIP)")
                        aip_action.setCheckable(True)
                        projection_type_group.addAction(aip_action)
                        if self.get_projection_type_callback:
                            aip_action.setChecked(self.get_projection_type_callback() == "aip")
                        aip_action.triggered.connect(
                            lambda: self.projection_type_changed.emit("aip")
                        )
                        
                        mip_action = projection_type_menu.addAction("Maximum (MIP)")
                        mip_action.setCheckable(True)
                        projection_type_group.addAction(mip_action)
                        if self.get_projection_type_callback:
                            mip_action.setChecked(self.get_projection_type_callback() == "mip")
                        mip_action.triggered.connect(
                            lambda: self.projection_type_changed.emit("mip")
                        )
                        
                        minip_action = projection_type_menu.addAction("Minimum (MinIP)")
                        minip_action.setCheckable(True)
                        projection_type_group.addAction(minip_action)
                        if self.get_projection_type_callback:
                            minip_action.setChecked(self.get_projection_type_callback() == "minip")
                        minip_action.triggered.connect(
                            lambda: self.projection_type_changed.emit("minip")
                        )
                        
                        # Slice count submenu
                        slice_count_menu = combine_menu.addMenu("Slice Count")
                        slice_count_group = QActionGroup(slice_count_menu)
                        slice_count_group.setExclusive(True)
                        
                        for count in [2, 3, 4, 6, 8]:
                            count_action = slice_count_menu.addAction(str(count))
                            count_action.setCheckable(True)
                            slice_count_group.addAction(count_action)
                            if self.get_projection_slice_count_callback:
                                count_action.setChecked(self.get_projection_slice_count_callback() == count)
                            count_action.triggered.connect(
                                lambda checked, c=count: self.projection_slice_count_changed.emit(c) if checked else None
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
                        
                        context_menu.addSeparator()
                        
                        # About this File action (at the bottom)
                        about_this_file_action = context_menu.addAction("About this File...")
                        about_this_file_action.triggered.connect(self.about_this_file_requested.emit)
                        
                        context_menu.exec(event.globalPosition().toPoint())
            
            # Reset right mouse drag tracking
            self.right_mouse_drag_start_pos = None
            self.right_mouse_drag_start_center = None
            self.right_mouse_drag_start_width = None
            self.right_mouse_context_menu_shown = False
        
        super().mouseReleaseEvent(event)
    
    def viewportEvent(self, event: QEvent) -> bool:
        """
        Override viewportEvent to catch mouse move events even when ScrollHandDrag is active.
        This ensures pixel info updates work consistently in all modes, including pan mode.
        
        Args:
            event: Viewport event
            
        Returns:
            True if event was handled, False otherwise
        """
        # Handle mouse move events to update pixel info even when ScrollHandDrag is active
        if event.type() == QEvent.Type.MouseMove and isinstance(event, QMouseEvent):
            # Update pixel info for all mouse move events, regardless of drag mode
            self._update_pixel_info(event)
        
        # Let Qt handle the event normally (for ScrollHandDrag, etc.)
        return super().viewportEvent(event)
    
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
            timestamp = time.time()
            focused_widget = QApplication.focusWidget()
            focus_info = f"focused={focused_widget.objectName() if focused_widget else 'None'}"
            print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer.keyPressEvent: LEFT arrow, {focus_info}")
            # Only handle if series navigator doesn't have focus
            if focused_widget:
                # Check if focused widget is the series navigator or one of its children
                widget = focused_widget
                while widget:
                    if widget.objectName() == "series_navigator" or widget.objectName() == "series_navigator_scroll_area" or widget.objectName() == "series_navigator_container":
                        # Series navigator has focus, let it handle the event
                        print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer: Series navigator has focus, skipping emit")
                        return
                    widget = widget.parent()
            print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer: Emitting series_navigation_requested(-1)")
            self.series_navigation_requested.emit(-1)
            event.accept()
        elif event.key() == Qt.Key.Key_Right:
            # Right arrow: next series
            timestamp = time.time()
            focused_widget = QApplication.focusWidget()
            focus_info = f"focused={focused_widget.objectName() if focused_widget else 'None'}"
            print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer.keyPressEvent: RIGHT arrow, {focus_info}")
            # Only handle if series navigator doesn't have focus
            if focused_widget:
                # Check if focused widget is the series navigator or one of its children
                widget = focused_widget
                while widget:
                    if widget.objectName() == "series_navigator" or widget.objectName() == "series_navigator_scroll_area" or widget.objectName() == "series_navigator_container":
                        # Series navigator has focus, let it handle the event
                        print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer: Series navigator has focus, skipping emit")
                        return
                    widget = widget.parent()
            print(f"[DEBUG-NAV] [{timestamp:.6f}] ImageViewer: Emitting series_navigation_requested(1)")
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
        
        Updates overlay positions immediately for smooth panning, using
        a debounced timer only to ensure final position is correct when
        panning stops.
        """
        # Check if scrollbar values actually changed
        current_h = self.horizontalScrollBar().value()
        current_v = self.verticalScrollBar().value()
        
        if current_h != self.last_horizontal_scroll or current_v != self.last_vertical_scroll:
            self.last_horizontal_scroll = current_h
            self.last_vertical_scroll = current_v
            
            # Emit transform_changed immediately for smooth updates during panning
            # This ensures overlay positions update in sync with viewport movement
            self.transform_changed.emit()
            
            # Also set up a debounced timer for a final update when panning stops
            # This ensures overlay positions are correct even if rapid panning
            # causes some updates to be missed
            if self._pan_update_timer is not None and self._pan_update_timer.isActive():
                self._pan_update_timer.stop()
            
            if self._pan_update_timer is None:
                self._pan_update_timer = QTimer()
                self._pan_update_timer.setSingleShot(True)
                self._pan_update_timer.timeout.connect(lambda: self.transform_changed.emit())
            
            # Start timer with short delay - this will fire if panning stops
            # and ensures final position is correct
            self._pan_update_timer.start(10)
    
    def get_viewport_center_scene(self) -> Optional[QPointF]:
        """
        Get the current viewport center point in scene coordinates.
        
        Returns:
            QPointF representing the viewport center in scene coordinates,
            or None if viewport is not available
        """
        if self.viewport() is None:
            return None
        
        # Calculate viewport center in viewport coordinates
        viewport_center_viewport = QPointF(
            self.viewport().width() / 2.0,
            self.viewport().height() / 2.0
        )
        
        # Convert to scene coordinates
        scene_center = self.mapToScene(viewport_center_viewport.toPoint())
        return scene_center
    
    def set_pixel_info_callbacks(
        self,
        get_dataset: Callable[[], Any],
        get_slice_index: Callable[[], int],
        get_use_rescaled: Callable[[], bool]
    ) -> None:
        """
        Set callbacks to get current dataset, slice index, and rescale setting for pixel value display.
        
        Args:
            get_dataset: Callback to get current DICOM dataset
            get_slice_index: Callback to get current slice index
            get_use_rescaled: Callback to get whether to use rescaled values
        """
        self.get_current_dataset_callback = get_dataset
        self.get_current_slice_index_callback = get_slice_index
        self.get_use_rescaled_values_callback = get_use_rescaled
    
    def _update_pixel_info(self, event: QMouseEvent) -> None:
        """
        Update pixel information based on cursor position.
        
        Args:
            event: Mouse event
        """
        if self.image_item is None:
            self.pixel_info_changed.emit("", 0, 0, 0)
            return
        
        # Convert viewport coordinates to scene coordinates
        scene_pos = self.mapToScene(event.position().toPoint())
        
        # Get image item bounding rect
        image_rect = self.image_item.boundingRect()
        
        # Check if cursor is over the image
        if not image_rect.contains(scene_pos):
            self.pixel_info_changed.emit("", 0, 0, 0)
            return
        
        # Convert scene coordinates to image pixel coordinates
        # Image item is positioned at (0, 0) in scene, so scene_pos is relative to image
        x = int(scene_pos.x())
        y = int(scene_pos.y())
        
        # Clamp to image bounds
        x = max(0, min(x, int(image_rect.width()) - 1))
        y = max(0, min(y, int(image_rect.height()) - 1))
        
        # Get z coordinate (slice index)
        z = 0
        if self.get_current_slice_index_callback:
            z = self.get_current_slice_index_callback()
        
        # Get pixel value from dataset
        pixel_value_str = ""
        if self.get_current_dataset_callback:
            dataset = self.get_current_dataset_callback()
            if dataset is not None:
                use_rescaled = False
                if self.get_use_rescaled_values_callback:
                    use_rescaled = self.get_use_rescaled_values_callback()
                
                pixel_value_str = self._get_pixel_value_at_coords(dataset, x, y, z, use_rescaled)
        
        # Emit signal with pixel info
        self.pixel_info_changed.emit(pixel_value_str, x, y, z)
    
    def _extract_image_region(self, center_x: float, center_y: float, size: int, zoom_factor: float) -> Optional[QPixmap]:
        """
        Extract a region from the displayed image for magnifier.
        
        Args:
            center_x: Scene X coordinate of center point
            center_y: Scene Y coordinate of center point
            size: Size of region to extract (in scene coordinates before zoom)
            zoom_factor: Magnification factor to apply
            
        Returns:
            QPixmap of the extracted and magnified region, or None if extraction fails
        """
        if self.image_item is None:
            return None
        
        # Get the pixmap from the image item
        source_pixmap = self.image_item.pixmap()
        if source_pixmap.isNull():
            return None
        
        # Calculate region bounds in pixmap coordinates
        # The image item is positioned at (0, 0) in scene coordinates
        # So scene coordinates directly map to pixmap coordinates
        half_size = size / 2.0
        x1 = max(0, int(center_x - half_size))
        y1 = max(0, int(center_y - half_size))
        x2 = min(source_pixmap.width(), int(center_x + half_size))
        y2 = min(source_pixmap.height(), int(center_y + half_size))
        
        # Check if region is valid
        if x2 <= x1 or y2 <= y1:
            return None
        
        # Extract region from pixmap
        extracted_width = x2 - x1
        extracted_height = y2 - y1
        region = source_pixmap.copy(x1, y1, extracted_width, extracted_height)
        
        print(f"[DEBUG-MAGNIFIER] _extract_image_region: center=({center_x:.1f}, {center_y:.1f}), size={size:.3f}, zoom_factor={zoom_factor:.3f}")
        print(f"[DEBUG-MAGNIFIER] _extract_image_region: extracted_region=({x1}, {y1}) to ({x2}, {y2}), dimensions=({extracted_width}x{extracted_height})")
        
        # Apply zoom factor
        if zoom_factor != 1.0:
            scaled_width = int(extracted_width * zoom_factor)
            scaled_height = int(extracted_height * zoom_factor)
            print(f"[DEBUG-MAGNIFIER] _extract_image_region: scaling to ({scaled_width}x{scaled_height})")
            region = region.scaled(
                scaled_width,
                scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            print(f"[DEBUG-MAGNIFIER] _extract_image_region: final_pixmap_size=({region.width()}x{region.height()})")
        else:
            print(f"[DEBUG-MAGNIFIER] _extract_image_region: no scaling, final_pixmap_size=({region.width()}x{region.height()})")
        
        return region
    
    def _get_pixel_value_at_coords(
        self,
        dataset,
        x: int,
        y: int,
        z: int,
        use_rescaled: bool
    ) -> str:
        """
        Get pixel value at specified coordinates.
        
        Args:
            dataset: DICOM dataset
            x: X coordinate (column)
            y: Y coordinate (row)
            z: Z coordinate (slice index)
            use_rescaled: Whether to use rescaled values
            
        Returns:
            Formatted string with pixel value(s)
        """
        try:
            from pydicom.dataset import Dataset
            from core.dicom_processor import DICOMProcessor
            
            # Get pixel array
            pixel_array = DICOMProcessor.get_pixel_array(dataset)
            if pixel_array is None:
                return ""
            
            # Determine if this is a color image by checking SamplesPerPixel
            samples_per_pixel = 1
            if hasattr(dataset, 'SamplesPerPixel'):
                spp_value = dataset.SamplesPerPixel
                if isinstance(spp_value, (list, tuple)):
                    samples_per_pixel = int(spp_value[0])
                else:
                    samples_per_pixel = int(spp_value)
            
            is_color = samples_per_pixel > 1
            
            # Handle different array shapes
            array_shape = pixel_array.shape
            
            if len(array_shape) == 4:
                # Multi-frame color: shape is (frames, rows, columns, channels)
                if z < 0 or z >= array_shape[0]:
                    return ""
                frame_array = pixel_array[z]
            elif len(array_shape) == 3:
                # Could be:
                # - Single-frame color: (height, width, channels) where channels = 3
                # - Multi-frame grayscale: (frames, height, width) where frames > 1
                if is_color and array_shape[2] == samples_per_pixel:
                    # Single-frame color: (height, width, channels)
                    frame_array = pixel_array
                elif not is_color and array_shape[0] > 1:
                    # Multi-frame grayscale: (frames, height, width)
                    if z < 0 or z >= array_shape[0]:
                        return ""
                    frame_array = pixel_array[z]
                else:
                    # Single-frame grayscale or ambiguous - check last dimension
                    if array_shape[2] == 3:
                        # Likely single-frame color
                        frame_array = pixel_array
                    else:
                        # Single-frame grayscale (shouldn't happen with 3D, but handle it)
                        frame_array = pixel_array
            else:
                # Single-frame grayscale: shape is (height, width)
                frame_array = pixel_array
            
            # Check bounds and extract pixel value
            if len(frame_array.shape) == 2:
                # Grayscale
                if y < 0 or y >= frame_array.shape[0] or x < 0 or x >= frame_array.shape[1]:
                    return ""
                pixel_value = float(frame_array[y, x])
                
                # Apply rescale if needed
                if use_rescaled:
                    slope = getattr(dataset, 'RescaleSlope', 1.0)
                    intercept = getattr(dataset, 'RescaleIntercept', 0.0)
                    if isinstance(slope, (list, tuple)):
                        slope = float(slope[0])
                    else:
                        slope = float(slope)
                    if isinstance(intercept, (list, tuple)):
                        intercept = float(intercept[0])
                    else:
                        intercept = float(intercept)
                    pixel_value = pixel_value * slope + intercept
                
                # Format pixel value
                if pixel_value == int(pixel_value):
                    return str(int(pixel_value))
                else:
                    return f"{pixel_value:.1f}"
                    
            elif len(frame_array.shape) == 3:
                # Color (RGB)
                if y < 0 or y >= frame_array.shape[0] or x < 0 or x >= frame_array.shape[1]:
                    return ""
                if frame_array.shape[2] < 3:
                    return ""
                
                r = int(frame_array[y, x, 0])
                g = int(frame_array[y, x, 1])
                b = int(frame_array[y, x, 2])
                
                # Apply rescale if needed (to all channels)
                if use_rescaled:
                    slope = getattr(dataset, 'RescaleSlope', 1.0)
                    intercept = getattr(dataset, 'RescaleIntercept', 0.0)
                    if isinstance(slope, (list, tuple)):
                        slope = float(slope[0])
                    else:
                        slope = float(slope)
                    if isinstance(intercept, (list, tuple)):
                        intercept = float(intercept[0])
                    else:
                        intercept = float(intercept)
                    
                    r = int(r * slope + intercept)
                    g = int(g * slope + intercept)
                    b = int(b * slope + intercept)
                
                return f"R={r}, G={g}, B={b}"
            else:
                return ""
            
        except Exception as e:
            # Silently fail - don't spam console with errors
            return ""
    
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
    
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        """
        Handle drag enter event - accept files and folders.
        
        Args:
            event: QDragEnterEvent
        """
        if event.mimeData().hasUrls():
            # Check if any of the URLs are files or directories
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path and os.path.exists(path):
                    # Accept if at least one valid file/folder exists
                    event.acceptProposedAction()
                    return
        
        event.ignore()
    
    def dragMoveEvent(self, event: QDragEnterEvent) -> None:
        """
        Handle drag move event - accept files and folders.
        
        Args:
            event: QDragEnterEvent (dragMoveEvent uses same event type)
        """
        if event.mimeData().hasUrls():
            # Check if any of the URLs are files or directories
            urls = event.mimeData().urls()
            for url in urls:
                path = url.toLocalFile()
                if path and os.path.exists(path):
                    # Accept if at least one valid file/folder exists
                    event.acceptProposedAction()
                    return
        
        event.ignore()
    
    def dropEvent(self, event: QDropEvent) -> None:
        """
        Handle drop event - emit signal with dropped file/folder paths.
        
        Args:
            event: QDropEvent
        """
        if not event.mimeData().hasUrls():
            event.ignore()
            return
        
        urls = event.mimeData().urls()
        if not urls:
            event.ignore()
            return
        
        # Extract file paths
        paths = []
        
        for url in urls:
            path = url.toLocalFile()
            if not path:
                continue
            
            if os.path.isfile(path) or os.path.isdir(path):
                paths.append(path)
        
        # Emit signal with paths if any valid paths found
        if paths:
            self.files_dropped.emit(paths)
        
        event.acceptProposedAction()

