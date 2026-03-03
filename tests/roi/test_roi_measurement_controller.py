"""
Unit tests for ROIMeasurementController.

Tests cover:
- Controller construction and ownership of ROI/measurement/annotation tools
  and panels.
- ROIListPanel is wired to ROIManager on construction.
- update_focused_managers updates active roi_manager and measurement_tool.
- update_styles delegates to the active (or initial) managers.
- clear_statistics delegates to ROIStatisticsPanel.
- update_roi_list delegates to ROIListPanel.
- select_roi_in_list delegates to ROIListPanel.

All tests use a real QApplication (via the session-scoped ``qapp`` fixture
from conftest.py) because the statistics panel and list panel are Qt widgets.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch, call

# Ensure src/ is on the path so imports resolve correctly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_controller(qapp):
    """
    Instantiate a ROIMeasurementController, patching the Qt panels to avoid
    real widget construction inside unit tests.
    """
    from roi.roi_measurement_controller import ROIMeasurementController

    mock_stats_panel = MagicMock()
    mock_list_panel = MagicMock()

    with (
        patch('roi.roi_measurement_controller.ROIStatisticsPanel', return_value=mock_stats_panel),
        patch('roi.roi_measurement_controller.ROIListPanel', return_value=mock_list_panel),
    ):
        ctrl = ROIMeasurementController(config_manager=MagicMock())

    return ctrl


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestROIMeasurementControllerConstruction:
    """Verify that construction creates all expected components."""

    def test_roi_manager_is_set(self, qapp):
        ctrl = _make_controller(qapp)
        assert ctrl.roi_manager is not None

    def test_measurement_tool_is_set(self, qapp):
        ctrl = _make_controller(qapp)
        assert ctrl.measurement_tool is not None

    def test_annotation_manager_is_set(self, qapp):
        ctrl = _make_controller(qapp)
        assert ctrl.annotation_manager is not None

    def test_roi_statistics_panel_is_set(self, qapp):
        ctrl = _make_controller(qapp)
        assert ctrl.roi_statistics_panel is not None

    def test_roi_list_panel_is_set(self, qapp):
        ctrl = _make_controller(qapp)
        assert ctrl.roi_list_panel is not None

    def test_list_panel_wired_to_roi_manager(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl.roi_list_panel.set_roi_manager.assert_called_once_with(ctrl.roi_manager)

    def test_active_managers_default_to_shared_instances(self, qapp):
        ctrl = _make_controller(qapp)
        assert ctrl._active_roi_manager is ctrl.roi_manager
        assert ctrl._active_measurement_tool is ctrl.measurement_tool


class TestROIMeasurementControllerUpdateFocusedManagers:
    """Test update_focused_managers tracks per-subwindow managers."""

    def test_update_sets_active_roi_manager(self, qapp):
        ctrl = _make_controller(qapp)
        new_mgr = MagicMock()
        ctrl.update_focused_managers(roi_manager=new_mgr, measurement_tool=None)
        assert ctrl._active_roi_manager is new_mgr

    def test_update_sets_active_measurement_tool(self, qapp):
        ctrl = _make_controller(qapp)
        new_tool = MagicMock()
        ctrl.update_focused_managers(roi_manager=None, measurement_tool=new_tool)
        assert ctrl._active_measurement_tool is new_tool

    def test_update_both_together(self, qapp):
        ctrl = _make_controller(qapp)
        mgr = MagicMock()
        tool = MagicMock()
        ctrl.update_focused_managers(roi_manager=mgr, measurement_tool=tool)
        assert ctrl._active_roi_manager is mgr
        assert ctrl._active_measurement_tool is tool

    def test_none_does_not_replace_existing_reference(self, qapp):
        ctrl = _make_controller(qapp)
        original_mgr = ctrl._active_roi_manager
        ctrl.update_focused_managers(roi_manager=None, measurement_tool=None)
        # Passing None should not overwrite the existing active manager.
        assert ctrl._active_roi_manager is original_mgr


class TestROIMeasurementControllerUpdateStyles:
    """Test update_styles delegates to the active managers."""

    def test_update_styles_calls_roi_manager(self, qapp):
        ctrl = _make_controller(qapp)
        cfg = MagicMock()
        ctrl.roi_manager = MagicMock()
        ctrl._active_roi_manager = ctrl.roi_manager
        ctrl.measurement_tool = MagicMock()
        ctrl._active_measurement_tool = ctrl.measurement_tool
        ctrl.update_styles(cfg)
        ctrl._active_roi_manager.update_all_roi_styles.assert_called_once_with(cfg)

    def test_update_styles_calls_measurement_tool(self, qapp):
        ctrl = _make_controller(qapp)
        cfg = MagicMock()
        ctrl.roi_manager = MagicMock()
        ctrl._active_roi_manager = ctrl.roi_manager
        ctrl.measurement_tool = MagicMock()
        ctrl._active_measurement_tool = ctrl.measurement_tool
        ctrl.update_styles(cfg)
        ctrl._active_measurement_tool.update_all_measurement_styles.assert_called_once_with(cfg)

    def test_update_styles_uses_active_not_shared_when_different(self, qapp):
        ctrl = _make_controller(qapp)
        active_mgr = MagicMock()
        active_tool = MagicMock()
        ctrl.update_focused_managers(roi_manager=active_mgr, measurement_tool=active_tool)
        cfg = MagicMock()
        ctrl.update_styles(cfg)
        active_mgr.update_all_roi_styles.assert_called_once_with(cfg)
        active_tool.update_all_measurement_styles.assert_called_once_with(cfg)

    def test_update_styles_falls_back_to_shared_if_active_none(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl._active_roi_manager = None
        ctrl._active_measurement_tool = None
        ctrl.roi_manager = MagicMock()
        ctrl.measurement_tool = MagicMock()
        cfg = MagicMock()
        ctrl.update_styles(cfg)
        ctrl.roi_manager.update_all_roi_styles.assert_called_once_with(cfg)
        ctrl.measurement_tool.update_all_measurement_styles.assert_called_once_with(cfg)


class TestROIMeasurementControllerPanelDelegation:
    """Test panel delegation methods."""

    def test_clear_statistics_delegates(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl.clear_statistics()
        ctrl.roi_statistics_panel.clear_statistics.assert_called_once()

    def test_update_roi_list_delegates(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl.update_roi_list("study1", "series1", 5)
        ctrl.roi_list_panel.update_roi_list.assert_called_once_with("study1", "series1", 5)

    def test_select_roi_in_list_delegates(self, qapp):
        ctrl = _make_controller(qapp)
        mock_roi = MagicMock()
        ctrl.select_roi_in_list(mock_roi)
        ctrl.roi_list_panel.select_roi_in_list.assert_called_once_with(mock_roi)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
