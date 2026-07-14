"""
DICOM Metadata Panel

This module provides a panel for displaying and editing DICOM tags,
including private tags.

Inputs:
    - pydicom.Dataset objects
    - User edits to tag values
    
Outputs:
    - Displayed DICOM tags
    - Updated tag values
    
Requirements:
    - PySide6 for GUI components
    - DICOMParser for tag extraction

Tag filter/group helpers: ``gui.metadata_table_model``.
"""

from collections.abc import Callable
from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.dicom_editor import DICOMEditor
from core.dicom_parser import DICOMParser
from core.tag_edit_history import TagEditHistoryManager
from gui.dialogs.tag_edit_dialog import TagEditDialog
from gui.metadata_table_model import (
    GROUP_HEADER_KEY_ROLE,
    GroupHeaderDelegate,
    filter_metadata_tags_by_search,
    format_metadata_value_for_tree,
    group_metadata_tags_sorted,
    index_metadata_tag_children,
    metadata_row_kind,
)
from gui.tag_edit_support import (
    apply_tag_edit,
    is_editable_metadata_item,
)
from utils.config_manager import ConfigManager
from utils.dicom_utils import is_patient_tag
from utils.undo_redo import UndoRedoManager


class MetadataPanel(QWidget):
    """
    Panel for displaying and editing DICOM metadata.
    
    Features:
    - Tree view of all DICOM tags
    - Edit tag values
    - Show/hide private tags
    - Search/filter tags
    """

    # Signals
    tag_edited = Signal(str, object)  # (tag_string, new_value)

    def __init__(self, parent=None, config_manager: ConfigManager | None = None,
                 undo_redo_manager: UndoRedoManager | None = None):
        """
        Initialize the metadata panel.
        
        Args:
            parent: Parent widget
            config_manager: Optional ConfigManager instance for saving/loading column widths
            undo_redo_manager: Optional UndoRedoManager for unified undo/redo
        """
        super().__init__(parent)
        self.setObjectName("metadata_panel")

        self.parser: DICOMParser | None = None
        self.dataset: Dataset | None = None
        self.show_private_tags = True
        self.privacy_mode: bool = False
        self.editor: DICOMEditor | None = None
        self.history_manager: TagEditHistoryManager | None = None
        self.config_manager: ConfigManager | None = config_manager
        self.undo_redo_manager: UndoRedoManager | None = undo_redo_manager
        self.ui_refresh_callback: Callable[[], None] | None = None

        # Undo/redo callbacks
        self.undo_callback: Callable[[], None] | None = None
        self.redo_callback: Callable[[], None] | None = None
        self.can_undo_callback: Callable[[], bool] | None = None
        self.can_redo_callback: Callable[[], bool] | None = None

        # Caching for performance
        self._cached_tags: dict[str, Any] | None = None
        self._cached_search_text: str = ""
        self._cached_include_private: bool = True
        self._active_tag_edit_dialog: TagEditDialog | None = None
        self._active_tag_edit_tag: str | None = None

        # Per-group expand/collapse memory, keyed by the group's raw bucket key (e.g.
        # "(0008"). Restored from config on launch and written back on every toggle, so
        # it survives image/series switches AND app restarts.
        #
        # Sequence rows are deliberately NOT part of this and are never remembered: they
        # always reopen collapsed. A group is a handful of rows; a sequence can be tens
        # of thousands (per-frame functional groups), and restoring into that would make
        # opening a study feel broken.
        self._group_expanded: dict[str, bool] = (
            config_manager.get_metadata_panel_group_expanded()
            if config_manager is not None
            else {}
        )
        # Set while Expand/Collapse All is running, so its per-row signals don't each
        # trigger a config write; the batch is persisted once at the end.
        self._suspend_group_persist: bool = False

        # Search debouncing timer
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)

        self._create_ui()

        # Connect timer after UI is created
        self._search_timer.timeout.connect(lambda: self._populate_tags(self.search_edit.text()))

    def set_history_manager(self, history_manager: TagEditHistoryManager) -> None:
        """
        Set the tag edit history manager.
        
        Args:
            history_manager: TagEditHistoryManager instance
        """
        self.history_manager = history_manager

    def set_undo_redo_callbacks(
        self,
        undo_cb: Callable[[], None],
        redo_cb: Callable[[], None],
        can_undo_cb: Callable[[], bool],
        can_redo_cb: Callable[[], bool],
    ) -> None:
        """
        Set callbacks for undo/redo operations.
        
        Args:
            undo_cb: Callback to execute undo
            redo_cb: Callback to execute redo
            can_undo_cb: Callback to check if undo is available
            can_redo_cb: Callback to check if redo is available
        """
        self.undo_callback = undo_cb
        self.redo_callback = redo_cb
        self.can_undo_callback = can_undo_cb
        self.can_redo_callback = can_redo_cb

    def _undo_tag_edit(self) -> None:
        """Handle undo tag edit from context menu."""
        if self.undo_callback:
            self.undo_callback()
            # Refresh display
            search_text = self.search_edit.text()
            self._cached_tags = None
            # Clear parser cache so it re-reads from updated dataset
            if self.parser is not None:
                self.parser._tag_cache.clear()
            self._populate_tags(search_text)

    def _redo_tag_edit(self) -> None:
        """Handle redo tag edit from context menu."""
        if self.redo_callback:
            self.redo_callback()
            # Refresh display
            search_text = self.search_edit.text()
            self._cached_tags = None
            # Clear parser cache so it re-reads from updated dataset
            if self.parser is not None:
                self.parser._tag_cache.clear()
            self._populate_tags(search_text)

    def set_privacy_mode(self, enabled: bool) -> None:
        """
        Set privacy mode for masking patient tags.
        
        Args:
            enabled: True to enable privacy mode, False to disable
        """
        self.privacy_mode = enabled
        if enabled and self.close_active_tag_edit_dialog_due_to_privacy():
            QMessageBox.information(
                self,
                "Privacy Mode Enabled",
                "Patient tag editing was closed because Privacy Mode is enabled.",
            )
        # Clear cache to force refresh
        self._cached_tags = None
        # Refresh display if parser is available
        if self.parser is not None:
            search_text = self.search_edit.text()
            self._populate_tags(search_text)

    def close_active_tag_edit_dialog_due_to_privacy(self) -> bool:
        """
        Close the active tag-edit dialog when privacy mode is enabled.

        Returns:
            True if a patient-tag edit dialog was active and closed; False otherwise.
        """
        if self._active_tag_edit_dialog is None:
            return False
        if not self._active_tag_edit_dialog.isVisible():
            return False
        if not is_patient_tag(self._active_tag_edit_tag or ""):
            return False

        self._active_tag_edit_dialog.reject()
        self._active_tag_edit_dialog = None
        self._active_tag_edit_tag = None
        return True

    def _is_edit_blocked_by_privacy(self, tag_str: str) -> bool:
        """Return True when patient-tag editing must be blocked in privacy mode."""
        return self.privacy_mode and is_patient_tag(tag_str)

    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 3, 4)

        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("DICOM Tags")
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        # Show private tags checkbox
        self.private_tags_checkbox = QCheckBox("Show Private Tags")
        self.private_tags_checkbox.setChecked(True)
        self.private_tags_checkbox.toggled.connect(self._on_private_tags_toggled)
        header_layout.addWidget(self.private_tags_checkbox)

        layout.addLayout(header_layout)

        # Search input field
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter tags...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit)

        # Expand All / Collapse All buttons for group + sequence collapse control
        expand_collapse_layout = QHBoxLayout()
        self.expand_all_button = QPushButton("Expand All")
        self.expand_all_button.clicked.connect(self._on_expand_all_clicked)
        expand_collapse_layout.addWidget(self.expand_all_button)

        self.collapse_all_button = QPushButton("Collapse All")
        self.collapse_all_button.clicked.connect(self._on_collapse_all_clicked)
        expand_collapse_layout.addWidget(self.collapse_all_button)
        layout.addLayout(expand_collapse_layout)

        # Tree widget for tags
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Tag", "Name", "VR", "Value"])
        # Root decorations ON: this is what draws the expand/collapse triangle on group
        # headings and on sequence rows. It used to be off, and a custom delegate then
        # pulled tag rows back to x=0 — which painted their text straight over the branch
        # column, so an expandable row's triangle was drawn and then covered up. Nothing
        # in the panel looked expandable, and the only way in was a double-click nobody
        # could guess at.
        self.tree_widget.setRootIsDecorated(True)
        # A narrow indent: enough to separate a tag row from its group heading and to
        # show sequence nesting, without spending much of the Tag column on whitespace.
        self.tree_widget.setIndentation(7)
        # Headings toggle on a single click anywhere on the row (see
        # _on_tree_item_clicked), so Qt's own double-click-to-expand would fire a second
        # toggle and cancel it out.
        self.tree_widget.setExpandsOnDoubleClick(False)

        # Keeps a heading's band from being washed out by hover/selection.
        self.tree_widget.setItemDelegate(GroupHeaderDelegate(self.tree_widget))

        # Banded rows make a long, dense tag list far easier to track across
        # columns (matches the tag viewer dialog).
        self.tree_widget.setAlternatingRowColors(True)

        # Restore saved column widths or use defaults
        if self.config_manager is not None:
            saved_widths = self.config_manager.get_metadata_panel_column_widths()
            if len(saved_widths) == 4:
                self.tree_widget.setColumnWidth(0, saved_widths[0])
                self.tree_widget.setColumnWidth(1, saved_widths[1])
                self.tree_widget.setColumnWidth(2, saved_widths[2])
                self.tree_widget.setColumnWidth(3, saved_widths[3])
            else:
                # Use defaults if saved widths are invalid
                self.tree_widget.setColumnWidth(0, 100)
                self.tree_widget.setColumnWidth(1, 200)
                self.tree_widget.setColumnWidth(2, 50)
                self.tree_widget.setColumnWidth(3, 200)
        else:
            # Use defaults if no config manager
            self.tree_widget.setColumnWidth(0, 100)
            self.tree_widget.setColumnWidth(1, 200)
            self.tree_widget.setColumnWidth(2, 50)
            self.tree_widget.setColumnWidth(3, 200)

        # Connect to header signals
        header = self.tree_widget.header()
        header.sectionResized.connect(self._on_column_resized)

        # Enable column reordering
        header.setSectionsMovable(True)
        header.sectionMoved.connect(self._on_column_moved)

        # Restore saved column order if available
        if self.config_manager is not None:
            saved_order = self.config_manager.get_metadata_panel_column_order()
            if len(saved_order) == 4 and set(saved_order) == {0, 1, 2, 3}:
                # Restore column order by moving sections to their saved visual positions
                # Move from right to left (highest visual index to lowest) to avoid index shifting
                for visual_pos in range(3, -1, -1):  # 3, 2, 1, 0
                    logical_idx = saved_order[visual_pos]
                    current_visual = header.visualIndex(logical_idx)
                    if current_visual != visual_pos:
                        header.moveSection(current_visual, visual_pos)

        # Enable context menu for collapse/expand
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)

        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree_widget.itemClicked.connect(self._on_tree_item_clicked)

        # Remember per-group expand/collapse state across image/series switches
        # (session-scoped only — never written to ConfigManager). Rebuilding the
        # tree in _populate_tags blocks these signals so programmatic setExpanded
        # calls there don't pollute the remembered state; only real user actions
        # (manual toggle, Expand All/Collapse All, context menu) reach here.
        self.tree_widget.itemExpanded.connect(self._on_tree_item_expanded)
        self.tree_widget.itemCollapsed.connect(self._on_tree_item_collapsed)

        layout.addWidget(self.tree_widget)

    def set_dataset(self, dataset: Dataset | None, clear_filter: bool = False) -> None:
        """
        Set the DICOM dataset to display.
        
        Args:
            dataset: pydicom Dataset or None to clear
            clear_filter: If True, clear the search filter. If False, preserve current filter.
                         Always clears filter if dataset is None.
        """
        self.dataset = dataset

        if dataset is None:
            # Clear everything when dataset is None
            self.parser = None
            self.editor = None
            self._cached_tags = None
            self._cached_search_text = ""
            self.search_edit.clear()
            self.tree_widget.clear()
            return

        self.parser = DICOMParser(dataset)
        self.editor = DICOMEditor(dataset)
        # Clear cache when dataset changes
        self._cached_tags = None

        # Handle filter clearing
        if clear_filter:
            self._cached_search_text = ""
            self.search_edit.clear()
            current_search_text = ""
        else:
            # Preserve current search filter text so it persists when switching subwindows or resetting view
            current_search_text = self.search_edit.text()
            self._cached_search_text = current_search_text

        # Apply the filter to the new dataset
        self._populate_tags(current_search_text)

    def clear_filter(self) -> None:
        """
        Clear the search filter and repopulate tags without filter.
        """
        self._cached_search_text = ""
        self.search_edit.clear()
        if self.parser is not None:
            self._populate_tags("")

    def _populate_tags(self, search_text: str = "") -> None:
        """
        Populate the tree widget with DICOM tags.

        Sequence contents are always included here — there is no "Show
        Sequences" checkbox in this panel; the noise-management affordance is
        group/sequence collapse. Nested rows
        (sequence items and their contents) hang off their sequence parent,
        matching the Phase 2 tree shape; only depth-0 tags get their own group
        bucket (``group_metadata_tags_sorted``).

        Args:
            search_text: Optional search text to filter tags
        """
        if self.parser is None:
            return

        # Check if tags need to be reloaded (dataset changed or private tags setting changed)
        need_reload = (self._cached_tags is None or
                      self.show_private_tags != self._cached_include_private)

        if need_reload:
            # Reload tags from parser (will use parser's cache)
            tags = self.parser.get_all_tags(
                include_private=self.show_private_tags,
                privacy_mode=self.privacy_mode,
                include_sequences=True,
            )
            self._cached_tags = tags
            self._cached_include_private = self.show_private_tags
        else:
            # Use cached tags
            tags = self._cached_tags

        if tags is None:
            return

        if search_text:
            # Retains ancestor chains, so a matching nested row stays reachable
            # under its sequence/item parents; groups/sequences with no match
            # (and no matching descendant) simply have no rows left to bucket,
            # which is what keeps them out of the tree below.
            tags = filter_metadata_tags_by_search(tags, search_text)

        # Update cached search text
        self._cached_search_text = search_text

        # With an active filter, every group/sequence still present has a match
        # (or is an ancestor of one) — force it open so results aren't hidden
        # behind a collapsed group or sequence parent. Clearing the filter falls
        # back to the remembered per-group state; sequence parents always
        # collapse back to their default regardless of the filter.
        is_filtering = bool(search_text)

        # Disable widget updates/signals during population to prevent expensive
        # repaints and to keep programmatic setExpanded() calls below from being
        # recorded as user actions in ``self._group_expanded``.
        self.tree_widget.setUpdatesEnabled(False)
        self.tree_widget.blockSignals(True)
        try:
            self.tree_widget.clear()

            # Only root-level (depth-0) tags get their own group bucket; nested
            # rows hang off their sequence/item parent instead.
            grouped = group_metadata_tags_sorted(tags)

            # Index children by parent_key once; resolving each parent's children
            # by rescanning the tag dict is O(n^2) and cost ~19s on a 24k-row
            # enhanced multi-frame study (see the plan's PERF FINDING).
            children_by_parent = index_metadata_tag_children(tags)

            # Create tree items
            # Group headings will be top-level children of invisible root (indented)
            # Tags will be children of group items (enabling collapse) but rendered fully left-aligned via delegate
            root_item = self.tree_widget.invisibleRootItem()

            # Create bold font for group headings
            bold_font = QFont()
            bold_font.setBold(True)

            header_bg, header_fg = self._group_header_colors()

            for group, tag_list in grouped:
                # Group header as child of root (will be indented by tree widget indentation)
                group_item = QTreeWidgetItem(root_item)
                group_label = group[1:5] if len(group) >= 5 else group
                group_item.setText(0, f"Group {group_label} — {len(tag_list)} tags")
                # Enable expansion/collapse for group items - need both ItemIsEnabled and ItemIsSelectable
                group_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                group_item.setFont(0, bold_font)  # Make group heading bold
                # Let the heading run the full width of the tree instead of being
                # clipped to the narrow Tag column ("Group 0002 — 7 t...").
                group_item.setFirstColumnSpanned(True)
                # Tinted band so a heading reads as a section divider, not as one more
                # tag row. Spanning means column 0's brush fills the whole row.
                group_item.setBackground(0, header_bg)
                group_item.setForeground(0, header_fg)
                group_item.setToolTip(0, "Click to expand or collapse this group")
                # Raw bucket key, used to key session-scoped expand/collapse memory.
                group_item.setData(0, GROUP_HEADER_KEY_ROLE, group)

                # Add tag items (and their nested descendants) as children
                for tag_str, tag_data in tag_list:
                    self._build_tag_tree_item(
                        group_item, tag_str, tag_data, children_by_parent, is_filtering
                    )

                # Set indicator policy and expanded state after children are added
                # This ensures the expand/collapse indicator (triangle arrow) is visible
                group_item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
                # Groups start collapsed on a fresh session; remembered per-group
                # state persists across image/series switches within the session
                # but is never written to ConfigManager (all-collapsed again on
                # the next app launch). An active filter forces the group open.
                group_item.setExpanded(is_filtering or self._group_expanded.get(group, False))
        finally:
            # Always re-enable updates/signals, even if an error occurred
            self.tree_widget.blockSignals(False)
            self.tree_widget.setUpdatesEnabled(True)

        # Note: Column widths are preserved from saved configuration
        # Removed resizeColumnToContents calls to maintain user's preferred column widths

    def changeEvent(self, event) -> None:
        """Recolor headings when the theme flips under a live panel.

        Heading colors are resolved once, when the tree is built. Without this, toggling
        the theme would leave the old band and old text color in place until something
        happened to repopulate — i.e. light text stranded on a light band, the very state
        this pair of colors exists to prevent.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.PaletteChange:
            self._apply_group_header_colors()

    def _apply_group_header_colors(self) -> None:
        """Push the current theme's heading colors onto every existing heading row."""
        background, foreground = self._group_header_colors()
        root = self.tree_widget.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if self._is_group_header(item):
                item.setBackground(0, background)
                item.setForeground(0, foreground)

    def _group_header_colors(self) -> tuple[QColor, QColor]:
        """
        Return (background, foreground) for a group heading row.

        The heading takes the tree's own background (Base) — no fill of its own. Every
        colored band tried here (grey, burgundy, the theme's black/white extreme) read as
        an odd block floating on the pane. What separates a heading now is the rule drawn
        above and below it by ``GroupHeaderDelegate``, which also keeps consecutive
        *collapsed* headings visually distinct, something a fill alone did poorly.

        Base is set explicitly rather than left unset so a heading never picks up the
        accent-tinted alternating-row color.

        Foreground is Text, so a heading always agrees with the tag rows beneath it. Both
        come from the palette, which is where the app's QSS theme resolves to.
        """
        palette = self.tree_widget.palette()
        return (
            palette.color(QPalette.ColorRole.Base),
            palette.color(QPalette.ColorRole.Text),
        )

    def _build_tag_tree_item(
        self,
        parent_item: QTreeWidgetItem,
        tag_str: str,
        tag_data: dict[str, Any],
        children_by_parent: dict[str | None, list[tuple[str, dict[str, Any]]]],
        force_expand_sequences: bool,
    ) -> QTreeWidgetItem:
        """
        Create a ``QTreeWidgetItem`` for one row and recursively attach its
        children (via ``parent_key``), matching the Phase 2 tree shape
        (``tag_viewer_dialog._build_tag_tree_item``): SQ parents hold ``Item N``
        nodes, which hold their own leaves/nested sequences.

        Args:
            parent_item: The group header or ancestor row this item nests under.
            tag_str: Row key (a path key, e.g. ``(0012, 0064)[0].(0008, 0104)``).
            tag_data: Row dict as returned by ``DICOMParser.get_all_tags``.
            children_by_parent: Child index from ``index_metadata_tag_children``
                (built ONCE per populate call — never re-index per parent, that
                is the O(n^2) trap this helper exists to avoid).
            force_expand_sequences: When True (active filter), expand SQ parents
                instead of defaulting to collapsed.
        """
        tag_item = QTreeWidgetItem(parent_item)
        # Use the map key (a path) so two leaves sharing a tag number under
        # different sequences stay distinguishable in the Tag column.
        tag_item.setText(0, tag_str)

        # Check if tag is edited
        tag_name = tag_data.get("name", "")
        is_edited = False
        if self.history_manager and self.dataset:
            is_edited = self.history_manager.is_tag_edited(self.dataset, tag_str)

        # Add asterisk to name if edited
        if is_edited:
            tag_name = tag_name + "*"

        tag_item.setText(1, tag_name)
        tag_item.setText(2, tag_data.get("VR", ""))

        # Set left alignment for tag column
        tag_item.setTextAlignment(0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        value_str = format_metadata_value_for_tree(tag_data.get("value", ""))
        tag_item.setText(3, value_str)

        # Set background color for edited tags
        if is_edited:
            # Use dark purple background (works well with white text in dark mode)
            edited_color = QColor(80, 50, 120)  # Dark purple
            for col in range(4):
                tag_item.setBackground(col, edited_color)

        tag_item.setData(0, Qt.ItemDataRole.UserRole, tag_str)
        tag_item.setData(0, Qt.ItemDataRole.UserRole + 1, tag_data)

        children = children_by_parent.get(tag_str, [])
        if children:
            tag_item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)

        kind = metadata_row_kind(tag_data)
        if kind == "sequence":
            # Sequence parents always start collapsed and are never remembered
            # across populate calls — only an active filter match forces one open.
            tag_item.setExpanded(force_expand_sequences)
        elif kind == "item":
            # Item nodes default expanded so an expanded SQ parent's leaves are
            # visible without an extra click.
            tag_item.setExpanded(True)

        for child_key, child_data in children:
            self._build_tag_tree_item(
                tag_item, child_key, child_data, children_by_parent, force_expand_sequences
            )

        return tag_item

    def _on_search_changed(self, text: str) -> None:
        """
        Handle search text change with debouncing.
        
        Args:
            text: Search text
        """
        # Stop timer if running and restart with delay
        self._search_timer.stop()
        self._search_timer.start(300)  # 300ms delay after user stops typing

    def _on_private_tags_toggled(self, checked: bool) -> None:
        """
        Handle private tags checkbox toggle.
        
        Args:
            checked: Checkbox state
        """
        self.show_private_tags = checked
        # Clear cache when private tags setting changes
        self._cached_tags = None
        if self.parser is not None:
            search_text = self.search_edit.text()
            self._populate_tags(search_text)

    def _on_expand_all_clicked(self) -> None:
        """Expand every group and sequence parent currently in the tree."""
        self._set_all_expanded(True)

    def _on_collapse_all_clicked(self) -> None:
        """Collapse every group and sequence parent currently in the tree."""
        self._set_all_expanded(False)

    def _set_all_expanded(self, expanded: bool) -> None:
        """
        Expand/collapse everything, writing the group state to config exactly once.

        expandAll()/collapseAll() emit itemExpanded/itemCollapsed per row, and persisting
        on each would rewrite the config file once per group — on a big study that is a
        burst of disk writes for a single click.
        """
        self._suspend_group_persist = True
        try:
            if expanded:
                self.tree_widget.expandAll()
            else:
                self.tree_widget.collapseAll()
        finally:
            self._suspend_group_persist = False
        self._persist_group_expansion()

    def _is_group_header(self, item: QTreeWidgetItem) -> bool:
        """True for a group heading row (the only rows carrying the bucket-key marker)."""
        return item.data(0, GROUP_HEADER_KEY_ROLE) is not None

    def _on_tree_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """
        Toggle a group heading on a single click anywhere along the row.

        The disclosure triangle is the discoverable affordance; this makes the whole
        heading a click target so the user doesn't have to hit it. Clicking the triangle
        itself is handled by the tree (the branch area is outside the item rect, so it
        does not reach this slot) and so cannot double-toggle.
        """
        if self._is_group_header(item):
            item.setExpanded(not item.isExpanded())

    def _on_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        """Remember a group's expanded state for this session (see ``_group_expanded``)."""
        self._remember_group_expansion(item, True)

    def _on_tree_item_collapsed(self, item: QTreeWidgetItem) -> None:
        """Remember a group's collapsed state for this session (see ``_group_expanded``)."""
        self._remember_group_expansion(item, False)

    def _remember_group_expansion(self, item: QTreeWidgetItem, expanded: bool) -> None:
        """
        Record *expanded* for a group heading and persist it.

        Only group headings carry the GROUP_HEADER_KEY_ROLE marker, so this is a no-op
        for sequence parents / item nodes / leaf rows — their expansion is never
        remembered, by design (see ``_group_expanded``).
        """
        if not self._is_group_header(item):
            return
        self._group_expanded[item.data(0, GROUP_HEADER_KEY_ROLE)] = expanded
        if not self._suspend_group_persist:
            self._persist_group_expansion()

    def _persist_group_expansion(self) -> None:
        """Write the remembered group expansion to config (no-op without a config manager)."""
        if self.config_manager is not None:
            self.config_manager.set_metadata_panel_group_expanded(self._group_expanded)

    def _on_column_resized(self, logical_index: int, old_size: int, new_size: int) -> None:
        """
        Handle column resize event to save column widths.
        
        Args:
            logical_index: Index of the column that was resized
            old_size: Previous size of the column
            new_size: New size of the column
        """
        if self.config_manager is not None:
            # Get current column widths
            widths = [
                self.tree_widget.columnWidth(0),
                self.tree_widget.columnWidth(1),
                self.tree_widget.columnWidth(2),
                self.tree_widget.columnWidth(3)
            ]
            # Save to config
            self.config_manager.set_metadata_panel_column_widths(widths)

    def _on_column_moved(self, logical_index: int, old_visual_index: int, new_visual_index: int) -> None:
        """
        Handle column move event to save column order.
        
        Args:
            logical_index: Logical index of the column that was moved
            old_visual_index: Previous visual position
            new_visual_index: New visual position
        """
        if self.config_manager is not None:
            # Get current visual order of all columns
            header = self.tree_widget.header()
            # Build list of logical indices in visual order
            column_order = []
            for visual_pos in range(4):
                logical_idx = header.logicalIndex(visual_pos)
                column_order.append(logical_idx)
            # Save to config
            self.config_manager.set_metadata_panel_column_order(column_order)

    def _show_context_menu(self, position: QPoint) -> None:
        """
        Show context menu for tree widget items.
        
        Args:
            position: Position where context menu was requested (in tree widget coordinates)
        """
        item = self.tree_widget.itemAt(position)
        if item is None:
            return

        is_group_item = self._is_group_header(item)

        # Create context menu
        context_menu = QMenu(self)

        if is_group_item:
            # Group item - show Collapse/Expand option with double-click hint
            if item.childCount() > 0:
                if item.isExpanded():
                    collapse_action = context_menu.addAction("Collapse (click)")
                    collapse_action.triggered.connect(lambda: item.setExpanded(False))
                else:
                    expand_action = context_menu.addAction("Expand (click)")
                    expand_action.triggered.connect(lambda: item.setExpanded(True))
        else:
            # Tag item - show Edit, Undo, Redo, and Collapse/Expand options
            edit_action = context_menu.addAction("Edit Tag")
            # Group headers, SQ parents, and Item N nodes are read-only.
            edit_action.setEnabled(self._is_editable_item(item))
            edit_action.triggered.connect(lambda: self._on_item_double_clicked(item, 3))

            context_menu.addSeparator()

            # Undo action
            undo_action = QAction("Undo", self)
            can_undo = self.can_undo_callback() if self.can_undo_callback else False
            undo_action.setEnabled(can_undo)
            undo_action.triggered.connect(self._undo_tag_edit)
            context_menu.addAction(undo_action)

            # Redo action
            redo_action = QAction("Redo", self)
            can_redo = self.can_redo_callback() if self.can_redo_callback else False
            redo_action.setEnabled(can_redo)
            redo_action.triggered.connect(self._redo_tag_edit)
            context_menu.addAction(redo_action)

            context_menu.addSeparator()

            # Collapse/Expand for parent group if it has one
            parent = item.parent()
            if parent is not None and self._is_group_header(parent):
                if parent.childCount() > 0:
                    if parent.isExpanded():
                        collapse_action = context_menu.addAction("Collapse Group")
                        collapse_action.triggered.connect(lambda: parent.setExpanded(False))
                    else:
                        expand_action = context_menu.addAction("Expand Group")
                        expand_action.triggered.connect(lambda: parent.setExpanded(True))

        # Show context menu at cursor position
        if context_menu.actions():
            context_menu.exec(self.tree_widget.mapToGlobal(position))

    def _is_editable_item(self, item: QTreeWidgetItem) -> bool:
        """
        Return True for scalar element rows at any depth.

        Group headers, SQ parent rows, and ``Item N`` nodes are read-only.
        Mirrors ``TagViewerDialog._is_editable_item``.
        """
        return is_editable_metadata_item(item)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Handle double-click on tag item for editing.

        Args:
            item: Tree widget item
            column: Column clicked
        """
        if column != 3:  # Only edit value column
            return

        # Skip group headers, SQ parents, and Item N nodes.
        if not self._is_editable_item(item):
            return

        tag_data = item.data(0, Qt.ItemDataRole.UserRole + 1)
        tag_str = item.data(0, Qt.ItemDataRole.UserRole)
        if tag_data is None or tag_str is None:
            return

        if self._is_edit_blocked_by_privacy(tag_str):
            QMessageBox.information(
                self,
                "Privacy Mode Enabled",
                "Patient information tags cannot be edited while Privacy Mode is enabled.",
            )
            return

        if self.dataset is None or self.editor is None:
            return

        # Get tag information
        tag_name = tag_data.get("name", tag_str)
        vr = tag_data.get("VR", "")
        current_value = tag_data.get("value", "")

        # Open edit dialog
        dialog = TagEditDialog(
            self,
            tag_str=tag_str,
            tag_name=tag_name,
            vr=vr,
            current_value=current_value
        )
        self._active_tag_edit_dialog = dialog
        self._active_tag_edit_tag = tag_str
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_value = dialog.get_value()
                if new_value is not None:
                    success = apply_tag_edit(
                        dataset=self.dataset,
                        editor=self.editor,
                        tag_str=tag_str,
                        tag_data=tag_data,
                        old_value=current_value,
                        new_value=new_value,
                        vr=vr,
                        undo_redo_manager=self.undo_redo_manager,
                        history_manager=self.history_manager,
                        ui_refresh_callback=self.ui_refresh_callback,
                    )
                    if not success:
                        QMessageBox.warning(
                            self,
                            "Edit Failed",
                            f"Failed to update tag {tag_str}.\n"
                            "The tag may be read-only or the value may be invalid."
                        )
                        return

                    # Emit signal
                    self.tag_edited.emit(tag_str, new_value)
                    # Refresh the tree view (preserve search text)
                    search_text = self.search_edit.text()
                    # Clear cache since tag was edited
                    self._cached_tags = None
                    # Clear parser cache so it re-reads from updated dataset
                    if self.parser is not None:
                        self.parser._tag_cache.clear()
                    self._populate_tags(search_text)
        finally:
            if self._active_tag_edit_dialog is dialog:
                self._active_tag_edit_dialog = None
                self._active_tag_edit_tag = None
