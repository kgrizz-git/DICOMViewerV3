"""Round-4 image-viewer input tests: misc behavior."""
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
class TestViewportEvent:
    def test_mouse_move_calls_update_pixel_info(self, qapp):
        v = _InputHarness()
        call_count = [0]

        def spy(event):
            call_count[0] += 1

        v._update_pixel_info = spy
        from PySide6.QtGui import QMouseEvent as RealMouseEvent

        real_event = RealMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(50, 50),
            QPoint(50, 50),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        call_count[0] = 0
        v.viewportEvent(real_event)
        assert call_count[0] >= 1


# ═══════════════════════════════════════════════════════════════════════════
#  LEAVE EVENT
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestLeaveEvent:
    def test_visible_overlay_schedules_hide(self, qapp):
        v = _InputHarness()
        overlay = MagicMock()
        overlay.isVisible.return_value = True
        overlay.is_interacting.return_value = False
        v._slider_overlay = overlay
        v.leaveEvent(QEvent(QEvent.Type.Leave))
        overlay.schedule_hide.assert_called_once()

    def test_hidden_overlay_no_action(self, qapp):
        v = _InputHarness()
        overlay = MagicMock()
        overlay.isVisible.return_value = False
        v._slider_overlay = overlay
        v.leaveEvent(QEvent(QEvent.Type.Leave))
        overlay.schedule_hide.assert_not_called()

    def test_interacting_overlay_no_action(self, qapp):
        v = _InputHarness()
        overlay = MagicMock()
        overlay.isVisible.return_value = True
        overlay.is_interacting.return_value = True
        v._slider_overlay = overlay
        v.leaveEvent(QEvent(QEvent.Type.Leave))
        overlay.schedule_hide.assert_not_called()

    def test_no_overlay(self, qapp):
        v = _InputHarness()
        v._slider_overlay = None
        v.leaveEvent(QEvent(QEvent.Type.Leave))  # no crash


# ═══════════════════════════════════════════════════════════════════════════
#  DRAG / DROP EVENTS
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestDragDropEvents:
    def test_drag_enter_accepts_valid_urls(self, qapp, tmp_path):
        v = _InputHarness()
        f = tmp_path / "test.txt"
        f.write_text("x")
        event = _FakeDragEvent([_FakeUrl(str(f))])
        v.dragEnterEvent(event)
        assert event.accepted_action
        assert v._drag_active is True

    def test_drag_enter_ignores_invalid_urls(self, qapp):
        v = _InputHarness()
        event = _FakeDragEvent([_FakeUrl("/nonexistent/path")])
        v.dragEnterEvent(event)
        assert event.ignored

    def test_drag_leave_clears_active(self, qapp):
        v = _InputHarness()
        v._drag_active = True
        v.dragLeaveEvent(None)
        assert v._drag_active is False

    def test_drop_with_valid_files(self, qapp, tmp_path):
        v = _InputHarness()
        f = tmp_path / "dicom.dcm"
        f.write_text("data")
        paths_emitted: list[list] = []
        v.files_dropped.connect(paths_emitted.append)
        event = _FakeDropEvent([_FakeUrl(str(f))])
        v.dropEvent(event)
        assert len(paths_emitted) == 1
        assert str(f) in paths_emitted[0]
        assert v._drag_active is False

    def test_drop_with_no_urls(self, qapp):
        v = _InputHarness()
        paths_emitted: list[list] = []
        v.files_dropped.connect(paths_emitted.append)
        event = _FakeDropEvent([])
        event._mime = _FakeMime([])
        v.dropEvent(event)
        assert paths_emitted == []
        assert event.ignored

    def test_drop_empty_list(self, qapp):
        v = _InputHarness()
        paths_emitted: list[list] = []
        v.files_dropped.connect(paths_emitted.append)
        event = _FakeDropEvent()
        event._mime = _FakeMime([])
        v.dropEvent(event)
        assert paths_emitted == []

    def test_drop_with_directories(self, qapp, tmp_path):
        v = _InputHarness()
        d = tmp_path / "subdir"
        d.mkdir()
        paths_emitted: list[list] = []
        v.files_dropped.connect(paths_emitted.append)
        event = _FakeDropEvent([_FakeUrl(str(d))])
        v.dropEvent(event)
        assert len(paths_emitted) == 1

    def test_drag_move_accepts_valid(self, qapp, tmp_path):
        v = _InputHarness()
        f = tmp_path / "test.txt"
        f.write_text("x")
        event = _FakeDragEvent([_FakeUrl(str(f))])
        v.dragMoveEvent(event)
        assert event.accepted_action

    def test_drag_move_ignores_invalid(self, qapp):
        v = _InputHarness()
        event = _FakeDragEvent([_FakeUrl("/nonexistent")])
        v.dragMoveEvent(event)
        assert event.ignored


