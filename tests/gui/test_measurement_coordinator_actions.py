"""Focused public-action tests for MeasurementCoordinator."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QGraphicsScene

from gui.measurement_coordinator import MeasurementCoordinator


def _dataset() -> Dataset:
    dataset = Dataset()
    dataset.StudyInstanceUID = "1.2.3"
    dataset.SeriesInstanceUID = "1.2.3.4"
    dataset.SeriesNumber = 7
    return dataset


def _coordinator(
    qapp, *, scene=Ellipsis, dataset: Dataset | None = None, tool=None, viewer=None
) -> MeasurementCoordinator:
    tool = tool or MagicMock()
    if viewer is None:
        viewer = SimpleNamespace(scene=QGraphicsScene() if scene is Ellipsis else scene)
    return MeasurementCoordinator(
        measurement_tool=tool,
        image_viewer=viewer,
        get_current_dataset=lambda: dataset,
        get_current_slice_index=lambda: 4,
    )


@pytest.mark.qt
def test_start_measurement_sets_slice_context_cancels_angle_and_starts(qapp) -> None:
    tool = MagicMock()
    coordinator = _coordinator(qapp, dataset=_dataset(), tool=tool)
    position = QPointF(10, 20)

    coordinator.handle_measurement_started(position)

    tool.cancel_angle_in_progress.assert_called_once_with(coordinator.image_viewer.scene)
    tool.set_current_slice.assert_called_once_with("1.2.3", "1.2.3.4_7", 4)
    tool.start_measurement.assert_called_once_with(position)


@pytest.mark.qt
def test_start_and_update_work_without_dataset_but_not_without_scene(qapp) -> None:
    tool = MagicMock()
    coordinator = _coordinator(qapp, dataset=None, tool=tool)
    position = QPointF(1, 2)

    coordinator.handle_measurement_started(position)
    coordinator.handle_measurement_updated(position)

    tool.set_current_slice.assert_not_called()
    tool.start_measurement.assert_called_once_with(position)
    tool.update_measurement.assert_called_once_with(position, coordinator.image_viewer.scene)

    no_scene = _coordinator(qapp, scene=None, dataset=_dataset(), tool=MagicMock())
    no_scene.handle_measurement_updated(position)
    no_scene.measurement_tool.update_measurement.assert_not_called()


@pytest.mark.qt
def test_finish_assigns_callbacks_only_when_tool_returns_measurement(qapp) -> None:
    tool = MagicMock()
    committed = SimpleNamespace()
    tool.finish_measurement.return_value = committed
    coordinator = _coordinator(qapp, dataset=_dataset(), tool=tool)

    coordinator.handle_measurement_finished()

    tool.finish_measurement.assert_called_once_with(coordinator.image_viewer.scene)
    assert callable(committed.on_moved_callback)
    assert callable(committed.on_mouse_release_callback)
    assert callable(committed.on_handle_drag_start_callback)

    tool.finish_measurement.reset_mock(return_value=True)
    tool.finish_measurement.return_value = None
    coordinator.handle_measurement_finished()
    assert tool.finish_measurement.call_count == 1


@pytest.mark.qt
def test_angle_actions_route_to_tool_only_when_scene_exists(qapp) -> None:
    tool = MagicMock()
    coordinator = _coordinator(qapp, dataset=_dataset(), tool=tool)
    position = QPointF(3, 5)

    coordinator.handle_angle_draw_cancel_requested()
    coordinator.handle_angle_measurement_preview(position)

    tool.cancel_angle_in_progress.assert_called_once_with(coordinator.image_viewer.scene)
    tool.update_angle_preview.assert_called_once_with(position, coordinator.image_viewer.scene)

    no_scene = _coordinator(qapp, scene=None, tool=MagicMock())
    no_scene.handle_angle_draw_cancel_requested()
    no_scene.handle_angle_measurement_preview(position)
    no_scene.measurement_tool.cancel_angle_in_progress.assert_not_called()
    no_scene.measurement_tool.update_angle_preview.assert_not_called()


@pytest.mark.qt
def test_delete_and_clear_fallbacks_call_tool_with_current_slice(qapp) -> None:
    tool = MagicMock()
    measurement = object()
    tool.measurements = {("1.2.3", "1.2.3.4_7", 4): [measurement]}
    coordinator = _coordinator(qapp, dataset=_dataset(), tool=tool)

    coordinator.handle_measurement_delete_requested(measurement)
    coordinator.handle_clear_measurements()

    tool.delete_measurement.assert_called_once_with(measurement, coordinator.image_viewer.scene)
    tool.clear_slice_measurements.assert_called_once_with(
        "1.2.3", "1.2.3.4_7", 4, coordinator.image_viewer.scene
    )


@pytest.mark.qt
def test_clear_ignores_missing_dataset_identifiers_or_measurements(qapp) -> None:
    tool = MagicMock()
    tool.measurements = {}
    coordinator = _coordinator(qapp, dataset=None, tool=tool)
    coordinator.handle_clear_measurements()

    incomplete = Dataset()
    coordinator = _coordinator(qapp, dataset=incomplete, tool=tool)
    coordinator.handle_clear_measurements()

    complete = _coordinator(qapp, dataset=_dataset(), tool=tool)
    complete.handle_clear_measurements()
    tool.clear_slice_measurements.assert_not_called()


@pytest.mark.qt
def test_handle_drag_controls_magnifier_and_restores_override_cursor(qapp) -> None:
    viewer = MagicMock(scene=QGraphicsScene())
    coordinator = _coordinator(qapp, viewer=viewer)
    position = QPointF(7, 9)

    coordinator._on_handle_drag_start(position, False)
    coordinator._on_handle_drag_move(position)
    coordinator._on_handle_drag_end()

    viewer.show_handle_drag_magnifier.assert_called_once_with(position)
    viewer.update_handle_drag_magnifier.assert_called_once_with(position)
    viewer.hide_handle_drag_magnifier.assert_called_once_with()
    viewer.restore_cursor_for_current_mode.assert_called_once_with()
    assert coordinator._handle_drag_magnifier_enabled is False
    assert QApplication.overrideCursor() is None
