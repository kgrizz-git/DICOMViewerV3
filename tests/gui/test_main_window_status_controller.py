"""
Comprehensive unit tests for src/gui/main_window_status_controller.py.

Achieves 100% statement and branch coverage for MainWindowStatusController and format_zoom_preset_status.
"""


from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStatusBar

from gui.main_window_status_controller import (
    MainWindowStatusController,
    format_zoom_preset_status,
)


def test_format_zoom_preset_status_zoom_only() -> None:
    """Test format_zoom_preset_status when W/L parameters are incomplete or None."""
    # 1. Only zoom provided
    assert format_zoom_preset_status(1.0) == "Zoom = 1.0"
    assert format_zoom_preset_status(2.54) == "Zoom = 2.5"

    # 2. Only window_center provided (incomplete W/L pair)
    assert format_zoom_preset_status(1.5, window_center=40.0, window_width=None) == "Zoom = 1.5"

    # 3. Only window_width provided (incomplete W/L pair)
    assert format_zoom_preset_status(1.5, window_center=None, window_width=400.0) == "Zoom = 1.5"


def test_format_zoom_preset_status_with_window_center_and_width() -> None:
    """Test format_zoom_preset_status with complete center and width parameters."""
    res_no_unit = format_zoom_preset_status(1.0, window_center=40.0, window_width=400.0)
    assert res_no_unit.startswith("Zoom = 1.0, W/L ")
    assert "40" in res_no_unit and "400" in res_no_unit

    res_with_unit = format_zoom_preset_status(1.2, window_center=40.0, window_width=400.0, unit="HU")
    assert res_with_unit.startswith("Zoom = 1.2, W/L ")
    assert "HU" in res_with_unit


def test_main_window_status_controller_init(qapp) -> None:
    """Test MainWindowStatusController initialization and label registration."""
    status_bar = QStatusBar()
    controller = MainWindowStatusController(status_bar)

    assert controller.file_study_label.text() == "Open a DICOM file or folder to begin"
    assert (
        controller.file_study_label.alignment()
        == (Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    )

    assert controller.zoom_preset_label.text() == ""
    assert (
        controller.zoom_preset_label.alignment()
        == (Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
    )

    assert controller.pixel_info_label.text() == ""
    assert (
        controller.pixel_info_label.alignment()
        == (Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    )


def test_status_controller_set_file_study(qapp) -> None:
    """Test set_file_study updates file_study_label text."""
    status_bar = QStatusBar()
    controller = MainWindowStatusController(status_bar)

    controller.set_file_study("Test Patient - Test Study")
    assert controller.file_study_label.text() == "Test Patient - Test Study"


def test_status_controller_set_zoom_preset(qapp) -> None:
    """Test set_zoom_preset updates zoom_preset_label text."""
    status_bar = QStatusBar()
    controller = MainWindowStatusController(status_bar)

    # Zoom only
    controller.set_zoom_preset(1.5)
    assert controller.zoom_preset_label.text() == "Zoom = 1.5"

    # Zoom + W/L + unit
    controller.set_zoom_preset(2.0, 50.0, 350.0, unit="HU")
    text = controller.zoom_preset_label.text()
    assert text.startswith("Zoom = 2.0, W/L ")
    assert "HU" in text


def test_status_controller_set_pixel_info(qapp) -> None:
    """Test set_pixel_info updates pixel_info_label text."""
    status_bar = QStatusBar()
    controller = MainWindowStatusController(status_bar)

    controller.set_pixel_info("X: 120, Y: 240, Value: 350 HU")
    assert controller.pixel_info_label.text() == "X: 120, Y: 240, Value: 350 HU"


def test_flaw_format_zoom_preset_status_silently_drops_incomplete_wl_pair() -> None:
    """Document flaw: format_zoom_preset_status silently drops window_center or window_width if passed incompletely."""
    # When window_center is provided without window_width, center is silently ignored
    res_center_only = format_zoom_preset_status(1.5, window_center=40.0)
    assert "W/L" not in res_center_only
    assert "40" not in res_center_only
    assert res_center_only == "Zoom = 1.5"

    # When window_width is provided without window_center, width is silently ignored
    res_width_only = format_zoom_preset_status(1.5, window_width=400.0)
    assert "W/L" not in res_width_only
    assert "400" not in res_width_only
    assert res_width_only == "Zoom = 1.5"


# ---------------------------------------------------------------------------
# Contract tests adopted from initial-commit suite
# ---------------------------------------------------------------------------

def test_format_zoom_with_wl_matches_catalog() -> None:
    """format_zoom_preset_status W/L segment must stay in sync with core.wl_preset_catalog.format_status_bar_wl."""
    from core.wl_preset_catalog import format_status_bar_wl
    expected_wl = format_status_bar_wl(40.0, 400.0, unit="HU")
    out = format_zoom_preset_status(1.0, 40.0, 400.0, unit="HU")
    assert out == f"Zoom = 1.0, W/L {expected_wl}"


def test_format_zoom_rounds_to_one_decimal() -> None:
    """format_zoom_preset_status must round zoom to one decimal place."""
    assert format_zoom_preset_status(2.0) == "Zoom = 2.0"
    assert format_zoom_preset_status(0.756) == "Zoom = 0.8"
