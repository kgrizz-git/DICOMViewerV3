"""Tests for src/gui/mpr_thumbnail_widget.py — round 4 coverage.

Focuses on constructor branches, update_preview paths, badge/slice-count
state logic, context-menu signal wiring, and guarded mouse/drag behaviour.
Uses the session qapp fixture; no paintEvent rendering is required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent

from core.mpr_view_drag import MPR_VIEW_MIME, OP_MOVE, decode_view_drag
from gui.mpr_thumbnail_widget import MprThumbnailWidget

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ORIGIN = "AbCdEfGhIjKlMnOpQr_-12"


def _make_widget(pane_index: int | None = 0, view_id: int = 7) -> MprThumbnailWidget:
    """Tile for view *view_id*; *pane_index* is the window showing it (None = detached)."""
    widget = MprThumbnailWidget(view_id, pane_index)
    widget.set_origin(_ORIGIN)
    return widget


def _make_array(
    shape: tuple[int, int] = (16, 16),
    value: float = 0.5,
    dtype: type = np.float32,
) -> np.ndarray:
    return np.full(shape, value, dtype=dtype)


def _mouse_press(pos: QPoint = QPoint(5, 5)) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        pos,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _mouse_move(
    pos: QPoint,
    buttons: Qt.MouseButton = Qt.MouseButton.LeftButton,
) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseMove,
        pos,
        pos,
        Qt.MouseButton.NoButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def _mouse_release(pos: QPoint = QPoint(5, 5)) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        pos,
        pos,
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


class TestConstructor:
    @pytest.mark.qt
    def test_identity_is_the_view_id_and_the_pane_is_separate(self, qapp) -> None:
        w = _make_widget(2, view_id=11)
        assert (w.view_id, w.pane_index) == (11, 2)
        assert w._dot_color == "#FF9800"  # SUBWINDOW_DOT_COLORS[2]

    @pytest.mark.qt
    def test_zero_pane(self, qapp) -> None:
        w = _make_widget(0)
        assert w.pane_index == 0
        assert w._dot_color == "#2196F3"

    @pytest.mark.qt
    def test_detached_view_has_no_pane_and_grey_dot(self, qapp) -> None:
        w = _make_widget(None, view_id=4)
        assert (w.view_id, w.pane_index) == (4, None)
        assert w._dot_color == "#9E9E9E"

    @pytest.mark.qt
    def test_out_of_range_pane_falls_back_to_default_blue(self, qapp) -> None:
        w = _make_widget(99)
        assert w._dot_color == "#2196F3"  # default from dict.get

    @pytest.mark.qt
    def test_caption_sets_tag_and_tooltip(self, qapp) -> None:
        w = _make_widget(1)
        w.set_caption("S2.1", "MPR Axial\nSession 2")
        assert w._tag == "S2.1" and w.toolTip() == "MPR Axial\nSession 2"

    @pytest.mark.qt
    def test_initial_state(self, qapp) -> None:
        w = _make_widget(0)
        assert w._preview_pixmap is None
        assert w._drag_start_pos is None
        assert w._slice_count is None
        assert w._show_slice_frame_count_badge is True
        assert w._img_bytes_ref is None


# ---------------------------------------------------------------------------
# update_preview
# ---------------------------------------------------------------------------


class TestUpdatePreview:
    @pytest.mark.qt
    def test_none_clears_pixmap(self, qapp) -> None:
        w = _make_widget()
        w.update_preview(_make_array())  # first set
        assert w._preview_pixmap is not None
        w.update_preview(None)
        assert w._preview_pixmap is None

    @pytest.mark.qt
    def test_empty_array_clears_pixmap(self, qapp) -> None:
        w = _make_widget()
        w.update_preview(np.array([], dtype=np.float32))
        assert w._preview_pixmap is None

    @pytest.mark.qt
    def test_auto_scale_normal_array(self, qapp) -> None:
        w = _make_widget()
        arr = np.linspace(0.0, 1.0, 100, dtype=np.float32).reshape(10, 10)
        w.update_preview(arr)
        assert w._preview_pixmap is not None
        assert not w._preview_pixmap.isNull()

    @pytest.mark.qt
    def test_windowed_rendering(self, qapp) -> None:
        w = _make_widget()
        arr = _make_array()
        w.update_preview(arr, window_center=0.5, window_width=0.5)
        assert w._preview_pixmap is not None

    @pytest.mark.qt
    def test_constant_array_produces_zeros(self, qapp) -> None:
        w = _make_widget()
        arr = np.ones((8, 8), dtype=np.float32)
        w.update_preview(arr)
        # span == 0 branch → zeros_like → valid pixmap
        assert w._preview_pixmap is not None

    @pytest.mark.qt
    def test_non_float_array_is_converted(self, qapp) -> None:
        w = _make_widget()
        arr = np.zeros((8, 8), dtype=np.int32)
        arr[2, 2] = 100
        w.update_preview(arr)
        assert w._preview_pixmap is not None

    @pytest.mark.qt
    def test_preview_bytes_reference_kept_alive(self, qapp) -> None:
        w = _make_widget()
        w.update_preview(_make_array())
        assert w._img_bytes_ref is not None
        assert isinstance(w._img_bytes_ref, bytes)

    @pytest.mark.qt
    def test_exception_during_conversion_sets_none(self, qapp) -> None:
        w = _make_widget()
        with patch("gui.mpr_thumbnail_widget.Image.fromarray", side_effect=RuntimeError("boom")):
            w.update_preview(_make_array())
        assert w._preview_pixmap is None

    @pytest.mark.qt
    def test_window_width_zero_falls_to_auto_scale(self, qapp) -> None:
        w = _make_widget()
        arr = np.linspace(0.0, 1.0, 64, dtype=np.float32).reshape(8, 8)
        w.update_preview(arr, window_center=0.5, window_width=0.0)
        assert w._preview_pixmap is not None


# ---------------------------------------------------------------------------
# set_slice_count / _slice_count_badge_text
# ---------------------------------------------------------------------------


class TestSliceCount:
    @pytest.mark.qt
    def test_set_valid_count(self, qapp) -> None:
        w = _make_widget()
        w.set_slice_count(7)
        assert w._slice_count == 7

    @pytest.mark.qt
    def test_set_none_clears(self, qapp) -> None:
        w = _make_widget()
        w.set_slice_count(5)
        w.set_slice_count(None)
        assert w._slice_count is None

    @pytest.mark.qt
    def test_zero_clears(self, qapp) -> None:
        w = _make_widget()
        w.set_slice_count(0)
        assert w._slice_count is None

    @pytest.mark.qt
    def test_negative_clears(self, qapp) -> None:
        w = _make_widget()
        w.set_slice_count(-3)
        assert w._slice_count is None

    @pytest.mark.qt
    def test_non_int_value_clears(self, qapp) -> None:
        w = _make_widget()
        w.set_slice_count("abc")
        assert w._slice_count is None

    @pytest.mark.qt
    def test_float_value_truncated_to_int(self, qapp) -> None:
        w = _make_widget()
        w.set_slice_count(4.9)
        assert w._slice_count == 4

    @pytest.mark.qt
    def test_badge_text_show_true(self, qapp) -> None:
        w = _make_widget()
        w.set_show_slice_frame_count_badge(True)
        w.set_slice_count(3)
        assert w._slice_count_badge_text() == "3"

    @pytest.mark.qt
    def test_badge_text_show_false_single_slice_hidden(self, qapp) -> None:
        w = _make_widget()
        w.set_show_slice_frame_count_badge(False)
        w.set_slice_count(1)
        assert w._slice_count_badge_text() == ""

    @pytest.mark.qt
    def test_badge_text_show_false_multi_slice_shown(self, qapp) -> None:
        w = _make_widget()
        w.set_show_slice_frame_count_badge(False)
        w.set_slice_count(4)
        assert w._slice_count_badge_text() == "4"

    @pytest.mark.qt
    def test_badge_text_none_slice_count(self, qapp) -> None:
        w = _make_widget()
        assert w._slice_count_badge_text() == ""

    @pytest.mark.qt
    def test_badge_text_zero_slice_count(self, qapp) -> None:
        w = _make_widget()
        w._slice_count = 0
        assert w._slice_count_badge_text() == ""


# ---------------------------------------------------------------------------
# set_dot_color
# ---------------------------------------------------------------------------


class TestSetDotColor:
    @pytest.mark.qt
    def test_updates_color(self, qapp) -> None:
        w = _make_widget()
        w.set_dot_color("#FF0000")
        assert w._dot_color == "#FF0000"


# ---------------------------------------------------------------------------
# Context menu signal wiring
# ---------------------------------------------------------------------------


class TestContextMenu:
    @pytest.mark.qt
    def test_custom_context_menu_policy_set(self, qapp) -> None:
        w = _make_widget()
        assert w.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu


# ---------------------------------------------------------------------------
# Mouse press / release — click path
# ---------------------------------------------------------------------------


class TestMouseClick:
    @pytest.mark.qt
    def test_left_click_emits_clicked(self, qapp) -> None:
        w = _make_widget(2)
        received: list[int] = []
        w.clicked.connect(received.append)

        w.mousePressEvent(_mouse_press(QPoint(5, 5)))
        w.mouseReleaseEvent(_mouse_release(QPoint(5, 5)))
        assert received == [7]  # the view ID, not the pane

    @pytest.mark.qt
    def test_non_left_click_does_not_emit(self, qapp) -> None:
        w = _make_widget(1)
        received: list[int] = []
        w.clicked.connect(received.append)

        right_press = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPoint(5, 5),
            QPoint(5, 5),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        w.mousePressEvent(right_press)
        right_release = QMouseEvent(
            QMouseEvent.Type.MouseButtonRelease,
            QPoint(5, 5),
            QPoint(5, 5),
            Qt.MouseButton.RightButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        w.mouseReleaseEvent(right_release)
        assert received == []

    @pytest.mark.qt
    def test_release_resets_drag_start_pos(self, qapp) -> None:
        w = _make_widget()
        w.mousePressEvent(_mouse_press(QPoint(5, 5)))
        assert w._drag_start_pos is not None
        w.mouseReleaseEvent(_mouse_release(QPoint(5, 5)))
        assert w._drag_start_pos is None

    @pytest.mark.qt
    def test_release_without_prior_press_emits_clicked(self, qapp) -> None:
        w = _make_widget(1)
        w._drag_start_pos = None
        received: list[int] = []
        w.clicked.connect(received.append)
        w.mouseReleaseEvent(_mouse_release(QPoint(5, 5)))
        # dist is 0 (None guard) <= 10, so clicked fires.
        assert received == [7]


# ---------------------------------------------------------------------------
# Drag behaviour
# ---------------------------------------------------------------------------


class TestDragBehaviour:
    @pytest.mark.qt
    def test_small_move_does_not_start_drag(self, qapp) -> None:
        w = _make_widget()
        w.mousePressEvent(_mouse_press(QPoint(5, 5)))
        w.mouseMoveEvent(_mouse_move(QPoint(8, 8)))  # dist=6 < 10
        assert w._drag_start_pos is not None  # drag not started

    @pytest.mark.qt
    def test_large_move_clears_start_pos(self, qapp) -> None:
        w = _make_widget()
        w.mousePressEvent(_mouse_press(QPoint(5, 5)))

        with patch.object(w, "_start_drag") as mock_drag:
            w.mouseMoveEvent(_mouse_move(QPoint(25, 25)))  # dist=40 > 10
            mock_drag.assert_called_once()

    @pytest.mark.qt
    def test_start_drag_clears_pos_and_sets_mime(self, qapp) -> None:
        w = _make_widget(1)
        w._drag_start_pos = QPoint(5, 5)

        drag_instance = MagicMock()
        with patch("gui.mpr_thumbnail_widget.QDrag", return_value=drag_instance):
            w._start_drag()

        assert w._drag_start_pos is None
        drag_instance.setMimeData.assert_called_once()
        mime = drag_instance.setMimeData.call_args[0][0]
        assert mime.hasFormat(MPR_VIEW_MIME)

    @pytest.mark.qt
    def test_start_drag_without_preview_skips_pixmap(self, qapp) -> None:
        w = _make_widget(0)
        w._preview_pixmap = None
        w._drag_start_pos = QPoint(5, 5)

        drag_instance = MagicMock()
        with patch("gui.mpr_thumbnail_widget.QDrag", return_value=drag_instance):
            w._start_drag()

        drag_instance.setPixmap.assert_not_called()

    @pytest.mark.qt
    def test_start_drag_with_preview_sets_scaled_pixmap(self, qapp) -> None:
        w = _make_widget(0)
        w.update_preview(_make_array())
        w._drag_start_pos = QPoint(5, 5)

        drag_instance = MagicMock()
        with patch("gui.mpr_thumbnail_widget.QDrag", return_value=drag_instance):
            w._start_drag()

        drag_instance.setPixmap.assert_called_once()
        drag_instance.setHotSpot.assert_called_once()

    @pytest.mark.qt
    def test_move_without_pressed_button_ignored(self, qapp) -> None:
        w = _make_widget()
        w._drag_start_pos = QPoint(0, 0)
        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPoint(20, 20),
            QPoint(20, 20),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch.object(w, "_start_drag") as mock_drag:
            w.mouseMoveEvent(move_event)
            mock_drag.assert_not_called()

    @pytest.mark.qt
    def test_move_without_start_pos_ignored(self, qapp) -> None:
        w = _make_widget()
        w._drag_start_pos = None
        move_event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPoint(20, 20),
            QPoint(20, 20),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        with patch.object(w, "_start_drag") as mock_drag:
            w.mouseMoveEvent(move_event)
            mock_drag.assert_not_called()

    @pytest.mark.qt
    def test_start_drag_payload_names_the_view_not_the_pane(self, qapp) -> None:
        w = _make_widget(3, view_id=42)
        w._drag_start_pos = QPoint(0, 0)

        captured_mime = None

        def capture_mime(mime):
            nonlocal captured_mime
            captured_mime = mime

        drag_instance = MagicMock()
        drag_instance.setMimeData.side_effect = capture_mime
        with patch("gui.mpr_thumbnail_widget.QDrag", return_value=drag_instance):
            w._start_drag()

        assert captured_mime is not None
        payload = decode_view_drag(bytes(captured_mime.data(MPR_VIEW_MIME)))
        assert payload is not None
        assert (payload.view_id, payload.operation, payload.origin) == (42, OP_MOVE, _ORIGIN)
        assert b"pane" not in bytes(captured_mime.data(MPR_VIEW_MIME))  # no pane index

    @pytest.mark.qt
    @pytest.mark.parametrize("origin", ["", "short", "bad token with spaces!!"])
    def test_a_tile_without_a_valid_origin_starts_no_drag(self, qapp, origin) -> None:
        w = MprThumbnailWidget(7, 0)
        if origin:
            w.set_origin(origin)
        w._drag_start_pos = QPoint(0, 0)
        with patch("gui.mpr_thumbnail_widget.QDrag") as drag_cls:
            w._start_drag()
        drag_cls.assert_not_called()
        assert w._drag_start_pos is None

    @pytest.mark.qt
    def test_start_drag_executes_move_action(self, qapp) -> None:
        w = _make_widget(0)
        w._drag_start_pos = QPoint(0, 0)

        drag_instance = MagicMock()
        with patch("gui.mpr_thumbnail_widget.QDrag", return_value=drag_instance):
            w._start_drag()

        drag_instance.exec.assert_called_once_with(Qt.DropAction.MoveAction)


# ---------------------------------------------------------------------------
# paintEvent (state-triggered rendering)
# ---------------------------------------------------------------------------


class TestPaintEvent:
    @pytest.mark.qt
    def test_paint_no_preview(self, qapp) -> None:
        w = _make_widget(0)
        w.show()
        w.repaint()
        # Widget painted without error; coverage exercises paintEvent lines.

    @pytest.mark.qt
    def test_paint_with_preview(self, qapp) -> None:
        w = _make_widget(0)
        w.update_preview(_make_array())
        w.show()
        w.repaint()

    @pytest.mark.qt
    def test_paint_detached_no_subwindow_digit(self, qapp) -> None:
        w = _make_widget(None)
        w.set_caption("S1", "tip")
        w.update_preview(_make_array())
        w.show()
        w.repaint()

    @pytest.mark.qt
    def test_paint_with_slice_count_badge(self, qapp) -> None:
        w = _make_widget(1)
        w.update_preview(_make_array())
        w.set_slice_count(5)
        w.show()
        w.repaint()

    @pytest.mark.qt
    def test_paint_with_hidden_slice_count_single(self, qapp) -> None:
        w = _make_widget(0)
        w.update_preview(_make_array())
        w.set_show_slice_frame_count_badge(False)
        w.set_slice_count(1)
        w.show()
        w.repaint()

    @pytest.mark.qt
    def test_paint_with_hidden_slice_count_multi(self, qapp) -> None:
        w = _make_widget(0)
        w.update_preview(_make_array())
        w.set_show_slice_frame_count_badge(False)
        w.set_slice_count(3)
        w.show()
        w.repaint()

    @pytest.mark.qt
    def test_paint_high_index_slot_number(self, qapp) -> None:
        w = _make_widget(3)
        w.update_preview(_make_array())
        w.show()
        w.repaint()


# ---------------------------------------------------------------------------
# _show_context_menu
# ---------------------------------------------------------------------------


class TestContextMenu2:
    @pytest.mark.qt
    def test_menu_actions_target_this_exact_view(self, qapp) -> None:
        w = _make_widget(2, view_id=13)
        w.set_caption("S1.1L", "tip", linked=True)
        seen: dict[str, list[int]] = {"dup": [], "linked": [], "unlink": [], "clear": []}
        w.duplicate_requested.connect(seen["dup"].append)
        w.duplicate_linked_requested.connect(seen["linked"].append)
        w.unlink_requested.connect(seen["unlink"].append)
        w.clear_mpr_requested.connect(seen["clear"].append)

        menu = w.build_context_menu()
        actions = menu.actions()
        assert [a.text() for a in actions] == [
            "Duplicate into Window…", "Duplicate Linked into Window…", "Unlink View", "Clear MPR",
        ]
        assert all(a.isEnabled() for a in actions)
        for action in actions:
            action.trigger()

        assert seen == {"dup": [13], "linked": [13], "unlink": [13], "clear": [13]}

    def test_unlink_is_disabled_for_an_unlinked_view_and_never_fires(self, qapp) -> None:
        w = _make_widget(2, view_id=13)
        fired: list[int] = []
        w.unlink_requested.connect(fired.append)
        unlink = next(a for a in w.build_context_menu().actions() if a.text() == "Unlink View")
        assert unlink.isEnabled() is False
        unlink.trigger()
        assert fired == []

    @pytest.mark.qt
    def test_show_context_menu_executes_the_built_menu(self, qapp) -> None:
        w = _make_widget(2)
        with patch.object(w, "build_context_menu") as build:
            w._show_context_menu(QPoint(10, 10))
        build.return_value.exec.assert_called_once()
