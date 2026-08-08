"""
Subwindow focus and multi-pane lifecycle regression tests (Phase 0 safety net).

Pins facade delegation from ``DICOMViewerApp`` into the subwindow lifecycle
controller and study-navigation helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from main_test_helpers import with_test_config_manager

import main as main_module
import main_app_subwindow_management as subwindow_mgmt_module


@pytest.mark.qt
def test_on_focused_subwindow_changed_delegates_to_controller(tmp_path, monkeypatch):
    """Focused subwindow changes must reach the lifecycle controller."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        controller = app._subwindow_lifecycle_controller
        controller.on_focused_subwindow_changed = MagicMock()
        monkeypatch.setattr(app, "_update_3d_view_action_state", MagicMock())
        monkeypatch.setattr(app, "_refresh_window_slot_map_widgets", MagicMock())
        monkeypatch.setattr(
            app._slice_location_line_coordinator,
            "refresh_all",
            MagicMock(),
        )
        app.config_manager.get_slice_location_lines_focused_only = MagicMock(
            return_value=False
        )

        subwindow = MagicMock()
        app._on_focused_subwindow_changed(subwindow)

        controller.on_focused_subwindow_changed.assert_called_once_with(subwindow)
    finally:
        restore()


@pytest.mark.qt
def test_update_focused_subwindow_references_syncs_roi_controller(tmp_path):
    """Legacy focus pointers update must delegate and refresh ROI managers."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        controller = app._subwindow_lifecycle_controller
        controller.update_focused_subwindow_references = MagicMock()
        app.roi_measurement_controller.update_focused_managers = MagicMock()

        app._update_focused_subwindow_references()

        controller.update_focused_subwindow_references.assert_called_once_with()
        app.roi_measurement_controller.update_focused_managers.assert_called_once()
    finally:
        restore()


@pytest.mark.qt
def test_redisplay_subwindow_slice_delegates_and_refreshes_lines(tmp_path):
    """Redisplay must delegate to the controller and refresh slice-location lines."""
    restore, _ = with_test_config_manager(tmp_path)
    try:
        app = main_module.DICOMViewerApp()
        controller = app._subwindow_lifecycle_controller
        controller.redisplay_subwindow_slice = MagicMock()
        app._slice_location_line_coordinator.refresh_all = MagicMock()

        app._redisplay_subwindow_slice(2, preserve_view=True)

        controller.redisplay_subwindow_slice.assert_called_once_with(2, True)
        app._slice_location_line_coordinator.refresh_all.assert_called_once_with()
    finally:
        restore()


@pytest.mark.qt
def test_clear_subwindow_delegates_to_study_navigation_helper(tmp_path, monkeypatch):
    """``_clear_subwindow`` must forward to ``study_navigation_handlers.clear_subwindow``."""
    restore, _ = with_test_config_manager(tmp_path)
    received: list[tuple[object, int]] = []

    def _spy(app_obj: object, idx: int) -> None:
        received.append((app_obj, idx))

    monkeypatch.setattr(subwindow_mgmt_module, "clear_subwindow", _spy)
    try:
        app = main_module.DICOMViewerApp()
        app._clear_subwindow(1)
        assert received == [(app, 1)]
    finally:
        restore()


@pytest.mark.qt
def test_close_series_delegates_to_study_navigation_helper(tmp_path, monkeypatch):
    """``_close_series`` must forward study and series keys."""
    restore, _ = with_test_config_manager(tmp_path)
    received: list[tuple[object, str, str]] = []

    def _spy(app_obj: object, study_uid: str, series_key: str) -> None:
        received.append((app_obj, study_uid, series_key))

    monkeypatch.setattr(subwindow_mgmt_module, "close_series", _spy)
    try:
        app = main_module.DICOMViewerApp()
        app._close_series("study-a", "series-b")
        assert received == [(app, "study-a", "series-b")]
    finally:
        restore()


@pytest.mark.qt
def test_close_study_delegates_to_study_navigation_helper(tmp_path, monkeypatch):
    """``_close_study`` must forward the study UID."""
    restore, _ = with_test_config_manager(tmp_path)
    received: list[tuple[object, str]] = []

    def _spy(app_obj: object, study_uid: str) -> None:
        received.append((app_obj, study_uid))

    monkeypatch.setattr(subwindow_mgmt_module, "close_study", _spy)
    try:
        app = main_module.DICOMViewerApp()
        app._close_study("study-z")
        assert received == [(app, "study-z")]
    finally:
        restore()
