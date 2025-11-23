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
                                QDialogButtonBox, QMessageBox, QMenu)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from typing import Optional

from utils.config_manager import ConfigManager


class EditRecentListDialog(QDialog):
    """
    Dialog for editing the recent files list.
    
    Features:
    - Display all recent files/folders in a checkable list
    - Remove selected items from the list
    - Remove all items from the list at once
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
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.list_widget.itemSelectionChanged.connect(self._update_move_buttons_state)
        # Connect itemPressed to capture selection before it changes
        self.list_widget.itemPressed.connect(self._on_item_pressed)
        # Connect itemClicked to unify selection and checkbox
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        # Connect itemChanged to handle checkbox clicks
        self.list_widget.itemChanged.connect(self._on_item_changed)
        # Enable context menu
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        # Track checkbox state before click to detect if checkbox was clicked vs row
        self._checkbox_state_before_click = {}
        layout.addWidget(self.list_widget)
        
        # Button layout
        button_layout = QHBoxLayout()
        
        # Remove All button (styled in red for warning) - at far left
        self.remove_all_button = QPushButton("Remove All")
        self.remove_all_button.clicked.connect(self._remove_all)
        # Style the button in red to indicate destructive action
        self.remove_all_button.setStyleSheet("QPushButton { background-color: #d32f2f; color: white; font-weight: bold; } QPushButton:hover { background-color: #b71c1c; }")
        button_layout.addWidget(self.remove_all_button)
        
        # Remove Selected button
        self.remove_button = QPushButton("Remove Selected")
        self.remove_button.clicked.connect(self._remove_selected)
        button_layout.addWidget(self.remove_button)
        
        button_layout.addStretch()
        
        # Move Up button
        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.clicked.connect(self._move_item_up)
        self.move_up_button.setEnabled(False)
        button_layout.addWidget(self.move_up_button)
        
        # Move Down button
        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.clicked.connect(self._move_item_down)
        self.move_down_button.setEnabled(False)
        button_layout.addWidget(self.move_down_button)
        
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
            self.remove_all_button.setEnabled(False)
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
            self.remove_all_button.setEnabled(True)
            # Move buttons will be enabled/disabled based on selection
            self._update_move_buttons_state()
    
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
            self.remove_all_button.setEnabled(False)
            self.move_up_button.setEnabled(False)
            self.move_down_button.setEnabled(False)
    
    def _on_item_pressed(self, item: QListWidgetItem) -> None:
        """
        Handle item pressed - capture checkbox state before click.
        This is used to detect if checkbox was clicked vs row was clicked.
        """
        # Store checkbox state before click to detect if checkbox was clicked
        if item.flags() & Qt.ItemFlag.ItemIsEnabled:
            file_path = item.data(Qt.ItemDataRole.UserRole)
            if file_path:
                self._checkbox_state_before_click[file_path] = item.checkState()
    
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        """
        Handle item click - toggle checkbox when row is clicked.
        Selection highlighting will be synced to checkbox state.
        """
        # Skip non-interactive items
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        
        clicked_path = item.data(Qt.ItemDataRole.UserRole)
        if not clicked_path:
            return
        
        # Check if checkbox state changed (meaning checkbox was clicked directly)
        # If checkbox was clicked, Qt already toggled it - just sync selection
        checkbox_was_clicked = False
        if clicked_path in self._checkbox_state_before_click:
            previous_state = self._checkbox_state_before_click[clicked_path]
            if item.checkState() != previous_state:
                # Checkbox state changed, so checkbox was clicked - Qt already toggled it
                checkbox_was_clicked = True
            # Clean up the tracking
            del self._checkbox_state_before_click[clicked_path]
        
        # If checkbox wasn't clicked directly, toggle it (row was clicked)
        if not checkbox_was_clicked:
            # Block signals to prevent itemChanged from firing
            self.list_widget.blockSignals(True)
            # Toggle checkbox state
            if item.checkState() == Qt.CheckState.Checked:
                item.setCheckState(Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Checked)
            self.list_widget.blockSignals(False)
        
        # Sync selection to checkbox state (checked = selected, unchecked = not selected)
        # This provides visual feedback
        self.list_widget.blockSignals(True)
        if item.checkState() == Qt.CheckState.Checked:
            item.setSelected(True)
        else:
            item.setSelected(False)
        self.list_widget.blockSignals(False)
        self._update_move_buttons_state()
    
    def _on_item_changed(self, item: QListWidgetItem) -> None:
        """
        Handle item changed (checkbox state change).
        Sync selection highlighting to checkbox state.
        """
        # Skip non-interactive items
        if not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return
        
        # Sync selection to checkbox state (checked = selected, unchecked = not selected)
        # Block signals to prevent recursive calls
        self.list_widget.blockSignals(True)
        if item.checkState() == Qt.CheckState.Checked:
            item.setSelected(True)
        else:
            item.setSelected(False)
        self.list_widget.blockSignals(False)
        self._update_move_buttons_state()
    
    def _show_context_menu(self, position) -> None:
        """
        Show context menu for list items.
        
        Args:
            position: Position where context menu was requested
        """
        item = self.list_widget.itemAt(position)
        if item is None or not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
            return  # Skip non-interactive items
        
        # Select the item if it's not already selected
        if not item.isSelected():
            item.setSelected(True)
            # Also check the checkbox
            item.setCheckState(Qt.CheckState.Checked)
        
        menu = QMenu(self)
        
        # Remove This Item action
        remove_action = QAction("Remove This Item", self)
        remove_action.triggered.connect(lambda: self._delete_context_item(item))
        menu.addAction(remove_action)
        
        menu.addSeparator()
        
        # Move Up action
        move_up_action = QAction("Move Up", self)
        row = self.list_widget.row(item)
        move_up_action.setEnabled(row > 0)
        move_up_action.triggered.connect(lambda: self._move_context_item_up(item))
        menu.addAction(move_up_action)
        
        # Move Down action
        move_down_action = QAction("Move Down", self)
        last_row = self.list_widget.count() - 1
        move_down_action.setEnabled(row < last_row)
        move_down_action.triggered.connect(lambda: self._move_context_item_down(item))
        menu.addAction(move_down_action)
        
        menu.exec(self.list_widget.mapToGlobal(position))
    
    def _delete_context_item(self, item: QListWidgetItem) -> None:
        """Delete a single item from context menu."""
        row = self.list_widget.row(item)
        self.list_widget.takeItem(row)
        
        # If list is now empty, show message
        if self.list_widget.count() == 0:
            item = QListWidgetItem("No recent files")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            self.remove_button.setEnabled(False)
            self.remove_all_button.setEnabled(False)
            self.move_up_button.setEnabled(False)
            self.move_down_button.setEnabled(False)
        else:
            self._update_move_buttons_state()
    
    def _move_context_item_up(self, item: QListWidgetItem) -> None:
        """Move a single item up from context menu."""
        row = self.list_widget.row(item)
        if row > 0:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row - 1, item)
            item.setSelected(True)
            self._update_move_buttons_state()
    
    def _move_context_item_down(self, item: QListWidgetItem) -> None:
        """Move a single item down from context menu."""
        row = self.list_widget.row(item)
        last_row = self.list_widget.count() - 1
        if row < last_row:
            item = self.list_widget.takeItem(row)
            self.list_widget.insertItem(row + 1, item)
            item.setSelected(True)
            self._update_move_buttons_state()
    
    def _remove_all(self) -> None:
        """Remove all items from the list with confirmation."""
        # Check if there are any items to remove
        if self.list_widget.count() == 0:
            return
        
        # Check if the only item is the "No recent files" message
        if self.list_widget.count() == 1:
            item = self.list_widget.item(0)
            if item and not (item.flags() & Qt.ItemFlag.ItemIsEnabled):
                return
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Confirm Remove All",
            "Are you sure you want to remove all items from the recent list?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Clear all items from the list widget
            self.list_widget.clear()
            
            # Show message if list is now empty
            item = QListWidgetItem("No recent files")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(item)
            
            # Disable both remove buttons
            self.remove_button.setEnabled(False)
            self.remove_all_button.setEnabled(False)
            self.move_up_button.setEnabled(False)
            self.move_down_button.setEnabled(False)
    
    def _move_item_up(self) -> None:
        """Move selected items up by one position in the list."""
        selected_items = self.list_widget.selectedItems()
        
        if not selected_items:
            return
        
        # Get row indices of selected items, sorted from top to bottom
        selected_rows = sorted([self.list_widget.row(item) for item in selected_items])
        
        # Check if any selected item is at the top (row 0)
        if selected_rows[0] == 0:
            return  # Can't move up if first item is selected
        
        # Store selected items to restore selection after move
        selected_paths = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        
        # Move items from bottom to top to avoid index shifting issues
        # Process from bottom to top
        for row in reversed(selected_rows):
            if row > 0:  # Can move up
                # Take the item from current position
                item = self.list_widget.takeItem(row)
                # Insert it one position up
                self.list_widget.insertItem(row - 1, item)
        
        # Restore selection
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) in selected_paths:
                item.setSelected(True)
        
        # Update button states
        self._update_move_buttons_state()
    
    def _move_item_down(self) -> None:
        """Move selected items down by one position in the list."""
        selected_items = self.list_widget.selectedItems()
        
        if not selected_items:
            return
        
        # Get row indices of selected items, sorted from top to bottom
        selected_rows = sorted([self.list_widget.row(item) for item in selected_items])
        last_row = self.list_widget.count() - 1
        
        # Check if any selected item is at the bottom
        if selected_rows[-1] == last_row:
            return  # Can't move down if last item is selected
        
        # Store selected items to restore selection after move
        selected_paths = [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]
        
        # Move items from bottom to top to avoid index shifting issues
        # Process from bottom to top
        for row in reversed(selected_rows):
            if row < last_row:  # Can move down
                # Take the item from current position
                item = self.list_widget.takeItem(row)
                # Insert it one position down
                self.list_widget.insertItem(row + 1, item)
        
        # Restore selection
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) in selected_paths:
                item.setSelected(True)
        
        # Update button states
        self._update_move_buttons_state()
    
    def _update_move_buttons_state(self) -> None:
        """Update enabled state of Move Up/Down buttons based on selection."""
        selected_items = self.list_widget.selectedItems()
        
        if not selected_items:
            self.move_up_button.setEnabled(False)
            self.move_down_button.setEnabled(False)
            return
        
        # Get row indices of selected items
        selected_rows = [self.list_widget.row(item) for item in selected_items]
        first_selected_row = min(selected_rows)
        last_selected_row = max(selected_rows)
        last_row = self.list_widget.count() - 1
        
        # Enable/disable Move Up button
        self.move_up_button.setEnabled(first_selected_row > 0)
        
        # Enable/disable Move Down button
        self.move_down_button.setEnabled(last_selected_row < last_row)
    
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

