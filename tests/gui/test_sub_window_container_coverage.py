"""Focused synthetic tests for gui.sub_window_container – untested branches and signals."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QByteArray, QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QDragEnterEvent, QDragMoveEvent, QMouseEvent

from core.mpr_view_drag import MPR_VIEW_MIME, encode_view_drag

_ORIGIN = "AbCdEfGhIjKlMnOpQr_-12"
from gui.image_viewer import ImageViewer
from gui.sub_window_container import (
    SubWindowContainer,
    _parse_series_drop_mime,
    _SliceSyncGroupBar,
)

# ---------------------------------------------------------------------------
# _parse_series_drop_mime
# ---------------------------------------------------------------------------

class TestParseSeriesDropMime:
    def test_dv3_assign_valid(self):
        uid, idx, study = _parse_series_drop_mime("dv3_assign\tSTUDY1\tSER1\t7")
        assert uid == "SER1"
        assert idx == 7
        assert study == "STUDY1"

    def test_dv3_assign_too_few_parts(self):
        uid, idx, study = _parse_series_drop_mime("dv3_assign\tSTUDY1\tSER1")
        assert uid == ""
        assert idx == 0
        assert study == ""

    def test_dv3_assign_bad_slice_index(self):
        uid, idx, study = _parse_series_drop_mime("dv3_assign\tSTUDY1\tSER1\tnotanum")
        assert uid == ""
        assert idx == 0
        assert study == ""

    def test_series_uid_prefix_only(self):
        uid, idx, study = _parse_series_drop_mime("series_uid:")
        assert uid == ""
        assert idx == 0
        assert study == ""

    def test_series_uid_with_slice(self):
        uid, idx, study = _parse_series_drop_mime("series_uid:UID123:42")
        assert uid == "UID123"
        assert idx == 42
        assert study == ""

    def test_series_uid_bad_slice_falls_back(self):
        uid, idx, study = _parse_series_drop_mime("series_uid:UID123:notnum")
        assert uid == "UID123:notnum"
        assert idx == 0
        assert study == ""

    def test_series_uid_no_slice(self):
        uid, idx, study = _parse_series_drop_mime("series_uid:MYUID")
        assert uid == "MYUID"
        assert idx == 0
        assert study == ""

    def test_unrecognized_text(self):
        uid, idx, study = _parse_series_drop_mime("something_else")
        assert uid == ""
        assert idx == 0
        assert study == ""


# ---------------------------------------------------------------------------
# SubWindowContainer basic construction and properties
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestSubWindowConstruction:
    def test_init_sets_focus_state(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        assert c.is_focused is False
        assert c.assigned_series_uid is None
        assert c.assigned_slice_index == 0

    def test_size_policy_expanding(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        from PySide6.QtWidgets import QSizePolicy
        assert c.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding
        assert c.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding

    def test_accept_drops_enabled(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        assert c.acceptDrops() is True


# ---------------------------------------------------------------------------
# set_focused / focus_changed signal
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestFocusManagement:
    def test_set_focused_true_emits_signal(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        received = []
        c.focus_changed.connect(lambda v: received.append(v))
        c.set_focused(True)
        assert c.is_focused is True
        assert received == [True]

    def test_set_focused_false_emits_signal(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_focused(True)
        received = []
        c.focus_changed.connect(lambda v: received.append(v))
        c.set_focused(False)
        assert c.is_focused is False
        assert received == [False]

    def test_set_focused_same_value_no_signal(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_focused(False)
        received = []
        c.focus_changed.connect(lambda v: received.append(v))
        c.set_focused(False)
        assert received == []

    def test_set_suppress_focus_border_for_export_toggles(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_focused(True)
        c.set_suppress_focus_border_for_export(True)
        assert c._suppress_focus_border_for_export is True
        c.set_suppress_focus_border_for_export(True)  # same value, no-op
        assert c._suppress_focus_border_for_export is True
        c.set_suppress_focus_border_for_export(False)
        assert c._suppress_focus_border_for_export is False


# ---------------------------------------------------------------------------
# set_assigned_series / get_assigned_series
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestAssignedSeries:
    def test_set_and_get(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_assigned_series("uid_abc", 5)
        assert c.get_assigned_series() == ("uid_abc", 5)

    def test_clear_series(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_assigned_series("uid_abc", 5)
        c.set_assigned_series(None, 0)
        assert c.get_assigned_series() == (None, 0)


# ---------------------------------------------------------------------------
# Slice-sync group indicator
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestSliceSyncIndicator:
    def test_show_indicator_shows_bar(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.show()
        c.resize(200, 200)
        c.set_slice_sync_group_indicator(QColor("red"))
        assert c._pane_title_bar.isVisibleTo(c) is True

    def test_hide_indicator_hides_bar(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.show()
        c.resize(200, 200)
        c.set_slice_sync_group_indicator(QColor("red"))
        c.set_slice_sync_group_indicator(None)
        assert c._pane_title_bar.isVisibleTo(c) is False

    def test_set_strip_height_clamps(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_slice_sync_strip_height(100)
        assert c._pane_title_bar.maximumHeight() <= 16
        c.set_slice_sync_strip_height(0)
        assert c._pane_title_bar.minimumHeight() >= 2

    def test_indicator_sets_tooltip(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.show()
        c.resize(200, 200)
        c.set_slice_sync_group_indicator(QColor("green"))
        assert "linked group" in c._sync_group_bar.toolTip()

    def test_indicator_none_clears_tooltip(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.show()
        c.resize(200, 200)
        c.set_slice_sync_group_indicator(QColor("green"))
        c.set_slice_sync_group_indicator(None)
        assert c._sync_group_bar.toolTip() == ""


# ---------------------------------------------------------------------------
# _mime_accepts_series_or_mpr
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestMimeAccepts:
    def _make_mime(self, text=None, mime_type=None):
        from PySide6.QtCore import QMimeData
        md = QMimeData()
        if text is not None:
            md.setText(text)
        if mime_type is not None:
            md.setData(mime_type, QByteArray(b"0"))
        return md

    def test_accepts_mpr_mime(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        assert c._mime_accepts_series_or_mpr(self._make_mime(mime_type=MPR_VIEW_MIME)) is True

    def test_accepts_series_uid_prefix(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        assert c._mime_accepts_series_or_mpr(self._make_mime(text="series_uid:X")) is True

    def test_accepts_dv3_assign(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        assert c._mime_accepts_series_or_mpr(self._make_mime(text="dv3_assign\tS\tU\t0")) is True

    def test_rejects_plain_text(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        assert c._mime_accepts_series_or_mpr(self._make_mime(text="hello")) is False

    def test_rejects_empty_mime(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        from PySide6.QtCore import QMimeData
        assert c._mime_accepts_series_or_mpr(QMimeData()) is False


# ---------------------------------------------------------------------------
# dragEnterEvent / dragMoveEvent
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestDragEvents:
    def _make_drag_event(self, mime_data, event_type=QEvent.Type.DragEnter):
        pos = QPoint(10, 10)
        return QDragEnterEvent(
            pos,
            Qt.DropAction.MoveAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ) if event_type == QEvent.Type.DragEnter else QDragMoveEvent(
            pos,
            Qt.DropAction.MoveAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def test_drag_enter_accepts_series(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        from PySide6.QtCore import QMimeData
        md = QMimeData()
        md.setText("series_uid:U1")
        ev = self._make_drag_event(md)
        c.dragEnterEvent(ev)
        assert ev.isAccepted()

    def test_drag_enter_rejects_unknown(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        from PySide6.QtCore import QMimeData
        md = QMimeData()
        md.setText("random_text")
        ev = self._make_drag_event(md)
        c.dragEnterEvent(ev)
        assert not ev.isAccepted()

    def test_drag_move_accepts_series(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        from PySide6.QtCore import QMimeData
        md = QMimeData()
        md.setText("series_uid:U1")
        pos = QPoint(10, 10)
        ev = QDragMoveEvent(pos, Qt.DropAction.MoveAction, md,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        c.dragMoveEvent(ev)
        assert ev.isAccepted()

    def test_drag_move_rejects_unknown(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        from PySide6.QtCore import QMimeData
        md = QMimeData()
        md.setText("nope")
        pos = QPoint(10, 10)
        ev = QDragMoveEvent(pos, Qt.DropAction.MoveAction, md,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        c.dragMoveEvent(ev)
        assert not ev.isAccepted()

    def test_drag_enter_accepts_mpr(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        from PySide6.QtCore import QMimeData
        md = QMimeData()
        md.setData(MPR_VIEW_MIME, QByteArray(b"0"))
        ev = self._make_drag_event(md)
        c.dragEnterEvent(ev)
        assert ev.isAccepted()


# ---------------------------------------------------------------------------
# dropEvent – use mock events to avoid QDropEvent segfault
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestDropEvent:
    def _mock_drop(self, text=None, mime_type=None, mime_data_obj=None):
        from PySide6.QtCore import QMimeData
        md = mime_data_obj or QMimeData()
        if text is not None:
            md.setText(text)
        if mime_type is not None:
            md.setData(mime_type, QByteArray(b"1"))
        ev = MagicMock()
        ev.mimeData.return_value = md
        ev.acceptProposedAction = MagicMock()
        ev.ignore = MagicMock()
        return ev

    def test_drop_series_uid_emits_assign(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        received = []
        c.assign_series_requested.connect(lambda uid, idx, study: received.append((uid, idx, study)))
        ev = self._mock_drop(text="series_uid:MYUID:3")
        c.dropEvent(ev)
        assert received == [("MYUID", 3, "")]
        ev.acceptProposedAction.assert_called_once()

    def test_drop_dv3_assign_emits(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        received = []
        c.assign_series_requested.connect(lambda uid, idx, study: received.append((uid, idx, study)))
        ev = self._mock_drop(text="dv3_assign\tSTUDY1\tSER1\t10")
        c.dropEvent(ev)
        assert received == [("SER1", 10, "STUDY1")]

    def test_drop_unknown_text_ignored(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        received = []
        c.assign_series_requested.connect(lambda uid, idx, study: received.append((uid, idx, study)))
        ev = self._mock_drop(text="something_else")
        c.dropEvent(ev)
        assert received == []
        ev.ignore.assert_called()

    def test_drop_empty_text_ignored(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        ev = self._mock_drop(text="series_uid:")
        c.dropEvent(ev)
        ev.ignore.assert_called()

    def test_drop_no_text_ignored(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        ev = self._mock_drop()
        c.dropEvent(ev)
        ev.ignore.assert_called()

    def _mpr_drop(self, payload: bytes):
        from PySide6.QtCore import QMimeData

        md = QMimeData()
        md.setData(MPR_VIEW_MIME, QByteArray(payload))
        ev = MagicMock()
        ev.mimeData.return_value = md
        return ev

    def test_drop_mpr_view_emits_stable_view_id_operation_and_target(self, qapp):
        viewer = ImageViewer()
        viewer.subwindow_index = 2
        c = SubWindowContainer(viewer)
        received = []
        c.mpr_view_drop_requested.connect(lambda v, op, o, t: received.append((v, op, o, t)))
        ev = self._mpr_drop(encode_view_drag(17, _ORIGIN))
        c.dropEvent(ev)
        assert received == [(17, "move", _ORIGIN, 2)]
        ev.acceptProposedAction.assert_called_once()

    def test_drop_mpr_view_no_subwindow_index_ignored(self, qapp):
        viewer = ImageViewer()
        viewer.subwindow_index = None
        c = SubWindowContainer(viewer)
        received = []
        c.mpr_view_drop_requested.connect(lambda v, op, o, t: received.append((v, op, o, t)))
        ev = self._mpr_drop(encode_view_drag(17, _ORIGIN))
        c.dropEvent(ev)
        assert received == []
        ev.ignore.assert_called()

    @pytest.mark.parametrize(
        "payload",
        [
            b"1",  # the old bare-integer pane/detached encoding is not a payload
            b"-1",
            b"not_a_number",
            b"",
            b'{"v":2,"op":"move","view":1}',  # foreign schema version
            b'{"v":1,"op":"swap","view":1}',  # unknown operation
            b'{"v":1,"op":"move","view":0}',
            b'{"v":1,"op":"move","view":true}',
            b'{"v":1,"op":"move","view":1,"pane":0}',  # extra key (pane ambiguity)
            b'{"v":1,"op":"move","view":1}',  # missing origin
            b'{"v":1,"op":"move","view":1,"origin":"short"}',  # malformed origin
            b"x" * 4096,  # oversized
        ],
    )
    def test_drop_malformed_foreign_or_oversized_mpr_payload_is_a_no_op(self, qapp, payload):
        viewer = ImageViewer()
        viewer.subwindow_index = 2
        c = SubWindowContainer(viewer)
        received = []
        c.mpr_view_drop_requested.connect(lambda v, op, o, t: received.append((v, op, o, t)))
        ev = self._mpr_drop(payload)
        c.dropEvent(ev)
        assert received == []
        ev.ignore.assert_called()
        ev.acceptProposedAction.assert_not_called()

    def test_oversized_payload_is_rejected_before_it_is_copied_or_parsed(self, qapp):
        from unittest.mock import patch

        from core.mpr_view_drag import MAX_PAYLOAD_BYTES

        viewer = ImageViewer()
        viewer.subwindow_index = 1
        c = SubWindowContainer(viewer)
        ev = self._mpr_drop(b"x" * (MAX_PAYLOAD_BYTES + 1))
        with patch("gui.sub_window_container.decode_view_drag") as decode:
            c.dropEvent(ev)
        decode.assert_not_called()
        ev.ignore.assert_called()

    def test_legacy_bare_integer_mime_is_not_accepted(self, qapp):
        from PySide6.QtCore import QMimeData

        md = QMimeData()
        md.setData("application/x-dv3-mpr-assign", QByteArray(b"1"))
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        assert c._mime_accepts_series_or_mpr(md) is False


# ---------------------------------------------------------------------------
# mousePressEvent
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestMousePressEvent:
    def _left_press(self, widget):
        local = QPointF(10.0, 10.0)
        g = widget.mapToGlobal(QPoint(int(local.x()), int(local.y())))
        return QMouseEvent(
            QEvent.Type.MouseButtonPress,
            local,
            widget.mapToScene(QPoint(int(local.x()), int(local.y()))) if hasattr(widget, 'mapToScene') else local,
            g,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def _right_press(self, widget):
        local = QPointF(10.0, 10.0)
        g = widget.mapToGlobal(QPoint(int(local.x()), int(local.y())))
        return QMouseEvent(
            QEvent.Type.MouseButtonPress,
            local,
            widget.mapToScene(QPoint(int(local.x()), int(local.y()))) if hasattr(widget, 'mapToScene') else local,
            g,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def test_unfocused_left_click_focuses_and_accepts(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        ev = self._left_press(c)
        c.mousePressEvent(ev)
        assert c.is_focused is True
        assert ev.isAccepted()

    def test_focused_left_click_propagates(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_focused(True)
        ev = self._left_press(c)
        c.mousePressEvent(ev)
        assert c.is_focused is True

    def test_right_click_on_unfocused_focuses_and_emits_context_menu(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        received = []
        c.context_menu_requested.connect(lambda: received.append(True))
        ev = self._right_press(c)
        c.mousePressEvent(ev)
        assert c.is_focused is True
        assert received == [True]

    def test_right_click_on_focused_emits_context_menu(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_focused(True)
        received = []
        c.context_menu_requested.connect(lambda: received.append(True))
        ev = self._right_press(c)
        c.mousePressEvent(ev)
        assert received == [True]


# ---------------------------------------------------------------------------
# eventFilter – double-click on background
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestEventFilterDoubleClick:
    def _dblclick(self, widget):
        local = QPointF(20.0, 20.0)
        g = widget.mapToGlobal(QPoint(int(local.x()), int(local.y())))
        return QMouseEvent(
            QEvent.Type.MouseButtonDblClick,
            local,
            widget.mapToScene(QPoint(int(local.x()), int(local.y()))) if hasattr(widget, 'mapToScene') else local,
            g,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )

    def test_dblclick_on_empty_scene_emits_expand(self, qapp):
        viewer = ImageViewer()
        viewer.resize(200, 200)
        c = SubWindowContainer(viewer)
        received = []
        c.expand_to_1x1_requested.connect(lambda: received.append(True))
        ev = self._dblclick(viewer.viewport())
        result = c.eventFilter(viewer.viewport(), ev)
        assert result is True
        assert received == [True]
        assert c.is_focused is True


# ---------------------------------------------------------------------------
# _SliceSyncGroupBar painting
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestSliceSyncGroupBar:
    def test_bar_without_fill_paints_nothing(self, qapp):
        bar = _SliceSyncGroupBar()
        bar._fill = None
        bar.show()
        bar.resize(100, 5)
        bar.repaint()

    def test_bar_with_fill_paints(self, qapp):
        bar = _SliceSyncGroupBar()
        bar.set_fill_color(QColor("blue"))
        bar.show()
        bar.resize(100, 5)
        bar.repaint()

    def test_set_fill_color_updates(self, qapp):
        bar = _SliceSyncGroupBar()
        bar.set_fill_color(QColor("red"))
        assert bar._fill == QColor("red")
        bar.set_fill_color(None)
        assert bar._fill is None


# ---------------------------------------------------------------------------
# _is_double_click_on_background_or_image – with None scene
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestDoubleClickHelpers:
    def test_returns_true_when_event_raises_exception(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        bad_event = MagicMock()
        bad_event.position.side_effect = RuntimeError("boom")
        assert c._is_double_click_on_background_or_image(bad_event) is True

    def test_returns_false_for_rect_item_on_scene(self, qapp):
        from PySide6.QtWidgets import QGraphicsRectItem
        viewer = ImageViewer()
        viewer.resize(200, 200)
        c = SubWindowContainer(viewer)
        scene = viewer.scene
        rect_item = QGraphicsRectItem(0, 0, 50, 50)
        scene.addItem(rect_item)
        viewer.fitInView(scene.sceneRect())
        local = QPointF(25.0, 25.0)
        g = viewer.mapToGlobal(QPoint(int(local.x()), int(local.y())))
        ev = QMouseEvent(
            QEvent.Type.MouseButtonDblClick,
            local,
            viewer.mapToScene(QPoint(int(local.x()), int(local.y()))),
            g,
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        assert c._is_double_click_on_background_or_image(ev) is False
        scene.removeItem(rect_item)


# ---------------------------------------------------------------------------
# Border style updates
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestBorderStyle:
    def test_focused_border_differs_from_unfocused(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_focused(True)
        focused_ss = c.styleSheet()
        c.set_focused(False)
        unfocused_ss = c.styleSheet()
        assert focused_ss != unfocused_ss

    def test_export_suppress_uses_normal_border(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_focused(True)
        c.set_suppress_focus_border_for_export(True)
        ss = c.styleSheet()
        assert "1px solid" in ss  # normal_border_width = 1


# ---------------------------------------------------------------------------
# paintEvent
# ---------------------------------------------------------------------------

@pytest.mark.qt
class TestPaintEvent:
    def test_focused_paint_event_runs(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.set_focused(True)
        c.resize(100, 100)
        c.show()
        c.repaint()

    def test_unfocused_paint_event_runs(self, qapp):
        viewer = ImageViewer()
        c = SubWindowContainer(viewer)
        c.resize(100, 100)
        c.show()
        c.repaint()
