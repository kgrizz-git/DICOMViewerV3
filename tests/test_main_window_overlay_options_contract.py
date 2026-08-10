"""
Contract test: MainWindow external API surface referenced outside main_window.py.

Cheap safety net against accidental renames during mixin/controller extractions.
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

from gui.main_window import MainWindow

CONTRACT_METHODS = (
    "show_toast_message",
    "set_fullscreen",
    "update_recent_menu",
    "get_current_mouse_mode",
    "set_mouse_mode_checked",
    "_on_mouse_mode_changed",
    "update_status",
    "update_zoom_preset_status",
    "_set_theme",
    "_apply_theme",
    "set_layout_mode",
    "set_show_instances_separately_enabled",
    "set_3d_view_actions_enabled",
    "set_smooth_when_zoomed_checked",
    "set_scale_markers_checked",
    "set_direction_labels_checked",
    "set_slice_slider_checked",
    "set_show_instances_separately_checked",
    "set_slice_location_lines_checked",
    "set_slice_location_lines_same_group_only_checked",
    "set_slice_location_lines_focused_only_checked",
    "set_slice_location_lines_slab_bounds_checked",
)

CONTRACT_SIGNALS = (
    "privacy_view_toggled",
    "smooth_when_zoomed_toggled",
    "layout_changed",
    "open_file_requested",
    "open_files_from_paths_requested",
    "export_requested",
)


@pytest.mark.parametrize("name", CONTRACT_METHODS)
def test_main_window_contract_method_exists(name: str) -> None:
    assert hasattr(MainWindow, name), f"Missing contract method: {name}"


@pytest.mark.parametrize("name", CONTRACT_SIGNALS)
def test_main_window_contract_signal_exists(name: str) -> None:
    assert hasattr(MainWindow, name), f"Missing contract signal: {name}"
