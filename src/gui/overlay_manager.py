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

from typing import Any

from PySide6.QtCore import QRectF, Qt
from PySide6.QtWidgets import QGraphicsTextItem, QLabel, QWidget

from core.dicom_parser import DICOMParser
from gui.overlay_items_factory import create_graphics_overlay_text_item
from gui.overlay_position_updater import (
    OVERLAY_VIEWPORT_MARGIN_PX,
    build_viewport_corner_anchors,
    filter_valid_overlay_items,
    position_left_aligned_corner_item,
    position_right_aligned_corner_items,
    resolve_corner_max_width_viewport,
    resolve_view_for_scene,
    schedule_scene_viewport_repaint,
    sync_widget_overlay_geometry,
)
from gui.overlay_text_builder import (
    get_corner_text,
    get_modality,
    merge_simple_and_detailed_extra_corner_tags,
)
from gui.view_transform_helpers import graphics_view_uniform_zoom
from utils.bundled_fonts import make_qfont

# MPR top-centre banner: keep below "Show Direction Labels" top edge text (~16px + font).
_MPR_BANNER_EXTRA_TOP_PX = 30
# Slightly above overlay corner text so the banner stays readable but unobtrusive.
_MPR_BANNER_FONT_MIN_PT = 9
_MPR_BANNER_FONT_OFFSET_PT = 1
# Semi-transparent panel so edge direction labels remain visible if overlap occurs.
_MPR_BANNER_BG_STYLE = "rgba(0, 0, 0, 88)"


