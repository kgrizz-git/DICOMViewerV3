"""Tests for OverlayCoordinator font size and color handlers."""

from __future__ import annotations

from unittest.mock import MagicMock

from pydicom.dataset import Dataset

from gui.overlay_coordinator import OverlayCoordinator


class TestHandleOverlayFontSizeChanged:
    def test_updates_overlay_manager_font_size(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.handle_overlay_font_size_changed(14)

        overlay_coordinator.overlay_manager.set_font_size.assert_called_once_with(14)

    def test_recreates_overlay_when_studies_exist(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_overlay_font_size_changed(12)

        overlay_coordinator.overlay_manager.create_overlay_items.assert_called_once()

    def test_does_not_recreate_overlay_when_no_studies(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.get_current_studies = MagicMock(return_value={})
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")

        overlay_coordinator.handle_overlay_font_size_changed(12)

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_passes_correct_parameters_after_font_change(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset, sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=1)

        overlay_coordinator.handle_overlay_font_size_changed(16)

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["total_slices"] == 2
        assert call_args[1]["stack_position"] == 2

    def test_handles_slice_index_out_of_bounds_when_studies_exist(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=5)

        overlay_coordinator.handle_overlay_font_size_changed(12)

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_font_size_boundary_values(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.handle_overlay_font_size_changed(1)
        overlay_coordinator.overlay_manager.set_font_size.assert_called_with(1)

        overlay_coordinator.handle_overlay_font_size_changed(100)
        overlay_coordinator.overlay_manager.set_font_size.assert_called_with(100)


class TestHandleOverlayFontColorChanged:
    def test_updates_overlay_manager_font_color(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.handle_overlay_font_color_changed(255, 0, 0)

        overlay_coordinator.overlay_manager.set_font_color.assert_called_once_with(
            255, 0, 0
        )

    def test_recreates_overlay_when_studies_exist(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_overlay_font_color_changed(0, 255, 0)

        overlay_coordinator.overlay_manager.create_overlay_items.assert_called_once()

    def test_does_not_recreate_overlay_when_no_studies(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.get_current_studies = MagicMock(return_value={})
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")

        overlay_coordinator.handle_overlay_font_color_changed(0, 0, 255)

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_color_change_with_multiframe_context(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        multiframe_context = {"frame_index": 2, "frame_count": 8}
        overlay_coordinator.get_multiframe_overlay_context = MagicMock(
            return_value=multiframe_context
        )
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_overlay_font_color_changed(128, 128, 128)

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["multiframe_context"] == multiframe_context

    def test_handles_slice_index_out_of_bounds_when_color_changed(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=5)

        overlay_coordinator.handle_overlay_font_color_changed(64, 64, 64)

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_color_boundary_values(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.handle_overlay_font_color_changed(0, 0, 0)
        overlay_coordinator.overlay_manager.set_font_color.assert_called_with(0, 0, 0)

        overlay_coordinator.handle_overlay_font_color_changed(255, 255, 255)
        overlay_coordinator.overlay_manager.set_font_color.assert_called_with(
            255, 255, 255
        )
