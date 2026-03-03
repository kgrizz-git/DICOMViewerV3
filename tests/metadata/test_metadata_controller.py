"""
Unit tests for MetadataController.

Tests cover:
- Controller construction and ownership of MetadataPanel.
- Privacy mode propagation to MetadataPanel.
- Undo/redo availability queries (can_undo, can_redo).
- undo_tag_edit / redo_tag_edit delegation to TagEditHistoryManager.
- clear_tag_history delegation.
- refresh_panel_tags cache-clearing behaviour.
- set_ui_refresh_callback wiring.

All tests use a real QApplication (via the session-scoped ``qapp`` fixture
from conftest.py) because MetadataPanel is a Qt widget.
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure src/ is on the path so imports resolve correctly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import pytest

from core.tag_edit_history import TagEditHistoryManager
from utils.undo_redo import UndoRedoManager


# ---------------------------------------------------------------------------
# Helpers – lightweight stubs that avoid full widget construction
# ---------------------------------------------------------------------------

def _make_mock_metadata_panel():
    """Return a MagicMock that looks like a MetadataPanel instance."""
    panel = MagicMock()
    panel.parser = None
    panel._cached_tags = None
    return panel


def _make_controller(qapp, privacy: bool = False, refresh_cb=None):
    """
    Instantiate a MetadataController with a real tag-edit history and
    undo/redo manager, patching MetadataPanel so no real widgets are built.
    """
    from metadata.metadata_controller import MetadataController

    tag_history = TagEditHistoryManager(max_history=10)
    undo_redo = UndoRedoManager(max_history=10)

    mock_panel = _make_mock_metadata_panel()

    # Patch MetadataPanel so the controller receives our mock instead.
    with patch('metadata.metadata_controller.MetadataPanel', return_value=mock_panel):
        ctrl = MetadataController(
            config_manager=MagicMock(),
            tag_edit_history=tag_history,
            undo_redo_manager=undo_redo,
            ui_refresh_callback=refresh_cb,
            initial_privacy_mode=privacy,
        )

    # Expose the real history and undo_redo managers for assertions.
    ctrl._tag_edit_history = tag_history
    ctrl._undo_redo_manager = undo_redo
    return ctrl


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestMetadataControllerConstruction:
    """Verify that MetadataController creates and wires MetadataPanel correctly."""

    def test_metadata_panel_is_set(self, qapp):
        ctrl = _make_controller(qapp)
        assert ctrl.metadata_panel is not None

    def test_set_history_manager_called(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl.metadata_panel.set_history_manager.assert_called_once()

    def test_set_undo_redo_callbacks_called(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl.metadata_panel.set_undo_redo_callbacks.assert_called_once()

    def test_initial_privacy_mode_false(self, qapp):
        ctrl = _make_controller(qapp, privacy=False)
        ctrl.metadata_panel.set_privacy_mode.assert_called_with(False)

    def test_initial_privacy_mode_true(self, qapp):
        ctrl = _make_controller(qapp, privacy=True)
        ctrl.metadata_panel.set_privacy_mode.assert_called_with(True)

    def test_ui_refresh_callback_wired(self, qapp):
        cb = MagicMock()
        ctrl = _make_controller(qapp, refresh_cb=cb)
        # The callback should have been assigned to the panel.
        assert ctrl.metadata_panel.ui_refresh_callback == cb


class TestMetadataControllerPrivacy:
    """Test set_privacy_mode delegation."""

    def test_set_privacy_mode_propagates(self, qapp):
        ctrl = _make_controller(qapp, privacy=False)
        ctrl.metadata_panel.reset_mock()
        ctrl.set_privacy_mode(True)
        ctrl.metadata_panel.set_privacy_mode.assert_called_once_with(True)

    def test_set_privacy_mode_false(self, qapp):
        ctrl = _make_controller(qapp, privacy=True)
        ctrl.metadata_panel.reset_mock()
        ctrl.set_privacy_mode(False)
        ctrl.metadata_panel.set_privacy_mode.assert_called_once_with(False)


class TestMetadataControllerUndoRedo:
    """Test can_undo, can_redo, undo_tag_edit, redo_tag_edit."""

    def test_can_undo_false_when_empty(self, qapp):
        ctrl = _make_controller(qapp)
        assert ctrl.can_undo() is False

    def test_can_redo_false_when_empty(self, qapp):
        ctrl = _make_controller(qapp)
        assert ctrl.can_redo() is False

    def test_undo_tag_edit_returns_false_for_none_dataset(self, qapp):
        ctrl = _make_controller(qapp)
        result = ctrl.undo_tag_edit(None)
        assert result is False

    def test_redo_tag_edit_returns_false_for_none_dataset(self, qapp):
        ctrl = _make_controller(qapp)
        result = ctrl.redo_tag_edit(None)
        assert result is False

    def test_undo_tag_edit_delegates_to_history(self, qapp):
        ctrl = _make_controller(qapp)
        mock_dataset = MagicMock()
        ctrl._tag_edit_history = MagicMock()
        ctrl._tag_edit_history.undo.return_value = True
        result = ctrl.undo_tag_edit(mock_dataset)
        ctrl._tag_edit_history.undo.assert_called_once_with(mock_dataset)
        assert result is True

    def test_redo_tag_edit_delegates_to_history(self, qapp):
        ctrl = _make_controller(qapp)
        mock_dataset = MagicMock()
        ctrl._tag_edit_history = MagicMock()
        ctrl._tag_edit_history.redo.return_value = True
        result = ctrl.redo_tag_edit(mock_dataset)
        ctrl._tag_edit_history.redo.assert_called_once_with(mock_dataset)
        assert result is True

    def test_undo_tag_edit_returns_false_on_history_failure(self, qapp):
        ctrl = _make_controller(qapp)
        mock_dataset = MagicMock()
        ctrl._tag_edit_history = MagicMock()
        ctrl._tag_edit_history.undo.return_value = False
        result = ctrl.undo_tag_edit(mock_dataset)
        assert result is False


class TestMetadataControllerClearHistory:
    """Test clear_tag_history."""

    def test_clear_tag_history_calls_through(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl._tag_edit_history = MagicMock()
        ctrl.clear_tag_history()
        ctrl._tag_edit_history.clear_history.assert_called_once()

    def test_clear_tag_history_no_error_when_history_none(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl._tag_edit_history = None
        # Should not raise
        ctrl.clear_tag_history()


class TestMetadataControllerRefreshPanelTags:
    """Test refresh_panel_tags cache-clearing and populate_tags delegation."""

    def test_refresh_clears_cached_tags(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl.metadata_panel._cached_tags = object()  # Set to non-None sentinel
        ctrl.refresh_panel_tags()
        assert ctrl.metadata_panel._cached_tags is None

    def test_refresh_without_search_text_calls_populate(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl.refresh_panel_tags()
        ctrl.metadata_panel._populate_tags.assert_called()

    def test_refresh_with_search_text_passes_it_through(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl.refresh_panel_tags(search_text="patient")
        ctrl.metadata_panel._populate_tags.assert_called_with("patient")

    def test_refresh_clears_parser_cache_if_present(self, qapp):
        ctrl = _make_controller(qapp)
        mock_parser = MagicMock()
        ctrl.metadata_panel.parser = mock_parser
        ctrl.refresh_panel_tags()
        mock_parser._tag_cache.clear.assert_called_once()


class TestMetadataControllerUiCallback:
    """Test set_ui_refresh_callback wiring."""

    def test_callback_is_updated_on_panel(self, qapp):
        ctrl = _make_controller(qapp)
        new_cb = MagicMock()
        ctrl.set_ui_refresh_callback(new_cb)
        assert ctrl.metadata_panel.ui_refresh_callback == new_cb
        assert ctrl._ui_refresh_callback == new_cb

    def test_callback_can_be_set_to_none(self, qapp):
        ctrl = _make_controller(qapp)
        ctrl.set_ui_refresh_callback(None)
        assert ctrl.metadata_panel.ui_refresh_callback is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
