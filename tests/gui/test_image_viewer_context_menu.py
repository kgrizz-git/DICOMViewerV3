"""Focused tests for gui.image_viewer_context_menu."""

from __future__ import annotations

from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QGraphicsRectItem

import gui.image_viewer_context_menu as image_viewer_context_menu


class _FakeSignal:
    def __init__(self) -> None:
        self.calls = []

    def connect(self, callback):
        self.calls.append(callback)

    def emit(self, *args):
        self.calls.append(args)


class _FakeAction:
    def __init__(self, text: str) -> None:
        self.text = text
        self.triggered = _FakeSignal()
        self.checkable = False
        self.checked = False
        self.enabled = True
        self.visible = True
        self.tooltip = ""

    def setCheckable(self, value: bool) -> None:
        self.checkable = value

    def setChecked(self, value: bool) -> None:
        self.checked = value

    def setEnabled(self, value: bool) -> None:
        self.enabled = value

    def setVisible(self, value: bool) -> None:
        self.visible = value

    def setToolTip(self, value: str) -> None:
        self.tooltip = value


class _FakeMenu:
    instances: ClassVar[list[_FakeMenu]] = []

    def __init__(self, _parent=None) -> None:
        self.actions: list[_FakeAction] = []
        self.submenus: list[tuple[str, _FakeMenu]] = []
        self.enabled = True
        _FakeMenu.instances.append(self)

    def addAction(self, text: str) -> _FakeAction:
        action = _FakeAction(text)
        self.actions.append(action)
        return action

    def addSeparator(self):
        return None

    def addMenu(self, text: str):
        menu = _FakeMenu()
        self.submenus.append((text, menu))
        return menu

    def setEnabled(self, value: bool) -> None:
        self.enabled = value

    def exec(self, _pos):
        return None


def _require_submenu(menu: _FakeMenu, label: str) -> _FakeMenu:
    """Return the named submenu, or fail the test if it is missing.

    Uses ``next(..., None)`` so a missing label becomes an assertion failure
    instead of an uncaught ``StopIteration`` (DeepSource PTC-W0063).
    """
    found = next((submenu for name, submenu in menu.submenus if name == label), None)
    assert found is not None, f"missing submenu {label!r}"
    return found


def _require_action(menu: _FakeMenu, text: str) -> _FakeAction:
    """Return the named action, or fail the test if it is missing."""
    found = next((action for action in menu.actions if action.text == text), None)
    assert found is not None, f"missing action {text!r}"
    return found


class _FakeActionGroup:
    def __init__(self, _parent=None) -> None:
        self.actions = []
        self.exclusive = False

    def setExclusive(self, value: bool) -> None:
        self.exclusive = value

    def addAction(self, action) -> None:
        self.actions.append(action)


def _event() -> QMouseEvent:
    return QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(3, 4),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )


