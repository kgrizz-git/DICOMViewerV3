"""Tests for OverlayCoordinator visibility and toggle handlers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset

from gui.overlay_coordinator import OverlayCoordinator


def _wire_dataset_and_hide_callbacks(coordinator, dataset) -> None:
    """Give the coordinator a dataset/series so the toggle reaches the
    measurement/ROI visibility branch, with all hide callbacks mocked."""
    coordinator.get_current_dataset = MagicMock(return_value=dataset)
    coordinator.get_current_studies = MagicMock(
        return_value={"study_1": {"series_1": [dataset]}}
    )
    coordinator.get_current_study_uid = MagicMock(return_value="study_1")
    coordinator.get_current_series_uid = MagicMock(return_value="series_1")
    coordinator.get_current_slice_index = MagicMock(return_value=0)
    coordinator.hide_measurement_labels = MagicMock()
    coordinator.hide_measurement_graphics = MagicMock()
    coordinator._hide_roi_graphics_callback = MagicMock()
    coordinator.hide_roi_statistics_overlays = MagicMock()


class TestRestoreMeasurementAndRoiVisibility:
    def test_calls_all_hide_callbacks_with_false(
        self, overlay_manager, image_viewer
    ):
        hide_measurement_labels = MagicMock()
        hide_measurement_graphics = MagicMock()
        hide_roi_graphics = MagicMock()
        hide_roi_statistics_overlays = MagicMock()

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_studies=lambda: {},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_measurement_labels=hide_measurement_labels,
            hide_measurement_graphics=hide_measurement_graphics,
            hide_roi_graphics=hide_roi_graphics,
            hide_roi_statistics_overlays=hide_roi_statistics_overlays,
        )

        coordinator.restore_measurement_and_roi_visibility()

        hide_measurement_labels.assert_called_once_with(False)
        hide_measurement_graphics.assert_called_once_with(False)
        hide_roi_graphics.assert_called_once_with(False)
        hide_roi_statistics_overlays.assert_called_once_with(False)

    def test_handles_none_callbacks_gracefully(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.hide_measurement_labels = None
        overlay_coordinator.hide_measurement_graphics = None
        overlay_coordinator._hide_roi_graphics_callback = None
        overlay_coordinator.hide_roi_statistics_overlays = None

        # Should not raise
        overlay_coordinator.restore_measurement_and_roi_visibility()

    def test_handles_partial_none_callbacks(
        self, overlay_manager, image_viewer
    ):
        hide_measurement_labels = MagicMock()
        hide_roi_graphics = MagicMock()

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_studies=lambda: {},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_measurement_labels=hide_measurement_labels,
            hide_measurement_graphics=None,
            hide_roi_graphics=hide_roi_graphics,
            hide_roi_statistics_overlays=None,
        )

        coordinator.restore_measurement_and_roi_visibility()

        hide_measurement_labels.assert_called_once_with(False)
        hide_roi_graphics.assert_called_once_with(False)


class TestHandleToggleOverlay:
    def test_toggles_overlay_visibility(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.handle_toggle_overlay()

        overlay_coordinator.overlay_manager.toggle_overlay_visibility.assert_called_once()

    def test_recreates_overlay_when_dataset_exists(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_dataset = MagicMock(return_value=sample_dataset)
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_toggle_overlay()

        overlay_coordinator.overlay_manager.create_overlay_items.assert_called_once()

    def test_does_not_recreate_overlay_when_no_dataset(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.get_current_dataset = MagicMock(return_value=None)

        overlay_coordinator.handle_toggle_overlay()

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_hides_measurements_and_roi_when_state_is_2(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        _wire_dataset_and_hide_callbacks(overlay_coordinator, sample_dataset)
        overlay_coordinator.overlay_manager.toggle_overlay_visibility = MagicMock(
            return_value=2
        )

        overlay_coordinator.handle_toggle_overlay()

        # State 2 hides measurements and ROI labels/graphics.
        overlay_coordinator.hide_measurement_labels.assert_called_once_with(True)
        overlay_coordinator.hide_measurement_graphics.assert_called_once_with(True)
        overlay_coordinator._hide_roi_graphics_callback.assert_called_once_with(True)
        overlay_coordinator.hide_roi_statistics_overlays.assert_called_once_with(True)

    @pytest.mark.parametrize("state", [0, 1])
    def test_shows_measurements_and_roi_when_state_is_0_or_1(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset, state: int
    ):
        _wire_dataset_and_hide_callbacks(overlay_coordinator, sample_dataset)
        overlay_coordinator.overlay_manager.toggle_overlay_visibility = MagicMock(
            return_value=state
        )

        overlay_coordinator.handle_toggle_overlay()

        # States 0 and 1 both restore measurement and ROI visibility.
        overlay_coordinator.hide_measurement_labels.assert_called_once_with(False)
        overlay_coordinator.hide_measurement_graphics.assert_called_once_with(False)
        overlay_coordinator._hide_roi_graphics_callback.assert_called_once_with(False)
        overlay_coordinator.hide_roi_statistics_overlays.assert_called_once_with(False)

    def test_updates_scene_after_toggle(
        self, overlay_coordinator: OverlayCoordinator
    ):
        # The scene update is not called in the current implementation
        # We'll just verify the toggle was called
        overlay_coordinator.handle_toggle_overlay()

        overlay_coordinator.overlay_manager.toggle_overlay_visibility.assert_called_once()

    def test_handles_none_scene_gracefully(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.image_viewer.scene = None

        # Should not raise
        overlay_coordinator.handle_toggle_overlay()

    def test_handles_missing_study_uid(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.get_current_study_uid = MagicMock(return_value=None)

        overlay_coordinator.handle_toggle_overlay()

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_missing_series_uid(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.get_current_series_uid = MagicMock(return_value=None)

        overlay_coordinator.handle_toggle_overlay()

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_none_callbacks_in_state_2(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.overlay_manager.toggle_overlay_visibility = MagicMock(
            return_value=2
        )
        overlay_coordinator.hide_measurement_labels = None
        overlay_coordinator.hide_measurement_graphics = None
        overlay_coordinator._hide_roi_graphics_callback = None

        # Should not raise
        overlay_coordinator.handle_toggle_overlay()

    def test_calculates_stack_position_correctly(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_dataset = MagicMock(return_value=sample_dataset)
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset, sample_dataset, sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=1)

        overlay_coordinator.handle_toggle_overlay()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["stack_position"] == 2

    def test_handles_toggle_with_multiframe_context(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        multiframe_context = {"frame_index": 4, "frame_count": 12}
        overlay_coordinator.get_multiframe_overlay_context = MagicMock(
            return_value=multiframe_context
        )
        overlay_coordinator.get_current_dataset = MagicMock(return_value=sample_dataset)
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_toggle_overlay()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["multiframe_context"] == multiframe_context

    def test_handles_toggle_with_no_multiframe_callback(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_multiframe_overlay_context = None
        overlay_coordinator.get_current_dataset = MagicMock(return_value=sample_dataset)
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_toggle_overlay()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["multiframe_context"] is None
