"""
Tests for DICOMViewerApp view-related signal wiring in main.py (Phase 1 refactor).

These tests focus on signals connected in _connect_view_signals():
- privacy_view_toggled -> _on_privacy_view_toggled
- smooth_when_zoomed_toggled -> _on_smooth_when_zoomed_toggled

The goal is to verify that emitting the MainWindow signals:
- updates DICOMViewerApp.privacy_view_enabled
- updates ConfigManager.smooth_image_when_zoomed
- calls MainWindow.set_smooth_when_zoomed_checked with the emitted value

Tests use a temporary config path per test to avoid mutating the user's
real configuration file on disk.
"""

from pathlib import Path

import pytest

import main as main_module
from utils.config_manager import ConfigManager as RealConfigManager


def _make_test_config_manager(tmp_path: Path) -> RealConfigManager:
    """
    Create a ConfigManager instance that writes to a test-specific config file.

    The underlying ConfigManager still uses the standard config directory but
    its config_path is redirected to a file under tmp_path so that any writes
    performed during the test do not touch the user's real configuration file.
    """
    cm = RealConfigManager()
    cm.config_path = tmp_path / "dicom_viewer_config_test_signals.json"
    return cm


@pytest.mark.qt
def test_privacy_view_signal_updates_privacy_state(tmp_path):
    """
    Emitting MainWindow.privacy_view_toggled should update DICOMViewerApp.privacy_view_enabled.

    This verifies that:
    - _connect_view_signals wired privacy_view_toggled to _on_privacy_view_toggled
    - the handler updates the application's privacy_view_enabled flag
    """
    original_cm = main_module.ConfigManager
    main_module.ConfigManager = lambda: _make_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()

        # Ensure initial state is a bool
        assert isinstance(app.privacy_view_enabled, bool)

        # Toggle privacy on
        app.main_window.privacy_view_toggled.emit(True)
        assert app.privacy_view_enabled is True

        # Toggle privacy off
        app.main_window.privacy_view_toggled.emit(False)
        assert app.privacy_view_enabled is False
    finally:
        main_module.ConfigManager = original_cm


@pytest.mark.qt
def test_smooth_when_zoomed_signal_updates_config_and_menu(tmp_path):
    """
    Emitting MainWindow.smooth_when_zoomed_toggled should:
    - update ConfigManager.get_smooth_image_when_zoomed()
    - call MainWindow.set_smooth_when_zoomed_checked with the same value

    This verifies both the signal wiring and the handler behavior in
    _on_smooth_when_zoomed_toggled.
    """
    original_cm = main_module.ConfigManager
    main_module.ConfigManager = lambda: _make_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()

        # Spy on MainWindow.set_smooth_when_zoomed_checked
        calls = []

        def fake_set_smooth_when_zoomed_checked(value: bool) -> None:
            calls.append(value)

        app.main_window.set_smooth_when_zoomed_checked = fake_set_smooth_when_zoomed_checked

        # Emit signal to enable smoothing
        app.main_window.smooth_when_zoomed_toggled.emit(True)
        assert app.config_manager.get_smooth_image_when_zoomed() is True
        assert calls and calls[-1] is True

        # Emit signal to disable smoothing
        app.main_window.smooth_when_zoomed_toggled.emit(False)
        assert app.config_manager.get_smooth_image_when_zoomed() is False
        assert calls and calls[-1] is False
    finally:
        main_module.ConfigManager = original_cm

