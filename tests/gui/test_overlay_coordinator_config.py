"""Tests for OverlayCoordinator handle_overlay_config_applied."""

from __future__ import annotations

from unittest.mock import MagicMock

from pydicom.dataset import Dataset

from gui.overlay_coordinator import OverlayCoordinator


class TestHandleOverlayConfigApplied:
    def test_creates_overlay_when_current_studies_exist(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_overlay_config_applied()

        overlay_coordinator.overlay_manager.create_overlay_items.assert_called_once()

    def test_handles_empty_current_studies(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.get_current_studies = MagicMock(return_value={})
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")

        overlay_coordinator.handle_overlay_config_applied()

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_missing_series_uid(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": []}}
        )
        overlay_coordinator.get_current_series_uid = MagicMock(return_value=None)

        overlay_coordinator.handle_overlay_config_applied()

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_slice_index_out_of_bounds(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=5)

        overlay_coordinator.handle_overlay_config_applied()

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_passes_correct_parameters_to_overlay_manager(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset, sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=1)

        overlay_coordinator.handle_overlay_config_applied()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[0][0] is overlay_coordinator.image_viewer.scene
        assert call_args[1]["total_slices"] == 2
        assert call_args[1]["stack_position"] == 2

    def test_handles_multiframe_context_when_callback_provided(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        multiframe_context = {"frame_index": 3, "frame_count": 10}
        overlay_coordinator.get_multiframe_overlay_context = MagicMock(
            return_value=multiframe_context
        )
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_overlay_config_applied()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["multiframe_context"] == multiframe_context
        overlay_coordinator.get_multiframe_overlay_context.assert_called_once_with(
            sample_dataset, "study_1", "series_1"
        )

    def test_handles_no_multiframe_context_when_callback_not_provided(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_multiframe_overlay_context = None
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_overlay_config_applied()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["multiframe_context"] is None

    def test_handles_empty_datasets_list(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": []}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_overlay_config_applied()

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_zero_total_slices(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_overlay_config_applied()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["total_slices"] == 1
