"""
Characterize ROICoordinator contracts for the Sonar S3776 finish slice.

Covers handle_roi_drawing_finished, handle_roi_delete_requested,
delete_all_rois_current_slice, and handle_scene_selection_changed.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from gui.roi_coordinator import ROICoordinator


def _make_coordinator(**overrides) -> ROICoordinator:
    """Build a coordinator with MagicMock collaborators for unit tests."""
    kwargs = {
        "roi_manager": MagicMock(),
        "roi_list_panel": MagicMock(),
        "roi_statistics_panel": MagicMock(),
        "image_viewer": MagicMock(),
        "dicom_processor": MagicMock(),
        "window_level_controls": MagicMock(),
        "main_window": MagicMock(),
        "get_current_dataset": MagicMock(return_value=None),
        "get_current_slice_index": MagicMock(return_value=2),
        "get_rescale_params": MagicMock(return_value=(1.0, 0.0, "HU", True)),
        "get_projection_enabled": MagicMock(return_value=False),
        "get_projection_type": MagicMock(return_value="aip"),
        "get_projection_slice_count": MagicMock(return_value=4),
        "get_current_studies": MagicMock(return_value={}),
        "get_mpr_pixel_array": MagicMock(return_value=None),
        "get_mpr_output_pixel_spacing": MagicMock(return_value=None),
        "undo_redo_manager": None,
        "update_undo_redo_state_callback": None,
        "crosshair_coordinator": None,
        "set_mouse_mode_callback": None,
    }
    kwargs.update(overrides)
    kwargs["image_viewer"].scene = MagicMock()
    kwargs["image_viewer"].mouse_mode = "roi"
    kwargs["image_viewer"].is_mpr_view_callback = MagicMock(return_value=False)
    kwargs["image_viewer"].set_mouse_mode = MagicMock()
    kwargs["main_window"].mouse_mode_pan_action = MagicMock()
    kwargs["main_window"].mouse_mode_auto_window_level_action = MagicMock()
    return ROICoordinator(**kwargs)


def _dataset(study: str = "study-1", series: str = "series-1") -> SimpleNamespace:
    return SimpleNamespace(StudyInstanceUID=study, SeriesInstanceUID=series)


def _roi(**attrs) -> MagicMock:
    roi = MagicMock()
    roi.shape_type = "rectangle"
    roi.statistics_overlay_item = None
    roi.statistics_overlay_visible = False
    for key, value in attrs.items():
        setattr(roi, key, value)
    return roi


@pytest.mark.qt
def test_drawing_finished_auto_wl_sets_controls_and_deletes_roi(qapp) -> None:
    ds = _dataset()
    roi = _roi()
    coord = _make_coordinator(
        get_current_dataset=MagicMock(return_value=ds),
        set_mouse_mode_callback=MagicMock(),
    )
    coord.image_viewer.mouse_mode = "auto_window_level"
    coord.roi_manager.finish_drawing.return_value = roi
    coord.roi_manager.calculate_statistics.return_value = {
        "min": 10.0,
        "max": 50.0,
    }
    with patch.object(
        coord, "_get_pixel_array_for_statistics", return_value=np.ones((4, 4))
    ):
        coord.handle_roi_drawing_finished()

    coord.window_level_controls.set_window_level.assert_called_once_with(30.0, 40.0)
    coord.roi_manager.delete_roi.assert_called_once_with(roi, coord.image_viewer.scene)
    coord.roi_statistics_panel.clear_statistics.assert_called()
    coord.roi_list_panel.update_roi_list.assert_called_once()
    coord.set_mouse_mode_callback.assert_called_once_with("pan")


@pytest.mark.qt
def test_drawing_finished_normal_path_executes_add_command(qapp) -> None:
    ds = _dataset()
    roi = _roi()
    undo = MagicMock()
    update_state = MagicMock()
    coord = _make_coordinator(
        get_current_dataset=MagicMock(return_value=ds),
        undo_redo_manager=undo,
        update_undo_redo_state_callback=update_state,
    )
    coord.roi_manager.finish_drawing.return_value = roi

    with (
        patch("utils.undo_redo.ROICommand") as cmd_cls,
        patch.object(coord, "update_roi_statistics") as update_stats,
        patch.object(coord, "_auto_show_resize_handles_after_select") as handles,
    ):
        coord.handle_roi_drawing_finished()

    cmd_cls.assert_called_once()
    assert cmd_cls.call_args[0][1] == "add"
    undo.execute_command.assert_called_once()
    update_state.assert_called_once()
    coord.roi_list_panel.select_roi_in_list.assert_called_once_with(roi)
    update_stats.assert_called_once_with(roi)
    handles.assert_called_once_with(roi)
    assert roi.on_moved_callback is not None


@pytest.mark.qt
def test_delete_requested_uses_undo_command(qapp) -> None:
    ds = _dataset()
    roi = _roi()
    item = MagicMock()
    undo = MagicMock()
    update_state = MagicMock()
    coord = _make_coordinator(
        get_current_dataset=MagicMock(return_value=ds),
        undo_redo_manager=undo,
        update_undo_redo_state_callback=update_state,
    )
    coord.roi_manager.find_roi_by_item.return_value = roi
    coord.roi_manager.get_selected_roi.return_value = None

    with (
        patch("utils.undo_redo.ROICommand") as cmd_cls,
        patch.object(coord, "handle_roi_deleted") as deleted,
    ):
        coord.handle_roi_delete_requested(item)

    roi.hide_resize_handles.assert_called_once_with(coord.image_viewer.scene)
    coord.roi_manager.exit_roi_geometry_edit_mode.assert_called_once()
    cmd_cls.assert_called_once()
    assert cmd_cls.call_args[0][1] == "remove"
    undo.execute_command.assert_called_once()
    update_state.assert_called_once()
    deleted.assert_called_once_with(roi)
    coord.roi_list_panel.update_roi_list.assert_called_once()
    coord.roi_statistics_panel.clear_statistics.assert_called_once()


@pytest.mark.qt
def test_delete_requested_falls_back_without_undo(qapp) -> None:
    ds = _dataset()
    roi = _roi()
    coord = _make_coordinator(get_current_dataset=MagicMock(return_value=ds))
    coord.roi_manager.find_roi_by_item.return_value = roi
    coord.roi_manager.get_selected_roi.return_value = roi

    with patch.object(coord, "handle_roi_deleted"):
        coord.handle_roi_delete_requested(MagicMock())

    coord.roi_manager.delete_roi.assert_called_once_with(roi, coord.image_viewer.scene)
    coord.roi_statistics_panel.clear_statistics.assert_not_called()


@pytest.mark.qt
def test_delete_all_builds_composite_for_rois_and_crosshairs(qapp) -> None:
    ds = _dataset()
    roi_a = _roi()
    roi_b = _roi()
    cross = MagicMock()
    undo = MagicMock()
    update_state = MagicMock()
    crosshair_coord = MagicMock()
    crosshair_coord.crosshair_manager = MagicMock()
    crosshair_coord.crosshair_manager.crosshairs = {
        ("study-1", "series-1", 2): [cross]
    }
    coord = _make_coordinator(
        get_current_dataset=MagicMock(return_value=ds),
        undo_redo_manager=undo,
        update_undo_redo_state_callback=update_state,
        crosshair_coordinator=crosshair_coord,
    )
    coord.roi_manager.rois = {("study-1", "series-1", 2): [roi_a, roi_b]}

    with (
        patch("utils.undo_redo.ROICommand") as roi_cmd,
        patch("utils.undo_redo.CrosshairCommand") as ch_cmd,
        patch("utils.undo_redo.CompositeCommand") as composite,
    ):
        coord.delete_all_rois_current_slice()

    assert roi_cmd.call_count == 2
    ch_cmd.assert_called_once()
    composite.assert_called_once()
    undo.execute_command.assert_called_once()
    update_state.assert_called_once()
    coord.roi_list_panel.update_roi_list.assert_called_once()
    coord.roi_statistics_panel.clear_statistics.assert_called_once()


@pytest.mark.qt
def test_delete_all_noop_when_slice_empty(qapp) -> None:
    ds = _dataset()
    coord = _make_coordinator(get_current_dataset=MagicMock(return_value=ds))
    coord.roi_manager.rois = {}
    coord.delete_all_rois_current_slice()
    coord.roi_manager.exit_roi_geometry_edit_mode.assert_not_called()
    coord.roi_list_panel.update_roi_list.assert_not_called()


@pytest.mark.qt
def test_scene_selection_syncs_selected_roi(qapp) -> None:
    roi = _roi()
    item = MagicMock()
    coord = _make_coordinator()
    coord.image_viewer.scene.selectedItems.return_value = [item]
    coord.roi_manager.find_roi_by_item.return_value = roi

    with (
        patch.object(coord, "update_roi_statistics") as update_stats,
        patch.object(coord, "_auto_show_resize_handles_after_select") as handles,
    ):
        coord.handle_scene_selection_changed()

    update_stats.assert_called_once_with(roi)
    coord.roi_list_panel.select_roi_in_list.assert_called_once_with(roi)
    handles.assert_called_once_with(roi)


@pytest.mark.qt
def test_scene_selection_refreshes_overlay_positions_when_deselected(qapp) -> None:
    ds = _dataset()
    roi = _roi(statistics_overlay_item=MagicMock(), statistics_overlay_visible=True)
    coord = _make_coordinator(get_current_dataset=MagicMock(return_value=ds))
    coord.image_viewer.scene.selectedItems.return_value = []
    coord.roi_manager.get_rois_for_slice.return_value = [roi]

    coord.handle_scene_selection_changed()

    coord.roi_manager.update_statistics_overlay_position.assert_called_once_with(
        roi, coord.image_viewer.scene
    )
