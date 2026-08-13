"""Bounded tests for image-viewer input delegation and guard paths."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QWidget

from gui.image_viewer_input import ImageViewerInputMixin


@dataclass
class _WheelEvent:
    delta_y: int
    modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier
    delta_x: int = 0
    accepted: bool = False

    def modifiers(self) -> Qt.KeyboardModifier:
        return self.modifier

    def angleDelta(self) -> QPoint:
        return QPoint(self.delta_x, self.delta_y)

    def accept(self) -> None:
        self.accepted = True


class _InputHarness(ImageViewerInputMixin, QGraphicsView):
    """Small real Qt view exposing only the mixin's signal/state contract."""

    overlay_font_size_adjust_requested = Signal(int)
    wheel_event_for_slice = Signal(int)
    arrow_key_pressed = Signal(int)
    series_navigation_requested = Signal(int)
    angle_draw_cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.image_item = None
        self.mouse_mode = "pan"
        self.roi_drawing_mode = None
        self.magnifier_widget = None
        self.magnifier_active = False
        self.measuring = False
        self.measurement_start_pos = None
        self.text_annotating = False
        self.text_annotation_start_pos = None
        self.arrow_annotating = False
        self.arrow_annotation_start_pos = None
        self._mpr_mode_override = False
        self.scroll_wheel_mode = "slice"
        self.current_zoom = 1.0
        self.min_zoom = 0.5
        self.max_zoom = 2.0

    def zoom_in(self) -> None:
        pass

    def zoom_out(self) -> None:
        pass

    def _apply_view_transform(self) -> None:
        pass

    def _check_transform_changed(self) -> None:
        pass

    def _restart_smooth_idle_timer(self) -> None:
        pass

    @property
    def scene(self) -> QGraphicsScene:
        return self._scene

@pytest.mark.qt
def test_wheel_delegates_zoom_and_slice_modes(qapp, monkeypatch) -> None:
    viewer = _InputHarness()
    calls: list[str] = []
    slices: list[int] = []
    viewer.wheel_event_for_slice.connect(slices.append)
    monkeypatch.setattr(viewer, "zoom_in", lambda: calls.append("in"))
    monkeypatch.setattr(viewer, "zoom_out", lambda: calls.append("out"))

    viewer.scroll_wheel_mode = "zoom"
    zoom_up = _WheelEvent(120)
    zoom_down = _WheelEvent(-120)
    viewer.wheelEvent(zoom_up)  # type: ignore[arg-type]
    viewer.wheelEvent(zoom_down)  # type: ignore[arg-type]
    viewer.scroll_wheel_mode = "slice"
    slice_event = _WheelEvent(60)
    viewer.wheelEvent(slice_event)  # type: ignore[arg-type]

    assert calls == ["in", "out"]
    assert slices == [60]
    assert zoom_up.accepted and zoom_down.accepted and slice_event.accepted


@pytest.mark.qt
def test_pinch_zoom_without_image_is_a_no_op(qapp) -> None:
    viewer = _InputHarness()
    viewer._apply_pinch_zoom(0.5)
    assert viewer.current_zoom == 1.0


@pytest.mark.qt
def test_pinch_zoom_clamps_and_delegates_transform(qapp, monkeypatch) -> None:
    viewer = _InputHarness()
    viewer.image_item = object()
    transforms: list[str] = []
    monkeypatch.setattr(viewer, "_apply_view_transform", lambda: transforms.append("transform"))
    monkeypatch.setattr(viewer, "_check_transform_changed", lambda: transforms.append("check"))
    monkeypatch.setattr(viewer, "_restart_smooth_idle_timer", lambda: transforms.append("timer"))

    viewer._apply_pinch_zoom(10.0)

    assert viewer.current_zoom == viewer.max_zoom
    assert transforms == ["transform", "check", "timer"]


