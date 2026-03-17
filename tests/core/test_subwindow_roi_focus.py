"""
Tests for ROI deselection on subwindow focus change.

Covers:
    - When on_focused_subwindow_changed is called and app.roi_coordinator is set,
      handle_image_clicked_no_roi() is called before refs are swapped so the
      outgoing subwindow's ROI selection and shared panels are cleared.
    - When app.roi_coordinator is None the method does not raise.
"""

import sys
import types
import pytest
from unittest.mock import MagicMock, patch, call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(roi_coordinator=None):
    """
    Return a minimal mock 'app' object that satisfies the attribute accesses
    inside on_focused_subwindow_changed without importing the real app or Qt.
    """
    mock_subwindow = MagicMock()
    mock_subwindow.isVisible.return_value = True

    app = MagicMock()
    app.roi_coordinator = roi_coordinator

    # Layout returns a list containing the one subwindow so focused_idx == 0
    app.multi_window_layout.get_all_subwindows.return_value = [mock_subwindow]

    # Minimal subwindow data / managers (empty dicts avoid key-error branches)
    app.subwindow_managers = {}
    app.subwindow_data = {}

    # Ensure guards that check truthiness of optional attrs pass safely
    app.keyboard_event_handler = None
    app.view_state_manager = None
    app.roi_list_panel = None
    app.roi_manager = None
    app.current_dataset = None
    app.series_navigator = None

    return app, mock_subwindow


def _make_controller(app):
    """
    Instantiate SubwindowLifecycleController with the minimal mock app,
    patching away the Qt-dependent __init__ side-effects (QTimer creation).
    """
    # Patch QTimer so the controller __init__ doesn't require a QApplication
    with patch("core.subwindow_lifecycle_controller.QTimer"):
        from core.subwindow_lifecycle_controller import SubwindowLifecycleController
        ctrl = SubwindowLifecycleController.__new__(SubwindowLifecycleController)
        ctrl.app = app
        ctrl._histogram_slots = {}
        ctrl._mpr_open_slots = {}
        ctrl._mpr_clear_slots = {}
        ctrl._viewport_resized_timer = None
    return ctrl


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestROIDeselectionOnSubwindowFocusChange:
    """ROI selection must be cleared on the outgoing subwindow when focus changes."""

    def test_handle_image_clicked_no_roi_called_on_focus_change(self):
        """
        on_focused_subwindow_changed must call app.roi_coordinator.handle_image_clicked_no_roi()
        before swapping refs, so the outgoing subwindow's ROI is deselected and both
        the stats panel and the list panel are cleared.
        """
        mock_coordinator = MagicMock()
        app, mock_subwindow = _make_app(roi_coordinator=mock_coordinator)
        ctrl = _make_controller(app)

        # Stub the three delegate calls so they don't fail with the minimal app mock
        ctrl.disconnect_focused_subwindow_signals = MagicMock()
        ctrl.update_focused_subwindow_references = MagicMock()
        ctrl.connect_focused_subwindow_signals = MagicMock()
        ctrl.update_right_panel_for_focused_subwindow = MagicMock()

        ctrl.on_focused_subwindow_changed(mock_subwindow)

        mock_coordinator.handle_image_clicked_no_roi.assert_called_once()

    def test_deselect_called_before_refs_swapped(self):
        """
        handle_image_clicked_no_roi() must be called BEFORE
        disconnect_focused_subwindow_signals / update_focused_subwindow_references
        so the coordinator still points to the outgoing subwindow's manager.
        """
        call_order = []
        mock_coordinator = MagicMock()
        mock_coordinator.handle_image_clicked_no_roi.side_effect = lambda: call_order.append("deselect")

        app, mock_subwindow = _make_app(roi_coordinator=mock_coordinator)
        ctrl = _make_controller(app)

        def record_disconnect():
            call_order.append("disconnect")
        def record_update_refs():
            call_order.append("update_refs")

        ctrl.disconnect_focused_subwindow_signals = MagicMock(side_effect=record_disconnect)
        ctrl.update_focused_subwindow_references = MagicMock(side_effect=record_update_refs)
        ctrl.connect_focused_subwindow_signals = MagicMock()
        ctrl.update_right_panel_for_focused_subwindow = MagicMock()

        ctrl.on_focused_subwindow_changed(mock_subwindow)

        assert call_order[0] == "deselect", (
            "handle_image_clicked_no_roi must be called before disconnect/update_refs; "
            f"actual order: {call_order}"
        )
        assert "disconnect" in call_order
        assert "update_refs" in call_order

    def test_no_error_when_roi_coordinator_is_none(self):
        """If app.roi_coordinator is None, on_focused_subwindow_changed must not raise."""
        app, mock_subwindow = _make_app(roi_coordinator=None)
        ctrl = _make_controller(app)

        ctrl.disconnect_focused_subwindow_signals = MagicMock()
        ctrl.update_focused_subwindow_references = MagicMock()
        ctrl.connect_focused_subwindow_signals = MagicMock()
        ctrl.update_right_panel_for_focused_subwindow = MagicMock()

        # Should not raise
        ctrl.on_focused_subwindow_changed(mock_subwindow)
