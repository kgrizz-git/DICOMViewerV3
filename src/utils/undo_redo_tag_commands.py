"""
DICOM tag edit commands for the unified undo/redo stack.

Phase 5E extraction from ``undo_redo.py``: keeps ROI/measurement/annotation
commands in the core module while tag-edit/pydicom mutation lives here.
``TagEditCommand`` is imported at the **end** of ``undo_redo.py`` and exposed
there so existing ``from utils.undo_redo import TagEditCommand`` imports keep
working.

Inputs:
    - Target dataset, pydicom tag, old/new values, optional VR, optional
      ``TagEditHistoryManager``, optional UI refresh callback.

Outputs:
    - ``TagEditCommand`` instances executed by ``UndoRedoManager``.

Requirements:
    - ``utils.undo_redo.Command``
    - pydicom (dataset elements, dictionary VR lookup, tag objects)
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from pydicom.dataelem import DataElement
from pydicom.datadict import dictionary_VR
from pydicom.tag import BaseTag
from pydicom.tag import Tag as make_tag

from utils.undo_redo import Command


class TagEditCommand(Command):
    """
    Command for DICOM tag edit operations.
    Integrates tag edits into the unified undo/redo system.
    """

    def __init__(
        self,
        dataset,
        tag,
        old_value: Any,
        new_value: Any,
        vr: Optional[str] = None,
        tag_edit_history_manager=None,
        ui_refresh_callback: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize tag edit command.

        Args:
            dataset: DICOM dataset to edit
            tag: pydicom Tag object or tag tuple
            old_value: Original value (None if tag didn't exist)
            new_value: New value to set
            vr: Value Representation (optional)
            tag_edit_history_manager: TagEditHistoryManager for tracking edited tags
            ui_refresh_callback: Optional callback to refresh UI after edit
        """
        self.dataset = dataset
        self.tag = tag
        self.old_value = old_value
        self.new_value = new_value
        self.vr = vr
        self.tag_edit_history_manager = tag_edit_history_manager
        self.ui_refresh_callback = ui_refresh_callback

    def get_target_dataset(self):
        """Get the target dataset for editing (handles wrapped datasets)."""
        if hasattr(self.dataset, "_original_dataset"):
            return self.dataset._original_dataset
        return self.dataset

    def get_tag_string(self) -> str:
        """Get tag as string for tracking."""
        if self.tag is None:
            return ""
        try:
            tag_obj = self.tag if isinstance(self.tag, BaseTag) else make_tag(self.tag)
            return f"({tag_obj.group:04X},{tag_obj.element:04X})"
        except Exception:
            return str(self.tag)

    def _resolve_vr(self) -> str:
        if self.vr is not None:
            return self.vr
        try:
            return dictionary_VR(self.tag)
        except (KeyError, AttributeError):
            return "LO"

    def execute(self) -> None:
        """Execute the command - set new value."""
        if self.tag is None:
            return

        target_dataset = self.get_target_dataset()

        try:
            if self.tag_edit_history_manager:
                tag_str = self.get_tag_string()
                if self.tag_edit_history_manager.get_original_value(self.dataset, tag_str) is None:
                    self.tag_edit_history_manager.store_original_value(
                        self.dataset, tag_str, self.old_value
                    )

            if self.new_value is None:
                if self.tag in target_dataset:
                    del target_dataset[self.tag]
                if hasattr(self.dataset, "_original_dataset") and self.dataset is not target_dataset:
                    if self.tag in self.dataset:
                        del self.dataset[self.tag]
            else:
                if self.tag in target_dataset:
                    target_dataset[self.tag].value = self.new_value
                else:
                    vr = self._resolve_vr()
                    new_elem = DataElement(self.tag, vr, self.new_value)
                    target_dataset.add(new_elem)

                if hasattr(self.dataset, "_original_dataset") and self.dataset is not target_dataset:
                    if self.tag in self.dataset:
                        self.dataset[self.tag].value = self.new_value
                    else:
                        vr = self._resolve_vr()
                        new_elem = DataElement(self.tag, vr, self.new_value)
                        self.dataset.add(new_elem)

            if self.tag_edit_history_manager:
                self.tag_edit_history_manager.mark_tag_edited(
                    self.dataset, self.get_tag_string(), self.new_value
                )

            if self.ui_refresh_callback:
                self.ui_refresh_callback()

        except Exception as e:
            print(f"Error executing tag edit command: {e}")
            raise

    def undo(self) -> None:
        """Undo the command - restore old value."""
        if self.tag is None:
            return

        target_dataset = self.get_target_dataset()

        try:
            if self.old_value is None:
                if self.tag in target_dataset:
                    del target_dataset[self.tag]
                if hasattr(self.dataset, "_original_dataset") and self.dataset is not target_dataset:
                    if self.tag in self.dataset:
                        del self.dataset[self.tag]
            else:
                if self.tag in target_dataset:
                    target_dataset[self.tag].value = self.old_value
                else:
                    vr = self._resolve_vr()
                    new_elem = DataElement(self.tag, vr, self.old_value)
                    target_dataset.add(new_elem)

                if hasattr(self.dataset, "_original_dataset") and self.dataset is not target_dataset:
                    if self.tag in self.dataset:
                        self.dataset[self.tag].value = self.old_value
                    else:
                        vr = self._resolve_vr()
                        new_elem = DataElement(self.tag, vr, self.old_value)
                        self.dataset.add(new_elem)

            if self.tag_edit_history_manager:
                tag_str = self.get_tag_string()
                self.tag_edit_history_manager.mark_tag_edited(self.dataset, tag_str, self.old_value)

            if self.ui_refresh_callback:
                self.ui_refresh_callback()

        except Exception as e:
            print(f"Error undoing tag edit command: {e}")
            raise