def _make_viewer(**overrides):
    defaults = {
        "mapToScene": lambda p: p,
        "scene": SimpleNamespace(itemAt=MagicMock(return_value=None)),
        "transform": lambda: None,
        "roi_statistics_selection_changed": _FakeSignal(),
        "roi_delete_requested": _FakeSignal(),
        "measurement_delete_requested": _FakeSignal(),
        "text_annotation_delete_requested": _FakeSignal(),
        "arrow_annotation_delete_requested": _FakeSignal(),
        "crosshair_delete_requested": _FakeSignal(),
        "annotation_options_requested": _FakeSignal(),
        "roi_statistics_overlay_toggle_requested": _FakeSignal(),
        "_toggle_statistic": MagicMock(),
        "get_roi_from_item_callback": None,
        "delete_all_rois_callback": MagicMock(),
        "right_mouse_context_menu_shown": False,
        "right_mouse_drag_start_pos": None,
        "right_mouse_press_for_drag": _FakeSignal(),
        "image_item": object(),
        "reset_view_requested": _FakeSignal(),
        "reset_all_views_requested": _FakeSignal(),
        "flip_h": MagicMock(),
        "flip_v": MagicMock(),
        "rotate_cw": MagicMock(),
        "rotate_ccw": MagicMock(),
        "rotate_180": MagicMock(),
        "reset_orientation": MagicMock(),
        "layout_change_requested": _FakeSignal(),
        "subwindow_index": 0,
        "window_slot_map_popup_requested": _FakeSignal(),
        "get_slot_to_view_callback": MagicMock(return_value=[0, 1, 2, 3]),
        "swap_view_requested": _FakeSignal(),
        "get_clear_this_window_enabled_callback": MagicMock(return_value=True),
        "clear_window_content_requested": _FakeSignal(),
        "series_navigation_requested": _FakeSignal(),
        "get_available_series_callback": MagicMock(return_value=[("s1", "Series 1")]),
        "assign_series_requested": _FakeSignal(),
        "is_mpr_view_callback": MagicMock(return_value=False),
        "clear_mpr_view_requested": _FakeSignal(),
        "create_mpr_view_requested": _FakeSignal(),
        "get_3d_volume_render_enabled_callback": MagicMock(return_value=True),
        "create_3d_view_requested": _FakeSignal(),
        "_mpr_mode_override": False,
        "mouse_mode": "pan",
        "context_menu_mouse_mode_changed": _FakeSignal(),
        "clear_measurements_requested": _FakeSignal(),
        "export_roi_statistics_requested": _FakeSignal(),
        "toggle_overlay_requested": _FakeSignal(),
        "_privacy_view_enabled": True,
        "privacy_view_toggled": _FakeSignal(),
        "_smooth_when_zoomed": True,
        "smooth_when_zoomed_toggled": _FakeSignal(),
        "_show_scale_markers": True,
        "scale_markers_toggled": _FakeSignal(),
        "_show_direction_labels": False,
        "direction_labels_toggled": _FakeSignal(),
        "overlay_config_requested": _FakeSignal(),
        "overlay_settings_requested": _FakeSignal(),
        "_slice_sync_enabled": True,
        "slice_sync_toggled": _FakeSignal(),
        "slice_sync_manage_requested": _FakeSignal(),
        "get_slice_location_lines_visible_callback": MagicMock(return_value=True),
        "get_slice_location_lines_same_group_only_callback": MagicMock(return_value=False),
        "get_slice_location_lines_focused_only_callback": MagicMock(return_value=True),
        "get_slice_location_lines_mode_callback": MagicMock(return_value="begin_end"),
        "slice_location_lines_toggled": _FakeSignal(),
        "slice_location_lines_same_group_only_toggled": _FakeSignal(),
        "slice_location_lines_focused_only_toggled": _FakeSignal(),
        "slice_location_lines_mode_toggled": _FakeSignal(),
        "left_pane_toggle_requested": _FakeSignal(),
        "right_pane_toggle_requested": _FakeSignal(),
        "toggle_series_navigator_requested": _FakeSignal(),
        "get_wl_preset_menu_context_callback": None,
        "manage_wl_presets_callback": None,
        "get_window_level_presets_callback": MagicMock(return_value=[]),
        "quick_window_level_requested": _FakeSignal(),
        "image_inverted": False,
        "invert_image": MagicMock(),
        "use_rescaled_values": True,
        "context_menu_rescale_toggle_changed": _FakeSignal(),
        "scroll_wheel_mode": "slice",
        "context_menu_scroll_wheel_mode_changed": _FakeSignal(),
        "get_projection_enabled_callback": MagicMock(return_value=True),
        "projection_enabled_changed": _FakeSignal(),
        "get_projection_type_callback": MagicMock(return_value="mip"),
        "projection_type_changed": _FakeSignal(),
        "get_projection_slice_count_callback": MagicMock(return_value=4),
        "projection_slice_count_changed": _FakeSignal(),
        "cine_controls_enabled": True,
        "get_cine_is_playing_callback": MagicMock(return_value=True),
        "cine_play_pause_toggle_requested": _FakeSignal(),
        "cine_stop_requested": _FakeSignal(),
        "get_cine_loop_state_callback": MagicMock(return_value=False),
        "cine_loop_toggled": _FakeSignal(),
        "histogram_requested": _FakeSignal(),
        "get_current_dataset_callback": MagicMock(return_value=object()),
        "structured_report_browser_requested": _FakeSignal(),
        "about_this_file_requested": _FakeSignal(),
        "get_file_path_callback": MagicMock(return_value="/tmp/file.dcm"),
        "_on_show_file_requested": MagicMock(),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _install_fake_menu_patches(monkeypatch) -> None:
    _FakeMenu.instances.clear()
    monkeypatch.setattr(image_viewer_context_menu, "QMenu", _FakeMenu)
    monkeypatch.setattr("PySide6.QtWidgets.QMenu", _FakeMenu)
    monkeypatch.setattr("PySide6.QtGui.QActionGroup", _FakeActionGroup)
    monkeypatch.setattr(
        "gui.wl_preset_menu.populate_wl_preset_menu",
        lambda menu, ctx, on_select, on_manage=None: menu.addAction("Preset"),
    )
    monkeypatch.setattr(
        "gui.wl_preset_menu.context_from_legacy_presets",
        lambda presets, current_index=0: SimpleNamespace(preset_objects=presets, current_index=current_index),
    )
    monkeypatch.setattr(
        "core.sr_sop_classes.is_structured_report_dataset",
        lambda _ds: True,
    )


def test_toggle_roi_statistic_adds_and_removes_entry() -> None:
    viewer = _make_viewer()
    roi = SimpleNamespace(visible_statistics={"mean"})

    image_viewer_context_menu.toggle_roi_statistic(viewer, roi, "std", True)
    image_viewer_context_menu.toggle_roi_statistic(viewer, roi, "mean", False)

    assert roi.visible_statistics == {"std"}
    assert viewer.roi_statistics_selection_changed.calls[-1] == (roi, {"std"})


@pytest.mark.qt
def test_handle_mouse_press_right_button_on_roi_builds_roi_menu(monkeypatch, qapp) -> None:
    _install_fake_menu_patches(monkeypatch)
    roi = SimpleNamespace(statistics_overlay_visible=True, visible_statistics={"mean", "count"})
    viewer = _make_viewer(
        scene=SimpleNamespace(itemAt=MagicMock(return_value=QGraphicsRectItem())),
        get_roi_from_item_callback=MagicMock(return_value=roi),
    )

    image_viewer_context_menu.handle_mouse_press_right_button(viewer, _event())

    assert viewer.right_mouse_context_menu_shown is True
    menu = _FakeMenu.instances[0]
    assert [action.text for action in menu.actions[:2]] == ["Delete ROI", "Delete all ROIs (D)"]
    stats_menu = _require_submenu(menu, "Statistics Overlay")
    stat_labels = [action.text for action in stats_menu.actions]
    assert "Show Statistics Overlay" in stat_labels
    assert "Show Mean" in stat_labels
    assert "Show Pixels" in stat_labels


@pytest.mark.qt
def test_handle_mouse_press_right_button_on_background_prepares_drag(monkeypatch, qapp) -> None:
    _install_fake_menu_patches(monkeypatch)
    viewer = _make_viewer()

    image_viewer_context_menu.handle_mouse_press_right_button(viewer, _event())

    assert viewer.right_mouse_context_menu_shown is False
    assert viewer.right_mouse_drag_start_pos == QPointF(3, 4)
    assert viewer.right_mouse_press_for_drag.calls[-1] == ()


@pytest.mark.qt
def test_show_image_background_context_menu_on_right_release_builds_full_menu(monkeypatch, qapp) -> None:
    _install_fake_menu_patches(monkeypatch)
    viewer = _make_viewer()

    image_viewer_context_menu.show_image_background_context_menu_on_right_release(viewer, _event())

    root = _FakeMenu.instances[0]
    root_labels = [action.text for action in root.actions]
    submenu_labels = [label for label, _submenu in root.submenus]
    assert "Reset View (V, Shift+V)" in root_labels
    assert "Prev Series (←)" in root_labels
    assert "3D Volume Render…" in root_labels
    assert "Quick Window/Level (Q)" in root_labels
    assert "Histogram (Ctrl+Shift+H)" in root_labels or "Histogram (Cmd+Shift+H)" in root_labels
    assert "Orientation" in submenu_labels
    assert "Layout" in submenu_labels
    assert "Tools" in submenu_labels
    assert "Annotations" in submenu_labels
    assert "Combine Slices…" in submenu_labels
    assert "Scroll Wheel Mode" in submenu_labels
    assert "Slice Sync" in submenu_labels

    assign_menu = _require_submenu(root, "Assign Series to Focused Window")
    assert [action.text for action in assign_menu.actions] == ["Series 1"]

    combine_menu = _require_submenu(root, "Combine Slices…")
    projection_type_menu = _require_submenu(combine_menu, "Projection Type")
    assert [action.text for action in projection_type_menu.actions] == ["Average (AIP)", "Maximum (MIP)", "Minimum (MinIP)"]


@pytest.mark.qt
def test_show_image_background_context_menu_handles_disabled_callbacks_and_mpr_override(monkeypatch, qapp) -> None:
    _install_fake_menu_patches(monkeypatch)
    viewer = _make_viewer(
        subwindow_index=None,
        get_available_series_callback=None,
        is_mpr_view_callback=MagicMock(return_value=True),
        get_3d_volume_render_enabled_callback=MagicMock(side_effect=RuntimeError("nope")),
        _mpr_mode_override=True,
        get_file_path_callback=MagicMock(side_effect=RuntimeError("missing")),
        cine_controls_enabled=False,
        get_current_dataset_callback=MagicMock(side_effect=RuntimeError("bad")),
        get_wl_preset_menu_context_callback=lambda: None,
        manage_wl_presets_callback=MagicMock(),
    )

    image_viewer_context_menu.show_image_background_context_menu_on_right_release(viewer, _event())

    root = _FakeMenu.instances[0]
    root_labels = [action.text for action in root.actions]
    assert "Clear MPR View" in root_labels
    assert "3D Volume Render…" in root_labels
    view_3d = _require_action(root, "3D Volume Render…")
    assert view_3d.enabled is False
    sr_action = _require_action(root, "Structured Report…")
    assert sr_action.visible is False
    show_file = _require_action(root, "Show File in File Explorer")
    assert show_file.enabled is False
    tools_menu = _require_submenu(root, "Tools")
    crosshair_action = _require_action(tools_menu, "Crosshair ROI (H)")
    assert crosshair_action.enabled is False
