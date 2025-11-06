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
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QTreeWidget, QTreeWidgetItem, QLineEdit,
                                QPushButton, QCheckBox, QSplitter)
from PySide6.QtCore import Qt, Signal
from typing import Optional, Dict, Any
import pydicom
from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser


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
    
    def __init__(self, parent=None):
        """
        Initialize the metadata panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.parser: Optional[DICOMParser] = None
        self.dataset: Optional[Dataset] = None
        self.show_private_tags = True
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
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
        
        # Tree widget for tags
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Tag", "Name", "VR", "Value"])
        self.tree_widget.setColumnWidth(0, 100)
        self.tree_widget.setColumnWidth(1, 200)
        self.tree_widget.setColumnWidth(2, 50)
        self.tree_widget.setColumnWidth(3, 200)
        self.tree_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree_widget)
    
    def set_dataset(self, dataset: Dataset) -> None:
        """
        Set the DICOM dataset to display.
        
        Args:
            dataset: pydicom Dataset
        """
        self.dataset = dataset
        self.parser = DICOMParser(dataset)
        self._populate_tags()
    
    def _populate_tags(self) -> None:
        """Populate the tree widget with DICOM tags."""
        if self.parser is None:
            return
        
        self.tree_widget.clear()
        
        # Get all tags
        tags = self.parser.get_all_tags(include_private=self.show_private_tags)
        
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
                
                # Truncate long values
                if len(value_str) > 50:
                    value_str = value_str[:47] + "..."
                
                tag_item.setText(3, value_str)
                tag_item.setData(0, Qt.ItemDataRole.UserRole, tag_str)
                tag_item.setData(0, Qt.ItemDataRole.UserRole + 1, tag_data)
        
        # Resize columns
        self.tree_widget.resizeColumnToContents(0)
        self.tree_widget.resizeColumnToContents(1)
        self.tree_widget.resizeColumnToContents(2)
    
    def _on_private_tags_toggled(self, checked: bool) -> None:
        """
        Handle private tags checkbox toggle.
        
        Args:
            checked: Checkbox state
        """
        self.show_private_tags = checked
        if self.parser is not None:
            self._populate_tags()
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Handle double-click on tag item for editing.
        
        Args:
            item: Tree widget item
            column: Column clicked
        """
        if column != 3:  # Only edit value column
            return
        
        tag_data = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if tag_data is None:
            return
        
        # Create edit dialog or inline editor
        # For now, we'll use a simple approach
        # In a full implementation, this would open a proper edit dialog
        # that handles different VR types appropriately
        pass  # Placeholder for edit functionality

