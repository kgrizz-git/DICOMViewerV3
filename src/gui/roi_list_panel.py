"""
ROI List Panel

This module provides a panel for listing and managing ROIs for the current slice.

Inputs:
    - ROI list from ROI manager
    - User selection and actions
    
Outputs:
    - ROI list display
    - Selection signals
    
Requirements:
    - PySide6 for GUI components
    - ROIManager for ROI data
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                                QListWidget, QListWidgetItem, QPushButton)
from PySide6.QtCore import Qt, Signal
from typing import Optional, List

from tools.roi_manager import ROIManager, ROIItem


class ROIListPanel(QWidget):
    """
    Panel for listing and managing ROIs.
    
    Features:
    - Display all ROIs for current slice
    - Select ROI from list
    - Delete ROI
    - Show ROI type (rectangle/ellipse)
    """
    
    # Signals
    roi_selected = Signal(object)  # Emitted when ROI is selected (ROIItem)
    roi_deleted = Signal(object)  # Emitted when ROI is deleted (ROIItem)
    
    def __init__(self, parent=None):
        """
        Initialize the ROI list panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.roi_manager: Optional[ROIManager] = None
        self.current_slice_index = 0
        
        self._create_ui()
    
    def _create_ui(self) -> None:
        """Create the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Title
        title_label = QLabel("ROIs")
        title_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        layout.addWidget(title_label)
        
        # ROI list
        self.roi_list = QListWidget()
        self.roi_list.itemSelectionChanged.connect(self._on_list_selection_changed)
        self.roi_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.roi_list)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self._delete_selected_roi)
        button_layout.addWidget(delete_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
    
    def set_roi_manager(self, roi_manager: ROIManager) -> None:
        """
        Set the ROI manager.
        
        Args:
            roi_manager: ROIManager instance
        """
        self.roi_manager = roi_manager
    
    def update_roi_list(self, slice_index: int) -> None:
        """
        Update the ROI list for a slice.
        
        Args:
            slice_index: Current slice index
        """
        self.current_slice_index = slice_index
        
        # Store current selection
        current_item = self.roi_list.currentItem()
        selected_text = current_item.text() if current_item else None
        
        self.roi_list.clear()
        
        if self.roi_manager is None:
            return
        
        # Get ROIs for current slice
        rois = self.roi_manager.get_rois_for_slice(slice_index)
        
        # Add to list
        for i, roi in enumerate(rois):
            item_text = f"ROI {i+1} ({roi.shape_type})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, roi)
            self.roi_list.addItem(item)
            
            # Restore selection if it was this item
            if selected_text == item_text:
                self.roi_list.setCurrentItem(item)
    
    def _on_list_selection_changed(self) -> None:
        """Handle list selection change."""
        current_item = self.roi_list.currentItem()
        if current_item and self.roi_manager:
            roi = current_item.data(Qt.ItemDataRole.UserRole)
            if roi:
                self.roi_manager.select_roi(roi)
                self.roi_selected.emit(roi)
    
    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Handle item double-click."""
        roi = item.data(Qt.ItemDataRole.UserRole)
        if roi and self.roi_manager:
            self.roi_manager.select_roi(roi)
            self.roi_selected.emit(roi)
    
    def _delete_selected_roi(self) -> None:
        """Delete selected ROI."""
        current_item = self.roi_list.currentItem()
        if current_item and self.roi_manager:
            roi = current_item.data(Qt.ItemDataRole.UserRole)
            if roi:
                # Get scene from ROI item's parent
                scene = roi.item.scene()
                if scene:
                    self.roi_manager.delete_roi(roi, scene)
                    self.roi_deleted.emit(roi)
                    # Update list
                    self.update_roi_list(self.current_slice_index)
    
    def select_roi_in_list(self, roi: Optional[ROIItem]) -> None:
        """
        Select ROI in the list.
        
        Args:
            roi: ROI item to select, or None to deselect
        """
        if roi is None:
            self.roi_list.clearSelection()
            return
        
        # Find item for this ROI
        for i in range(self.roi_list.count()):
            item = self.roi_list.item(i)
            item_roi = item.data(Qt.ItemDataRole.UserRole)
            if item_roi == roi:
                self.roi_list.setCurrentItem(item)
                break

