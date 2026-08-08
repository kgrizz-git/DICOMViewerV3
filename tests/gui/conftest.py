"""Shared fixtures for overlay_coordinator and crosshair_coordinator tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtWidgets import QGraphicsScene

from gui.crosshair_coordinator import CrosshairCoordinator
from gui.image_viewer import ImageViewer
from gui.overlay_coordinator import OverlayCoordinator
from gui.overlay_manager import OverlayManager
from tools.crosshair_manager import CrosshairManager


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


@pytest.fixture
def crosshair_manager() -> CrosshairManager:
    """Fixture providing a mocked CrosshairManager instance."""
    manager = MagicMock(spec=CrosshairManager)
    manager.crosshairs = {}
    manager.current_study_uid = ""
    manager.current_series_uid = ""
    manager.current_instance_identifier = 0

    def set_current_slice_impl(study_uid, series_uid, instance_identifier):
        manager.current_study_uid = study_uid
        manager.current_series_uid = series_uid
        manager.current_instance_identifier = instance_identifier

    manager.set_current_slice = MagicMock(side_effect=set_current_slice_impl)
    manager.create_crosshair = MagicMock()
    manager.delete_crosshair = MagicMock()
    manager.clear_crosshairs_for_slice = MagicMock()
    manager.display_crosshairs_for_slice = MagicMock()
    manager.set_privacy_mode = MagicMock()
    manager.get_crosshairs_for_slice = MagicMock(return_value=[])
    return manager


@pytest.fixture
def crosshair_image_viewer(qapp) -> ImageViewer:
    """Fixture providing a mocked ImageViewer for crosshair tests."""
    viewer = MagicMock(spec=ImageViewer)
    viewer.scene = QGraphicsScene()
    viewer._get_pixel_value_at_coords = MagicMock(return_value="42")
    return viewer


@pytest.fixture
def crosshair_sample_dataset() -> Dataset:
    """Fixture providing a sample DICOM dataset with required attributes."""
    dataset = Dataset()
    dataset.StudyInstanceUID = "1.2.3.4.5"
    dataset.SeriesInstanceUID = "1.2.3.4.5.6"
    dataset.SOPInstanceUID = "1.2.3.4.5.6.7"
    dataset.ImagePositionPatient = [10.0, 20.0, 30.0]
    dataset.PixelSpacing = [0.5, 0.5]
    dataset.SliceThickness = 2.0
    return dataset


@pytest.fixture
def crosshair_coordinator(
    crosshair_manager: CrosshairManager,
    crosshair_image_viewer: ImageViewer,
) -> CrosshairCoordinator:
    """Fixture providing a CrosshairCoordinator instance with mocked dependencies."""

    def get_current_dataset() -> Dataset | None:
        return None

    def get_current_slice_index() -> int:
        return 0

    coordinator = CrosshairCoordinator(
        crosshair_manager=crosshair_manager,
        image_viewer=crosshair_image_viewer,
        get_current_dataset=get_current_dataset,
        get_current_slice_index=get_current_slice_index,
    )
    return coordinator
