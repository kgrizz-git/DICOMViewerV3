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
                                QPushButton, QCheckBox, QGroupBox)
from PySide6.QtCore import Qt, Signal
from typing import Optional, Dict, Any
import pydicom
from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser


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
        
        self._create_ui()
    
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
        layout.addWidget(self.tree_widget)
        
        # Buttons
        button_layout = QHBoxLayout()
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
        self._populate_tags()
    
    def _populate_tags(self, search_text: str = "") -> None:
        """
        Populate the tree widget with DICOM tags.
        
        Args:
            search_text: Optional search text to filter tags
        """
        if self.parser is None:
            return
        
        self.tree_widget.clear()
        self.all_tag_items = []
        
        # Get all tags
        tags = self.parser.get_all_tags(include_private=self.show_private_tags)
        
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
        
        # Resize columns
        self.tree_widget.resizeColumnToContents(0)
        self.tree_widget.resizeColumnToContents(1)
        self.tree_widget.resizeColumnToContents(2)
    
    def _on_search_changed(self, text: str) -> None:
        """
        Handle search text change.
        
        Args:
            text: Search text
        """
        self._populate_tags(text)
    
    def _on_private_tags_toggled(self, checked: bool) -> None:
        """
        Handle private tags checkbox toggle.
        
        Args:
            checked: Checkbox state
        """
        self.show_private_tags = checked
        if self.parser is not None:
            search_text = self.search_edit.text()
            self._populate_tags(search_text)

