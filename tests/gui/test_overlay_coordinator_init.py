"""Tests for OverlayCoordinator initialization."""

from __future__ import annotations

from unittest.mock import MagicMock

from pydicom.dataset import Dataset

from gui.image_viewer import ImageViewer
from gui.overlay_coordinator import OverlayCoordinator
from gui.overlay_manager import OverlayManager


class TestOverlayCoordinatorInitialization:
    def test_initialization_stores_all_dependencies(
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
    ):
        def get_current_dataset() -> Dataset | None:
            return None

        def get_current_studies() -> dict[str, any]:
            return {}

        def get_current_study_uid() -> str:
            return "study_1"

        def get_current_series_uid() -> str:
            return "series_1"

        def get_current_slice_index() -> int:
            return 0

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=get_current_dataset,
            get_current_studies=get_current_studies,
            get_current_study_uid=get_current_study_uid,
            get_current_series_uid=get_current_series_uid,
            get_current_slice_index=get_current_slice_index,
        )

        assert coordinator.overlay_manager is overlay_manager
        assert coordinator.image_viewer is image_viewer
        assert coordinator.get_current_dataset is get_current_dataset
        assert coordinator.get_current_studies is get_current_studies
        assert coordinator.get_current_study_uid is get_current_study_uid
        assert coordinator.get_current_series_uid is get_current_series_uid
        assert coordinator.get_current_slice_index is get_current_slice_index

    def test_initialization_with_optional_callbacks(
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
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

        assert coordinator.hide_measurement_labels is hide_measurement_labels
        assert coordinator.hide_measurement_graphics is hide_measurement_graphics
        assert coordinator._hide_roi_graphics_callback is hide_roi_graphics
        assert coordinator.hide_roi_statistics_overlays is hide_roi_statistics_overlays

    def test_initialization_with_multiframe_context_callback(
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
    ):
        get_multiframe_overlay_context = MagicMock(return_value={"frame_index": 1})

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_studies=lambda: {},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            get_multiframe_overlay_context=get_multiframe_overlay_context,
        )

        assert coordinator.get_multiframe_overlay_context is get_multiframe_overlay_context
