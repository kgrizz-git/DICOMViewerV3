"""
Slice Location Line Manager (per subwindow)

Manages QGraphicsLineItem objects that display the intersection of other
views' slice planes on the current image. Lines zoom and pan with the image
(scene coordinates, no ItemIgnoresTransformations).

Inputs:
    - Scene reference
    - Segment descriptors from slice_location_line_helper

Outputs:
    - Line items added to the scene, updated or cleared on demand

Requirements:
    - PySide6 (QGraphicsLineItem, QPen, QColor, QGraphicsScene)
"""

from typing import Dict, List, Optional

from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene

# Color palette for source subwindow indices (cyan, magenta, green, orange).
# Index 0 = Window 1, etc. Wraps for indices >= 4.
_SOURCE_COLORS = [
    (0, 255, 255),   # Cyan
    (255, 0, 255),   # Magenta
    (0, 255, 128),   # Green
    (255, 165, 0),   # Orange
]
_LINE_WIDTH = 2
_Z_VALUE = 100


def _color_for_source(source_idx: int) -> tuple:
    """Return (r, g, b) for the given source subwindow index."""
    idx = source_idx % len(_SOURCE_COLORS)
    return _SOURCE_COLORS[idx]


class SliceLocationLineManager:
    """
    Manages slice location line items for one subwindow's scene.

    Lines are drawn in scene coordinates (pixel coords = scene coords when
    image is at origin) so they zoom and pan with the image.
    """

    def __init__(self, scene: Optional[QGraphicsScene] = None) -> None:
        """
        Initialize the manager.

        Args:
            scene: QGraphicsScene to add line items to. May be None initially;
                  set via set_scene or update_lines.
        """
        self._scene = scene
        self._line_items: Dict[int, QGraphicsLineItem] = {}  # source_idx -> item

    def set_scene(self, scene: Optional[QGraphicsScene]) -> None:
        """Set or clear the scene. Clears existing items if scene changes."""
        if self._scene != scene:
            self.clear()
            self._scene = scene

    def has_scene(self) -> bool:
        """Return True if the manager has a valid scene."""
        return self._scene is not None

    def update_lines(self, segments: List[Dict]) -> None:
        """
        Update line items to match the given segments.

        Removes items for sources no longer present; adds or updates items
        for each segment. Segments are dicts with keys: source_idx, col1,
        row1, col2, row2.

        Args:
            segments: List of segment descriptors from get_slice_location_line_segments.
        """
        if self._scene is None:
            return

        seen_sources = set()
        for seg in segments:
            source_idx = seg.get("source_idx", -1)
            col1 = seg.get("col1", 0)
            row1 = seg.get("row1", 0)
            col2 = seg.get("col2", 0)
            row2 = seg.get("row2", 0)
            seen_sources.add(source_idx)

            if source_idx in self._line_items:
                item = self._line_items[source_idx]
                item.setLine(col1, row1, col2, row2)
            else:
                item = QGraphicsLineItem(col1, row1, col2, row2)
                color = _color_for_source(source_idx)
                pen = QPen(QColor(*color), _LINE_WIDTH)
                item.setPen(pen)
                item.setZValue(_Z_VALUE)
                item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
                item.setFlag(item.GraphicsItemFlag.ItemIsFocusable, False)
                self._scene.addItem(item)
                self._line_items[source_idx] = item

        # Remove items for sources no longer in segments.
        for src in list(self._line_items.keys()):
            if src not in seen_sources:
                item = self._line_items.pop(src)
                if self._scene and item.scene() == self._scene:
                    self._scene.removeItem(item)

    def clear(self) -> None:
        """Remove all line items from the scene."""
        for item in list(self._line_items.values()):
            if self._scene and item.scene() == self._scene:
                self._scene.removeItem(item)
        self._line_items.clear()

    def set_visible(self, visible: bool) -> None:
        """Show or hide all line items without recomputing."""
        for item in self._line_items.values():
            item.setVisible(visible)
