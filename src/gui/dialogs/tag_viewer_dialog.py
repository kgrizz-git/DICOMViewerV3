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

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QTreeWidget, QTreeWidgetItem, QLineEdit,
                                QPushButton, QCheckBox, QGroupBox, QMessageBox,
                                QMenu, QAbstractItemView, QApplication, QHeaderView)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut, QColor
from typing import Optional, Dict, Any, Callable
import pydicom
from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser
from core.dicom_editor import DICOMEditor
from core.tag_edit_history import TagEditHistoryManager
from gui.dialogs.tag_edit_dialog import TagEditDialog
from utils.undo_redo import UndoRedoManager, TagEditCommand


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
        self.undo_redo_manager: Optional['UndoRedoManager'] = undo_redo_manager
        self.ui_refresh_callback: Optional[Callable] = None
        self.resize(800, 600)
        
        self.parser: Optional[DICOMParser] = None
        self.dataset: Optional[Dataset] = None
        self.show_private_tags = True
        self.privacy_mode: bool = False
        self.all_tag_items: list = []  # Store all items for filtering
        self.editor: Optional[DICOMEditor] = None
        self.history_manager: Optional[TagEditHistoryManager] = None
        
        # Undo/redo callbacks (for communicating with main window)
        self.undo_callback: Optional[Callable] = None
        self.redo_callback: Optional[Callable] = None
        self.can_undo_callback: Optional[Callable] = None
        self.can_redo_callback: Optional[Callable] = None
        
        # Caching for performance
        self._cached_tags: Optional[Dict[str, Any]] = None
        self._cached_search_text: str = ""
        self._cached_include_private: bool = True
        self._cached_privacy_mode: bool = False
        
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
    
    def set_undo_redo_callbacks(self, undo_cb: Callable, redo_cb: Callable,
                                can_undo_cb: Callable, can_redo_cb: Callable) -> None:
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
        # Clear cache to force refresh
        self._cached_tags = None
        # Refresh display if parser is available
        if self.parser is not None:
            search_text = self.search_edit.text()
            self._populate_tags(search_text)
    
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
        undo_shortcut = QShortcut(QKeySequence.Undo, self)
        undo_shortcut.activated.connect(self._on_undo_requested)
        
        redo_shortcut = QShortcut(QKeySequence.Redo, self)
        redo_shortcut.activated.connect(self._on_redo_requested)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        edit_button = QPushButton("Edit Selected Tag")
        edit_button.clicked.connect(self._edit_selected_tag)
        button_layout.addWidget(edit_button)
        
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
        
        # Check if tags need to be reloaded (dataset changed, private tags setting changed, or privacy mode changed)
        need_reload = (self._cached_tags is None or 
                      self.show_private_tags != self._cached_include_private or
                      self.privacy_mode != getattr(self, '_cached_privacy_mode', False))
        
        if need_reload:
            # Reload tags from parser (will use parser's cache)
            tags = self.parser.get_all_tags(include_private=self.show_private_tags, privacy_mode=self.privacy_mode)
            self._cached_tags = tags
            self._cached_include_private = self.show_private_tags
            self._cached_privacy_mode = self.privacy_mode
        else:
            # Use cached tags
            tags = self._cached_tags
        
        # Filter by search text if provided
        if search_text:
            search_lower = search_text.lower()
            filtered_tags = {}
            for tag_str, tag_data in tags.items():
                # Search in tag, name, keyword, or value
                tag_lower = tag_str.lower()
                name_lower = tag_data.get("name", "").lower()
                keyword_lower = tag_data.get("keyword", "").lower()
                value_str = str(tag_data.get("value", "")).lower()
                
                if (search_lower in tag_lower or 
                    search_lower in name_lower or 
                    search_lower in keyword_lower or
                    search_lower in value_str):
                    filtered_tags[tag_str] = tag_data
            tags = filtered_tags
        
        # Update cached search text
        self._cached_search_text = search_text
        
        # Disable widget updates during population to prevent expensive repaints
        self.tree_widget.setUpdatesEnabled(False)
        try:
            # Clear tree widget
            self.tree_widget.clear()
            self.all_tag_items = []
            
            # Sort tags by tag number
            sorted_tags = sorted(tags.items(), key=lambda x: x[0])
            
            # Group by tag group (first 4 hex digits)
            groups: Dict[str, list] = {}
            for tag_str, tag_data in sorted_tags:
                group = tag_str[:5]  # e.g., "(0008," for group 0008
                if group not in groups:
                    groups[group] = []
                groups[group].append((tag_str, tag_data))
            
            # Create tree items
            for group, tag_list in sorted(groups.items()):
                group_item = QTreeWidgetItem(self.tree_widget)
                group_item.setText(0, f"Group {group}")
                group_item.setExpanded(True)
                
                for tag_str, tag_data in tag_list:
                    tag_item = QTreeWidgetItem(group_item)
                    tag_item.setText(0, tag_data.get("tag", tag_str))
                    
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
                        # Use dark purple background (works well with white text in dark mode)
                        edited_color = QColor(80, 50, 120)  # Dark purple
                        for col in range(4):
                            tag_item.setBackground(col, edited_color)
                    
                    tag_item.setData(0, Qt.ItemDataRole.UserRole, tag_str)
                    tag_item.setData(0, Qt.ItemDataRole.UserRole + 1, tag_data)
                    
                    self.all_tag_items.append(tag_item)
            
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
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Handle double-click on tag item for editing.
        
        Args:
            item: Tree widget item
            column: Column clicked
        """
        if column != 3:  # Only edit value column
            return
        
        # Skip group items
        if item.parent() is None:
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
        
        # Skip group items
        if current_item.parent() is None:
            QMessageBox.information(
                self,
                "Invalid Selection",
                "Please select a tag item, not a group header."
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
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_value = dialog.get_value()
            if new_value is not None:
                # Get old value for undo/redo
                old_value = current_value
                
                # Create edit command - use unified undo/redo manager if available
                if self.undo_redo_manager and self.dataset:
                    # Convert tag_str to tag object
                    from pydicom.tag import Tag
                    tag_tuple = tuple(int(x, 16) for x in tag_str.strip("()").split(","))
                    tag = Tag(tag_tuple)
                    
                    command = TagEditCommand(
                        self.dataset,
                        tag,
                        old_value,
                        new_value,
                        vr,
                        tag_edit_history_manager=self.history_manager,
                        ui_refresh_callback=self.ui_refresh_callback
                    )
                    # Execute command through unified undo/redo manager
                    self.undo_redo_manager.execute_command(command)
                else:
                    # Fallback: update directly if no undo/redo manager
                    success = self.editor.update_tag(tag_str, new_value, vr)
                    if not success:
                        QMessageBox.warning(
                            self,
                            "Edit Failed",
                            f"Failed to update tag {tag_str}.\n"
                            "The tag may be read-only or the value may be invalid."
                        )
                        return
                    # Still mark as edited if we have history manager
                    if self.history_manager:
                        self.history_manager.mark_tag_edited(self.dataset, tag_str)
                
                # Emit signal
                self.tag_edited.emit(tag_str, new_value)
                # Refresh the tree view
                search_text = self.search_edit.text()
                # Clear parser cache so it re-reads from updated dataset
                if self.parser is not None:
                    self.parser._tag_cache.clear()
                self._cached_tags = None
                self._populate_tags(search_text)
    
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

