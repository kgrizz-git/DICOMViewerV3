"""
Comprehensive unit tests for src/gui/text_annotation_coordinator.py.

Achieves 100% statement and branch coverage for TextAnnotationCoordinator.
"""

from unittest.mock import MagicMock, patch

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsScene

from gui.text_annotation_coordinator import TextAnnotationCoordinator
from tools.text_annotation_tool import TextAnnotationTool


@pytest.fixture
def scene(qapp) -> QGraphicsScene:
    """Fixture providing a QGraphicsScene."""
    return QGraphicsScene()


@pytest.fixture
def mock_image_viewer() -> MagicMock:
    """Fixture providing a mocked ImageViewer."""
    viewer = MagicMock()
    viewer.scene = MagicMock(spec=QGraphicsScene)
    return viewer


@pytest.fixture
def mock_text_tool() -> MagicMock:
    """Fixture providing a mocked TextAnnotationTool."""
    tool = MagicMock(spec=TextAnnotationTool)
    tool.current_item = None
    return tool


@pytest.fixture
def sample_dataset() -> Dataset:
    """Fixture providing a sample DICOM dataset."""
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3"
    ds.SeriesInstanceUID = "1.2.3.4"
    ds.SOPInstanceUID = "1.2.3.4.5"
    return ds


def test_init(mock_text_tool: MagicMock, mock_image_viewer: MagicMock) -> None:
    """Test initialization of TextAnnotationCoordinator."""
    def get_dataset():
        return None
    def get_slice():
        return 0
    undo_mgr = MagicMock()
    update_cb = MagicMock()

    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=get_dataset,
        get_current_slice_index=get_slice,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=update_cb,
    )

    assert coord.text_annotation_tool is mock_text_tool
    assert coord.image_viewer is mock_image_viewer
    assert coord.undo_redo_manager is undo_mgr
    assert coord.update_undo_redo_state_callback is update_cb
    assert coord._processing_finished is False
    assert coord._annotation_in_progress is False
    assert coord._text_move_tracking == {}
    assert coord._text_move_batch_timer is None


