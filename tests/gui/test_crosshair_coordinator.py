"""
Comprehensive unit tests for src/gui/crosshair_coordinator.py.

Achieves 100% statement and branch coverage for CrosshairCoordinator.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF

from gui.crosshair_coordinator import CrosshairCoordinator


@pytest.fixture
def mock_coordinator_setup(qapp):
    """Fixture providing CrosshairCoordinator with mocked dependencies."""
    cm = MagicMock()
    iv = MagicMock()
    get_dataset_cb = MagicMock(return_value=None)
    get_slice_cb = MagicMock(return_value=0)
    undo_mgr = MagicMock()
    undo_state_cb = MagicMock()
    rescaled_cb = MagicMock(return_value=True)

    coordinator = CrosshairCoordinator(
        crosshair_manager=cm,
        image_viewer=iv,
        get_current_dataset=get_dataset_cb,
        get_current_slice_index=get_slice_cb,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=undo_state_cb,
        get_use_rescaled_values=rescaled_cb,
    )
    return coordinator, cm, iv, get_dataset_cb, get_slice_cb, undo_mgr, undo_state_cb, rescaled_cb


def test_init_and_attributes(mock_coordinator_setup) -> None:
    """Test initialization of CrosshairCoordinator."""
    coordinator, cm, iv, get_ds, get_slice, undo_mgr, undo_cb, resc_cb = mock_coordinator_setup

    assert coordinator.crosshair_manager == cm
    assert coordinator.image_viewer == iv
    assert coordinator.get_current_dataset == get_ds
    assert coordinator.get_current_slice_index == get_slice
    assert coordinator.undo_redo_manager == undo_mgr
    assert coordinator.update_undo_redo_state_callback == undo_cb
    assert coordinator.get_use_rescaled_values == resc_cb
    assert coordinator._crosshair_move_tracking == {}
    assert coordinator._move_batch_timer is None


def test_handle_crosshair_clicked(mock_coordinator_setup) -> None:
    """Test handle_crosshair_clicked under various scene, dataset, and patient coordinate conditions."""
    coordinator, cm, iv, get_ds, get_slice, undo_mgr, undo_cb, _ = mock_coordinator_setup

    # 1. scene is None
    iv.scene = None
    coordinator.handle_crosshair_clicked(QPointF(10, 20), "100 HU", 10, 20, 0)
    cm.create_crosshair.assert_not_called()

    # 2. scene present, current_dataset present with patient coordinates
    scene = MagicMock()
    iv.scene = scene
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3.4"
    ds.SeriesInstanceUID = "1.2.3.4.5"
    get_ds.return_value = ds

    mock_crosshair = MagicMock()
    cm.create_crosshair.return_value = mock_crosshair

    with patch("utils.dicom_utils.pixel_to_patient_coordinates", return_value=(1.0, 2.0, 3.0)):
        coordinator.handle_crosshair_clicked(QPointF(10, 20), "100 HU", 10, 20, 0)

        cm.set_current_slice.assert_called_once()
        cm.create_crosshair.assert_called_once()
        undo_mgr.execute_command.assert_called_once()
        undo_cb.assert_called_once()
        assert callable(mock_crosshair.on_moved_callback)
        # Test lambda trigger
        with patch.object(coordinator, "_on_crosshair_moved") as mock_moved:
            mock_crosshair.on_moved_callback()
            mock_moved.assert_called_once_with(mock_crosshair)

    # 3. current_dataset present with NO patient coordinates and no undo_cb
    cm.reset_mock()
    undo_mgr.reset_mock()
    coordinator.update_undo_redo_state_callback = None

    with patch("utils.dicom_utils.pixel_to_patient_coordinates", return_value=None):
        coordinator.handle_crosshair_clicked(QPointF(10, 20), "100 HU", 10, 20, 0)
        cm.create_crosshair.assert_called_once()
        undo_mgr.execute_command.assert_called_once()

    # 4. current_dataset is None and undo_redo_manager is None
    cm.reset_mock()
    get_ds.return_value = None
    coordinator.undo_redo_manager = None

    coordinator.handle_crosshair_clicked(QPointF(10, 20), "100 HU", 10, 20, 0)
    cm.create_crosshair.assert_called_once()

    # 5. create_crosshair returns None (hits 144->exit branch)
    cm.create_crosshair.return_value = None
    coordinator.handle_crosshair_clicked(QPointF(10, 20), "100 HU", 10, 20, 0)


def test_handle_crosshair_delete_requested(mock_coordinator_setup) -> None:
    """Test handle_crosshair_delete_requested with and without undo_redo_manager."""
    coordinator, cm, iv, get_ds, get_slice, undo_mgr, undo_cb, _ = mock_coordinator_setup

    item = MagicMock()

    # 1. scene is None
    iv.scene = None
    coordinator.handle_crosshair_delete_requested(item)
    undo_mgr.execute_command.assert_not_called()

    # 2. scene present with undo_redo_manager
    scene = MagicMock()
    iv.scene = scene
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3.4"
    get_ds.return_value = ds

    coordinator.handle_crosshair_delete_requested(item)
    undo_mgr.execute_command.assert_called_once()
    undo_cb.assert_called_once()

    # 3. current_dataset is None and update_undo_redo_state_callback is None (hits 162->168 & 181->exit)
    get_ds.return_value = None
    coordinator.update_undo_redo_state_callback = None
    undo_mgr.reset_mock()
    coordinator.handle_crosshair_delete_requested(item)
    undo_mgr.execute_command.assert_called_once()

    # 4. scene present WITHOUT undo_redo_manager (fallback deletion)
    coordinator.undo_redo_manager = None
    coordinator.handle_crosshair_delete_requested(item)
    cm.delete_crosshair.assert_called_once_with(item, scene)


def test_handle_clear_crosshairs(mock_coordinator_setup) -> None:
    """Test handle_clear_crosshairs under various empty/valid slice conditions."""
    coordinator, cm, iv, get_ds, get_slice, undo_mgr, undo_cb, _ = mock_coordinator_setup

    # 1. scene is None
    iv.scene = None
    coordinator.handle_clear_crosshairs()

    # 2. current_dataset is None
    iv.scene = MagicMock()
    get_ds.return_value = None
    coordinator.handle_clear_crosshairs()

    # 3. missing study_uid or series_uid
    ds = Dataset()
    get_ds.return_value = ds
    with patch("gui.crosshair_coordinator.get_composite_series_key", return_value=""):
        coordinator.handle_clear_crosshairs()

    # 4. crosshairs_to_delete is empty
    with patch("gui.crosshair_coordinator.get_composite_series_key", return_value="1.2.3.4.5"):
        ds.StudyInstanceUID = "1.2.3.4"
        cm.crosshairs = {}
        coordinator.handle_clear_crosshairs()
        undo_mgr.execute_command.assert_not_called()

        # 5. crosshairs_to_delete present with undo_redo_manager
        item1 = MagicMock()
        item2 = MagicMock()
        key = ("1.2.3.4", "1.2.3.4.5", 0)
        cm.crosshairs = {key: [item1, item2]}

        coordinator.handle_clear_crosshairs()
        undo_mgr.execute_command.assert_called_once()
        undo_cb.assert_called_once()

        # 6. update_undo_redo_state_callback is None (hits 238->exit)
        coordinator.update_undo_redo_state_callback = None
        undo_mgr.reset_mock()
        coordinator.handle_clear_crosshairs()
        undo_mgr.execute_command.assert_called_once()

        # 7. crosshairs_to_delete present WITHOUT undo_redo_manager (fallback clear)
        coordinator.undo_redo_manager = None
        coordinator.handle_clear_crosshairs()
        cm.clear_crosshairs_for_slice.assert_called_once_with(iv.scene)


def test_update_crosshairs_for_slice_and_privacy_mode(mock_coordinator_setup) -> None:
    """Test update_crosshairs_for_slice and update_privacy_mode."""
    coordinator, cm, iv, get_ds, get_slice, _, _, _ = mock_coordinator_setup

    # 1. scene is None
    iv.scene = None
    coordinator.update_crosshairs_for_slice()
    cm.display_crosshairs_for_slice.assert_not_called()

    # 2. scene present with current_dataset is None (hits 255->263)
    scene = MagicMock()
    iv.scene = scene
    get_ds.return_value = None
    coordinator.update_crosshairs_for_slice()
    cm.display_crosshairs_for_slice.assert_called_once_with(scene)

    # 3. scene present with current_dataset
    cm.reset_mock()
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3.4"
    get_ds.return_value = ds

    coordinator.update_crosshairs_for_slice()
    cm.set_current_slice.assert_called_once()
    cm.display_crosshairs_for_slice.assert_called_once_with(scene)

    # 4. Privacy mode toggle
    coordinator.update_privacy_mode(True)
    cm.set_privacy_mode.assert_called_with(True)


def test_on_crosshair_moved_and_finalize(mock_coordinator_setup) -> None:
    """Test _on_crosshair_moved, batch timer reset, exception handling, and _finalize_crosshair_move."""
    coordinator, cm, iv, get_ds, get_slice, undo_mgr, undo_cb, _ = mock_coordinator_setup
    iv.scene = MagicMock()

    # 1. Invalid item (None or no pos attribute)
    coordinator._on_crosshair_moved(None)
    coordinator._on_crosshair_moved("string_without_pos")

    # 2. First move tracking and timer start
    item = MagicMock()
    pos1 = QPointF(10, 20)
    item.pos.return_value = pos1

    coordinator._on_crosshair_moved(item)
    assert item in coordinator._crosshair_move_tracking
    assert coordinator._crosshair_move_tracking[item]["initial_pos"] == pos1
    assert coordinator._move_batch_timer is not None

    # 3. Subsequent move with timer restart
    pos2 = QPointF(30, 40)
    item.pos.return_value = pos2
    coordinator._on_crosshair_moved(item)
    assert coordinator._crosshair_move_tracking[item]["current_pos"] == pos2

    # 4. Exception in _on_crosshair_moved logged cleanly
    with patch.object(item, "pos", side_effect=Exception("Pos error")):
        coordinator._on_crosshair_moved(item)

    # 5. Finalize move when item not in tracking
    dummy_item = MagicMock()
    coordinator._finalize_crosshair_move(dummy_item)

    # 6. Finalize move when position did NOT change (initial == final)
    coordinator._crosshair_move_tracking[item] = {
        "initial_pos": pos1,
        "current_pos": pos1,
    }
    with patch.object(coordinator, "_update_crosshair_pixel_values") as mock_upd:
        coordinator._finalize_crosshair_move(item)
        mock_upd.assert_called_once_with(item, pos1)
        undo_mgr.execute_command.assert_not_called()
        assert item not in coordinator._crosshair_move_tracking

    # 7. Finalize move when position DID change (initial != final)
    coordinator._crosshair_move_tracking[item] = {
        "initial_pos": pos1,
        "current_pos": pos2,
    }
    with patch.object(coordinator, "_update_crosshair_pixel_values") as mock_upd:
        coordinator._finalize_crosshair_move(item)
        mock_upd.assert_called_once_with(item, pos2)
        undo_mgr.execute_command.assert_called_once()
        undo_cb.assert_called_once()
        assert item not in coordinator._crosshair_move_tracking

    # 8. Finalize move when update_undo_redo_state_callback is None (hits 334->338)
    coordinator._crosshair_move_tracking[item] = {
        "initial_pos": pos1,
        "current_pos": pos2,
    }
    coordinator.update_undo_redo_state_callback = None
    undo_mgr.reset_mock()
    with patch.object(coordinator, "_update_crosshair_pixel_values"):
        coordinator._finalize_crosshair_move(item)
        undo_mgr.execute_command.assert_called_once()



def test_update_crosshair_pixel_values(mock_coordinator_setup) -> None:
    """Test _update_crosshair_pixel_values with rescaled values, patient coordinates, and exceptions."""
    coordinator, cm, iv, get_ds, get_slice, _, _, rescaled_cb = mock_coordinator_setup

    item = MagicMock()
    pos = QPointF(15.4, 25.8)

    # 1. current_dataset is None
    get_ds.return_value = None
    coordinator._update_crosshair_pixel_values(item, pos)
    item.update_pixel_values.assert_not_called()

    # 2. current_dataset present with patient coordinates and rescaled callback
    ds = Dataset()
    get_ds.return_value = ds
    iv._get_pixel_value_at_coords.return_value = "250 HU"

    with patch("utils.dicom_utils.pixel_to_patient_coordinates", return_value=(10.0, 20.0, 30.0)):
        coordinator._update_crosshair_pixel_values(item, pos)

        iv._get_pixel_value_at_coords.assert_called_with(ds, 15, 25, 0, True)
        item.update_pixel_values.assert_called_once()
        assert "Patient: (10.00, 20.00, 30.00) mm" in item.update_pixel_values.call_args[0][0]

    # 3. rescaled_cb is None and no patient coordinates
    coordinator.get_use_rescaled_values = None
    item.reset_mock()

    with patch("utils.dicom_utils.pixel_to_patient_coordinates", return_value=None):
        coordinator._update_crosshair_pixel_values(item, pos)
        item.update_pixel_values.assert_called_once()

    # 4. Exception in _update_crosshair_pixel_values logged cleanly
    with patch.object(iv, "_get_pixel_value_at_coords", side_effect=Exception("Pixel error")):
        coordinator._update_crosshair_pixel_values(item, pos)


def test_handle_clear_crosshairs_executes_command_for_nonempty_crosshair_set(
    mock_coordinator_setup,
) -> None:
    """A nonempty crosshair set produces an undo command."""
    coordinator, cm, iv, get_ds, _, undo_mgr, _, _ = mock_coordinator_setup
    iv.scene = MagicMock()

    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3.4"
    get_ds.return_value = ds

    with patch("gui.crosshair_coordinator.get_composite_series_key", return_value="1.2.3.4.5"):
        key = ("1.2.3.4", "1.2.3.4.5", 0)
        cm.crosshairs = {key: [MagicMock()]}

        coordinator.handle_clear_crosshairs()
        undo_mgr.execute_command.assert_called_once()


def test_move_batch_timer_is_replaced_between_sequential_moves(
    mock_coordinator_setup,
) -> None:
    """Python-owned timers are replaced between sequential crosshair moves."""
    coordinator, _, iv, _, _, _, _, _ = mock_coordinator_setup
    iv.scene = MagicMock()

    item = MagicMock()
    item.pos.return_value = QPointF(10, 20)

    coordinator._on_crosshair_moved(item)
    timer1 = coordinator._move_batch_timer

    item.pos.return_value = QPointF(15, 25)
    coordinator._on_crosshair_moved(item)
    timer2 = coordinator._move_batch_timer

    assert timer1 is not timer2
    assert timer1 is not None
    assert timer2 is not None
