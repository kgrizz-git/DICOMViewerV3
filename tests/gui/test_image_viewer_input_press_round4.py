"""Round-4 image-viewer input tests: press behavior."""
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


def _make_real_mouse_event(
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    buttons: Qt.MouseButton = Qt.MouseButton.NoButton,
    pos: QPoint = QPoint(50, 50),
) -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress, QPointF(pos), pos, button, buttons,
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
class TestMousePressEvent:
    def test_right_button_delegates_to_context_menu(self, qapp, monkeypatch):
        v = _InputHarness()
        called: list[str] = []
        monkeypatch.setattr(
            "gui.image_viewer_item_context_menu.handle_mouse_press_right_button",
            lambda viewer, event: called.append("context"),
        )
        e = _make_real_mouse_event(button=Qt.MouseButton.RightButton)
        v.mousePressEvent(e)
        assert called == ["context"]

    def test_slider_overlay_hidden_on_press_outside(self, qapp):
        v = _InputHarness()
        overlay = MagicMock()
        overlay.isVisible.return_value = True
        overlay.is_interacting.return_value = False
        overlay.geometry.return_value.contains.return_value = False
        v._slider_overlay = overlay
        e = _make_real_mouse_event(pos=QPoint(50, 50))
        v.mousePressEvent(e)
        overlay.hide_immediately.assert_called_once()

    def test_slider_overlay_not_hidden_when_interacting(self, qapp):
        v = _InputHarness()
        overlay = MagicMock()
        overlay.isVisible.return_value = True
        overlay.is_interacting.return_value = True
        v._slider_overlay = overlay
        e = _make_real_mouse_event(pos=QPoint(50, 50))
        v.mousePressEvent(e)
        overlay.hide_immediately.assert_not_called()

    def test_parent_focus_on_first_click(self, qapp):
        v = _InputHarness()
        parent = MagicMock()
        parent.is_focused = False
        parent.set_focused = MagicMock()
        parent.focus_changed = MagicMock()
        with patch.object(v, "parent", return_value=parent):
            e = _make_real_mouse_event(button=Qt.MouseButton.LeftButton)
            v.mousePressEvent(e)
        parent.set_focused.assert_called_once_with(True)
        parent.focus_changed.emit.assert_called_once_with(True)

    def test_no_parent_focus_when_already_focused(self, qapp):
        v = _InputHarness()
        parent = MagicMock()
        parent.is_focused = True
        with patch.object(v, "parent", return_value=parent):
            e = _make_real_mouse_event(button=Qt.MouseButton.LeftButton)
            v.mousePressEvent(e)
        parent.set_focused.assert_not_called()

    def test_no_focus_when_right_button(self, qapp):
        v = _InputHarness()
        parent = MagicMock()
        parent.is_focused = False
        with patch.object(v, "parent", return_value=parent):
            e = _make_real_mouse_event(button=Qt.MouseButton.RightButton)
            v.mousePressEvent(e)
        parent.set_focused.assert_not_called()

