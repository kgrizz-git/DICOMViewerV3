"""
Subwindow focus and multi-pane lifecycle regression tests (Phase 0 safety net).

Pins facade delegation from ``DICOMViewerApp`` into the subwindow lifecycle
controller and study-navigation helpers.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from main_test_helpers import with_test_config_manager

import main as main_module
import main_app_subwindow_management as subwindow_mgmt_module
from main_app_subwindow_management import SubwindowManagementMixin


def _make_subwindow_stub(**attrs):
    """Return a minimal ``SubwindowManagementMixin`` instance with mock collaborators."""
    stub = SubwindowManagementMixin.__new__(SubwindowManagementMixin)
    stub._subwindow_lifecycle_controller = MagicMock()
    stub.roi_measurement_controller = MagicMock()
    stub._slice_location_line_coordinator = MagicMock()
    stub.config_manager = MagicMock()
    stub._update_3d_view_action_state = MagicMock()
    stub._refresh_window_slot_map_widgets = MagicMock()
    for k, v in attrs.items():
        setattr(stub, k, v)
    return stub


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
def test_update_focused_subwindow_references_syncs_roi_controller():
    """Legacy focus pointers update must delegate and refresh ROI managers."""
    stub = _make_subwindow_stub()

    stub._update_focused_subwindow_references()

    stub._subwindow_lifecycle_controller.update_focused_subwindow_references.assert_called_once_with()
    stub.roi_measurement_controller.update_focused_managers.assert_called_once()


@pytest.mark.qt
def test_redisplay_subwindow_slice_delegates_and_refreshes_lines():
    """Redisplay must delegate to the controller and refresh slice-location lines."""
    stub = _make_subwindow_stub()

    stub._redisplay_subwindow_slice(2, preserve_view=True)

    stub._subwindow_lifecycle_controller.redisplay_subwindow_slice.assert_called_once_with(
        2, True
    )
    stub._slice_location_line_coordinator.refresh_all.assert_called_once_with()


@pytest.mark.qt
def test_clear_subwindow_delegates_to_study_navigation_helper():
    """``_clear_subwindow`` must forward to ``study_navigation_handlers.clear_subwindow``."""
    stub = _make_subwindow_stub()

    with patch.object(subwindow_mgmt_module, "clear_subwindow") as mock_clear:
        stub._clear_subwindow(1)
        mock_clear.assert_called_once_with(stub, 1)


@pytest.mark.qt
def test_close_series_delegates_to_study_navigation_helper():
    """``_close_series`` must forward study and series keys."""
    stub = _make_subwindow_stub()

    with patch.object(subwindow_mgmt_module, "close_series") as mock_close:
        stub._close_series("study-a", "series-b")
        mock_close.assert_called_once_with(stub, "study-a", "series-b")


@pytest.mark.qt
def test_close_study_delegates_to_study_navigation_helper():
    """``_close_study`` must forward the study UID."""
    stub = _make_subwindow_stub()

    with patch.object(subwindow_mgmt_module, "close_study") as mock_close:
        stub._close_study("study-z")
        mock_close.assert_called_once_with(stub, "study-z")
