"""Round-4 image-viewer input tests: drag behavior."""
# ruff: noqa: F401

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import (
    QKeyEvent,
    QMouseEvent,
    QNativeGestureEvent,
    QPixmap,
    QPointingDevice,
)
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

from gui.image_viewer_input import (
    ImageViewerInputMixin,
    _is_measurement_descendant,
    _make_magnifier_cursor,
    _normalize_scene_pick_item_for_roi,
    _PressItemFlags,
)


def _make_real_mouse_release_event(
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    buttons: Qt.MouseButton = Qt.MouseButton.NoButton,
    pos: QPoint = QPoint(50, 50),
) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease, QPointF(pos), pos, button, buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def _make_real_mouse_move_event(
    buttons: Qt.MouseButton = Qt.MouseButton.NoButton,
    pos: QPoint = QPoint(50, 50),
) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseMove, QPointF(pos), pos, Qt.MouseButton.NoButton,
        buttons, Qt.KeyboardModifier.NoModifier,
    )

# ── Lightweight fakes for tool classes ──────────────────────────────────────


class _FakeROIResizeHandleItem:
    """Minimal stand-in for tools.roi_manager.ROIResizeHandleItem."""

    def __init__(self, shape_item=None):
        self._shape = shape_item

    def roi_graphics_shape_item(self):
        return self._shape


class _FakeMeasurementItem:
    pass


class _FakeAngleMeasurementItem:
    pass


class _FakeDraggableMeasurementText:
    pass


class _FakeDraggableAngleMeasurementText:
    pass


class _FakeMeasurementHandle:
    pass


class _FakeAngleVertexHandle:
    pass


class _FakeTextAnnotationItem:
    pass


class _FakeArrowAnnotationItem:
    pass


# ── Wheel event stub ───────────────────────────────────────────────────────


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


# ── Mouse event stub ───────────────────────────────────────────────────────


@dataclass
class _MouseEvent:
    _button: Qt.MouseButton = Qt.MouseButton.LeftButton
    _buttons: Qt.MouseButton = Qt.MouseButton.NoButton
    _pos_x: int = 50
    _pos_y: int = 50
    accepted: bool = False

    def button(self) -> Qt.MouseButton:
        return self._button

    def buttons(self) -> Qt.MouseButton:
        return self._buttons

    def position(self) -> QPointF:
        return QPointF(self._pos_x, self._pos_y)

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.accepted = False


# ── KeyEvent stub ──────────────────────────────────────────────────────────


