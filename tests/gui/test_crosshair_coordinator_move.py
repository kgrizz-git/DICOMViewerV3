"""Tests for CrosshairCoordinator crosshair movement handling."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF

from gui.crosshair_coordinator import CrosshairCoordinator


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

        # Timer should be reused (same instance) and restarted for debounce
        assert crosshair_coordinator._move_batch_timer is first_timer
        assert crosshair_coordinator._move_batch_timer.isActive()

    @pytest.mark.qt
    def test_finalizes_previous_pending_item_when_different_crosshair_moves(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        undo_redo_manager = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager

        first_item = MagicMock()
        first_item.pos.return_value = QPointF(10, 20)
        second_item = MagicMock()
        second_item.pos.return_value = QPointF(30, 40)

        crosshair_coordinator._on_crosshair_moved(first_item)
        first_item.pos.return_value = QPointF(12, 22)
        crosshair_coordinator._on_crosshair_moved(first_item)

        crosshair_coordinator._on_crosshair_moved(second_item)

        assert first_item not in crosshair_coordinator._crosshair_move_tracking
        assert second_item in crosshair_coordinator._crosshair_move_tracking
        assert crosshair_coordinator._pending_move_item is second_item
        undo_redo_manager.execute_command.assert_called_once()

        second_item.pos.return_value = QPointF(35, 45)
        crosshair_coordinator._on_crosshair_moved(second_item)

        crosshair_coordinator._on_move_batch_timer_timeout()

        assert second_item not in crosshair_coordinator._crosshair_move_tracking
        assert undo_redo_manager.execute_command.call_count == 2


@pytest.mark.qt
class TestFinalizeCrosshairMove:
    def test_updates_pixel_values_at_new_position(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        crosshair_item = MagicMock()
        crosshair_item.pos.return_value = QPointF(15, 25)
        crosshair_coordinator._crosshair_move_tracking[crosshair_item] = {
            'initial_pos': QPointF(10, 20),
            'current_pos': QPointF(15, 25)
        }

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        # Verify pixel value was updated
        crosshair_item.update_pixel_values.assert_called_once()

    @pytest.mark.qt
    def test_creates_undo_command_when_position_changed(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        undo_redo_manager = MagicMock()
        update_callback = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager
        crosshair_coordinator.update_undo_redo_state_callback = update_callback
        crosshair_item = MagicMock()
        crosshair_item.pos.return_value = QPointF(15, 25)
        crosshair_coordinator._crosshair_move_tracking[crosshair_item] = {
            'initial_pos': QPointF(10, 20),
            'current_pos': QPointF(15, 25)
        }

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        undo_redo_manager.execute_command.assert_called_once()
        update_callback.assert_called_once()

    @pytest.mark.qt
    def test_does_not_create_command_when_position_unchanged(
        self, crosshair_coordinator: CrosshairCoordinator, crosshair_sample_dataset: Dataset
    ):
        crosshair_coordinator.get_current_dataset = lambda: crosshair_sample_dataset
        undo_redo_manager = MagicMock()
        crosshair_coordinator.undo_redo_manager = undo_redo_manager
        crosshair_item = MagicMock()
        crosshair_item.pos.return_value = QPointF(10, 20)
        crosshair_coordinator._crosshair_move_tracking[crosshair_item] = {
            'initial_pos': QPointF(10, 20),
            'current_pos': QPointF(10, 20)
        }

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        undo_redo_manager.execute_command.assert_not_called()

    @pytest.mark.qt
    def test_clears_tracking_after_finalization(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_item = MagicMock()
        crosshair_item.pos.return_value = QPointF(10, 20)
        crosshair_coordinator._crosshair_move_tracking[crosshair_item] = {
            'initial_pos': QPointF(10, 20),
            'current_pos': QPointF(10, 20)
        }

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        assert crosshair_item not in crosshair_coordinator._crosshair_move_tracking

    @pytest.mark.qt
    def test_returns_early_when_crosshair_not_tracked(
        self, crosshair_coordinator: CrosshairCoordinator
    ):
        crosshair_item = MagicMock()

        crosshair_coordinator._finalize_crosshair_move(crosshair_item)

        # Should not raise
        assert True
