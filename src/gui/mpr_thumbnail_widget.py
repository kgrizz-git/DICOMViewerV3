"""
MPR Thumbnail Widget

A thumbnail widget representing an active MPR (Multi-Planar Reconstruction)
view in the series navigator bar.

Inputs:
    view_id (int): Stable ID of the MPR view this tile represents (attached
        or detached; the tile identity never changes when the view moves).
    pane_index (int | None): Pane currently showing the view, shown as the
        window number; None when detached.
    pixel_array (np.ndarray): 2-D float array from the MPR slice.
    window_center, window_width (float): Optional W/L for rendering.
    dot_color (str): Hex color for the subwindow digit in the top-right corner.

Outputs:
    - Visual thumbnail with MPR badge, optional bottom-left slice count (same
      rules as series thumbnails for View → slice/frame count badge), and
      subwindow number tint.
    - clicked(int) signal: emitted with view_id on left-click.
    - drag_started(int) signal: emitted when a drag begins.
    - Drag MIME type ``application/x-dv3-mpr-view`` carrying the versioned
      ``core.mpr_view_drag`` payload (view ID + operation + the owning
      controller's opaque origin token, never a pane index).
    - Context menu: Duplicate into Window…, Duplicate Linked into Window…,
      Unlink View (enabled only while linked) and Clear MPR, all by view_id.

Requirements:
    PySide6, PIL (Pillow), numpy, gui.navigator_colors.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image
from PySide6.QtCore import QByteArray, QMimeData, QPoint, QRect, Qt, Signal
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

from core.display_normalize import normalize_to_uint8
from core.lut_display import apply_user_invert_and_lut, rgb_preview_image
from core.lut_engine import LookUpTable
from core.mpr_view_drag import MPR_VIEW_MIME, OP_MOVE, encode_view_drag
from core.photometric_polarity import apply_monochrome1_polarity
from gui.navigator_colors import SUBWINDOW_DOT_COLORS, subwindow_slot_display_number
from utils.privacy.console import print_redacted

_THUMBNAIL_SIZE = 68  # pixels — matches SeriesThumbnail default


class MprThumbnailWidget(QWidget):
    """
    Thumbnail widget for an active MPR view.

    Displays a preview of the current MPR plane with:
    - A dark background when no preview image is available.
    - An ``MPR`` badge in the top-left corner.
    - Optional bottom-left slice count when ``set_slice_count`` is used (honours
      ``set_show_slice_frame_count_badge``, matching ``SeriesThumbnail``).
    - A very small colored window number in the top-right (same colors as
      series navigator slot indicators).

    Clicking the widget emits ``clicked(view_id)``. Dragging it produces an
    ``application/x-dv3-mpr-view`` MIME event so drop targets
    (SubWindowContainer) can move/attach exactly this view.
    """

    clicked = Signal(int)       # view_id
    drag_started = Signal(int)  # view_id
    clear_mpr_requested = Signal(int)  # view_id
    duplicate_requested = Signal(int)  # view_id
    duplicate_linked_requested = Signal(int)  # view_id
    unlink_requested = Signal(int)  # view_id

    THUMBNAIL_SIZE: int = _THUMBNAIL_SIZE

    def __init__(
        self, view_id: int, pane_index: int | None = None, parent: QWidget | None = None
    ) -> None:
        """
        Args:
            view_id: Stable ID of the MPR view this tile represents.
            pane_index: Pane showing the view, or None when detached.
            parent: Parent widget.
        """
        super().__init__(parent)
        self._view_id: int = view_id
        self._pane_index: int | None = pane_index
        self._tag: str = ""
        self._origin: str = ""  # controller drag-origin token; a tile without one cannot be dragged
        self._linked: bool = False  # member of a session-local link group (enables Unlink View)
        self._preview_pixmap: QPixmap | None = None
        self._dot_color: str = (
            "#9E9E9E"
            if pane_index is None
            else SUBWINDOW_DOT_COLORS.get(pane_index, "#2196F3")
        )
        self._drag_start_pos: QPoint | None = None
        self._img_bytes_ref: bytes | None = None
        # MPR stack depth for navigator badge (None = unknown / do not paint).
        self._slice_count: int | None = None
        # Align with SeriesThumbnail / View → Show Slice/Frame Count on Navigator.
        self._show_slice_frame_count_badge: bool = True

        self.setFixedSize(self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def view_id(self) -> int:
        """Stable ID of the view this tile represents."""
        return self._view_id

    @property
    def pane_index(self) -> int | None:
        """Pane currently showing the view (window number source), None if detached."""
        return self._pane_index

    def set_origin(self, origin: str) -> None:
        """Set the owning controller's opaque drag-origin token (stamped into drag payloads)."""
        self._origin = origin

    def apply_spec(self, spec: dict[str, Any], show_count_badge: bool) -> None:
        """Apply a navigator tile spec: caption, drag origin, link state, preview and badges."""
        self.set_caption(spec.get("tag", ""), spec.get("tooltip", ""), spec.get("linked", False))
        self.set_origin(spec.get("origin", ""))
        self.update_preview(
            spec.get("pixel_array"), spec.get("window_center"), spec.get("window_width"),
            spec.get("photometric_interpretation"),
            image_inverted=bool(spec.get("image_inverted", False)), lut=spec.get("lut"),
        )
        self.set_slice_count(spec.get("n_slices"))
        self.set_show_slice_frame_count_badge(show_count_badge)

    def set_caption(self, tag: str, tooltip: str, linked: bool = False) -> None:
        """Set the compact corner tag (e.g. ``S2.1L``), full tooltip (no PHI) and link state."""
        self._tag = tag
        self._linked = bool(linked)
        self.setToolTip(tooltip)
        self.update()

    def update_preview(
        self,
        pixel_array: np.ndarray | None,
        window_center: float | None = None,
        window_width: float | None = None,
        photometric_interpretation: str | None = None,
        *,
        image_inverted: bool = False,
        lut: LookUpTable | None = None,
    ) -> None:
        """
        Render a new preview from a 2-D float pixel array.

        Applies W/L windowing when both ``window_center`` and ``window_width``
        are provided; otherwise auto-scales to the data min/max.

        Args:
            pixel_array: 2-D float32 MPR slice array, or None to clear.
            window_center: Window centre for display (optional).
            window_width: Window width for display (optional, must be > 0).
            photometric_interpretation: Source series PI; MONOCHROME1 inverts the
                finalized 8-bit array so the thumbnail matches the pane it previews.
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
            arr = normalize_to_uint8(arr)

        uint8_arr = apply_monochrome1_polarity(
            arr.astype(np.uint8), photometric_interpretation
        )
        uint8_arr = apply_user_invert_and_lut(
            uint8_arr, image_inverted=image_inverted, lut=lut
        )

        try:
            # Convert via PIL for high-quality resize while preserving aspect ratio.
            pil_img = rgb_preview_image(uint8_arr)
            thumb = Image.new(
                "RGB",
                (self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE),
                color=(42, 42, 42),
            )
            fit_img = pil_img.copy()
            fit_img.thumbnail(
                (self.THUMBNAIL_SIZE, self.THUMBNAIL_SIZE),
                Image.Resampling.LANCZOS,
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
            print_redacted(f"[MprThumbnailWidget] Failed to build preview pixmap: {exc}")
            self._preview_pixmap = None

        self.update()

    def set_slice_count(self, count: int | None) -> None:
        """
        Set the number of planes in the MPR stack for the bottom-left badge.

        Args:
            count: Total MPR slices (``MprResult.n_slices``), or None to hide
                   the count until a value is provided again.
        """
        if count is None:
            self._slice_count = None
        else:
            try:
                n = int(count)
            except (TypeError, ValueError):
                self._slice_count = None
            else:
                self._slice_count = n if n > 0 else None
        self.update()

    def set_show_slice_frame_count_badge(self, show: bool) -> None:
        """Match series thumbnails: when False, show count only if slices > 1."""
        self._show_slice_frame_count_badge = bool(show)
        self.update()

    def _slice_count_badge_text(self) -> str:
        """Compact slice count string; empty when the badge should not paint."""
        n = self._slice_count
        if n is None or n <= 0:
            return ""
        if self._show_slice_frame_count_badge:
            return str(n)
        if n > 1:
            return str(n)
        return ""

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

    def paintEvent(self, event) -> None:
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

        indicator_text = self._slice_count_badge_text()
        if indicator_text:
            indicator_font = QFont()
            indicator_font.setBold(True)
            indicator_font.setPointSize(7)
            painter.setFont(indicator_font)
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(indicator_text)
            text_h = fm.height()
            padding = 3
            bottom_left = self.rect().bottomLeft()
            x = int(bottom_left.x()) + padding
            y_bottom = int(bottom_left.y()) - padding
            text_rect = QRect(x, y_bottom - text_h, text_w, text_h)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QColor(255, 255, 0))
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
                indicator_text,
            )

        if self._tag:
            tag_font = QFont()
            tag_font.setPointSize(7)
            painter.setFont(tag_font)
            tag_fm = painter.fontMetrics()
            tag_rect = QRect(
                self.THUMBNAIL_SIZE - 3 - tag_fm.horizontalAdvance(self._tag),
                self.THUMBNAIL_SIZE - 3 - tag_fm.height(),
                tag_fm.horizontalAdvance(self._tag),
                tag_fm.height(),
            )
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(tag_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom, self._tag)

        # Window number — top-right (detached view: no digit).
        if self._pane_index is not None:
            slot_font = QFont()
            slot_font.setBold(True)
            slot_font.setPointSize(9)
            painter.setFont(slot_font)
            fm = painter.fontMetrics()
            label = subwindow_slot_display_number(self._pane_index)
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

    def build_context_menu(self) -> QMenu:
        """Menu for this tile; both actions act on this exact view ID."""
        menu = QMenu(self)
        duplicate_act = menu.addAction("Duplicate into Window…")
        duplicate_act.triggered.connect(lambda: self.duplicate_requested.emit(self._view_id))
        linked_act = menu.addAction("Duplicate Linked into Window…")
        linked_act.triggered.connect(lambda: self.duplicate_linked_requested.emit(self._view_id))
        unlink_act = menu.addAction("Unlink View")
        unlink_act.setEnabled(self._linked)
        unlink_act.triggered.connect(lambda: self.unlink_requested.emit(self._view_id))
        clear_act = menu.addAction("Clear MPR")
        clear_act.triggered.connect(lambda: self.clear_mpr_requested.emit(self._view_id))
        return menu

    def _show_context_menu(self, pos) -> None:
        self.build_context_menu().exec(self.mapToGlobal(pos))

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
                self.clicked.emit(self._view_id)
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    # Drag support
    # ------------------------------------------------------------------

    def _start_drag(self) -> None:
        """
        Initiate a QDrag carrying the versioned ``application/x-dv3-mpr-view`` payload.

        The payload names the stable view ID and a "move" operation. It never
        carries a pane index, so a drop after the pane was cleared or replaced
        moves the original view (or does nothing), never the replacement. The
        controller's origin token rides along so another instance cannot
        collide on the same view ID; a tile with no/invalid token starts no drag.
        """
        self._drag_start_pos = None  # Prevent re-entry.
        try:
            payload = encode_view_drag(self._view_id, self._origin, OP_MOVE)
        except ValueError:
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MPR_VIEW_MIME, QByteArray(payload))
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

        drag.exec(Qt.DropAction.MoveAction)
        self.drag_started.emit(self._view_id)
