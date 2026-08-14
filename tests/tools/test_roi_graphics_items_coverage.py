"""Coverage tests for tools.roi_graphics_items: shapes, resize handles, callbacks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsScene,
    QGraphicsView,
)

from tools.roi_graphics_items import (
    ROI_RESIZE_HANDLE_IDS,
    DraggableStatisticsOverlay,
    ROIGraphicsEllipseItem,
    ROIGraphicsRectItem,
    ROIResizeHandleItem,
    apply_roi_scene_bounding_rect,
    compute_resized_scene_rect_from_handle,
    roi_scene_bounding_rect,
)

# ---------------------------------------------------------------------------
# ROIGraphicsEllipseItem
# ---------------------------------------------------------------------------

class TestROIGraphicsEllipseItem:
    @pytest.fixture(autouse=True)
    def _setup(self, qapp):
        self.scene = QGraphicsScene()
        self.item = ROIGraphicsEllipseItem(0.0, 0.0, 100.0, 60.0)
        self.scene.addItem(self.item)

    def test_item_change_no_callback(self):
        from PySide6.QtWidgets import QGraphicsItem
        result = self.item.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(5, 5)
        )
        assert result is not None

    def test_item_change_with_callback(self):
        cb = MagicMock()
        self.item.on_moved_callback = cb
        from PySide6.QtWidgets import QGraphicsItem
        self.item.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )
        cb.assert_called()

    def test_item_change_callback_raises(self):
        self.item.on_moved_callback = MagicMock(side_effect=RuntimeError("boom"))
        from PySide6.QtWidgets import QGraphicsItem
        # Should not raise
        self.item.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )

    def test_item_change_non_position(self):
        from PySide6.QtWidgets import QGraphicsItem
        result = self.item.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemZValueChange, 5.0
        )
        assert result == 5.0

    def test_shape_returns_stroked_outline(self):
        path = self.item.shape()
        assert not path.isEmpty()

    def test_shape_with_thick_pen(self):
        pen = QPen(Qt.PenStyle.SolidLine)
        pen.setWidthF(3.0)
        self.item.setPen(pen)
        path = self.item.shape()
        assert not path.isEmpty()

    def test_mouse_move_left_button(self):
        cb = MagicMock()
        self.item.on_moved_callback = cb
        self.item.setPos(0.0, 0.0)
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.LeftButton
        self.item.mouseMoveEvent(ev)
        cb.assert_called()

    def test_mouse_move_no_callback(self):
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.LeftButton
        # Should not raise
        self.item.mouseMoveEvent(ev)

    def test_mouse_move_right_button_no_trigger(self):
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        cb = MagicMock()
        self.item.on_moved_callback = cb
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.RightButton
        self.item.mouseMoveEvent(ev)
        cb.assert_not_called()

    def test_mouse_move_callback_raises(self):
        self.item.on_moved_callback = MagicMock(side_effect=RuntimeError("boom"))
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.LeftButton
        # Should not raise
        self.item.mouseMoveEvent(ev)

    def test_mouse_move_throttling(self):
        cb = MagicMock()
        self.item.on_moved_callback = cb
        self.item.setPos(0.0, 0.0)
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.LeftButton
        # First call sets _last_callback_pos
        self.item.mouseMoveEvent(ev)
        assert cb.call_count == 1
        # Second call at same pos should be throttled (manhattanLength <= 1)
        self.item.mouseMoveEvent(ev)
        assert cb.call_count == 1


# ---------------------------------------------------------------------------
# ROIGraphicsRectItem
# ---------------------------------------------------------------------------

class TestROIGraphicsRectItem:
    @pytest.fixture(autouse=True)
    def _setup(self, qapp):
        self.scene = QGraphicsScene()
        self.item = ROIGraphicsRectItem(0.0, 0.0, 80.0, 50.0)
        self.scene.addItem(self.item)

    def test_item_change_with_callback(self):
        cb = MagicMock()
        self.item.on_moved_callback = cb
        from PySide6.QtWidgets import QGraphicsItem
        self.item.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )
        cb.assert_called()

    def test_item_change_callback_raises(self):
        self.item.on_moved_callback = MagicMock(side_effect=RuntimeError("boom"))
        from PySide6.QtWidgets import QGraphicsItem
        self.item.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )

    def test_shape(self):
        path = self.item.shape()
        assert not path.isEmpty()

    def test_shape_thick_pen(self):
        pen = QPen(Qt.PenStyle.SolidLine)
        pen.setWidthF(4.0)
        self.item.setPen(pen)
        path = self.item.shape()
        assert not path.isEmpty()

    def test_mouse_move_left_button(self):
        cb = MagicMock()
        self.item.on_moved_callback = cb
        self.item.setPos(0.0, 0.0)
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.LeftButton
        self.item.mouseMoveEvent(ev)
        cb.assert_called()

    def test_mouse_move_no_callback(self):
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.LeftButton
        self.item.mouseMoveEvent(ev)

    def test_mouse_move_right_button(self):
        cb = MagicMock()
        self.item.on_moved_callback = cb
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.RightButton
        self.item.mouseMoveEvent(ev)
        cb.assert_not_called()

    def test_mouse_move_callback_raises(self):
        self.item.on_moved_callback = MagicMock(side_effect=RuntimeError("boom"))
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.LeftButton
        self.item.mouseMoveEvent(ev)

    def test_mouse_move_throttling(self):
        cb = MagicMock()
        self.item.on_moved_callback = cb
        self.item.setPos(0.0, 0.0)
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.buttons = lambda: Qt.MouseButton.LeftButton
        self.item.mouseMoveEvent(ev)
        assert cb.call_count == 1
        self.item.mouseMoveEvent(ev)
        assert cb.call_count == 1

    def test_item_change_non_position(self):
        from PySide6.QtWidgets import QGraphicsItem
        result = self.item.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemZValueChange, 3.0
        )
        assert result == 3.0


# ---------------------------------------------------------------------------
# compute_resized_scene_rect_from_handle
# ---------------------------------------------------------------------------

class TestComputeResizedSceneRect:
    anchor = QRectF(10.0, 10.0, 40.0, 30.0)

    def test_br_handle(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "br", QPointF(60.0, 50.0))
        assert r.right() >= 50.0
        assert r.bottom() >= 40.0

    def test_tl_handle(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "tl", QPointF(5.0, 5.0))
        assert r.left() <= 10.0
        assert r.top() <= 10.0

    def test_tr_handle(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "tr", QPointF(60.0, 5.0))
        assert r.right() >= 50.0
        assert r.top() <= 10.0

    def test_bl_handle(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "bl", QPointF(5.0, 50.0))
        assert r.left() <= 10.0
        assert r.bottom() >= 40.0

    def test_mr_handle(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "mr", QPointF(60.0, 25.0))
        assert r.right() >= 50.0

    def test_ml_handle(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "ml", QPointF(5.0, 25.0))
        assert r.left() <= 10.0

    def test_tm_handle(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "tm", QPointF(30.0, 5.0))
        assert r.top() <= 10.0

    def test_bm_handle(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "bm", QPointF(30.0, 50.0))
        assert r.bottom() >= 40.0

    def test_unknown_handle_returns_normalized_anchor(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "xx", QPointF(0, 0))
        assert r == self.anchor.normalized()

    def test_br_clamp_min_size(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "br", QPointF(11.0, 11.0), min_size=10.0)
        assert r.width() >= 10.0
        assert r.height() >= 10.0

    def test_tl_clamp_min_size(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "tl", QPointF(59.0, 39.0), min_size=10.0)
        assert r.width() >= 10.0
        assert r.height() >= 10.0

    def test_tr_clamp_min_size(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "tr", QPointF(11.0, 39.0), min_size=10.0)
        assert r.width() >= 10.0
        assert r.height() >= 10.0

    def test_bl_clamp_min_size(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "bl", QPointF(59.0, 11.0), min_size=10.0)
        assert r.width() >= 10.0
        assert r.height() >= 10.0

    def test_mr_clamp(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "mr", QPointF(11.0, 25.0), min_size=10.0)
        assert r.width() >= 10.0

    def test_ml_clamp(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "ml", QPointF(59.0, 25.0), min_size=10.0)
        assert r.width() >= 10.0

    def test_tm_clamp(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "tm", QPointF(30.0, 39.0), min_size=10.0)
        assert r.height() >= 10.0

    def test_bm_clamp(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "bm", QPointF(30.0, 11.0), min_size=10.0)
        assert r.height() >= 10.0

    def test_br_clamp_w_narrow(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "br", QPointF(5.0, 50.0), min_size=20.0)
        assert r.width() >= 20.0

    def test_tl_clamp_h_narrow(self):
        r = compute_resized_scene_rect_from_handle(self.anchor, "tl", QPointF(60.0, 5.0), min_size=20.0)
        assert r.height() >= 20.0


# ---------------------------------------------------------------------------
# apply_roi_scene_bounding_rect / roi_scene_bounding_rect
# ---------------------------------------------------------------------------

class TestSceneBoundingRectHelpers:
    def test_apply_and_read(self, qapp):
        scene = QGraphicsScene()
        item = ROIGraphicsEllipseItem(0.0, 0.0, 10.0, 10.0)
        scene.addItem(item)
        roi = SimpleNamespace(
            item=item,
            update_resize_handle_positions=MagicMock(),
            _resize_handles=None,
        )
        apply_roi_scene_bounding_rect(roi, QRectF(5.0, 10.0, 20.0, 30.0))
        assert item.pos() == QPointF(5.0, 10.0)
        assert item.rect().width() == 20.0
        assert item.rect().height() == 30.0

    def test_apply_with_handles(self, qapp):
        scene = QGraphicsScene()
        item = ROIGraphicsRectItem(0.0, 0.0, 10.0, 10.0)
        scene.addItem(item)
        roi = SimpleNamespace(
            item=item,
            update_resize_handle_positions=MagicMock(),
            _resize_handles={"tl": MagicMock()},
        )
        apply_roi_scene_bounding_rect(roi, QRectF(0, 0, 50, 50))
        roi.update_resize_handle_positions.assert_called_once()

    def test_roi_scene_bounding_rect(self, qapp):
        scene = QGraphicsScene()
        item = ROIGraphicsEllipseItem(3.0, 4.0, 20.0, 10.0)
        scene.addItem(item)
        roi = SimpleNamespace(item=item)
        rect = roi_scene_bounding_rect(roi)
        assert rect.x() == pytest.approx(3.0)
        assert rect.y() == pytest.approx(4.0)
        assert rect.width() == pytest.approx(20.0)
        assert rect.height() == pytest.approx(10.0)

    def test_apply_normalized_rect(self, qapp):
        scene = QGraphicsScene()
        item = ROIGraphicsRectItem(0.0, 0.0, 10.0, 10.0)
        scene.addItem(item)
        roi = SimpleNamespace(
            item=item,
            update_resize_handle_positions=MagicMock(),
            _resize_handles=None,
        )
        # Inverted rect should be normalized
        apply_roi_scene_bounding_rect(roi, QRectF(20.0, 20.0, -10.0, -10.0))
        assert item.rect().width() == pytest.approx(10.0)
        assert item.rect().height() == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# ROIResizeHandleItem
# ---------------------------------------------------------------------------

class TestROIResizeHandleItem:
    @pytest.fixture(autouse=True)
    def _setup(self, qapp):
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.roi_item = ROIGraphicsEllipseItem(0.0, 0.0, 100.0, 80.0)
        self.scene.addItem(self.roi_item)
        self.roi_proto = SimpleNamespace(
            item=self.roi_item,
            begin_resize_handle_drag=MagicMock(),
            continue_resize_handle_drag=MagicMock(),
            finish_resize_handle_drag=MagicMock(),
        )
        self.handle = ROIResizeHandleItem(self.roi_proto, "tl")
        self.scene.addItem(self.handle)

    def test_handle_id(self):
        assert self.handle.handle_id() == "tl"

    def test_roi_graphics_shape_item(self):
        assert self.handle.roi_graphics_shape_item() is self.roi_item

    def test_all_handle_ids_have_cursors(self):
        for hid in ROI_RESIZE_HANDLE_IDS:
            h = ROIResizeHandleItem(self.roi_proto, hid)
            assert h.handle_id() == hid

    def _make_event(self, button=Qt.MouseButton.LeftButton, scene_pos=QPointF(5.0, 5.0)):
        from PySide6.QtWidgets import QGraphicsSceneMouseEvent
        ev = QGraphicsSceneMouseEvent()
        ev.button = lambda: button
        ev.buttons = lambda: button
        ev.scenePos = lambda: scene_pos
        ev.accept = MagicMock()
        return ev

    def test_mouse_press_left_button(self):
        ev = self._make_event(Qt.MouseButton.LeftButton, QPointF(5.0, 5.0))
        self.handle.mousePressEvent(ev)
        self.roi_proto.begin_resize_handle_drag.assert_called_once_with("tl", QPointF(5.0, 5.0))
        ev.accept.assert_called_once()

    def test_mouse_press_right_button_falls_through(self):
        ev = self._make_event(Qt.MouseButton.RightButton)
        self.handle.mousePressEvent(ev)
        self.roi_proto.begin_resize_handle_drag.assert_not_called()

    def test_mouse_move_dragging(self):
        self.handle._dragging = True
        ev = self._make_event(Qt.MouseButton.LeftButton, QPointF(15.0, 15.0))
        self.handle.mouseMoveEvent(ev)
        self.roi_proto.continue_resize_handle_drag.assert_called_once_with(QPointF(15.0, 15.0))
        ev.accept.assert_called_once()

    def test_mouse_move_not_dragging(self):
        self.handle._dragging = False
        ev = self._make_event(Qt.MouseButton.LeftButton, QPointF(15.0, 15.0))
        self.handle.mouseMoveEvent(ev)
        self.roi_proto.continue_resize_handle_drag.assert_not_called()

    def test_mouse_release_dragging(self):
        self.handle._dragging = True
        ev = self._make_event(Qt.MouseButton.LeftButton)
        self.handle.mouseReleaseEvent(ev)
        assert self.handle._dragging is False
        self.roi_proto.finish_resize_handle_drag.assert_called_once()
        ev.accept.assert_called_once()

    def test_mouse_release_right_button_falls_through(self):
        self.handle._dragging = True
        ev = self._make_event(Qt.MouseButton.RightButton)
        self.handle.mouseReleaseEvent(ev)
        self.roi_proto.finish_resize_handle_drag.assert_not_called()

    def test_mouse_release_not_dragging(self):
        self.handle._dragging = False
        ev = self._make_event(Qt.MouseButton.LeftButton)
        self.handle.mouseReleaseEvent(ev)
        self.roi_proto.finish_resize_handle_drag.assert_not_called()


# ---------------------------------------------------------------------------
# DraggableStatisticsOverlay
# ---------------------------------------------------------------------------

class TestDraggableStatisticsOverlay:
    @pytest.fixture(autouse=True)
    def _setup(self, qapp):
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.scene.addWidget(self.view)
        self.roi = SimpleNamespace(
            item=QGraphicsEllipseItem(0.0, 0.0, 50.0, 50.0),
            get_bounds=MagicMock(return_value=QRectF(0, 0, 50, 50)),
        )
        self.scene.addItem(self.roi.item)
        self.cb = MagicMock()
        self.overlay = DraggableStatisticsOverlay(self.roi, self.cb)
        self.scene.addItem(self.overlay)

    def test_mark_and_clear_deleted(self):
        self.overlay.mark_deleted()
        assert self.overlay._is_deleted is True
        self.overlay.clear_deleted_flag()
        assert self.overlay._is_deleted is False

    def test_set_updating_position(self):
        self.overlay.set_updating_position(True)
        assert self.overlay._updating_position is True
        self.overlay.set_updating_position(False)
        assert self.overlay._updating_position is False

    def test_item_change_deleted_ignores(self):
        from PySide6.QtWidgets import QGraphicsItem
        self.overlay.mark_deleted()
        # Should just call super without callback
        result = self.overlay.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(5, 5)
        )
        assert result is not None

    def test_item_change_updating_position_ignores(self):
        from PySide6.QtWidgets import QGraphicsItem
        self.overlay.set_updating_position(True)
        self.overlay.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(5, 5)
        )
        self.cb.assert_not_called()

    def test_item_change_non_position(self):
        from PySide6.QtWidgets import QGraphicsItem
        result = self.overlay.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemZValueChange, 10.0
        )
        assert result == 10.0

    def test_item_change_no_roi(self):
        from PySide6.QtWidgets import QGraphicsItem
        self.overlay.roi = None
        # Should not raise, just call super
        self.overlay.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )

    def test_item_change_no_scene(self):
        from PySide6.QtWidgets import QGraphicsItem
        self.overlay.roi.item.scene = MagicMock(return_value=None)
        self.overlay.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )

    def test_item_change_no_views(self):
        from PySide6.QtWidgets import QGraphicsItem
        self.scene.views = MagicMock(return_value=[])
        self.overlay.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )

    def test_item_change_callback_exception(self):
        from PySide6.QtWidgets import QGraphicsItem
        self.cb.side_effect = RuntimeError("boom")
        # Should not raise
        self.overlay.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )

    def test_item_change_normal_callback(self):
        from PySide6.QtWidgets import QGraphicsItem
        self.overlay.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )
        self.cb.assert_called_once()

    def test_roi_item_none(self):
        from PySide6.QtWidgets import QGraphicsItem
        self.overlay.roi = SimpleNamespace(item=None)
        self.overlay.itemChange(
            QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )
