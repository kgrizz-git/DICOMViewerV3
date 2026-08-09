"""
Characterization tests for MainWindow mouse-mode toolbar QAction exclusivity.

Pins set_mouse_mode_checked / get_current_mouse_mode behavior for all 12 modes
before the action map is extracted.
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
from utils.config_manager import ConfigManager

MOUSE_MODES = (
    "select",
    "roi_ellipse",
    "roi_rectangle",
    "measure",
    "measure_angle",
    "text_annotation",
    "arrow_annotation",
    "crosshair",
    "zoom",
    "magnifier",
    "pan",
    "auto_window_level",
)

MOUSE_MODE_ACTION_ATTRS = (
    "mouse_mode_select_action",
    "mouse_mode_ellipse_roi_action",
    "mouse_mode_rectangle_roi_action",
    "mouse_mode_measure_action",
    "mouse_mode_measure_angle_action",
    "mouse_mode_text_annotation_action",
    "mouse_mode_arrow_annotation_action",
    "mouse_mode_crosshair_action",
    "mouse_mode_zoom_action",
    "mouse_mode_magnifier_action",
    "mouse_mode_pan_action",
    "mouse_mode_auto_window_level_action",
)


@pytest.mark.qt
@pytest.mark.parametrize("mode", MOUSE_MODES)
def test_set_mouse_mode_checked_exactly_one_action_and_get_current(qapp, tmp_path, mode):
    w = MainWindow(ConfigManager(config_dir=tmp_path / "config"))
    w.set_mouse_mode_checked(mode)

    actions = [getattr(w, attr) for attr in MOUSE_MODE_ACTION_ATTRS]
    checked_actions = [action for action in actions if action.isChecked()]

    assert len(checked_actions) == 1
    assert w.get_current_mouse_mode() == mode
    w.close()
