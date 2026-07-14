"""
DICOM Tag Viewer Dialog

This module provides a separate window for viewing and searching DICOM tags
with full search functionality for both tags and values.

Inputs:
    - pydicom.Dataset objects
    - Search queries
    
Outputs:
    - Displayed and searchable DICOM tags
    - Separate resizable window
    
Requirements:
    - PySide6 for dialog components
    - DICOMParser for tag extraction
"""

from collections.abc import Callable
from typing import Any, Optional

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core.dicom_editor import DICOMEditor
from core.dicom_parser import DICOMParser
from core.tag_edit_history import TagEditHistoryManager
from gui.accent_presets import DEFAULT_ACCENT_ID, get_preset
from gui.dialogs.tag_edit_dialog import TagEditDialog
from gui.metadata_table_model import (
    filter_metadata_tags_by_search,
    group_metadata_tags_sorted,
    hide_nested_metadata_rows,
    index_metadata_tag_children,
    metadata_row_kind,
)
from gui.tag_edit_support import (
    apply_tag_edit,
    is_editable_metadata_item,
)
from utils.dicom_utils import is_patient_tag
from utils.undo_redo import UndoRedoManager


class TagViewerDialog(QDialog):
    """
    Separate dialog window for viewing and searching DICOM tags.
    
    Features:
    - Tree view of all DICOM tags
    - Search/filter by tag name or value
    - Show/hide private tags
    - Resizable window
    """

    # Signals
    tag_edited = Signal(str, object)  # (tag_string, new_value)

    def __init__(self, parent=None, undo_redo_manager: Optional['UndoRedoManager'] = None):
        """
        Initialize the tag viewer dialog.
        
        Args:
            parent: Parent widget
            undo_redo_manager: Optional UndoRedoManager for unified undo/redo
        """
        super().__init__(parent)

        self.setWindowTitle("DICOM Tag Viewer/Editor")
        self.setModal(False)  # Non-modal so it can stay open
        self.undo_redo_manager: UndoRedoManager | None = undo_redo_manager
        self.ui_refresh_callback: Callable[[], None] | None = None
        self.resize(800, 600)

        self.parser: DICOMParser | None = None
        self.dataset: Dataset | None = None
        self.show_private_tags = True
        self.show_sequences: bool = True
        self.privacy_mode: bool = False
        self.all_tag_items: list[QTreeWidgetItem] = []  # Store all items for filtering
        self.editor: DICOMEditor | None = None
        self.history_manager: TagEditHistoryManager | None = None

        # Undo/redo callbacks (for communicating with main window)
        self.undo_callback: Callable[[], None] | None = None
        self.redo_callback: Callable[[], None] | None = None
        self.can_undo_callback: Callable[[], bool] | None = None
        self.can_redo_callback: Callable[[], bool] | None = None

        # Caching for performance
        self._cached_tags: dict[str, Any] | None = None
        self._cached_search_text: str = ""
        self._cached_include_private: bool = True
        self._cached_privacy_mode: bool = False
        self._active_tag_edit_dialog: TagEditDialog | None = None
        self._active_tag_edit_tag: str | None = None

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

    def _edited_tag_row_colors(self) -> tuple[QColor, QColor]:
        """Return readable accent-tinted colors for edited DICOM tag rows."""
        accent_id = DEFAULT_ACCENT_ID
        parent = self.parent()
        config_manager = getattr(parent, "config_manager", None)
        if config_manager is not None and hasattr(config_manager, "get_accent"):
            accent_id = config_manager.get_accent()
        return QColor(get_preset(accent_id).accent_soft), QColor(0, 0, 0)

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
            self._populate_tags(search_text)

    def _redo_tag_edit(self) -> None:
        """Handle redo tag edit from context menu."""
        if self.redo_callback:
            self.redo_callback()
            # Refresh display
            search_text = self.search_edit.text()
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
        layout.setContentsMargins(10, 10, 10, 10)

        # Search group
        search_group = QGroupBox("Search")
        search_layout = QVBoxLayout()

        # Search input
        search_input_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search tags or values...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_input_layout.addWidget(search_label)
        search_input_layout.addWidget(self.search_edit)
        search_layout.addLayout(search_input_layout)

        # Show private tags checkbox
        self.private_tags_checkbox = QCheckBox("Show Private Tags")
        self.private_tags_checkbox.setChecked(True)
        self.private_tags_checkbox.toggled.connect(self._on_private_tags_toggled)
        search_layout.addWidget(self.private_tags_checkbox)

        # Show sequences checkbox (default on; unchecking hides sequence *contents*,
        # leaving each SQ parent as a one-line "N item(s)" summary)
        self.show_sequences_checkbox = QCheckBox("Show Sequences")
        self.show_sequences_checkbox.setChecked(True)
        self.show_sequences_checkbox.toggled.connect(self._on_show_sequences_toggled)
        search_layout.addWidget(self.show_sequences_checkbox)

        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        # Tree widget for tags
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Tag", "Name", "VR", "Value"])
        # Set initial column widths (can expand beyond these)
        self.tree_widget.setColumnWidth(0, 100)
        self.tree_widget.setColumnWidth(1, 200)
        self.tree_widget.setColumnWidth(2, 50)
        self.tree_widget.setColumnWidth(3, 300)
        # Enable horizontal scrolling to see full content
        self.tree_widget.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.tree_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Prevent text elision to show full content
        self.tree_widget.setTextElideMode(Qt.TextElideMode.ElideNone)
        # Don't stretch last section - allow columns to have natural width for horizontal scrolling
        self.tree_widget.header().setStretchLastSection(False)
        # Set section resize mode to allow manual resizing and natural content width
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.tree_widget.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.tree_widget.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tree_widget.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree_widget)

        # Add keyboard shortcut for copy (Ctrl+C)
        copy_shortcut = QShortcut(QKeySequence("Ctrl+C"), self)
        copy_shortcut.activated.connect(self._copy_selected_to_clipboard)

        # Add keyboard shortcuts for undo/redo (Cmd+Z / Ctrl+Z and Cmd+Shift+Z / Ctrl+Shift+Z)
        undo_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Undo), self)
        undo_shortcut.activated.connect(self._on_undo_requested)

        redo_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.Redo), self)
        redo_shortcut.activated.connect(self._on_redo_requested)

        # Buttons
        button_layout = QHBoxLayout()

        edit_button = QPushButton("Edit Selected Tag")
        edit_button.clicked.connect(self._edit_selected_tag)
        button_layout.addWidget(edit_button)

        expand_all_button = QPushButton("Expand All")
        expand_all_button.clicked.connect(self.tree_widget.expandAll)
        button_layout.addWidget(expand_all_button)

        collapse_all_button = QPushButton("Collapse All")
        collapse_all_button.clicked.connect(self.tree_widget.collapseAll)
        button_layout.addWidget(collapse_all_button)

        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def set_dataset(self, dataset: Dataset) -> None:
        """
        Set the DICOM dataset to display.
        
        Args:
            dataset: pydicom Dataset
        """
        self.dataset = dataset
        self.parser = DICOMParser(dataset)
        self.editor = DICOMEditor(dataset)
        # Clear cache when dataset changes
        self._cached_tags = None

        # Preserve current filter text from search_edit if it exists
        # This allows the filter to persist when switching between datasets/series
        current_search_text = self.search_edit.text()
        if current_search_text:
            self._cached_search_text = current_search_text
        else:
            self._cached_search_text = ""

        # Apply the preserved filter to the new dataset
        self._populate_tags(self._cached_search_text)

    def _populate_tags(self, search_text: str = "") -> None:
        """
        Populate the tree widget with DICOM tags.

        Args:
            search_text: Optional search text to filter tags
        """
        if self.parser is None:
            return

        # Check if tags need to be reloaded (dataset changed, private tags setting
        # changed, or privacy mode changed). The sequences toggle is NOT a reload
        # trigger: this view always parses sequence contents and hides the nested
        # rows for display, so toggling it never re-parses.
        need_reload = (self._cached_tags is None or
                      self.show_private_tags != self._cached_include_private or
                      self.privacy_mode != getattr(self, '_cached_privacy_mode', False))

        if need_reload:
            # Always parse with sequence contents on. Re-parsing without them when the checkbox
            # is off would scatter each sequence's leaves back into whatever tag
            # group their own number falls in (a Code Meaning from a de-identification
            # sequence landing under "Group 0008", keyed "(0008, 0104)#4"), detached
            # from the sequence that owns them. Hiding the nested rows instead keeps
            # the SQ parent visible as an "N item(s)" summary with nothing under it.
            tags = self.parser.get_all_tags(
                include_private=self.show_private_tags,
                privacy_mode=self.privacy_mode,
                include_sequences=True,
            )
            self._cached_tags = tags
            self._cached_include_private = self.show_private_tags
            self._cached_privacy_mode = self.privacy_mode
        else:
            # Use cached tags
            tags = self._cached_tags

        if tags is None:
            return

        # Collapse sequences down to their summary rows BEFORE searching, so a hidden
        # nested row can't pull its ancestors back into the tree as a search hit.
        if not self.show_sequences:
            tags = hide_nested_metadata_rows(tags)

        # Filter by search text if provided, retaining ancestor chains so a matching
        # nested row stays reachable under its sequence/item parents.
        tags = filter_metadata_tags_by_search(tags, search_text)

        # Update cached search text
        self._cached_search_text = search_text

        # With an active filter, every sequence parent present in the filtered set is
        # an ancestor of a match (or a match itself) — expand it rather than defaulting
        # to collapsed, so results are visible without a manual click.
        force_expand_sequences = bool(search_text)

        # Disable widget updates during population to prevent expensive repaints
        self.tree_widget.setUpdatesEnabled(False)
        try:
            # Clear tree widget
            self.tree_widget.clear()
            self.all_tag_items = []

            # Group depth-0 tags by tag group (first 4 hex digits); nested rows hang
            # off their sequence/item parent instead of getting their own group.
            grouped = group_metadata_tags_sorted(tags)

            # Index children by parent once; looking them up per parent instead is
            # O(n²) and takes ~19s on a 24k-row enhanced multi-frame study.
            children_by_parent = index_metadata_tag_children(tags)

            # Create tree items
            for group, tag_list in grouped:
                group_item = QTreeWidgetItem(self.tree_widget)
                group_item.setText(0, f"Group {group}")
                group_item.setExpanded(True)

                for tag_str, tag_data in tag_list:
                    self._build_tag_tree_item(
                        group_item,
                        tag_str,
                        tag_data,
                        children_by_parent,
                        force_expand_sequences,
                    )

            # Resize columns only on initial load (no search text)
            # Skip expensive column resizing during filtering/searching
            # Note: resizeColumnToContents allows columns to expand beyond viewport for horizontal scrolling
            if not search_text:
                self.tree_widget.resizeColumnToContents(0)
                self.tree_widget.resizeColumnToContents(1)
                self.tree_widget.resizeColumnToContents(2)
                # For the value column, resize to contents but ensure it can expand
                self.tree_widget.resizeColumnToContents(3)
        finally:
            # Always re-enable updates, even if an error occurred
            self.tree_widget.setUpdatesEnabled(True)

    def _build_tag_tree_item(
        self,
        parent_item: QTreeWidgetItem,
        tag_str: str,
        tag_data: dict[str, Any],
        children_by_parent: dict[str | None, list[tuple[str, dict[str, Any]]]],
        force_expand_sequences: bool,
    ) -> QTreeWidgetItem:
        """
        Create a ``QTreeWidgetItem`` for one row and recursively attach its children
        (via ``parent_key``), per the Phase 2 tree shape: SQ parents contain
        ``Item N`` nodes, which contain their own leaves/nested sequences.

        Args:
            parent_item: The group header or ancestor row this item nests under.
            tag_str: Row key (a path key, e.g. ``(0012, 0064)[0].(0008, 0104)``).
            tag_data: Row dict as returned by ``DICOMParser.get_all_tags``.
            children_by_parent: Child index from ``index_metadata_tag_children``.
            force_expand_sequences: When True (active filter), expand SQ parents
                instead of defaulting to collapsed.
        """
        tag_item = QTreeWidgetItem(parent_item)
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

        # Format value
        value = tag_data.get("value", "")
        if isinstance(value, list):
            value_str = ", ".join(str(v) for v in value)
        else:
            value_str = str(value)

        # Don't truncate in separate window - show full value
        tag_item.setText(3, value_str)

        # Set background color for edited tags
        if is_edited:
            edited_color, edited_text_color = self._edited_tag_row_colors()
            for col in range(4):
                tag_item.setBackground(col, edited_color)
                tag_item.setForeground(col, edited_text_color)

        tag_item.setData(0, Qt.ItemDataRole.UserRole, tag_str)
        tag_item.setData(0, Qt.ItemDataRole.UserRole + 1, tag_data)

        self.all_tag_items.append(tag_item)

        kind = metadata_row_kind(tag_data)
        if kind == "sequence":
            # Sequence parents default collapsed; expanded when they (or their
            # descendants) matched an active filter.
            tag_item.setExpanded(force_expand_sequences)
        elif kind == "item":
            # Item nodes default expanded so an expanded SQ parent's leaves are
            # visible without an extra click.
            tag_item.setExpanded(True)

        for child_key, child_data in children_by_parent.get(tag_str, []):
            self._build_tag_tree_item(
                tag_item,
                child_key,
                child_data,
                children_by_parent,
                force_expand_sequences,
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

    def _on_show_sequences_toggled(self, checked: bool) -> None:
        """
        Handle "Show Sequences" checkbox toggle.

        Shows or hides sequence *contents*. Unchecked, each SQ parent stays visible as
        a collapsed "N item(s)" summary row with no children; nothing from inside a
        sequence is shown anywhere. Purely a display filter over the same full
        parse — no re-parse, hence no cache clear.

        Args:
            checked: Checkbox state
        """
        self.show_sequences = checked
        if self.parser is not None:
            search_text = self.search_edit.text()
            self._populate_tags(search_text)

    def _is_editable_item(self, item: QTreeWidgetItem) -> bool:
        """
        Return True for scalar element rows at any depth.

        Group headers, SQ parent rows, and ``Item N`` nodes are read-only.
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

        # Skip group headers, SQ parents, and item nodes
        if not self._is_editable_item(item):
            return

        self._edit_tag_item(item)

    def _edit_selected_tag(self) -> None:
        """Edit the currently selected tag."""
        current_item = self.tree_widget.currentItem()
        if current_item is None:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select a tag to edit."
            )
            return

        # Skip group headers, SQ parents, and item nodes
        if not self._is_editable_item(current_item):
            QMessageBox.information(
                self,
                "Invalid Selection",
                "Please select an editable tag. Group headers, sequence parents, "
                "and item nodes are read-only."
            )
            return

        self._edit_tag_item(current_item)

    def _edit_tag_item(self, item: QTreeWidgetItem) -> None:
        """
        Edit a tag item.

        Args:
            item: Tree widget item to edit
        """
        tag_data = item.data(0, Qt.ItemDataRole.UserRole + 1)
        tag_str = item.data(0, Qt.ItemDataRole.UserRole)
        if tag_data is None or tag_str is None:
            return

        # Defensive: reject group headers, SQ parents, and item nodes
        # even if a caller (context menu) reaches this without checking first.
        if metadata_row_kind(tag_data) != "element":
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
                    # Refresh the tree view
                    search_text = self.search_edit.text()
                    # Clear parser cache so it re-reads from updated dataset
                    if self.parser is not None:
                        self.parser._tag_cache.clear()
                    self._cached_tags = None
                    self._populate_tags(search_text)
        finally:
            if self._active_tag_edit_dialog is dialog:
                self._active_tag_edit_dialog = None
                self._active_tag_edit_tag = None

    def _show_context_menu(self, position) -> None:
        """
        Show context menu for tag items with copy options.
        
        Args:
            position: Position where context menu was requested
        """
        item = self.tree_widget.itemAt(position)
        if item is None or item.parent() is None:
            return  # Skip group items

        # Determine which column was clicked
        column = self.tree_widget.columnAt(position.x())
        if column < 0:
            # Fallback: use current column if available
            column = self.tree_widget.currentColumn()
            if column < 0:
                column = 0  # Default to first column

        menu = QMenu(self)

        # Edit action
        edit_action = QAction("Edit Tag", self)
        tag_str = item.data(0, Qt.ItemDataRole.UserRole)
        edit_action.setEnabled(
            self._is_editable_item(item) and not self._is_edit_blocked_by_privacy(tag_str or "")
        )
        edit_action.triggered.connect(lambda: self._edit_tag_item(item))
        menu.addAction(edit_action)

        menu.addSeparator()

        # Undo action
        undo_action = QAction("Undo", self)
        can_undo = self.can_undo_callback() if self.can_undo_callback else False
        undo_action.setEnabled(can_undo)
        undo_action.triggered.connect(self._undo_tag_edit)
        menu.addAction(undo_action)

        # Redo action
        redo_action = QAction("Redo", self)
        can_redo = self.can_redo_callback() if self.can_redo_callback else False
        redo_action.setEnabled(can_redo)
        redo_action.triggered.connect(self._redo_tag_edit)
        menu.addAction(redo_action)

        menu.addSeparator()

        # Copy actions
        copy_tag_action = QAction("Copy Tag", self)
        copy_tag_action.triggered.connect(lambda: self._copy_to_clipboard(item, 0))
        menu.addAction(copy_tag_action)

        copy_name_action = QAction("Copy Name", self)
        copy_name_action.triggered.connect(lambda: self._copy_to_clipboard(item, 1))
        menu.addAction(copy_name_action)

        copy_vr_action = QAction("Copy VR", self)
        copy_vr_action.triggered.connect(lambda: self._copy_to_clipboard(item, 2))
        menu.addAction(copy_vr_action)

        copy_value_action = QAction("Copy Value", self)
        copy_value_action.triggered.connect(lambda: self._copy_to_clipboard(item, 3))
        menu.addAction(copy_value_action)

        menu.addSeparator()

        copy_all_action = QAction("Copy All", self)
        copy_all_action.triggered.connect(lambda: self._copy_all_to_clipboard(item))
        menu.addAction(copy_all_action)

        menu.exec(self.tree_widget.mapToGlobal(position))

    def _copy_to_clipboard(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Copy a specific column's text to clipboard.
        
        Args:
            item: Tree widget item
            column: Column index to copy (0=Tag, 1=Name, 2=VR, 3=Value)
        """
        if item is None:
            return

        text = item.text(column)
        clipboard = QApplication.clipboard()
        clipboard.setText(text)

    def _copy_all_to_clipboard(self, item: QTreeWidgetItem) -> None:
        """
        Copy all fields from a row to clipboard (tab-separated).
        
        Args:
            item: Tree widget item
        """
        if item is None:
            return

        # Get all column texts
        tag_text = item.text(0)
        name_text = item.text(1)
        vr_text = item.text(2)
        value_text = item.text(3)

        # Combine with tab separator
        all_text = f"{tag_text}\t{name_text}\t{vr_text}\t{value_text}"

        clipboard = QApplication.clipboard()
        clipboard.setText(all_text)

    def _copy_selected_to_clipboard(self) -> None:
        """
        Copy selected item to clipboard using keyboard shortcut.
        Copies the current column if available, otherwise copies all fields.
        """
        current_item = self.tree_widget.currentItem()
        if current_item is None or current_item.parent() is None:
            return  # Skip if no selection or group item

        # Get current column
        current_column = self.tree_widget.currentColumn()
        if current_column >= 0:
            # Copy the current column
            self._copy_to_clipboard(current_item, current_column)
        else:
            # Otherwise, copy all fields
            self._copy_all_to_clipboard(current_item)

    def _on_undo_requested(self) -> None:
        """Handle undo request via keyboard shortcut."""
        if self.undo_callback:
            self.undo_callback()

    def _on_redo_requested(self) -> None:
        """Handle redo request via keyboard shortcut."""
        if self.redo_callback:
            self.redo_callback()

    def clear_filter(self) -> None:
        """
        Clear the search filter and repopulate tags without filter.
        This is called when files are closed or new files are opened.
        """
        self._cached_search_text = ""
        self.search_edit.clear()
        if self.parser is not None:
            self._populate_tags("")
