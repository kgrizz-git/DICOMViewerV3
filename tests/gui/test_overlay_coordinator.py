"""Comprehensive tests for gui.overlay_coordinator.OverlayCoordinator."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem

from gui.image_viewer import ImageViewer
from gui.overlay_coordinator import OverlayCoordinator
from gui.overlay_manager import OverlayManager


@pytest.fixture
def overlay_manager() -> OverlayManager:
    """Fixture providing a mocked OverlayManager."""
    manager = MagicMock(spec=OverlayManager)
    manager.create_overlay_items = MagicMock()
    manager.set_font_size = MagicMock()
    manager.set_font_color = MagicMock()
    manager.toggle_overlay_visibility = MagicMock(return_value=0)
    return manager


@pytest.fixture
def image_viewer() -> ImageViewer:
    """Fixture providing a mocked ImageViewer."""
    viewer = MagicMock(spec=ImageViewer)
    viewer.scene = MagicMock()
    viewer.image_item = MagicMock()
    return viewer


@pytest.fixture
def sample_dataset() -> Dataset:
    """Fixture providing a sample DICOM dataset."""
    dataset = Dataset()
    dataset.PatientName = "Test^Patient"
    dataset.PatientID = "12345"
    dataset.StudyDate = "20240101"
    return dataset


@pytest.fixture
def overlay_coordinator(
    overlay_manager: OverlayManager,
    image_viewer: ImageViewer,
) -> OverlayCoordinator:
    """Fixture providing an OverlayCoordinator instance with mocked dependencies."""

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
    return coordinator


# ---------------------------------------------------------------------------
# Initialization Tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# handle_overlay_config_applied Tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# handle_overlay_font_size_changed Tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# handle_overlay_font_color_changed Tests
# ---------------------------------------------------------------------------


class TestHandleOverlayFontColorChanged:
    def test_updates_overlay_manager_font_color(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.handle_overlay_font_color_changed(255, 128, 64)

        overlay_coordinator.overlay_manager.set_font_color.assert_called_once_with(
            255, 128, 64
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

        overlay_coordinator.handle_overlay_font_color_changed(255, 0, 0)

        overlay_coordinator.overlay_manager.create_overlay_items.assert_called_once()

    def test_does_not_recreate_overlay_when_no_studies(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.get_current_studies = MagicMock(return_value={})
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")

        overlay_coordinator.handle_overlay_font_color_changed(255, 0, 0)

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_color_change_with_multiframe_context(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        multiframe_context = {"frame_index": 2, "frame_count": 5}
        overlay_coordinator.get_multiframe_overlay_context = MagicMock(
            return_value=multiframe_context
        )
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_overlay_font_color_changed(0, 255, 0)

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
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=10)

        overlay_coordinator.handle_overlay_font_color_changed(255, 0, 0)

        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_color_boundary_values(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.handle_overlay_font_color_changed(0, 0, 0)
        overlay_coordinator.overlay_manager.set_font_color.assert_called_with(0, 0, 0)

        overlay_coordinator.handle_overlay_font_color_changed(255, 255, 255)
        overlay_coordinator.overlay_manager.set_font_color.assert_called_with(255, 255, 255)


# ---------------------------------------------------------------------------
# restore_measurement_and_roi_visibility Tests
# ---------------------------------------------------------------------------


class TestRestoreMeasurementAndRoiVisibility:
    def test_calls_all_hide_callbacks_with_false(
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
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
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


# ---------------------------------------------------------------------------
# handle_toggle_overlay Tests
# ---------------------------------------------------------------------------


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
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
    ):
        hide_measurement_labels = MagicMock()
        hide_measurement_graphics = MagicMock()
        hide_roi_graphics = MagicMock()
        hide_roi_statistics_overlays = MagicMock()

        overlay_manager.toggle_overlay_visibility = MagicMock(return_value=2)

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: Dataset(),
            get_current_studies=lambda: {"study_1": {"series_1": [Dataset()]}},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_measurement_labels=hide_measurement_labels,
            hide_measurement_graphics=hide_measurement_graphics,
            hide_roi_graphics=hide_roi_graphics,
            hide_roi_statistics_overlays=hide_roi_statistics_overlays,
        )

        coordinator.handle_toggle_overlay()

        hide_measurement_labels.assert_called_once_with(True)
        hide_measurement_graphics.assert_called_once_with(True)
        hide_roi_graphics.assert_called_once_with(True)
        hide_roi_statistics_overlays.assert_called_once_with(True)

    def test_shows_measurements_and_roi_when_state_is_0(
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
    ):
        hide_measurement_labels = MagicMock()
        hide_measurement_graphics = MagicMock()
        hide_roi_graphics = MagicMock()
        hide_roi_statistics_overlays = MagicMock()

        overlay_manager.toggle_overlay_visibility = MagicMock(return_value=0)

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: Dataset(),
            get_current_studies=lambda: {"study_1": {"series_1": [Dataset()]}},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_measurement_labels=hide_measurement_labels,
            hide_measurement_graphics=hide_measurement_graphics,
            hide_roi_graphics=hide_roi_graphics,
            hide_roi_statistics_overlays=hide_roi_statistics_overlays,
        )

        coordinator.handle_toggle_overlay()

        hide_measurement_labels.assert_called_once_with(False)
        hide_measurement_graphics.assert_called_once_with(False)
        hide_roi_graphics.assert_called_once_with(False)
        hide_roi_statistics_overlays.assert_called_once_with(False)

    def test_shows_measurements_and_roi_when_state_is_1(
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
    ):
        hide_measurement_labels = MagicMock()
        hide_measurement_graphics = MagicMock()
        hide_roi_graphics = MagicMock()
        hide_roi_statistics_overlays = MagicMock()

        overlay_manager.toggle_overlay_visibility = MagicMock(return_value=1)

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: Dataset(),
            get_current_studies=lambda: {"study_1": {"series_1": [Dataset()]}},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_measurement_labels=hide_measurement_labels,
            hide_measurement_graphics=hide_measurement_graphics,
            hide_roi_graphics=hide_roi_graphics,
            hide_roi_statistics_overlays=hide_roi_statistics_overlays,
        )

        coordinator.handle_toggle_overlay()

        hide_measurement_labels.assert_called_once_with(False)
        hide_measurement_graphics.assert_called_once_with(False)
        hide_roi_graphics.assert_called_once_with(False)
        hide_roi_statistics_overlays.assert_called_once_with(False)

    def test_updates_scene_after_toggle(
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

        overlay_coordinator.image_viewer.scene.update.assert_called_once()

    def test_handles_none_scene_gracefully(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.image_viewer.scene = None
        overlay_coordinator.get_current_dataset = MagicMock(return_value=sample_dataset)

        overlay_coordinator.handle_toggle_overlay()

        # Should not raise
        overlay_coordinator.overlay_manager.create_overlay_items.assert_not_called()

    def test_handles_missing_study_uid(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_dataset = MagicMock(return_value=sample_dataset)
        overlay_coordinator.get_current_study_uid = MagicMock(return_value=None)
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_toggle_overlay()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["total_slices"] is None

    def test_handles_missing_series_uid(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_dataset = MagicMock(return_value=sample_dataset)
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value=None)
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset]}}
        )
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=0)

        overlay_coordinator.handle_toggle_overlay()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["total_slices"] is None

    def test_handles_none_callbacks_in_state_2(
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
    ):
        overlay_manager.toggle_overlay_visibility = MagicMock(return_value=2)

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: Dataset(),
            get_current_studies=lambda: {"study_1": {"series_1": [Dataset()]}},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_measurement_labels=None,
            hide_measurement_graphics=None,
            hide_roi_graphics=None,
            hide_roi_statistics_overlays=None,
        )

        # Should not raise
        coordinator.handle_toggle_overlay()

    def test_calculates_stack_position_correctly(
        self, overlay_coordinator: OverlayCoordinator, sample_dataset: Dataset
    ):
        overlay_coordinator.get_current_dataset = MagicMock(return_value=sample_dataset)
        overlay_coordinator.get_current_studies = MagicMock(
            return_value={"study_1": {"series_1": [sample_dataset, sample_dataset, sample_dataset]}}
        )
        overlay_coordinator.get_current_study_uid = MagicMock(return_value="study_1")
        overlay_coordinator.get_current_series_uid = MagicMock(return_value="series_1")
        overlay_coordinator.get_current_slice_index = MagicMock(return_value=2)

        overlay_coordinator.handle_toggle_overlay()

        call_args = overlay_coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["stack_position"] == 3

    def test_handles_toggle_with_multiframe_context(
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
    ):
        multiframe_context = {"frame_index": 5, "frame_count": 20}
        get_multiframe_overlay_context = MagicMock(return_value=multiframe_context)

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: Dataset(),
            get_current_studies=lambda: {"study_1": {"series_1": [Dataset()]}},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            get_multiframe_overlay_context=get_multiframe_overlay_context,
        )

        coordinator.handle_toggle_overlay()

        call_args = coordinator.overlay_manager.create_overlay_items.call_args
        assert call_args[1]["multiframe_context"] == multiframe_context
        get_multiframe_overlay_context.assert_called_once()

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


# ---------------------------------------------------------------------------
# hide_roi_labels Tests
# ---------------------------------------------------------------------------


class TestHideRoiLabels:
    def test_hide_roi_labels_is_noop(
        self, overlay_coordinator: OverlayCoordinator
    ):
        # This method is documented as a no-op for now
        overlay_coordinator.hide_roi_labels(True)
        overlay_coordinator.hide_roi_labels(False)

        # Should not raise or do anything
        assert True


# ---------------------------------------------------------------------------
# hide_roi_graphics Tests
# ---------------------------------------------------------------------------


class TestHideRoiGraphics:
    def test_delegates_to_callback_when_provided(
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
    ):
        hide_roi_graphics = MagicMock()

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_studies=lambda: {},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_roi_graphics=hide_roi_graphics,
        )

        coordinator.hide_roi_graphics(True)

        hide_roi_graphics.assert_called_once_with(True)

    def test_returns_early_when_callback_provided(
        self, overlay_manager: OverlayManager, image_viewer: ImageViewer
    ):
        hide_roi_graphics = MagicMock()

        coordinator = OverlayCoordinator(
            overlay_manager=overlay_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_studies=lambda: {},
            get_current_study_uid=lambda: "study_1",
            get_current_series_uid=lambda: "series_1",
            get_current_slice_index=lambda: 0,
            hide_roi_graphics=hide_roi_graphics,
        )

        coordinator.hide_roi_graphics(True)

        # Should not iterate scene items
        image_viewer.scene.items.assert_not_called()

    def test_returns_early_when_scene_is_none(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.image_viewer.scene = None
        overlay_coordinator._hide_roi_graphics_callback = None

        overlay_coordinator.hide_roi_graphics(True)

        # Should not raise
        assert True

    def test_hides_rect_items_when_no_callback(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        ellipse_item = MagicMock(spec=QGraphicsEllipseItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item, ellipse_item]
        )
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(True)

        rect_item.setVisible.assert_called_once_with(False)
        ellipse_item.setVisible.assert_called_once_with(False)

    def test_shows_rect_items_when_no_callback(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        ellipse_item = MagicMock(spec=QGraphicsEllipseItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item, ellipse_item]
        )
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(False)

        rect_item.setVisible.assert_called_once_with(True)
        ellipse_item.setVisible.assert_called_once_with(True)

    def test_does_not_hide_image_item(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item]
        )
        overlay_coordinator.image_viewer.image_item = rect_item

        overlay_coordinator.hide_roi_graphics(True)

        rect_item.setVisible.assert_not_called()

    def test_filters_non_roi_items(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        other_item = MagicMock()
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item, other_item]
        )
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(True)

        rect_item.setVisible.assert_called_once_with(False)
        other_item.setVisible.assert_not_called()

    def test_handles_empty_scene(
        self, overlay_coordinator: OverlayCoordinator
    ):
        overlay_coordinator.image_viewer.scene.items = MagicMock(return_value=[])
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(True)

        # Should not raise
        assert True

    def test_handles_mixed_scene_items(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        ellipse_item = MagicMock(spec=QGraphicsEllipseItem)
        text_item = MagicMock()
        line_item = MagicMock()
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item, ellipse_item, text_item, line_item]
        )
        overlay_coordinator.image_viewer.image_item = MagicMock()

        overlay_coordinator.hide_roi_graphics(True)

        rect_item.setVisible.assert_called_once_with(False)
        ellipse_item.setVisible.assert_called_once_with(False)
        text_item.setVisible.assert_not_called()
        line_item.setVisible.assert_not_called()

    def test_handles_image_item_being_rect(
        self, overlay_coordinator: OverlayCoordinator
    ):
        rect_item = MagicMock(spec=QGraphicsRectItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[rect_item]
        )
        overlay_coordinator.image_viewer.image_item = rect_item

        overlay_coordinator.hide_roi_graphics(True)

        # Image item should not be hidden
        rect_item.setVisible.assert_not_called()

    def test_handles_image_item_being_ellipse(
        self, overlay_coordinator: OverlayCoordinator
    ):
        ellipse_item = MagicMock(spec=QGraphicsEllipseItem)
        overlay_coordinator.image_viewer.scene.items = MagicMock(
            return_value=[ellipse_item]
        )
        overlay_coordinator.image_viewer.image_item = ellipse_item

        overlay_coordinator.hide_roi_graphics(True)

        # Image item should not be hidden
        ellipse_item.setVisible.assert_not_called()
