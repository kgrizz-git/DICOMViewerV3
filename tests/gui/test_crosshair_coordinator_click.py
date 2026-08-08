"""Tests for CrosshairCoordinator handle_crosshair_clicked."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF

from gui.crosshair_coordinator import CrosshairCoordinator
from tools.crosshair_manager import CrosshairManager


@pytest.mark.qt
class TestHandleCrosshairClicked:
    def test_creates_crosshair_with_valid_inputs(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.handle_crosshair_clicked(
            QPointF(10, 20), "42", 10, 20, 0
        )

        crosshair_coordinator.crosshair_manager.create_crosshair.assert_called_once()

    @pytest.mark.qt
    def test_returns_early_when_scene_is_none(
        self, crosshair_manager: CrosshairManager
    ):
        viewer = MagicMock()
        viewer.scene = None
        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_manager,
            image_viewer=viewer,
            get_current_dataset=lambda: None,
            get_current_slice_index=lambda: 0,
        )

        coordinator.handle_crosshair_clicked(QPointF(1, 1), "1", 1, 1, 0)

        assert all(len(v) == 0 for v in crosshair_manager.crosshairs.values())

    @pytest.mark.qt
    def test_sets_current_slice_context_with_dataset(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 5

        crosshair_coordinator.handle_crosshair_clicked(
            QPointF(10, 20), "42", 10, 20, 5
        )

        assert crosshair_coordinator.crosshair_manager.current_study_uid == crosshair_sample_dataset.StudyInstanceUID
        assert crosshair_coordinator.crosshair_manager.current_series_uid is not None
        assert crosshair_coordinator.crosshair_manager.current_instance_identifier == 5

    @pytest.mark.qt
    def test_appends_patient_coordinates_when_available(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        with patch('utils.dicom_utils.pixel_to_patient_coordinates') as mock_pixel_to_patient:
            mock_pixel_to_patient.return_value = (100.0, 200.0, 300.0)

            crosshair_coordinator.handle_crosshair_clicked(
                QPointF(10, 20), "42", 10, 20, 0
            )

            # Verify pixel_to_patient_coordinates was called
            mock_pixel_to_patient.assert_called_once()
            # Verify create_crosshair was called with modified pixel_value_str
            crosshair_coordinator.crosshair_manager.create_crosshair.assert_called_once()
            call_args = crosshair_coordinator.crosshair_manager.create_crosshair.call_args
            pixel_value_str = call_args[0][1]
            assert "Patient:" in pixel_value_str

    @pytest.mark.qt
    def test_creates_undo_command_when_undo_redo_available(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        undo_redo_manager = MagicMock()
        update_callback = MagicMock()
        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_coordinator.crosshair_manager,
            image_viewer=crosshair_coordinator.image_viewer,
            get_current_dataset=lambda: crosshair_sample_dataset,
            get_current_slice_index=lambda: 0,
            undo_redo_manager=undo_redo_manager,
            update_undo_redo_state_callback=update_callback,
        )

        coordinator.handle_crosshair_clicked(QPointF(10, 20), "42", 10, 20, 0)

        undo_redo_manager.execute_command.assert_called_once()
        update_callback.assert_called_once()

    @pytest.mark.qt
    def test_sets_movement_callback_on_created_crosshair(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        mock_crosshair = MagicMock()
        crosshair_coordinator.crosshair_manager.create_crosshair.return_value = mock_crosshair

        crosshair_coordinator.handle_crosshair_clicked(
            QPointF(10, 20), "42", 10, 20, 0
        )

        assert mock_crosshair.on_moved_callback is not None

    @pytest.mark.qt
    def test_handles_none_dataset_gracefully(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.get_current_dataset = lambda: None

        crosshair_coordinator.handle_crosshair_clicked(
            QPointF(10, 20), "42", 10, 20, 0
        )

        # Should still create crosshair, just without patient coordinates
        crosshair_coordinator.crosshair_manager.create_crosshair.assert_called_once()
