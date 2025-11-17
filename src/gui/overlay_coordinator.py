"""
Overlay Coordinator

This module coordinates overlay operations and visibility.

Inputs:
    - Overlay configuration changes
    - Overlay visibility toggle requests
    - Font size/color changes
    
Outputs:
    - Overlay updates
    - Visibility state changes
    
Requirements:
    - OverlayManager for overlay operations
    - DICOMParser for metadata parsing
"""

from typing import Optional, Callable
from pydicom.dataset import Dataset
from gui.overlay_manager import OverlayManager
from core.dicom_parser import DICOMParser
from gui.image_viewer import ImageViewer
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem


class OverlayCoordinator:
    """
    Coordinates overlay operations and visibility.
    
    Responsibilities:
    - Handle overlay configuration changes
    - Handle overlay visibility toggles
    - Handle font size/color changes
    - Coordinate with measurement and ROI visibility
    """
    
    def __init__(
        self,
        overlay_manager: OverlayManager,
        image_viewer: ImageViewer,
        get_current_dataset: Callable[[], Optional[Dataset]],
        get_current_studies: Callable[[], dict],
        get_current_study_uid: Callable[[], str],
        get_current_series_uid: Callable[[], str],
        get_current_slice_index: Callable[[], int],
        hide_measurement_labels: Optional[Callable[[bool], None]] = None,
        hide_measurement_graphics: Optional[Callable[[bool], None]] = None,
        hide_roi_graphics: Optional[Callable[[bool], None]] = None,
        hide_roi_statistics_overlays: Optional[Callable[[bool], None]] = None
    ):
        """
        Initialize the overlay coordinator.
        
        Args:
            overlay_manager: Overlay manager instance
            image_viewer: Image viewer widget
            get_current_dataset: Callback to get current dataset
            get_current_studies: Callback to get current studies
            get_current_study_uid: Callback to get current study UID
            get_current_series_uid: Callback to get current series UID
            get_current_slice_index: Callback to get current slice index
            hide_measurement_labels: Optional callback to hide/show measurement labels
            hide_measurement_graphics: Optional callback to hide/show measurement graphics
            hide_roi_graphics: Optional callback to hide/show ROI graphics
        """
        self.overlay_manager = overlay_manager
        self.image_viewer = image_viewer
        self.get_current_dataset = get_current_dataset
        self.get_current_studies = get_current_studies
        self.get_current_study_uid = get_current_study_uid
        self.get_current_series_uid = get_current_series_uid
        self.get_current_slice_index = get_current_slice_index
        self.hide_measurement_labels = hide_measurement_labels
        self.hide_measurement_graphics = hide_measurement_graphics
        self.hide_roi_graphics = hide_roi_graphics
        self.hide_roi_statistics_overlays = hide_roi_statistics_overlays
    
    def handle_overlay_config_applied(self) -> None:
        """Handle overlay configuration being applied."""
        # Recreate overlay if we have a current dataset
        current_studies = self.get_current_studies()
        current_study_uid = self.get_current_study_uid()
        current_series_uid = self.get_current_series_uid()
        current_slice_index = self.get_current_slice_index()
        
        if current_studies and current_series_uid:
            datasets = current_studies.get(current_study_uid, {}).get(current_series_uid, [])
            if current_slice_index < len(datasets):
                dataset = datasets[current_slice_index]
                parser = DICOMParser(dataset)
                total_slices = len(datasets)
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser,
                    total_slices=total_slices if total_slices > 0 else None
                )
    
    def handle_overlay_font_size_changed(self, font_size: int) -> None:
        """
        Handle overlay font size change from toolbar.
        
        Args:
            font_size: New font size in points
        """
        # Update overlay manager
        self.overlay_manager.set_font_size(font_size)
        
        # Recreate overlay if we have a current dataset
        current_studies = self.get_current_studies()
        current_study_uid = self.get_current_study_uid()
        current_series_uid = self.get_current_series_uid()
        current_slice_index = self.get_current_slice_index()
        
        if current_studies and current_series_uid:
            datasets = current_studies.get(current_study_uid, {}).get(current_series_uid, [])
            if current_slice_index < len(datasets):
                dataset = datasets[current_slice_index]
                parser = DICOMParser(dataset)
                total_slices = len(datasets)
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser,
                    total_slices=total_slices if total_slices > 0 else None
                )
    
    def handle_overlay_font_color_changed(self, r: int, g: int, b: int) -> None:
        """
        Handle overlay font color change from toolbar.
        
        Args:
            r: Red component (0-255)
            g: Green component (0-255)
            b: Blue component (0-255)
        """
        # Update overlay manager
        self.overlay_manager.set_font_color(r, g, b)
        
        # Recreate overlay if we have a current dataset
        current_studies = self.get_current_studies()
        current_study_uid = self.get_current_study_uid()
        current_series_uid = self.get_current_series_uid()
        current_slice_index = self.get_current_slice_index()
        
        if current_studies and current_series_uid:
            datasets = current_studies.get(current_study_uid, {}).get(current_series_uid, [])
            if current_slice_index < len(datasets):
                dataset = datasets[current_slice_index]
                parser = DICOMParser(dataset)
                total_slices = len(datasets)
                self.overlay_manager.create_overlay_items(
                    self.image_viewer.scene,
                    parser,
                    total_slices=total_slices if total_slices > 0 else None
                )
    
    def handle_toggle_overlay(self) -> None:
        """Handle toggle overlay request from context menu."""
        # Toggle overlay visibility (cycles through 3 states)
        new_state = self.overlay_manager.toggle_overlay_visibility()
        
        # Update overlay display
        current_dataset = self.get_current_dataset()
        if current_dataset is not None and self.image_viewer.scene is not None:
            # Refresh overlay items
            parser = DICOMParser(current_dataset)
            # Get total slices from current series
            current_study_uid = self.get_current_study_uid()
            current_series_uid = self.get_current_series_uid()
            current_studies = self.get_current_studies()
            
            if current_study_uid and current_series_uid:
                datasets = current_studies.get(current_study_uid, {}).get(current_series_uid, [])
                total_slices = len(datasets) if datasets else None
            else:
                total_slices = None
            self.overlay_manager.create_overlay_items(
                self.image_viewer.scene,
                parser,
                total_slices=total_slices
            )
            
            # Handle measurement and ROI label visibility based on state
            if new_state == 2:
                # State 2: Hide all text including measurements and ROI labels
                if self.hide_measurement_labels:
                    self.hide_measurement_labels(True)
                if self.hide_measurement_graphics:
                    self.hide_measurement_graphics(True)
                if self.hide_roi_graphics:
                    self.hide_roi_graphics(True)
                if self.hide_roi_statistics_overlays:
                    self.hide_roi_statistics_overlays(True)
            else:
                # State 0 or 1: Show measurements and ROI labels
                if self.hide_measurement_labels:
                    self.hide_measurement_labels(False)
                if self.hide_measurement_graphics:
                    self.hide_measurement_graphics(False)
                if self.hide_roi_graphics:
                    self.hide_roi_graphics(False)
                if self.hide_roi_statistics_overlays:
                    self.hide_roi_statistics_overlays(False)
            
            # Force scene update to refresh immediately
            self.image_viewer.scene.update()
    
    def hide_roi_labels(self, hide: bool) -> None:
        """
        Hide or show ROI labels.
        
        Note: ROIs don't have labels by default, so this is a no-op for now.
        This method exists for future extensibility if ROI labels are added.
        
        Args:
            hide: True to hide labels, False to show them
        """
        # ROIs don't have text labels, so nothing to hide
        pass
    
    def hide_roi_graphics(self, hide: bool) -> None:
        """
        Hide or show ROI graphics (shapes).
        
        Args:
            hide: True to hide graphics, False to show them
        """
        if self.image_viewer.scene is None:
            return
        
        for item in self.image_viewer.scene.items():
            if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
                # Don't hide the image item
                if item != self.image_viewer.image_item:
                    item.setVisible(not hide)

