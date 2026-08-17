"""
Expand/collapse navigation for the DICOM tag export dialog (Phase C6).

Inputs:
    - Tag tree widget and filter field already constructed on the owning dialog

Outputs:
    - Expand All / Collapse All controls, context menu, dialog-scoped shortcuts,
      optional filter Clear when a filter hides every tag

Requirements:
    - PySide6 Qt widgets on the owning dialog
    - ``_is_filtering`` guard on the dialog for filter walks
"""
# Pyright: methods run only on ``TagExportDialog`` (combined Qt type); mixin bases
# cannot express cross-mixin ``self`` without a duplicate protocol surface.
# ``reportArgumentType`` / ``reportCallIssue`` are also off so ``self`` can be
# passed as a ``QWidget`` / ``QObject`` parent without a Protocol cast surface.
# pyright: reportAttributeAccessIssue=false, reportUninitializedInstanceVariable=false, reportArgumentType=false, reportCallIssue=false
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidgetItem,
)

# Dialog-scoped shortcuts (parent will document in DESIGN.md §6).
_EXPAND_ALL_SHORTCUT = QKeySequence("Ctrl+Shift+E")
_COLLAPSE_ALL_SHORTCUT = QKeySequence("Ctrl+Shift+C")


class TagExportDialogNavigationMixin:
    """
    Mixin for tag-tree expand/collapse navigation parity with the metadata panel.

    Expects the owning dialog to provide ``tags_tree``, ``tag_search``, and the
    Phase A ``_is_filtering`` flag. Uses ``_suspend_expand_signals`` so programmatic
    expand/collapse batches do not fire large-sequence warnings per row.
    """

    def _init_tag_export_navigation_state(self) -> None:
        """Initialize navigation flags (wire shortcuts after buttons exist)."""
        self._suspend_expand_signals = False

    def _add_tag_navigation_buttons(self, button_layout: QHBoxLayout) -> None:
        """Add Expand All / Collapse All beside the Select All row."""
        self.expand_all_button = QPushButton("Expand All", self)
        self.expand_all_button.clicked.connect(self._on_expand_all_clicked)
        button_layout.addWidget(self.expand_all_button)

        self.collapse_all_button = QPushButton("Collapse All", self)
        self.collapse_all_button.clicked.connect(self._on_collapse_all_clicked)
        button_layout.addWidget(self.collapse_all_button)

    def _add_tag_filter_clear_button(self, search_layout: QHBoxLayout) -> None:
        """Add a Clear control shown when the active filter hides every tag."""
        self.tag_filter_clear_button = QPushButton("Clear", self)
        self.tag_filter_clear_button.setToolTip("Clear the tag filter")
        self.tag_filter_clear_button.clicked.connect(self._clear_tag_filter)
        self.tag_filter_clear_button.setVisible(False)
        search_layout.addWidget(self.tag_filter_clear_button)

    def _wire_tag_tree_navigation(self) -> None:
        """Context menu, shortcuts, and dialog-scoped key bindings."""
        self.tags_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tags_tree.customContextMenuRequested.connect(self._show_tags_context_menu)

        expand_shortcut = QShortcut(_EXPAND_ALL_SHORTCUT, self)
        expand_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        expand_shortcut.activated.connect(self._on_expand_all_clicked)

        collapse_shortcut = QShortcut(_COLLAPSE_ALL_SHORTCUT, self)
        collapse_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        collapse_shortcut.activated.connect(self._on_collapse_all_clicked)

        # QAction shortcuts for tests and future menu/toolbar wiring.
        self._expand_all_action = QAction("Expand All", self)
        self._expand_all_action.setShortcut(_EXPAND_ALL_SHORTCUT)
        self.addAction(self._expand_all_action)
        self._expand_all_action.triggered.connect(self._on_expand_all_clicked)

        self._collapse_all_action = QAction("Collapse All", self)
        self._collapse_all_action.setShortcut(_COLLAPSE_ALL_SHORTCUT)
        self.addAction(self._collapse_all_action)
        self._collapse_all_action.triggered.connect(self._on_collapse_all_clicked)

    def _on_expand_all_clicked(self) -> None:
        """Expand every group and sequence parent currently in the tree."""
        self._set_all_tags_expanded(True)

    def _on_collapse_all_clicked(self) -> None:
        """Collapse every group and sequence parent currently in the tree."""
        self._set_all_tags_expanded(False)

    def _set_all_tags_expanded(self, expanded: bool) -> None:
        """
        Expand or collapse the full tag tree without per-row large-sequence warnings.

        ``expandAll()`` / ``collapseAll()`` emit ``itemExpanded`` / ``itemCollapsed``
        per row; ``_suspend_expand_signals`` makes those slots return early. Group-header
        tri-state is unchanged by expand/collapse, so no refresh is required here.
        """
        self._suspend_expand_signals = True
        try:
            if expanded:
                self.tags_tree.expandAll()
            else:
                self.tags_tree.collapseAll()
        finally:
            self._suspend_expand_signals = False

    def _clear_tag_filter(self) -> None:
        """Clear the tag filter and restore the full tag tree."""
        if self.tag_search.text():
            self.tag_search.clear()  # textChanged -> _filter_tags
        else:
            self._filter_tags("")  # direct filter calls leave the field empty
        self.tag_filter_clear_button.hide()

    def _update_tag_filter_clear_visibility(self, search_text: str) -> None:
        """Show Clear when a non-empty filter hides every tag row."""
        if not search_text:
            self.tag_filter_clear_button.setVisible(False)
            return
        root = self.tags_tree.invisibleRootItem()
        any_visible = False
        for i in range(root.childCount()):
            if not root.child(i).isHidden():
                any_visible = True
                break
        self.tag_filter_clear_button.setVisible(not any_visible)

    def _show_tags_context_menu(self, position: QPoint) -> None:
        """
        Context menu for the tag tree: Expand / Collapse for the row under the cursor.

        Only offered when that row has children. Does not include metadata edit/undo/redo.
        """
        item = self.tags_tree.itemAt(position)
        if item is None or item.childCount() == 0:
            return

        menu = QMenu(self)
        if item.isExpanded():
            collapse_action = menu.addAction("Collapse")
            collapse_action.triggered.connect(lambda: item.setExpanded(False))
        else:
            expand_action = menu.addAction("Expand")
            expand_action.triggered.connect(lambda: item.setExpanded(True))

        menu.exec(self.tags_tree.mapToGlobal(position))

    def _on_tag_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        """
        Warn when the user expands a sequence node flagged as large (plan's
        large-sequence warning). Eager population is already fast (Phase 2 perf
        finding), so this is a UX guard against browsing/over-selecting a huge
        subtree unintentionally, not a performance mitigation.

        During ``_filter_tags`` the walk expands ancestor rows programmatically
        (``_is_filtering`` is True); the slot returns early then so filtering
        never pops the warning. Structural state is recomputed once at the end
        of the filter walk instead of per-row. Expand All uses
        ``_suspend_expand_signals`` for the same batching behavior.
        """
        if self._is_filtering or self._suspend_expand_signals:
            return
        leaf_count = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not isinstance(leaf_count, int):
            return
        tag_str = item.data(0, Qt.ItemDataRole.UserRole)
        QMessageBox.warning(
            self,
            "Large Sequence",
            f"{tag_str} contains {leaf_count:,} nested tags across its items.\n\n"
            "Expanding and selecting individual leaves may be slow to browse. "
            "Use the filter box to narrow down, or check the sequence row itself "
            "to export a single summary column instead.",
        )
