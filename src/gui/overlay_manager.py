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

from dataclasses import dataclass
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


@dataclass(frozen=True)
class OverlayTextContext:
    """Inputs shared by all four graphics-overlay corner renderers."""

    parser: DICOMParser
    total_slices: int | None
    projection_enabled: bool
    projection_start_slice: int | None
    projection_end_slice: int | None
    projection_total_thickness: float | None
    projection_type: str | None
    multiframe_context: dict[str, Any] | None
    stack_position: int | None


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
        self.current_projection_enabled: bool = False
        self.current_projection_start_slice: int | None = None
        self.current_projection_end_slice: int | None = None
        self.current_projection_total_thickness: float | None = None
        self.current_projection_type: str | None = None
        self.current_multiframe_context: dict[str, Any] | None = None

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

    def _store_overlay_context(
        self,
        scene,
        parser: DICOMParser,
        total_slices: int | None,
        projection_enabled: bool,
        projection_start_slice: int | None,
        projection_end_slice: int | None,
        projection_total_thickness: float | None,
        projection_type: str | None,
        multiframe_context: dict[str, Any] | None,
        stack_position: int | None,
    ) -> None:
        """Record the rendering inputs used when overlays are repositioned."""
        self.current_parser = parser
        self.current_scene = scene
        if total_slices is not None:
            self.current_total_slices = total_slices
        self.current_stack_position = stack_position
        self.current_projection_enabled = projection_enabled
        self.current_projection_start_slice = projection_start_slice
        self.current_projection_end_slice = projection_end_slice
        self.current_projection_total_thickness = projection_total_thickness
        self.current_projection_type = projection_type
        self.current_multiframe_context = multiframe_context

    @staticmethod
    def _first_scene_view(scene):
        """Return the scene's first view, matching the legacy overlay path."""
        return scene.views()[0] if scene.views() else None

    @staticmethod
    def _resolve_scene_dimensions(scene) -> tuple[float, float]:
        """Resolve graphics-overlay dimensions from the scene, items, or defaults."""
        scene_rect = scene.sceneRect()
        if scene_rect.width() > 0 and scene_rect.height() > 0:
            return scene_rect.width(), scene_rect.height()

        items = scene.items()
        if items:
            max_rect = QRectF()
            for item in items:
                if hasattr(item, "boundingRect"):
                    item_rect = item.boundingRect()
                    if item_rect.width() * item_rect.height() > max_rect.width() * max_rect.height():
                        max_rect = item_rect
            if max_rect.width() > 0 and max_rect.height() > 0:
                return max_rect.width(), max_rect.height()
        return 800, 600

    @staticmethod
    def _graphics_corner_anchors(
        view, scene_width: float, scene_height: float, margin: float
    ) -> tuple[float, float, list[tuple[str, float, float, Qt.AlignmentFlag]]]:
        """Return the fixed-scene or viewport-mapped corner anchors."""
        viewport_to_scene_scale = 1.0
        corners = [
            ("upper_left", margin, margin, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            ("upper_right", scene_width - margin, margin, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            ("lower_left", margin, scene_height - margin, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
            ("lower_right", scene_width - margin, scene_height - margin, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
        ]
        if view is None:
            return viewport_to_scene_scale, margin, corners

        viewport_to_scene_scale = 1.0 / graphics_view_uniform_zoom(view)
        margin_scene = margin * viewport_to_scene_scale
        viewport = view.viewport()
        viewport_width = viewport.width()
        viewport_height = viewport.height()
        top_left_scene = view.mapToScene(0, 0)
        top_right_scene = view.mapToScene(viewport_width, 0)
        bottom_left_scene = view.mapToScene(0, viewport_height)
        bottom_right_scene = view.mapToScene(viewport_width, viewport_height)
        corners = [
            ("upper_left", top_left_scene.x() + margin_scene, top_left_scene.y() + margin_scene, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop),
            ("upper_right", top_right_scene.x(), top_right_scene.y() + margin_scene, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop),
            ("lower_left", bottom_left_scene.x() + margin_scene, bottom_left_scene.y() - margin_scene, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom),
            # Intentionally retain the legacy bottom-left y anchor for rendering parity.
            ("lower_right", bottom_right_scene.x(), bottom_left_scene.y() - margin_scene, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom),
        ]
        return viewport_to_scene_scale, margin_scene, corners

    def _corner_overlay_text(
        self,
        context: OverlayTextContext,
        tags: list[str],
    ) -> str:
        """Build one corner's text with every caller-provided display context."""
        return get_corner_text(
            context.parser,
            tags,
            self.privacy_mode,
            context.total_slices,
            context.projection_enabled,
            context.projection_start_slice,
            context.projection_end_slice,
            context.projection_total_thickness,
            context.projection_type,
            context.multiframe_context,
            context.stack_position,
        )

    def _track_graphics_overlay_item(self, scene, corner_key: str, item: QGraphicsTextItem) -> None:
        """Add an overlay item to the scene and the two manager-owned collections."""
        scene.addItem(item)
        self.overlay_items.append(item)
        self.corner_item_map[corner_key].append(item)

    def _right_aligned_text_width(
        self, lines: list[str], alignment: Qt.AlignmentFlag
    ) -> float:
        """Measure the padded fixed document width used by one right corner."""
        max_text_width_viewport = 0
        for line in lines:
            temporary_item = self._create_text_item(line, 0, 0, alignment)
            max_text_width_viewport = max(
                max_text_width_viewport, temporary_item.boundingRect().width()
            )
        return max_text_width_viewport + 5

    def _render_right_aligned_corner(
        self,
        scene,
        corner_key: str,
        text: str,
        x: float,
        y: float,
        alignment: Qt.AlignmentFlag,
        margin_scene: float,
        viewport_to_scene_scale: float,
    ) -> None:
        """Render independent fixed-width lines so a right corner stays aligned."""
        lines = [line for line in text.split("\n") if line.strip()]
        max_text_width_viewport = self._right_aligned_text_width(lines, alignment)
        self.corner_max_width_map[corner_key] = max_text_width_viewport
        max_text_width_scene = max_text_width_viewport * viewport_to_scene_scale
        left_edge_x = x - margin_scene - max_text_width_scene
        line_height_viewport = None
        for line_idx, line in enumerate(lines):
            text_item = self._create_text_item(
                line, 0, 0, alignment, text_width=max_text_width_viewport
            )
            if line_height_viewport is None:
                line_height_viewport = text_item.boundingRect().height()
            line_spacing = line_height_viewport * viewport_to_scene_scale * 0.9
            if alignment & Qt.AlignmentFlag.AlignBottom:
                text_y = y - (len(lines) - line_idx) * line_spacing
            else:
                text_y = y + line_idx * line_spacing
            text_item.setPos(left_edge_x, text_y)
            self._track_graphics_overlay_item(scene, corner_key, text_item)

    def _render_left_aligned_corner(
        self,
        scene,
        corner_key: str,
        text: str,
        x: float,
        y: float,
        alignment: Qt.AlignmentFlag,
        viewport_to_scene_scale: float,
    ) -> None:
        """Render one multiline text item for a left-aligned corner."""
        text_item = self._create_text_item(text, x, y, alignment)
        text_item.setPos(x, y)
        if alignment & Qt.AlignmentFlag.AlignBottom:
            text_height_scene = text_item.boundingRect().height() * viewport_to_scene_scale
            text_item.setPos(text_item.pos().x(), y - text_height_scene)
        self._track_graphics_overlay_item(scene, corner_key, text_item)

    def _render_graphics_corner(
        self,
        scene,
        context: OverlayTextContext,
        corner_key: str,
        x: float,
        y: float,
        alignment: Qt.AlignmentFlag,
        tags: list[str],
        margin_scene: float,
        viewport_to_scene_scale: float,
    ) -> None:
        """Build and render the configured text for one graphics-overlay corner."""
        if not tags:
            return
        text = self._corner_overlay_text(
            context,
            tags,
        )
        if not text:
            return
        if alignment & Qt.AlignmentFlag.AlignRight:
            self._render_right_aligned_corner(
                scene, corner_key, text, x, y, alignment, margin_scene, viewport_to_scene_scale
            )
            return
        self._render_left_aligned_corner(
            scene, corner_key, text, x, y, alignment, viewport_to_scene_scale
        )

    def create_overlay_items(self, scene, parser: DICOMParser,
                            position: tuple[int, int] = (10, 10),  # pyright: ignore[reportUnusedParameter]
                            total_slices: int | None = None,
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
        self._store_overlay_context(
            scene,
            parser,
            total_slices,
            projection_enabled,
            projection_start_slice,
            projection_end_slice,
            projection_total_thickness,
            projection_type,
            multiframe_context,
            stack_position,
        )
        view = self._first_scene_view(scene)
        if self.use_widget_overlays and view is not None:
            return self._create_widget_overlays(
                view, parser, total_slices, projection_enabled, projection_start_slice,
                projection_end_slice, projection_total_thickness, projection_type,
                multiframe_context, stack_position,
            )

        self.clear_overlay_items(scene)
        for corner_key in self.corner_item_map:
            self.corner_item_map[corner_key].clear()
        if not self.should_show_text_overlays():
            return []

        modality = get_modality(parser)
        corner_tags = self._corner_tags_for_current_mode(modality)
        scene_width, scene_height = self._resolve_scene_dimensions(scene)
        viewport_to_scene_scale, margin_scene, corners = self._graphics_corner_anchors(
            view, scene_width, scene_height, margin=10
        )
        text_context = OverlayTextContext(
            parser=parser,
            total_slices=total_slices,
            projection_enabled=projection_enabled,
            projection_start_slice=projection_start_slice,
            projection_end_slice=projection_end_slice,
            projection_total_thickness=projection_total_thickness,
            projection_type=projection_type,
            multiframe_context=multiframe_context,
            stack_position=stack_position,
        )
        for corner_key, x, y, alignment in corners:
            self._render_graphics_corner(
                scene,
                text_context,
                corner_key,
                x,
                y,
                alignment,
                corner_tags.get(corner_key, []),
                margin_scene,
                viewport_to_scene_scale,
            )

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
        parser = self.current_parser
        if parser is None:
            return
        total_slices = getattr(self, "current_total_slices", None)
        stack_position = getattr(self, "current_stack_position", None)
        self.create_overlay_items(
            scene,
            parser,
            total_slices=total_slices,
            stack_position=stack_position,
            projection_enabled=getattr(self, "current_projection_enabled", False),
            projection_start_slice=getattr(self, "current_projection_start_slice", None),
            projection_end_slice=getattr(self, "current_projection_end_slice", None),
            projection_total_thickness=getattr(
                self, "current_projection_total_thickness", None
            ),
            projection_type=getattr(self, "current_projection_type", None),
            multiframe_context=getattr(self, "current_multiframe_context", None),
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
