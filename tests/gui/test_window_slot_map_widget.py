"""Focused tests for WindowSlotMapWidget layout helpers and click signals."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QDialog

from gui.window_slot_map_widget import (
    WINDOW_SLOT_MAP_SIZE,
    WindowSlotMapPopupDialog,
    WindowSlotMapWidget,
)


@pytest.mark.qt
def test_set_callbacks_and_safe_defaults(qapp) -> None:
    widget = WindowSlotMapWidget()
    assert widget.width() == WINDOW_SLOT_MAP_SIZE

    # Without callbacks, helpers return safe defaults.
    assert widget._safe_slot_to_view() == [0, 1, 2, 3]
    assert widget._safe_layout_mode() == "2x2"
    assert widget._safe_focused_view_index() == 0

    widget.set_callbacks(
        get_slot_to_view=lambda: [3, 2, 1, 0, 9],
        get_layout_mode=lambda: "1x1",
        get_focused_view_index=lambda: 2,
        get_thumbnail_for_view=lambda _i: QPixmap(8, 8),
    )
    assert widget._safe_slot_to_view() == [3, 2, 1, 0]
    assert widget._safe_layout_mode() == "1x1"
    assert widget._safe_focused_view_index() == 2
    assert widget._compute_focused_slot([3, 2, 1, 0]) == 1


@pytest.mark.qt
def test_compute_displayed_slots_for_common_layouts(qapp) -> None:
    widget = WindowSlotMapWidget()
    stv = [0, 1, 2, 3]
    widget.set_callbacks(
        get_slot_to_view=lambda: stv,
        get_layout_mode=lambda: "2x2",
        get_focused_view_index=lambda: 0,
    )
    assert widget._compute_displayed_slots(stv) == []

    widget.set_callbacks(
        get_slot_to_view=lambda: stv,
        get_layout_mode=lambda: "1x1",
        get_focused_view_index=lambda: 3,
    )
    assert widget._compute_displayed_slots(stv) == [3]

    widget.set_callbacks(
        get_slot_to_view=lambda: stv,
        get_layout_mode=lambda: "1x2",
        get_focused_view_index=lambda: 2,
    )
    assert widget._compute_displayed_slots(stv) == [2, 3]

    widget.set_callbacks(
        get_slot_to_view=lambda: stv,
        get_layout_mode=lambda: "2x1",
        get_focused_view_index=lambda: 1,
    )
    assert widget._compute_displayed_slots(stv) == [1, 3]


@pytest.mark.qt
def test_mouse_press_emits_cell_clicked(qapp) -> None:
    widget = WindowSlotMapWidget()
    clicked: list[int] = []
    widget.cell_clicked.connect(clicked.append)

    # Bottom-right cell (slot 3) in the fixed 80×80 map.
    pos = QPoint(60, 60)
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        pos.toPointF(),
        pos.toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mousePressEvent(event)
    assert clicked == [3]


@pytest.mark.qt
def test_popup_dialog_exposes_map_widget(qapp) -> None:
    from PySide6.QtWidgets import QWidget

    parent = QWidget()
    boundary = QWidget()
    dialog = WindowSlotMapPopupDialog(parent, boundary)
    assert isinstance(dialog, QDialog)
    assert isinstance(dialog.get_map_widget(), WindowSlotMapWidget)
    dialog.reject()
    assert dialog.result() == int(dialog.DialogCode.Rejected)