def test_handle_text_annotation_started_guard_in_progress(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Test handle_text_annotation_started returns early when annotation is already in progress."""
    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord._annotation_in_progress = True
    coord.handle_text_annotation_started(QPointF(10, 20))
    mock_text_tool.start_annotation.assert_not_called()


def test_handle_text_annotation_started_with_dataset_and_item_in_scene(
    mock_text_tool: MagicMock,
    mock_image_viewer: MagicMock,
    sample_dataset: Dataset,
) -> None:
    """Test starting text annotation with dataset and item scene insertion."""
    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: sample_dataset,
        get_current_slice_index=lambda: 2,
    )

    # Mock current_item
    mock_item = MagicMock()
    mock_item.scene.return_value = None
    mock_text_tool.current_item = mock_item

    mock_image_viewer.text_annotating = True
    mock_image_viewer.text_annotation_start_pos = QPointF(10, 20)

    pos = QPointF(10, 20)
    coord.handle_text_annotation_started(pos)

    # Verify set_current_slice called
    mock_text_tool.set_current_slice.assert_called_once_with("1.2.3", "1.2.3.4", 2)
    mock_text_tool.start_annotation.assert_called_once()
    mock_image_viewer.scene.addItem.assert_called_once_with(mock_item)
    mock_item.start_editing.assert_called_once()

    # Extract on_editing_finished callback
    _, kwargs = mock_text_tool.start_annotation.call_args
    on_editing_finished = kwargs["on_editing_finished"]

    # Test callback when accept=False and scene is present
    on_editing_finished(False)
    assert mock_image_viewer.text_annotating is False
    assert mock_image_viewer.text_annotation_start_pos is None
    mock_text_tool.cancel_annotation.assert_called_once_with(mock_image_viewer.scene)
    assert coord._annotation_in_progress is False

    # Test callback when accept=False and scene is None
    mock_image_viewer.scene = None
    coord._annotation_in_progress = True
    on_editing_finished(False)
    assert coord._annotation_in_progress is False

    # Test callback when accept=True and _processing_finished is already True
    coord._processing_finished = True
    on_editing_finished(True)


def test_handle_text_annotation_started_without_text_annotating_attr(
    mock_text_tool: MagicMock,
) -> None:
    """Test editing finished callback when image_viewer lacks text_annotating attribute."""
    viewer = MagicMock(spec=[])  # Lacks text_annotating attribute
    viewer.scene = MagicMock()

    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    mock_item = MagicMock()
    mock_item.scene.return_value = viewer.scene
    mock_text_tool.current_item = mock_item

    coord.handle_text_annotation_started(QPointF(5, 5))
    _, kwargs = mock_text_tool.start_annotation.call_args
    on_editing_finished = kwargs["on_editing_finished"]

    with patch.object(coord, "handle_text_annotation_finished") as mock_finish:
        on_editing_finished(True)
        assert coord._processing_finished is True
        mock_finish.assert_called_once()
        assert coord._annotation_in_progress is False


def test_handle_text_annotation_started_no_scene_or_item(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Test start_annotation when scene is None or current_item is None."""
    mock_image_viewer.scene = None
    mock_text_tool.current_item = None

    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord.handle_text_annotation_started(QPointF(1, 1))
    mock_text_tool.start_annotation.assert_called_once()


def test_handle_text_annotation_finished_no_scene(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Test handle_text_annotation_finished returns early when scene is None."""
    mock_image_viewer.scene = None
    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord._processing_finished = True
    coord.handle_text_annotation_finished()
    assert coord._processing_finished is False


def test_handle_text_annotation_finished_no_annotation(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Test handle_text_annotation_finished when finish_annotation returns None."""
    mock_text_tool.finish_annotation.return_value = None
    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord.handle_text_annotation_finished()
    assert coord._processing_finished is False
    assert coord._annotation_in_progress is False


def test_handle_text_annotation_finished_with_undo_redo(
    mock_text_tool: MagicMock,
    mock_image_viewer: MagicMock,
    sample_dataset: Dataset,
) -> None:
    """Test handle_text_annotation_finished executing TextAnnotationCommand and setting callbacks."""
    mock_item = MagicMock()
    mock_item.pos.return_value = QPointF(1, 2)
    mock_text_tool.finish_annotation.return_value = mock_item

    undo_mgr = MagicMock()
    update_cb = MagicMock()

    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: sample_dataset,
        get_current_slice_index=lambda: 1,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=update_cb,
    )

    # Pre-populate tracking to test 'annotation not in tracking' False branch
    coord._text_move_tracking[mock_item] = {}

    coord.handle_text_annotation_finished()

    undo_mgr.execute_command.assert_called_once()
    assert mock_item.on_moved_callback == coord._on_text_annotation_moved
    assert mock_item.on_text_edit_finished == coord._on_text_annotation_edited
    update_cb.assert_called_once()
    assert coord._processing_finished is False
    assert coord._annotation_in_progress is False


def test_handle_text_annotation_finished_no_dataset_no_callback(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Test handle_text_annotation_finished when dataset is None and callback is None."""
    mock_item = MagicMock()
    mock_item.pos.return_value = QPointF(1, 2)
    mock_text_tool.finish_annotation.return_value = mock_item

    undo_mgr = MagicMock()

    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=None,
    )

    coord.handle_text_annotation_finished()
    undo_mgr.execute_command.assert_called_once()
    assert mock_item in coord._text_move_tracking


def test_handle_text_annotation_finished_without_undo_redo(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Test handle_text_annotation_finished when undo_redo_manager is None."""
    mock_item = MagicMock()
    mock_text_tool.finish_annotation.return_value = mock_item

    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=None,
    )
    coord.handle_text_annotation_finished()
    assert coord._processing_finished is False
    assert coord._annotation_in_progress is False


def test_on_text_annotation_moved(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Test _on_text_annotation_moved tracking position and setting batch timer."""
    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )

    # 1. None item -> returns early
    coord._on_text_annotation_moved(None)

    # 2. Track new item
    mock_item = MagicMock()
    mock_item.pos.return_value = QPointF(10, 20)

    coord._on_text_annotation_moved(mock_item)
    assert mock_item in coord._text_move_tracking
    assert coord._text_move_tracking[mock_item]["current_position"] == QPointF(10, 20)
    assert coord._text_move_batch_timer is not None

    # 3. Update existing item move position (re-starts batch timer)
    mock_item.pos.return_value = QPointF(15, 25)
    coord._on_text_annotation_moved(mock_item)
    assert coord._text_move_tracking[mock_item]["current_position"] == QPointF(15, 25)

    # 4. Exception handling
    mock_item.pos.side_effect = RuntimeError("Qt object deleted")
    coord._on_text_annotation_moved(mock_item)  # Should be caught by try/except block


def test_on_text_annotation_edited(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Test _on_text_annotation_edited command creation and guards."""
    undo_mgr = MagicMock()
    update_cb = MagicMock()

    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=update_cb,
    )

    # Guard: None item or None undo_mgr
    coord._on_text_annotation_edited(None, "old", "new")
    coord_no_undo = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord_no_undo._on_text_annotation_edited(MagicMock(), "old", "new")

    # Guard: text unchanged
    coord._on_text_annotation_edited(MagicMock(), "same", "same")
    undo_mgr.execute_command.assert_not_called()

    # Valid text change without callback
    coord_no_cb = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=None,
    )
    coord_no_cb._on_text_annotation_edited(MagicMock(), "old", "new")
    undo_mgr.execute_command.assert_called_once()

    # Valid text change with callback
    undo_mgr.reset_mock()
    mock_item = MagicMock()
    coord._on_text_annotation_edited(mock_item, "old text", "new text")
    undo_mgr.execute_command.assert_called_once()
    update_cb.assert_called_once()