class ViewportOverlayWidget(QWidget):
    """
    Widget container for viewport-based overlay labels.
    
    Manages QLabel widgets positioned at viewport corners (not scene coordinates).
    These widgets stay fixed at viewport positions regardless of zoom/pan.
    
    Features:
    - Four corner labels (upper_left, upper_right, lower_left, lower_right)
    - Viewport pixel-based positioning (no scene coordinate conversion needed)
    - Automatic position updates on viewport resize
    - Same styling as QGraphicsItem overlays
    """

    def __init__(self, parent: QWidget | None = None, font_size: int = 6,
                 font_color: tuple[int, int, int] = (255, 255, 0), font_family: str = "IBM Plex Sans",
                 font_variant: str = "Bold"):
        """
        Initialize the viewport overlay widget.

        Args:
            parent: Parent widget (should be ImageViewer's viewport)
            font_size: Font size in points
            font_color: Font color as (r, g, b) tuple
            font_family: Font family name (must be a bundled font)
            font_variant: Font variant (e.g. "Bold", "Regular")
        """
        super().__init__(parent)
        self.font_size = font_size
        self.font_color = font_color
        self.font_family = font_family
        self.font_variant = font_variant

        # Set widget to be transparent and not interfere with mouse events
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setStyleSheet("background: transparent;")

        # Ensure widget stays fixed at viewport coordinates
        # Set widget to use absolute positioning relative to viewport
        # This prevents the widget from being affected by parent transforms
        if parent:
            # Set geometry immediately to ensure widget is positioned correctly
            self.setGeometry(0, 0, parent.width(), parent.height())

        # Create labels for each corner
        self.corner_labels: dict[str, QLabel] = {
            "upper_left": QLabel(self),
            "upper_right": QLabel(self),
            "lower_left": QLabel(self),
            "lower_right": QLabel(self)
        }

        # Configure labels
        font = make_qfont(font_family, font_variant, font_size)

        for label in self.corner_labels.values():
            label.setFont(font)
            label.setStyleSheet(f"color: rgb({font_color[0]}, {font_color[1]}, {font_color[2]}); background: transparent;")
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            label.hide()  # Hide by default until content is set

        # Margin in viewport pixels
        self.margin = 10

        # MPR banner label (top-centre, shown only in MPR mode).
        self.mpr_banner_label = QLabel("", self)
        mpr_font = make_qfont(
            font_family,
            font_variant,
            max(font_size + _MPR_BANNER_FONT_OFFSET_PT, _MPR_BANNER_FONT_MIN_PT),
        )
        self.mpr_banner_label.setFont(mpr_font)
        self.mpr_banner_label.setStyleSheet(
            f"color: rgb(255, 220, 50); background: {_MPR_BANNER_BG_STYLE};"
            " padding: 1px 6px; border-radius: 3px;"
        )
        self.mpr_banner_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.mpr_banner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.mpr_banner_label.hide()

    def set_mpr_banner(self, text: str | None) -> None:
        """
        Show or hide the MPR banner at the top-centre of the viewport.

        Args:
            text: Banner text (e.g. "MPR – Coronal"), or None to hide.
        """
        if text:
            self.mpr_banner_label.setText(text)
            self.mpr_banner_label.adjustSize()
            self._position_mpr_banner()
            self.mpr_banner_label.show()
        else:
            self.mpr_banner_label.hide()

    def _position_mpr_banner(self) -> None:
        """Centre the MPR banner horizontally, below top edge direction labels."""
        w = self.width()
        label_w = self.mpr_banner_label.width()
        x = max(0, (w - label_w) // 2)
        y = self.margin + _MPR_BANNER_EXTRA_TOP_PX
        self.mpr_banner_label.move(x, y)

    def resizeEvent(self, event) -> None:
        """
        Handle resize events to update label positions.
        
        Args:
            event: Resize event
        """
        super().resizeEvent(event)
        # Update label positions when widget resizes
        # This is the ONLY place where label positions should be updated
        # (not during zoom/pan operations)
        # Debug logging commented out to reduce noise (uncomment if debugging overlay resize issues)
        # print(f"[DEBUG-WIDGET] resizeEvent: widget resized to {event.size().width()}x{event.size().height()}")
        self.update_positions(event.size().width(), event.size().height())
        if self.mpr_banner_label.isVisible():
            self._position_mpr_banner()

    def set_corner_text(self, corner_key: str, text: str, alignment: Qt.AlignmentFlag) -> None:
        """
        Set text for a corner label.
        
        Args:
            corner_key: Corner identifier ("upper_left", "upper_right", "lower_left", "lower_right")
            text: Text to display
            alignment: Text alignment (AlignLeft, AlignRight, etc.)
        """
        if corner_key not in self.corner_labels:
            return

        label = self.corner_labels[corner_key]

        if text:
            label.setText(text)
            label.setAlignment(alignment)
            label.show()
        else:
            label.hide()

    def update_positions(self, viewport_width: int, viewport_height: int) -> None:
        """
        Update label positions based on viewport size.
        
        Args:
            viewport_width: Viewport width in pixels
            viewport_height: Viewport height in pixels
        """
        margin = self.margin

        # Upper left
        upper_left_label = self.corner_labels["upper_left"]
        if upper_left_label.isVisible():
            upper_left_label.move(margin, margin)
            upper_left_label.adjustSize()

        # Upper right
        upper_right_label = self.corner_labels["upper_right"]
        if upper_right_label.isVisible():
            upper_right_label.adjustSize()
            label_width = upper_right_label.width()
            upper_right_label.move(viewport_width - label_width - margin, margin)

        # Lower left
        lower_left_label = self.corner_labels["lower_left"]
        if lower_left_label.isVisible():
            lower_left_label.adjustSize()
            label_height = lower_left_label.height()
            lower_left_label.move(margin, viewport_height - label_height - margin)

        # Lower right
        lower_right_label = self.corner_labels["lower_right"]
        if lower_right_label.isVisible():
            lower_right_label.adjustSize()
            label_width = lower_right_label.width()
            label_height = lower_right_label.height()
            lower_right_label.move(viewport_width - label_width - margin,
                                  viewport_height - label_height - margin)

    def set_font_size(self, font_size: int) -> None:
        """
        Update font size for all labels.

        Args:
            font_size: New font size in points
        """
        self.font_size = font_size
        font = make_qfont(self.font_family, self.font_variant, font_size)
        for label in self.corner_labels.values():
            label.setFont(font)
        mpr_font = make_qfont(
            self.font_family,
            self.font_variant,
            max(font_size + _MPR_BANNER_FONT_OFFSET_PT, _MPR_BANNER_FONT_MIN_PT),
        )
        self.mpr_banner_label.setFont(mpr_font)

    def set_font_family(self, family: str) -> None:
        """
        Update font family for all labels.

        Args:
            family: Font family name
        """
        self.font_family = family
        font = make_qfont(family, self.font_variant, self.font_size)
        for label in self.corner_labels.values():
            label.setFont(font)
        mpr_font = make_qfont(
            family,
            self.font_variant,
            max(self.font_size + _MPR_BANNER_FONT_OFFSET_PT, _MPR_BANNER_FONT_MIN_PT),
        )
        self.mpr_banner_label.setFont(mpr_font)

    def set_font_variant(self, variant: str) -> None:
        """
        Update font variant for all labels.

        Args:
            variant: Font variant name (e.g. "Bold", "Light Italic")
        """
        self.font_variant = variant
        font = make_qfont(self.font_family, variant, self.font_size)
        for label in self.corner_labels.values():
            label.setFont(font)
        mpr_font = make_qfont(
            self.font_family,
            variant,
            max(self.font_size + _MPR_BANNER_FONT_OFFSET_PT, _MPR_BANNER_FONT_MIN_PT),
        )
        self.mpr_banner_label.setFont(mpr_font)

    def set_font_color(self, font_color: tuple[int, int, int]) -> None:
        """
        Update font color for all labels.
        
        Args:
            font_color: Font color as (r, g, b) tuple
        """
        self.font_color = font_color
        style = f"color: rgb({font_color[0]}, {font_color[1]}, {font_color[2]}); background: transparent;"
        for label in self.corner_labels.values():
            label.setStyleSheet(style)

    def clear_all(self) -> None:
        """Clear all corner labels and the MPR banner."""
        for label in self.corner_labels.values():
            label.clear()
            label.hide()
        self.mpr_banner_label.clear()
        self.mpr_banner_label.hide()


class OverlayManager:
    """
    Manages metadata overlays on DICOM images.
    
    Features:
    - Customizable overlay fields
    - Multiple display modes (minimal, detailed, hidden)
    - Text positioning and styling
    - Customizable font size and color

    QWidget vs QGraphics corner text: ``create_overlay_items`` uses either
    ``_create_widget_overlays`` or the QGraphicsItem branch. Both must pass the
    same ``projection_*`` and ``multiframe_context`` arguments into
    ``get_corner_text`` so MPR combine / multiframe strings stay identical
    (see the two ``get_corner_text(...)`` call sites in this file).
    """

    def __init__(self, font_size: int = 6, font_color: tuple[int, int, int] = (255, 255, 0),
                 config_manager=None, use_widget_overlays: bool = True,
                 font_family: str = "IBM Plex Sans", font_variant: str = "Bold"):
        """
        Initialize the overlay manager.

        Args:
            font_size: Default font size in points
            font_color: Default font color as (r, g, b) tuple
            config_manager: Optional ConfigManager instance for overlay tag configuration
            use_widget_overlays: If True, use QWidget viewport overlays instead of QGraphicsItem overlays
            font_family: Font family name for overlay labels
            font_variant: Font variant (e.g. "Bold", "Regular")
        """
        self.mode = "minimal"  # minimal, detailed, hidden (kept for backward compatibility)
        self.visibility_state = 0  # 0=show all, 1=hide corner text, 2=hide all text
        self.custom_fields: list[str] = []
        self.overlay_items: list[QGraphicsTextItem] = []
        self.font_size = font_size
        self.font_color = font_color
        self.font_family = font_family
        self.font_variant = font_variant
        self.config_manager = config_manager
        self.use_widget_overlays = use_widget_overlays  # Flag to switch between approaches
        self.privacy_mode: bool = False

        # Store current parser and scene for updating positions
        self.current_parser: DICOMParser | None = None
        self.current_scene = None
        self.current_total_slices: int | None = None
        self.current_stack_position: int | None = None

        # QWidget overlay widget (viewport-based)
        self.viewport_overlay_widget: ViewportOverlayWidget | None = None

        # Track which items belong to which corner for position updates
        self.corner_item_map: dict[str, list[QGraphicsTextItem]] = {
            "upper_left": [],
            "upper_right": [],
            "lower_left": [],
            "lower_right": []
        }

        # Cache maximum text widths for right-aligned corners (prevents jitter during cine playback)
        # Stores max width in viewport pixels for each right-aligned corner
        self.corner_max_width_map: dict[str, float] = {}

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

    def _corner_tags_for_current_mode(self, modality: str) -> dict[str, list[str]]:
        """
        Resolve per-corner tag keyword lists for the current ``self.mode``.

        Simple (minimal) uses configured ``overlay_tags`` only. Detailed merges
        ``overlay_tags_detailed_extra`` after simple tags (deduplicated).
        """
        if self.config_manager is None:
            return {
                "upper_left": list(self.minimal_fields),
                "upper_right": [],
                "lower_left": [],
                "lower_right": [],
            }
        simple = self.config_manager.get_overlay_tags(modality)
        if self.mode != "detailed":
            return simple
        extras = self.config_manager.get_overlay_tags_detailed_extra(modality)
        return merge_simple_and_detailed_extra_corner_tags(simple, extras)

    def should_show_text_overlays(self) -> bool:
        """
        Return True when metadata-style text overlays should be visible.

        This covers both the regular corner text and the MPR banner so every
        overlay entry point respects the same Spacebar visibility cycle.
        """
        return self.mode != "hidden" and self.visibility_state == 0

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

    def set_custom_fields(self, fields: list[str]) -> None:
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
            if self.viewport_overlay_widget is not None:
                self.viewport_overlay_widget.set_font_size(size)

    def set_font_color(self, r: int, g: int, b: int) -> None:
        """
        Set overlay font color.

        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        self.font_color = (r, g, b)
        if self.viewport_overlay_widget is not None:
            self.viewport_overlay_widget.set_font_color((r, g, b))

    def set_font_family(self, family: str) -> None:
        """
        Set overlay font family and propagate to the viewport widget if it exists.

        Args:
            family: Font family name (should be a bundled font)
        """
        self.font_family = family
        if self.viewport_overlay_widget is not None:
            self.viewport_overlay_widget.set_font_family(family)

    def set_font_variant(self, variant: str) -> None:
        """
        Set overlay font variant and propagate to the viewport widget if it exists.

        Args:
            variant: Font variant name (e.g. "Bold", "Light Italic")
        """
        self.font_variant = variant
        if self.viewport_overlay_widget is not None:
            self.viewport_overlay_widget.set_font_variant(variant)

    def set_privacy_mode(self, enabled: bool) -> None:
        """
        Set privacy mode for masking patient tags in overlays.
        
        Args:
            enabled: True to enable privacy mode, False to disable
        """
        self.privacy_mode = enabled

    def set_mpr_banner(self, text: str | None) -> None:
        """
        Show or hide the MPR banner on this overlay's viewport widget.

        Delegates to ``ViewportOverlayWidget.set_mpr_banner`` if the
        viewport overlay widget is available.

        Args:
            text: Banner text (e.g. "MPR – Coronal"), or None to hide.
        """
        if self.viewport_overlay_widget is not None and hasattr(
            self.viewport_overlay_widget, "set_mpr_banner"
        ):
            self.viewport_overlay_widget.set_mpr_banner(text)

    def _create_text_item(self, text: str, x: float, y: float, alignment: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignLeft, text_width: float | None = None) -> QGraphicsTextItem:
        """Delegate QGraphicsTextItem construction to ``overlay_items_factory``."""
        return create_graphics_overlay_text_item(
            text, x, y, self.font_color, self.font_size, alignment, text_width
        )

    def create_overlay_items(self, scene, parser: DICOMParser,
                            position: tuple[int, int] = (10, 10), total_slices: int | None = None,
                            projection_enabled: bool = False, projection_start_slice: int | None = None,
                            projection_end_slice: int | None = None, projection_total_thickness: float | None = None,
                            projection_type: str | None = None,
                            multiframe_context: dict[str, Any] | None = None,
                            stack_position: int | None = None) -> list[QGraphicsTextItem]:
        """
        Create overlay text items for a graphics scene (4 corners).

        Args:
            scene: QGraphicsScene to add items to
            parser: DICOMParser instance
            position: (x, y) position - ignored, using 4 corners instead
            total_slices: Total number of slices in the series (denominator for "Slice X/Y")
            stack_position: 1-based position of the current slice in the loaded series
                (numerator for "Slice X/Y"); see get_corner_text for details
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
        # Store total_slices / stack_position for position updates
        if total_slices is not None:
            self.current_total_slices = total_slices
        self.current_stack_position = stack_position

        # Get view for QWidget overlay creation
        view = scene.views()[0] if scene.views() else None

        # Use QWidget overlays if enabled
        if self.use_widget_overlays and view is not None:
            return self._create_widget_overlays(view, parser, total_slices, projection_enabled,
                                                projection_start_slice, projection_end_slice,
                                                projection_total_thickness, projection_type,
                                                multiframe_context, stack_position)

        # Clear existing items and corner mapping (QGraphicsItem approach)
        self.clear_overlay_items(scene)
        # Reset corner mapping
        for corner_key in self.corner_item_map:
            self.corner_item_map[corner_key].clear()

        # Hide overlays based on visibility state
        # State 1 and 2 hide corner text overlays
        if not self.should_show_text_overlays():
            return []

        # Get modality and corner tags (simple vs simple+detailed extras)
        modality = get_modality(parser)
        corner_tags = self._corner_tags_for_current_mode(modality)

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
            # Use uniform zoom (not m11): rotation / flip break m11 as a scalar.
            view_scale = graphics_view_uniform_zoom(view)
            viewport_to_scene_scale = 1.0 / view_scale
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
                text = get_corner_text(
                                    parser, tags, self.privacy_mode, total_slices,
                                    projection_enabled, projection_start_slice,
                                    projection_end_slice, projection_total_thickness,
                                    projection_type, multiframe_context, stack_position
                                )
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

    def _create_widget_overlays(self, view, parser: DICOMParser,
                                total_slices: int | None = None,
                                projection_enabled: bool = False,
                                projection_start_slice: int | None = None,
                                projection_end_slice: int | None = None,
                                projection_total_thickness: float | None = None,
                                projection_type: str | None = None,
                                multiframe_context: dict[str, Any] | None = None,
                                stack_position: int | None = None) -> list[QGraphicsTextItem]:
        """
        Create QWidget-based viewport overlays.
        
        Args:
            view: QGraphicsView to add overlays to
            parser: DICOMParser instance
            total_slices: Total number of slices in the series
            projection_enabled: Whether Combine Slices projection is enabled
            projection_start_slice: Start slice index (0-based) of the projection range
            projection_end_slice: End slice index (0-based) of the projection range
            projection_total_thickness: Total thickness of combined slices in mm
            projection_type: Projection type ("aip", "mip", or "minip")
            
        Returns:
            Empty list (for compatibility with QGraphicsItem approach)
        """
        # Hide overlays based on visibility state
        if not self.should_show_text_overlays():
            if self.viewport_overlay_widget:
                self.viewport_overlay_widget.clear_all()
            return []

        # Get viewport
        viewport = view.viewport()
        if viewport is None:
            return []

        # Create or get existing overlay widget
        if self.viewport_overlay_widget is None:
            self.viewport_overlay_widget = ViewportOverlayWidget(
                viewport,
                font_size=self.font_size,
                font_color=self.font_color,
                font_family=self.font_family,
                font_variant=self.font_variant,
            )
            # Make widget fill the viewport and raise it above other widgets
            # Widget must stay at (0,0) and match viewport size to remain fixed during pan/zoom
            self.viewport_overlay_widget.setGeometry(0, 0, viewport.width(), viewport.height())
            self.viewport_overlay_widget.raise_()  # Raise above other widgets
            self.viewport_overlay_widget.show()
        else:
            # Update font size, color, family, and variant if changed
            self.viewport_overlay_widget.set_font_size(self.font_size)
            self.viewport_overlay_widget.set_font_color(self.font_color)
            self.viewport_overlay_widget.set_font_family(self.font_family)
            self.viewport_overlay_widget.set_font_variant(self.font_variant)
            # Ensure widget fills viewport and stays at (0,0) (in case viewport was resized)
            # This ensures widget stays fixed during pan/zoom operations
            current_geometry = self.viewport_overlay_widget.geometry()
            if (current_geometry.x() != 0 or current_geometry.y() != 0 or
                current_geometry.width() != viewport.width() or
                current_geometry.height() != viewport.height()):
                self.viewport_overlay_widget.setGeometry(0, 0, viewport.width(), viewport.height())

        # Get modality and corner tags (simple vs simple+detailed extras)
        modality = get_modality(parser)
        corner_tags = self._corner_tags_for_current_mode(modality)

        # Generate text for each corner
        corners = [
            ("upper_left", Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            ("upper_right", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            ("lower_left", Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
            ("lower_right", Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        ]

        for corner_key, alignment in corners:
            tags = corner_tags.get(corner_key, [])
            if tags:
                text = get_corner_text(
                                    parser, tags, self.privacy_mode, total_slices,
                                    projection_enabled, projection_start_slice,
                                    projection_end_slice, projection_total_thickness,
                                    projection_type, multiframe_context, stack_position
                                )
                if text:
                    self.viewport_overlay_widget.set_corner_text(corner_key, text, alignment)
                else:
                    self.viewport_overlay_widget.set_corner_text(corner_key, "", alignment)
            else:
                self.viewport_overlay_widget.set_corner_text(corner_key, "", alignment)

        # Update positions based on current viewport size
        self.viewport_overlay_widget.update_positions(viewport.width(), viewport.height())

        # Return empty list for compatibility (QWidget overlays don't return QGraphicsItems)
        return []

    def clear_overlay_items(self, scene) -> None:
        """
        Clear overlay items from scene.
        
        Args:
            scene: QGraphicsScene to remove items from
        """
        # Clear QWidget overlays if they exist
        if self.viewport_overlay_widget:
            self.viewport_overlay_widget.clear_all()
            self.viewport_overlay_widget = None

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

    def _recreate_overlay_items_for_current_state(self, scene) -> None:
        """Rebuild corner overlays after stale/deleted graphics items are detected."""
        total_slices = getattr(self, "current_total_slices", None)
        stack_position = getattr(self, "current_stack_position", None)
        self.create_overlay_items(
            scene,
            self.current_parser,
            total_slices=total_slices,
            stack_position=stack_position,
        )

    def _update_one_corner_overlay_position(
        self,
        scene,
        corner_key: str,
        x: float,
        y: float,
        alignment: Qt.AlignmentFlag,
        margin_scene: float,
        viewport_to_scene_scale: float,
    ) -> bool:
        """
        Reposition items for one corner.

        Returns:
            False when stale items forced a full recreate (caller must stop).
        """
        items = self.corner_item_map.get(corner_key, [])
        if not items:
            return True

        valid_items = filter_valid_overlay_items(items, scene)
        if len(valid_items) != len(items):
            self._recreate_overlay_items_for_current_state(scene)
            return False

        if bool(alignment & Qt.AlignmentFlag.AlignRight):
            cached = self.corner_max_width_map.get(corner_key, 0)
            max_width, to_cache = resolve_corner_max_width_viewport(cached, valid_items)
            if to_cache is not None:
                self.corner_max_width_map[corner_key] = to_cache
            position_right_aligned_corner_items(
                valid_items=valid_items,
                scene=scene,
                anchor_x=x,
                anchor_y=y,
                alignment=alignment,
                margin_scene=margin_scene,
                max_text_width_viewport=max_width,
                viewport_to_scene_scale=viewport_to_scene_scale,
            )
            return True

        if valid_items:
            position_left_aligned_corner_item(
                item=valid_items[0],
                scene=scene,
                x=x,
                y=y,
                alignment=alignment,
                viewport_to_scene_scale=viewport_to_scene_scale,
            )
        return True

    def update_overlay_positions(self, scene) -> None:
        """
        Update overlay item positions when view transform changes (zoom/pan).

        This ensures text stays anchored to viewport edges when zooming/panning.
        Updates existing items instead of recreating them to prevent jitter.

        For QWidget overlays, only syncs widget geometry; label layout is owned
        by ``ViewportOverlayWidget.resizeEvent``.

        Args:
            scene: QGraphicsScene containing overlay items
        """
        view = scene.views()[0] if scene.views() else None
        if view is None:
            return

        # QWidget path: geometry only (label positions come from resizeEvent).
        if self.use_widget_overlays:
            if self.viewport_overlay_widget:
                sync_widget_overlay_geometry(self.viewport_overlay_widget, view)
            return

        # QGraphicsItem path — always update (focused or not) so overlays stay
        # pinned to viewport edges rather than moving with the image.
        if not self.overlay_items or self.current_parser is None:
            return

        view = resolve_view_for_scene(scene, view)
        if view is None:
            return

        scene_rect = scene.sceneRect()
        if scene_rect.width() <= 0 or scene_rect.height() <= 0:
            return

        viewport_to_scene_scale, corners = build_viewport_corner_anchors(view)
        margin_scene = OVERLAY_VIEWPORT_MARGIN_PX * viewport_to_scene_scale

        for corner in corners:
            ok = self._update_one_corner_overlay_position(
                scene,
                corner.key,
                corner.x,
                corner.y,
                corner.alignment,
                margin_scene,
                viewport_to_scene_scale,
            )
            if not ok:
                return

        schedule_scene_viewport_repaint(scene, view)

