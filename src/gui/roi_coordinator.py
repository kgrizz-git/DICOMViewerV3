"""
ROI Coordinator

This module coordinates ROI operations between the ROI manager and UI components.

Inputs:
    - ROI drawing events
    - ROI selection events
    - ROI deletion events
    
Outputs:
    - ROI operations coordinated with UI
    - Statistics updates
    - List panel updates
    
Requirements:
    - ROIManager for ROI management
    - ROIListPanel for list display
    - ROIStatisticsPanel for statistics display
    - ImageViewer for scene operations
    - DICOMProcessor for pixel array operations
"""

from PySide6.QtCore import QPointF
from typing import Optional, Callable
from pydicom.dataset import Dataset
from tools.roi_manager import ROIManager
from gui.roi_list_panel import ROIListPanel
from gui.roi_statistics_panel import ROIStatisticsPanel
from gui.image_viewer import ImageViewer
from core.dicom_processor import DICOMProcessor
from gui.window_level_controls import WindowLevelControls
from gui.main_window import MainWindow
from utils.dicom_utils import get_pixel_spacing


class ROICoordinator:
    """
    Coordinates ROI operations between manager and UI components.
    
    Responsibilities:
    - Handle ROI drawing events
    - Handle ROI selection events
    - Handle ROI deletion events
    - Update statistics panel
    - Update list panel
    - Handle auto window/level from ROI
    """
    
    def __init__(
        self,
        roi_manager: ROIManager,
        roi_list_panel: ROIListPanel,
        roi_statistics_panel: ROIStatisticsPanel,
        image_viewer: ImageViewer,
        dicom_processor: DICOMProcessor,
        window_level_controls: WindowLevelControls,
        main_window: MainWindow,
        get_current_dataset: Callable[[], Optional[Dataset]],
        get_current_slice_index: Callable[[], int],
        get_rescale_params: Callable[[], tuple[Optional[float], Optional[float], Optional[str], bool]],
        set_mouse_mode_callback: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize the ROI coordinator.
        
        Args:
            roi_manager: ROI manager instance
            roi_list_panel: ROI list panel widget
            roi_statistics_panel: ROI statistics panel widget
            image_viewer: Image viewer widget
            dicom_processor: DICOM processor for pixel operations
            window_level_controls: Window/level controls widget
            main_window: Main window for UI updates
            get_current_dataset: Callback to get current dataset
            get_current_slice_index: Callback to get current slice index
            get_rescale_params: Callback to get rescale parameters (slope, intercept, type, use_rescaled)
            set_mouse_mode_callback: Optional callback to set mouse mode
        """
        self.roi_manager = roi_manager
        self.roi_list_panel = roi_list_panel
        self.roi_statistics_panel = roi_statistics_panel
        self.image_viewer = image_viewer
        self.dicom_processor = dicom_processor
        self.window_level_controls = window_level_controls
        self.main_window = main_window
        self.get_current_dataset = get_current_dataset
        self.get_current_slice_index = get_current_slice_index
        self.get_rescale_params = get_rescale_params
        self.set_mouse_mode_callback = set_mouse_mode_callback
    
    def handle_roi_drawing_started(self, pos: QPointF) -> None:
        """
        Handle ROI drawing start.
        
        Args:
            pos: Starting position
        """
        current_dataset = self.get_current_dataset()
        if current_dataset is None:
            return
        
        # Extract DICOM identifiers
        study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
        series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
        # Try to get InstanceNumber from DICOM, fall back to slice_index
        instance_number = getattr(current_dataset, 'InstanceNumber', None)
        if instance_number is None:
            instance_identifier = self.get_current_slice_index()
        else:
            instance_identifier = int(instance_number)
        
        self.roi_manager.set_current_slice(study_uid, series_uid, instance_identifier)
        self.roi_manager.start_drawing(pos, self.image_viewer.roi_drawing_mode)
    
    def handle_roi_drawing_updated(self, pos: QPointF) -> None:
        """
        Handle ROI drawing update.
        
        Args:
            pos: Current position
        """
        self.roi_manager.update_drawing(pos, self.image_viewer.scene)
    
    def handle_roi_drawing_finished(self) -> None:
        """Handle ROI drawing finish."""
        roi_item = self.roi_manager.finish_drawing()
        
        # Extract DICOM identifiers for updating ROI list
        current_dataset = self.get_current_dataset()
        study_uid = ""
        series_uid = ""
        instance_identifier = self.get_current_slice_index()
        if current_dataset is not None:
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
            instance_number = getattr(current_dataset, 'InstanceNumber', None)
            if instance_number is not None:
                instance_identifier = int(instance_number)
        
        # Check if we're in auto_window_level mode
        if self.image_viewer.mouse_mode == "auto_window_level" and roi_item is not None:
            # Auto window/level mode - calculate window/level from ROI and delete ROI
            try:
                # roi_item is already the ROIItem we need (finish_drawing returns ROIItem directly)
                roi = roi_item
                if roi is not None and current_dataset is not None:
                    # Get pixel array
                    pixel_array = self.dicom_processor.get_pixel_array(current_dataset)
                    if pixel_array is not None:
                        # Extract pixel spacing for area calculation
                        pixel_spacing = get_pixel_spacing(current_dataset)
                        
                        # Get rescale parameters
                        rescale_slope, rescale_intercept, rescale_type, use_rescaled = self.get_rescale_params()
                        
                        # Calculate statistics with rescale parameters if using rescaled values
                        stats = self.roi_manager.calculate_statistics(
                            roi, pixel_array,
                            rescale_slope=rescale_slope if use_rescaled else None,
                            rescale_intercept=rescale_intercept if use_rescaled else None,
                            pixel_spacing=pixel_spacing
                        )
                        if stats and "min" in stats and "max" in stats:
                            # Set window width = max - min
                            window_width = stats["max"] - stats["min"]
                            # Set window center = midpoint (halfway between min and max)
                            window_center = (stats["min"] + stats["max"]) / 2.0
                            
                            # Update window/level controls
                            self.window_level_controls.set_window_level(window_center, window_width)
                            
                            # Delete the ROI (it was only used for calculation)
                            self.roi_manager.delete_roi(roi, self.image_viewer.scene)
                            
                            # Clear statistics panel since ROI was deleted
                            self.roi_statistics_panel.clear_statistics()
                            
                            # Update ROI list panel
                            self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
                            
                            # Switch back to pan mode
                            if self.set_mouse_mode_callback:
                                self.set_mouse_mode_callback("pan")
                            else:
                                self.image_viewer.set_mouse_mode("pan")
                                # Update toolbar button state
                                self.main_window.mouse_mode_pan_action.setChecked(True)
                                self.main_window.mouse_mode_auto_window_level_action.setChecked(False)
            except Exception as e:
                print(f"Error in auto window/level: {e}")
                import traceback
                traceback.print_exc()
                # If error occurs, still delete ROI and switch back to pan mode
                if roi_item is not None:
                    # roi_item is already the ROIItem we need
                    self.roi_manager.delete_roi(roi_item, self.image_viewer.scene)
                    # Clear statistics panel since ROI was deleted
                    self.roi_statistics_panel.clear_statistics()
                    self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
                if self.set_mouse_mode_callback:
                    self.set_mouse_mode_callback("pan")
                else:
                    self.image_viewer.set_mouse_mode("pan")
                    self.main_window.mouse_mode_pan_action.setChecked(True)
                    self.main_window.mouse_mode_auto_window_level_action.setChecked(False)
            return
        
        # Normal ROI drawing finish (not auto window/level)
        # Update ROI list
        self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
        
        # Auto-select the newly drawn ROI: highlight in list and show statistics
        if roi_item is not None:
            self.roi_list_panel.select_roi_in_list(roi_item)
            if current_dataset is not None:
                self.update_roi_statistics(roi_item)
    
    def handle_roi_clicked(self, item) -> None:
        """
        Handle ROI click.
        
        Args:
            item: QGraphicsItem that was clicked
        """
        roi = self.roi_manager.find_roi_by_item(item)
        if roi:
            self.roi_manager.select_roi(roi)
            self.roi_list_panel.select_roi_in_list(roi)
            self.update_roi_statistics(roi)
    
    def handle_image_clicked_no_roi(self) -> None:
        """Handle image click when not on an ROI - deselect current ROI."""
        # Deselect ROI
        self.roi_manager.select_roi(None)
        # Clear scene selection to prevent Qt's default mouse release behavior from re-selecting the ROI
        if self.image_viewer.scene is not None:
            self.image_viewer.scene.clearSelection()
        # Clear ROI list selection
        self.roi_list_panel.select_roi_in_list(None)
        # Clear ROI statistics panel
        self.roi_statistics_panel.clear_statistics()
    
    def handle_roi_selected(self, roi) -> None:
        """
        Handle ROI selection from list.
        
        Args:
            roi: Selected ROI item
        """
        self.update_roi_statistics(roi)
    
    def handle_roi_delete_requested(self, item) -> None:
        """
        Handle ROI deletion request from context menu.
        
        Args:
            item: QGraphicsItem to delete
        """
        roi = self.roi_manager.find_roi_by_item(item)
        if roi:
            self.roi_manager.delete_roi(roi, self.image_viewer.scene)
            # Update ROI list panel - extract identifiers from current dataset
            current_dataset = self.get_current_dataset()
            if current_dataset is not None:
                study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
                series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
                instance_number = getattr(current_dataset, 'InstanceNumber', None)
                if instance_number is None:
                    instance_identifier = self.get_current_slice_index()
                else:
                    instance_identifier = int(instance_number)
                self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
            if self.roi_manager.get_selected_roi() is None:
                self.roi_statistics_panel.clear_statistics()
    
    def handle_roi_deleted(self, roi) -> None:
        """
        Handle ROI deletion.
        
        Args:
            roi: Deleted ROI item
        """
        # Clear statistics if this was the selected ROI
        if self.roi_manager.get_selected_roi() is None:
            self.roi_statistics_panel.clear_statistics()
    
    def delete_all_rois_current_slice(self) -> None:
        """
        Delete all ROIs on the current slice.
        
        Called by D key keyboard shortcut and Delete All button in ROI list panel.
        """
        current_dataset = self.get_current_dataset()
        if current_dataset is None:
            return
        
        # Get current slice identifiers
        study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
        series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
        
        if not study_uid or not series_uid:
            return
        
        # Get current instance identifier (must match how ROIs are stored)
        # Try to get InstanceNumber from DICOM, fall back to slice_index
        instance_number = getattr(current_dataset, 'InstanceNumber', None)
        if instance_number is None:
            instance_identifier = self.get_current_slice_index()
        else:
            instance_identifier = int(instance_number)
        
        # Clear all ROIs for this slice
        self.roi_manager.clear_slice_rois(study_uid, series_uid, instance_identifier, self.image_viewer.scene)
        
        # Update ROI list panel
        self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
        
        # Clear ROI statistics panel
        self.roi_statistics_panel.clear_statistics()
    
    def update_roi_statistics(self, roi) -> None:
        """
        Update statistics panel for a ROI.
        
        Args:
            roi: ROI item
        """
        if roi is None:
            return
        
        current_dataset = self.get_current_dataset()
        if current_dataset is None:
            return
        
        try:
            # Extract DICOM identifiers
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
            instance_number = getattr(current_dataset, 'InstanceNumber', None)
            if instance_number is None:
                instance_identifier = self.get_current_slice_index()
            else:
                instance_identifier = int(instance_number)
            
            # Get ROI identifier (e.g., "ROI 1 (rectangle)")
            roi_identifier = None
            rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
            for i, r in enumerate(rois):
                if r == roi:
                    roi_identifier = f"ROI {i+1} ({roi.shape_type})"
                    break
            
            pixel_array = self.dicom_processor.get_pixel_array(current_dataset)
            if pixel_array is not None:
                # Extract pixel spacing for area calculation
                pixel_spacing = get_pixel_spacing(current_dataset)
                
                # Get rescale parameters
                rescale_slope, rescale_intercept, rescale_type, use_rescaled = self.get_rescale_params()
                
                # Pass rescale parameters if using rescaled values
                stats = self.roi_manager.calculate_statistics(
                    roi, pixel_array, 
                    rescale_slope=rescale_slope if use_rescaled else None,
                    rescale_intercept=rescale_intercept if use_rescaled else None,
                    pixel_spacing=pixel_spacing
                )
                # Pass rescale_type for display
                display_rescale_type = rescale_type if use_rescaled else None
                self.roi_statistics_panel.update_statistics(stats, roi_identifier, rescale_type=display_rescale_type)
        except Exception as e:
            print(f"Error calculating ROI statistics: {e}")
    
    def handle_scene_selection_changed(self) -> None:
        """Handle scene selection change (e.g., when ROI is moved)."""
        try:
            # Check if scene is still valid
            if self.image_viewer.scene is None:
                return
            selected_items = self.image_viewer.scene.selectedItems()
            if selected_items:
                # Find ROI for selected item
                for item in selected_items:
                    roi = self.roi_manager.find_roi_by_item(item)
                    if roi:
                        # Update statistics when ROI is moved/selected
                        self.update_roi_statistics(roi)
                        # Update list panel selection
                        self.roi_list_panel.select_roi_in_list(roi)
                        break
        except RuntimeError:
            # Scene has been deleted or is invalid, ignore
            return
    
    def hide_roi_graphics(self, hide: bool) -> None:
        """
        Hide or show ROI graphics (shapes).
        
        Args:
            hide: True to hide graphics, False to show them
        """
        if self.image_viewer.scene is None:
            return
        
        from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsEllipseItem
        for item in self.image_viewer.scene.items():
            if isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
                # Don't hide the image item
                if item != self.image_viewer.image_item:
                    item.setVisible(not hide)

