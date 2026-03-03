"""
Window Slot Map Widget

Small square 2×2 thumbnail that shows a preview of the actual image in each
window slot (1–4) and the mapping to logical views (A–D). In non-2x2 layouts,
overlay highlighting indicates which slot(s) are currently displayed.

Inputs (via callbacks set by the app):
    - get_slot_to_view(): List[int] mapping slot index → view index.
    - get_layout_mode(): str in {"1x1", "1x2", "2x1", "2x2"}.
    - get_focused_view_index(): int (0–3) for the currently focused view.
    - get_thumbnail_for_view(view_index: int): Optional[QPixmap] for that view's current image.

Outputs:
    - Square widget with 4 equal square cells; each cell shows the image
      thumbnail for the view in that slot, plus slot number (1–4) and optional label.
    - Overlay highlighting for displayed slots when not in 2x2.

Requirements:
    - PySide6 for QWidget and painting.
"""

from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget, QSizePolicy


# Fixed size for the whole widget so it stays small and square in the navigator bar.
WINDOW_SLOT_MAP_SIZE = 80


class WindowSlotMapWidget(QWidget):
    """
    Square 2×2 thumbnail: four equal square cells, one per window slot.
    Each cell shows a thumbnail of the actual image for that view (if available)
    and a small slot number (1–4). Displayed-slot overlay when layout is not 2x2.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.get_slot_to_view: Optional[Callable[[], List[int]]] = None
        self.get_layout_mode: Optional[Callable[[], str]] = None
        self.get_focused_view_index: Optional[Callable[[], int]] = None
        self.get_thumbnail_for_view: Optional[Callable[[int], Optional[QPixmap]]] = None

        # Fixed small square so the thumbnail does not dominate the bar in 1x1/1x2.
        self.setFixedSize(QSize(WINDOW_SLOT_MAP_SIZE, WINDOW_SLOT_MAP_SIZE))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # Public API ---------------------------------------------------------

    def set_callbacks(
        self,
        get_slot_to_view: Optional[Callable[[], List[int]]] = None,
        get_layout_mode: Optional[Callable[[], str]] = None,
        get_focused_view_index: Optional[Callable[[], int]] = None,
        get_thumbnail_for_view: Optional[Callable[[int], Optional[QPixmap]]] = None,
    ) -> None:
        """Set callbacks used to query layout state and per-view thumbnails."""
        self.get_slot_to_view = get_slot_to_view
        self.get_layout_mode = get_layout_mode
        self.get_focused_view_index = get_focused_view_index
        self.get_thumbnail_for_view = get_thumbnail_for_view
        self.update()

    def refresh(self) -> None:
        """Request a repaint using the latest callback values."""
        self.update()

    # Internal helpers ---------------------------------------------------

    def _safe_slot_to_view(self) -> List[int]:
        """Return a safe slot_to_view list of length 4."""
        default = [0, 1, 2, 3]
        if not self.get_slot_to_view:
            return default
        try:
            stv = self.get_slot_to_view()
            if isinstance(stv, list) and len(stv) >= 4:
                # Only first 4 are relevant (slots 0–3).
                return [int(stv[0]), int(stv[1]), int(stv[2]), int(stv[3])]
        except Exception:
            pass
        return default

    def _safe_layout_mode(self) -> str:
        """Return current layout mode or '2x2' as a safe default."""
        if not self.get_layout_mode:
            return "2x2"
        try:
            mode = self.get_layout_mode()
            if mode in ("1x1", "1x2", "2x1", "2x2"):
                return mode
        except Exception:
            pass
        return "2x2"

    def _safe_focused_view_index(self) -> int:
        """Return focused view index or 0 as a default."""
        if not self.get_focused_view_index:
            return 0
        try:
            idx = int(self.get_focused_view_index())
            if 0 <= idx <= 3:
                return idx
        except Exception:
            pass
        return 0

    def _compute_focused_slot(self, slot_to_view: List[int]) -> int:
        """Return slot index (0–3) that contains the focused view."""
        focused_view_idx = self._safe_focused_view_index()
        for s in range(4):
            if s < len(slot_to_view) and slot_to_view[s] == focused_view_idx:
                return s
        return 0

    def _compute_displayed_slots(self, slot_to_view: List[int]) -> List[int]:
        """
        Compute which slot indices (0–3) are currently displayed based on
        the layout mode and focused slot.
        """
        mode = self._safe_layout_mode()
        if mode == "2x2":
            # All slots are visible; for overlay purposes we don't highlight any.
            return []

        focused_slot = self._compute_focused_slot(slot_to_view)
        if mode == "1x1":
            return [focused_slot]
        if mode == "1x2":
            row = focused_slot // 2
            base = row * 2
            return [base, base + 1]
        if mode == "2x1":
            col = focused_slot % 2
            return [col, col + 2]
        return []

    # Painting -----------------------------------------------------------

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        rect = self.rect().adjusted(1, 1, -1, -1)
        # Keep the drawn area square: four equal square cells
        side = min(rect.width(), rect.height())
        if side <= 0:
            painter.end()
            return
        cell_side = side // 2
        # Center the square in the widget if there is slack
        ox = rect.left() + (rect.width() - side) // 2
        oy = rect.top() + (rect.height() - side) // 2

        slot_to_view = self._safe_slot_to_view()
        displayed_slots = set(self._compute_displayed_slots(slot_to_view))
        focused_slot = self._compute_focused_slot(slot_to_view)

        # Colors
        border_color = QColor(180, 180, 180)
        text_color = QColor(255, 255, 255)
        bg_color = QColor(40, 40, 40, 255)
        display_overlay_color = QColor(80, 130, 200, 140)
        focused_border_color = QColor(255, 220, 120)

        painter.fillRect(ox, oy, side, side, bg_color)

        for slot in range(4):
            row = slot // 2
            col = slot % 2
            cell_rect = QRect(
                ox + col * cell_side,
                oy + row * cell_side,
                cell_side,
                cell_side,
            )

            view_idx = slot_to_view[slot] if slot < len(slot_to_view) else slot
            # Draw thumbnail of the actual image for this view
            thumb = None
            if self.get_thumbnail_for_view:
                try:
                    thumb = self.get_thumbnail_for_view(view_idx)
                except Exception:
                    pass
            if thumb is not None and not thumb.isNull():
                # Scale to fill cell preserving aspect ratio (letterbox if needed)
                tw, th = thumb.width(), thumb.height()
                if tw > 0 and th > 0:
                    cw, ch = cell_rect.width(), cell_rect.height()
                    scale = min(cw / tw, ch / th)
                    sw, sh = int(tw * scale), int(th * scale)
                    sx = cell_rect.left() + (cw - sw) // 2
                    sy = cell_rect.top() + (ch - sh) // 2
                    painter.drawPixmap(QRect(sx, sy, sw, sh), thumb, thumb.rect())

            # Displayed-slot overlay (for non-2x2 layouts)
            if slot in displayed_slots:
                painter.fillRect(cell_rect, display_overlay_color)

            # Cell border
            pen = QPen(border_color)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawRect(cell_rect)

            # Focused window border
            if slot == focused_slot:
                focus_pen = QPen(focused_border_color)
                focus_pen.setWidth(2)
                painter.setPen(focus_pen)
                painter.drawRect(cell_rect.adjusted(1, 1, -1, -1))

            # Small slot number (1–4) in corner so thumbnail remains visible
            painter.setPen(text_color)
            slot_num = slot + 1
            painter.drawText(
                cell_rect.adjusted(2, 2, -2, -2),
                Qt.AlignTop | Qt.AlignLeft,
                str(slot_num),
            )

        painter.end()

