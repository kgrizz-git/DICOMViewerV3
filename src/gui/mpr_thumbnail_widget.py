"""
MPR Thumbnail Widget

A thumbnail widget representing an active MPR (Multi-Planar Reconstruction)
view in the series navigator bar.

Inputs:
    subwindow_index (int): Index of the subwindow hosting the MPR view.
    pixel_array (np.ndarray): 2-D float array from the MPR slice.
    window_center, window_width (float): Optional W/L for rendering.
    dot_color (str): Hex color for the subwindow digit in the top-right corner.

Outputs:
    - Visual thumbnail with MPR badge and subwindow number tint.
    - clicked(int) signal: emitted with subwindow_index on left-click.
    - drag_started(int) signal: emitted when a drag begins.
    - Drag MIME type ``application/x-dv3-mpr-assign`` with source subwindow
      index encoded as UTF-8 bytes.

Requirements:
    PySide6, PIL (Pillow), numpy, gui.navigator_colors.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PIL import Image

from PySide6.QtCore import Qt, Signal, QPoint, QByteArray, QMimeData, QRect
from PySide6.QtGui import (
    QColor,
    QDrag,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QMenu, QWidget

from gui.navigator_colors import SUBWINDOW_DOT_COLORS, subwindow_slot_display_number

# MIME type used to distinguish MPR thumbnail drags from regular series drags.
MPR_ASSIGN_MIME = "application/x-dv3-mpr-assign"

_THUMBNAIL_SIZE = 68  # pixels — matches SeriesThumbnail default


class MprThumbnailWidget(QWidget):
    """
    Thumbnail widget for an active MPR view.

    Displays a preview of the current MPR plane with:
    - A dark background when no preview image is available.
    - An ``MPR`` badge in the top-left corner.
    - A very small colored window number in the top-right (same colors as
      series navigator slot indicators).

    Clicking the widget emits ``clicked(subwindow_index)``.
    Dragging the widget produces a ``application/x-dv3-mpr-assign`` MIME event
    so drop targets (SubWindowContainer) can identify it as an MPR reassignment.
    """

    clicked = Signal(int)       # subwindow_index
    drag_started = Signal(int)  # subwindow_index
    clear_mpr_requested = Signal(int)  # subwindow_index (-1 = detached)

    THUMBNAIL_SIZE: int = _THUMBNAIL_SIZE

    def __init__(self, subwindow_index: int, parent: Optional[QWidget] = None) -> None:
        """
        Args:
            subwindow_index: Zero-based index of the subwindow hosting the MPR.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._subwindow_index: int = subwindow_index
        self._preview_pixmap: Optional[QPixmap] = None
        self._dot_color: str = (
            "#9E9E9E"
            if subwindow_index < 0
            else SUBWINDOW_DOT_COLORS.get(subwindow_index, "#2196F3")
        )
        self._drag_start_pos: Optional[QPoint] = None

        self.setFixedSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        if subwindow_index < 0:
            self.setToolTip(
                "MPR — not assigned to a window\n"
                "Drag onto an image pane to assign  |  Right-click: Clear MPR"
            )
        else:
            self.setToolTip(
                f"MPR View — Window {subwindow_index + 1}\n"
                "Click to focus  |  Drag to move to another window  |  Right-click: Clear MPR"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def subwindow_index(self) -> int:
        """Return the subwindow index this thumbnail represents."""
        return self._subwindow_index

    def update_preview(
        self,
        pixel_array: Optional[np.ndarray],
        window_center: Optional[float] = None,
        window_width: Optional[float] = None,
    ) -> None:
        """
        Render a new preview from a 2-D float pixel array.

        Applies W/L windowing when both ``window_center`` and ``window_width``
        are provided; otherwise auto-scales to the data min/max.

        Args:
            pixel_array: 2-D float32 MPR slice array, or None to clear.
            window_center: Window centre for display (optional).
            window_width: Window width for display (optional, must be > 0).
        """
        if pixel_array is None or pixel_array.size == 0:
            self._preview_pixmap = None
            self.update()
            return

        arr = pixel_array.astype(float)

        if window_center is not None and window_width is not None and window_width > 0:
            lo = window_center - window_width / 2.0
            arr = np.clip((arr - lo) / window_width * 255.0, 0.0, 255.0)
        else:
            mn, mx = arr.min(), arr.max()
            span = mx - mn
            if span > 0:
                arr = (arr - mn) / span * 255.0
            else:
                arr = np.zeros_like(arr)

        uint8_arr = arr.astype(np.uint8)

        try:
            # Convert via PIL for high-quality resize while preserving aspect ratio.
            pil_img = Image.fromarray(uint8_arr, mode="L").convert("RGB")
            thumb = Image.new(
                "RGB",
                (self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE),
                color=(42, 42, 42),
            )
            fit_img = pil_img.copy()
            fit_img.thumbnail(
                (self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE),
                Image.LANCZOS,
            )
            offset_x = (self.THUMBNAIL_SIZE - fit_img.width) // 2
            offset_y = (self.THUMBNAIL_SIZE - fit_img.height) // 2
            thumb.paste(fit_img, (offset_x, offset_y))
            img_bytes = thumb.tobytes()
            qimg = QImage(
                img_bytes,
                self.THUMBNAIL_SIZE,
                self.THUMBNAIL_SIZE,
                3 * self.THUMBNAIL_SIZE,
                QImage.Format.Format_RGB888,
            )
            # Keep a bytes reference alive so QImage data stays valid.
            self._img_bytes_ref = img_bytes
            self._preview_pixmap = QPixmap.fromImage(qimg)
        except Exception as exc:
            print(f"[MprThumbnailWidget] Failed to build preview pixmap: {exc}")
            self._preview_pixmap = None

        self.update()

    def set_dot_color(self, color: str) -> None:
        """
        Update the color used for the subwindow number in the top-right corner.

        Args:
            color: Hex color string, e.g. ``"#2196F3"``.
        """
        self._dot_color = color
        self.update()

    # ------------------------------------------------------------------
    # Qt painting
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt convention)
        """Paint the thumbnail: preview image + MPR badge + window number."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background — dark grey when no preview is available.
        painter.fillRect(self.rect(), QColor("#2a2a2a"))

        # Preview image.
        if self._preview_pixmap is not None and not self._preview_pixmap.isNull():
            painter.drawPixmap(0, 0, self._preview_pixmap)

        # MPR badge — semi-transparent dark background with yellow text.
        badge_text = "MPR"
        badge_font = QFont()
        badge_font.setPointSize(7)
        badge_font.setBold(True)
        painter.setFont(badge_font)
        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(badge_text)
        padding = 3
        badge_rect = text_rect.adjusted(-padding, -padding, padding, padding)
        badge_rect.moveTopLeft(QPoint(3, 3))

        painter.setBrush(QColor(0, 0, 0, 170))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge_rect, 2, 2)

        painter.setPen(QColor(255, 200, 50))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

        # Subwindow number — top-right (detached MPR: no digit).
        if self._subwindow_index >= 0:
            slot_font = QFont()
            slot_font.setBold(True)
            slot_font.setPointSize(9)
            painter.setFont(slot_font)
            fm = painter.fontMetrics()
            label = subwindow_slot_display_number(self._subwindow_index)
            tw = fm.horizontalAdvance(label)
            th = fm.height()
            margin = 3
            text_rect = QRect(
                self.THUMBNAIL_SIZE - margin - tw,
                margin,
                tw,
                th,
            )
            fill = QColor(self._dot_color)
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                painter.setPen(QPen(QColor(0, 0, 0, 210)))
                painter.drawText(
                    text_rect.translated(ox, oy),
                    Qt.AlignmentFlag.AlignCenter,
                    label,
                )
            painter.setPen(QPen(fill))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)
        clear_act = menu.addAction("Clear MPR")
        clear_act.triggered.connect(
            lambda: self.clear_mpr_requested.emit(self._subwindow_index)
        )
        menu.exec(self.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Record press position for drag threshold detection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Start a drag operation if the mouse has moved far enough."""
        if (
            (event.buttons() & Qt.MouseButton.LeftButton)
            and self._drag_start_pos is not None
        ):
            dist = (event.pos() - self._drag_start_pos).manhattanLength()
            if dist > 10:
                self._start_drag()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Emit ``clicked`` if the release was not the end of a drag."""
        if event.button() == Qt.MouseButton.LeftButton:
            dist = (
                (event.pos() - self._drag_start_pos).manhattanLength()
                if self._drag_start_pos is not None
                else 0
            )
            if dist <= 10:
                self.clicked.emit(self._subwindow_index)
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Drag support
    # ------------------------------------------------------------------

    def _start_drag(self) -> None:
        """
        Initiate a QDrag with the ``application/x-dv3-mpr-assign`` MIME type.

        The MIME payload is the source subwindow index encoded as ASCII bytes
        so that drop targets (SubWindowContainer) can decode it without ambiguity.
        """
        self._drag_start_pos = None  # Prevent re-entry.

        drag = QDrag(self)
        mime = QMimeData()
        payload = QByteArray(str(self._subwindow_index).encode("ascii"))
        mime.setData(MPR_ASSIGN_MIME, payload)
        drag.setMimeData(mime)

        if self._preview_pixmap is not None and not self._preview_pixmap.isNull():
            scaled = self._preview_pixmap.scaled(
                48,
                48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            drag.setPixmap(scaled)
            drag.setHotSpot(QPoint(scaled.width() // 2, scaled.height() // 2))

        drag.exec(Qt.DropAction.CopyAction)
        self.drag_started.emit(self._subwindow_index)
