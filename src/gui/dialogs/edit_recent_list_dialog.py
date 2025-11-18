"""
Edit Recent List Dialog

This module provides a dialog for editing the recent files list.

Inputs:
    - User selections of items to remove from recent list
    
Outputs:
    - Updated recent files list in config
    
Requirements:
    - PySide6 for dialog components
    - ConfigManager for settings persistence
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QListWidget, QListWidgetItem, QPushButton,
                                QDialogButtonBox)
from PySide6.QtCore import Qt
from typing import Optional

from utils.config_manager import ConfigManager


class EditRecentListDialog(QDialog):
    """
    Dialog for editing the recent files list.
    
    Features:
    - Display all recent files/folders in a checkable list
    - Remove selected items from the list
    - Update config when OK is clicked
    """
    
    def __init__(self, config_manager: ConfigManager, parent: Optional[QDialog] = None):
        """
        Initialize the Edit Recent List dialog.
        
        Args:
            config_manager: ConfigManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.config_manager = config_manager
        self.setWindowTitle("Edit Recent List")
        self.setModal(True)
        self.resize(800, 400)
        
        # Store original recent files for cancel functionality
        self.original_recent_files = config_manager.get_recent_files().copy()
        
        self._create_ui()
        self._populate_list()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        
        # Label
        label = QLabel("Select items to remove from recent list:")
        layout.addWidget(label)
        
        # List widget with checkable items
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.list_widget)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Remove Selected button
        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self._remove_selected)
        button_layout.addWidget(self.remove_button)
        
        button_layout.addStretch()
        
        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._on_ok)
        button_box.rejected.connect(self.reject)
        button_layout.addWidget(button_box)
        
        layout.addLayout(button_layout)
    
    def _populate_list(self) -> None:
        """Populate the list widget with recent files."""
        self.list_widget.clear()
        
        recent_files = self.config_manager.get_recent_files()
        
        if not recent_files:
            # Show message if no recent files
            item = QListWidgetItem("No recent files")
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # Make it non-interactive
            self.list_widget.addItem(item)
            self.remove_button.setEnabled(False)
        else:
            for file_path in recent_files:
                # Create checkable item with full path (no truncation)
                item = QListWidgetItem(file_path)
                item.setCheckState(Qt.CheckState.Unchecked)
                # Store full path in item data
                item.setData(Qt.ItemDataRole.UserRole, file_path)
                # Add tooltip with full path for hover display
                item.setToolTip(file_path)
                self.list_widget.addItem(item)
            
            self.remove_button.setEnabled(True)
    
    def _remove_selected(self) -> None:
        """Remove checked items from the list."""
        # Collect items to remove (iterate backwards to avoid index issues)
        items_to_remove = []
        for i in range(self.list_widget.count() - 1, -1, -1):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                items_to_remove.append(i)
        
        # Remove items from widget
        for index in items_to_remove:
            self.list_widget.takeItem(index)
        
        # If list is now empty, show message
        if self.list_widget.count() == 0:
            item = QListWidgetItem("No recent files")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            self.remove_button.setEnabled(False)
    
    def _on_ok(self) -> None:
        """Handle OK button click - save changes to config."""
        # Get all remaining file paths from the list
        remaining_files = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            # Skip non-interactive items (like "No recent files" message)
            if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                file_path = item.data(Qt.ItemDataRole.UserRole)
                if file_path:
                    remaining_files.append(file_path)
        
        # Update config with remaining files
        self.config_manager.config["recent_files"] = remaining_files
        self.config_manager.save_config()
        
        self.accept()

