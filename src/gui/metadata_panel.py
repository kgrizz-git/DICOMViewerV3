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
                                QPushButton, QCheckBox, QSplitter, QDialog)
from PySide6.QtCore import Qt, Signal, QTimer
from typing import Optional, Dict, Any, List
import pydicom
from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser
from core.dicom_editor import DICOMEditor
from core.tag_edit_history import TagEditHistoryManager, EditTagCommand
from gui.dialogs.tag_edit_dialog import TagEditDialog
from utils.config_manager import ConfigManager


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
    
    def __init__(self, parent=None, config_manager: Optional[ConfigManager] = None):
        """
        Initialize the metadata panel.
        
        Args:
            parent: Parent widget
            config_manager: Optional ConfigManager instance for saving/loading column widths
        """
        super().__init__(parent)
        self.setObjectName("metadata_panel")
        
        self.parser: Optional[DICOMParser] = None
        self.dataset: Optional[Dataset] = None
        self.show_private_tags = True
        self.editor: Optional[DICOMEditor] = None
        self.history_manager: Optional[TagEditHistoryManager] = None
        self.config_manager: Optional[ConfigManager] = config_manager
        
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
        
        # Search input field
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter tags...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit)
        
        # Tree widget for tags
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Tag", "Name", "VR", "Value"])
        
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
        
        # Connect to header sectionResized signal to save column widths
        header = self.tree_widget.header()
        header.sectionResized.connect(self._on_column_resized)
        
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
                # Search in tag number, name, VR, and value
                tag_match = tag_str.lower() if tag_str else ""
                name_match = tag_data.get("name", "").lower() if tag_data.get("name") else ""
                vr_match = tag_data.get("VR", "").lower() if tag_data.get("VR") else ""
                
                # Format value for searching
                value = tag_data.get("value", "")
                if isinstance(value, list):
                    value_str = ", ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                value_match = value_str.lower()
                
                # Check if search text matches any field
                if (search_lower in tag_match or 
                    search_lower in name_match or 
                    search_lower in vr_match or 
                    search_lower in value_match):
                    filtered_tags[tag_str] = tag_data
            tags = filtered_tags
        
        # Update cached search text
        self._cached_search_text = search_text
        
        # Disable widget updates during population to prevent expensive repaints
        self.tree_widget.setUpdatesEnabled(False)
        try:
            self.tree_widget.clear()
            
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
        finally:
            # Always re-enable updates, even if an error occurred
            self.tree_widget.setUpdatesEnabled(True)
        
        # Note: Column widths are preserved from saved configuration
        # Removed resizeColumnToContents calls to maintain user's preferred column widths
    
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
                        from PySide6.QtWidgets import QMessageBox
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
                self._populate_tags(search_text)

