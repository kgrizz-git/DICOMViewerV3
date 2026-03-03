"""
Metadata controller module.

Coordinates the metadata panel, tag edit history, and related undo/redo and
privacy behavior for the DICOM Viewer application. This controller is intended
to centralize metadata-related responsibilities that were previously handled
directly by DICOMViewerApp.

Inputs / dependencies:
- Config manager instance
- TagEditHistoryManager instance
- UndoRedoManager instance
- Callback used to refresh tag UI when metadata changes

Outputs / responsibilities:
- Creates and owns a MetadataPanel instance
- Wires undo/redo callbacks and history manager
- Manages privacy mode for the metadata panel
- Provides helper methods to interact with metadata-related state

Requirements:
- This module assumes PySide6/Qt has been initialized by the caller.
- The caller is responsible for integrating the controller with the rest of
  the application (signals, dataset changes, etc.).
"""

from __future__ import annotations

from typing import Callable, Optional

from core.tag_edit_history import TagEditHistoryManager
from utils.undo_redo import UndoRedoManager
from gui.metadata_panel import MetadataPanel


class MetadataController:
    """
    Controller that owns and coordinates the metadata panel and related history.

    This controller is designed to be instantiated by the main application class
    and then used as the single integration point for metadata-related behavior.
    """

    def __init__(
        self,
        config_manager,
        tag_edit_history: TagEditHistoryManager,
        undo_redo_manager: UndoRedoManager,
        ui_refresh_callback: Optional[Callable[[], None]] = None,
        initial_privacy_mode: bool = False,
    ) -> None:
        self._config_manager = config_manager
        self._tag_edit_history = tag_edit_history
        self._undo_redo_manager = undo_redo_manager
        self._ui_refresh_callback = ui_refresh_callback

        # Create the metadata panel using the same configuration and undo/redo
        # manager that were previously passed directly from DICOMViewerApp.
        self.metadata_panel = MetadataPanel(
            config_manager=self._config_manager,
            undo_redo_manager=self._undo_redo_manager,
        )

        # Preserve existing wiring: history manager and UI refresh callback.
        self.metadata_panel.set_history_manager(self._tag_edit_history)
        self.metadata_panel.ui_refresh_callback = self._ui_refresh_callback

        # Set undo/redo callbacks using the central undo/redo manager.
        self.metadata_panel.set_undo_redo_callbacks(
            self._undo_last_edit,
            self._redo_last_edit,
            lambda: self._undo_redo_manager_can_undo(),
            lambda: self._undo_redo_manager_can_redo(),
        )

        # Initialize privacy mode to the given initial state.
        self.metadata_panel.set_privacy_mode(initial_privacy_mode)

    # ------------------------------------------------------------------
    # Undo / redo helpers
    # ------------------------------------------------------------------

    def _undo_last_edit(self) -> None:
        """Undo the last metadata edit using the shared undo/redo manager."""
        if self._undo_redo_manager and self._undo_redo_manager.can_undo():
            self._undo_redo_manager.undo()

    def _redo_last_edit(self) -> None:
        """Redo the last metadata edit using the shared undo/redo manager."""
        if self._undo_redo_manager and self._undo_redo_manager.can_redo():
            self._undo_redo_manager.redo()

    def _undo_redo_manager_can_undo(self) -> bool:
        """Return whether there is an operation available to undo."""
        return bool(self._undo_redo_manager and self._undo_redo_manager.can_undo())

    def _undo_redo_manager_can_redo(self) -> bool:
        """Return whether there is an operation available to redo."""
        return bool(self._undo_redo_manager and self._undo_redo_manager.can_redo())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_privacy_mode(self, enabled: bool) -> None:
        """Set privacy mode on the metadata panel."""
        self.metadata_panel.set_privacy_mode(enabled)

    def set_ui_refresh_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """
        Update the UI refresh callback used by the metadata panel.

        This allows the main application to change how metadata-driven UI
        refreshes are triggered without recreating the controller.
        """
        self._ui_refresh_callback = callback
        self.metadata_panel.ui_refresh_callback = callback

    def can_undo(self) -> bool:
        """Return True if there is a tag-edit action available to undo."""
        return self._undo_redo_manager_can_undo()

    def can_redo(self) -> bool:
        """Return True if there is a tag-edit action available to redo."""
        return self._undo_redo_manager_can_redo()

    def undo_tag_edit(self, dataset) -> bool:
        """
        Undo the last tag edit for the given dataset.

        Returns True if the undo was performed successfully, False otherwise.
        """
        if dataset is not None and self._tag_edit_history:
            return bool(self._tag_edit_history.undo(dataset))
        return False

    def redo_tag_edit(self, dataset) -> bool:
        """
        Redo the last undone tag edit for the given dataset.

        Returns True if the redo was performed successfully, False otherwise.
        """
        if dataset is not None and self._tag_edit_history:
            return bool(self._tag_edit_history.redo(dataset))
        return False

    def clear_tag_history(self) -> None:
        """Clear the tag edit history for all datasets."""
        if self._tag_edit_history:
            self._tag_edit_history.clear_history()

    def refresh_panel_tags(self, search_text: Optional[str] = None) -> None:
        """
        Refresh the metadata panel tag display, clearing internal caches.

        Args:
            search_text: Optional search string to filter the displayed tags.
                         If None, the panel re-uses its current search text.
        """
        self.metadata_panel._cached_tags = None
        if self.metadata_panel.parser is not None:
            self.metadata_panel.parser._tag_cache.clear()
        if search_text is not None:
            self.metadata_panel._populate_tags(search_text)
        else:
            self.metadata_panel._populate_tags()

