"""
View State Manager

This module manages view state including window/level, rescale, zoom, pan, and reset view operations.

Inputs:
    - Window/level changes
    - Rescale toggle changes
    - Zoom/pan changes
    - Viewport resize events
    - Reset view requests
    
Outputs:
    - Updated view state
    - Window/level updates
    - Rescale state updates
    - View reset operations
    
Requirements:
    - PySide6 for Qt integration
    - pydicom for DICOM dataset handling
    - DICOMProcessor for image processing
"""

from PySide6.QtCore import QPointF
from pydicom.dataset import Dataset
from typing import Optional, Dict, Callable, List, Tuple
import numpy as np
from core.dicom_processor import DICOMProcessor
from gui.image_viewer import ImageViewer
from gui.window_level_controls import WindowLevelControls
from gui.main_window import MainWindow


class ViewStateManager:
    """
    Manages view state including window/level, rescale, zoom, pan, and reset view.
    
    Handles:
    - Window/level state management
    - Rescale state management
    - Zoom/pan state management
    - Series-specific view defaults
    - View reset functionality
    """
    
    def __init__(
        self,
        dicom_processor: DICOMProcessor,
        image_viewer: ImageViewer,
        window_level_controls: WindowLevelControls,
        main_window: MainWindow,
        overlay_manager,
        overlay_coordinator: Optional[Callable] = None,
        roi_coordinator: Optional[Callable] = None,
        display_rois_for_slice: Optional[Callable] = None
    ):
        """
        Initialize the view state manager.
        
        Args:
            dicom_processor: DICOM processor for image operations
            image_viewer: Image viewer widget
            window_level_controls: Window/level controls widget
            main_window: Main window for UI updates
            overlay_manager: Overlay manager for overlay operations
            overlay_coordinator: Optional callback to recreate overlay
            roi_coordinator: Optional callback to redisplay ROIs
            display_rois_for_slice: Optional callback to display ROIs for current slice
        """
        self.dicom_processor = dicom_processor
        self.image_viewer = image_viewer
        self.window_level_controls = window_level_controls
        self.main_window = main_window
        self.overlay_manager = overlay_manager
        self.overlay_coordinator = overlay_coordinator
        self.roi_coordinator = roi_coordinator
        self.display_rois_for_slice = display_rois_for_slice
        self.series_navigator = None  # Will be set by set_series_navigator method
        
        # Window/level state - preserve between slices
        self.current_window_center: Optional[float] = None
        self.current_window_width: Optional[float] = None
        self.window_level_user_modified = False  # Track if user has manually changed window/level
        
        # Window/level presets from DICOM tags
        self.window_level_presets: List[Tuple[float, float, bool, Optional[str]]] = []
        self.current_preset_index: int = 0  # 0 = default/first preset
        
        # Initial view state for reset functionality
        self.initial_zoom: Optional[float] = None
        self.initial_h_scroll: Optional[int] = None
        self.initial_v_scroll: Optional[int] = None
        self.initial_scene_center: Optional[QPointF] = None  # Scene center point in scene coordinates
        self.initial_window_center: Optional[float] = None
        self.initial_window_width: Optional[float] = None
        
        # Series defaults storage: key is series identifier (StudyInstanceUID + SeriesInstanceUID)
        # Value is dict with: window_center, window_width, zoom, h_scroll, v_scroll, scene_center
        self.series_defaults: Dict[str, Dict] = {}
        
        # Track current series identifier for comparison
        self.current_series_identifier: Optional[str] = None
        
        # Rescale state management
        self.use_rescaled_values: bool = False  # Default to False, will be set based on dataset
        self.rescale_slope: Optional[float] = None
        self.rescale_intercept: Optional[float] = None
        self.rescale_type: Optional[str] = None
        
        # Viewport resize state - store scene center to preserve centered view
        self.saved_scene_center: Optional[QPointF] = None
        
        # Current dataset reference (needed for some operations)
        self.current_dataset: Optional[Dataset] = None
        
        # Current studies and slice info (needed for reset view)
        self.current_studies: dict = {}
        self.current_study_uid: str = ""
        self.current_series_uid: str = ""
        self.current_slice_index: int = 0
        
        # Series pixel range storage (for window width slider maximum)
        self.series_pixel_min: Optional[float] = None
        self.series_pixel_max: Optional[float] = None
    
    def set_series_navigator(self, series_navigator) -> None:
        """
        Set the series navigator reference.
        
        Args:
            series_navigator: SeriesNavigator instance
        """
        self.series_navigator = series_navigator
    
    def get_series_identifier(self, dataset: Dataset) -> str:
        """
        Get a unique identifier for a study/series combination.
        Uses StudyInstanceUID and SeriesInstanceUID.
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            Series identifier string
        """
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = getattr(dataset, 'SeriesInstanceUID', '')
        return f"{study_uid}_{series_uid}"
    
    def is_new_study_or_series(self, dataset: Dataset) -> bool:
        """
        Detect if this is a new study or series by comparing DICOM tags.
        
        Compares:
        - Study Date (0008,0020)
        - Modality (0008,0060)
        - Series Number (0020,0011)
        - Series Description (0008,103E)
        - Study Time (0008,0030)
        - Series Time (0008,0031)
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            True if this is a new study/series, False otherwise
        """
        if self.current_series_identifier is None:
            return True
        
        # Get current series identifier
        new_series_identifier = self.get_series_identifier(dataset)
        
        # If series identifier changed, it's a new study/series
        if new_series_identifier != self.current_series_identifier:
            return True
        
        return False
    
    def store_initial_view_state(self) -> None:
        """
        Store the initial view state (zoom, pan, window/level) for reset functionality.
        Stores per-series defaults in addition to global initial values.
        
        Called after the first image is displayed and the view has settled.
        """
        if self.image_viewer.image_item is None:
            return
        
        # print(f"[DEBUG-WL] store_initial_view_state called: series_id={self.current_series_identifier[:20] if self.current_series_identifier else 'None'}...")
        # print(f"[DEBUG-WL] Current values: wc={self.current_window_center}, ww={self.current_window_width}, use_rescaled={self.use_rescaled_values}")
        
        # Store initial zoom (global fallback)
        if self.initial_zoom is None:
            self.initial_zoom = self.image_viewer.current_zoom
        
        # Store initial pan position (scrollbar values) - global fallback
        # Keep for backward compatibility, but prefer scene center for reset
        if self.initial_h_scroll is None:
            self.initial_h_scroll = self.image_viewer.horizontalScrollBar().value()
        if self.initial_v_scroll is None:
            self.initial_v_scroll = self.image_viewer.verticalScrollBar().value()
        
        # Store initial scene center point in scene coordinates - preferred for reset
        # This works correctly even when viewport size changes (e.g., splitter moved)
        if self.initial_scene_center is None:
            scene_center = self.image_viewer.get_viewport_center_scene()
            if scene_center is not None:
                self.initial_scene_center = scene_center
        
        # Store initial window/level (global fallback)
        if self.initial_window_center is None:
            self.initial_window_center = self.current_window_center
        if self.initial_window_width is None:
            self.initial_window_width = self.current_window_width
        
        # Store per-series defaults if we have a current series identifier
        if self.current_series_identifier:
            # Get scene center point for this series
            scene_center = self.image_viewer.get_viewport_center_scene()
            
            if self.current_series_identifier not in self.series_defaults:
                # Create new entry with all defaults
                # print(f"[DEBUG-WL] Creating NEW series_defaults entry")
                self.series_defaults[self.current_series_identifier] = {
                    'window_center': self.current_window_center,
                    'window_width': self.current_window_width,
                    'zoom': self.image_viewer.current_zoom,
                    'h_scroll': self.image_viewer.horizontalScrollBar().value(),
                    'v_scroll': self.image_viewer.verticalScrollBar().value(),
                    'scene_center': scene_center,  # Store scene center point in scene coordinates
                    'use_rescaled_values': self.use_rescaled_values
                }
            else:
                # Entry already exists - check if window/level defaults were already set during display_slice
                defaults_already_set = self.series_defaults[self.current_series_identifier].get('window_level_defaults_set', False)
                
                if defaults_already_set:
                    # Window/level defaults were already set correctly during display_slice
                    # Restore current values from series_defaults in case they were corrupted
                    stored_wc = self.series_defaults[self.current_series_identifier]['window_center']
                    stored_ww = self.series_defaults[self.current_series_identifier]['window_width']
                    stored_rescaled = self.series_defaults[self.current_series_identifier]['use_rescaled_values']
                    # print(f"[DEBUG-WL] UPDATING existing series_defaults (preserving window/level)")
                    # print(f"[DEBUG-WL] Restoring current values from series_defaults: wc={stored_wc}, ww={stored_ww}")
                    
                    # Restore current values to correct defaults
                    self.current_window_center = stored_wc
                    self.current_window_width = stored_ww
                    
                    # Update the window/level controls to reflect the restored values
                    unit = self.rescale_type if (stored_rescaled and self.rescale_type) else None
                    self.window_level_controls.set_window_level(
                        stored_wc, stored_ww, block_signals=True, unit=unit
                    )
                    # print(f"[DEBUG-WL] Updated window/level controls with restored values")
                    
                    # Re-display the current image with the corrected window/level
                    # This fixes the initial display that was rendered with corrupted values
                    if (self.current_dataset is not None and self.current_studies and 
                        self.current_study_uid and self.current_series_uid):
                        if (self.current_study_uid in self.current_studies and 
                            self.current_series_uid in self.current_studies[self.current_study_uid]):
                            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                            if self.current_slice_index < len(datasets):
                                # Re-render image with correct window/level
                                image = self.dicom_processor.dataset_to_image(
                                    self.current_dataset,
                                    window_center=stored_wc,
                                    window_width=stored_ww,
                                    apply_rescale=stored_rescaled
                                )
                                if image:
                                    self.image_viewer.set_image(image, preserve_view=True)
                                    # print(f"[DEBUG-WL] Re-displayed image with corrected window/level")
                                    
                                    # Also regenerate series navigator thumbnail with corrected window/level
                                    if self.series_navigator and datasets:
                                        first_dataset = datasets[0]  # Use first slice of series for thumbnail
                                        self.series_navigator.regenerate_series_thumbnail(
                                            self.current_study_uid,
                                            self.current_series_uid,
                                            first_dataset,
                                            stored_wc,
                                            stored_ww,
                                            stored_rescaled
                                        )
                    
                    # Only update zoom/pan, preserve window/level values in series_defaults
                    self.series_defaults[self.current_series_identifier].update({
                        'zoom': self.image_viewer.current_zoom,
                        'h_scroll': self.image_viewer.horizontalScrollBar().value(),
                        'v_scroll': self.image_viewer.verticalScrollBar().value(),
                        'scene_center': scene_center
                    })
                    # Keep the flag set
                    self.series_defaults[self.current_series_identifier]['window_level_defaults_set'] = True
                else:
                    # No defaults set yet, update all fields including window/level
                    # print(f"[DEBUG-WL] UPDATING existing series_defaults entry (all fields)")
                    self.series_defaults[self.current_series_identifier].update({
                        'window_center': self.current_window_center,
                        'window_width': self.current_window_width,
                        'zoom': self.image_viewer.current_zoom,
                        'h_scroll': self.image_viewer.horizontalScrollBar().value(),
                        'v_scroll': self.image_viewer.verticalScrollBar().value(),
                        'scene_center': scene_center,
                        'use_rescaled_values': self.use_rescaled_values  # Always update to match current state
                    })
            # print(f"[DEBUG-WL] Stored in series_defaults: wc={self.series_defaults[self.current_series_identifier]['window_center']}, ww={self.series_defaults[self.current_series_identifier]['window_width']}, use_rescaled={self.series_defaults[self.current_series_identifier]['use_rescaled_values']}")
    
    def reset_view(self) -> None:
        """
        Reset view to initial state (zoom, pan, window center/level).
        
        Uses series-specific defaults if available, otherwise falls back to global initial values.
        """
        if self.current_dataset is None:
            # No current dataset
            return
        
        modality = getattr(self.current_dataset, 'Modality', 'Unknown')
        # print(f"[DEBUG-WL] ===== reset_view called: modality={modality}, current_use_rescaled={self.use_rescaled_values} =====")
        
        # Get series identifier
        series_identifier = self.get_series_identifier(self.current_dataset)
        # print(f"[DEBUG-WL] Series identifier: {series_identifier[:20]}...")
        
        # Try to get series-specific defaults
        if series_identifier in self.series_defaults:
            # print(f"[DEBUG-WL] Found series_defaults for this series")
            defaults = self.series_defaults[series_identifier]
            reset_zoom = defaults.get('zoom')
            reset_h_scroll = defaults.get('h_scroll')
            reset_v_scroll = defaults.get('v_scroll')
            reset_scene_center = defaults.get('scene_center')  # Preferred: scene center point
            reset_window_center = defaults.get('window_center')
            reset_window_width = defaults.get('window_width')
            reset_use_rescaled_values = defaults.get('use_rescaled_values')
            # print(f"[DEBUG-WL] Retrieved from series_defaults: wc={reset_window_center}, ww={reset_window_width}, stored_use_rescaled={reset_use_rescaled_values}")
        else:
            # Fall back to global initial values
            # print(f"[DEBUG-WL] No series_defaults found, using global initial values")
            reset_zoom = self.initial_zoom
            reset_h_scroll = self.initial_h_scroll
            reset_v_scroll = self.initial_v_scroll
            reset_scene_center = self.initial_scene_center  # Preferred: scene center point
            reset_window_center = self.initial_window_center
            reset_window_width = self.initial_window_width
            reset_use_rescaled_values = None
            # print(f"[DEBUG-WL] Global initial values: wc={reset_window_center}, ww={reset_window_width}")
        
        # If we have window/level values but they're in a different rescale state than current,
        # convert them to match the current rescale state
        if (reset_window_center is not None and reset_window_width is not None and 
            reset_use_rescaled_values is not None and 
            reset_use_rescaled_values != self.use_rescaled_values):
            # print(f"[DEBUG-WL] Rescale state mismatch! stored={reset_use_rescaled_values}, current={self.use_rescaled_values}")
            orig_wc, orig_ww = reset_window_center, reset_window_width
            # Stored values are in different units than current display mode - convert them
            if reset_use_rescaled_values and not self.use_rescaled_values:
                # Stored in rescaled, need raw
                if (self.rescale_slope is not None and self.rescale_intercept is not None and 
                    self.rescale_slope != 0.0):
                    reset_window_center, reset_window_width = self.dicom_processor.convert_window_level_rescaled_to_raw(
                        reset_window_center, reset_window_width, self.rescale_slope, self.rescale_intercept
                    )
                    # print(f"[DEBUG-WL] Converted rescaled->raw: ({orig_wc}, {orig_ww}) -> ({reset_window_center}, {reset_window_width})")
            elif not reset_use_rescaled_values and self.use_rescaled_values:
                # Stored in raw, need rescaled
                if self.rescale_slope is not None and self.rescale_intercept is not None:
                    reset_window_center, reset_window_width = self.dicom_processor.convert_window_level_raw_to_rescaled(
                        reset_window_center, reset_window_width, self.rescale_slope, self.rescale_intercept
                    )
                    # print(f"[DEBUG-WL] Converted raw->rescaled: ({orig_wc}, {orig_ww}) -> ({reset_window_center}, {reset_window_width})")
        else:
            # print(f"[DEBUG-WL] No conversion needed (rescale states match or values missing)")
            pass
        
        # If window/level defaults are missing, recalculate them based on current dataset
        # Always use current rescale state when recalculating to ensure consistency
        if reset_window_center is None or reset_window_width is None:
            # Recalculate window/level defaults from current dataset
            if self.current_studies and self.current_study_uid and self.current_series_uid:
                if (self.current_study_uid in self.current_studies and 
                    self.current_series_uid in self.current_studies[self.current_study_uid]):
                    series_datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                    if series_datasets and len(series_datasets) > 0:
                        dataset = series_datasets[0]  # Use first dataset in series
                        # Use current rescale state to ensure defaults match current display mode
                        # This is important when toggling between raw and rescaled values
                        use_rescaled = self.use_rescaled_values
                        
                        # Calculate series pixel range
                        try:
                            series_pixel_min, series_pixel_max = self.dicom_processor.get_series_pixel_value_range(
                                series_datasets, apply_rescale=use_rescaled
                            )
                            self.set_series_pixel_range(series_pixel_min, series_pixel_max)
                        except Exception:
                            series_pixel_min = None
                            series_pixel_max = None
                        
                        # Check for window/level in DICOM metadata
                        wc, ww, is_rescaled = self.dicom_processor.get_window_level_from_dataset(
                            dataset,
                            rescale_slope=self.rescale_slope,
                            rescale_intercept=self.rescale_intercept
                        )
                        if wc is not None and ww is not None:
                            # Convert if needed
                            if is_rescaled and not use_rescaled:
                                if (self.rescale_slope is not None and self.rescale_intercept is not None and self.rescale_slope != 0.0):
                                    wc, ww = self.dicom_processor.convert_window_level_rescaled_to_raw(
                                        wc, ww, self.rescale_slope, self.rescale_intercept
                                    )
                            elif not is_rescaled and use_rescaled:
                                if (self.rescale_slope is not None and self.rescale_intercept is not None):
                                    wc, ww = self.dicom_processor.convert_window_level_raw_to_rescaled(
                                        wc, ww, self.rescale_slope, self.rescale_intercept
                                    )
                            reset_window_center = wc
                            reset_window_width = ww
                        elif series_pixel_min is not None and series_pixel_max is not None:
                            # Calculate median from series for window center
                            if series_datasets:
                                reset_window_center = self.dicom_processor.get_series_pixel_median(
                                    series_datasets, apply_rescale=use_rescaled
                                )
                                # If median calculation failed, fall back to midpoint
                                if reset_window_center is None:
                                    reset_window_center = (series_pixel_min + series_pixel_max) / 2.0
                            else:
                                reset_window_center = (series_pixel_min + series_pixel_max) / 2.0
                            reset_window_width = series_pixel_max - series_pixel_min
                            if reset_window_width <= 0:
                                reset_window_width = 1.0
                        else:
                            # Fallback to single slice
                            try:
                                pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                                    dataset, apply_rescale=use_rescaled
                                )
                                if pixel_min is not None and pixel_max is not None:
                                    # Calculate median from single slice pixel array
                                    pixel_array = self.dicom_processor.get_pixel_array(dataset)
                                    if pixel_array is not None:
                                        # Apply rescale if needed
                                        if use_rescaled:
                                            rescale_slope, rescale_intercept, _ = self.dicom_processor.get_rescale_parameters(dataset)
                                            if rescale_slope is not None and rescale_intercept is not None:
                                                pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
                                        reset_window_center = float(np.median(pixel_array))
                                    else:
                                        # Fall back to midpoint if pixel array unavailable
                                        reset_window_center = (pixel_min + pixel_max) / 2.0
                                    reset_window_width = pixel_max - pixel_min
                                    if reset_window_width <= 0:
                                        reset_window_width = 1.0
                            except Exception:
                                pass  # Will use None values which will be handled below
        
        # Ensure we have a valid rescale state value - calculate default if missing
        if reset_use_rescaled_values is None:
            # Default to True if rescale parameters exist, False otherwise
            reset_use_rescaled_values = (self.rescale_slope is not None and self.rescale_intercept is not None)
        
        if reset_zoom is None:
            # No reset values available
            return
        
        # Reset rescale state to default FIRST (before window/level to avoid incorrect conversion)
        # Always restore rescale state, even if it's the same as current
        # Restore rescale state directly without converting window/level values
        # (the stored window/level values are already in the correct units for the restored state)
        self.use_rescaled_values = reset_use_rescaled_values
        # Update UI toggle states
        self.main_window.set_rescale_toggle_state(reset_use_rescaled_values)
        self.image_viewer.set_rescale_toggle_state(reset_use_rescaled_values)
        
        # Recalculate pixel value ranges for window/level controls
        if self.current_dataset is not None:
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                self.current_dataset, apply_rescale=self.use_rescaled_values
            )
            if pixel_min is not None and pixel_max is not None:
                # Get series pixel range for both center and width ranges
                series_pixel_min, series_pixel_max = self.get_series_pixel_range()
                
                if series_pixel_min is not None and series_pixel_max is not None:
                    # Use series range for both center and width ranges
                    center_range = (series_pixel_min, series_pixel_max)
                    width_range = (1.0, max(1.0, series_pixel_max - series_pixel_min))
                else:
                    # Fallback to current slice range if series range not available
                    center_range = (pixel_min, pixel_max)
                    width_range = (1.0, max(1.0, pixel_max - pixel_min))
                
                self.window_level_controls.set_ranges(center_range, width_range)
            
            # Update window/level unit labels
            unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
            self.window_level_controls.set_unit(unit)
        
        # Reset window/level to initial values (already in correct units for current rescale state)
        if reset_window_center is not None and reset_window_width is not None:
            # print(f"[DEBUG-WL] Applying final values: wc={reset_window_center}, ww={reset_window_width}, use_rescaled={self.use_rescaled_values}")
            # Get unit for window/level display
            unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
            self.window_level_controls.set_window_level(
                reset_window_center, 
                reset_window_width, 
                block_signals=True,
                unit=unit
            )
            self.current_window_center = reset_window_center
            self.current_window_width = reset_window_width
            self.window_level_user_modified = False
        
        # Re-display current slice with reset window/level and rescale state
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                # Use current window/level values (which have been reset)
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    window_center=self.current_window_center,
                    window_width=self.current_window_width,
                    apply_rescale=self.use_rescaled_values
                )
                if image:
                    # Set image first (without preserving view to avoid wrong centering)
                    self.image_viewer.set_image(image, preserve_view=False)
                    
                    # Always fit to view and center based on current viewport size
                    # This ensures the image is properly centered and fits regardless of
                    # viewport size changes (e.g., navigator visibility, splitter positions)
                    self.image_viewer.fit_to_view(center_image=True)
                    
                    self.image_viewer.last_transform = self.image_viewer.transform()
                    self.image_viewer.zoom_changed.emit(self.image_viewer.current_zoom)
                    
                    # Recreate overlay
                    from core.dicom_parser import DICOMParser
                    parser = DICOMParser(dataset)
                    # Get total slice count
                    total_slices = len(datasets) if datasets else 0
                    self.overlay_manager.create_overlay_items(
                        self.image_viewer.scene,
                        parser,
                        total_slices=total_slices if total_slices > 0 else None
                    )
                    # Re-display ROIs for current slice
                    if self.display_rois_for_slice:
                        self.display_rois_for_slice(dataset)
                    # Update ROI statistics if there's a selected ROI
                    if self.roi_coordinator:
                        self.roi_coordinator(dataset)
    
    def handle_window_changed(self, center: float, width: float) -> None:
        """
        Handle window/level change.
        
        Args:
            center: Window center
            width: Window width
        """
        # DEBUG: Print received values and current state
        # print(f"[DEBUG-PRESET-MATCH] handle_window_changed called: center={center:.2f}, width={width:.2f}")
        # print(f"[DEBUG-PRESET-MATCH] Rescale state: use_rescaled={self.use_rescaled_values}, slope={self.rescale_slope}, intercept={self.rescale_intercept}")
        # print(f"[DEBUG-PRESET-MATCH] Available presets: {len(self.window_level_presets) if self.window_level_presets else 0}")
        # print(f"[DEBUG-PRESET-MATCH] Stored values: center={self.current_window_center}, width={self.current_window_width}")
        
        # Check if received values match stored values (to detect stale values from previous series)
        # Use small tolerance for comparison
        match_tolerance = 0.1
        values_match_stored = (
            self.current_window_center is not None and 
            self.current_window_width is not None and
            abs(self.current_window_center - center) < match_tolerance and
            abs(self.current_window_width - width) < match_tolerance
        )
        
        # If presets exist and received values don't match stored values, use stored values for preset matching
        # This handles the case where stale values from previous series are received
        match_center = center
        match_width = width
        if self.window_level_presets and not values_match_stored and self.current_window_center is not None and self.current_window_width is not None:
            # print(f"[DEBUG-PRESET-MATCH] Received values don't match stored values - using stored values for preset matching")
            # print(f"[DEBUG-PRESET-MATCH]   Received: center={center:.2f}, width={width:.2f}")
            # print(f"[DEBUG-PRESET-MATCH]   Stored: center={self.current_window_center:.2f}, width={self.current_window_width:.2f}")
            match_center = self.current_window_center
            match_width = self.current_window_width
        else:
            # Store current window/level values (only if they match stored or no stored values exist)
            self.current_window_center = center
            self.current_window_width = width
        
        # Check if the new values match any existing preset
        preset_name = None
        matched_preset = False
        
        # Skip preset matching if no presets are loaded yet
        if not self.window_level_presets:
            # No presets available, mark as user-modified
            # print(f"[DEBUG-PRESET-MATCH] No presets available, marking as user-modified")
            self.window_level_user_modified = True
        else:
            # Use relative tolerance for better matching with larger values
            # Use 0.1% relative tolerance, with minimum absolute tolerance of 0.1
            center_tolerance = max(0.1, abs(match_center) * 0.001)
            width_tolerance = max(0.1, abs(match_width) * 0.001)
            # print(f"[DEBUG-PRESET-MATCH] Using values for matching: center={match_center:.2f}, width={match_width:.2f}")
            # print(f"[DEBUG-PRESET-MATCH] Tolerances: center_tol={center_tolerance:.4f}, width_tol={width_tolerance:.4f}")
            
            for idx, (preset_wc, preset_ww, preset_is_rescaled, preset_name_val) in enumerate(self.window_level_presets):
                # print(f"[DEBUG-PRESET-MATCH] Checking preset {idx}: original wc={preset_wc:.2f}, ww={preset_ww:.2f}, is_rescaled={preset_is_rescaled}, name={preset_name_val}")
                
                # Convert preset values to match current rescale state before comparing
                compare_wc = preset_wc
                compare_ww = preset_ww
                
                # Convert if needed based on current rescale state
                # Only convert if rescale parameters are available
                if preset_is_rescaled and not self.use_rescaled_values:
                    # Preset is rescaled, but we're using raw - convert preset to raw
                    if (self.rescale_slope is not None and self.rescale_intercept is not None and 
                        self.rescale_slope != 0.0):
                        compare_wc, compare_ww = self.dicom_processor.convert_window_level_rescaled_to_raw(
                            preset_wc, preset_ww, self.rescale_slope, self.rescale_intercept
                        )
                        # print(f"[DEBUG-PRESET-MATCH] Converted rescaled->raw: ({preset_wc:.2f}, {preset_ww:.2f}) -> ({compare_wc:.2f}, {compare_ww:.2f})")
                elif not preset_is_rescaled and self.use_rescaled_values:
                    # Preset is raw, but we're using rescaled - convert preset to rescaled
                    if (self.rescale_slope is not None and self.rescale_intercept is not None):
                        compare_wc, compare_ww = self.dicom_processor.convert_window_level_raw_to_rescaled(
                            preset_wc, preset_ww, self.rescale_slope, self.rescale_intercept
                        )
                        # print(f"[DEBUG-PRESET-MATCH] Converted raw->rescaled: ({preset_wc:.2f}, {preset_ww:.2f}) -> ({compare_wc:.2f}, {compare_ww:.2f})")
                else:
                    # print(f"[DEBUG-PRESET-MATCH] No conversion needed: preset_is_rescaled={preset_is_rescaled}, use_rescaled={self.use_rescaled_values}")
                    pass
                
                # Compare converted preset values with match values using relative tolerance
                center_diff = abs(compare_wc - match_center)
                width_diff = abs(compare_ww - match_width)
                center_match = center_diff < center_tolerance
                width_match = width_diff < width_tolerance
                
                # print(f"[DEBUG-PRESET-MATCH] Comparison: compare_wc={compare_wc:.2f} vs match_center={match_center:.2f} (diff={center_diff:.4f}, tol={center_tolerance:.4f}, match={center_match})")
                # print(f"[DEBUG-PRESET-MATCH] Comparison: compare_ww={compare_ww:.2f} vs match_width={match_width:.2f} (diff={width_diff:.4f}, tol={width_tolerance:.4f}, match={width_match})")
                
                if center_match and width_match:
                    # Found a match - this is a preset, not a user modification
                    # print(f"[DEBUG-PRESET-MATCH] MATCH FOUND! Preset {idx} matches: {preset_name_val if preset_name_val else 'Default'}")
                    self.current_preset_index = idx
                    self.window_level_user_modified = False
                    preset_name = preset_name_val if preset_name_val else "Default"
                    matched_preset = True
                    break
                else:
                    # print(f"[DEBUG-PRESET-MATCH] No match for preset {idx}")
                    pass
        
        # If no preset match found, mark as user-modified
        if not matched_preset:
            # print(f"[DEBUG-PRESET-MATCH] No preset match found, marking as user-modified")
            self.window_level_user_modified = True
        
        # Update status bar widget
        # print(f"[DEBUG-PRESET-MATCH] Final result: preset_name={preset_name}, user_modified={self.window_level_user_modified}")
        current_zoom = self.image_viewer.current_zoom
        self.main_window.update_zoom_preset_status(current_zoom, preset_name)
        
        # Re-display current slice with new window/level
        if self.current_studies and self.current_series_uid:
            datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if self.current_slice_index < len(datasets):
                dataset = datasets[self.current_slice_index]
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    window_center=center,
                    window_width=width,
                    apply_rescale=self.use_rescaled_values
                )
                if image:
                    # Preserve view when window/level changes (same slice)
                    self.image_viewer.set_image(image, preserve_view=True)
                    # Recreate overlay to ensure it stays on top
                    from core.dicom_parser import DICOMParser
                    parser = DICOMParser(dataset)
                    total_slices = len(datasets)
                    self.overlay_manager.create_overlay_items(
                        self.image_viewer.scene,
                        parser,
                        total_slices=total_slices if total_slices > 0 else None
                    )
                    # Refresh ROIs to ensure they remain visible
                    if self.display_rois_for_slice:
                        self.display_rois_for_slice(dataset)
    
    def handle_rescale_toggle(self, checked: bool) -> None:
        """
        Handle rescale toggle change from toolbar or context menu.
        
        Converts current window/level values to preserve image appearance when toggling.
        
        Args:
            checked: True to use rescaled values, False to use raw values
        """
        # Get current window/level values before updating state
        current_center = self.current_window_center
        current_width = self.current_window_width
        
        # Convert window/level values if we have rescale parameters
        if (current_center is not None and current_width is not None and
            self.rescale_slope is not None and self.rescale_intercept is not None and
            self.rescale_slope != 0.0):
            
            # Determine conversion direction
            if self.use_rescaled_values and not checked:
                # Toggling from rescaled to raw: convert rescaled -> raw
                current_center, current_width = self.dicom_processor.convert_window_level_rescaled_to_raw(
                    current_center, current_width, self.rescale_slope, self.rescale_intercept
                )
            elif not self.use_rescaled_values and checked:
                # Toggling from raw to rescaled: convert raw -> rescaled
                current_center, current_width = self.dicom_processor.convert_window_level_raw_to_rescaled(
                    current_center, current_width, self.rescale_slope, self.rescale_intercept
                )
        
        # Update state
        self.use_rescaled_values = checked
        
        # Update UI toggle states
        self.main_window.set_rescale_toggle_state(checked)
        self.image_viewer.set_rescale_toggle_state(checked)
        
        # Recalculate and update everything
        if self.current_dataset is not None:
            # Recalculate pixel value ranges
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                self.current_dataset, apply_rescale=self.use_rescaled_values
            )
            if pixel_min is not None and pixel_max is not None:
                # Recalculate series pixel range for both center and width ranges
                # Get all datasets for current series
                if self.current_studies and self.current_study_uid and self.current_series_uid:
                    if (self.current_study_uid in self.current_studies and 
                        self.current_series_uid in self.current_studies[self.current_study_uid]):
                        series_datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                        try:
                            series_pixel_min, series_pixel_max = self.dicom_processor.get_series_pixel_value_range(
                                series_datasets, apply_rescale=self.use_rescaled_values
                            )
                            # Store the recalculated series pixel range
                            self.set_series_pixel_range(series_pixel_min, series_pixel_max)
                            
                            # Use series range for both center and width ranges if available
                            if series_pixel_min is not None and series_pixel_max is not None:
                                center_range = (series_pixel_min, series_pixel_max)
                                width_range = (1.0, max(1.0, series_pixel_max - series_pixel_min))
                            else:
                                # Fallback to current slice range
                                center_range = (pixel_min, pixel_max)
                                width_range = (1.0, max(1.0, pixel_max - pixel_min))
                        except Exception as e:
                            # If series pixel range calculation fails, use current slice range
                            error_type = type(e).__name__
                            print(f"Error recalculating series pixel range for rescale toggle ({error_type}): {e}")
                            center_range = (pixel_min, pixel_max)
                            width_range = (1.0, max(1.0, pixel_max - pixel_min))
                            # Clear stored series pixel range on error
                            self.clear_series_pixel_range()
                    else:
                        # Series not found, use current slice range
                        center_range = (pixel_min, pixel_max)
                        width_range = (1.0, max(1.0, pixel_max - pixel_min))
                else:
                    # No series data available, use current slice range
                    center_range = (pixel_min, pixel_max)
                    width_range = (1.0, max(1.0, pixel_max - pixel_min))
                
                self.window_level_controls.set_ranges(center_range, width_range)
            
            # Update window/level unit labels
            unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
            self.window_level_controls.set_unit(unit)
            
            # Update window/level controls with converted values
            if current_center is not None and current_width is not None:
                self.current_window_center = current_center
                self.current_window_width = current_width
                self.window_level_controls.set_window_level(
                    current_center, current_width, block_signals=True, unit=unit
                )
            
            # Re-display current slice with new rescale setting
            if self.current_studies and self.current_series_uid:
                datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                if self.current_slice_index < len(datasets):
                    dataset = datasets[self.current_slice_index]
                    # Re-display with converted window/level and new rescale setting
                    if self.current_window_center is not None and self.current_window_width is not None:
                        image = self.dicom_processor.dataset_to_image(
                            dataset,
                            window_center=self.current_window_center,
                            window_width=self.current_window_width,
                            apply_rescale=self.use_rescaled_values
                        )
                    else:
                        image = self.dicom_processor.dataset_to_image(
                            dataset,
                            apply_rescale=self.use_rescaled_values
                        )
                    if image:
                        # Preserve view when toggling rescale
                        self.image_viewer.set_image(image, preserve_view=True)
                        # Recreate overlay
                        from core.dicom_parser import DICOMParser
                        parser = DICOMParser(dataset)
                        total_slices = len(datasets)
                        self.overlay_manager.create_overlay_items(
                            self.image_viewer.scene,
                            parser,
                            total_slices=total_slices if total_slices > 0 else None
                        )
                        # Re-display ROIs for current slice
                        if self.roi_coordinator:
                            self.roi_coordinator(dataset)
    
    def handle_zoom_changed(self, zoom_level: float) -> None:
        """
        Handle zoom level change.
        
        Updates overlay positions immediately to keep text anchored to viewport edges
        during zoom operations, eliminating jitter.
        
        Args:
            zoom_level: Current zoom level
        """
        # Update overlay positions immediately when zoom changes
        # This eliminates jitter by updating synchronously with zoom changes,
        # rather than waiting for the delayed transform_changed signal
        if self.current_dataset is not None:
            self.overlay_manager.update_overlay_positions(self.image_viewer.scene)
    
    def handle_transform_changed(self) -> None:
        """
        Handle view transform change (zoom/pan).
        
        Updates overlay positions to keep text anchored to viewport edges.
        This is called after the transform is fully applied.
        """
        # Update overlay positions when transform changes
        if self.current_dataset is not None:
            self.overlay_manager.update_overlay_positions(self.image_viewer.scene)
    
    def handle_viewport_resizing(self) -> None:
        """
        Handle viewport resize start (when splitter starts moving).
        
        Captures the current viewport center in scene coordinates before the resize
        completes, so we can restore it after resize to maintain the centered view.
        """
        # Capture current viewport center in scene coordinates before resize
        if self.image_viewer.image_item is not None:
            scene_center = self.image_viewer.get_viewport_center_scene()
            if scene_center is not None:
                self.saved_scene_center = scene_center
    
    def handle_viewport_resized(self) -> None:
        """
        Handle viewport resize (when splitter moves or series navigator visibility changes).
        
        Updates overlay positions to keep text anchored to viewport edges
        when the left or right panels are resized.
        Also rescales the image to fill the viewport and restores the centered view
        if a scene center was captured.
        """
        # Rescale image to fill viewport and restore center if we captured a scene center point
        if self.saved_scene_center is not None and self.image_viewer.image_item is not None:
            # First, fit the image to the new viewport size (rescale to fill)
            self.image_viewer.fit_to_view(center_image=False)
            # Then restore the center point that was captured before the resize
            self.image_viewer.centerOn(self.saved_scene_center)
            self.saved_scene_center = None  # Clear after use
        
        # Update overlay positions when viewport size changes
        if self.current_dataset is not None:
            self.overlay_manager.update_overlay_positions(self.image_viewer.scene)
    
    def handle_window_level_drag(self, center_delta: float, width_delta: float) -> None:
        """
        Handle window/level drag adjustment from image viewer.
        
        Args:
            center_delta: Change in window center (positive = up, negative = down)
            width_delta: Change in window width (positive = right/wider, negative = left/narrower)
        """
        # Get initial values from image_viewer (these are set when drag starts)
        if (self.image_viewer.right_mouse_drag_start_center is None or 
            self.image_viewer.right_mouse_drag_start_width is None):
            return  # Drag not properly initialized
        
        # Apply deltas to initial values
        new_center = self.image_viewer.right_mouse_drag_start_center + center_delta
        new_width = self.image_viewer.right_mouse_drag_start_width + width_delta
        
        # Clamp to valid ranges
        center_range = self.window_level_controls.center_range
        width_range = self.window_level_controls.width_range
        
        new_center = max(center_range[0], min(center_range[1], new_center))
        new_width = max(width_range[0], min(width_range[1], new_width))
        
        # Update window/level controls (block signals to prevent recursive updates during drag)
        self.window_level_controls.set_window_level(new_center, new_width, block_signals=True)
        
        # Manually trigger window change to update image
        self.handle_window_changed(new_center, new_width)
    
    def handle_right_mouse_press_for_drag(self) -> None:
        """
        Handle right mouse press for drag - provide window/level values to image viewer.
        """
        # Get current window/level values and ranges
        center, width = self.window_level_controls.get_window_level()
        center_range = self.window_level_controls.center_range
        width_range = self.window_level_controls.width_range
        
        # Set values in image viewer for drag tracking
        self.image_viewer.set_window_level_for_drag(center, width, center_range, width_range)
    
    def reset_window_level_state(self) -> None:
        """Reset window/level state when loading new files."""
        self.current_window_center = None
        self.current_window_width = None
        self.window_level_user_modified = False
        self.clear_window_level_presets()
        # Clear global initial values to prevent persistence from previous datasets
        self.initial_window_center = None
        self.initial_window_width = None
    
    def clear_window_level_presets(self) -> None:
        """Clear window/level presets when changing series."""
        self.window_level_presets = []
        self.current_preset_index = 0
    
    def reset_series_tracking(self) -> None:
        """Reset series tracking when loading new files."""
        self.current_series_identifier = None
        # Clear series pixel range when resetting series tracking
        self.clear_series_pixel_range()
        # Clear series defaults when loading new files so window/level resets to defaults
        # even if the same series is loaded again
        self.series_defaults.clear()
    
    def set_rescale_parameters(self, slope: Optional[float], intercept: Optional[float], rescale_type: Optional[str]) -> None:
        """
        Set rescale parameters from dataset.
        
        Args:
            slope: Rescale slope
            intercept: Rescale intercept
            rescale_type: Rescale type (e.g., "HU")
        """
        self.rescale_slope = slope
        self.rescale_intercept = intercept
        self.rescale_type = rescale_type
    
    def set_current_series_identifier(self, identifier: Optional[str]) -> None:
        """
        Set current series identifier.
        
        Args:
            identifier: Series identifier string
        """
        self.current_series_identifier = identifier
    
    def set_current_data_context(
        self,
        current_dataset: Optional[Dataset],
        current_studies: dict,
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int
    ) -> None:
        """
        Set current data context for operations that need it.
        
        Args:
            current_dataset: Current DICOM dataset
            current_studies: Dictionary of studies
            current_study_uid: Current study UID
            current_series_uid: Current series UID
            current_slice_index: Current slice index
        """
        self.current_dataset = current_dataset
        self.current_studies = current_studies
        self.current_study_uid = current_study_uid
        self.current_series_uid = current_series_uid
        self.current_slice_index = current_slice_index
    
    def set_series_pixel_range(self, pixel_min: Optional[float], pixel_max: Optional[float]) -> None:
        """
        Set the pixel value range for the current series.
        
        Args:
            pixel_min: Minimum pixel value across the series
            pixel_max: Maximum pixel value across the series
        """
        self.series_pixel_min = pixel_min
        self.series_pixel_max = pixel_max
    
    def get_series_pixel_range(self) -> tuple[Optional[float], Optional[float]]:
        """
        Get the pixel value range for the current series.
        
        Returns:
            Tuple of (pixel_min, pixel_max) or (None, None) if not set
        """
        return (self.series_pixel_min, self.series_pixel_max)
    
    def clear_series_pixel_range(self) -> None:
        """Clear the stored series pixel range."""
        self.series_pixel_min = None
        self.series_pixel_max = None

