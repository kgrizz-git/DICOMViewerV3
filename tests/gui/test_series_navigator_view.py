"""Focused tests for gui.series_navigator_view."""

from __future__ import annotations

from typing import ClassVar

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QMouseEvent
from PySide6.QtWidgets import QWidget

from gui.series_navigator_view import SeriesThumbnail, StudyDivider, StudyLabel


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self):
        for callback in list(self._callbacks):
            callback()


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.triggered = _FakeSignal()


class _FakeMenu:
    instances: ClassVar[list[_FakeMenu]] = []

    def __init__(self, _parent=None) -> None:
        self.actions: list[_FakeAction] = []
        self.separators = 0
        _FakeMenu.instances.append(self)

    def addAction(self, text: str) -> _FakeAction:
        action = _FakeAction(text)
        self.actions.append(action)
        return action

    def addSeparator(self):
        self.separators += 1

    def exec(self, _pos):
        return None


class _FakeDrag:
    instances: ClassVar[list[_FakeDrag]] = []

    def __init__(self, _parent=None) -> None:
        self.mime_data = None
        self.pixmap = None
        self.hot_spot = None
        self.drop_action = None
        _FakeDrag.instances.append(self)

    def setMimeData(self, mime_data) -> None:
        self.mime_data = mime_data

    def setPixmap(self, pixmap) -> None:
        self.pixmap = pixmap

    def setHotSpot(self, hot_spot) -> None:
        self.hot_spot = hot_spot

    def exec(self, drop_action) -> None:
        self.drop_action = drop_action


@pytest.mark.qt
def test_study_divider_and_label_basic_properties(qapp) -> None:
    divider = StudyDivider()
    label = StudyLabel("Study A")

    assert divider.width() == 2
    assert divider.height() == 95
    assert label.height() == 18

    label.set_text("Study B")
    label.set_width(123)
    label.apply_navigator_tooltip("Tooltip")

    assert label.label.text() == "Study B"
    assert label.width() == 123
    assert label.toolTip() == "Tooltip"
    assert label.label.toolTip() == "Tooltip"


@pytest.mark.qt
def test_series_thumbnail_state_mutators_and_badge_text(qapp) -> None:
    thumb = SeriesThumbnail("series", 7, None, study_uid="study", display_label="AX")

    thumb.update_thumbnail_image(Image.new("L", (8, 8), 10))
    assert thumb.thumbnail_image is not None

    thumb.set_current(True)
    assert thumb.is_current is True
    assert "2px solid" in thumb.styleSheet()

    thumb.set_current(False)
    assert "1px solid" in thumb.styleSheet()

    thumb.set_subwindow_dots([0, 2])
    assert thumb._dot_slots == [0, 2]

    thumb.set_multiframe_info(3, 1)
    assert thumb._get_multiframe_indicator_text() == "3"

    thumb.set_multiframe_info(1, 5)
    assert thumb._get_multiframe_indicator_text() == "5f"

    thumb.set_multiframe_info(2, 4)
    assert thumb._get_multiframe_indicator_text() == "2×4"

    thumb.set_show_slice_frame_count_badge(False)
    assert thumb._get_multiframe_indicator_text() == "2i x 4f"


@pytest.mark.qt
def test_thumbnail_to_qimage_handles_gray_rgb_other_and_failure(qapp) -> None:
    thumb = SeriesThumbnail("series", 1, None)

    gray = thumb._thumbnail_to_qimage(Image.new("L", (5, 6), 1))
    rgb = thumb._thumbnail_to_qimage(Image.new("RGB", (7, 8), (1, 2, 3)))
    rgba = thumb._thumbnail_to_qimage(Image.new("RGBA", (4, 4), (1, 2, 3, 4)))

    assert not gray.isNull()
    assert gray.width() == 5
    assert gray.height() == 6
    assert not rgb.isNull()
    assert rgb.width() == 7
    assert rgb.height() == 8
    assert not rgba.isNull()

    class _BadImage:
        mode = "L"

    fallback = thumb._thumbnail_to_qimage(_BadImage())
    assert not fallback.isNull()


