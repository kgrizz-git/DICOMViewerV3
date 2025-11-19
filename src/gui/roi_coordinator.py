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
import numpy as np
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
        set_mouse_mode_callback: Optional[Callable[[str], None]] = None,
        get_projection_enabled: Optional[Callable[[], bool]] = None,
        get_projection_type: Optional[Callable[[], str]] = None,
        get_projection_slice_count: Optional[Callable[[], int]] = None,
        get_current_studies: Optional[Callable[[], dict]] = None
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
            get_projection_enabled: Optional callback to get projection enabled state
            get_projection_type: Optional callback to get projection type ("aip", "mip", or "minip")
            get_projection_slice_count: Optional callback to get projection slice count (2, 3, 4, 6, or 8)
            get_current_studies: Optional callback to get current_studies dictionary
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
        self.get_projection_enabled = get_projection_enabled
        self.get_projection_type = get_projection_type
        self.get_projection_slice_count = get_projection_slice_count
        self.get_current_studies = get_current_studies
    
    def _get_pixel_array_for_statistics(self) -> Optional[np.ndarray]:
        """
        Get pixel array for ROI statistics calculation.
        
        If projection is enabled, returns the projection array.
        Otherwise, returns the original slice's pixel array.
        
        Returns:
            NumPy array (projection or original), or None if unavailable
        """
        current_dataset = self.get_current_dataset()
        if current_dataset is None:
            return None
        
        # Check if projection is enabled
        if (self.get_projection_enabled is None or 
            not self.get_projection_enabled()):
            # Projection not enabled, return original slice array
            return self.dicom_processor.get_pixel_array(current_dataset)
        
        # Projection is enabled, create projection array
        try:
            # Get projection parameters
            projection_type = "aip"  # default
            if self.get_projection_type is not None:
                projection_type = self.get_projection_type()
            
            projection_slice_count = 4  # default
            if self.get_projection_slice_count is not None:
                projection_slice_count = self.get_projection_slice_count()
            
            # Get current studies dictionary
            if self.get_current_studies is None:
                # Fall back to original if we can't get studies
                return self.dicom_processor.get_pixel_array(current_dataset)
            
            current_studies = self.get_current_studies()
            if not current_studies:
                # Fall back to original if studies is empty
                return self.dicom_processor.get_pixel_array(current_dataset)
            
            # Extract DICOM identifiers
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
            current_slice_index = self.get_current_slice_index()
            
            # Get series datasets
            if (not study_uid or not series_uid or 
                study_uid not in current_studies or 
                series_uid not in current_studies[study_uid]):
                # Fall back to original if series not found
                return self.dicom_processor.get_pixel_array(current_dataset)
            
            series_datasets = current_studies[study_uid][series_uid]
            total_slices = len(series_datasets)
            
            if total_slices < 2:
                # Not enough slices for projection, fall back to original
                return self.dicom_processor.get_pixel_array(current_dataset)
            
            # Calculate slice range
            start_slice = max(0, current_slice_index)
            end_slice = min(total_slices - 1, current_slice_index + projection_slice_count - 1)
            
            # Ensure we have at least 2 slices
            if end_slice - start_slice + 1 < 2:
                # Not enough slices available, fall back to original
                return self.dicom_processor.get_pixel_array(current_dataset)
            
            # Gather slices for projection
            projection_slices = []
            for i in range(start_slice, end_slice + 1):
                if 0 <= i < total_slices:
                    projection_slices.append(series_datasets[i])
            
            if len(projection_slices) < 2:
                # Not enough slices gathered, fall back to original
                return self.dicom_processor.get_pixel_array(current_dataset)
            
            # Calculate projection based on type
            projection_array = None
            if projection_type == "aip":
                projection_array = self.dicom_processor.average_intensity_projection(projection_slices)
            elif projection_type == "mip":
                projection_array = self.dicom_processor.maximum_intensity_projection(projection_slices)
            elif projection_type == "minip":
                projection_array = self.dicom_processor.minimum_intensity_projection(projection_slices)
            
            if projection_array is None:
                # Projection calculation failed, fall back to original
                return self.dicom_processor.get_pixel_array(current_dataset)
            
            # Return projection array (rescale will be applied in calculate_statistics if needed)
            return projection_array
            
        except Exception:
            # Any error during projection, fall back to original
            return self.dicom_processor.get_pixel_array(current_dataset)
    
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
        # Use current slice index as instance identifier (array position)
        instance_identifier = self.get_current_slice_index()
        
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
        # Use current slice index as instance identifier (array position)
        instance_identifier = self.get_current_slice_index()
        if current_dataset is not None:
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
        
        # Check if we're in auto_window_level mode
        if self.image_viewer.mouse_mode == "auto_window_level" and roi_item is not None:
            # Auto window/level mode - calculate window/level from ROI and delete ROI
            try:
                # roi_item is already the ROIItem we need (finish_drawing returns ROIItem directly)
                roi = roi_item
                if roi is not None and current_dataset is not None:
                    # Get pixel array (projection if enabled, otherwise original)
                    pixel_array = self._get_pixel_array_for_statistics()
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
            # Set up movement callback for the newly created ROI
            roi_item.on_moved_callback = lambda r=roi_item: self._on_roi_moved(r)
            
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
            # Explicitly handle deletion to ensure overlay is removed
            self.handle_roi_deleted(roi)
            # Update ROI list panel - extract identifiers from current dataset
            current_dataset = self.get_current_dataset()
            if current_dataset is not None:
                study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
                series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
                # Use current slice index as instance identifier (array position)
                instance_identifier = self.get_current_slice_index()
                self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
            if self.roi_manager.get_selected_roi() is None:
                self.roi_statistics_panel.clear_statistics()
    
    def handle_roi_deleted(self, roi) -> None:
        """
        Handle ROI deletion.
        
        Args:
            roi: Deleted ROI item
        """
        # print(f"[DEBUG-ROI] handle_roi_deleted called for ROI {id(roi)}")
        # Explicitly remove statistics overlay from scene
        if self.image_viewer.scene is not None:
            # Check if ROI still has overlay before trying to remove
            if hasattr(roi, 'statistics_overlay_item') and roi.statistics_overlay_item is not None:
                # print(f"[DEBUG-ROI] Removing overlay from deleted ROI")
                self.roi_manager.remove_statistics_overlay(roi, self.image_viewer.scene)
        
        # Mark overlay visibility false to prevent recreation via stale callbacks
        if hasattr(roi, "statistics_overlay_visible"):
            roi.statistics_overlay_visible = False
        if hasattr(roi, "statistics"):
            roi.statistics = None
        
        # Update ROI statistics overlays to refresh display only if other ROIs remain
        current_dataset = self.get_current_dataset()
        if current_dataset is not None:
            study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
            series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
            instance_identifier = self.get_current_slice_index()
            remaining_rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
            if remaining_rois:
                # print(f"[DEBUG-ROI] Rebuilding overlays for {len(remaining_rois)} remaining ROIs")
                self.update_roi_statistics_overlays()
        
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
        
        # Use current slice index as instance identifier (array position)
        instance_identifier = self.get_current_slice_index()
        
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
            # Use current slice index as instance identifier (array position)
            instance_identifier = self.get_current_slice_index()
            
            # Get ROI identifier (e.g., "ROI 1 (rectangle)")
            roi_identifier = None
            rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
            for i, r in enumerate(rois):
                if r == roi:
                    roi_identifier = f"ROI {i+1} ({roi.shape_type})"
                    break
            
            pixel_array = self._get_pixel_array_for_statistics()
            if pixel_array is not None:
                # Extract pixel spacing for area calculation
                pixel_spacing = get_pixel_spacing(current_dataset)
                
                # Get rescale parameters
                rescale_slope, rescale_intercept, rescale_type, use_rescaled = self.get_rescale_params()
                
                # Pass rescale parameters if using rescaled values
                # Note: For projections, rescale is not applied in helper, so we pass params here
                stats = self.roi_manager.calculate_statistics(
                    roi, pixel_array, 
                    rescale_slope=rescale_slope if use_rescaled else None,
                    rescale_intercept=rescale_intercept if use_rescaled else None,
                    pixel_spacing=pixel_spacing
                )
                # Pass rescale_type for display
                display_rescale_type = rescale_type if use_rescaled else None
                self.roi_statistics_panel.update_statistics(stats, roi_identifier, rescale_type=display_rescale_type)
                
                # Update statistics overlay on image
                if self.image_viewer.scene is not None and roi.statistics_overlay_visible:
                    # Font size and color will be retrieved from config in create_statistics_overlay
                    self.roi_manager.update_statistics_overlay(
                        roi, stats, self.image_viewer.scene,
                        font_size=None, font_color=None,  # None = use config values
                        rescale_type=display_rescale_type
                    )
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
            else:
                # No selection - update overlay positions for all ROIs that might have moved
                # This handles the case where ROI is moved but then deselected
                current_dataset = self.get_current_dataset()
                if current_dataset is not None:
                    study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
                    series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
                    instance_identifier = self.get_current_slice_index()
                    rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
                    for roi in rois:
                        if roi.statistics_overlay_item is not None and roi.statistics_overlay_visible:
                            self.roi_manager.update_statistics_overlay_position(roi, self.image_viewer.scene)
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
    
    def update_roi_statistics_overlays(self) -> None:
        """
        Create/update statistics overlays for all ROIs on current slice.
        """
        if self.image_viewer.scene is None:
            return
        
        current_dataset = self.get_current_dataset()
        if current_dataset is None:
            return
        
        # Extract DICOM identifiers
        study_uid = getattr(current_dataset, 'StudyInstanceUID', '')
        series_uid = getattr(current_dataset, 'SeriesInstanceUID', '')
        instance_identifier = self.get_current_slice_index()
        
        # Get all ROIs for current slice
        rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
        
        # Get pixel array (projection if enabled, otherwise original)
        pixel_array = self._get_pixel_array_for_statistics()
        if pixel_array is None:
            return
        
        # Extract pixel spacing and rescale parameters
        pixel_spacing = get_pixel_spacing(current_dataset)
        rescale_slope, rescale_intercept, rescale_type, use_rescaled = self.get_rescale_params()
        display_rescale_type = rescale_type if use_rescaled else None
        
        # Remove all statistics overlays from scene before creating new ones
        # This ensures orphaned overlays from previous slices are removed
        self.roi_manager.remove_all_statistics_overlays_from_scene(self.image_viewer.scene)
        
        # Font size and color will be retrieved from config in create_statistics_overlay
        
        # Create/update overlays for each ROI
        for roi in rois:
            # Set up movement callback for ROI if not already set
            if roi.on_moved_callback is None:
                roi.on_moved_callback = lambda r=roi: self._on_roi_moved(r)
            
            # Always recalculate statistics to ensure overlays reflect latest ROI position
            stats = self.roi_manager.calculate_statistics(
                roi,
                pixel_array,
                rescale_slope=rescale_slope if use_rescaled else None,
                rescale_intercept=rescale_intercept if use_rescaled else None,
                pixel_spacing=pixel_spacing
            )
            
            if stats and roi.statistics_overlay_visible:
                self.roi_manager.create_statistics_overlay(
                    roi,
                    stats,
                    self.image_viewer.scene,
                    font_size=None,
                    font_color=None,  # None = use config values
                    rescale_type=display_rescale_type
                )
    
    def handle_roi_statistics_overlay_toggle(self, roi, visible: bool) -> None:
        """
        Toggle statistics overlay visibility for a specific ROI.
        
        Args:
            roi: ROI item
            visible: True to show overlay, False to hide
        """
        roi.statistics_overlay_visible = visible
        
        if self.image_viewer.scene is None:
            return
        
        if visible:
            # Recalculate statistics and recreate overlay so it reflects latest ROI position
            self.update_roi_statistics(roi)
        else:
            # Hide overlay
            self.roi_manager.remove_statistics_overlay(roi, self.image_viewer.scene)
    
    def handle_roi_statistics_selection(self, roi, statistics_to_show: set) -> None:
        """
        Change which statistics are displayed for an ROI.
        
        Args:
            roi: ROI item
            statistics_to_show: Set of statistic names to show (e.g., {"mean", "std", "min"})
        """
        roi.visible_statistics = statistics_to_show
        
        # Update overlay if it exists and is visible
        if roi.statistics_overlay_visible:
            self.update_roi_statistics(roi)
    
    def hide_roi_statistics_overlays(self, hide: bool) -> None:
        """
        Hide or show all ROI statistics overlays.
        
        Args:
            hide: True to hide overlays, False to show them
        """
        if self.image_viewer.scene is None:
            return
        
        self.roi_manager.hide_all_statistics_overlays(self.image_viewer.scene, hide)
    
    def _on_roi_moved(self, roi) -> None:
        """
        Handle ROI movement - recalculate statistics and update overlays.
        
        Args:
            roi: ROI item that was moved
        """
        # print(f"[DEBUG-ROI] _on_roi_moved called for ROI {id(roi)}")
        try:
            # Check if ROI is still valid
            if roi is None or not hasattr(roi, 'item') or roi.item is None:
                # print(f"[DEBUG-ROI] ROI is invalid, skipping movement handling")
                return
            
            # Recalculate statistics for the moved ROI
            # print(f"[DEBUG-ROI] Recalculating statistics for moved ROI")
            self.update_roi_statistics(roi)
            
            # Update overlay position
            if hasattr(roi, 'statistics_overlay_item') and roi.statistics_overlay_item is not None:
                if hasattr(roi, 'statistics_overlay_visible') and roi.statistics_overlay_visible:
                    if self.image_viewer.scene is not None:
                        # print(f"[DEBUG-ROI] Updating overlay position for moved ROI")
                        self.roi_manager.update_statistics_overlay_position(roi, self.image_viewer.scene)
            
            # Update ROI statistics panel if this ROI is selected
            if self.roi_manager.get_selected_roi() == roi:
                # Statistics panel will be updated by update_roi_statistics
                # print(f"[DEBUG-ROI] ROI is selected, statistics panel updated")
                pass
        except Exception as e:
            # print(f"[DEBUG-ROI] Error in _on_roi_moved: {e}")
            import traceback
            traceback.print_exc()

