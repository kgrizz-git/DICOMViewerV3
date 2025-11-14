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
                                QMenu)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction
from typing import Optional, Dict, Any
import pydicom
from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser
from core.dicom_editor import DICOMEditor
from core.tag_edit_history import TagEditHistoryManager, EditTagCommand
from gui.dialogs.tag_edit_dialog import TagEditDialog


class TagViewerDialog(QDialog):
    """
    Separate dialog window for viewing and searching DICOM tags.
    
    Features:
    - Tree view of all DICOM tags
    - Search/filter by tag name or value
    - Show/hide private tags
    - Resizable window
    """
    
    def __init__(self, parent=None):
        """
        Initialize the tag viewer dialog.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.setWindowTitle("DICOM Tag Viewer/Editor")
        self.setModal(False)  # Non-modal so it can stay open
        self.resize(800, 600)
        
        self.parser: Optional[DICOMParser] = None
        self.dataset: Optional[Dataset] = None
        self.show_private_tags = True
        self.all_tag_items: list = []  # Store all items for filtering
        self.editor: Optional[DICOMEditor] = None
        self.history_manager: Optional[TagEditHistoryManager] = None
        
        # Caching for performance
        self._cached_tags: Optional[Dict[str, Any]] = None
        self._cached_search_text: str = ""
        self._cached_include_private: bool = True
        
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
        self.tree_widget.setColumnWidth(0, 100)
        self.tree_widget.setColumnWidth(1, 200)
        self.tree_widget.setColumnWidth(2, 50)
        self.tree_widget.setColumnWidth(3, 300)
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree_widget)
        
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
        self._cached_search_text = ""
        self._populate_tags()
    
    def _populate_tags(self, search_text: str = "") -> None:
        """
        Populate the tree widget with DICOM tags.
        
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
            tags = self.parser.get_all_tags(include_private=self.show_private_tags)
            self._cached_tags = tags
            self._cached_include_private = self.show_private_tags
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
                    tag_item.setText(1, tag_data.get("name", ""))
                    tag_item.setText(2, tag_data.get("VR", ""))
                    
                    # Format value
                    value = tag_data.get("value", "")
                    if isinstance(value, list):
                        value_str = ", ".join(str(v) for v in value)
                    else:
                        value_str = str(value)
                    
                    # Don't truncate in separate window - show full value
                    tag_item.setText(3, value_str)
                    tag_item.setData(0, Qt.ItemDataRole.UserRole, tag_str)
                    tag_item.setData(0, Qt.ItemDataRole.UserRole + 1, tag_data)
                    
                    self.all_tag_items.append(tag_item)
            
            # Resize columns only on initial load (no search text)
            # Skip expensive column resizing during filtering/searching
            if not search_text:
                self.tree_widget.resizeColumnToContents(0)
                self.tree_widget.resizeColumnToContents(1)
                self.tree_widget.resizeColumnToContents(2)
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
                
                # Create edit command
                if self.history_manager and self.dataset:
                    command = EditTagCommand(
                        self.dataset,
                        tag_str,
                        old_value,
                        new_value,
                        vr
                    )
                    # Execute command through history manager
                    self.history_manager.execute_command(command)
                else:
                    # Fallback: update directly if no history manager
                    success = self.editor.update_tag(tag_str, new_value, vr)
                    if not success:
                        QMessageBox.warning(
                            self,
                            "Edit Failed",
                            f"Failed to update tag {tag_str}.\n"
                            "The tag may be read-only or the value may be invalid."
                        )
                        return
                
                # Refresh the tree view
                search_text = self.search_edit.text()
                self._populate_tags(search_text)
    
    def _show_context_menu(self, position) -> None:
        """
        Show context menu for tag items.
        
        Args:
            position: Position where context menu was requested
        """
        item = self.tree_widget.itemAt(position)
        if item is None or item.parent() is None:
            return  # Skip group items
        
        menu = QMenu(self)
        edit_action = QAction("Edit Tag", self)
        edit_action.triggered.connect(lambda: self._edit_tag_item(item))
        menu.addAction(edit_action)
        
        menu.exec(self.tree_widget.mapToGlobal(position))

