"""Tests for gui.main_window_status_controller (refactor Stream C).

The pure text builder is tested without Qt; the controller is tested with an
offscreen QApplication to confirm label creation and update delegation.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from core.wl_preset_catalog import format_status_bar_wl
from gui.main_window_status_controller import (
    MainWindowStatusController,
    format_zoom_preset_status,
)

# --- pure formatter (no Qt) -------------------------------------------------

def test_format_zoom_only():
    assert format_zoom_preset_status(1.5) == "Zoom = 1.5"


def test_format_zoom_rounds_to_one_decimal():
    assert format_zoom_preset_status(2.0) == "Zoom = 2.0"
    assert format_zoom_preset_status(0.756) == "Zoom = 0.8"


def test_format_zoom_with_wl_matches_catalog():
    expected_wl = format_status_bar_wl(40.0, 400.0, unit="HU")
    out = format_zoom_preset_status(1.0, 40.0, 400.0, unit="HU")
    assert out == f"Zoom = 1.0, W/L {expected_wl}"


def test_format_partial_wl_ignored():
    # Only one of center/width -> no W/L segment (mirrors prior behavior)
    assert format_zoom_preset_status(1.0, 40.0, None) == "Zoom = 1.0"
    assert format_zoom_preset_status(1.0, None, 400.0) == "Zoom = 1.0"


# --- controller (offscreen Qt) ---------------------------------------------

@pytest.fixture(scope="module")
def _qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def controller(_qapp):
    from PySide6.QtWidgets import QMainWindow

    win = QMainWindow()
    ctrl = MainWindowStatusController(win.statusBar())
    yield ctrl
    win.deleteLater()


def test_controller_creates_three_labels(controller):
    assert controller.file_study_label.text() == "Open a DICOM file or folder to begin"
    assert controller.zoom_preset_label.text() == ""
    assert controller.pixel_info_label.text() == ""


def test_controller_set_file_study(controller):
    controller.set_file_study("Study: CT Chest")
    assert controller.file_study_label.text() == "Study: CT Chest"


def test_controller_set_zoom_preset(controller):
    controller.set_zoom_preset(1.0, 40.0, 400.0, unit="HU")
    assert controller.zoom_preset_label.text().startswith("Zoom = 1.0, W/L ")


def test_controller_set_pixel_info(controller):
    controller.set_pixel_info("(120, 64) = 512 HU")
    assert controller.pixel_info_label.text() == "(120, 64) = 512 HU"
