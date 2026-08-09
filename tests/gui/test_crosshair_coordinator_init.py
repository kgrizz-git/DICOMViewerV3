"""Tests for CrosshairCoordinator initialization."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset

from gui.crosshair_coordinator import CrosshairCoordinator


@pytest.mark.qt
class TestCrosshairCoordinatorInitialization:
    def test_initialization_stores_all_dependencies(
        self, crosshair_manager, crosshair_image_viewer
    ):
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

        assert coordinator.crosshair_manager is crosshair_manager
        assert coordinator.image_viewer is crosshair_image_viewer
        assert coordinator.get_current_dataset is get_current_dataset
        assert coordinator.get_current_slice_index is get_current_slice_index

    @pytest.mark.qt
    def test_initialization_with_optional_undo_redo(
        self, crosshair_manager, crosshair_image_viewer
    ):
        undo_redo_manager = MagicMock()
        update_callback = MagicMock()

        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_manager,
            image_viewer=crosshair_image_viewer,
            get_current_dataset=lambda: None,
            get_current_slice_index=lambda: 0,
            undo_redo_manager=undo_redo_manager,
            update_undo_redo_state_callback=update_callback,
        )

        assert coordinator.undo_redo_manager is undo_redo_manager
        assert coordinator.update_undo_redo_state_callback is update_callback

    @pytest.mark.qt
    def test_initialization_with_rescaled_values_callback(
        self, crosshair_manager, crosshair_image_viewer
    ):
        get_use_rescaled = MagicMock(return_value=True)

        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_manager,
            image_viewer=crosshair_image_viewer,
            get_current_dataset=lambda: None,
            get_current_slice_index=lambda: 0,
            get_use_rescaled_values=get_use_rescaled,
        )

        assert coordinator.get_use_rescaled_values is get_use_rescaled

    @pytest.mark.qt
    def test_initialization_creates_move_tracking_dict(
        self, crosshair_manager, crosshair_image_viewer
    ):
        coordinator = CrosshairCoordinator(
            crosshair_manager=crosshair_manager,
            image_viewer=crosshair_image_viewer,
            get_current_dataset=lambda: None,
            get_current_slice_index=lambda: 0,
        )

        assert coordinator._crosshair_move_tracking == {}
        assert coordinator._move_batch_timer is not None