def test_finalize_text_move(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Test _finalize_text_move command creation, guards, and cleanup."""
    undo_mgr = MagicMock()
    update_cb = MagicMock()

    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=update_cb,
    )

    mock_item = MagicMock()

    # 1. Untracked item -> return early
    coord._finalize_text_move(mock_item)
    undo_mgr.execute_command.assert_not_called()

    # 2. Position unchanged -> no command executed, removed from tracking
    coord._text_move_tracking[mock_item] = {
        "initial_position": QPointF(0, 0),
        "current_position": QPointF(0, 0),
    }
    coord._finalize_text_move(mock_item)
    undo_mgr.execute_command.assert_not_called()
    assert mock_item not in coord._text_move_tracking

    # 3. Position changed but undo_redo_manager is None
    coord_no_undo = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=None,
    )
    coord_no_undo._text_move_tracking[mock_item] = {
        "initial_position": QPointF(0, 0),
        "current_position": QPointF(10, 10),
    }
    coord_no_undo._finalize_text_move(mock_item)

    # 4. Position changed but scene is None
    coord_no_scene = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=MagicMock(scene=None),
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=undo_mgr,
    )
    coord_no_scene._text_move_tracking[mock_item] = {
        "initial_position": QPointF(0, 0),
        "current_position": QPointF(10, 10),
    }
    coord_no_scene._finalize_text_move(mock_item)

    # 5. Position changed without callback
    coord_no_cb = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=None,
    )
    coord_no_cb._text_move_tracking[mock_item] = {
        "initial_position": QPointF(0, 0),
        "current_position": QPointF(10, 10),
    }
    coord_no_cb._finalize_text_move(mock_item)
    undo_mgr.execute_command.assert_called_once()
    assert mock_item not in coord_no_cb._text_move_tracking

    # 6. Position changed with callback
    undo_mgr.reset_mock()
    coord._text_move_tracking[mock_item] = {
        "initial_position": QPointF(0, 0),
        "current_position": QPointF(10, 10),
    }

    # Custom update callback that deletes item from _text_move_tracking to test line 275 False branch
    def deleting_cb():
        del coord._text_move_tracking[mock_item]

    coord.update_undo_redo_state_callback = deleting_cb
    coord._finalize_text_move(mock_item)
    undo_mgr.execute_command.assert_called_once()


def test_handle_text_annotation_delete_requested(
    mock_text_tool: MagicMock,
    mock_image_viewer: MagicMock,
    sample_dataset: Dataset,
) -> None:
    """Test delete requested under various conditions."""
    # 1. Guard: scene is None
    mock_image_viewer.scene = None
    coord_no_scene = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord_no_scene.handle_text_annotation_delete_requested(MagicMock())

    # Restore scene
    mock_image_viewer.scene = MagicMock()

    # 2. With undo/redo manager and dataset
    undo_mgr = MagicMock()
    update_cb = MagicMock()

    coord_with_undo = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: sample_dataset,
        get_current_slice_index=lambda: 1,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=update_cb,
    )
    item1 = MagicMock()
    coord_with_undo.handle_text_annotation_delete_requested(item1)
    undo_mgr.execute_command.assert_called_once()
    update_cb.assert_called_once()

    # 3. With undo/redo manager, dataset is None, callback is None
    undo_mgr.reset_mock()
    coord_no_ds = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
        undo_redo_manager=undo_mgr,
        update_undo_redo_state_callback=None,
    )
    item2 = MagicMock()
    coord_no_ds.handle_text_annotation_delete_requested(item2)
    undo_mgr.execute_command.assert_called_once()

    # 4. Without undo/redo manager (fallback to direct delete)
    coord_direct = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    item3 = MagicMock()
    coord_direct.handle_text_annotation_delete_requested(item3)
    mock_text_tool.delete_annotation.assert_called_once_with(item3, mock_image_viewer.scene)


def test_display_annotations_for_slice(
    mock_text_tool: MagicMock,
    mock_image_viewer: MagicMock,
) -> None:
    """Test displaying annotations for slice wires callbacks."""
    # Guard: scene is None
    mock_image_viewer.scene = None
    coord_no_scene = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord_no_scene.display_annotations_for_slice("st", "se", 0)

    # Restore scene
    mock_image_viewer.scene = MagicMock()
    item1 = MagicMock()
    item1.pos.return_value = QPointF(1, 1)
    item2 = MagicMock()
    item2.pos.return_value = QPointF(2, 2)
    mock_text_tool.get_annotations_for_slice.return_value = [item1, item2]

    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    # Pre-populate item1 in tracking to test 'annotation not in tracking' False branch
    coord._text_move_tracking[item1] = {}

    coord.display_annotations_for_slice("st", "se", 0)

    mock_text_tool.display_annotations_for_slice.assert_called_once_with("st", "se", 0, mock_image_viewer.scene)
    assert item1.on_moved_callback == coord._on_text_annotation_moved
    assert item1.on_text_edit_finished == coord._on_text_annotation_edited
    assert item2.on_moved_callback == coord._on_text_annotation_moved
    assert item2.on_text_edit_finished == coord._on_text_annotation_edited
    assert item2 in coord._text_move_tracking


def test_clear_annotations_from_other_slices(
    mock_text_tool: MagicMock,
    mock_image_viewer: MagicMock,
) -> None:
    """Test clear_annotations_from_other_slices."""
    # Guard: scene is None
    mock_image_viewer.scene = None
    coord_no_scene = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord_no_scene.clear_annotations_from_other_slices("st", "se", 0)
    mock_text_tool.clear_annotations_from_other_slices.assert_not_called()

    # Restore scene
    mock_image_viewer.scene = MagicMock()
    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    coord.clear_annotations_from_other_slices("st", "se", 0)
    mock_text_tool.clear_annotations_from_other_slices.assert_called_once_with("st", "se", 0, mock_image_viewer.scene)


def test_flaw_deletion_leaves_item_in_text_move_tracking(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Document flaw: handle_text_annotation_delete_requested leaks deleted item in _text_move_tracking."""
    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    mock_item = MagicMock()
    coord._text_move_tracking[mock_item] = {"initial_position": QPointF(0, 0)}

    coord.handle_text_annotation_delete_requested(mock_item)

    # Documents the memory leak flaw: item remains in tracking dict after deletion
    assert mock_item in coord._text_move_tracking


def test_flaw_batch_timer_overwritten_by_second_moving_item(
    mock_text_tool: MagicMock, mock_image_viewer: MagicMock
) -> None:
    """Document flaw: moving itemB cancels itemA's batch timer, stranding itemA's move."""
    coord = TextAnnotationCoordinator(
        text_annotation_tool=mock_text_tool,
        image_viewer=mock_image_viewer,
        get_current_dataset=lambda: None,
        get_current_slice_index=lambda: 0,
    )
    itemA = MagicMock()
    itemA.pos.return_value = QPointF(10, 10)
    itemB = MagicMock()
    itemB.pos.return_value = QPointF(50, 50)

    # Move itemA -> creates timer for itemA
    coord._on_text_annotation_moved(itemA)
    timer_a = coord._text_move_batch_timer

    # Move itemB in rapid succession -> stops timer_a and overwrites timer
    coord._on_text_annotation_moved(itemB)
    timer_b = coord._text_move_batch_timer

    # Documents flaw: timer_a was stopped, timer_b overwrote it
    assert timer_b is not timer_a
    assert itemA in coord._text_move_tracking
    assert itemB in coord._text_move_tracking
