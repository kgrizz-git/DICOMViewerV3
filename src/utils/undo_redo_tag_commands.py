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

import copy
from collections.abc import Callable
from typing import Any

from pydicom.datadict import dictionary_VR
from pydicom.dataelem import DataElement
from pydicom.tag import BaseTag
from pydicom.tag import Tag as make_tag

from utils.dicom_tag_path import resolve_tag_path
from utils.dicom_value_conversion import convert_dicom_value
from utils.undo_redo_command import Command


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
        vr: str | None = None,
        tag_edit_history_manager=None,
        ui_refresh_callback: Callable[[], None] | None = None,
        path_key: str | None = None,
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
            path_key: Optional parser path key for nested sequence elements
        """
        self.dataset = dataset
        self.tag = tag
        self.old_value = old_value
        self.new_value = new_value
        self.vr = vr
        self.tag_edit_history_manager = tag_edit_history_manager
        self.ui_refresh_callback = ui_refresh_callback
        self.path_key = path_key
        self._captured_old_values: dict[int, Any] = {}

    def get_target_dataset(self):
        """Get the target dataset for editing (handles wrapped datasets)."""
        if hasattr(self.dataset, "_original_dataset"):
            return self.dataset._original_dataset
        return self.dataset

    def get_tag_string(self) -> str:
        """Get tag as string for tracking."""
        if self.path_key is not None:
            return self.path_key
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

    def _tag_obj(self) -> BaseTag | None:
        if self.tag is None:
            return None
        return self.tag if isinstance(self.tag, BaseTag) else make_tag(self.tag)

    def _datasets_to_write(self):
        target_dataset = self.get_target_dataset()
        datasets = [target_dataset]
        if hasattr(self.dataset, "_original_dataset") and self.dataset is not target_dataset:
            datasets.append(self.dataset)
        return datasets

    def _resolve_write_targets(self) -> list[tuple[Any, BaseTag]]:
        if self.path_key is not None:
            if self.new_value is None:
                raise ValueError("Nested tag deletion is not supported")
            resolved_targets = []
            for dataset in self._datasets_to_write():
                resolved = resolve_tag_path(dataset, self.path_key)
                if resolved is None:
                    raise ValueError(f"Unresolvable tag path: {self.path_key}")
                containing_dataset, tag = resolved
                if tag not in containing_dataset:
                    raise ValueError(f"Nested tag does not exist: {self.path_key}")
                if getattr(containing_dataset[tag], "VR", None) == "SQ":
                    raise ValueError(f"Cannot edit sequence parent: {self.path_key}")
                resolved_targets.append((containing_dataset, tag))
            return resolved_targets

        tag = self._tag_obj()
        if tag is None:
            return []
        return [(dataset, tag) for dataset in self._datasets_to_write()]

    def _capture_old_values(self, targets: list[tuple[Any, BaseTag]]) -> None:
        for containing_dataset, tag in targets:
            dataset_id = id(containing_dataset)
            if dataset_id in self._captured_old_values:
                continue
            if tag in containing_dataset:
                self._captured_old_values[dataset_id] = copy.deepcopy(
                    containing_dataset[tag].value
                )
            else:
                self._captured_old_values[dataset_id] = None

    def _old_value_for(self, containing_dataset) -> Any:
        dataset_id = id(containing_dataset)
        if dataset_id in self._captured_old_values:
            return self._captured_old_values[dataset_id]
        return self.old_value

    def _history_old_value(self, targets: list[tuple[Any, BaseTag]]) -> Any:
        for containing_dataset, _tag in targets:
            if containing_dataset is self.dataset:
                return self._old_value_for(containing_dataset)
        return self._old_value_for(targets[0][0]) if targets else self.old_value

    def _apply_value(self, containing_dataset, tag: BaseTag, value: Any) -> None:
        if value is None:
            if tag in containing_dataset:
                del containing_dataset[tag]
            return

        converted_value = convert_dicom_value(value, self.vr)
        if tag in containing_dataset:
            containing_dataset[tag].value = converted_value
        else:
            vr = self._resolve_vr()
            new_elem = DataElement(tag, vr, converted_value)
            containing_dataset.add(new_elem)

    def execute(self) -> None:
        """Execute the command - set new value."""
        if self.tag is None:
            return

        try:
            targets = self._resolve_write_targets()
            self._capture_old_values(targets)

            if self.tag_edit_history_manager:
                tag_str = self.get_tag_string()
                if self.tag_edit_history_manager.get_original_value(self.dataset, tag_str) is None:
                    self.tag_edit_history_manager.store_original_value(
                        self.dataset, tag_str, self._history_old_value(targets)
                    )

            for containing_dataset, tag in targets:
                self._apply_value(containing_dataset, tag, self.new_value)

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

        try:
            targets = self._resolve_write_targets()
            for containing_dataset, tag in targets:
                self._apply_value(containing_dataset, tag, self._old_value_for(containing_dataset))

            if self.tag_edit_history_manager:
                tag_str = self.get_tag_string()
                self.tag_edit_history_manager.mark_tag_edited(
                    self.dataset, tag_str, self._history_old_value(targets)
                )

            if self.ui_refresh_callback:
                self.ui_refresh_callback()

        except Exception as e:
            print(f"Error undoing tag edit command: {e}")
            raise
