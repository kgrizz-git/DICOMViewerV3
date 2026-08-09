"""Tests for CrosshairCoordinator handle_clear_crosshairs."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset

from gui.crosshair_coordinator import CrosshairCoordinator
from utils.dicom_utils import get_composite_series_key
from utils.undo_redo import CompositeCommand


@pytest.mark.qt
class TestHandleClearCrosshairs:
    def test_clears_all_crosshairs_on_current_slice(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0
        undo_redo_manager = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager

        # Populate a crosshair on the current slice so the clear path has work.
        series_uid = get_composite_series_key(crosshair_sample_dataset)
        key = (crosshair_sample_dataset.StudyInstanceUID, series_uid, 0)
        crosshair_coordinator.crosshair_manager.crosshairs[key] = [MagicMock()]

        crosshair_coordinator.handle_clear_crosshairs()

        # The clear dispatches a single composite command for the slice.
        undo_redo_manager.execute_command.assert_called_once()
        command = undo_redo_manager.execute_command.call_args[0][0]
        assert isinstance(command, CompositeCommand)

    @pytest.mark.qt
    def test_creates_composite_command_for_multiple_crosshairs(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        # Set up undo/redo
        undo_redo_manager = MagicMock()
        update_callback = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager
        crosshair_coordinator.update_undo_redo_state_callback = update_callback

        # Add mock crosshairs to manager after setting up series context
        from utils.dicom_utils import get_composite_series_key
        series_uid = get_composite_series_key(crosshair_sample_dataset)
        crosshair_coordinator.crosshair_manager.current_series_uid = series_uid
        mock_crosshair1 = MagicMock()
        mock_crosshair2 = MagicMock()
        key = (crosshair_sample_dataset.StudyInstanceUID, series_uid, 0)
        crosshair_coordinator.crosshair_manager.crosshairs[key] = [mock_crosshair1, mock_crosshair2]

        crosshair_coordinator.handle_clear_crosshairs()

        undo_redo_manager.execute_command.assert_called_once()
        update_callback.assert_called_once()

    @pytest.mark.qt
    def test_returns_early_when_scene_is_none(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.image_viewer.scene = None

        crosshair_coordinator.handle_clear_crosshairs()

        # Should not attempt any operations
        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_not_called()

    @pytest.mark.qt
    def test_returns_early_when_dataset_is_none(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.get_current_dataset = lambda: None

        crosshair_coordinator.handle_clear_crosshairs()

        # Should not attempt any operations
        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_not_called()

    @pytest.mark.qt
    def test_returns_early_when_study_or_series_uid_missing(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        dataset = Dataset()
        # Missing StudyInstanceUID
        crosshair_coordinator.get_current_dataset = lambda: dataset

        crosshair_coordinator.handle_clear_crosshairs()

        # Should not attempt any operations
        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_not_called()

    @pytest.mark.qt
    def test_returns_early_when_no_crosshairs_to_delete(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        # No crosshairs created

        crosshair_coordinator.handle_clear_crosshairs()

        # Should not attempt any operations
        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_not_called()

    @pytest.mark.qt
    def test_uses_direct_deletion_without_undo_redo(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        # Add mock crosshair to manager after setting up series context
        from utils.dicom_utils import get_composite_series_key
        series_uid = get_composite_series_key(crosshair_sample_dataset)
        crosshair_coordinator.crosshair_manager.current_series_uid = series_uid
        mock_crosshair = MagicMock()
        key = (crosshair_sample_dataset.StudyInstanceUID, series_uid, 0)
        crosshair_coordinator.crosshair_manager.crosshairs[key] = [mock_crosshair]

        crosshair_coordinator.handle_clear_crosshairs()

        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_called_once()
