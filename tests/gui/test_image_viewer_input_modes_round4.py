"""Round-4 image-viewer input tests: modes behavior."""
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

class TestNormalizeScenePickItemForRoi:
    """Tests for _normalize_scene_pick_item_for_roi (pure helper, no Qt needed)."""

    def test_non_handle_passthrough(self):
        obj = object()
        assert _normalize_scene_pick_item_for_roi(obj) is obj

    def test_none_passthrough(self):
        assert _normalize_scene_pick_item_for_roi(None) is None

    @patch("tools.roi_manager.ROIResizeHandleItem", _FakeROIResizeHandleItem)
    def test_roi_handle_returns_shape_item(self):
        shape = QGraphicsEllipseItem(0, 0, 10, 10)
        handle = _FakeROIResizeHandleItem(shape)
        assert _normalize_scene_pick_item_for_roi(handle) is shape

    @patch("tools.roi_manager.ROIResizeHandleItem", _FakeROIResizeHandleItem)
    def test_roi_handle_with_none_shape(self):
        handle = _FakeROIResizeHandleItem(None)
        assert _normalize_scene_pick_item_for_roi(handle) is None

class TestIsMeasurementDescendant:
    """Tests for _is_measurement_descendant (pure tree-walk helper)."""

    def test_none_returns_false(self):
        assert _is_measurement_descendant(None) is False

    def test_no_parent_returns_false(self):
        item = MagicMock()
        item.parentItem.return_value = None
        assert _is_measurement_descendant(item) is False

    def test_no_measurement_ancestor_returns_false(self):
        leaf = MagicMock()
        parent = MagicMock()
        parent.parentItem.return_value = None
        leaf.parentItem.return_value = parent
        assert _is_measurement_descendant(leaf) is False

class TestMakeMagnifierCursor:
    """_make_magnifier_cursor always returns a usable cursor."""

    def test_returns_cursor(self):
        cursor = _make_magnifier_cursor()
        assert cursor is not None
        # Cursor pixmap should not be null
        assert not cursor.pixmap().isNull()


# ═══════════════════════════════════════════════════════════════════════════
#  PRESS ITEM FLAGS
# ═══════════════════════════════════════════════════════════════════════════

class TestPressItemFlags:
    def test_named_tuple_construction(self):
        flags = _PressItemFlags(True, False, False, False, False, False, False)
        assert flags.is_roi_item is True
        assert flags.is_measurement_item is False

    def test_all_false(self):
        flags = _PressItemFlags(*[False] * 7)
        assert all(v is False for v in flags)


# ═══════════════════════════════════════════════════════════════════════════
#  WHEEL EVENT BRANCHES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestWheelEventBranches:
    def test_ctrl_wheel_zoom_in(self, qapp):
        v = _InputHarness()
        e = _WheelEvent(120, Qt.KeyboardModifier.ControlModifier)
        v.wheelEvent(e)
        assert v._zoom_in_calls == ["in"]
        assert e.accepted

    def test_ctrl_wheel_zoom_out(self, qapp):
        v = _InputHarness()
        e = _WheelEvent(-120, Qt.KeyboardModifier.ControlModifier)
        v.wheelEvent(e)
        assert v._zoom_out_calls == ["out"]
        assert e.accepted

    def test_ctrl_wheel_zero_delta_no_action(self, qapp):
        v = _InputHarness()
        e = _WheelEvent(0, Qt.KeyboardModifier.ControlModifier)
        v.wheelEvent(e)
        assert not v._zoom_in_calls
        assert not v._zoom_out_calls
        assert e.accepted

    def test_shift_wheel_font_up(self, qapp):
        v = _InputHarness()
        font_sizes: list[int] = []
        v.overlay_font_size_adjust_requested.connect(font_sizes.append)
        e = _WheelEvent(120, Qt.KeyboardModifier.ShiftModifier)
        v.wheelEvent(e)
        assert font_sizes == [1]
        assert e.accepted

    def test_shift_wheel_font_down(self, qapp):
        v = _InputHarness()
        font_sizes: list[int] = []
        v.overlay_font_size_adjust_requested.connect(font_sizes.append)
        e = _WheelEvent(-120, Qt.KeyboardModifier.ShiftModifier)
        v.wheelEvent(e)
        assert font_sizes == [-1]
        assert e.accepted

    def test_shift_wheel_falls_back_to_x_when_y_zero(self, qapp):
        v = _InputHarness()
        font_sizes: list[int] = []
        v.overlay_font_size_adjust_requested.connect(font_sizes.append)
        e = _WheelEvent(0, Qt.KeyboardModifier.ShiftModifier, delta_x=80)
        v.wheelEvent(e)
        assert font_sizes == [1]

    def test_shift_wheel_negative_x(self, qapp):
        v = _InputHarness()
        font_sizes: list[int] = []
        v.overlay_font_size_adjust_requested.connect(font_sizes.append)
        e = _WheelEvent(0, Qt.KeyboardModifier.ShiftModifier, delta_x=-80)
        v.wheelEvent(e)
        assert font_sizes == [-1]

    def test_meta_modifier_ignored_by_shift_branch(self, qapp):
        v = _InputHarness()
        font_sizes: list[int] = []
        v.overlay_font_size_adjust_requested.connect(font_sizes.append)
        # Cmd+Shift should NOT trigger font size (only bare Shift does)
        e = _WheelEvent(120, Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.MetaModifier)
        v.wheelEvent(e)
        assert font_sizes == []

    def test_zoom_mode_wheel_up_zoom_in(self, qapp):
        v = _InputHarness()
        v.scroll_wheel_mode = "zoom"
        e = _WheelEvent(120)
        v.wheelEvent(e)
        assert v._zoom_in_calls == ["in"]
        assert e.accepted

    def test_zoom_mode_wheel_down_zoom_out(self, qapp):
        v = _InputHarness()
        v.scroll_wheel_mode = "zoom"
        e = _WheelEvent(-120)
        v.wheelEvent(e)
        assert v._zoom_out_calls == ["out"]

    def test_slice_mode_emits_signal(self, qapp):
        v = _InputHarness()
        v.scroll_wheel_mode = "slice"
        slices: list[int] = []
        v.wheel_event_for_slice.connect(slices.append)
        e = _WheelEvent(60)
        v.wheelEvent(e)
        assert slices == [60]


