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
from gui.qt_tree_widget_utils import iter_tree_children


class TagExportDialogSelectionMixin:
    """
    Mixin for visible-leaf Select All behavior, group-header tri-state, and
    the selected-tag count label.

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

    def _iter_visible_exportable_leaves(
        self, start_item: QTreeWidgetItem | None = None
    ) -> Iterator[QTreeWidgetItem]:
        """
        Yield visible exportable leaf tag items (``row_kind == "element"``).

        When *start_item* is given, only leaves beneath it are yielded (used by
        the group-header tri-state pass); otherwise the whole tree is walked.

        Sequence and Item parent rows are independently checkable export columns
        and are intentionally excluded from Select All / the top checkbox aggregate.
        """
        merged = self._active_merged_tags_for_kind_lookup()
        if start_item is None:
            start_item = self.tags_tree.invisibleRootItem()
        for item in self._iter_all_tag_items(start_item):
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

    def _on_tag_tree_item_collapsed(self, item: QTreeWidgetItem) -> None:
        """
        Return immediately while ``_filter_tags`` is walking.

        Outside filtering this is a no-op in Phase A; Phase B uses it for
        stripe parity.
        """
        if self._is_filtering or self._suspend_expand_signals:
            return
        del item

    def _visible_children_aggregate(
        self, item: QTreeWidgetItem
    ) -> Qt.CheckState | None:
        """
        Aggregate *item*'s tri-state from its **visible direct children**.

        Returns ``None`` when there are no visible children (callers leave such
        parents untouched).
        """
        any_visible_child = False
        all_checked = True
        any_checked = False
        for child in iter_tree_children(item):
            if child.isHidden():
                continue
            any_visible_child = True
            child_state = child.checkState(0)
            if child_state == Qt.CheckState.Checked:
                any_checked = True
            elif child_state == Qt.CheckState.PartiallyChecked:
                any_checked = True
                all_checked = False
            else:
                all_checked = False

        if not any_visible_child:
            return None
        if all_checked:
            return Qt.CheckState.Checked
        if any_checked:
            return Qt.CheckState.PartiallyChecked
        return Qt.CheckState.Unchecked

    def _exportable_leaf_aggregate(
        self, item: QTreeWidgetItem
    ) -> Qt.CheckState | None:
        """
        Aggregate *item*'s tri-state from its **visible exportable leaves**.

        Sequence/Item parent rows are not part of the aggregation, so a group
        that still has an independently unchecked SQ summary row can still read
        ``Checked`` once its leaves are all selected. Returns ``None`` when
        there are no visible exportable leaves.
        """
        any_visible_leaf = False
        all_checked = True
        any_checked = False
        for leaf in self._iter_visible_exportable_leaves(start_item=item):
            any_visible_leaf = True
            leaf_state = leaf.checkState(0)
            if leaf_state == Qt.CheckState.Checked:
                any_checked = True
            elif leaf_state == Qt.CheckState.PartiallyChecked:
                any_checked = True
                all_checked = False
            else:
                all_checked = False

        if not any_visible_leaf:
            return None
        if all_checked:
            return Qt.CheckState.Checked
        if any_checked:
            return Qt.CheckState.PartiallyChecked
        return Qt.CheckState.Unchecked

    def _update_ancestors_check_state(self, item: QTreeWidgetItem | None) -> None:
        """
        Recompute tri-state check state from *item* up to the tree root.

        Sequence/Item ancestors use visible **direct children**. Group headers
        (no tag string in ``UserRole``) use visible **exportable leaves**.
        """
        while item is not None:
            if item.data(0, Qt.ItemDataRole.UserRole) is None:
                aggregate = self._exportable_leaf_aggregate(item)
            else:
                aggregate = self._visible_children_aggregate(item)
            if aggregate is not None:
                item.setCheckState(0, aggregate)
            item = item.parent()

    def _refresh_group_header_check_states(self) -> None:
        """
        Recompute only top-level group-header tri-state from visible exportable
        leaves beneath each header. Never rewrites Sequence/Item parents.
        """
        root = self.tags_tree.invisibleRootItem()
        self.tags_tree.blockSignals(True)
        try:
            for group_item in iter_tree_children(root):
                if group_item.isHidden():
                    continue
                if group_item.data(0, Qt.ItemDataRole.UserRole) is not None:
                    continue
                aggregate = self._exportable_leaf_aggregate(group_item)
                if aggregate is None:
                    # Visible header whose exportable leaves are all hidden
                    # (e.g. filter matched only the group label).
                    group_item.setCheckState(0, Qt.CheckState.Unchecked)
                else:
                    group_item.setCheckState(0, aggregate)
        finally:
            self.tags_tree.blockSignals(False)
