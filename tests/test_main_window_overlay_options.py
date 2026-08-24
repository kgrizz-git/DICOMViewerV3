"""
Characterization tests for MainWindow overlay / view-option sync helpers.

Pins current behavior: set_*_checked syncs QAction state without emitting;
_on_*_toggled handlers emit the corresponding signals.
"""

from __future__ import annotations

import os
import sys

import pytest

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src = os.path.join(_project_root, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

pytest.importorskip("PySide6")

from qt_widget_scope import widget_scope

from gui.main_window import MainWindow
from utils.config_manager import ConfigManager

_DEFAULT_3D_TIP = "Open 3D Volume Render of current series"


@pytest.fixture(autouse=True)
def _destroy_leaked_windows():
    """Destroy windows this module's tests create (see ``qt_widget_scope``)."""
    with widget_scope():
        yield


@pytest.fixture
def main_window(qapp, tmp_path):
    return MainWindow(ConfigManager(config_dir=tmp_path / "config"))


def _spy_signal(window, signal_name: str) -> list:
    emitted: list = []
    getattr(window, signal_name).connect(emitted.append)
    return emitted


@pytest.mark.qt
def test_set_smooth_when_zoomed_checked_syncs_without_emitting(main_window):
    emitted = _spy_signal(main_window, "smooth_when_zoomed_toggled")
    initial = main_window.smooth_when_zoomed_action.isChecked()

    main_window.set_smooth_when_zoomed_checked(not initial)
    assert main_window.smooth_when_zoomed_action.isChecked() is (not initial)
    assert emitted == []

    main_window._on_smooth_when_zoomed_toggled(not initial)
    assert emitted == [not initial]


@pytest.mark.qt
def test_set_scale_markers_checked_syncs_without_emitting(main_window):
    emitted = _spy_signal(main_window, "scale_markers_toggled")
    initial = main_window.scale_markers_action.isChecked()

    main_window.set_scale_markers_checked(not initial)
    assert main_window.scale_markers_action.isChecked() is (not initial)
    assert emitted == []

    main_window._on_scale_markers_toggled(not initial)
    assert emitted == [not initial]


@pytest.mark.qt
def test_set_direction_labels_checked_syncs_without_emitting(main_window):
    emitted = _spy_signal(main_window, "direction_labels_toggled")
    initial = main_window.direction_labels_action.isChecked()

    main_window.set_direction_labels_checked(not initial)
    assert main_window.direction_labels_action.isChecked() is (not initial)
    assert emitted == []

    main_window._on_direction_labels_toggled(not initial)
    assert emitted == [not initial]


@pytest.mark.qt
def test_set_show_instances_separately_checked_syncs_without_emitting(main_window):
    emitted = _spy_signal(main_window, "show_instances_separately_toggled")
    initial = main_window.show_instances_separately_action.isChecked()

    main_window.set_show_instances_separately_checked(not initial)
    assert main_window.show_instances_separately_action.isChecked() is (not initial)
    assert emitted == []

    main_window._on_show_instances_separately_toggled(not initial)
    assert emitted == [not initial]


@pytest.mark.qt
def test_set_slice_location_lines_checked_syncs_without_emitting(main_window):
    emitted = _spy_signal(main_window, "slice_location_lines_toggled")
    initial = main_window.slice_location_lines_enable_action.isChecked()

    main_window.set_slice_location_lines_checked(not initial)
    assert main_window.slice_location_lines_enable_action.isChecked() is (not initial)
    assert emitted == []

    main_window.slice_location_lines_enable_action.trigger()
    assert emitted == [initial]


@pytest.mark.qt
def test_set_slice_location_lines_same_group_only_checked_syncs_without_emitting(
    main_window,
):
    emitted = _spy_signal(main_window, "slice_location_lines_same_group_only_toggled")
    initial = main_window.slice_location_lines_same_group_only_action.isChecked()

    main_window.set_slice_location_lines_same_group_only_checked(not initial)
    assert (
        main_window.slice_location_lines_same_group_only_action.isChecked()
        is (not initial)
    )
    assert emitted == []

    main_window.slice_location_lines_same_group_only_action.trigger()
    assert emitted == [initial]


@pytest.mark.qt
def test_set_slice_location_lines_focused_only_checked_syncs_without_emitting(
    main_window,
):
    emitted = _spy_signal(main_window, "slice_location_lines_focused_only_toggled")
    initial = main_window.slice_location_lines_focused_only_action.isChecked()

    main_window.set_slice_location_lines_focused_only_checked(not initial)
    assert (
        main_window.slice_location_lines_focused_only_action.isChecked()
        is (not initial)
    )
    assert emitted == []

    main_window.slice_location_lines_focused_only_action.trigger()
    assert emitted == [initial]


@pytest.mark.qt
def test_set_slice_location_lines_slab_bounds_checked_syncs_without_emitting(
    main_window,
):
    emitted = _spy_signal(main_window, "slice_location_lines_mode_toggled")
    action = main_window.slice_location_lines_show_slab_bounds_action

    main_window.set_slice_location_lines_slab_bounds_checked("begin_end")
    assert action.isChecked() is True
    assert emitted == []

    main_window.set_slice_location_lines_slab_bounds_checked("middle")
    assert action.isChecked() is False
    assert emitted == []

    action.setChecked(False)
    action.trigger()
    assert emitted == ["begin_end"]


@pytest.mark.qt
def test_privacy_handlers_emit_privacy_view_toggled(main_window):
    emitted = _spy_signal(main_window, "privacy_view_toggled")

    main_window._on_privacy_toggled(True)
    assert emitted == [True]

    main_window._on_privacy_view_toggled(False)
    assert emitted == [True, False]
    assert main_window.privacy_action.isChecked() is False


@pytest.mark.qt
def test_adjust_overlay_font_size_round_trip(main_window):
    original = main_window.config_manager.get_overlay_font_size()

    main_window.adjust_overlay_font_size(1)
    assert main_window.config_manager.get_overlay_font_size() == min(24, original + 1)

    main_window.adjust_overlay_font_size(-1)
    assert main_window.config_manager.get_overlay_font_size() == original


@pytest.mark.qt
def test_set_3d_view_actions_enabled_toggles_tooltip(main_window):
    assert main_window.view_3d_action is not None
    assert main_window.create_3d_action is not None

    main_window.set_3d_view_actions_enabled(False, "why")
    assert main_window.view_3d_action.isEnabled() is False
    assert main_window.create_3d_action.isEnabled() is False
    assert main_window.view_3d_action.toolTip() == "why"
    assert main_window.create_3d_action.toolTip() == "why"
    assert main_window.create_3d_action.statusTip() == "why"

    custom = "Series ready for 3D"
    main_window.set_3d_view_actions_enabled(True, custom)
    assert main_window.view_3d_action.isEnabled() is True
    assert main_window.create_3d_action.isEnabled() is True
    assert main_window.view_3d_action.toolTip() == custom
    assert main_window.create_3d_action.toolTip() == custom

    main_window.set_3d_view_actions_enabled(True, "")
    assert main_window.view_3d_action.toolTip() == _DEFAULT_3D_TIP
    assert main_window.create_3d_action.toolTip() == _DEFAULT_3D_TIP
