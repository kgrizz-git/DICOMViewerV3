"""
Tests for MainWindow.show_toast_message placement and background alpha.

Headless QApplication; does not depend on platform compositing.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src = os.path.join(_project_root, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from gui.main_window import MainWindow  # noqa: E402
from utils.config_manager import ConfigManager  # noqa: E402


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


@pytest.mark.qt
def test_toast_bottom_center_default_alpha(qapp):
    w = MainWindow(ConfigManager())
    w.resize(800, 600)
    w.show_toast_message("hello", timeout_ms=999_999)
    label = w._toast_label
    assert label is not None
    x = (w.width() - label.width()) // 2
    y = w.height() - 100
    assert label.x() == max(0, x)
    assert label.y() == max(0, y)
    ss = label.styleSheet()
    assert re.search(r"rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.75\s*\)", ss, re.I)


@pytest.mark.qt
def test_toast_center_placement_and_alpha(qapp):
    w = MainWindow(ConfigManager())
    w.resize(800, 600)
    w.show_toast_message("hello", timeout_ms=999_999, position="center", bg_alpha=0.85)
    label = w._toast_label
    assert label is not None
    x = (w.width() - label.width()) // 2
    y = (w.height() - label.height()) // 2
    assert label.x() == max(0, x)
    assert label.y() == max(0, y)
    ss = label.styleSheet()
    assert re.search(r"rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0\.85\s*\)", ss, re.I)


@pytest.mark.qt
def test_toast_bg_alpha_clamped_high(qapp):
    w = MainWindow(ConfigManager())
    w.resize(400, 300)
    w.show_toast_message("x", timeout_ms=999_999, bg_alpha=99.0)
    label = w._toast_label
    assert label is not None
    ss = label.styleSheet()
    assert re.search(r"rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*1(?:\.0)?\s*\)", ss, re.I)


@pytest.mark.qt
def test_toast_bg_alpha_clamped_low(qapp):
    w = MainWindow(ConfigManager())
    w.resize(400, 300)
    w.show_toast_message("x", timeout_ms=999_999, bg_alpha=-5.0)
    label = w._toast_label
    assert label is not None
    ss = label.styleSheet()
    assert re.search(r"rgba\s*\(\s*0\s*,\s*0\s*,\s*0\s*,\s*0(?:\.0)?\s*\)", ss, re.I)