# ═══════════════════════════════════════════════════════════════════════════
#  SET_MOUSE_MODE — ALL BRANCHES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestSetMouseModeBranches:
    def test_select_mode(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("select")
        assert v.mouse_mode == "select"
        assert v.roi_drawing_mode is None
        assert v.dragMode() == QGraphicsView.DragMode.NoDrag
        assert v.cursor().shape() == Qt.CursorShape.ArrowCursor

    def test_roi_ellipse(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("roi_ellipse")
        assert v.roi_drawing_mode == "ellipse"
        assert v.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_roi_rectangle(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("roi_rectangle")
        assert v.roi_drawing_mode == "rectangle"

    def test_auto_window_level(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("auto_window_level")
        assert v.roi_drawing_mode == "rectangle"

    def test_measure_resets_state(self, qapp):
        v = _InputHarness()
        v.measuring = True
        v.measurement_start_pos = QPointF(1, 2)
        v.set_mouse_mode("measure")
        assert v.measuring is False
        assert v.measurement_start_pos is None

    def test_measure_angle_resets_state(self, qapp):
        v = _InputHarness()
        v.measuring = True
        v.measurement_start_pos = QPointF(1, 2)
        v.set_mouse_mode("measure_angle")
        assert v.measuring is False
        assert v.measurement_start_pos is None

    def test_text_annotation_resets_state(self, qapp):
        v = _InputHarness()
        v.text_annotating = True
        v.text_annotation_start_pos = QPointF(1, 2)
        v.set_mouse_mode("text_annotation")
        assert v.text_annotating is False
        assert v.text_annotation_start_pos is None
        assert v.cursor().shape() == Qt.CursorShape.IBeamCursor

    def test_arrow_annotation_resets_state(self, qapp):
        v = _InputHarness()
        v.arrow_annotating = True
        v.arrow_annotation_start_pos = QPointF(1, 2)
        v.set_mouse_mode("arrow_annotation")
        assert v.arrow_annotating is False
        assert v.arrow_annotation_start_pos is None
        assert v.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_zoom_mode_sets_magnifier_cursor(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("zoom")
        assert not v.cursor().pixmap().isNull()

    def test_magnifier_mode_hides_existing_widget(self, qapp):
        v = _InputHarness()
        mock_widget = MagicMock()
        mock_widget.isVisible.return_value = True
        v.magnifier_widget = mock_widget
        v.magnifier_active = True
        v.set_mouse_mode("magnifier")
        mock_widget.hide.assert_called_once()
        assert v.magnifier_active is False

    def test_magnifier_mode_no_widget(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("magnifier")
        assert v.magnifier_active is False

    def test_crosshair_mode(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("crosshair")
        assert v.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_pan_mode_enables_scrollbars(self, qapp):
        v = _InputHarness()
        v.set_mouse_mode("pan")
        assert v.dragMode() == QGraphicsView.DragMode.ScrollHandDrag
        assert v.cursor().shape() == Qt.CursorShape.OpenHandCursor
        assert v.horizontalScrollBar().isEnabled()
        assert v.verticalScrollBar().isEnabled()

    def test_mpr_mode_fallback_to_pan(self, qapp):
        v = _InputHarness()
        v._mpr_mode_override = True
        v.set_mouse_mode("crosshair")
        assert v.mouse_mode == "pan"
        assert v.dragMode() == QGraphicsView.DragMode.ScrollHandDrag

    def test_mpr_mode_allows_roi(self, qapp):
        v = _InputHarness()
        v._mpr_mode_override = True
        v.set_mouse_mode("roi_ellipse")
        assert v.mouse_mode == "roi_ellipse"

    def test_mpr_mode_allows_measure(self, qapp):
        v = _InputHarness()
        v._mpr_mode_override = True
        v.set_mouse_mode("measure")
        assert v.mouse_mode == "measure"

    def test_mpr_mode_allows_text_annotation(self, qapp):
        v = _InputHarness()
        v._mpr_mode_override = True
        v.set_mouse_mode("text_annotation")
        assert v.mouse_mode == "text_annotation"

    def test_mpr_mode_allows_arrow_annotation(self, qapp):
        v = _InputHarness()
        v._mpr_mode_override = True
        v.set_mouse_mode("arrow_annotation")
        assert v.mouse_mode == "arrow_annotation"

    def test_switching_away_from_angle_cancels(self, qapp):
        v = _InputHarness()
        cancelled: list[bool] = []
        v.angle_draw_cancel_requested.connect(lambda: cancelled.append(True))
        v.set_mouse_mode("measure_angle")
        v.set_mouse_mode("pan")
        assert cancelled == [True]

    def test_switching_within_angle_no_cancel(self, qapp):
        v = _InputHarness()
        cancelled: list[bool] = []
        v.angle_draw_cancel_requested.connect(lambda: cancelled.append(True))
        v.set_mouse_mode("measure_angle")
        v.set_mouse_mode("measure_angle")
        assert cancelled == []
