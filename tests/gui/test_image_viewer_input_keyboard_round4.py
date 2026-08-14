"""Round-4 image-viewer input tests: keyboard behavior."""
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

@pytest.mark.qt
class TestApplyCursorForMouseMode:
    def test_select(self, qapp):
        v = _InputHarness()
        v.mouse_mode = "select"
        v._apply_cursor_for_mouse_mode()
        assert v.cursor().shape() == Qt.CursorShape.ArrowCursor

    @pytest.mark.parametrize(
        "mode",
        ["roi_ellipse", "roi_rectangle", "measure", "measure_angle", "crosshair", "arrow_annotation", "auto_window_level"],
    )
    def test_crosshair_modes(self, qapp, mode):
        v = _InputHarness()
        v.mouse_mode = mode
        v._apply_cursor_for_mouse_mode()
        assert v.cursor().shape() == Qt.CursorShape.CrossCursor

    @pytest.mark.parametrize("mode", ["zoom", "magnifier"])
    def test_magnifier_modes(self, qapp, mode):
        v = _InputHarness()
        v.mouse_mode = mode
        v._apply_cursor_for_mouse_mode()
        assert not v.cursor().pixmap().isNull()

    def test_text_annotation(self, qapp):
        v = _InputHarness()
        v.mouse_mode = "text_annotation"
        v._apply_cursor_for_mouse_mode()
        assert v.cursor().shape() == Qt.CursorShape.IBeamCursor

    def test_pan_default(self, qapp):
        v = _InputHarness()
        v.mouse_mode = "pan"
        v._apply_cursor_for_mouse_mode()
        assert v.cursor().shape() == Qt.CursorShape.OpenHandCursor

    def test_unknown_mode_falls_to_pan(self, qapp):
        v = _InputHarness()
        v.mouse_mode = "totally_unknown"
        v._apply_cursor_for_mouse_mode()
        assert v.cursor().shape() == Qt.CursorShape.OpenHandCursor


# ═══════════════════════════════════════════════════════════════════════════
#  SET_ROI_DRAWING_MODE
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestSetRoiDrawingMode:
    def test_set_rectangle(self, qapp):
        v = _InputHarness()
        v.set_roi_drawing_mode("rectangle")
        assert v.roi_drawing_mode == "rectangle"
        assert v.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_set_ellipse(self, qapp):
        v = _InputHarness()
        v.set_roi_drawing_mode("ellipse")
        assert v.roi_drawing_mode == "ellipse"

    def test_clear_mode(self, qapp):
        v = _InputHarness()
        v.set_roi_drawing_mode("rectangle")
        v.set_roi_drawing_mode(None)
        assert v.roi_drawing_mode is None
        assert v.cursor().shape() == Qt.CursorShape.ArrowCursor


# ═══════════════════════════════════════════════════════════════════════════
#  KEY PRESS — ADDITIONAL BRANCHES
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestKeyPressBranches:
    def test_unknown_key_delegates(self, qapp):
        v = _InputHarness()
        e = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
        v.keyPressEvent(e)
        # Not accepted by our handler — delegated to super

    def test_up_emits_slice(self, qapp):
        v = _InputHarness()
        dirs: list[int] = []
        v.arrow_key_pressed.connect(dirs.append)
        e = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        v.keyPressEvent(e)
        assert dirs == [1]
        assert e.isAccepted()

    def test_down_emits_slice(self, qapp):
        v = _InputHarness()
        dirs: list[int] = []
        v.arrow_key_pressed.connect(dirs.append)
        e = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        v.keyPressEvent(e)
        assert dirs == [-1]

    @patch("tools.text_annotation_tool.is_any_text_annotation_editing", return_value=True)
    def test_text_editing_suppresses_arrows(self, mock_editing, qapp):
        v = _InputHarness()
        dirs: list[int] = []
        v.arrow_key_pressed.connect(dirs.append)
        e = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        v.keyPressEvent(e)
        assert dirs == []

    def test_left_arrow_no_focus_skips(self, qapp):
        v = _InputHarness()
        series: list[int] = []
        v.series_navigation_requested.connect(series.append)
        with patch("gui.image_viewer_input.QApplication.focusWidget", return_value=None):
            e = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier)
            v.keyPressEvent(e)
        assert series == [-1]

    def test_right_arrow_no_focus(self, qapp):
        v = _InputHarness()
        series: list[int] = []
        v.series_navigation_requested.connect(series.append)
        with patch("gui.image_viewer_input.QApplication.focusWidget", return_value=None):
            e = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
            v.keyPressEvent(e)
        assert series == [1]

    def test_left_arrow_navigator_child_has_focus(self, qapp):
        v = _InputHarness()
        series: list[int] = []
        v.series_navigation_requested.connect(series.append)
        child = QWidget()
        child.setObjectName("series_navigator_scroll_area")
        with patch("gui.image_viewer_input.QApplication.focusWidget", return_value=child):
            e = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier)
            v.keyPressEvent(e)
        assert series == []

    def test_right_arrow_navigator_container_has_focus(self, qapp):
        v = _InputHarness()
        series: list[int] = []
        v.series_navigation_requested.connect(series.append)
        child = QWidget()
        child.setObjectName("series_navigator_container")
        with patch("gui.image_viewer_input.QApplication.focusWidget", return_value=child):
            e = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier)
            v.keyPressEvent(e)
        assert series == []


