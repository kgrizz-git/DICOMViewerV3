"""
Slice Display Manager

This module handles slice display, ROI/measurement display, and series navigation.

Inputs:
    - DICOM datasets
    - Slice index changes
    - Series navigation requests
    
Outputs:
    - Displayed slices
    - ROIs and measurements for current slice
    - Series navigation
    
Requirements:
    - DICOMProcessor for image processing
    - DICOMParser for metadata parsing
    - ImageViewer for display
    - ROIManager for ROI operations
    - MeasurementTool for measurements
    - OverlayManager for overlays
    - ViewStateManager for view state coordination
"""

from typing import Optional, Callable
from pydicom.dataset import Dataset
from core.dicom_processor import DICOMProcessor
from core.dicom_parser import DICOMParser
from gui.image_viewer import ImageViewer
from gui.metadata_panel import MetadataPanel
from gui.slice_navigator import SliceNavigator
from gui.window_level_controls import WindowLevelControls
from tools.roi_manager import ROIManager
from tools.measurement_tool import MeasurementTool
from gui.overlay_manager import OverlayManager
from gui.roi_list_panel import ROIListPanel
from gui.roi_statistics_panel import ROIStatisticsPanel
from utils.dicom_utils import get_pixel_spacing


class SliceDisplayManager:
    """
    Manages slice display, ROI/measurement display, and series navigation.
    
    Responsibilities:
    - Display DICOM slices
    - Display ROIs for current slice
    - Display measurements for current slice
    - Handle slice navigation
    - Handle series navigation
    """
    
    def __init__(
        self,
        dicom_processor: DICOMProcessor,
        image_viewer: ImageViewer,
        metadata_panel: MetadataPanel,
        slice_navigator: SliceNavigator,
        window_level_controls: WindowLevelControls,
        roi_manager: ROIManager,
        measurement_tool: MeasurementTool,
        overlay_manager: OverlayManager,
        view_state_manager,
        update_tag_viewer_callback: Optional[Callable] = None,
        display_rois_callback: Optional[Callable] = None,
        display_measurements_callback: Optional[Callable] = None,
        roi_list_panel: Optional[ROIListPanel] = None,
        roi_statistics_panel: Optional[ROIStatisticsPanel] = None
    ):
        """
        Initialize the slice display manager.
        
        Args:
            dicom_processor: DICOM processor for image operations
            image_viewer: Image viewer widget
            metadata_panel: Metadata panel widget
            slice_navigator: Slice navigator widget
            window_level_controls: Window/level controls widget
            roi_manager: ROI manager
            measurement_tool: Measurement tool
            overlay_manager: Overlay manager
            view_state_manager: View state manager for coordination
            update_tag_viewer_callback: Optional callback to update tag viewer
            display_rois_callback: Optional callback to display ROIs
            display_measurements_callback: Optional callback to display measurements
            roi_list_panel: Optional ROI list panel for updating ROI list
            roi_statistics_panel: Optional ROI statistics panel for updating statistics
        """
        self.dicom_processor = dicom_processor
        self.image_viewer = image_viewer
        self.metadata_panel = metadata_panel
        self.slice_navigator = slice_navigator
        self.window_level_controls = window_level_controls
        self.roi_manager = roi_manager
        self.measurement_tool = measurement_tool
        self.overlay_manager = overlay_manager
        self.view_state_manager = view_state_manager
        self.update_tag_viewer_callback = update_tag_viewer_callback
        self.display_rois_callback = display_rois_callback
        self.display_measurements_callback = display_measurements_callback
        self.roi_list_panel = roi_list_panel
        self.roi_statistics_panel = roi_statistics_panel
        
        # Current data context
        self.current_studies: dict = {}
        self.current_study_uid: str = ""
        self.current_series_uid: str = ""
        self.current_slice_index: int = 0
        self.current_dataset: Optional[Dataset] = None
    
    def display_slice(
        self,
        dataset: Dataset,
        current_studies: dict,
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int
    ) -> None:
        """
        Display a DICOM slice.
        
        Args:
            dataset: pydicom Dataset
            current_studies: Dictionary of studies
            current_study_uid: Current study UID
            current_series_uid: Current series UID
            current_slice_index: Current slice index
        """
        try:
            # Update current context
            self.current_studies = current_studies
            self.current_study_uid = current_study_uid
            self.current_series_uid = current_series_uid
            self.current_slice_index = current_slice_index
            self.current_dataset = dataset
            
            # Update view state manager context
            self.view_state_manager.set_current_data_context(
                dataset, current_studies, current_study_uid, current_series_uid, current_slice_index
            )
            
            # Extract and store rescale parameters from dataset
            rescale_slope, rescale_intercept, rescale_type = self.dicom_processor.get_rescale_parameters(dataset)
            self.view_state_manager.set_rescale_parameters(rescale_slope, rescale_intercept, rescale_type)
            
            # Get series UID from dataset to check if we're in the same series
            new_series_uid = getattr(dataset, 'SeriesInstanceUID', '')
            is_same_series = (new_series_uid == current_series_uid and current_series_uid != "")
            
            # Detect if this is a new study/series
            is_new_study_series = self.view_state_manager.is_new_study_or_series(dataset)
            series_identifier = self.view_state_manager.get_series_identifier(dataset)
            
            # Set default use_rescaled_values based on whether parameters exist
            # Default to True if parameters exist, False otherwise
            if is_new_study_series:
                use_rescaled = (rescale_slope is not None and rescale_intercept is not None)
                self.view_state_manager.use_rescaled_values = use_rescaled
                # Update UI toggle state
                from gui.main_window import MainWindow
                if hasattr(self.view_state_manager, 'main_window'):
                    self.view_state_manager.main_window.set_rescale_toggle_state(use_rescaled)
                self.image_viewer.set_rescale_toggle_state(use_rescaled)
                # Update current series identifier
                self.view_state_manager.set_current_series_identifier(series_identifier)
            
            # Get window/level values from view state manager
            window_center = self.view_state_manager.current_window_center
            window_width = self.view_state_manager.current_window_width
            use_rescaled_values = self.view_state_manager.use_rescaled_values
            
            # For new series, calculate or restore window/level defaults
            if is_new_study_series:
                # Check if we have stored defaults for this series
                stored_window_center = None
                stored_window_width = None
                if series_identifier in self.view_state_manager.series_defaults:
                    defaults = self.view_state_manager.series_defaults[series_identifier]
                    if 'window_center' in defaults and defaults.get('window_center') is not None:
                        stored_window_center = defaults.get('window_center')
                        stored_window_width = defaults.get('window_width')
                        self.view_state_manager.window_level_user_modified = False
                
                if stored_window_center is None or stored_window_width is None:
                    # Calculate window/level from series or dataset
                    study_uid = getattr(dataset, 'StudyInstanceUID', '')
                    if study_uid and new_series_uid and current_studies:
                        if study_uid in current_studies and new_series_uid in current_studies[study_uid]:
                            series_datasets = current_studies[study_uid][new_series_uid]
                            # Calculate pixel range for entire series
                            series_pixel_min, series_pixel_max = self.dicom_processor.get_series_pixel_value_range(
                                series_datasets, apply_rescale=use_rescaled_values
                            )
                            # Check for window/level in DICOM metadata
                            wc, ww, is_rescaled = self.dicom_processor.get_window_level_from_dataset(
                                dataset,
                                rescale_slope=rescale_slope,
                                rescale_intercept=rescale_intercept
                            )
                            if wc is not None and ww is not None:
                                # Convert if needed
                                if is_rescaled and not use_rescaled_values:
                                    if (rescale_slope is not None and rescale_intercept is not None and rescale_slope != 0.0):
                                        wc, ww = self.dicom_processor.convert_window_level_rescaled_to_raw(
                                            wc, ww, rescale_slope, rescale_intercept
                                        )
                                elif not is_rescaled and use_rescaled_values:
                                    if (rescale_slope is not None and rescale_intercept is not None):
                                        wc, ww = self.dicom_processor.convert_window_level_raw_to_rescaled(
                                            wc, ww, rescale_slope, rescale_intercept
                                        )
                                stored_window_center = wc
                                stored_window_width = ww
                            elif series_pixel_min is not None and series_pixel_max is not None:
                                stored_window_center = (series_pixel_min + series_pixel_max) / 2.0
                                stored_window_width = series_pixel_max - series_pixel_min
                                if stored_window_width <= 0:
                                    stored_window_width = 1.0
                            else:
                                # Fallback to single slice
                                pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                                    dataset, apply_rescale=use_rescaled_values
                                )
                                if pixel_min is not None and pixel_max is not None:
                                    stored_window_center = (pixel_min + pixel_max) / 2.0
                                    stored_window_width = pixel_max - pixel_min
                                    if stored_window_width <= 0:
                                        stored_window_width = 1.0
                            self.view_state_manager.window_level_user_modified = False
                
                # Set window/level values
                if stored_window_center is not None and stored_window_width is not None:
                    window_center = stored_window_center
                    window_width = stored_window_width
                    self.view_state_manager.current_window_center = window_center
                    self.view_state_manager.current_window_width = window_width
                    # Store defaults for this series (will be updated with zoom/pan after fit_to_view)
                    if series_identifier not in self.view_state_manager.series_defaults:
                        self.view_state_manager.series_defaults[series_identifier] = {}
                    self.view_state_manager.series_defaults[series_identifier].update({
                        'window_center': window_center,
                        'window_width': window_width,
                        'use_rescaled_values': use_rescaled_values
                    })
            
            # For same series, preserve existing window/level values (already set above)
            
            # Convert to image
            # If same series and we have preserved window/level values, use them
            if is_same_series and window_center is not None and window_width is not None:
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    window_center=window_center,
                    window_width=window_width,
                    apply_rescale=use_rescaled_values
                )
            else:
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    apply_rescale=use_rescaled_values
                )
            if image is None:
                return
            
            # Set image in viewer - preserve zoom/pan if same series
            self.image_viewer.set_image(image, preserve_view=is_same_series and not is_new_study_series)
            
            # If new study/series, fit to view and center
            if is_new_study_series:
                self.image_viewer.fit_to_view(center_image=True)
                # Store zoom and scroll positions after fit_to_view
                stored_zoom = self.image_viewer.current_zoom
                stored_h_scroll = self.image_viewer.horizontalScrollBar().value()
                stored_v_scroll = self.image_viewer.verticalScrollBar().value()
                # Update series defaults with zoom/pan info if we have window/level already stored
                if series_identifier in self.view_state_manager.series_defaults:
                    self.view_state_manager.series_defaults[series_identifier].update({
                        'zoom': stored_zoom,
                        'h_scroll': stored_h_scroll,
                        'v_scroll': stored_v_scroll
                    })
            
            # Update metadata panel
            self.metadata_panel.set_dataset(dataset)
            
            # Update tag viewer if open
            if self.update_tag_viewer_callback:
                self.update_tag_viewer_callback(dataset)
            
            # Calculate pixel value range for window/level controls
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                dataset, apply_rescale=use_rescaled_values
            )
            if pixel_min is not None and pixel_max is not None:
                # Set ranges based on actual pixel values (no margins)
                center_range = (pixel_min, pixel_max)
                # Width range from 1 to the pixel range (not 2x)
                width_range = (1.0, max(1.0, pixel_max - pixel_min))
                self.window_level_controls.set_ranges(center_range, width_range)
            
            # Update window/level controls unit label
            unit = rescale_type if (use_rescaled_values and rescale_type) else None
            self.window_level_controls.set_unit(unit)
            
            # Update window/level controls with current values
            if is_new_study_series and window_center is not None and window_width is not None:
                # New series - use calculated/stored defaults
                self.window_level_controls.set_window_level(
                    window_center, window_width, block_signals=True, unit=unit
                )
            elif is_same_series and window_center is not None and window_width is not None:
                # Same series - preserve existing window/level values
                self.window_level_controls.set_window_level(
                    window_center, window_width, block_signals=True, unit=unit
                )
            else:
                # First time or no existing values - try to get from dataset or use defaults
                wc, ww, is_rescaled = self.dicom_processor.get_window_level_from_dataset(
                    dataset,
                    rescale_slope=rescale_slope,
                    rescale_intercept=rescale_intercept
                )
                if wc is not None and ww is not None:
                    # Convert if needed
                    if is_rescaled and not use_rescaled_values:
                        if (rescale_slope is not None and rescale_intercept is not None and rescale_slope != 0.0):
                            wc, ww = self.dicom_processor.convert_window_level_rescaled_to_raw(
                                wc, ww, rescale_slope, rescale_intercept
                            )
                    elif not is_rescaled and use_rescaled_values:
                        if (rescale_slope is not None and rescale_intercept is not None):
                            wc, ww = self.dicom_processor.convert_window_level_raw_to_rescaled(
                                wc, ww, rescale_slope, rescale_intercept
                            )
                    self.window_level_controls.set_window_level(wc, ww, block_signals=True, unit=unit)
                    self.view_state_manager.current_window_center = wc
                    self.view_state_manager.current_window_width = ww
                elif pixel_min is not None and pixel_max is not None:
                    # Use default window/level based on pixel range
                    default_center = (pixel_min + pixel_max) / 2.0
                    default_width = pixel_max - pixel_min
                    if default_width <= 0:
                        default_width = 1.0
                    self.window_level_controls.set_window_level(default_center, default_width, block_signals=True, unit=unit)
                    self.view_state_manager.current_window_center = default_center
                    self.view_state_manager.current_window_width = default_width
                self.view_state_manager.window_level_user_modified = False
            
            # Update overlay
            parser = DICOMParser(dataset)
            # Get total slice count for current series
            total_slices = 0
            if current_studies and current_study_uid and current_series_uid:
                if (current_study_uid in current_studies and 
                    current_series_uid in current_studies[current_study_uid]):
                    total_slices = len(current_studies[current_study_uid][current_series_uid])
            self.overlay_manager.create_overlay_items(
                self.image_viewer.scene,
                parser,
                total_slices=total_slices if total_slices > 0 else None
            )
            
            # Extract pixel spacing and set on measurement tool
            pixel_spacing = get_pixel_spacing(dataset)
            self.measurement_tool.set_pixel_spacing(pixel_spacing)
            
            # Set current slice context for ROI manager and measurements
            study_uid = getattr(dataset, 'StudyInstanceUID', '')
            series_uid = getattr(dataset, 'SeriesInstanceUID', '')
            # Use current_slice_index as instance identifier (array position)
            instance_identifier = current_slice_index
            # Update ROI manager's current slice context
            self.roi_manager.set_current_slice(study_uid, series_uid, instance_identifier)
            self.measurement_tool.set_current_slice(study_uid, series_uid, instance_identifier)
            
            # Clear measurements when switching to new series (not when switching slices)
            if is_new_study_series:
                self.measurement_tool.clear_measurements(self.image_viewer.scene)
            
            # Display ROIs for current slice
            if self.display_rois_callback:
                self.display_rois_callback(dataset)
            else:
                self.display_rois_for_slice(dataset)
            
            # Display measurements for current slice
            if self.display_measurements_callback:
                self.display_measurements_callback(dataset)
            else:
                self.display_measurements_for_slice(dataset)
        
        except Exception as e:
            # Error handling will be done by caller
            raise
    
    def display_rois_for_slice(self, dataset: Dataset) -> None:
        """
        Display ROIs for a slice.
        
        Ensures all ROIs for the current slice are visible in the scene.
        
        Args:
            dataset: pydicom Dataset for the current slice
        """
        # Extract DICOM identifiers
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = getattr(dataset, 'SeriesInstanceUID', '')
        # Use current_slice_index as instance identifier (array position)
        instance_identifier = self.current_slice_index
        # print(f"[ROI DEBUG] display_rois_for_slice retrieving ROIs with instance_identifier={instance_identifier} (self.current_slice_index)")
        
        # Get all ROIs for this slice using composite key
        rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
        # print(f"[ROI DEBUG] Found {len(rois)} ROIs for slice {instance_identifier}")
        
        # Remove ROIs from other slices from the scene
        # (but keep them in the manager's storage)
        current_scene_items = list(self.image_viewer.scene.items())
        for item in current_scene_items:
            # Check if this item is an ROI
            roi = self.roi_manager.find_roi_by_item(item)
            if roi is not None:
                # Check if this ROI belongs to current slice
                roi_belongs_to_current = False
                for key, roi_list in self.roi_manager.rois.items():
                    if roi in roi_list:
                        # Check if this key matches current slice
                        if key == (study_uid, series_uid, instance_identifier):
                            roi_belongs_to_current = True
                        break
                # Remove ROI if it's from a different slice
                if not roi_belongs_to_current:
                    # Only remove if item actually belongs to this scene
                    if item.scene() == self.image_viewer.scene:
                        self.image_viewer.scene.removeItem(item)
        
        # Add ROIs for current slice to scene if not already there
        # Force refresh to ensure visibility after image changes
        for roi in rois:
            if roi.item.scene() == self.image_viewer.scene:
                # Already in scene, but ensure it's visible and has correct Z-value
                roi.item.setZValue(100)  # Above image but below overlay
                roi.item.show()  # Ensure visible
            else:
                # Not in scene, add it
                self.image_viewer.scene.addItem(roi.item)
                # Ensure ROI is visible (set appropriate Z-value)
                roi.item.setZValue(100)  # Above image but below overlay
        
        # Update ROI list panel to show only ROIs for current slice
        if self.roi_list_panel is not None:
            self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
        
        # Check selected ROI and update/clear statistics
        selected_roi = self.roi_manager.get_selected_roi()
        if selected_roi is not None and selected_roi in rois:
            # Selected ROI belongs to current slice - keep it selected and update list selection
            if self.roi_list_panel is not None:
                self.roi_list_panel.select_roi_in_list(selected_roi)
            # Statistics will be updated by ROI coordinator when ROI is clicked/selected
        else:
            # Clear selection if ROI doesn't belong to current slice
            if selected_roi is not None:
                self.roi_manager.select_roi(None)
            # Clear list selection
            if self.roi_list_panel is not None:
                self.roi_list_panel.select_roi_in_list(None)
            # Clear statistics panel
            if self.roi_statistics_panel is not None:
                self.roi_statistics_panel.clear_statistics()
    
    def display_measurements_for_slice(self, dataset: Dataset) -> None:
        """
        Display measurements for a slice.
        
        Ensures all measurements for the current slice are visible in the scene.
        Removes measurements from other slices before displaying current slice measurements.
        
        Args:
            dataset: pydicom Dataset for the current slice
        """
        # Extract DICOM identifiers
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = getattr(dataset, 'SeriesInstanceUID', '')
        # Use current_slice_index as instance identifier (array position)
        instance_identifier = self.current_slice_index
        
        # Clear measurements from other slices first
        self.measurement_tool.clear_measurements_from_other_slices(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )
        
        # Display measurements for this slice
        self.measurement_tool.display_measurements_for_slice(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )
    
    def handle_slice_changed(self, slice_index: int) -> None:
        """
        Handle slice index change.
        
        Args:
            slice_index: New slice index
        """
        if not self.current_studies or not self.current_series_uid:
            return
        
        datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
        if 0 <= slice_index < len(datasets):
            self.current_slice_index = slice_index
            dataset = datasets[slice_index]
            self.display_slice(
                dataset,
                self.current_studies,
                self.current_study_uid,
                self.current_series_uid,
                slice_index
            )
    
    def handle_series_navigation(self, direction: int) -> tuple[Optional[str], Optional[int], Optional[Dataset]]:
        """
        Handle series navigation request.
        
        Args:
            direction: -1 for left/previous series, 1 for right/next series
            
        Returns:
            Tuple of (new_series_uid, slice_index, dataset) or (None, None, None) if navigation not possible
        """
        if not self.current_studies or not self.current_study_uid:
            return None, None, None
        
        # Get all series for current study
        study_series = self.current_studies[self.current_study_uid]
        
        # Check if there are multiple series
        if len(study_series) <= 1:
            return None, None, None  # No navigation needed if only one series
        
        # Build list of series with SeriesNumber for sorting
        series_list = []
        for series_uid, datasets in study_series.items():
            if datasets:
                # Extract SeriesNumber from first dataset
                first_dataset = datasets[0]
                series_number = getattr(first_dataset, 'SeriesNumber', None)
                # Convert to int if possible, otherwise use 0
                try:
                    series_num = int(series_number) if series_number is not None else 0
                except (ValueError, TypeError):
                    series_num = 0
                series_list.append((series_num, series_uid, datasets))
        
        # Sort by SeriesNumber (ascending)
        series_list.sort(key=lambda x: x[0])
        
        # Find current series in sorted list
        current_index = None
        for idx, (_, series_uid, _) in enumerate(series_list):
            if series_uid == self.current_series_uid:
                current_index = idx
                break
        
        if current_index is None:
            return None, None, None  # Current series not found
        
        # Calculate new series index
        new_index = current_index + direction
        
        # Clamp to valid range
        if new_index < 0 or new_index >= len(series_list):
            return None, None, None  # Already at first or last series
        
        # Get new series UID and datasets
        _, new_series_uid, datasets = series_list[new_index]
        
        if not datasets:
            return None, None, None
        
        # Return new series information
        return new_series_uid, 0, datasets[0]
    
    def handle_arrow_key_pressed(self, direction: int) -> None:
        """
        Handle arrow key press from image viewer.
        
        Args:
            direction: 1 for up (next slice), -1 for down (previous slice)
        """
        if direction == 1:
            # Up arrow: next slice
            self.slice_navigator.next_slice()
        elif direction == -1:
            # Down arrow: previous slice
            self.slice_navigator.previous_slice()
    
    def set_current_data_context(
        self,
        current_studies: dict,
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int
    ) -> None:
        """
        Set current data context.
        
        Args:
            current_studies: Dictionary of studies
            current_study_uid: Current study UID
            current_series_uid: Current series UID
            current_slice_index: Current slice index
        """
        self.current_studies = current_studies
        self.current_study_uid = current_study_uid
        self.current_series_uid = current_series_uid
        self.current_slice_index = current_slice_index

