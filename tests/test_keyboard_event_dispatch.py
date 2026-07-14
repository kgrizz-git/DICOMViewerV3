"""
Characterization tests for KeyboardEventHandler.handle_key_event.

These pin the full key/modifier dispatch table so it can be refactored without
behaviour drift. Non-obvious invariants captured here:

  - Ctrl/Cmd is a passthrough (return False) for most keys, so Qt can route the
    combo to the menu QActions -- including Ctrl+P (Privacy) and Ctrl/Cmd+Shift+H
    (Histogram), which this handler deliberately does NOT own.
  - G, I and Space have NO Ctrl/Cmd guard: they consume the key regardless.
  - The "a text annotation is being edited" guard applies to the arrow keys AND
    to the layout digits 1-4.
  - N and I return True even when their callback is None.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from gui.keyboard_event_handler import KeyboardEventHandler
from tools.angle_measurement_items import AngleMeasurementItem
from tools.arrow_annotation_tool import ArrowAnnotationItem
from tools.measurement_items import MeasurementItem
from tools.text_annotation_tool import TextAnnotationItem

CTRL = Qt.KeyboardModifier.ControlModifier
META = Qt.KeyboardModifier.MetaModifier
SHIFT = Qt.KeyboardModifier.ShiftModifier
NONE = Qt.KeyboardModifier.NoModifier


class _Scene:
    def __init__(self, selected=None, items=None):
        self._selected = selected or []
        self._items = items or []

    def selectedItems(self):
        return self._selected

    def items(self):
        return self._items


class _Viewer:
    def __init__(self, scene=None, mouse_mode="pan"):
        self.scene = scene if scene is not None else _Scene()
        self.mouse_mode = mouse_mode


class _Nav:
    def __init__(self, calls):
        self._calls = calls

    def next_slice(self):
        self._calls.append("next_slice")

    def previous_slice(self):
        self._calls.append("previous_slice")


def _make(calls, *, viewer=None, selected_roi=None, focus_ok=True, **overrides):
    """Build a handler whose callbacks append their name to ``calls``."""
    def cb(name, ret=None):
        def _fn(*args):
            calls.append(name)
            return ret
        return _fn

    kwargs: dict[str, Any] = {
        "roi_manager": None,
        "measurement_tool": None,
        "slice_navigator": _Nav(calls),
        "overlay_manager": None,
        "image_viewer": viewer if viewer is not None else _Viewer(),
        "set_mouse_mode": lambda mode: calls.append(f"mode:{mode}"),
        "delete_all_rois_callback": cb("delete_all_rois"),
        "clear_measurements_callback": cb("clear_measurements"),
        "toggle_overlay_callback": cb("toggle_overlay"),
        "cycle_overlay_detail_callback": cb("cycle_overlay_detail"),
        "toggle_overlay_visibility_legacy_callback": cb("legacy_overlay"),
        "get_selected_roi": lambda: selected_roi,
        "delete_roi_callback": cb("delete_roi"),
        "delete_measurement_callback": cb("delete_measurement"),
        "update_roi_list_callback": cb("update_roi_list"),
        "clear_roi_statistics_callback": cb("clear_roi_statistics"),
        "reset_view_callback": cb("reset_view"),
        "toggle_series_navigator_callback": cb("toggle_series_navigator"),
        "invert_image_callback": cb("invert_image"),
        "reset_all_views_callback": cb("reset_all_views"),
        "delete_text_annotation_callback": cb("delete_text_annotation"),
        "delete_arrow_annotation_callback": cb("delete_arrow_annotation"),
        "change_layout_callback": lambda mode: calls.append(f"layout:{mode}"),
        "cycle_three_pane_layout_callback": cb("cycle_three_pane"),
        "toggle_two_pane_layout_callback": cb("toggle_two_pane"),
        "is_focus_ok_for_reset_view": lambda: focus_ok,
        "open_quick_window_level_callback": cb("quick_window_level"),
        "cancel_angle_draw_callback": cb("cancel_angle_draw"),
        "exit_roi_geometry_edit_callback": cb("exit_roi_geometry_edit", ret=False),
    }
    kwargs.update(overrides)
    return KeyboardEventHandler(**kwargs)  # type: ignore[arg-type]


def _key(key, modifiers=NONE, type_=QEvent.Type.KeyPress):
    return QKeyEvent(type_, key, modifiers)


def _press(handler, key, modifiers=NONE):
    return handler.handle_key_event(_key(key, modifiers))


# --- event type -------------------------------------------------------------

def test_non_keypress_event_is_ignored():
    calls: list[str] = []
    h = _make(calls)
    assert h.handle_key_event(_key(Qt.Key.Key_P, NONE, QEvent.Type.KeyRelease)) is False
    assert calls == []


def test_unbound_key_returns_false():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_F9) is False
    assert calls == []


# --- mouse-mode keys with Ctrl/Cmd passthrough ------------------------------

MODE_KEYS = [
    (Qt.Key.Key_P, "pan"),
    (Qt.Key.Key_Z, "zoom"),
    (Qt.Key.Key_M, "measure"),
    (Qt.Key.Key_S, "select"),
    (Qt.Key.Key_W, "auto_window_level"),
    (Qt.Key.Key_R, "roi_rectangle"),
    (Qt.Key.Key_E, "roi_ellipse"),
    (Qt.Key.Key_H, "crosshair"),
    (Qt.Key.Key_A, "arrow_annotation"),
    (Qt.Key.Key_T, "text_annotation"),
]


@pytest.mark.parametrize(("key", "mode"), MODE_KEYS)
def test_plain_key_sets_mouse_mode(key, mode):
    calls: list[str] = []
    assert _press(_make(calls), key) is True
    assert calls == [f"mode:{mode}"]


@pytest.mark.parametrize(("key", "mode"), MODE_KEYS)
@pytest.mark.parametrize("mod", [CTRL, META])
def test_ctrl_cmd_passes_through_for_mode_keys(key, mode, mod):
    calls: list[str] = []
    assert _press(_make(calls), key, mod) is False
    assert calls == []


def test_g_has_no_ctrl_guard_and_always_sets_magnifier():
    for mod in (NONE, CTRL, META):
        calls: list[str] = []
        assert _press(_make(calls), Qt.Key.Key_G, mod) is True
        assert calls == ["mode:magnifier"]


def test_shift_m_selects_angle_measure():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_M, SHIFT) is True
    assert calls == ["mode:measure_angle"]


# --- action keys ------------------------------------------------------------

def test_c_clears_measurements():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_C) is True
    assert calls == ["clear_measurements"]


def test_d_deletes_all_rois():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_D) is True
    assert calls == ["delete_all_rois"]


def test_i_inverts_image_and_has_no_ctrl_guard():
    for mod in (NONE, CTRL, META):
        calls: list[str] = []
        assert _press(_make(calls), Qt.Key.Key_I, mod) is True
        assert calls == ["invert_image"]


def test_i_returns_true_even_without_callback():
    calls: list[str] = []
    h = _make(calls, invert_image_callback=None)
    assert _press(h, Qt.Key.Key_I) is True
    assert calls == []


def test_n_toggles_series_navigator():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_N) is True
    assert calls == ["toggle_series_navigator"]


def test_n_returns_true_even_without_callback():
    calls: list[str] = []
    h = _make(calls, toggle_series_navigator_callback=None)
    assert _press(h, Qt.Key.Key_N) is True
    assert calls == []


# --- V (reset view) ---------------------------------------------------------

def test_shift_v_resets_view_regardless_of_focus():
    calls: list[str] = []
    h = _make(calls, focus_ok=False)
    assert _press(h, Qt.Key.Key_V, SHIFT) is True
    assert calls == ["reset_view"]


def test_plain_v_resets_view_when_focus_ok():
    calls: list[str] = []
    assert _press(_make(calls, focus_ok=True), Qt.Key.Key_V) is True
    assert calls == ["reset_view"]


def test_plain_v_is_not_handled_when_focus_not_ok():
    calls: list[str] = []
    assert _press(_make(calls, focus_ok=False), Qt.Key.Key_V) is False
    assert calls == []


# --- Q (quick window/level) -------------------------------------------------

def test_q_opens_quick_window_level_when_focus_ok():
    calls: list[str] = []
    assert _press(_make(calls, focus_ok=True), Qt.Key.Key_Q) is True
    assert calls == ["quick_window_level"]


def test_q_is_not_handled_when_focus_not_ok():
    calls: list[str] = []
    assert _press(_make(calls, focus_ok=False), Qt.Key.Key_Q) is False
    assert calls == []


@pytest.mark.parametrize("mod", [CTRL, META])
def test_ctrl_q_passes_through(mod):
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_Q, mod) is False
    assert calls == []


# --- Shift+A ----------------------------------------------------------------

def test_shift_a_resets_all_views():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_A, SHIFT) is True
    assert calls == ["reset_all_views"]


# --- Space ------------------------------------------------------------------

def test_space_cycles_overlay_detail():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_Space) is True
    assert calls == ["cycle_overlay_detail"]


def test_shift_space_uses_legacy_cycle():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_Space, SHIFT) is True
    assert calls == ["legacy_overlay"]


def test_space_falls_back_to_toggle_overlay_without_cycle_callback():
    calls: list[str] = []
    h = _make(calls, cycle_overlay_detail_callback=None)
    assert _press(h, Qt.Key.Key_Space) is True
    assert calls == ["toggle_overlay"]


def test_shift_space_falls_back_to_toggle_overlay_without_legacy_callback():
    calls: list[str] = []
    h = _make(calls, toggle_overlay_visibility_legacy_callback=None)
    assert _press(h, Qt.Key.Key_Space, SHIFT) is True
    assert calls == ["toggle_overlay"]


def test_space_has_no_ctrl_guard():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_Space, CTRL) is True
    assert calls == ["cycle_overlay_detail"]


# --- Escape -----------------------------------------------------------------

def test_escape_cancels_angle_draw_in_measure_angle_mode():
    calls: list[str] = []
    h = _make(calls, viewer=_Viewer(mouse_mode="measure_angle"))
    assert _press(h, Qt.Key.Key_Escape) is True
    assert calls == ["cancel_angle_draw"]


def test_escape_exits_roi_geometry_edit_when_that_handler_claims_it():
    calls: list[str] = []
    h = _make(calls, exit_roi_geometry_edit_callback=lambda: True)
    assert _press(h, Qt.Key.Key_Escape) is True


def test_escape_falls_through_when_nothing_to_cancel():
    calls: list[str] = []
    h = _make(calls)
    assert _press(h, Qt.Key.Key_Escape) is False
    assert calls == ["exit_roi_geometry_edit"]


# --- Delete / Backspace -----------------------------------------------------

@pytest.mark.parametrize("key", [Qt.Key.Key_Delete, Qt.Key.Key_Backspace])
def test_delete_removes_selected_roi_first(key):
    calls: list[str] = []
    h = _make(calls, selected_roi=object())
    assert _press(h, key) is True
    assert calls == ["delete_roi", "update_roi_list", "clear_roi_statistics"]


@pytest.mark.parametrize("cls", [MeasurementItem, AngleMeasurementItem])
def test_delete_removes_selected_measurement(cls):
    calls: list[str] = []
    item = MagicMock(spec=cls)
    h = _make(calls, viewer=_Viewer(_Scene(selected=[item])))
    assert _press(h, Qt.Key.Key_Delete) is True
    assert calls == ["delete_measurement"]


def test_delete_removes_selected_text_annotation():
    calls: list[str] = []
    item = MagicMock(spec=TextAnnotationItem)
    h = _make(calls, viewer=_Viewer(_Scene(selected=[item])))
    assert _press(h, Qt.Key.Key_Delete) is True
    assert calls == ["delete_text_annotation"]


def test_delete_removes_selected_arrow_annotation():
    calls: list[str] = []
    item = MagicMock(spec=ArrowAnnotationItem)
    h = _make(calls, viewer=_Viewer(_Scene(selected=[item])))
    assert _press(h, Qt.Key.Key_Delete) is True
    assert calls == ["delete_arrow_annotation"]


def test_delete_with_nothing_selected_is_not_handled():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_Delete) is False
    assert calls == []


def test_delete_tolerates_deleted_scene():
    class _Boom:
        def selectedItems(self):
            raise RuntimeError("scene deleted")

        def items(self):
            return []

    calls: list[str] = []
    h = _make(calls, viewer=_Viewer(_Boom()))
    assert _press(h, Qt.Key.Key_Delete) is False


# --- arrow navigation -------------------------------------------------------

def test_up_arrow_goes_to_next_slice():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_Up) is True
    assert calls == ["next_slice"]


def test_down_arrow_goes_to_previous_slice():
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_Down) is True
    assert calls == ["previous_slice"]


def _editing_scene():
    editing = MagicMock(spec=TextAnnotationItem)
    editing._editing = True
    return _Scene(items=[editing])


@pytest.mark.parametrize("key", [Qt.Key.Key_Up, Qt.Key.Key_Down])
def test_arrow_keys_defer_to_text_editor_while_editing(key):
    calls: list[str] = []
    h = _make(calls, viewer=_Viewer(_editing_scene()))
    assert _press(h, key) is False
    assert calls == []


# --- layout digits ----------------------------------------------------------

def test_layout_digits():
    for key, expected in [
        (Qt.Key.Key_1, "layout:1x1"),
        (Qt.Key.Key_2, "toggle_two_pane"),
        (Qt.Key.Key_3, "cycle_three_pane"),
        (Qt.Key.Key_4, "layout:2x2"),
    ]:
        calls: list[str] = []
        assert _press(_make(calls), key) is True
        assert calls == [expected]


@pytest.mark.parametrize(
    "key", [Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4]
)
@pytest.mark.parametrize("mod", [CTRL, META])
def test_ctrl_cmd_passes_through_for_layout_digits(key, mod):
    calls: list[str] = []
    assert _press(_make(calls), key, mod) is False
    assert calls == []


@pytest.mark.parametrize(
    "key", [Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4]
)
def test_layout_digits_defer_to_text_editor_while_editing(key):
    calls: list[str] = []
    h = _make(calls, viewer=_Viewer(_editing_scene()))
    assert _press(h, key) is False
    assert calls == []


def test_layout_digits_are_consumed_even_without_callbacks():
    calls: list[str] = []
    h = _make(calls, change_layout_callback=None, toggle_two_pane_layout_callback=None)
    assert _press(h, Qt.Key.Key_1) is True
    assert _press(h, Qt.Key.Key_2) is True
    assert calls == []


# --- shortcuts this handler must NOT own ------------------------------------

@pytest.mark.parametrize("mod", [CTRL, META])
def test_ctrl_p_is_left_to_the_privacy_menu_action(mod):
    """Ctrl/Cmd+P must pass through to the QAction in main_window."""
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_P, mod) is False
    assert calls == []


@pytest.mark.parametrize("mod", [CTRL, META])
def test_ctrl_shift_h_is_left_to_the_histogram_menu_action(mod):
    """Ctrl/Cmd+Shift+H must pass through to the Tools-menu QAction."""
    calls: list[str] = []
    assert _press(_make(calls), Qt.Key.Key_H, mod | SHIFT) is False
    assert calls == []
