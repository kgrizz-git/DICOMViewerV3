"""Tests for CrosshairCoordinator update_crosshairs_for_slice and update_privacy_mode."""

from __future__ import annotations

import pytest
from pydicom.dataset import Dataset

from gui.crosshair_coordinator import CrosshairCoordinator


@pytest.mark.qt
class TestUpdateCrosshairsForSlice:
    def test_updates_current_slice_context(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 3

        crosshair_coordinator.update_crosshairs_for_slice()

        assert crosshair_coordinator.crosshair_manager.current_study_uid == crosshair_sample_dataset.StudyInstanceUID
        assert crosshair_coordinator.crosshair_manager.current_series_uid is not None
        assert crosshair_coordinator.crosshair_manager.current_instance_identifier == 3

    @pytest.mark.qt
    def test_displays_crosshairs_for_current_slice(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        crosshair_coordinator.update_crosshairs_for_slice()

        crosshair_coordinator.crosshair_manager.display_crosshairs_for_slice.assert_called_once_with(
            crosshair_coordinator.image_viewer.scene
        )

    @pytest.mark.qt
    def test_returns_early_when_scene_is_none(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.image_viewer.scene = None

        crosshair_coordinator.update_crosshairs_for_slice()

        # Should not attempt any operations
        crosshair_coordinator.crosshair_manager.display_crosshairs_for_slice.assert_not_called()

    @pytest.mark.qt
    def test_handles_none_dataset_gracefully(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.get_current_dataset = lambda: None

        crosshair_coordinator.update_crosshairs_for_slice()

        # Should still call display (with empty context)
        crosshair_coordinator.crosshair_manager.display_crosshairs_for_slice.assert_called_once_with(
            crosshair_coordinator.image_viewer.scene
        )


@pytest.mark.qt
class TestUpdatePrivacyMode:
    def test_enables_privacy_mode(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.update_privacy_mode(True)

        crosshair_coordinator.crosshair_manager.set_privacy_mode.assert_called_once_with(True)

    @pytest.mark.qt
    def test_disables_privacy_mode(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.update_privacy_mode(False)

        crosshair_coordinator.crosshair_manager.set_privacy_mode.assert_called_once_with(False)