# ═══════════════════════════════════════════════════════════════════════════
#  SLIDER OVERLAY VISIBILITY
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestSliderVisibility:
    def _make_overlay(self, maximum=10, interacting=False):
        overlay = MagicMock()
        overlay.maximum.return_value = maximum
        overlay.is_interacting.return_value = interacting
        overlay.isVisible.return_value = False
        overlay.geometry.return_value.contains.return_value = False
        return overlay

    def test_single_slice_hidden(self, qapp):
        v = _InputHarness()
        v._slider_overlay = self._make_overlay(maximum=1)
        v._update_slider_visibility_from_mouse(QPoint(50, 5))
        v._slider_overlay.reveal.assert_not_called()

    def test_bottom_edge_reveals(self, qapp):
        v = _InputHarness()
        v._slice_slider_placement = "bottom"
        v.viewport().resize(200, 200)
        overlay = self._make_overlay()
        v._slider_overlay = overlay
        # Near bottom edge
        v._update_slider_visibility_from_mouse(QPoint(100, 195))
        overlay.reveal.assert_called_once()

    def test_bottom_edge_far_hides(self, qapp):
        v = _InputHarness()
        v._slice_slider_placement = "bottom"
        v.viewport().resize(200, 200)
        overlay = self._make_overlay()
        overlay.isVisible.return_value = True
        v._slider_overlay = overlay
        v._update_slider_visibility_from_mouse(QPoint(100, 50))
        overlay.schedule_hide.assert_called_once()

    def test_top_placement(self, qapp):
        v = _InputHarness()
        v._slice_slider_placement = "top"
        v.viewport().resize(200, 200)
        overlay = self._make_overlay()
        v._slider_overlay = overlay
        v._update_slider_visibility_from_mouse(QPoint(100, 5))
        overlay.reveal.assert_called_once()

    def test_left_placement(self, qapp):
        v = _InputHarness()
        v._slice_slider_placement = "left"
        v.viewport().resize(200, 200)
        overlay = self._make_overlay()
        v._slider_overlay = overlay
        v._update_slider_visibility_from_mouse(QPoint(5, 100))
        overlay.reveal.assert_called_once()

    def test_right_placement(self, qapp):
        v = _InputHarness()
        v._slice_slider_placement = "right"
        v.viewport().resize(200, 200)
        overlay = self._make_overlay()
        v._slider_overlay = overlay
        v._update_slider_visibility_from_mouse(QPoint(195, 100))
        overlay.reveal.assert_called_once()

    def test_interacting_keeps_visible(self, qapp):
        v = _InputHarness()
        overlay = self._make_overlay(interacting=True)
        v._slider_overlay = overlay
        v._update_slider_visibility_from_mouse(QPoint(100, 100))
        overlay.keep_visible.assert_called_once()

    def test_over_overlay_keeps_visible(self, qapp):
        v = _InputHarness()
        overlay = self._make_overlay()
        overlay.isVisible.return_value = True
        overlay.geometry.return_value.contains.return_value = True
        v._slider_overlay = overlay
        v._update_slider_visibility_from_mouse(QPoint(100, 100))
        overlay.keep_visible.assert_called_once()

    def test_slice_slider_disabled_skips(self, qapp):
        v = _InputHarness()
        v._slice_slider_enabled = False
        overlay = self._make_overlay()
        v._slider_overlay = overlay
        v._update_slider_visibility_from_mouse = MagicMock()
        event = QMouseEvent(
            QMouseEvent.Type.MouseMove,
            QPointF(100, 195),
            QPoint(100, 195),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        v.mouseMoveEvent(event)
        v._update_slider_visibility_from_mouse.assert_not_called()
        assert overlay.mock_calls == []


# ═══════════════════════════════════════════════════════════════════════════
#  EMIT CROSSHAIR
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestEmitCrosshair:
    def test_no_callback_returns(self, qapp):
        v = _InputHarness()
        v.get_current_dataset_callback = None
        crosshair: list = []
        v.crosshair_clicked.connect(lambda *args: crosshair.append(args))
        ImageViewerInputMixin._emit_crosshair(v, QPointF(10, 20))
        assert crosshair == []

    def test_none_dataset_returns(self, qapp):
        v = _InputHarness()
        v.get_current_dataset_callback = lambda: None
        crosshair: list = []
        v.crosshair_clicked.connect(lambda *args: crosshair.append(args))
        ImageViewerInputMixin._emit_crosshair(v, QPointF(10, 20))
        assert crosshair == []

    def test_emits_with_dataset(self, qapp):
        v = _InputHarness()
        v.get_current_dataset_callback = lambda: "dataset"
        v.get_current_slice_index_callback = lambda: 5
        v.get_use_rescaled_values_callback = lambda: False
        crosshair: list = []
        v.crosshair_clicked.connect(lambda *args: crosshair.append(args))
        ImageViewerInputMixin._emit_crosshair(v, QPointF(10, 20))
        assert len(crosshair) == 1
        args = crosshair[0]
        assert args[2] == 10  # x
        assert args[3] == 20  # y
        assert args[4] == 5  # z

    def test_no_slice_callback_z_is_zero(self, qapp):
        v = _InputHarness()
        v.get_current_dataset_callback = lambda: "dataset"
        v.get_current_slice_index_callback = None
        crosshair: list = []
        v.crosshair_clicked.connect(lambda *args: crosshair.append(args))
        ImageViewerInputMixin._emit_crosshair(v, QPointF(10, 20))
        assert crosshair[0][4] == 0

    def test_no_rescaled_callback_uses_false(self, qapp):
        v = _InputHarness()
        v.get_current_dataset_callback = lambda: "dataset"
        v.get_current_slice_index_callback = None
        v.get_use_rescaled_values_callback = None
        seen: list[bool] = []
        v._get_pixel_value_at_coords = (
            lambda dataset, x, y, z, use_rescaled: seen.append(use_rescaled)
            or f"pixel({x},{y},{z})"
        )
        crosshair: list = []
        v.crosshair_clicked.connect(lambda *args: crosshair.append(args))
        ImageViewerInputMixin._emit_crosshair(v, QPointF(10, 20))
        assert crosshair[0][1] == "pixel(10,20,0)"
        assert seen == [False]


# ═══════════════════════════════════════════════════════════════════════════
#  ACTIVATE MAGNIFIER
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestActivateMagnifier:
    def test_re_activation_noop(self, qapp):
        v = _InputHarness()
        v.magnifier_active = True
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        ImageViewerInputMixin._activate_magnifier(v, e, QPointF(10, 10))
        assert v.cursor().shape() != Qt.CursorShape.BlankCursor

    def test_first_activation(self, qapp):
        v = _InputHarness()
        v.magnifier_active = False
        v.magnifier_widget = MagicMock()
        e = _MouseEvent(_pos_x=50, _pos_y=50)
        ImageViewerInputMixin._activate_magnifier(v, e, QPointF(10, 10))
        assert v.magnifier_active is True
        assert v.cursor().shape() == Qt.CursorShape.BlankCursor
        v.magnifier_widget.update_magnified_region.assert_called_once()
        v.magnifier_widget.show_at_position.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════
#  DESELECT ALL ANNOTATION ITEMS
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestDeselectAllAnnotationItems:
    def test_no_scene(self, qapp):
        v = _InputHarness()
        v._scene = None
        # Should not crash
        v._deselect_all_annotation_items()

    def test_clears_selection(self, qapp):
        v = _InputHarness()
        v._deselect_all_annotation_items()
        assert v._scene.selectedItems() == []


# ═══════════════════════════════════════════════════════════════════════════
#  ON SHOW FILE REQUESTED
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestOnShowFileRequested:
    def test_no_callback(self, qapp):
        v = _InputHarness()
        v.get_file_path_callback = None
        v._on_show_file_requested()  # no crash

    def test_none_path(self, qapp):
        v = _InputHarness()
        v.get_file_path_callback = lambda: None
        v._on_show_file_requested()  # no crash

    def test_nonexistent_path(self, qapp):
        v = _InputHarness()
        v.get_file_path_callback = lambda: "/nonexistent/file.txt"
        v._on_show_file_requested()  # no crash


# ═══════════════════════════════════════════════════════════════════════════
#  TOGGLE STATISTIC
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.qt
class TestToggleStatistic:
    def test_delegates_to_context_menu(self, qapp, monkeypatch):
        v = _InputHarness()
        called: list = []
        monkeypatch.setattr(
            "gui.image_viewer_context_menu.toggle_roi_statistic",
            lambda viewer, roi, stat, checked: called.append((roi, stat, checked)),
        )
        v._toggle_statistic("roi", "mean", True)
        assert called == [("roi", "mean", True)]
