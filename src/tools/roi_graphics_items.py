"""
ROI graphics primitives and scene-geometry helpers.

Extracted from ``tools.roi_manager`` so the manager can focus on orchestration
while keeping the Qt item implementations reusable and importable on their own.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QPainterPath,
    QPainterPathStroker,
    QPen,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsSceneMouseEvent,
    QGraphicsTextItem,
)

from gui.view_transform_helpers import graphics_view_uniform_zoom
from utils.log_sanitizer import sanitized_format_exc


class _ROIProtocol(Protocol):
    item: QGraphicsEllipseItem | QGraphicsRectItem

    def get_bounds(self) -> QRectF: ...
    def update_resize_handle_positions(self) -> None: ...
    def begin_resize_handle_drag(self, handle_id: str, scene_pos: QPointF) -> None: ...
    def continue_resize_handle_drag(self, scene_pos: QPointF) -> None: ...
    def finish_resize_handle_drag(self) -> None: ...

_logger = logging.getLogger(__name__)


class ROIGraphicsEllipseItem(QGraphicsEllipseItem):
    """Custom ellipse item that emits ROI movement callbacks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_moved_callback: Callable[[], None] | None = None
        self._last_callback_pos: QPointF | None = None

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.on_moved_callback:
                try:
                    self.on_moved_callback()
                except Exception:
                    pass
        return super().itemChange(change, value)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if event.buttons() & Qt.MouseButton.LeftButton:
            current_pos = self.pos()
            if self._last_callback_pos is None or (
                current_pos - self._last_callback_pos
            ).manhattanLength() > 1.0:
                if self.on_moved_callback:
                    try:
                        self.on_moved_callback()
                        self._last_callback_pos = current_pos
                    except Exception:
                        pass

    def shape(self) -> QPainterPath:
        """Only the ellipse outline, not the interior, is hit-testable."""
        path = QPainterPath()
        path.addEllipse(self.rect())
        tolerance = max(self.pen().widthF(), 1.0) + 5.0
        pen = QPen(Qt.PenStyle.SolidLine)
        pen.setWidthF(tolerance)
        stroker = QPainterPathStroker(pen)
        return stroker.createStroke(path)


