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
      thumbnail for the view in that slot, plus a very small colored window
      number (1–4) in the corner.
    - Overlay highlighting for displayed slots when not in 2x2.

Requirements:
    - PySide6 for QWidget and painting.
"""

from typing import Callable, List, Optional

from PySide6.QtCore import Qt, QPoint, QRect, QSize, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap, QMouseEvent
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QSizePolicy, QStyle, QVBoxLayout, QWidget

from gui.style_constants import FOCUS_BORDER_COLOR
from gui.navigator_colors import SUBWINDOW_DOT_COLORS, subwindow_slot_display_number


# Fixed size for the whole widget so it stays small and square in the navigator bar.
WINDOW_SLOT_MAP_SIZE = 80


class WindowSlotMapWidget(QWidget):
    """
    Square 2×2 thumbnail: four equal square cells, one per window slot.
    Each cell shows a thumbnail of the actual image for that view (if available)
    and a very small colored window number (1–4). Displayed-slot overlay when layout is not 2x2.
    """

    cell_clicked = Signal(int)  # slot index 0–3 (grid TL, TR, BL, BR)

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

    def mousePressEvent(self, event: QMouseEvent) -> None:  # type: ignore[override]
        """Left-click a cell to focus that window slot (see main app wiring)."""
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        rect = self.rect().adjusted(1, 1, -1, -1)
        side = min(rect.width(), rect.height())
        if side <= 0:
            return super().mousePressEvent(event)
        cell_side = side // 2
        ox = rect.left() + (rect.width() - side) // 2
        oy = rect.top() + (rect.height() - side) // 2
        p = event.position().toPoint()
        col = (p.x() - ox) // cell_side
        row = (p.y() - oy) // cell_side
        if 0 <= col <= 1 and 0 <= row <= 1:
            slot = row * 2 + col
            self.cell_clicked.emit(int(slot))
        super().mousePressEvent(event)

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
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

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
        bg_color = QColor(40, 40, 40, 255)
        display_overlay_color = QColor(255, 220, 100, 140)  # semi-transparent yellow for displayed slots
        focused_border_color = FOCUS_BORDER_COLOR

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

            # Very small colored window number (1–4), top-right — matches navigator thumbnail legend.
            label_font = QFont()
            label_font.setBold(True)
            label_font.setPointSize(9)
            painter.setFont(label_font)
            fm = painter.fontMetrics()
            slot_label = subwindow_slot_display_number(slot)
            tw = fm.horizontalAdvance(slot_label)
            th = fm.height()
            pad = 2
            text_rect = QRect(
                cell_rect.right() - pad - tw,
                cell_rect.top() + pad,
                tw,
                th,
            )
            label_fill = QColor(SUBWINDOW_DOT_COLORS.get(slot, "#FFFFFF"))
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                painter.setPen(QColor(0, 0, 0, 220))
                painter.drawText(
                    text_rect.translated(ox, oy),
                    Qt.AlignmentFlag.AlignCenter,
                    slot_label,
                )
            painter.setPen(label_fill)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, slot_label)

        painter.end()


class _LayoutMapTopBar(QWidget):
    """
    Top bar for the layout map popup: drag area on the left, X close button on the right.
    Implements drag-to-move for the parent window (same logic as the container).
    """

    def __init__(
        self,
        parent: QWidget,
        boundary_widget: QWidget,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._boundary_widget = boundary_widget
        self._on_position_changed = on_position_changed
        self._drag_start_global: Optional[QPoint] = None
        self._window_start_pos: Optional[QPoint] = None

        self.setFixedHeight(11)
        self.setFixedWidth(WINDOW_SLOT_MAP_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        bar_layout = QHBoxLayout(self)
        bar_layout.setContentsMargins(1, 1, 1, 1)
        bar_layout.setSpacing(0)
        bar_layout.addStretch()

        close_btn = QPushButton(self)
        close_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        close_btn.setFixedSize(10, 10)
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self._on_close_clicked)
        bar_layout.addWidget(close_btn)

    def _on_close_clicked(self) -> None:
        """Close the parent dialog when X is clicked."""
        win = self.window()
        if win is not None:
            win.close()

    def _boundary_rect_global(self) -> QRect:
        """Return the boundary widget's frame geometry in global coordinates."""
        return self._boundary_widget.frameGeometry()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_global = event.globalPosition().toPoint()
            win = self.window()
            self._window_start_pos = win.mapToGlobal(QPoint(0, 0)) if win else QPoint(0, 0)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if (
            self._drag_start_global is not None
            and self._window_start_pos is not None
            and event.buttons() & Qt.MouseButton.LeftButton
        ):
            win = self.window()
            if win is not None:
                delta = event.globalPosition().toPoint() - self._drag_start_global
                new_pos = self._window_start_pos + delta
                boundary = self._boundary_rect_global()
                w, h = win.width(), win.height()
                new_x = max(boundary.left(), min(new_pos.x(), boundary.right() - w))
                new_y = max(boundary.top(), min(new_pos.y(), boundary.bottom() - h))
                win.move(new_x, new_y)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start_global is not None:
            win = self.window()
            if win is not None and self._on_position_changed is not None:
                pos = win.mapToGlobal(QPoint(0, 0))
                self._on_position_changed(pos.x(), pos.y())
            self._drag_start_global = None
            self._window_start_pos = None
        super().mouseReleaseEvent(event)


class _DraggableWindowSlotMapContainer(QWidget):
    """
    Popup body: holds the top drag bar (moves the parent dialog) and the
    ``WindowSlotMapWidget``. Map clicks are handled on the map itself (cell focus).
    """

    def __init__(
        self,
        parent: QWidget,
        boundary_widget: QWidget,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._boundary_widget = boundary_widget

        # Keep popup width equal to the square map (no wider)
        total_w = 4 + WINDOW_SLOT_MAP_SIZE + 4
        self.setFixedWidth(total_w)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)
        self._top_bar = _LayoutMapTopBar(self, boundary_widget, on_position_changed)
        layout.addWidget(self._top_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        self._map_widget = WindowSlotMapWidget(self)
        layout.addWidget(self._map_widget)

    def get_map_widget(self) -> WindowSlotMapWidget:
        """Return the embedded WindowSlotMapWidget for setting callbacks and refresh."""
        return self._map_widget


class WindowSlotMapPopupDialog(QDialog):
    """
    Frameless dialog that shows the window-slot map thumbnail (from context menu).
    Contains a draggable container so the user can move the popup; position
    is constrained to the boundary widget (main window) and can be persisted.
    """

    def __init__(
        self,
        parent: QWidget,
        boundary_widget: QWidget,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setModal(False)
        self.setObjectName("window_slot_map_popup_dialog")
        self.setStyleSheet(
            "#window_slot_map_popup_dialog { border: 1px solid #000000; background-color: palette(window); }"
        )
        self._container = _DraggableWindowSlotMapContainer(
            self, boundary_widget, on_position_changed
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._container)

    def get_map_widget(self) -> WindowSlotMapWidget:
        """Return the embedded WindowSlotMapWidget for setting callbacks and refresh."""
        return self._container.get_map_widget()