@dataclass
class _KeyEvent:
    _key: Qt.Key = Qt.Key.Key_Up
    accepted: bool = False

    def key(self) -> Qt.Key:
        return self._key

    def accept(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.accepted = False


# ── Drag / Drop event stubs ────────────────────────────────────────────────


class _FakeMime:
    def __init__(self, urls=None):
        self._urls = urls or []

    def hasUrls(self) -> bool:
        return bool(self._urls)

    def urls(self):
        return self._urls


class _FakeUrl:
    def __init__(self, path: str):
        self._path = path

    def toLocalFile(self) -> str:
        return self._path


class _FakeDragEvent:
    def __init__(self, urls=None):
        self._mime = _FakeMime(urls)
        self.ignored = False
        self.accepted_action = False

    def mimeData(self):
        return self._mime

    def ignore(self) -> None:
        self.ignored = True

    def acceptProposedAction(self) -> None:
        self.accepted_action = True


class _FakeDropEvent(_FakeDragEvent):
    pass


# ── Full test harness ──────────────────────────────────────────────────────


class _InputHarness(ImageViewerInputMixin, QGraphicsView):
    """Full synthetic host exposing all mixin signals and state slots."""

    overlay_font_size_adjust_requested = Signal(int)
    wheel_event_for_slice = Signal(int)
    arrow_key_pressed = Signal(int)
    series_navigation_requested = Signal(int)
    angle_draw_cancel_requested = Signal()
    image_clicked_no_roi = Signal()
    roi_clicked = Signal(object)
    crosshair_clicked = Signal(object, str, int, int, int)
    measurement_started = Signal(object)
    measurement_updated = Signal(object)
    measurement_finished = Signal()
    angle_measurement_clicked = Signal(object)
    angle_measurement_preview = Signal(object)
    roi_drawing_started = Signal(object)
    roi_drawing_updated = Signal(object)
    roi_drawing_finished = Signal()
    text_annotation_started = Signal(object)
    text_annotation_finished = Signal()
    arrow_annotation_started = Signal(object)
    arrow_annotation_updated = Signal(object)
    arrow_annotation_finished = Signal()
    window_level_drag_changed = Signal(float, float)
    right_mouse_press_for_drag = Signal()
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.image_item = None
        self.mouse_mode = "pan"
        self.roi_drawing_mode = None
        self.magnifier_widget = None
        self.magnifier_active = False
        self._drag_active = False
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
        self.zoom_start_pos = None
        self.zoom_start_zoom = None
        self.zoom_mouse_moved = False
        self.roi_drawing_start = None
        self.right_mouse_drag_start_pos = None
        self.right_mouse_drag_start_center = None
        self.right_mouse_drag_start_width = None
        self.right_mouse_context_menu_shown = False
        self.window_center_sensitivity = 1.0
        self.window_width_sensitivity = 1.0
        self.get_current_dataset_callback = None
        self.get_current_slice_index_callback = None
        self.get_use_rescaled_values_callback = None
        self.get_file_path_callback = None
        self.get_roi_from_item_callback = None
        self._slider_overlay = None
        self._slice_slider_enabled = False
        self._slice_slider_placement = "bottom"
        # Spy lists
        self._zoom_in_calls: list[str] = []
        self._zoom_out_calls: list[str] = []
        self._toggle_measurement_called: list = []
        self._activate_magnifier_called: list = []
        self._emit_crosshair_called: list = []

    def zoom_in(self):
        self._zoom_in_calls.append("in")

    def zoom_out(self):
        self._zoom_out_calls.append("out")

    def _apply_view_transform(self):
        pass

    def _check_transform_changed(self):
        pass

    def _restart_smooth_idle_timer(self):
        pass

    def _update_pixel_info(self, event):
        pass

    def _get_pixel_value_at_coords(self, dataset, x, y, z, use_rescaled):
        return f"pixel({x},{y},{z})"

    def _render_scene_region(self, cx, cy, size, zoom):
        return QPixmap(200, 200)

    def _toggle_measurement(self, scene_pos, *, hide_cursor: bool):
        self._toggle_measurement_called.append((scene_pos, hide_cursor))

    def _activate_magnifier(self, event, scene_pos):
        self._activate_magnifier_called.append(scene_pos)

    def _emit_crosshair(self, scene_pos):
        self._emit_crosshair_called.append(scene_pos)

    @property
    def scene(self):
        return self._scene


# ═══════════════════════════════════════════════════════════════════════════
#  PURE HELPERS
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestMouseMoveEventBranches:
    def test_select_mode_delegates(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("select")
        wl_deltas: list[tuple] = []
        v.window_level_drag_changed.connect(lambda c, w: wl_deltas.append((c, w)))
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.LeftButton)
        v.mouseMoveEvent(e)
        assert wl_deltas == []

    def test_zoom_drag_adjusts(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("zoom")
        v.zoom_start_pos = QPointF(50, 100)
        v.zoom_start_zoom = 1.0
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.LeftButton, pos=QPoint(50, 200))
        v.mouseMoveEvent(e)
        assert v.current_zoom != 1.0

    def test_zoom_drag_below_threshold_no_change(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("zoom")
        v.zoom_start_pos = QPointF(50, 50)
        v.zoom_start_zoom = 1.0
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.LeftButton, pos=QPoint(50, 51))
        v.mouseMoveEvent(e)
        assert v.current_zoom == 1.0
        assert v.zoom_mouse_moved is False

    def test_measure_mode_hides_cursor(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("measure")
        v.measuring = True
        v.measurement_start_pos = QPointF(10, 10)
        v.setCursor(Qt.CursorShape.ArrowCursor)
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
        v.mouseMoveEvent(e)
        assert v.cursor().shape() == Qt.CursorShape.BlankCursor

    def test_measure_angle_emits_preview(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("measure_angle")
        previews: list = []
        v.angle_measurement_preview.connect(lambda pos: previews.append(pos))
        e = _make_real_mouse_move_event(pos=QPoint(50, 50))
        v.mouseMoveEvent(e)
        assert len(previews) == 1

    def test_arrow_annotation_drag_emits_update(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("arrow_annotation")
        v.arrow_annotating = True
        v.arrow_annotation_start_pos = QPointF(10, 10)
        updates: list = []
        v.arrow_annotation_updated.connect(lambda pos: updates.append(pos))
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
        v.mouseMoveEvent(e)
        assert len(updates) == 1

    def test_roi_drawing_drag_emits_update(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("roi_ellipse")
        v.roi_drawing_start = QPointF(10, 10)
        updates: list = []
        v.roi_drawing_updated.connect(lambda pos: updates.append(pos))
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
        v.mouseMoveEvent(e)
        assert len(updates) == 1

    def test_magnifier_active_updates(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("magnifier")
        v.magnifier_active = True
        v.magnifier_widget = MagicMock()
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
        v.mouseMoveEvent(e)
        v.magnifier_widget.update_magnified_region.assert_called_once()

    def test_magnifier_not_active_no_update(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("magnifier")
        v.magnifier_active = False
        wl_deltas: list[tuple] = []
        v.window_level_drag_changed.connect(lambda c, w: wl_deltas.append((c, w)))
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
        v.mouseMoveEvent(e)
        assert wl_deltas == []

    def test_pan_restores_scrolldrag(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("pan")
        v.setDragMode(QGraphicsView.DragMode.NoDrag)
        e = _make_real_mouse_move_event(pos=QPoint(50, 50))
        v.mouseMoveEvent(e)
        assert v.dragMode() == QGraphicsView.DragMode.ScrollHandDrag

    def test_right_mouse_drag_wl(self, qapp):
        v = _InputHarness()
        v.right_mouse_drag_start_pos = QPointF(50, 50)
        v.right_mouse_drag_start_center = 0.0
        v.right_mouse_drag_start_width = 100.0
        v.right_mouse_context_menu_shown = False
        wl_deltas: list[tuple] = []
        v.window_level_drag_changed.connect(lambda c, w: wl_deltas.append((c, w)))
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.RightButton, pos=QPoint(80, 30))
        v.mouseMoveEvent(e)
        assert len(wl_deltas) == 1

    def test_right_drag_context_menu_shown_no_wl(self, qapp):
        v = _InputHarness()
        v.right_mouse_drag_start_pos = QPointF(50, 50)
        v.right_mouse_drag_start_center = 0.0
        v.right_mouse_drag_start_width = 100.0
        v.right_mouse_context_menu_shown = True
        wl_deltas: list[tuple] = []
        v.window_level_drag_changed.connect(lambda c, w: wl_deltas.append((c, w)))
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.RightButton, pos=QPoint(80, 30))
        v.mouseMoveEvent(e)
        assert wl_deltas == []

    def test_right_drag_no_start_pos_no_wl(self, qapp):
        v = _InputHarness()
        v.right_mouse_drag_start_pos = None
        wl_deltas: list[tuple] = []
        v.window_level_drag_changed.connect(lambda c, w: wl_deltas.append((c, w)))
        e = _make_real_mouse_move_event(buttons=Qt.MouseButton.RightButton, pos=QPoint(80, 30))
        v.mouseMoveEvent(e)
        assert wl_deltas == []


# ═══════════════════════════════════════════════════════════════════════════
#  MOUSE RELEASE EVENT — BRANCHES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestMouseReleaseEventBranches:
    def test_select_left_delegates(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("select")
        wl_deltas: list[tuple] = []
        v.window_level_drag_changed.connect(lambda c, w: wl_deltas.append((c, w)))
        e = _make_real_mouse_release_event(button=Qt.MouseButton.LeftButton)
        v.mouseReleaseEvent(e)
        assert wl_deltas == []

    def test_select_right_falls_through(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("select")
        wl_deltas: list[tuple] = []
        v.window_level_drag_changed.connect(lambda c, w: wl_deltas.append((c, w)))
        e = _make_real_mouse_release_event(button=Qt.MouseButton.RightButton)
        v.mouseReleaseEvent(e)
        assert wl_deltas == []

    def test_zoom_release_clears_state(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("zoom")
        v.zoom_start_pos = QPointF(10, 10)
        v.zoom_start_zoom = 1.0
        v.zoom_mouse_moved = True
        e = _make_real_mouse_release_event(button=Qt.MouseButton.LeftButton)
        v.mouseReleaseEvent(e)
        assert v.zoom_start_pos is None
        assert v.zoom_start_zoom is None
        assert v.zoom_mouse_moved is False

    def test_measure_release_finishes(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("measure")
        v.measuring = True
        v.measurement_start_pos = QPointF(5, 5)
        finished: list[bool] = []
        v.measurement_finished.connect(lambda: finished.append(True))
        e = _make_real_mouse_release_event(button=Qt.MouseButton.LeftButton)
        v.mouseReleaseEvent(e)
        assert v.measuring is False
        assert finished == [True]
        assert v.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_text_annotation_release_noop(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("text_annotation")
        v.text_annotating = True
        e = _make_real_mouse_release_event(button=Qt.MouseButton.LeftButton)
        v.mouseReleaseEvent(e)
        assert v.text_annotating is True

    def test_arrow_annotation_release_finishes(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("arrow_annotation")
        v.arrow_annotating = True
        v.arrow_annotation_start_pos = QPointF(5, 5)
        finished: list[bool] = []
        v.arrow_annotation_finished.connect(lambda: finished.append(True))
        e = _make_real_mouse_release_event(button=Qt.MouseButton.LeftButton)
        v.mouseReleaseEvent(e)
        assert v.arrow_annotating is False
        assert finished == [True]

    def test_roi_release_finishes(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("roi_ellipse")
        v.roi_drawing_start = QPointF(10, 10)
        finished: list[bool] = []
        v.roi_drawing_finished.connect(lambda: finished.append(True))
        e = _make_real_mouse_release_event(button=Qt.MouseButton.LeftButton)
        v.mouseReleaseEvent(e)
        assert finished == [True]
        assert v.roi_drawing_start is None

    def test_roi_release_pan_restores_drag(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("pan")
        v.roi_drawing_mode = "roi_ellipse"
        v.roi_drawing_start = QPointF(10, 10)
        v.setDragMode(QGraphicsView.DragMode.NoDrag)
        e = _make_real_mouse_release_event(button=Qt.MouseButton.LeftButton)
        v.mouseReleaseEvent(e)
        assert v.dragMode() == QGraphicsView.DragMode.ScrollHandDrag

    def test_magnifier_release_hides(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("magnifier")
        v.magnifier_active = True
        mock_widget = MagicMock()
        v.magnifier_widget = mock_widget
        e = _make_real_mouse_release_event(button=Qt.MouseButton.LeftButton)
        v.mouseReleaseEvent(e)
        assert v.magnifier_active is False
        mock_widget.hide.assert_called_once()

    def test_right_release_no_drag_shows_context(self, qapp):
        v = _InputHarness()
        v.right_mouse_drag_start_pos = QPointF(50, 50)
        v.right_mouse_context_menu_shown = False
        called: list[str] = []
        with patch(
            "gui.image_viewer_context_menu.show_image_background_context_menu_on_right_release",
            lambda viewer, event: called.append("ctx"),
        ):
            e = _make_real_mouse_release_event(button=Qt.MouseButton.RightButton, pos=QPoint(50, 50))
            v.mouseReleaseEvent(e)
        assert called == ["ctx"]

    def test_right_release_drag_distance_skips_context(self, qapp):
        v = _InputHarness()
        v.right_mouse_drag_start_pos = QPointF(0, 0)
        v.right_mouse_context_menu_shown = False
        called: list[str] = []
        with patch(
            "gui.image_viewer_context_menu.show_image_background_context_menu_on_right_release",
            lambda viewer, event: called.append("ctx"),
        ):
            e = _make_real_mouse_release_event(button=Qt.MouseButton.RightButton, pos=QPoint(50, 50))
            v.mouseReleaseEvent(e)
        assert called == []

    def test_right_release_resets_state(self, qapp):
        v = _InputHarness()
        v.right_mouse_drag_start_pos = QPointF(50, 50)
        v.right_mouse_drag_start_center = 0.0
        v.right_mouse_drag_start_width = 100.0
        v.right_mouse_context_menu_shown = True
        e = _make_real_mouse_release_event(button=Qt.MouseButton.RightButton, pos=QPoint(50, 50))
        v.mouseReleaseEvent(e)
        assert v.right_mouse_drag_start_pos is None
        assert v.right_mouse_drag_start_center is None
        assert v.right_mouse_drag_start_width is None
        assert v.right_mouse_context_menu_shown is False


# ═══════════════════════════════════════════════════════════════════════════
#  VIEWPORT EVENT
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestEventNativeGesture:
    def test_non_gesture_event_delegates(self, qapp):
        v = _InputHarness()
        e = QEvent(QEvent.Type.None_)
        result = v.event(e)
        # Should delegate to super().event() which returns False for None_
        assert result is False

    def test_zoom_gesture_with_image(self, qapp, monkeypatch):
        v = _InputHarness()
        v.image_item = object()
        transforms: list[str] = []
        monkeypatch.setattr(v, "_apply_view_transform", lambda: transforms.append("t"))
        monkeypatch.setattr(v, "_check_transform_changed", lambda: transforms.append("c"))
        monkeypatch.setattr(v, "_restart_smooth_idle_timer", lambda: transforms.append("r"))
        dev = QPointingDevice()
        gesture_event = QNativeGestureEvent(
            Qt.NativeGestureType.ZoomNativeGesture, dev, 1,
            QPointF(50, 50), QPointF(50, 50), QPointF(50, 50),
            0.1, QPointF(0, 0),
        )
        result = v.event(gesture_event)
        assert result is True
        assert v.current_zoom == pytest.approx(1.1, abs=0.01)

    def test_non_zoom_gesture_delegates(self, qapp, monkeypatch):
        v = _InputHarness()
        dev = QPointingDevice()
        gesture_event = QNativeGestureEvent(
            Qt.NativeGestureType.RotateNativeGesture, dev, 1,
            QPointF(50, 50), QPointF(50, 50), QPointF(50, 50),
            45.0, QPointF(0, 0),
        )
        monkeypatch.setattr(QGraphicsView, "event", lambda self, e: False)
        result = v.event(gesture_event)
        assert result is False
