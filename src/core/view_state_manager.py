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
from typing import Optional, Dict, Callable
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
        roi_coordinator: Optional[Callable] = None
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
        """
        self.dicom_processor = dicom_processor
        self.image_viewer = image_viewer
        self.window_level_controls = window_level_controls
        self.main_window = main_window
        self.overlay_manager = overlay_manager
        self.overlay_coordinator = overlay_coordinator
        self.roi_coordinator = roi_coordinator
        
        # Window/level state - preserve between slices
        self.current_window_center: Optional[float] = None
        self.current_window_width: Optional[float] = None
        self.window_level_user_modified = False  # Track if user has manually changed window/level
        
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
                # Entry already exists - update fields while preserving existing values
                self.series_defaults[self.current_series_identifier].update({
                    'window_center': self.current_window_center,
                    'window_width': self.current_window_width,
                    'zoom': self.image_viewer.current_zoom,
                    'h_scroll': self.image_viewer.horizontalScrollBar().value(),
                    'v_scroll': self.image_viewer.verticalScrollBar().value(),
                    'scene_center': scene_center
                })
                # Don't overwrite use_rescaled_values - it was already set to the initial default
    
    def reset_view(self) -> None:
        """
        Reset view to initial state (zoom, pan, window center/level).
        
        Uses series-specific defaults if available, otherwise falls back to global initial values.
        """
        if self.current_dataset is None:
            # No current dataset
            return
        
        # Get series identifier
        series_identifier = self.get_series_identifier(self.current_dataset)
        
        # Try to get series-specific defaults
        if series_identifier in self.series_defaults:
            defaults = self.series_defaults[series_identifier]
            reset_zoom = defaults.get('zoom')
            reset_h_scroll = defaults.get('h_scroll')
            reset_v_scroll = defaults.get('v_scroll')
            reset_scene_center = defaults.get('scene_center')  # Preferred: scene center point
            reset_window_center = defaults.get('window_center')
            reset_window_width = defaults.get('window_width')
            reset_use_rescaled_values = defaults.get('use_rescaled_values')
        else:
            # Fall back to global initial values
            reset_zoom = self.initial_zoom
            reset_h_scroll = self.initial_h_scroll
            reset_v_scroll = self.initial_v_scroll
            reset_scene_center = self.initial_scene_center  # Preferred: scene center point
            reset_window_center = self.initial_window_center
            reset_window_width = self.initial_window_width
            reset_use_rescaled_values = None
        
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
                center_range = (pixel_min, pixel_max)
                width_range = (1.0, max(1.0, pixel_max - pixel_min))
                self.window_level_controls.set_ranges(center_range, width_range)
            
            # Update window/level unit labels
            unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
            self.window_level_controls.set_unit(unit)
        
        # Reset window/level to initial values (already in correct units for current rescale state)
        if reset_window_center is not None and reset_window_width is not None:
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
                    
                    # Now set up the view: zoom, transform, and centering
                    # Prefer scene center point (works correctly even if viewport size changed)
                    # Fall back to scrollbar positions for backward compatibility
                    self.image_viewer.resetTransform()
                    self.image_viewer.scale(reset_zoom, reset_zoom)
                    self.image_viewer.current_zoom = reset_zoom
                    
                    # Use scene center point if available (preferred method)
                    if reset_scene_center is not None:
                        # Center on the stored scene point - works correctly regardless of viewport size
                        self.image_viewer.centerOn(reset_scene_center)
                    elif reset_h_scroll is not None and reset_v_scroll is not None:
                        # Fallback: restore scrollbar positions (for backward compatibility)
                        # This may not work correctly if viewport size has changed
                        self.image_viewer.horizontalScrollBar().setValue(reset_h_scroll)
                        self.image_viewer.verticalScrollBar().setValue(reset_v_scroll)
                    else:
                        # No saved positions - use fit_to_view with centering
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
                    if self.roi_coordinator:
                        self.roi_coordinator(dataset)
    
    def handle_window_changed(self, center: float, width: float) -> None:
        """
        Handle window/level change.
        
        Args:
            center: Window center
            width: Window width
        """
        # Store current window/level values
        self.current_window_center = center
        self.current_window_width = width
        self.window_level_user_modified = True  # Mark as user-modified
        
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
        
        Args:
            zoom_level: Current zoom level
        """
        # Note: Overlay position updates are handled by handle_transform_changed
        # which fires after the transform is fully applied
        pass
    
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
        Handle viewport resize (when splitter moves).
        
        Updates overlay positions to keep text anchored to viewport edges
        when the left or right panels are resized.
        Also restores the centered view if a scene center was captured.
        """
        # Restore centered view if we captured a scene center point
        if self.saved_scene_center is not None and self.image_viewer.image_item is not None:
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
    
    def reset_series_tracking(self) -> None:
        """Reset series tracking when loading new files."""
        self.current_series_identifier = None
        # Note: We keep series_defaults to preserve across file loads if desired
        # If you want to clear them, uncomment: self.series_defaults.clear()
    
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