@pytest.mark.qt
def test_set_mouse_mode_restricts_mpr_and_emits_angle_cancel(qapp) -> None:
    viewer = _InputHarness()
    cancelled: list[bool] = []
    viewer.angle_draw_cancel_requested.connect(lambda: cancelled.append(True))

    viewer.set_mouse_mode("measure_angle")
    viewer.set_mouse_mode("unsupported")
    viewer._mpr_mode_override = True
    viewer.set_mouse_mode("unsupported")

    assert viewer.mouse_mode == "pan"
    assert viewer.roi_drawing_mode is None
    assert cancelled == [True]
    assert viewer.dragMode() == QGraphicsView.DragMode.ScrollHandDrag


@pytest.mark.qt
def test_set_mouse_mode_resets_annotation_state(qapp) -> None:
    viewer = _InputHarness()
    viewer.text_annotating = True
    viewer.text_annotation_start_pos = QPointF(3, 4)
    viewer.set_mouse_mode("text_annotation")
    assert not viewer.text_annotating
    assert viewer.text_annotation_start_pos is None

    viewer.arrow_annotating = True
    viewer.arrow_annotation_start_pos = QPointF(5, 6)
    viewer.set_mouse_mode("arrow_annotation")
    assert not viewer.arrow_annotating
    assert viewer.arrow_annotation_start_pos is None


@pytest.mark.qt
@pytest.mark.parametrize(
    ("mode", "drawing_mode", "cursor"),
    [
        ("select", None, Qt.CursorShape.ArrowCursor),
        ("roi_ellipse", "ellipse", Qt.CursorShape.CrossCursor),
        ("roi_rectangle", "rectangle", Qt.CursorShape.CrossCursor),
        ("auto_window_level", "rectangle", Qt.CursorShape.CrossCursor),
        ("measure", None, Qt.CursorShape.CrossCursor),
        ("zoom", None, Qt.CursorShape.CrossCursor),
        ("magnifier", None, Qt.CursorShape.CrossCursor),
        ("crosshair", None, Qt.CursorShape.CrossCursor),
    ],
)
def test_set_mouse_mode_updates_tool_state(qapp, mode, drawing_mode, cursor) -> None:
    viewer = _InputHarness()
    viewer.set_mouse_mode(mode)

    assert viewer.roi_drawing_mode == drawing_mode
    if mode in {"zoom", "magnifier"}:
        assert viewer.cursor().pixmap().isNull() is False
    else:
        assert viewer.cursor().shape() == cursor


@pytest.mark.qt
def test_key_press_emits_navigation_directions(qapp) -> None:
    viewer = _InputHarness()
    slice_directions: list[int] = []
    series_directions: list[int] = []
    viewer.arrow_key_pressed.connect(slice_directions.append)
    viewer.series_navigation_requested.connect(series_directions.append)

    for key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
        event = QKeyEvent(QKeyEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
        viewer.keyPressEvent(event)
        assert event.isAccepted()

    assert slice_directions == [1, -1]
    assert series_directions == [-1, 1]


@pytest.mark.qt
def test_key_press_delegates_when_series_navigator_has_focus(qapp, monkeypatch) -> None:
    viewer = _InputHarness()
    navigator = QWidget(viewer)
    navigator.setObjectName("series_navigator")
    navigator.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    monkeypatch.setattr(
        "gui.image_viewer_input.QApplication.focusWidget", lambda: navigator
    )
    series_directions: list[int] = []
    viewer.series_navigation_requested.connect(series_directions.append)

    viewer.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier))

    assert series_directions == []


@pytest.mark.qt
def test_mode_cursor_parent_sync_guard_handles_non_widget_parent(qapp) -> None:
    viewer = _InputHarness()
    viewer.set_mouse_mode("select")
    viewer.restore_cursor_for_current_mode()
    assert viewer.cursor().shape() == Qt.CursorShape.ArrowCursor


@pytest.mark.qt
def test_drag_guards_ignore_events_without_urls(qapp) -> None:
    viewer = _InputHarness()

    class _Mime:
        def hasUrls(self) -> bool:
            return False

    class _DragEvent:
        def mimeData(self) -> _Mime:
            return _Mime()

        def ignore(self) -> None:
            self.ignored = True

        ignored = False

    for method in (viewer.dragEnterEvent, viewer.dragMoveEvent, viewer.dropEvent):
        event = _DragEvent()
        method(event)  # type: ignore[arg-type]
        assert event.ignored