class ROIGraphicsRectItem(QGraphicsRectItem):
    """Custom rectangle item that emits ROI movement callbacks."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.on_moved_callback: Callable[[], None] | None = None
        self._last_callback_pos: QPointF | None = None

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            if self.on_moved_callback:
                try:
                    self.on_moved_callback()
                except Exception:
                    pass
        return super().itemChange(change, value)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mouseMoveEvent(event)
        if event.buttons() & Qt.MouseButton.LeftButton:
            current_pos = self.pos()
            if self._last_callback_pos is None or (
                current_pos - self._last_callback_pos
            ).manhattanLength() > 1.0:
                if self.on_moved_callback:
                    try:
                        self.on_moved_callback()
                        self._last_callback_pos = current_pos
                    except Exception:
                        pass

    def shape(self) -> QPainterPath:
        """Only the rectangle outline, not the interior, is hit-testable."""
        path = QPainterPath()
        path.addRect(self.rect())
        tolerance = max(self.pen().widthF(), 1.0) + 5.0
        pen = QPen(Qt.PenStyle.SolidLine)
        pen.setWidthF(tolerance)
        stroker = QPainterPathStroker(pen)
        return stroker.createStroke(path)


ROI_RESIZE_HANDLE_IDS: tuple[str, ...] = ("tl", "tm", "tr", "mr", "br", "bm", "bl", "ml")

_CURSOR_FOR_RESIZE_HANDLE: dict[str, Qt.CursorShape] = {
    "tl": Qt.CursorShape.SizeFDiagCursor,
    "br": Qt.CursorShape.SizeFDiagCursor,
    "tr": Qt.CursorShape.SizeBDiagCursor,
    "bl": Qt.CursorShape.SizeBDiagCursor,
    "tm": Qt.CursorShape.SizeVerCursor,
    "bm": Qt.CursorShape.SizeVerCursor,
    "ml": Qt.CursorShape.SizeHorCursor,
    "mr": Qt.CursorShape.SizeHorCursor,
}


def compute_resized_scene_rect_from_handle(
    anchor: QRectF, handle: str, p: QPointF, min_size: float = 2.0
) -> QRectF:
    """Compute a new axis-aligned scene rectangle by dragging one resize handle."""
    left, top, right, bottom = (
        anchor.left(),
        anchor.top(),
        anchor.right(),
        anchor.bottom(),
    )
    x, y = p.x(), p.y()
    min_scene_size = min_size

    def clamp_w(new_left: float, new_right: float) -> tuple[float, float]:
        if new_right - new_left < min_scene_size:
            center = (new_left + new_right) * 0.5
            return center - min_scene_size / 2.0, center + min_scene_size / 2.0
        return new_left, new_right

    def clamp_h(new_top: float, new_bottom: float) -> tuple[float, float]:
        if new_bottom - new_top < min_scene_size:
            center = (new_top + new_bottom) * 0.5
            return center - min_scene_size / 2.0, center + min_scene_size / 2.0
        return new_top, new_bottom

    if handle == "br":
        new_left, new_top = left, top
        new_right, new_bottom = max(x, left + min_scene_size), max(y, top + min_scene_size)
        new_left, new_right = clamp_w(new_left, new_right)
        new_top, new_bottom = clamp_h(new_top, new_bottom)
        return QRectF(new_left, new_top, new_right - new_left, new_bottom - new_top).normalized()
    if handle == "tl":
        new_right, new_bottom = right, bottom
        new_left, new_top = min(x, new_right - min_scene_size), min(y, new_bottom - min_scene_size)
        new_left, new_right = clamp_w(new_left, new_right)
        new_top, new_bottom = clamp_h(new_top, new_bottom)
        return QRectF(new_left, new_top, new_right - new_left, new_bottom - new_top).normalized()
    if handle == "tr":
        new_left, new_bottom = left, bottom
        new_right, new_top = max(x, new_left + min_scene_size), min(y, new_bottom - min_scene_size)
        new_left, new_right = clamp_w(new_left, new_right)
        new_top, new_bottom = clamp_h(new_top, new_bottom)
        return QRectF(new_left, new_top, new_right - new_left, new_bottom - new_top).normalized()
    if handle == "bl":
        new_right, new_top = right, top
        new_left, new_bottom = min(x, new_right - min_scene_size), max(y, new_top + min_scene_size)
        new_left, new_right = clamp_w(new_left, new_right)
        new_top, new_bottom = clamp_h(new_top, new_bottom)
        return QRectF(new_left, new_top, new_right - new_left, new_bottom - new_top).normalized()
    if handle == "mr":
        new_left, new_top, new_bottom = left, top, bottom
        new_right = max(x, new_left + min_scene_size)
        new_left, new_right = clamp_w(new_left, new_right)
        new_top, new_bottom = clamp_h(new_top, new_bottom)
        return QRectF(new_left, new_top, new_right - new_left, new_bottom - new_top).normalized()
    if handle == "ml":
        new_right, new_top, new_bottom = right, top, bottom
        new_left = min(x, new_right - min_scene_size)
        new_left, new_right = clamp_w(new_left, new_right)
        new_top, new_bottom = clamp_h(new_top, new_bottom)
        return QRectF(new_left, new_top, new_right - new_left, new_bottom - new_top).normalized()
    if handle == "tm":
        new_left, new_right, new_bottom = left, right, bottom
        new_top = min(y, new_bottom - min_scene_size)
        new_left, new_right = clamp_w(new_left, new_right)
        new_top, new_bottom = clamp_h(new_top, new_bottom)
        return QRectF(new_left, new_top, new_right - new_left, new_bottom - new_top).normalized()
    if handle == "bm":
        new_left, new_right, new_top = left, right, top
        new_bottom = max(y, new_top + min_scene_size)
        new_left, new_right = clamp_w(new_left, new_right)
        new_top, new_bottom = clamp_h(new_top, new_bottom)
        return QRectF(new_left, new_top, new_right - new_left, new_bottom - new_top).normalized()
    return anchor.normalized()


def apply_roi_scene_bounding_rect(roi: _ROIProtocol, rect: QRectF) -> None:
    """Apply a scene-axis-aligned bounding box to the ROI graphics item."""
    rect = rect.normalized()
    roi.item.setPos(rect.topLeft())
    roi.item.setRect(0.0, 0.0, rect.width(), rect.height())
    handles = getattr(roi, "_resize_handles", None)
    if handles:
        roi.update_resize_handle_positions()


def roi_scene_bounding_rect(roi: _ROIProtocol) -> QRectF:
    """Return the ROI shape bounds in scene coordinates."""
    return roi.item.mapRectToScene(roi.item.rect())


class ROIResizeHandleItem(QGraphicsRectItem):
    """Small scene-space handle for resizing a finished ROI."""

    HANDLE_HALF = 4.0

    def __init__(self, roi_item: _ROIProtocol, handle_id: str) -> None:
        size = self.HANDLE_HALF * 2.0
        super().__init__(-self.HANDLE_HALF, -self.HANDLE_HALF, size, size)
        self._roi_item = roi_item
        self._handle_id = handle_id
        self._dragging = False
        self.setAcceptHoverEvents(True)
        self.setPen(QPen(QColor(255, 255, 255), 1))
        self.setBrush(QBrush(QColor(0, 200, 255, 200)))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.setZValue(120)
        self.setCursor(QCursor(_CURSOR_FOR_RESIZE_HANDLE.get(handle_id, Qt.CursorShape.ArrowCursor)))

    def handle_id(self) -> str:
        return self._handle_id

    def roi_graphics_shape_item(self) -> QGraphicsEllipseItem | QGraphicsRectItem:
        return self._roi_item.item

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._roi_item.begin_resize_handle_drag(self._handle_id, event.scenePos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            self._roi_item.continue_resize_handle_drag(event.scenePos())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._roi_item.finish_resize_handle_drag()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class DraggableStatisticsOverlay(QGraphicsTextItem):
    """Draggable ROI statistics overlay that persists its viewport offset."""

    def __init__(self, roi: _ROIProtocol, offset_update_callback: Callable[[float, float], None]):
        super().__init__()
        self.roi: _ROIProtocol | None = roi
        self.offset_update_callback = offset_update_callback
        self._updating_position = False
        self._is_deleted = False

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value) -> object:
        if self._is_deleted:
            return super().itemChange(change, value)

        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged
            and not self._updating_position
        ):
            try:
                if self.roi is None or not hasattr(self.roi, "item") or self.roi.item is None:
                    return super().itemChange(change, value)
                if self.roi.item.scene() is None or self.scene() is None:
                    return super().itemChange(change, value)

                view = self.scene().views()[0] if self.scene().views() else None
                if view is not None:
                    bounds = self.roi.get_bounds()
                    overlay_pos = self.pos()
                    scene_to_viewport_scale = graphics_view_uniform_zoom(view)
                    offset_x = (overlay_pos.x() - bounds.right()) * scene_to_viewport_scale
                    offset_y = (overlay_pos.y() - bounds.top()) * scene_to_viewport_scale
                    if self.offset_update_callback:
                        self.offset_update_callback(offset_x, offset_y)
            except Exception:
                _logger.debug("%s", sanitized_format_exc())

        return super().itemChange(change, value)

    def mark_deleted(self) -> None:
        self._is_deleted = True

    def clear_deleted_flag(self) -> None:
        self._is_deleted = False

    def set_updating_position(self, updating: bool) -> None:
        self._updating_position = updating


__all__ = [
    "ROI_RESIZE_HANDLE_IDS",
    "DraggableStatisticsOverlay",
    "ROIGraphicsEllipseItem",
    "ROIGraphicsRectItem",
    "ROIResizeHandleItem",
    "apply_roi_scene_bounding_rect",
    "compute_resized_scene_rect_from_handle",
    "roi_scene_bounding_rect",
]
