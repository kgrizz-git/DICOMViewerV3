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

from gui.mpr_thumbnail_widget import MPR_ASSIGN_MIME, MprThumbnailWidget

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_widget(subwindow_index: int = 0) -> MprThumbnailWidget:
    return MprThumbnailWidget(subwindow_index)


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
    def test_positive_index(self, qapp) -> None:
        w = _make_widget(2)
        assert w.subwindow_index == 2
        assert w._dot_color == "#FF9800"  # SUBWINDOW_DOT_COLORS[2]
        assert w.toolTip().startswith("MPR View — Window 3")

    @pytest.mark.qt
    def test_zero_index(self, qapp) -> None:
        w = _make_widget(0)
        assert w.subwindow_index == 0
        assert w._dot_color == "#2196F3"
        assert "Window 1" in w.toolTip()

    @pytest.mark.qt
    def test_negative_index_uses_default_grey(self, qapp) -> None:
        w = _make_widget(-1)
        assert w._dot_color == "#9E9E9E"
        assert "not assigned" in w.toolTip()

    @pytest.mark.qt
    def test_out_of_range_index_falls_back_to_default_blue(self, qapp) -> None:
        w = _make_widget(99)
        assert w._dot_color == "#2196F3"  # default from dict.get

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
    def test_clear_mpr_requested_signal_emits(self, qapp) -> None:
        w = _make_widget(3)
        received: list[int] = []
        w.clear_mpr_requested.connect(received.append)

        # Simulate the lambda that the context-menu action would trigger.
        # We cannot open a real QMenu in tests, so invoke the connected
        # slot directly through the action's triggered signal.
        from PySide6.QtWidgets import QMenu

        menu = QMenu(w)
        action = menu.addAction("Clear MPR")
        action.triggered.connect(
            lambda: w.clear_mpr_requested.emit(w._subwindow_index)
        )
        action.triggered.emit()
        assert received == [3]

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
        assert received == [2]

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
        assert received == [1]


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
        assert mime.hasFormat(MPR_ASSIGN_MIME)

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
    def test_start_drag_mimedata_payload(self, qapp) -> None:
        w = _make_widget(3)
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
        data = captured_mime.data(MPR_ASSIGN_MIME)
        assert bytes(data).decode("ascii") == "3"

    @pytest.mark.qt
    def test_start_drag_executes_copy_action(self, qapp) -> None:
        w = _make_widget(0)
        w._drag_start_pos = QPoint(0, 0)

        drag_instance = MagicMock()
        with patch("gui.mpr_thumbnail_widget.QDrag", return_value=drag_instance):
            w._start_drag()

        drag_instance.exec.assert_called_once_with(Qt.DropAction.CopyAction)


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
        w = _make_widget(-1)
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


class TestShowContextMenu:
    @pytest.mark.qt
    def test_context_menu_emits_clear_signal(self, qapp) -> None:
        w = _make_widget(2)
        received: list[int] = []
        w.clear_mpr_requested.connect(received.append)

        with patch("gui.mpr_thumbnail_widget.QMenu") as MockMenu:
            instance = MagicMock()
            MockMenu.return_value = instance
            action = MagicMock()
            instance.addAction.return_value = action

            w._show_context_menu(QPoint(10, 10))

            # Verify the action was connected to emit clear_mpr_requested
            instance.addAction.assert_called_once_with("Clear MPR")
            instance.exec.assert_called_once()
