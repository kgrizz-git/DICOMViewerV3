"""Tests for CrosshairCoordinator handle_crosshair_delete_requested."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset

from gui.crosshair_coordinator import CrosshairCoordinator


@pytest.mark.qt
class TestHandleCrosshairDeleteRequested:
    def test_deletes_crosshair_with_undo_redo(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_crosshair_sample_dataset
        undo_redo_manager = MagicMock()
        update_callback = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager
        crosshair_coordinator.update_undo_redo_state_callback = update_callback
        crosshair_item = MagicMock()

        crosshair_coordinator.handle_crosshair_delete_requested(crosshair_item)

        undo_redo_manager.execute_command.assert_called_once()
        update_callback.assert_called_once()

    @pytest.mark.qt
    def test_deletes_crosshair_without_undo_redo(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_crosshair_sample_dataset
        crosshair_item = MagicMock()

        crosshair_coordinator.handle_crosshair_delete_requested(crosshair_item)

        crosshair_coordinator.crosshair_manager.delete_crosshair.assert_called_once()

    @pytest.mark.qt
    def test_returns_early_when_scene_is_none(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.image_viewer.scene = None
        crosshair_item = MagicMock()

        crosshair_coordinator.handle_crosshair_delete_requested(crosshair_item)

        # Should not attempt deletion
        crosshair_coordinator.crosshair_manager.delete_crosshair.assert_not_called()

    @pytest.mark.qt
    def test_extracts_dicom_identifiers_before_deletion(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_crosshair_sample_dataset
        undo_redo_manager = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager
        crosshair_item = MagicMock()

        crosshair_coordinator.handle_crosshair_delete_requested(crosshair_item)

        # Check that undo command was executed
        undo_redo_manager.execute_command.assert_called_once()