# ═══════════════════════════════════════════════════════════════════════════
#  SELECT MODE PRESS
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestSelectModePress:
    def test_empty_space_deselects(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("select")
        no_roi: list[bool] = []
        v.image_clicked_no_roi.connect(lambda: no_roi.append(True))
        e = _make_real_mouse_event(pos=QPoint(50, 50))
        v._handle_select_mode_press(e)
        assert no_roi == [True]
        assert e.isAccepted()

    def test_image_item_deselects(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("select")
        v.image_item = MagicMock()
        no_roi: list[bool] = []
        v.image_clicked_no_roi.connect(lambda: no_roi.append(True))
        e = _make_real_mouse_event(pos=QPoint(50, 50))
        v._handle_select_mode_press(e)
        assert no_roi == [True]

    def test_roi_item_not_deselected(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("select")
        roi_item = QGraphicsEllipseItem(0, 0, 10, 10)
        v._scene.addItem(roi_item)
        v.get_roi_from_item_callback = lambda item: item if item is roi_item else None
        no_roi: list[bool] = []
        v.image_clicked_no_roi.connect(lambda: no_roi.append(True))
        with patch.object(v, "mapToScene", return_value=QPointF(5, 5)), \
             patch.object(v._scene, "itemAt", return_value=roi_item):
            e = _make_real_mouse_event(pos=QPoint(5, 5))
            v._handle_select_mode_press(e)
        assert no_roi == []


# ═══════════════════════════════════════════════════════════════════════════
#  SCROLLHAND PRESS
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestScrollHandPress:
    def test_empty_space_pans(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("pan")
        no_roi: list[bool] = []
        v.image_clicked_no_roi.connect(lambda: no_roi.append(True))
        with patch.object(v, "mapToScene", return_value=QPointF(50, 50)), \
             patch.object(v._scene, "itemAt", return_value=None):
            e = _make_real_mouse_event(pos=QPoint(50, 50))
            v._handle_scrollhand_press(e)
        assert no_roi == [True]

    def test_roi_item_disables_drag(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("pan")
        roi_item = QGraphicsEllipseItem(0, 0, 10, 10)
        v._scene.addItem(roi_item)
        clicked_items: list = []
        v.roi_clicked.connect(clicked_items.append)
        with patch.object(v, "mapToScene", return_value=QPointF(5, 5)), \
             patch.object(v._scene, "itemAt", return_value=roi_item):
            e = _make_real_mouse_event(pos=QPoint(5, 5))
            v._handle_scrollhand_press(e)
        assert clicked_items == [roi_item]
        assert v.dragMode() == QGraphicsView.DragMode.NoDrag


# ═══════════════════════════════════════════════════════════════════════════
#  LEFT BUTTON PRESS DISPATCH
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestHandleLeftButtonPress:
    def test_roi_item_emits_signal(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("pan")
        roi_item = QGraphicsEllipseItem(0, 0, 10, 10)
        v._scene.addItem(roi_item)
        clicked: list = []
        v.roi_clicked.connect(clicked.append)
        with patch.object(v, "mapToScene", return_value=QPointF(5, 5)), \
             patch.object(v._scene, "itemAt", return_value=roi_item):
            e = _make_real_mouse_event(pos=QPoint(5, 5))
            v._handle_left_button_press(e)
        assert clicked == [roi_item]

    def test_empty_space_dispatches_zoom(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("zoom")
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert v.zoom_start_pos is not None

    def test_empty_space_dispatches_measure(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("measure")
        toggle_calls: list = []
        v._toggle_measurement_called = toggle_calls
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert len(toggle_calls) == 1

    def test_empty_space_dispatches_measure_angle(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("measure_angle")
        angle_calls: list = []
        v.angle_measurement_clicked.connect(lambda pos: angle_calls.append(pos))
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert len(angle_calls) == 1

    def test_empty_space_dispatches_magnifier(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("magnifier")
        mag_calls: list = []
        v._activate_magnifier_called = mag_calls
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert len(mag_calls) == 1

    def test_empty_space_dispatches_crosshair(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("crosshair")
        cross_calls: list = []
        v._emit_crosshair_called = cross_calls
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert len(cross_calls) == 1

    def test_text_annotation_start(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("text_annotation")
        started: list = []
        v.text_annotation_started.connect(lambda pos: started.append(pos))
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert len(started) == 1
        assert v.text_annotating is True

    def test_text_annotation_finishes_previous(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("text_annotation")
        v.text_annotating = True
        finished: list[bool] = []
        v.text_annotation_finished.connect(lambda: finished.append(True))
        started: list = []
        v.text_annotation_started.connect(lambda pos: started.append(pos))
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert finished == [True]
        assert len(started) == 1

    def test_arrow_annotation_start(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("arrow_annotation")
        started: list = []
        v.arrow_annotation_started.connect(lambda pos: started.append(pos))
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert len(started) == 1
        assert v.arrow_annotating is True

    def test_arrow_annotation_finishes_previous(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("arrow_annotation")
        v.arrow_annotating = True
        finished: list[bool] = []
        v.arrow_annotation_finished.connect(lambda: finished.append(True))
        started: list = []
        v.arrow_annotation_started.connect(lambda pos: started.append(pos))
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert finished == [True]
        assert len(started) == 1

    def test_roi_drawing_start(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("roi_ellipse")
        roi_started: list = []
        v.roi_drawing_started.connect(lambda pos: roi_started.append(pos))
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert len(roi_started) == 1
        assert v.roi_drawing_start is not None

    def test_zoom_mode_on_non_empty_item(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("zoom")
        item = QGraphicsEllipseItem(0, 0, 10, 10)
        v._scene.addItem(item)
        no_roi: list[bool] = []
        v.image_clicked_no_roi.connect(lambda: no_roi.append(True))
        e = _MouseEvent(_pos_x=5, _pos_y=5)
        v._handle_left_button_press(e)
        assert no_roi == [True]
        assert v.zoom_start_pos is not None

    def test_measure_on_non_empty_item(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("measure")
        item = QGraphicsEllipseItem(0, 0, 10, 10)
        v._scene.addItem(item)
        toggle_calls: list = []
        v._toggle_measurement_called = toggle_calls
        e = _MouseEvent(_pos_x=5, _pos_y=5)
        v._handle_left_button_press(e)
        assert len(toggle_calls) == 1

    def test_measure_angle_on_non_empty_item(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("measure_angle")
        item = QGraphicsEllipseItem(0, 0, 10, 10)
        v._scene.addItem(item)
        angle_calls: list = []
        v.angle_measurement_clicked.connect(lambda pos: angle_calls.append(pos))
        e = _MouseEvent(_pos_x=5, _pos_y=5)
        v._handle_left_button_press(e)
        assert len(angle_calls) == 1

    def test_roi_drawing_on_non_empty_item(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("roi_ellipse")
        item = QGraphicsEllipseItem(0, 0, 10, 10)
        v._scene.addItem(item)
        roi_started: list = []
        v.roi_drawing_started.connect(lambda pos: roi_started.append(pos))
        e = _MouseEvent(_pos_x=5, _pos_y=5)
        v._handle_left_button_press(e)
        assert len(roi_started) == 1

    def test_other_item_deselects(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("pan")
        no_roi: list[bool] = []
        v.image_clicked_no_roi.connect(lambda: no_roi.append(True))
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        v._handle_left_button_press(e)
        assert no_roi == [True]


# ═══════════════════════════════════════════════════════════════════════════
#  CLASSIFY NORMAL PRESS ITEM
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestClassifyNormalPressItem:
    def test_none_item(self, qapp):
        v = _InputHarness()
        flags = v._classify_normal_press_item(None)
        assert flags == _PressItemFlags(False, False, False, False, False, False, False)

    def test_roi_item(self, qapp):
        v = _InputHarness()
        item = QGraphicsEllipseItem(0, 0, 10, 10)
        v._scene.addItem(item)
        flags = v._classify_normal_press_item(item)
        assert flags.is_roi_item is True

    def test_image_item_not_roi(self, qapp):
        v = _InputHarness()
        v.image_item = QGraphicsEllipseItem(0, 0, 10, 10)
        flags = v._classify_normal_press_item(v.image_item)
        assert flags.is_roi_item is False


# ═══════════════════════════════════════════════════════════════════════════
#  TOGGLE MEASUREMENT
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestToggleMeasurement:
    def test_start_new(self, qapp):
        v = _InputHarness()
        started: list = []
        v.measurement_started.connect(lambda pos: started.append(pos))
        v.measuring = False
        pos = QPointF(10, 20)
        # Call the real method
        ImageViewerInputMixin._toggle_measurement(v, pos, hide_cursor=False)
        assert v.measuring is True
        assert v.measurement_start_pos == pos
        assert started == [pos]

    def test_finish_existing(self, qapp):
        v = _InputHarness()
        finished: list[bool] = []
        v.measurement_finished.connect(lambda: finished.append(True))
        v.measuring = True
        v.measurement_start_pos = QPointF(5, 5)
        ImageViewerInputMixin._toggle_measurement(v, QPointF(10, 10), hide_cursor=False)
        assert v.measuring is False
        assert v.measurement_start_pos is None
        assert finished == [True]

    def test_start_with_hide_cursor(self, qapp):
        v = _InputHarness()
        v.measuring = False
        v.setCursor(Qt.CursorShape.ArrowCursor)
        ImageViewerInputMixin._toggle_measurement(v, QPointF(1, 1), hide_cursor=True)
        assert v.cursor().shape() == Qt.CursorShape.BlankCursor


# ═══════════════════════════════════════════════════════════════════════════
#  MOUSE MOVE EVENT — BRANCHES
# ═══════════════════════════════════════════════════════════════════════════
