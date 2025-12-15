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
                                QListWidget, QListWidgetItem, QPushButton, QMenu)
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QContextMenuEvent
from typing import Optional, List, Callable

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
    delete_all_requested = Signal()  # Emitted when Delete All button is clicked
    
    def __init__(self, parent=None):
        """
        Initialize the ROI list panel.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self.roi_manager: Optional[ROIManager] = None
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_instance_identifier = 0
        
        # Callbacks for context menu actions
        self.roi_delete_callback: Optional[Callable[[ROIItem], None]] = None
        self.delete_all_rois_callback: Optional[Callable[[], None]] = None
        self.roi_statistics_overlay_toggle_callback: Optional[Callable[[ROIItem, bool], None]] = None
        self.roi_statistics_selection_callback: Optional[Callable[[ROIItem, str, bool], None]] = None
        self.annotation_options_callback: Optional[Callable[[], None]] = None
        
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
        
        # Set minimum height to show at least 2 ROIs, but allow expansion
        # Use typical row height for QListWidget (approximately 25px per row)
        row_height = 25  # Typical row height for QListWidget
        min_list_height = (row_height * 2) + 10  # 2 rows minimum + padding
        self.roi_list.setMinimumHeight(min_list_height)
        
        # Allow the list to expand vertically (no maximum height constraint)
        # The list will grow/shrink based on available space
        from PySide6.QtWidgets import QSizePolicy
        self.roi_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout.addWidget(self.roi_list, 1)  # Add with stretch factor 1 to allow resizing
        
        # Buttons
        button_layout = QHBoxLayout()
        
        delete_button = QPushButton("Delete Selected")
        delete_button.clicked.connect(self._delete_selected_roi)
        button_layout.addWidget(delete_button)
        
        delete_all_button = QPushButton("Delete All")
        delete_all_button.clicked.connect(self._delete_all_rois)
        button_layout.addWidget(delete_all_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
    
    def set_roi_manager(self, roi_manager: ROIManager) -> None:
        """
        Set the ROI manager.
        
        Args:
            roi_manager: ROIManager instance
        """
        self.roi_manager = roi_manager
    
    def update_roi_list(self, study_uid: str, series_uid: str, instance_identifier: int, roi_manager: Optional[ROIManager] = None) -> None:
        """
        Update the ROI list for a slice using composite key.
        
        Args:
            study_uid: StudyInstanceUID
            series_uid: SeriesInstanceUID
            instance_identifier: InstanceNumber from DICOM or slice_index as fallback
            roi_manager: Optional ROI manager to use. If not provided, uses the panel's stored ROI manager.
        """
        self.current_study_uid = study_uid
        self.current_series_uid = series_uid
        self.current_instance_identifier = instance_identifier
        
        # Store current selection - get ROI object, not just text
        current_item = self.roi_list.currentItem()
        selected_roi = current_item.data(Qt.ItemDataRole.UserRole) if current_item else None
        selected_text = current_item.text() if current_item else None
        
        # Block signals while clearing to prevent triggering selection change
        self.roi_list.blockSignals(True)
        self.roi_list.clear()
        self.roi_list.blockSignals(False)
        
        # Use provided ROI manager if available, otherwise fall back to stored reference
        manager_to_use = roi_manager if roi_manager is not None else self.roi_manager
        
        if manager_to_use is None:
            return
        
        # Update stored ROI manager reference if a manager was provided
        # This ensures selection and other operations use the correct manager
        if roi_manager is not None:
            self.roi_manager = roi_manager
        
        # Get ROIs for current slice using composite key
        rois = manager_to_use.get_rois_for_slice(study_uid, series_uid, instance_identifier)
        
        # Add to list
        for i, roi in enumerate(rois):
            item_text = f"ROI {i+1} ({roi.shape_type})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, roi)
            self.roi_list.addItem(item)
        
        # Restore selection if ROI object matches (not just text)
        if selected_roi is not None:
            for i, roi in enumerate(rois):
                if roi == selected_roi:  # Object identity check
                    item = self.roi_list.item(i)
                    if item:
                        self.roi_list.setCurrentItem(item)
                    break
    
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
                    self.update_roi_list(self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
    
    def _delete_all_rois(self) -> None:
        """
        Delete all ROIs on current slice.
        
        Emits delete_all_requested signal to be handled by main application.
        """
        self.delete_all_requested.emit()
    
    def select_roi_in_list(self, roi: Optional[ROIItem]) -> None:
        """
        Select ROI in the list.
        
        Args:
            roi: ROI item to select, or None to deselect
        """
        # print(f"[DEBUG-DESELECT] select_roi_in_list: roi={id(roi) if roi else None}")
        current_item = self.roi_list.currentItem()
        # print(f"[DEBUG-DESELECT]   Current list item before: {current_item.text() if current_item else None}")
        
        if roi is None:
            # Block signals to prevent itemSelectionChanged from firing
            self.roi_list.blockSignals(True)
            self.roi_list.clearSelection()
            # Also clear the current item - clearSelection() doesn't do this
            self.roi_list.setCurrentItem(None)
            self.roi_list.blockSignals(False)
            current_item_after = self.roi_list.currentItem()
            # print(f"[DEBUG-DESELECT]   Current list item after clearSelection: {current_item_after.text() if current_item_after else None}")
            return
        
        # Find item for this ROI
        for i in range(self.roi_list.count()):
            item = self.roi_list.item(i)
            item_roi = item.data(Qt.ItemDataRole.UserRole)
            if item_roi == roi:
                # Block signals to prevent itemSelectionChanged from firing if item is already current
                if self.roi_list.currentItem() == item:
                    # Already selected, don't trigger signal
                    # print(f"[DEBUG-DESELECT]   Item {i} already current, skipping setCurrentItem")
                    return
                self.roi_list.setCurrentItem(item)
                # print(f"[DEBUG-DESELECT]   Selected item {i} in list")
                break
    
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Handle right-click context menu on list items."""
        # Get item at click position
        item = self.roi_list.itemAt(self.roi_list.mapFromGlobal(event.globalPos()))
        if item is None:
            return
        
        roi = item.data(Qt.ItemDataRole.UserRole)
        if roi is None:
            return
        
        # Create context menu
        context_menu = QMenu(self)
        
        # Delete action
        delete_action = context_menu.addAction("Delete ROI")
        delete_action.triggered.connect(lambda: self._handle_delete_roi(roi))
        
        # Delete all ROIs action
        delete_all_action = context_menu.addAction("Delete all ROIs (D)")
        if self.delete_all_rois_callback:
            delete_all_action.triggered.connect(self.delete_all_rois_callback)
        
        context_menu.addSeparator()
        
        # Statistics Overlay submenu
        stats_submenu = context_menu.addMenu("Statistics Overlay")
        
        # Toggle overlay visibility
        toggle_action = stats_submenu.addAction("Show Statistics Overlay")
        toggle_action.setCheckable(True)
        toggle_action.setChecked(roi.statistics_overlay_visible)
        toggle_action.triggered.connect(lambda checked: self._handle_statistics_overlay_toggle(roi, checked))
        
        stats_submenu.addSeparator()
        
        # Statistics checkboxes
        mean_action = stats_submenu.addAction("Show Mean")
        mean_action.setCheckable(True)
        mean_action.setChecked("mean" in roi.visible_statistics)
        mean_action.triggered.connect(lambda checked: self._handle_statistic_toggle(roi, "mean", checked))
        
        std_action = stats_submenu.addAction("Show Std Dev")
        std_action.setCheckable(True)
        std_action.setChecked("std" in roi.visible_statistics)
        std_action.triggered.connect(lambda checked: self._handle_statistic_toggle(roi, "std", checked))
        
        min_action = stats_submenu.addAction("Show Min")
        min_action.setCheckable(True)
        min_action.setChecked("min" in roi.visible_statistics)
        min_action.triggered.connect(lambda checked: self._handle_statistic_toggle(roi, "min", checked))
        
        max_action = stats_submenu.addAction("Show Max")
        max_action.setCheckable(True)
        max_action.setChecked("max" in roi.visible_statistics)
        max_action.triggered.connect(lambda checked: self._handle_statistic_toggle(roi, "max", checked))
        
        count_action = stats_submenu.addAction("Show Pixels")
        count_action.setCheckable(True)
        count_action.setChecked("count" in roi.visible_statistics)
        count_action.triggered.connect(lambda checked: self._handle_statistic_toggle(roi, "count", checked))
        
        area_action = stats_submenu.addAction("Show Area")
        area_action.setCheckable(True)
        area_action.setChecked("area" in roi.visible_statistics)
        area_action.triggered.connect(lambda checked: self._handle_statistic_toggle(roi, "area", checked))
        
        context_menu.addSeparator()
        
        # Annotation Options action
        annotation_options_action = context_menu.addAction("Annotation Options...")
        annotation_options_action.triggered.connect(self._handle_annotation_options)
        
        # Show context menu
        context_menu.exec(event.globalPos())
    
    def _handle_delete_roi(self, roi: ROIItem) -> None:
        """Handle ROI delete from context menu."""
        if self.roi_delete_callback:
            self.roi_delete_callback(roi)
        else:
            # Fallback to default behavior
            scene = roi.item.scene()
            if scene and self.roi_manager:
                self.roi_manager.delete_roi(roi, scene)
                self.roi_deleted.emit(roi)
                self.update_roi_list(self.current_study_uid, self.current_series_uid, self.current_instance_identifier)
    
    def _handle_statistics_overlay_toggle(self, roi: ROIItem, visible: bool) -> None:
        """Handle statistics overlay toggle from context menu."""
        if self.roi_statistics_overlay_toggle_callback:
            self.roi_statistics_overlay_toggle_callback(roi, visible)
    
    def _handle_statistic_toggle(self, roi: ROIItem, stat_name: str, checked: bool) -> None:
        """Handle individual statistic toggle from context menu."""
        if self.roi_statistics_selection_callback:
            self.roi_statistics_selection_callback(roi, stat_name, checked)
    
    def _handle_annotation_options(self) -> None:
        """Handle annotation options request from context menu."""
        if self.annotation_options_callback:
            self.annotation_options_callback()

