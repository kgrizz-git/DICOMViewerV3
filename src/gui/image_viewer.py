"""
Image Viewer Widget

Coordinates display and interaction via `ImageViewerInputMixin`, `ImageViewerViewMixin`,
and `image_viewer_context_menu` (Phase 3). Behavior matches the pre-split implementation.

Requirements: PySide6, PIL, numpy.
"""
from __future__ import annotations

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QWidget
from PySide6.QtCore import Qt, QPointF, Signal, QTimer
from PySide6.QtGui import QColor, QPainter, QTransform
from PIL import Image
import os
from typing import Optional, Callable, Any, List, Tuple, TYPE_CHECKING

from gui.image_viewer_input import ImageViewerInputMixin
from gui.image_viewer_view import ImageViewerViewMixin
from gui.edge_reveal_slider_overlay import EdgeRevealSliderOverlay
from gui.no_pixel_placeholder_overlay import NoPixelPlaceholderOverlay

if TYPE_CHECKING:
    from tools.roi_manager import ROIItem


class ImageViewer(ImageViewerInputMixin, ImageViewerViewMixin, QGraphicsView):
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
    roi_geometry_edit_requested = Signal(object)  # Emitted when user requests resize handles (ROIItem)
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
    cine_play_requested = Signal()  # Legacy; context menu uses cine_play_pause_toggle_requested
    cine_pause_requested = Signal()  # Legacy; context menu uses cine_play_pause_toggle_requested
    cine_play_pause_toggle_requested = Signal()  # Single play/pause action for context menu
    cine_stop_requested = Signal()  # Emitted when cine stop is requested from context menu
    cine_loop_toggled = Signal(bool)  # Emitted when cine loop is toggled from context menu (True = enabled)
    histogram_requested = Signal()  # Emitted when histogram dialog is requested from context menu
    structured_report_browser_requested = Signal()  # Context menu: Structured Report browser for SR
    quick_window_level_requested = Signal()  # Emitted when Quick Window/Level dialog is requested (context menu or shortcut Q)
    export_roi_statistics_requested = Signal()  # Emitted when Export ROI Statistics is requested from context menu
    measurement_started = Signal(QPointF)  # Emitted when measurement starts (start position)
    measurement_updated = Signal(QPointF)  # Emitted when measurement is updated (current position)
    measurement_finished = Signal()  # Emitted when measurement is finished
    measurement_delete_requested = Signal(object)  # Emitted when measurement deletion is requested (MeasurementItem)
    angle_measurement_clicked = Signal(QPointF)  # Placing angle: click P1, P2, then P3
    angle_measurement_preview = Signal(QPointF)  # Cursor move while placing angle
    angle_draw_cancel_requested = Signal()  # Leaving angle mode or Esc: cancel rubber-band
    text_annotation_started = Signal(QPointF)  # Emitted when text annotation starts (position)
    text_annotation_finished = Signal()  # Emitted when text annotation is finished
    arrow_annotation_started = Signal(QPointF)  # Emitted when arrow annotation starts (start position)
    arrow_annotation_updated = Signal(QPointF)  # Emitted when arrow annotation is updated (current position)
    arrow_annotation_finished = Signal()  # Emitted when arrow annotation is finished
    text_annotation_delete_requested = Signal(object)  # Emitted when text annotation deletion is requested (TextAnnotationItem)
    arrow_annotation_delete_requested = Signal(object)  # Emitted when arrow annotation deletion is requested (ArrowAnnotationItem)
    crosshair_delete_requested = Signal(object)  # Emitted when crosshair deletion is requested (CrosshairItem)
    clear_measurements_requested = Signal()  # Emitted when clear measurements is requested
    toggle_overlay_requested = Signal()  # Emitted when toggle overlay is requested
    privacy_view_toggled = Signal(bool)  # Emitted when privacy view is toggled from context menu (True = enabled)
    smooth_when_zoomed_toggled = Signal(bool)  # Emitted when smooth when zoomed is toggled from context menu (True = enabled)
    scale_markers_toggled = Signal(bool)  # Emitted when scale markers are toggled from context menu (True = enabled)
    direction_labels_toggled = Signal(bool)  # Emitted when direction labels are toggled from context menu (True = enabled)
    slice_sync_toggled = Signal(bool)  # Emitted when slice sync is toggled from context menu (True = enabled)
    slice_sync_manage_requested = Signal()  # Emitted when slice sync group management is requested from context menu
    slice_location_lines_toggled = Signal(bool)  # Emitted when slice location lines toggled from context menu (True = show)
    slice_location_lines_same_group_only_toggled = Signal(bool)  # Emitted when same-group-only toggled (True = only same group)
    slice_location_lines_focused_only_toggled = Signal(bool)  # Emitted when focused-only toggled (True = only focused window)
    slice_location_lines_mode_toggled = Signal(str)  # Emitted when line mode toggled from context menu ("middle" or "begin_end")
    left_pane_toggle_requested = Signal()  # Emitted when Show/Hide Left Pane is requested from context menu
    right_pane_toggle_requested = Signal()  # Emitted when Show/Hide Right Pane is requested from context menu
    annotation_options_requested = Signal()  # Emitted when annotation options dialog is requested
    overlay_settings_requested = Signal()  # Emitted when Overlay Settings dialog is requested from context menu
    overlay_config_requested = Signal()  # Emitted when Configure Overlay Tags dialog is requested from context menu
    crosshair_clicked = Signal(QPointF, str, int, int, int)  # Emitted when crosshair tool is clicked (pos, pixel_value_str, x, y, z)
    about_this_file_requested = Signal()  # Emitted when About this File is requested from context menu
    assign_series_requested = Signal(str)  # Emitted when series assignment is requested (series_uid)
    pixel_info_changed = Signal(str, int, int, int)  # Emitted when pixel info changes (pixel_value_str, x, y, z)
    files_dropped = Signal(list)  # Emitted when files/folders are dropped (list of paths)
    projection_enabled_changed = Signal(bool)  # Emitted when projection enabled state changes from context menu
    projection_type_changed = Signal(str)  # Emitted when projection type changes from context menu ("aip", "mip", "minip")
    projection_slice_count_changed = Signal(int)  # Emitted when projection slice count changes from context menu
    layout_change_requested = Signal(str)  # Emitted when layout change is requested from context menu ("1x1", "1x2", "2x1", "2x2")
    swap_view_requested = Signal(int)  # Emitted when user chooses Swap with View X (argument = other view index 0-3)
    window_slot_map_popup_requested = Signal()  # Emitted when user requests window-slot map popup from Swap menu
    create_mpr_view_requested = Signal()  # Emitted when "Create MPR view…" is chosen from context menu
    clear_mpr_view_requested = Signal()  # Emitted when "Clear MPR view" is chosen from context menu
    clear_window_content_requested = Signal()  # Clear this pane only; subwindow_index identifies target

    @property
    def scene(self) -> QGraphicsScene:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Graphics scene for items in this viewer (legacy attribute-style access)."""
        return self._graphics_scene

    def __init__(self, parent: Optional[QWidget] = None, config_manager=None):
        """
        Initialize the image viewer.
        
        Args:
            parent: Parent widget
            config_manager: Optional ConfigManager instance for overlay font settings
        """
        super().__init__(parent)
        self.config_manager = config_manager
        
        # View index (0-3) when used in multi-window layout; set by app so context menu can build Swap submenu
        self.subwindow_index: Optional[int] = None
        # Callback to get current slot_to_view [4 ints] for Swap menu (Window 1-4 = slot 0-3). Set by app.
        self.get_slot_to_view_callback: Optional[Callable[[], List[int]]] = None
        # Callback returning True when this subwindow is in MPR mode (used to show Clear vs Create).
        self.is_mpr_view_callback: Optional[Callable[[], bool]] = None
        # Per-subwindow override flag set by MprController to suppress tool activation in MPR mode.
        self._mpr_mode_override: bool = False
        
        # Set transformation anchor to viewport center for consistent zoom behavior
        # This anchor should remain constant - when set, scale() automatically centers zooming on viewport center
        # No manual translation is needed when using scale() with AnchorViewCenter
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # Set alignment to center the scene when it's smaller than viewport
        # This ensures small images are centered, not positioned at top-left
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Graphics scene for all viewer items
        self._graphics_scene = QGraphicsScene(self)
        self.setScene(self._graphics_scene)
        
        # Enable mouse tracking for hover events (pixel info updates)
        self.setMouseTracking(True)
        
        # Image item
        self.image_item: Optional[QGraphicsPixmapItem] = None
        
        # Image inversion state
        self.image_inverted: bool = False
        self.original_image: Optional[Image.Image] = None  # Store original image for inversion
        
        # Callback to notify when inversion state changes (for persistence per series)
        self.inversion_state_changed_callback: Optional[Callable[[bool], None]] = None

        # Orientation state (flip and rotation) — non-destructive display transforms
        self._flip_h: bool = False  # Horizontal flip (mirror left-right)
        self._flip_v: bool = False  # Vertical flip (mirror top-bottom)
        self._rotation_deg: int = 0  # Rotation in degrees: 0, 90, 180, 270

        # Callback to notify when orientation changes (for persistence per series)
        # Called with (flip_h: bool, flip_v: bool, rotation_deg: int)
        self.orientation_changed_callback: Optional[Callable[[bool, bool, int], None]] = None
        
        # Callbacks to get current dataset and slice index for pixel value display
        self.get_current_dataset_callback: Optional[Callable[[], Any]] = None
        self.get_current_slice_index_callback: Optional[Callable[[], int]] = None
        self.get_use_rescaled_values_callback: Optional[Callable[[], bool]] = None
        # Callback to get file path for current slice (for "Show file" context menu)
        self.get_file_path_callback: Optional[Callable[[], Optional[str]]] = None
        
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
        
        # Text annotation state
        self.text_annotating = False
        self.text_annotation_start_pos: Optional[QPointF] = None
        
        # Arrow annotation state
        self.arrow_annotating = False
        self.arrow_annotation_start_pos: Optional[QPointF] = None
        
        # Zoom mode state
        self.zoom_start_pos: Optional[QPointF] = None
        self.zoom_start_zoom: Optional[float] = None
        self.zoom_mouse_moved = False  # Track if mouse actually moved during zoom drag
        
        # Magnifier state
        from gui.magnifier_widget import MagnifierWidget
        self.magnifier_widget: Optional[MagnifierWidget] = None
        self.magnifier_active: bool = False
        # Note: magnifier zoom is calculated dynamically as 1.5 * current_zoom
        # Handle-drag magnifier: separate widget for Shift+drag on measurement handle
        self.handle_drag_magnifier_widget: Optional[MagnifierWidget] = None
        self.handle_drag_magnifier_active: bool = False
        self._handle_drag_magnifier_size = 200
        
        # Scroll wheel mode
        self.scroll_wheel_mode = "slice"  # "slice" or "zoom"
        
        # Callback to get cine loop state (set from main.py)
        self.get_cine_loop_state_callback: Optional[Callable[[], bool]] = None
        # Whether cine is currently playing (for context menu play/pause label)
        self.get_cine_is_playing_callback: Optional[Callable[[], bool]] = None
        # Whether this pane has content that Clear This Window can remove
        self.get_clear_this_window_enabled_callback: Optional[Callable[[], bool]] = None
        self.get_available_series_callback: Optional[Callable[[], List[Tuple[str, str]]]] = None

        # Slice-location line visibility and mode (optional; filled by app for context menu sync)
        self.get_slice_location_lines_visible_callback: Optional[Callable[[], bool]] = None
        self.get_slice_location_lines_same_group_only_callback: Optional[Callable[[], bool]] = None
        self.get_slice_location_lines_focused_only_callback: Optional[Callable[[], bool]] = None
        self.get_slice_location_lines_mode_callback: Optional[Callable[[], str]] = None
        
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

        # Smooth image when zoomed (display option; applied to view and image item)
        self._smooth_when_zoomed: bool = False
        # Viewer overlays (independent from metadata corner overlays)
        self._show_scale_markers: bool = False
        self._show_direction_labels: bool = False
        self._scale_markers_color: Tuple[int, int, int] = (255, 255, 0)
        self._direction_labels_color: Tuple[int, int, int] = (255, 255, 0)
        self._direction_label_size: int = 16
        self._scale_markers_major_tick_interval_mm: int = 10
        self._scale_markers_minor_tick_interval_mm: int = 5
        # Slice sync state (for context menu synchronization)
        self._slice_sync_enabled: bool = False
        # When True, we are in "interacting" state (zoom/pan just happened); use fast transform until idle timer fires
        self._smooth_idle_interacting: bool = False
        # Single-shot timer: when it fires, we leave "interacting" state and apply smooth mode if enabled
        self._smooth_idle_timer = QTimer(self)
        self._smooth_idle_timer.setSingleShot(True)
        self._smooth_idle_timer.timeout.connect(self._on_smooth_idle_timeout)
        
        # Callbacks for window/level presets (set from main.py)
        self.get_window_level_presets_callback: Optional[Callable[[], List[Tuple[float, float, bool, Optional[str]]]]] = None
        self.get_current_preset_index_callback: Optional[Callable[[], int]] = None
        
        # Callback to get ROI from item (set from main.py)
        self.get_roi_from_item_callback: Optional[Callable[[object], Optional["ROIItem"]]] = None
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
        # SmoothPixmapTransform is set/cleared by _apply_smoothing_mode() based on _smooth_when_zoomed
        
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

        # Apply initial smoothing mode (view hint only when no image yet)
        self._apply_smoothing_mode()

        # ------------------------------------------------------------------ #
        # Edge-reveal slice/frame slider overlay
        # ------------------------------------------------------------------ #
        # Must be a child of the *viewport* so its geometry is viewport-local.
        self._slider_overlay = EdgeRevealSliderOverlay(self.viewport())
        self._slider_overlay.slider_value_changed.connect(
            self._on_slider_overlay_value_changed
        )
        # Bottom hint + optional "Open tag browser…" for SR / no-pixel datasets
        self._no_pixel_placeholder_overlay = NoPixelPlaceholderOverlay(self.viewport())
        # Global on/off toggle (driven by View menu).  True by default.
        self._slice_slider_enabled: bool = True
        # Called with 0-based slice index when the user drags the overlay slider.
        # Wired by subwindow_lifecycle_controller after each focus change.
        self.slider_navigate_callback: Optional[Callable[[int], None]] = None

    # -------------------------------------------------------------------------
    # Orientation (flip / rotate) public API
    # -------------------------------------------------------------------------

    def get_flip_h(self) -> bool:
        """Return the current horizontal flip state."""
        return self._flip_h

    def get_flip_v(self) -> bool:
        """Return the current vertical flip state."""
        return self._flip_v

    def get_rotation_deg(self) -> int:
        """Return the current rotation in degrees (0, 90, 180, or 270)."""
        return self._rotation_deg

    def set_flip_h(self, v: bool) -> None:
        """Set horizontal flip state and refresh the view transform."""
        self._flip_h = v
        self._apply_view_transform()
        self._notify_orientation_changed()

    def set_flip_v(self, v: bool) -> None:
        """Set vertical flip state and refresh the view transform."""
        self._flip_v = v
        self._apply_view_transform()
        self._notify_orientation_changed()

    def set_rotation(self, deg: int) -> None:
        """
        Set rotation in degrees, normalised modulo 360 then snapped to the nearest
        multiple of 90° (0, 90, 180, or 270), and refresh the view transform.
        """
        r = (int(deg) % 360 + 360) % 360
        self._rotation_deg = ((r + 45) // 90 % 4) * 90
        self._apply_view_transform()
        self._notify_orientation_changed()

    def reset_orientation(self) -> None:
        """Reset flip and rotation to defaults and refresh the view transform."""
        self._flip_h = False
        self._flip_v = False
        self._rotation_deg = 0
        self._apply_view_transform()
        self._notify_orientation_changed()

    def flip_h(self) -> None:
        """Toggle horizontal flip."""
        self.set_flip_h(not self._flip_h)

    def flip_v(self) -> None:
        """Toggle vertical flip."""
        self.set_flip_v(not self._flip_v)

    def rotate_cw(self) -> None:
        """Rotate 90 degrees clockwise."""
        self.set_rotation((self._rotation_deg + 90) % 360)

    def rotate_ccw(self) -> None:
        """Rotate 90 degrees counter-clockwise."""
        self.set_rotation((self._rotation_deg - 90) % 360)

    def rotate_180(self) -> None:
        """Rotate 180 degrees."""
        self.set_rotation((self._rotation_deg + 180) % 360)

    def _notify_orientation_changed(self) -> None:
        """Call the orientation-changed callback if registered."""
        if self.orientation_changed_callback is not None:
            self.orientation_changed_callback(self._flip_h, self._flip_v, self._rotation_deg)

    # ------------------------------------------------------------------ #
    # Edge-reveal slice/frame slider — public API
    # ------------------------------------------------------------------ #

    def set_slice_slider_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the edge-reveal slice/frame slider globally.

        When disabled the overlay is hidden immediately and will not appear
        on hover until re-enabled.

        Args:
            enabled: True to allow the slider to reveal on hover; False to
                     always hide it.
        """
        self._slice_slider_enabled = enabled
        if not enabled:
            # Reset internal range so hover logic (maximum <= 1) cannot reveal a stale bar.
            self._slider_overlay.set_range_and_value(1, 1, 1, "Slice")
            self._slider_overlay.setVisible(False)

    def set_navigation_slider_state(
        self,
        *,
        enabled: bool,
        minimum: int = 1,
        maximum: int = 1,
        value: int = 1,
        mode_label: str = "Slice",
        reveal: bool = False,
    ) -> None:
        """
        Update the overlay slider range and current position.

        Does **not** reveal the overlay — it only appears when the user
        hovers near the right edge.  Hides the overlay immediately when the
        series has only one slice/frame (``maximum <= minimum``).

        Args:
            enabled:    Whether this subwindow's content has navigable slices.
            minimum:    Lowest 1-based position (normally 1).
            maximum:    Highest 1-based position (== total slices/frames).
            value:      Current 1-based position.
            mode_label: "Slice" or "Frame" label prefix.
            reveal:     If True, briefly reveal the overlay after updating it.
        """
        if not self._slice_slider_enabled or not enabled or maximum <= minimum:
            # Always reset QSlider range/value so _update_slider_visibility_from_mouse
            # does not treat an old multi-slice maximum as navigable after clear.
            self._slider_overlay.set_range_and_value(1, 1, 1, mode_label)
            self._slider_overlay.setVisible(False)
            return
        self._slider_overlay.set_range_and_value(minimum, maximum, value, mode_label)
        self._reposition_slider_overlay()
        if reveal:
            self._slider_overlay.reveal()

    def _on_slider_overlay_value_changed(self, value: int) -> None:
        """
        Handle the user dragging the edge-reveal slider.

        Converts the 1-based slider value to a 0-based slice index and calls
        the registered ``slider_navigate_callback`` (if any).

        Args:
            value: 1-based slice/frame position chosen by the user.
        """
        if self.slider_navigate_callback is not None:
            self.slider_navigate_callback(value - 1)

    def _reposition_slider_overlay(self) -> None:
        """
        Re-geometry the slider overlay to sit along the right edge of the
        viewport.  Called from resizeEvent and after layout changes.
        """
        vp = self.viewport()
        if vp is None:
            return
        overlay_width = 52
        vp_h = vp.height()
        if vp_h < 80:
            # Too narrow to be useful; keep hidden
            self._slider_overlay.setVisible(False)
            return
        self._slider_overlay.setGeometry(
            vp.width() - overlay_width, 0, overlay_width, vp_h
        )

    def set_no_pixel_placeholder_bar(
        self,
        active: bool,
        *,
        open_callback: Optional[Callable[[], None]] = None,
        show_open_button: bool = True,
    ) -> None:
        """
        Show or hide the bottom bar for structured reports without pixel data.

        When ``active`` and ``show_open_button`` are True and ``open_callback`` is set,
        the user can open the tag browser without using the main menu.
        """
        self._no_pixel_placeholder_overlay.configure(
            active=active,
            show_open_button=show_open_button,
            open_callback=open_callback,
        )
        self._reposition_no_pixel_placeholder_overlay()
        if active:
            self._no_pixel_placeholder_overlay.raise_()

    def _reposition_no_pixel_placeholder_overlay(self) -> None:
        """Pin the SR / no-pixel hint bar to the bottom of the viewport."""
        vp = self.viewport()
        if vp is None:
            return
        bar_h = 88
        if not self._no_pixel_placeholder_overlay.isVisible():
            return
        if vp.height() < bar_h + 40:
            self._no_pixel_placeholder_overlay.setGeometry(0, 0, vp.width(), min(vp.height(), bar_h + 20))
            return
        self._no_pixel_placeholder_overlay.setGeometry(0, vp.height() - bar_h, vp.width(), bar_h)

