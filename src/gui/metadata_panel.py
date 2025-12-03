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
                                QPushButton, QCheckBox, QSplitter, QDialog,
                                QStyledItemDelegate, QStyleOptionViewItem, QMenu)
from PySide6.QtCore import Qt, Signal, QTimer, QPoint
from PySide6.QtGui import QFont, QPainter, QAction, QColor
from typing import Optional, Dict, Any, List, Callable
import pydicom
from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser
from core.dicom_editor import DICOMEditor
from core.tag_edit_history import TagEditHistoryManager
from gui.dialogs.tag_edit_dialog import TagEditDialog
from utils.config_manager import ConfigManager
from utils.undo_redo import UndoRedoManager, TagEditCommand


class MetadataItemDelegate(QStyledItemDelegate):
    """
    Custom delegate for metadata panel tree widget.
    
    This delegate handles indentation rendering:
    - Group items: Keep their indentation (20px from tree widget)
    - Tag items: Remove indentation from first column only to make tags fully left-aligned
    - Other columns (Name, VR, Value): Render normally without adjustment
    """
    
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        """
        Paint the item with column-specific adjustments.
        
        Only adjusts the first column (Tag) for tag items to remove indentation.
        Other columns render normally to maintain proper alignment.
        
        Args:
            painter: QPainter instance
            option: Style option for the item
            index: Model index of the item
        """
        # Get the tree widget from the option
        tree_widget = option.widget
        if tree_widget is None or not isinstance(tree_widget, QTreeWidget):
            super().paint(painter, option, index)
            return
        
        # Get the item from the tree widget using the index
        item = tree_widget.itemFromIndex(index)
        if item is None:
            super().paint(painter, option, index)
            return
        
        # Check if this is a tag item (has a parent that is a group item) and we're painting column 0
        parent = item.parent()
        is_tag_item = (parent is not None and parent.text(0).startswith("Group "))
        is_first_column = (index.column() == 0)
        
        if is_tag_item and is_first_column:
            # This is the Tag column of a tag item - remove indentation
            base_indent = tree_widget.indentation()
            # Create a modified option with adjusted rect for first column only
            adjusted_option = QStyleOptionViewItem(option)
            current_left = adjusted_option.rect.left()
            if current_left >= base_indent:
                # Shift the rect left by the indentation amount
                adjusted_option.rect.setLeft(current_left - base_indent)
                # Adjust width to maintain the same right edge
                adjusted_option.rect.setWidth(adjusted_option.rect.width() + base_indent)
            super().paint(painter, adjusted_option, index)
        else:
            # For group items or other columns - render normally
            super().paint(painter, option, index)


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
    
    def __init__(self, parent=None, config_manager: Optional[ConfigManager] = None,
                 undo_redo_manager: Optional[UndoRedoManager] = None):
        """
        Initialize the metadata panel.
        
        Args:
            parent: Parent widget
            config_manager: Optional ConfigManager instance for saving/loading column widths
            undo_redo_manager: Optional UndoRedoManager for unified undo/redo
        """
        super().__init__(parent)
        self.setObjectName("metadata_panel")
        
        self.parser: Optional[DICOMParser] = None
        self.dataset: Optional[Dataset] = None
        self.show_private_tags = True
        self.privacy_mode: bool = False
        self.editor: Optional[DICOMEditor] = None
        self.history_manager: Optional[TagEditHistoryManager] = None
        self.config_manager: Optional[ConfigManager] = config_manager
        self.undo_redo_manager: Optional[UndoRedoManager] = undo_redo_manager
        self.ui_refresh_callback: Optional[Callable] = None
        
        # Undo/redo callbacks
        self.undo_callback: Optional[Callable] = None
        self.redo_callback: Optional[Callable] = None
        self.can_undo_callback: Optional[Callable] = None
        self.can_redo_callback: Optional[Callable] = None
        
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
        # Clear cache to force refresh
        self._cached_tags = None
        # Refresh display if parser is available
        if self.parser is not None:
            search_text = self.search_edit.text()
            self._populate_tags(search_text)
    
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
        # Set indentation for expand/collapse functionality
        # The custom delegate will remove indentation from tag items to make them fully left-aligned
        self.tree_widget.setIndentation(20)  # Indent for expand/collapse indicators (triangle arrows)
        self.tree_widget.setRootIsDecorated(False)  # Hide root expand/collapse indicator
        # Ensure branch decorations (expand/collapse indicators) are visible
        # QTreeWidget shows these automatically when items have children
        
        # Apply custom delegate to remove indentation from tag items
        self.tree_widget.setItemDelegate(MetadataItemDelegate(self.tree_widget))
        
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
        layout.addWidget(self.tree_widget)
    
    def set_dataset(self, dataset: Optional[Dataset], clear_filter: bool = False) -> None:
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
            tags = self.parser.get_all_tags(include_private=self.show_private_tags, privacy_mode=self.privacy_mode)
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
            # Group headings will be top-level children of invisible root (indented)
            # Tags will be children of group items (enabling collapse) but rendered fully left-aligned via delegate
            root_item = self.tree_widget.invisibleRootItem()
            
            # Create bold font for group headings
            bold_font = QFont()
            bold_font.setBold(True)
            
            for group, tag_list in sorted(groups.items()):
                # Group header as child of root (will be indented by tree widget indentation)
                group_item = QTreeWidgetItem(root_item)
                group_item.setText(0, f"Group {group}")
                # Enable expansion/collapse for group items - need both ItemIsEnabled and ItemIsSelectable
                group_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                group_item.setFont(0, bold_font)  # Make group heading bold
                
                # Add tag items as children first
                for tag_str, tag_data in tag_list:
                    # Tags as children of group items (enables collapse functionality)
                    # The custom delegate will render them fully left-aligned
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
                    
                    # Set left alignment for tag column
                    tag_item.setTextAlignment(0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                    
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
                    
                    # Set background color for edited tags
                    if is_edited:
                        # Use dark purple background (works well with white text in dark mode)
                        edited_color = QColor(80, 50, 120)  # Dark purple
                        for col in range(4):
                            tag_item.setBackground(col, edited_color)
                    
                    tag_item.setData(0, Qt.ItemDataRole.UserRole, tag_str)
                    tag_item.setData(0, Qt.ItemDataRole.UserRole + 1, tag_data)
                
                # Set indicator policy and expanded state after children are added
                # This ensures the expand/collapse indicator (triangle arrow) is visible
                group_item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
                group_item.setExpanded(True)  # Expand groups by default
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
        
        # Check if it's a group item (starts with "Group ")
        is_group_item = item.text(0).startswith("Group ")
        
        # Create context menu
        context_menu = QMenu(self)
        
        if is_group_item:
            # Group item - show Collapse/Expand option with double-click hint
            if item.childCount() > 0:
                if item.isExpanded():
                    collapse_action = context_menu.addAction("Collapse (double-click)")
                    collapse_action.triggered.connect(lambda: item.setExpanded(False))
                else:
                    expand_action = context_menu.addAction("Expand (double-click)")
                    expand_action.triggered.connect(lambda: item.setExpanded(True))
        else:
            # Tag item - show Edit, Undo, Redo, and Collapse/Expand options
            edit_action = context_menu.addAction("Edit Tag")
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
            if parent is not None and parent.text(0).startswith("Group "):
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
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """
        Handle double-click on tag item for editing.
        
        Args:
            item: Tree widget item
            column: Column clicked
        """
        if column != 3:  # Only edit value column
            return
        
        # Skip group items (check if first column starts with "Group")
        if item.text(0).startswith("Group "):
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
                # Use unified undo/redo manager if available
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
                        from PySide6.QtWidgets import QMessageBox
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
                # Refresh the tree view (preserve search text)
                search_text = self.search_edit.text()
                # Clear cache since tag was edited
                self._cached_tags = None
                # Clear parser cache so it re-reads from updated dataset
                if self.parser is not None:
                    self.parser._tag_cache.clear()
                self._populate_tags(search_text)

