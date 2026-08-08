"""
Select-All / tag-count helpers for the DICOM tag export dialog.

Inputs:
    - Tag tree items and the active union dict used for row_kind lookup

Outputs:
    - Visible exportable leaf iteration, top Select All checkbox sync, count label

Requirements:
    - PySide6 Qt widgets already constructed on the owning dialog
    - gui.metadata_table_model.metadata_row_kind
"""
# Pyright: methods run only on ``TagExportDialog`` (combined Qt type); mixin bases
# cannot express cross-mixin ``self`` without a duplicate protocol surface.
# pyright: reportAttributeAccessIssue=false, reportUninitializedInstanceVariable=false
from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItem

from gui.metadata_table_model import metadata_row_kind


class TagExportDialogSelectionMixin:
    """
    Mixin for visible-leaf Select All behavior and the selected-tag count label.

    Expects the owning dialog to provide ``tags_tree``, union caches, the top
    Select All checkbox, the count label, and ``_iter_all_tag_items`` /
    ``_toggle_all_tags`` / ``_update_selected_tags`` as appropriate.
    """

    def _active_merged_tags_for_kind_lookup(self) -> dict[str, Any]:
        """
        Return the union dict that drove the last tag-tree render.

        Used to resolve ``metadata_row_kind`` for tree items (items store only the
        tag string in UserRole, not the full tag_data / row_kind).
        """
        if self.include_sequences_checkbox.isChecked():
            return self._tag_union_merged_sequences or {}
        return self._tag_union_merged_full or {}

    def _iter_visible_exportable_leaves(self) -> Iterator[QTreeWidgetItem]:
        """
        Yield visible exportable leaf tag items (``row_kind == "element"``).

        Sequence and Item parent rows are independently checkable export columns
        and are intentionally excluded from Select All / the top checkbox aggregate.
        """
        merged = self._active_merged_tags_for_kind_lookup()
        root = self.tags_tree.invisibleRootItem()
        for item in self._iter_all_tag_items(root):
            if item.isHidden():
                continue
            tag_str = item.data(0, Qt.ItemDataRole.UserRole)
            if tag_str is None:
                continue
            tag_data = merged.get(tag_str)
            if tag_data is None:
                continue
            if metadata_row_kind(tag_data) != "element":
                continue
            yield item

    def _on_select_all_tag_checkbox(self, state: Qt.CheckState | int) -> None:
        """
        Apply the top Select All checkbox to visible exportable leaf tags only.

        ``setCheckState(PartiallyChecked)`` forces Qt tristate mode on, so a user
        click from ``Unchecked`` can land on ``PartiallyChecked``. Treat that as
        Select All (not a no-op). ``Checked`` selects all; ``Unchecked`` clears.
        """
        if isinstance(state, int):
            state = Qt.CheckState(state)
        if state == Qt.CheckState.Unchecked:
            self._toggle_all_tags(False)
        else:
            # Checked or PartiallyChecked (first click after a partial mirror)
            self._toggle_all_tags(True)

    def _refresh_select_all_checkbox_state(self) -> None:
        """
        Set the top Select All checkbox from visible exportable leaf check states.

        Uses ``blockSignals`` so programmatic ``setCheckState`` does not re-enter
        ``_on_select_all_tag_checkbox``. When the aggregate is not partial,
        ``setTristate(False)`` is restored so the next user click toggles
        Unchecked↔Checked directly (Qt turns tristate back on whenever
        ``PartiallyChecked`` is applied).
        """
        leaves = list(self._iter_visible_exportable_leaves())
        if not leaves:
            aggregate = Qt.CheckState.Unchecked
        else:
            checked_count = sum(
                1 for item in leaves if item.checkState(0) == Qt.CheckState.Checked
            )
            if checked_count == 0:
                aggregate = Qt.CheckState.Unchecked
            elif checked_count == len(leaves):
                aggregate = Qt.CheckState.Checked
            else:
                aggregate = Qt.CheckState.PartiallyChecked
        self.select_all_tags_checkbox.blockSignals(True)
        if aggregate == Qt.CheckState.PartiallyChecked:
            self.select_all_tags_checkbox.setTristate(True)
            self.select_all_tags_checkbox.setCheckState(aggregate)
        else:
            self.select_all_tags_checkbox.setCheckState(aggregate)
            self.select_all_tags_checkbox.setTristate(False)
        self.select_all_tags_checkbox.blockSignals(False)

    def _refresh_tag_count_label(self) -> None:
        """Update the dialog-bottom label from ``len(self.selected_tags)``."""
        count = len(self.selected_tags)
        if count == 0:
            text = "No tags selected"
        elif count == 1:
            text = "1 tag selected"
        else:
            text = f"{count} tags selected"
        self.tag_count_label.setText(text)