# ═══════════════════════════════════════════════════════════════════════════
#  SYNC CURSOR TO PARENT CHAIN
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestSyncCursorToParentChain:
    def test_no_parent_is_noop(self, qapp):
        v = _InputHarness()
        v._sync_cursor_to_parent_chain()  # no crash

    def test_with_widget_parent(self, qapp):
        parent = QWidget()
        v = _InputHarness(parent)
        v.set_mouse_mode("select")
        v._sync_cursor_to_parent_chain()
        assert parent.cursor().shape() == Qt.CursorShape.ArrowCursor

    def test_with_grandparent(self, qapp):
        grandparent = QWidget()
        parent = QWidget(grandparent)
        v = _InputHarness(parent)
        v.set_mouse_mode("pan")
        v._sync_cursor_to_parent_chain()
        assert parent.cursor().shape() == Qt.CursorShape.OpenHandCursor
        assert grandparent.cursor().shape() == Qt.CursorShape.OpenHandCursor

    def test_with_great_grandparent(self, qapp):
        great = QWidget()
        grand = QWidget(great)
        parent = QWidget(grand)
        v = _InputHarness(parent)
        v.set_mouse_mode("crosshair")
        v._sync_cursor_to_parent_chain()
        assert parent.cursor().shape() == Qt.CursorShape.CrossCursor
        assert grand.cursor().shape() == Qt.CursorShape.CrossCursor


# ═══════════════════════════════════════════════════════════════════════════
#  RESTORE CURSOR
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestRestoreCursorForCurrentMode:
    def test_restores_crosshair(self, qapp):
        v = _InputHarness()
        v.mouse_mode = "roi_ellipse"
        v.setCursor(Qt.CursorShape.ArrowCursor)  # simulate hiding
        v.restore_cursor_for_current_mode()
        assert v.cursor().shape() == Qt.CursorShape.CrossCursor

    def test_restores_arrow(self, qapp):
        v = _InputHarness()
        v.mouse_mode = "select"
        v.setCursor(Qt.CursorShape.CrossCursor)
        v.restore_cursor_for_current_mode()
        assert v.cursor().shape() == Qt.CursorShape.ArrowCursor


# ═══════════════════════════════════════════════════════════════════════════
#  MOUSE PRESS — RIGHT BUTTON
# ═══════════════════════════════════════════════════════════════════════════


def _make_real_mouse_event(
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    buttons: Qt.MouseButton = Qt.MouseButton.NoButton,
    pos: QPoint = QPoint(50, 50),
) -> QMouseEvent:
    """Create a real QMouseEvent for tests that reach super() calls."""
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(pos),
        pos,
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )

def _make_real_mouse_release_event(
    button: Qt.MouseButton = Qt.MouseButton.LeftButton,
    buttons: Qt.MouseButton = Qt.MouseButton.NoButton,
    pos: QPoint = QPoint(50, 50),
) -> QMouseEvent:
    """Create a real QMouseEvent for release tests."""
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(pos),
        pos,
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def _make_real_mouse_move_event(
    buttons: Qt.MouseButton = Qt.MouseButton.NoButton,
    pos: QPoint = QPoint(50, 50),
) -> QMouseEvent:
    """Create a real QMouseEvent for move tests."""
    return QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(pos),
        pos,
        Qt.MouseButton.NoButton,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
