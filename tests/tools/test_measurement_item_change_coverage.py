"""Coverage tests for tools.measurement_item_change: all branches and helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QLineF, QPointF
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsScene,
    QGraphicsTextItem,
)

from tools.measurement_item_change import (
    _fmt_point,
    _invalidate_measurement_line_scene,
    _line_item_str,
    _viewport_to_scene_scale,
    apply_end_handle_scene_move,
    apply_measurement_group_position_has_changed,
    apply_measurement_group_selection_changed,
    apply_start_handle_scene_move,
    debug_log_handle_drag,
    notify_handle_drag_callbacks,
    process_measurement_group_item_change,
    process_measurement_handle_item_change,
    resolve_measurement_group_position_change,
    sync_measurement_geometry_after_external_move,
    sync_other_handle_during_drag,
)

# ---------------------------------------------------------------------------
# _fmt_point / _line_item_str helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_fmt_point(self):
        assert _fmt_point(QPointF(1.0, 2.0)) == "(1.0, 2.0)"

    def test_fmt_point_negative(self):
        assert _fmt_point(QPointF(-3.5, 0.0)) == "(-3.5, 0.0)"

    def test_line_item_str(self):
        li = QGraphicsLineItem(QLineF(1.0, 2.0, 3.0, 4.0))
        result = _line_item_str(li)
        assert "p1=" in result
        assert "p2=" in result


# ---------------------------------------------------------------------------
# debug_log_handle_drag
# ---------------------------------------------------------------------------

class TestDebugLogHandleDrag:
    def _make_measurement(self):
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 10))
        m = SimpleNamespace(
            pos=lambda: QPointF(5, 5),
            start_point=QPointF(0, 0),
            end_point=QPointF(10, 10),
            end_relative=QPointF(10, 10),
            line_item=line_item,
            start_handle=SimpleNamespace(pos=lambda: QPointF(0, 0)),
            end_handle=SimpleNamespace(pos=lambda: QPointF(10, 10)),
        )
        return m

    def test_before_phase(self):
        from utils import debug_flags
        old = debug_flags.DEBUG_MEASUREMENT_DRAG
        try:
            debug_flags.DEBUG_MEASUREMENT_DRAG = True
            m = self._make_measurement()
            handle = SimpleNamespace(is_start=True, pos=lambda: QPointF(0, 0))
            debug_log_handle_drag(handle, m, phase="before")
        finally:
            debug_flags.DEBUG_MEASUREMENT_DRAG = old

    def test_after_phase(self):
        from utils import debug_flags
        old = debug_flags.DEBUG_MEASUREMENT_DRAG
        try:
            debug_flags.DEBUG_MEASUREMENT_DRAG = True
            m = self._make_measurement()
            handle = SimpleNamespace(is_start=False, pos=lambda: QPointF(10, 10))
            debug_log_handle_drag(handle, m, phase="after")
        finally:
            debug_flags.DEBUG_MEASUREMENT_DRAG = old

    def test_disabled_no_output(self):
        from utils import debug_flags
        old = debug_flags.DEBUG_MEASUREMENT_DRAG
        try:
            debug_flags.DEBUG_MEASUREMENT_DRAG = False
            m = self._make_measurement()
            handle = SimpleNamespace(is_start=True, pos=lambda: QPointF(0, 0))
            # Should not print anything
            debug_log_handle_drag(handle, m, phase="before")
        finally:
            debug_flags.DEBUG_MEASUREMENT_DRAG = old

    def test_no_start_handle(self):
        from utils import debug_flags
        old = debug_flags.DEBUG_MEASUREMENT_DRAG
        try:
            debug_flags.DEBUG_MEASUREMENT_DRAG = True
            m = self._make_measurement()
            m.start_handle = None
            handle = SimpleNamespace(is_start=True, pos=lambda: QPointF(0, 0))
            debug_log_handle_drag(handle, m, phase="before")
        finally:
            debug_flags.DEBUG_MEASUREMENT_DRAG = old


# ---------------------------------------------------------------------------
# _invalidate_measurement_line_scene
# ---------------------------------------------------------------------------

class TestInvalidateMeasurementLineScene:
    def test_no_scene(self):
        m = SimpleNamespace(scene=lambda: None, line_item=MagicMock())
        _invalidate_measurement_line_scene(m)

    def test_with_scene(self):
        scene = MagicMock()
        m = SimpleNamespace(scene=lambda: scene, line_item=MagicMock())
        m.line_item.boundingRect.return_value = MagicMock()
        m.line_item.mapRectToScene.return_value = MagicMock()
        _invalidate_measurement_line_scene(m)
        scene.update.assert_called_once()


# ---------------------------------------------------------------------------
# apply_start_handle_scene_move / apply_end_handle_scene_move
# ---------------------------------------------------------------------------

class TestHandleSceneMoves:
    @pytest.fixture(autouse=True)
    def _setup(self, qapp):
        from tools.measurement_items import MeasurementItem

        self.scene = QGraphicsScene()
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        self.item = MeasurementItem(
            QPointF(0, 0), QPointF(10, 0), line_item, text_item,
            pixel_spacing=(1.0, 1.0),
        )
        self.scene.addItem(self.item)

    def test_apply_end_handle(self):
        apply_end_handle_scene_move(self.item, QPointF(20.0, 5.0))
        assert self.item.end_point == QPointF(20.0, 5.0)
        assert self.item.start_point == QPointF(0.0, 0.0)

    def test_apply_start_handle(self):
        apply_start_handle_scene_move(self.item, QPointF(5.0, 3.0))
        assert self.item.start_point == QPointF(5.0, 3.0)
        assert self.item.pos() == QPointF(5.0, 3.0)
        assert self.item.end_point == QPointF(10.0, 0.0)


# ---------------------------------------------------------------------------
# sync_other_handle_during_drag
# ---------------------------------------------------------------------------

class TestSyncOtherHandle:
    @pytest.fixture(autouse=True)
    def _setup(self, qapp):
        from tools.measurement_items import MeasurementItem

        self.scene = QGraphicsScene()
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        self.item = MeasurementItem(
            QPointF(0, 0), QPointF(10, 0), line_item, text_item,
        )
        self.scene.addItem(self.item)
        # Handles must be in the scene for sync to run
        self.scene.addItem(self.item.start_handle)
        self.scene.addItem(self.item.end_handle)

    def test_sync_end_when_dragging_start(self):
        handle = SimpleNamespace(is_start=True)
        sync_other_handle_during_drag(handle, self.item)
        pos = self.item.end_handle.pos()
        assert pos.x() == pytest.approx(10.0)
        assert pos.y() == pytest.approx(0.0)

    def test_sync_start_when_dragging_end(self):
        handle = SimpleNamespace(is_start=False)
        sync_other_handle_during_drag(handle, self.item)
        pos = self.item.start_handle.pos()
        assert pos.x() == pytest.approx(0.0)
        assert pos.y() == pytest.approx(0.0)

    def test_no_end_handle(self):
        handle = SimpleNamespace(is_start=True)
        self.item.end_handle = None
        sync_other_handle_during_drag(handle, self.item)

    def test_no_start_handle(self):
        handle = SimpleNamespace(is_start=False)
        self.item.start_handle = None
        sync_other_handle_during_drag(handle, self.item)

    def test_end_handle_not_in_scene(self):
        handle = SimpleNamespace(is_start=True)
        end_handle = MagicMock()
        end_handle.scene.return_value = None
        self.item.end_handle = end_handle
        sync_other_handle_during_drag(handle, self.item)

    def test_start_handle_not_in_scene(self):
        handle = SimpleNamespace(is_start=False)
        start_handle = MagicMock()
        start_handle.scene.return_value = None
        self.item.start_handle = start_handle
        sync_other_handle_during_drag(handle, self.item)


# ---------------------------------------------------------------------------
# notify_handle_drag_callbacks
# ---------------------------------------------------------------------------

class TestNotifyCallbacks:
    def test_both_callbacks(self):
        m = SimpleNamespace(
            on_moved_callback=MagicMock(),
            on_handle_drag_move_callback=MagicMock(),
        )
        notify_handle_drag_callbacks(m, QPointF(5, 5))
        m.on_moved_callback.assert_called_once()
        m.on_handle_drag_move_callback.assert_called_once_with(QPointF(5, 5))

    def test_no_callbacks(self):
        m = SimpleNamespace(
            on_moved_callback=None,
            on_handle_drag_move_callback=None,
        )
        notify_handle_drag_callbacks(m, QPointF(5, 5))

    def test_moved_callback_raises(self):
        m = SimpleNamespace(
            on_moved_callback=MagicMock(side_effect=RuntimeError("boom")),
            on_handle_drag_move_callback=MagicMock(),
        )
        notify_handle_drag_callbacks(m, QPointF(5, 5))
        m.on_handle_drag_move_callback.assert_called_once()

    def test_drag_move_callback_raises(self):
        m = SimpleNamespace(
            on_moved_callback=MagicMock(),
            on_handle_drag_move_callback=MagicMock(side_effect=RuntimeError("boom")),
        )
        notify_handle_drag_callbacks(m, QPointF(5, 5))
        m.on_moved_callback.assert_called_once()


# ---------------------------------------------------------------------------
# process_measurement_handle_item_change
# ---------------------------------------------------------------------------

class TestProcessHandleItemChange:
    def test_item_position_change_vetos(self):
        handle = SimpleNamespace(is_start=True)
        handled, result = process_measurement_handle_item_change(
            handle, QGraphicsItem.GraphicsItemChange.ItemPositionChange, QPointF(5, 5)
        )
        assert handled is True
        assert result == QPointF(5, 5)

    def test_non_position_change_falls_through(self):
        handle = SimpleNamespace(is_start=True)
        val = object()
        handled, result = process_measurement_handle_item_change(
            handle, QGraphicsItem.GraphicsItemChange.ItemZValueChange, val
        )
        assert handled is False
        assert result is val

    def test_no_measurement(self):
        handle = SimpleNamespace(is_start=True, parent_measurement=None)
        val = object()
        handled, result = process_measurement_handle_item_change(
            handle, QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, val
        )
        assert handled is False

    def test_measurement_no_scene(self):
        handle = SimpleNamespace(is_start=True)
        handle.parent_measurement = SimpleNamespace(scene=lambda: None)
        val = object()
        handled, result = process_measurement_handle_item_change(
            handle, QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, val
        )
        assert handled is True

    def test_updating_handles(self):
        from tools.measurement_items import MeasurementItem
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        m = MeasurementItem(QPointF(0, 0), QPointF(10, 0), line_item, text_item)
        m._updating_handles = True
        handle = SimpleNamespace(is_start=True, parent_measurement=m, pos=lambda: QPointF(0, 0))
        handled, result = process_measurement_handle_item_change(
            handle, QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(0, 0)
        )
        assert handled is True

    def test_start_handle_position_has_changed(self):
        from tools.measurement_items import MeasurementItem
        scene = QGraphicsScene()
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        m = MeasurementItem(QPointF(0, 0), QPointF(10, 0), line_item, text_item)
        scene.addItem(m)
        handle = SimpleNamespace(is_start=True, parent_measurement=m, pos=lambda: QPointF(5, 5))
        handled, result = process_measurement_handle_item_change(
            handle, QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(5, 5)
        )
        assert handled is False
        assert m.start_point == QPointF(5, 5)

    def test_end_handle_position_has_changed(self):
        from tools.measurement_items import MeasurementItem
        scene = QGraphicsScene()
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        m = MeasurementItem(QPointF(0, 0), QPointF(10, 0), line_item, text_item)
        scene.addItem(m)
        handle = SimpleNamespace(is_start=False, parent_measurement=m, pos=lambda: QPointF(20, 10))
        handled, result = process_measurement_handle_item_change(
            handle, QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(20, 10)
        )
        assert handled is False
        assert m.end_point == QPointF(20, 10)


# ---------------------------------------------------------------------------
# resolve_measurement_group_position_change
# ---------------------------------------------------------------------------

class TestResolveGroupPosition:
    def test_updating_handles_allows(self):
        m = SimpleNamespace(_updating_handles=True, _handle_drag_in_progress=False)
        proposed = QPointF(9, 9)
        assert resolve_measurement_group_position_change(m, proposed) == proposed

    def test_handle_drag_blocks(self):
        m = SimpleNamespace(
            _updating_handles=False,
            _handle_drag_in_progress=True,
            pos=lambda: QPointF(1, 2),
        )
        assert resolve_measurement_group_position_change(m, QPointF(9, 9)) == QPointF(1, 2)

    def test_neither_allows(self):
        m = SimpleNamespace(_updating_handles=False, _handle_drag_in_progress=False)
        proposed = QPointF(9, 9)
        assert resolve_measurement_group_position_change(m, proposed) == proposed

    def test_updating_handles_debug(self):
        from utils import debug_flags
        old = debug_flags.DEBUG_MEASUREMENT_DRAG
        try:
            debug_flags.DEBUG_MEASUREMENT_DRAG = True
            m = SimpleNamespace(_updating_handles=True, _handle_drag_in_progress=False)
            result = resolve_measurement_group_position_change(m, QPointF(5, 5))
            assert result == QPointF(5, 5)
        finally:
            debug_flags.DEBUG_MEASUREMENT_DRAG = old

    def test_handle_drag_debug(self):
        from utils import debug_flags
        old = debug_flags.DEBUG_MEASUREMENT_DRAG
        try:
            debug_flags.DEBUG_MEASUREMENT_DRAG = True
            m = SimpleNamespace(
                _updating_handles=False,
                _handle_drag_in_progress=True,
                pos=lambda: QPointF(1, 2),
            )
            result = resolve_measurement_group_position_change(m, QPointF(5, 5))
            assert result == QPointF(1, 2)
        finally:
            debug_flags.DEBUG_MEASUREMENT_DRAG = old


# ---------------------------------------------------------------------------
# _viewport_to_scene_scale
# ---------------------------------------------------------------------------

class TestViewportToSceneScale:
    def test_no_scene(self):
        m = SimpleNamespace(scene=lambda: None)
        assert _viewport_to_scene_scale(m) == 1.0

    def test_no_views(self):
        scene = MagicMock()
        scene.views.return_value = []
        m = SimpleNamespace(scene=lambda: scene)
        assert _viewport_to_scene_scale(m) == 1.0

    def test_with_view(self):
        view = MagicMock()
        view.current_zoom = 2.0
        scene = MagicMock()
        scene.views.return_value = [view]
        m = SimpleNamespace(scene=lambda: scene)
        assert _viewport_to_scene_scale(m) == 0.5


# ---------------------------------------------------------------------------
# sync_measurement_geometry_after_external_move
# ---------------------------------------------------------------------------

class TestSyncGeometryAfterExternalMove:
    @pytest.fixture(autouse=True)
    def _setup(self, qapp):
        from tools.measurement_items import MeasurementItem
        self._scene = QGraphicsScene()
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        self.item = MeasurementItem(
            QPointF(0, 0), QPointF(10, 0), line_item, text_item,
        )
        self._scene.addItem(self.item)
        view = MagicMock()
        view.current_zoom = 1.0
        self._views = [view]
        self.item._scene_ref = self._scene  # keep a reference
        # Patch scene().views() to return our list
        self.item.scene = lambda: self._scene
        self._scene.views = lambda: self._views

    def test_same_position_noop(self):
        self.item.setPos(0, 0)
        self.item.start_point = QPointF(0, 0)
        self.item.end_point = QPointF(10, 0)
        sync_measurement_geometry_after_external_move(self.item)

    def test_different_position_syncs(self):
        self.item.start_point = QPointF(0, 0)
        self.item.end_point = QPointF(10, 0)
        self.item.setPos(5, 5)
        sync_measurement_geometry_after_external_move(self.item)
        assert self.item.start_point == QPointF(5, 5)
        assert self.item.end_point == QPointF(15, 5)

    def test_no_scene(self):
        self.item.start_point = QPointF(0, 0)
        self.item.end_point = QPointF(10, 0)
        self.item.setPos(5, 5)
        self.item.scene = lambda: None
        sync_measurement_geometry_after_external_move(self.item)
        assert self.item.start_point == QPointF(5, 5)

    def test_no_view(self):
        self._views.clear()
        self.item.start_point = QPointF(0, 0)
        self.item.end_point = QPointF(10, 0)
        self.item.setPos(5, 5)
        sync_measurement_geometry_after_external_move(self.item)
        assert self.item.start_point == QPointF(5, 5)


# ---------------------------------------------------------------------------
# apply_measurement_group_position_has_changed
# ---------------------------------------------------------------------------

class TestApplyGroupPositionHasChanged:
    @pytest.fixture(autouse=True)
    def _setup(self, qapp):
        from tools.measurement_items import MeasurementItem
        self._scene = QGraphicsScene()
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        self.item = MeasurementItem(
            QPointF(0, 0), QPointF(10, 0), line_item, text_item,
        )
        self._scene.addItem(self.item)
        view = MagicMock()
        view.current_zoom = 1.0
        self._views = [view]
        self.item.scene = lambda: self._scene
        self._scene.views = lambda: self._views

    def test_last_drag_pos_not_none(self):
        self.item._last_drag_pos = QPointF(5, 5)
        assert apply_measurement_group_position_has_changed(self.item) is True

    def test_with_callback(self):
        self.item._last_drag_pos = None
        self.item.on_moved_callback = MagicMock()
        self.item.setPos(5, 5)
        self.item.start_point = QPointF(0, 0)
        self.item.end_point = QPointF(10, 0)
        apply_measurement_group_position_has_changed(self.item)
        assert self.item.on_moved_callback.call_count >= 1

    def test_with_callback_raises(self):
        self.item._last_drag_pos = None
        self.item.on_moved_callback = MagicMock(side_effect=RuntimeError("boom"))
        self.item.setPos(5, 5)
        self.item.start_point = QPointF(0, 0)
        self.item.end_point = QPointF(10, 0)
        apply_measurement_group_position_has_changed(self.item)

    def test_updating_handles(self):
        self.item._last_drag_pos = None
        self.item.on_moved_callback = None
        self.item._updating_handles = True
        result = apply_measurement_group_position_has_changed(self.item)
        assert result is True

    def test_handle_drag_in_progress(self):
        self.item._last_drag_pos = None
        self.item.on_moved_callback = None
        self.item._updating_handles = False
        self.item._handle_drag_in_progress = True
        result = apply_measurement_group_position_has_changed(self.item)
        assert result is True


# ---------------------------------------------------------------------------
# apply_measurement_group_selection_changed
# ---------------------------------------------------------------------------

class TestApplyGroupSelectionChanged:
    @pytest.fixture(autouse=True)
    def _setup(self, qapp):
        from tools.measurement_items import MeasurementItem
        self.scene = QGraphicsScene()
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        self.item = MeasurementItem(
            QPointF(0, 0), QPointF(10, 0), line_item, text_item,
        )
        self.scene.addItem(self.item)

    def test_selected(self):
        result = apply_measurement_group_selection_changed(self.item, True)
        assert result is False

    def test_deselected(self):
        result = apply_measurement_group_selection_changed(self.item, False)
        assert result is False

    def test_selected_with_drag_in_progress(self):
        self.item._handle_drag_in_progress = True
        result = apply_measurement_group_selection_changed(self.item, True)
        assert result is True

    def test_deselected_clears_flags(self):
        self.item._handle_drag_in_progress = True
        self.item._dragging_handle = MagicMock()
        result = apply_measurement_group_selection_changed(self.item, False)
        assert result is False
        assert self.item._handle_drag_in_progress is False
        assert self.item._dragging_handle is None


# ---------------------------------------------------------------------------
# process_measurement_group_item_change
# ---------------------------------------------------------------------------

class TestProcessGroupItemChange:
    def test_item_position_change(self):
        m = SimpleNamespace(_updating_handles=False, _handle_drag_in_progress=False)
        handled, result = process_measurement_group_item_change(
            m, QGraphicsItem.GraphicsItemChange.ItemPositionChange, QPointF(5, 5)
        )
        assert handled is True
        assert result == QPointF(5, 5)

    def test_item_position_has_changed(self):
        from tools.measurement_items import MeasurementItem
        scene = QGraphicsScene()
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        m = MeasurementItem(QPointF(0, 0), QPointF(10, 0), line_item, text_item)
        scene.addItem(m)
        view = MagicMock()
        view.current_zoom = 1.0
        views = [view]
        m.scene = lambda: scene
        scene.views = lambda: views
        m.setPos(5, 5)
        m.start_point = QPointF(0, 0)
        m.end_point = QPointF(10, 0)
        m._last_drag_pos = None
        m.on_moved_callback = None
        m._updating_handles = False
        m._handle_drag_in_progress = False
        handled, result = process_measurement_group_item_change(
            m, QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged, QPointF(5, 5)
        )
        assert handled is False

    def test_item_selected_has_changed(self):
        from tools.measurement_items import MeasurementItem
        scene = QGraphicsScene()
        line_item = QGraphicsLineItem(QLineF(0, 0, 10, 0))
        text_item = QGraphicsTextItem("test")
        m = MeasurementItem(QPointF(0, 0), QPointF(10, 0), line_item, text_item)
        scene.addItem(m)
        handled, result = process_measurement_group_item_change(
            m, QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged, True
        )
        assert handled is False

    def test_item_scene_has_changed_with_value(self):
        m = MagicMock()
        m.update_text_offset_for_zoom = MagicMock()
        handled, result = process_measurement_group_item_change(
            m, QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged, object()
        )
        assert handled is True
        m.update_text_offset_for_zoom.assert_called_once()

    def test_item_scene_has_changed_none(self):
        m = MagicMock()
        handled, result = process_measurement_group_item_change(
            m, QGraphicsItem.GraphicsItemChange.ItemSceneHasChanged, None
        )
        assert handled is True
        m.update_text_offset_for_zoom.assert_not_called()

    def test_other_change_falls_through(self):
        val = object()
        handled, result = process_measurement_group_item_change(
            MagicMock(), QGraphicsItem.GraphicsItemChange.ItemZValueChange, val
        )
        assert handled is False
        assert result is val