@pytest.mark.qt
def test_mouse_release_emits_clicked_or_instance_clicked(qapp) -> None:
    thumb = SeriesThumbnail("series", 1, None)
    clicked: list[str] = []
    thumb.clicked.connect(clicked.append)

    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(1, 1),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    thumb.mouseReleaseEvent(release)
    assert clicked == ["series"]

    instance_thumb = SeriesThumbnail("series2", 2, None, study_uid="study", target_slice_index=5)
    instances: list[tuple[str, str, int]] = []
    instance_thumb.instance_clicked.connect(lambda study, series, idx: instances.append((study, series, idx)))
    instance_thumb.mouseReleaseEvent(release)
    assert instances == [("study", "series2", 5)]

    drag_thumb = SeriesThumbnail("series3", 3, None)
    drag_thumb._drag_started = True
    ignored: list[str] = []
    drag_thumb.clicked.connect(ignored.append)
    drag_thumb.mouseReleaseEvent(release)
    assert ignored == []


@pytest.mark.qt
def test_mouse_move_starts_drag_and_sets_series_payload(monkeypatch, qapp) -> None:
    monkeypatch.setattr("gui.series_navigator_view.QDrag", _FakeDrag)
    _FakeDrag.instances.clear()
    thumb = SeriesThumbnail("series", 1, Image.new("L", (8, 8), 5))
    thumb.drag_start_position = QPoint(0, 0)

    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(30, 0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    thumb.mouseMoveEvent(move)

    assert thumb._drag_started is True
    drag = _FakeDrag.instances[-1]
    assert drag.mime_data.text() == "series_uid:series"
    assert drag.pixmap is not None
    assert drag.hot_spot == QPoint(32, 32)
    assert drag.drop_action == Qt.DropAction.CopyAction


@pytest.mark.qt
def test_mouse_move_uses_instance_payload_and_ignores_short_or_non_left_drag(monkeypatch, qapp) -> None:
    monkeypatch.setattr("gui.series_navigator_view.QDrag", _FakeDrag)
    _FakeDrag.instances.clear()
    thumb = SeriesThumbnail("series", 1, None, study_uid="study", target_slice_index=9)
    thumb.drag_start_position = QPoint(0, 0)

    short_move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(5, 0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    thumb.mouseMoveEvent(short_move)
    assert _FakeDrag.instances == []

    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(25, 0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    thumb.mouseMoveEvent(move)
    assert _FakeDrag.instances[-1].mime_data.text() == "dv3_assign\tstudy\tseries\t9"

    no_left = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(40, 0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    thumb.mouseMoveEvent(no_left)
    assert len(_FakeDrag.instances) == 1


@pytest.mark.qt
def test_get_series_navigator_walks_parent_chain(qapp) -> None:
    class SeriesNavigator(QWidget):
        pass

    navigator = SeriesNavigator()
    parent = QWidget(navigator)
    thumb = SeriesThumbnail("series", 1, None, parent=parent)

    assert thumb._get_series_navigator() is navigator


@pytest.mark.qt
def test_context_menu_emits_expected_actions(monkeypatch, qapp) -> None:
    monkeypatch.setattr("PySide6.QtWidgets.QMenu", _FakeMenu)
    _FakeMenu.instances.clear()

    class SeriesNavigator(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[tuple[str, str]] = []

        def _add_show_instances_action(self, menu, study_uid: str, series_uid: str) -> None:
            self.calls.append((study_uid, series_uid))
            menu.addAction("Show Instances")

    navigator = SeriesNavigator()
    container = QWidget(navigator)
    thumb = SeriesThumbnail("series", 1, None, study_uid="study", parent=container)
    close_series: list[tuple[str, str]] = []
    close_study: list[str] = []
    about: list[tuple[str, str]] = []
    show: list[tuple[str, str]] = []
    thumb.close_series_signal.connect(lambda study, series: close_series.append((study, series)))
    thumb.close_study_signal.connect(close_study.append)
    thumb.about_this_file_requested.connect(lambda study, series: about.append((study, series)))
    thumb.show_file_requested.connect(lambda study, series: show.append((study, series)))

    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(1, 1), QPoint(1, 1))
    thumb.contextMenuEvent(event)

    menu = _FakeMenu.instances[-1]
    assert navigator.calls == [("study", "series")]
    for action in menu.actions:
        action.triggered.emit()

    assert close_series == [("study", "series")]
    assert close_study == ["study"]
    assert about == [("study", "series")]
    assert show == [("study", "series")]


@pytest.mark.qt
def test_context_menu_returns_early_without_study_uid(monkeypatch, qapp) -> None:
    monkeypatch.setattr("PySide6.QtWidgets.QMenu", _FakeMenu)
    _FakeMenu.instances.clear()
    thumb = SeriesThumbnail("series", 1, None, study_uid="")

    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(1, 1), QPoint(1, 1))
    thumb.contextMenuEvent(event)

    assert _FakeMenu.instances == []
