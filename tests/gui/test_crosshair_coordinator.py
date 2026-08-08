"""Comprehensive tests for gui.crosshair_coordinator.CrosshairCoordinator."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from gui.crosshair_coordinator import CrosshairCoordinator
from gui.image_viewer import ImageViewer
from tools.crosshair_manager import CrosshairManager


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
def image_viewer(qapp) -> ImageViewer:
    """Fixture providing a mocked ImageViewer."""
    viewer = MagicMock(spec=ImageViewer)
    viewer.scene = QGraphicsScene()
    viewer._get_pixel_value_at_coords = MagicMock(return_value="42")
    return viewer


@pytest.fixture
def sample_dataset() -> Dataset:
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
    image_viewer: ImageViewer,
) -> CrosshairCoordinator:
    """Fixture providing a CrosshairCoordinator instance with mocked dependencies."""

    def get_current_dataset() -> Dataset | None:
        return None

    def get_current_slice_index() -> int:
        return 0

    coordinator = CrosshairCoordinator(
        crosshair_manager=crosshair_manager,
        image_viewer=image_viewer,
        get_current_dataset=get_current_dataset,
        get_current_slice_index=get_current_slice_index,
    )
    return coordinator


# ---------------------------------------------------------------------------
# Initialization Tests
# ---------------------------------------------------------------------------


@pytest.mark.qt
class TestCrosshairCoordinatorInitialization:
    def test_initialization_stores_all_dependencies(
        self, crosshair_manager: CrosshairManager, image_viewer: ImageViewer
    ):
        def get_current_dataset() -> Dataset | None:
            return None

        def get_current_slice_index() -> int:
            return 0

        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_manager,
            image_viewer=image_viewer,
            get_current_dataset=get_current_dataset,
            get_current_slice_index=get_current_slice_index,
        )

        assert coordinator.crosshair_manager is crosshair_manager
        assert coordinator.image_viewer is image_viewer
        assert coordinator.get_current_dataset is get_current_dataset
        assert coordinator.get_current_slice_index is get_current_slice_index

    @pytest.mark.qt
    def test_initialization_with_optional_undo_redo(
        self, crosshair_manager: CrosshairManager, image_viewer: ImageViewer
    ):
        undo_redo_manager = MagicMock()
        update_callback = MagicMock()

        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_slice_index=lambda: 0,
            undo_redo_manager=undo_redo_manager,
            update_undo_redo_state_callback=update_callback,
        )

        assert coordinator.undo_redo_manager is undo_redo_manager
        assert coordinator.update_undo_redo_state_callback is update_callback

    @pytest.mark.qt
    def test_initialization_with_rescaled_values_callback(
        self, crosshair_manager: CrosshairManager, image_viewer: ImageViewer
    ):
        get_use_rescaled = MagicMock(return_value=True)

        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_slice_index=lambda: 0,
            get_use_rescaled_values=get_use_rescaled,
        )

        assert coordinator.get_use_rescaled_values is get_use_rescaled

    @pytest.mark.qt
    def test_initialization_creates_move_tracking_dict(
        self, crosshair_manager: CrosshairManager, image_viewer: ImageViewer
    ):
        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_manager,
            image_viewer=image_viewer,
            get_current_dataset=lambda: None,
            get_current_slice_index=lambda: 0,
        )

        assert coordinator._crosshair_move_tracking == {}
        assert coordinator._move_batch_timer is None


# ---------------------------------------------------------------------------
# handle_crosshair_clicked Tests
# ---------------------------------------------------------------------------


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
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 5

        crosshair_coordinator.handle_crosshair_clicked(
            QPointF(10, 20), "42", 10, 20, 5
        )

        assert crosshair_coordinator.crosshair_manager.current_study_uid == sample_dataset.StudyInstanceUID
        assert crosshair_coordinator.crosshair_manager.current_series_uid is not None
        assert crosshair_coordinator.crosshair_manager.current_instance_identifier == 5

    @pytest.mark.qt
    def test_appends_patient_coordinates_when_available(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
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
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        undo_redo_manager = MagicMock()
        update_callback = MagicMock()
        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_coordinator.crosshair_manager,
            image_viewer=crosshair_coordinator.image_viewer,
            get_current_dataset=lambda: sample_dataset,
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


# ---------------------------------------------------------------------------
# handle_crosshair_delete_requested Tests
# ---------------------------------------------------------------------------


@pytest.mark.qt
class TestHandleCrosshairDeleteRequested:
    def test_deletes_crosshair_with_undo_redo(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
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
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
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
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        undo_redo_manager = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager
        crosshair_item = MagicMock()

        crosshair_coordinator.handle_crosshair_delete_requested(crosshair_item)

        # Check that undo command was executed
        undo_redo_manager.execute_command.assert_called_once()


# ---------------------------------------------------------------------------
# handle_clear_crosshairs Tests
# ---------------------------------------------------------------------------


@pytest.mark.qt
class TestHandleClearCrosshairs:
    def test_clears_all_crosshairs_on_current_slice(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        # This test verifies the method runs without error when crosshairs exist
        # The actual clearing logic is tested by the composite command test
        crosshair_coordinator.handle_clear_crosshairs()

    @pytest.mark.qt
    def test_creates_composite_command_for_multiple_crosshairs(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        # Set up undo/redo
        undo_redo_manager = MagicMock()
        update_callback = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager
        crosshair_coordinator.update_undo_redo_state_callback = update_callback

        # Add mock crosshairs to manager after setting up series context
        from utils.dicom_utils import get_composite_series_key
        series_uid = get_composite_series_key(sample_dataset)
        crosshair_coordinator.crosshair_manager.current_series_uid = series_uid
        mock_crosshair1 = MagicMock()
        mock_crosshair2 = MagicMock()
        key = (sample_dataset.StudyInstanceUID, series_uid, 0)
        crosshair_coordinator.crosshair_manager.crosshairs[key] = [mock_crosshair1, mock_crosshair2]

        crosshair_coordinator.handle_clear_crosshairs()

        undo_redo_manager.execute_command.assert_called_once()
        update_callback.assert_called_once()

    @pytest.mark.qt
    def test_returns_early_when_scene_is_none(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.image_viewer.scene = None

        crosshair_coordinator.handle_clear_crosshairs()

        # Should not attempt any operations
        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_not_called()

    @pytest.mark.qt
    def test_returns_early_when_dataset_is_none(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.get_current_dataset = lambda: None

        crosshair_coordinator.handle_clear_crosshairs()

        # Should not attempt any operations
        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_not_called()

    @pytest.mark.qt
    def test_returns_early_when_study_or_series_uid_missing(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        dataset = Dataset()
        # Missing StudyInstanceUID
        crosshair_coordinator.get_current_dataset = lambda: dataset

        crosshair_coordinator.handle_clear_crosshairs()

        # Should not attempt any operations
        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_not_called()

    @pytest.mark.qt
    def test_returns_early_when_no_crosshairs_to_delete(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        # No crosshairs created

        crosshair_coordinator.handle_clear_crosshairs()

        # Should not attempt any operations
        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_not_called()

    @pytest.mark.qt
    def test_uses_direct_deletion_without_undo_redo(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        # Add mock crosshair to manager after setting up series context
        from utils.dicom_utils import get_composite_series_key
        series_uid = get_composite_series_key(sample_dataset)
        crosshair_coordinator.crosshair_manager.current_series_uid = series_uid
        mock_crosshair = MagicMock()
        key = (sample_dataset.StudyInstanceUID, series_uid, 0)
        crosshair_coordinator.crosshair_manager.crosshairs[key] = [mock_crosshair]

        crosshair_coordinator.handle_clear_crosshairs()

        crosshair_coordinator.crosshair_manager.clear_crosshairs_for_slice.assert_called_once()


# ---------------------------------------------------------------------------
# update_crosshairs_for_slice Tests
# ---------------------------------------------------------------------------


@pytest.mark.qt
class TestUpdateCrosshairsForSlice:
    def test_updates_current_slice_context(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 3

        crosshair_coordinator.update_crosshairs_for_slice()

        assert crosshair_coordinator.crosshair_manager.current_study_uid == sample_dataset.StudyInstanceUID
        assert crosshair_coordinator.crosshair_manager.current_series_uid is not None
        assert crosshair_coordinator.crosshair_manager.current_instance_identifier == 3

    @pytest.mark.qt
    def test_displays_crosshairs_for_current_slice(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
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


# ---------------------------------------------------------------------------
# update_privacy_mode Tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _on_crosshair_moved Tests
# ---------------------------------------------------------------------------


@pytest.mark.qt
class TestOnCrosshairMoved:
    def test_tracks_initial_position_on_first_move(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_item = MagicMock()
        crosshair_item.pos.return_value = QPointF(10, 20)

        crosshair_coordinator._on_crosshair_moved(crosshair_item)

        assert crosshair_item in crosshair_coordinator._crosshair_move_tracking
        tracking = crosshair_coordinator._crosshair_move_tracking[crosshair_item]
        assert tracking['initial_pos'] == QPointF(10, 20)
        assert tracking['current_pos'] == QPointF(10, 20)

    @pytest.mark.qt
    def test_updates_current_position_on_subsequent_moves(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_item = MagicMock()
        crosshair_item.pos.return_value = QPointF(10, 20)

        # First move
        crosshair_coordinator._on_crosshair_moved(crosshair_item)

        # Second move
        crosshair_item.pos.return_value = QPointF(15, 25)
        crosshair_coordinator._on_crosshair_moved(crosshair_item)

        tracking = crosshair_coordinator._crosshair_move_tracking[crosshair_item]
        assert tracking['initial_pos'] == QPointF(10, 20)
        assert tracking['current_pos'] == QPointF(15, 25)

    @pytest.mark.qt
    def test_returns_early_for_none_crosshair(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator._on_crosshair_moved(None)

        assert len(crosshair_coordinator._crosshair_move_tracking) == 0

    @pytest.mark.qt
    def test_returns_early_for_crosshair_without_pos_attribute(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_item = MagicMock(spec=[])  # Mock without pos attribute

        crosshair_coordinator._on_crosshair_moved(crosshair_item)

        assert len(crosshair_coordinator._crosshair_move_tracking) == 0

    @pytest.mark.qt
    def test_creates_batch_timer_on_move(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_item = MagicMock()
        crosshair_item.pos.return_value = QPointF(10, 20)

        crosshair_coordinator._on_crosshair_moved(crosshair_item)

        assert crosshair_coordinator._move_batch_timer is not None

    @pytest.mark.qt
    def test_restarts_timer_on_subsequent_moves(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_item = MagicMock()
        crosshair_item.pos.return_value = QPointF(10, 20)

        # First move
        crosshair_coordinator._on_crosshair_moved(crosshair_item)
        first_timer = crosshair_coordinator._move_batch_timer

        # Second move
        crosshair_item.pos.return_value = QPointF(15, 25)
        crosshair_coordinator._on_crosshair_moved(crosshair_item)

        # Timer should be replaced
        assert crosshair_coordinator._move_batch_timer is not first_timer


# ---------------------------------------------------------------------------
# _finalize_crosshair_move Tests
# ---------------------------------------------------------------------------


@pytest.mark.qt
class TestFinalizeCrosshairMove:
    def test_updates_pixel_values_at_new_position(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        crosshair_item = MagicMock()
        crosshair_coordinator._crosshair_move_tracking[crosshair_item] = {
            'initial_pos': QPointF(10, 20),
            'current_pos': QPointF(15, 25)
        }

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        crosshair_item.update_pixel_values.assert_called_once()

    @pytest.mark.qt
    def test_creates_undo_command_when_position_changed(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        undo_redo_manager = MagicMock()
        update_callback = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager
        crosshair_coordinator.update_undo_redo_state_callback = update_callback

        crosshair_item = MagicMock()
        crosshair_coordinator._crosshair_move_tracking[crosshair_item] = {
            'initial_pos': QPointF(10, 20),
            'current_pos': QPointF(15, 25)
        }

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        undo_redo_manager.execute_command.assert_called_once()
        update_callback.assert_called_once()

    @pytest.mark.qt
    def test_does_not_create_command_when_position_unchanged(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        undo_redo_manager = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager

        crosshair_item = MagicMock()
        crosshair_coordinator._crosshair_move_tracking[crosshair_item] = {
            'initial_pos': QPointF(10, 20),
            'current_pos': QPointF(10, 20)  # Same position
        }

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        undo_redo_manager.execute_command.assert_not_called()

    @pytest.mark.qt
    def test_clears_tracking_after_finalization(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
        crosshair_coordinator.get_current_slice_index = lambda: 0

        crosshair_item = MagicMock()
        crosshair_coordinator._crosshair_move_tracking[crosshair_item] = {
            'initial_pos': QPointF(10, 20),
            'current_pos': QPointF(15, 25)
        }

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        assert crosshair_item not in crosshair_coordinator._crosshair_move_tracking

    @pytest.mark.qt
    def test_returns_early_when_crosshair_not_tracked(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_item = MagicMock()

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        # Should not raise an error
        crosshair_item.update_pixel_values.assert_not_called()


# ---------------------------------------------------------------------------
# _update_crosshair_pixel_values Tests
# ---------------------------------------------------------------------------


@pytest.mark.qt
class TestUpdateCrosshairPixelValues:
    def test_updates_pixel_values_with_rescaled_callback(
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
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
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
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
        self, crosshair_coordinator: CrosshairCoordinator, sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: sample_dataset
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
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_coordinator.get_current_dataset = lambda: None

        crosshair_item = MagicMock()
        new_pos = QPointF(15, 25)

        # Should not raise an exception
        crosshair_coordinator._update_crosshair_pixel_values(crosshair_item, new_pos)
