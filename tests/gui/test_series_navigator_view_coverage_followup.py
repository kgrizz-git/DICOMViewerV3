"""Additional synthetic coverage for SeriesThumbnail painting and guards."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent, QPaintEvent

from gui.series_navigator_view import SeriesThumbnail


@pytest.mark.qt
def test_badge_text_legacy_single_frame_and_clamped_counts(qapp) -> None:
    thumb = SeriesThumbnail("series", 1, None)
    thumb.set_multiframe_info(0, 0)
    assert thumb._get_multiframe_indicator_text() == "1"
    thumb.set_show_slice_frame_count_badge(False)
    assert thumb._get_multiframe_indicator_text() == ""
    thumb.set_multiframe_info(1, 3)
    assert thumb._get_multiframe_indicator_text() == "3fr"


@pytest.mark.qt
def test_mouse_press_resets_drag_state_and_instance_without_study_clicks_series(qapp) -> None:
    thumb = SeriesThumbnail("series", 1, None, target_slice_index=4)
    thumb._drag_started = True
    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(3, 4),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    thumb.mousePressEvent(press)
    assert thumb.drag_start_position == QPoint(3, 4)
    assert thumb._drag_started is False
    clicked: list[str] = []
    thumb.clicked.connect(clicked.append)
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(3, 4),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    thumb.mouseReleaseEvent(release)
    assert clicked == ["series"]


@pytest.mark.qt
def test_paint_event_covers_placeholder_rgb_other_mode_and_dots(qapp) -> None:
    for image in (None, Image.new("RGB", (8, 6), (1, 2, 3)), Image.new("RGBA", (6, 8))):
        thumb = SeriesThumbnail("series", 3, image, display_label="CT")
        thumb.resize(68, 68)
        thumb.set_subwindow_dots([0, 1, 3, 99])
        thumb.set_multiframe_info(2, 4)
        thumb.paintEvent(QPaintEvent(QRect(0, 0, 68, 68)))


@pytest.mark.qt
def test_paint_event_falls_back_for_invalid_image(qapp) -> None:
    invalid = SimpleNamespace(width=0, height=0, mode="RGB")
    thumb = SeriesThumbnail("series", 3, invalid)  # type: ignore[arg-type]
    thumb.resize(68, 68)
    thumb.paintEvent(QPaintEvent(QRect(0, 0, 68, 68)))
