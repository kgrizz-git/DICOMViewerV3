"""Shared helpers for DICOM tag editing UI surfaces."""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

from core.dicom_editor import DICOMEditor
from core.tag_edit_history import TagEditHistoryManager
from core.tag_path import resolve_tag_path
from gui.metadata_table_model import metadata_row_depth, metadata_row_kind
from utils.dicom_tag_keys import leaf_tag_from_key
from utils.undo_redo import UndoRedoManager
from utils.undo_redo_tag_commands import TagEditCommand


def is_editable_metadata_item(item: QTreeWidgetItem) -> bool:
    """Return True for scalar element rows at any depth."""
    tag_data = item.data(0, Qt.ItemDataRole.UserRole + 1)
    return tag_data is not None and metadata_row_kind(tag_data) == "element"


def store_original_value_for_direct_tag_edit(
    *,
    history_manager: TagEditHistoryManager | None,
    dataset: Dataset | None,
    tag_str: str,
) -> None:
    """Store the raw current value before a non-undo-manager edit path mutates it."""
    if history_manager is None or dataset is None:
        return
    if history_manager.get_original_value(dataset, tag_str) is not None:
        return

    resolved = resolve_tag_path(dataset, tag_str)
    if resolved is None:
        return
    containing_dataset, tag = resolved
    if tag not in containing_dataset:
        return
    history_manager.store_original_value(
        dataset, tag_str, copy.deepcopy(containing_dataset[tag].value)
    )


def apply_tag_edit(
    *,
    dataset: Dataset,
    editor: DICOMEditor,
    tag_str: str,
    tag_data: dict[str, Any],
    old_value: Any,
    new_value: Any,
    vr: str,
    undo_redo_manager: UndoRedoManager | None,
    history_manager: TagEditHistoryManager | None,
    ui_refresh_callback: Callable[[], None] | None,
) -> bool:
    """Apply a tag edit through undo/redo when available, otherwise directly."""
    if undo_redo_manager is not None:
        tag = leaf_tag_from_key(tag_str)
        if tag is None:
            return False

        undo_redo_manager.execute_command(
            TagEditCommand(
                dataset,
                tag,
                old_value,
                new_value,
                vr,
                tag_edit_history_manager=history_manager,
                ui_refresh_callback=ui_refresh_callback,
                path_key=tag_str if metadata_row_depth(tag_data) > 0 else None,
            )
        )
        return True

    store_original_value_for_direct_tag_edit(
        history_manager=history_manager,
        dataset=dataset,
        tag_str=tag_str,
    )
    success = editor.update_tag(tag_str, new_value, vr)
    if success and history_manager is not None:
        history_manager.mark_tag_edited(dataset, tag_str)
    return success
