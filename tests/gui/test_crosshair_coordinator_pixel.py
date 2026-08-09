"""Tests for CrosshairCoordinator _update_crosshair_pixel_values."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF

from gui.crosshair_coordinator import CrosshairCoordinator


@pytest.mark.qt
class TestUpdateCrosshairPixelValues:
    def test_updates_pixel_values_with_rescaled_callback(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0
        crosshair_coordinator.get_use_rescaled_values = lambda: True

        crosshair_item = MagicMock()
        new_pos = QPointF(15, 25)

        crosshair_coordinator._update_crosshair_pixel_values(crosshair_item, new_pos)

        crosshair_item.update_pixel_values.assert_called_once()
        call_args = crosshair_item.update_pixel_values.call_args
        assert call_args[0][1] == 15  # x
        assert call_args[0][2] == 25  # y
        assert call_args[0][3] == 0  # z

    @pytest.mark.qt
    def test_updates_pixel_values_without_rescaled_callback(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0
        crosshair_coordinator.get_use_rescaled_values = None

        crosshair_item = MagicMock()
        new_pos = QPointF(15, 25)

        crosshair_coordinator._update_crosshair_pixel_values(crosshair_item, new_pos)

        crosshair_item.update_pixel_values.assert_called_once()

    @pytest.mark.qt
    def test_returns_early_when_dataset_is_none(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.get_current_dataset = lambda: None

        crosshair_item = MagicMock()
        new_pos = QPointF(15, 25)

        crosshair_coordinator._update_crosshair_pixel_values(crosshair_item, new_pos)

        crosshair_item.update_pixel_values.assert_not_called()

    @pytest.mark.qt
    def test_appends_patient_coordinates_when_available(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        with patch('utils.dicom_utils.pixel_to_patient_coordinates') as mock_pixel_to_patient:
            mock_pixel_to_patient.return_value = (100.0, 200.0, 300.0)

            crosshair_item = MagicMock()
            new_pos = QPointF(15, 25)

            crosshair_coordinator._update_crosshair_pixel_values(crosshair_item, new_pos)

            crosshair_item.update_pixel_values.assert_called_once()
            call_args = crosshair_item.update_pixel_values.call_args
            pixel_value_str = call_args[0][0]
            assert "Patient:" in pixel_value_str

    @pytest.mark.qt
    def test_handles_exceptions_gracefully(
        self,
        crosshair_coordinator: CrosshairCoordinator,
        crosshair_sample_dataset: Dataset,
    ):
        # A valid dataset gets past the early return; a failure in the pixel
        # lookup must be swallowed rather than propagated to the caller.
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.image_viewer._get_pixel_value_at_coords = MagicMock(
            side_effect=RuntimeError("pixel lookup failed")
        )

        crosshair_item = MagicMock()
        new_pos = QPointF(15, 25)

        # Should not raise despite the dependency error.
        crosshair_coordinator._update_crosshair_pixel_values(crosshair_item, new_pos)

        crosshair_item.update_pixel_values.assert_not_called()
