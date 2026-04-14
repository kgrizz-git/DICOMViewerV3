"""
Slice Location Line Manager (per subwindow)

Manages QGraphicsLineItem objects that display the intersection of other
views' slice planes on the current image. Line geometry uses scene coordinates
so endpoints zoom and pan with the image (no ItemIgnoresTransformations).
Stroke width uses a cosmetic QPen so it matches ROI-style overlays: width is
in viewport pixels and does not grow or shrink when the view is zoomed.

Line colors match the subwindow dot colors from navigator_colors (blue, green,
orange, magenta) so each window's line is visually associated with its dot.

Each segment dict produced by slice_location_line_helper contains:
    source_idx – used for colour (0–3, wraps if ≥ 4)
    line_id    – unique string key for the QGraphicsLineItem.
                 Middle mode:    "middle:<source_idx>"
                 Begin/end mode: "begin:<source_idx>" / "end:<source_idx>"

Inputs:
    - Scene reference
    - Segment descriptors from slice_location_line_helper

Outputs:
    - Line items added to the scene, updated or cleared on demand

Requirements:
    - PySide6 (QGraphicsLineItem, QPen, QColor, QGraphicsScene)
"""

from typing import Any, Dict, List, Optional

from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene
from shiboken6 import isValid

from gui.navigator_colors import SUBWINDOW_DOT_COLORS


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert hex color (e.g. #2196F3) to (r, g, b) tuple."""
    hex_str = hex_str.lstrip("#")
    return (
        int(hex_str[0:2], 16),
        int(hex_str[2:4], 16),
        int(hex_str[4:6], 16),
    )


# Colors match SUBWINDOW_DOT_COLORS (slot 0–3 = windows 1–4): blue, green, orange, magenta.
# Index 0 = Window 1, etc. Wraps for indices >= 4.
_SOURCE_COLORS: list[tuple[int, int, int]] = [
    _hex_to_rgb(SUBWINDOW_DOT_COLORS.get(i, "#2196F3"))
    for i in range(4)
]
_DEFAULT_LINE_WIDTH = 1
_Z_VALUE = 100


def _color_for_source(source_idx: int) -> tuple[int, int, int]:
    """Return (r, g, b) for the given source subwindow index. Matches navigator dot colors."""
    idx = source_idx % len(_SOURCE_COLORS)
    return _SOURCE_COLORS[idx]


def _pen_for_line(color: tuple[int, int, int], width: int) -> QPen:
    """
    Build a pen for slice-location strokes: viewport-relative width (cosmetic),
    aligned with ROI / measurement / crosshair overlay lines.
    """
    pen = QPen(QColor(*color), width)
    pen.setCosmetic(True)
    return pen


class SliceLocationLineManager:
    """
    Manages slice location line items for one subwindow's scene.

    Endpoints are in scene coordinates (image pixel space when the pixmap is
    at the origin) so the line moves and scales with zoom/pan. Pen width is
    cosmetic (viewport pixels), independent of zoom.

    Each line item is keyed by ``line_id`` from the segment descriptor.
    In middle mode line_id == source_idx (single line per source).
    In begin_end mode there are two line_ids per source:
        source_idx * 100 + 1  (begin boundary)
        source_idx * 100 + 2  (end boundary)
    Color for all lines from the same source is determined by source_idx.
    """

    def __init__(self, scene: Optional[QGraphicsScene] = None) -> None:
        """
        Initialize the manager.

        Args:
            scene: QGraphicsScene to add line items to. May be None initially;
                  set via set_scene or update_lines.
        """
        self._scene = scene
        # Keyed by line_id rather than source_idx so that begin/end mode can
        # maintain two distinct items per source subwindow without colliding
        # with middle-mode keys.
        self._line_items: Dict[str, QGraphicsLineItem] = {}
        self._line_width_px: int = _DEFAULT_LINE_WIDTH

    def set_line_width_px(self, width_px: int) -> None:
        """Set stroke width for slice position lines (1–8 viewport pixels, cosmetic pen)."""
        self._line_width_px = max(1, min(8, int(width_px)))

    def set_scene(self, scene: Optional[QGraphicsScene]) -> None:
        """Set or clear the scene. Clears existing items if scene changes."""
        if self._scene != scene:
            self.clear()
            self._scene = scene

    def has_scene(self) -> bool:
        """Return True if the manager has a valid scene."""
        return self._scene is not None

    def update_lines(
        self,
        segments: List[Dict[str, Any]],
        line_width_px: Optional[int] = None,
    ) -> None:
        """
        Update line items to match the given segments.

        Removes items for line_ids no longer present; adds or updates items
        for each segment.  Each segment dict must contain:
            source_idx – integer 0–3 for colour selection.
            line_id    – unique string key (defaults to "middle:<source_idx>"
                         when absent for backward compatibility).
            col1, row1, col2, row2 – pixel endpoint coordinates.

        Args:
            segments: List of segment descriptors from get_slice_location_line_segments.
            line_width_px: Optional cosmetic pen width (viewport px); defaults to last set width.
        """
        if self._scene is None:
            return

        lw = self._line_width_px if line_width_px is None else max(1, min(8, int(line_width_px)))
        if line_width_px is not None:
            self._line_width_px = lw

        # Drop dead wrappers (e.g. after scene.clear()) so we never reuse zombies
        # or skip removal because scene() no longer matches self._scene.
        for lid, dead in list(self._line_items.items()):
            if not isValid(dead):
                self._line_items.pop(lid, None)

        seen_ids: set[str] = set()
        for seg in segments:
            source_idx = seg.get("source_idx", -1)
            # line_id defaults to a mode-safe middle key for backward compatibility
            # with any caller that omits it.
            line_id: str = str(seg.get("line_id", f"middle:{source_idx}"))
            col1 = seg.get("col1", 0)
            row1 = seg.get("row1", 0)
            col2 = seg.get("col2", 0)
            row2 = seg.get("row2", 0)
            seen_ids.add(line_id)

            item = self._line_items.get(line_id)
            if item is not None and not isValid(item):
                # Underlying C++ item was destroyed (e.g. scene cleared); drop it.
                self._line_items.pop(line_id, None)
                item = None

            if item is not None:
                item.setLine(col1, row1, col2, row2)
                color = _color_for_source(source_idx)
                item.setPen(_pen_for_line(color, lw))
                # Item may have been removed from the scene elsewhere; re-attach so
                # geometry updates are visible. If it lives on another scene, move it.
                if self._scene is not None:
                    attached = item.scene()
                    if attached is None:
                        item.setZValue(_Z_VALUE)
                        item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
                        item.setFlag(item.GraphicsItemFlag.ItemIsFocusable, False)
                        self._scene.addItem(item)
                    elif attached is not self._scene:
                        attached.removeItem(item)
                        item.setZValue(_Z_VALUE)
                        item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
                        item.setFlag(item.GraphicsItemFlag.ItemIsFocusable, False)
                        self._scene.addItem(item)
            else:
                item = QGraphicsLineItem(col1, row1, col2, row2)
                color = _color_for_source(source_idx)
                item.setPen(_pen_for_line(color, lw))
                item.setZValue(_Z_VALUE)
                item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
                item.setFlag(item.GraphicsItemFlag.ItemIsFocusable, False)
                self._scene.addItem(item)
                self._line_items[line_id] = item

        # Remove items for line_ids no longer in segments.
        for lid in list(self._line_items.keys()):
            if lid not in seen_ids:
                item = self._line_items.pop(lid)
                if not isValid(item):
                    continue
                sc = item.scene()
                if sc is not None:
                    sc.removeItem(item)

    def clear(self) -> None:
        """Remove all line items from the scene."""
        for item in list(self._line_items.values()):
            if not isValid(item):
                continue
            sc = item.scene()
            if sc is not None:
                sc.removeItem(item)
        self._line_items.clear()

    def set_visible(self, visible: bool) -> None:
        """Show or hide all line items without recomputing."""
        # Filter out any items whose underlying C++ objects have been destroyed.
        for lid, item in list(self._line_items.items()):
            if not isValid(item):
                self._line_items.pop(lid, None)
                continue
            item.setVisible(visible)
