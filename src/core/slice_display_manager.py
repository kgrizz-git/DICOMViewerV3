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
import numpy as np
from PIL import Image
from pydicom.dataset import Dataset
from core.dicom_processor import DICOMProcessor
from core.dicom_parser import DICOMParser
from core.dicom_organizer import DICOMOrganizer
from gui.image_viewer import ImageViewer
from gui.metadata_panel import MetadataPanel
from gui.slice_navigator import SliceNavigator
from gui.window_level_controls import WindowLevelControls
from tools.roi_manager import ROIManager
from tools.measurement_tool import MeasurementTool
from tools.annotation_manager import AnnotationManager
from gui.overlay_manager import OverlayManager
from gui.roi_list_panel import ROIListPanel
from gui.roi_statistics_panel import ROIStatisticsPanel
from utils.dicom_utils import get_pixel_spacing, get_slice_thickness, get_composite_series_key


class SliceDisplayManager:
    """
    Manages slice display, ROI/measurement display, and series navigation.
    
    Responsibilities:
    - Display DICOM slices
    - Display ROIs for current slice
    - Display measurements for current slice
    - Handle slice navigation
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
        roi_statistics_panel: Optional[ROIStatisticsPanel] = None,
        update_roi_statistics_overlays_callback: Optional[Callable] = None,
        annotation_manager: Optional[AnnotationManager] = None,
        dicom_organizer: Optional[DICOMOrganizer] = None
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
            annotation_manager: Optional annotation manager for Presentation State and Key Object annotations
            dicom_organizer: Optional DICOM organizer for accessing Presentation States and Key Objects
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
        self.update_roi_statistics_overlays_callback = update_roi_statistics_overlays_callback
        self.annotation_manager = annotation_manager
        self.dicom_organizer = dicom_organizer
        
        # Current data context
        self.current_studies: dict = {}
        self.current_study_uid: str = ""
        self.current_series_uid: str = ""
        self.current_slice_index: int = 0
        self.current_dataset: Optional[Dataset] = None
        
        # Intensity projection state
        self.projection_enabled: bool = False
        self.projection_type: str = "aip"  # "aip", "mip", or "minip"
        self.projection_slice_count: int = 4  # 2, 3, 4, 6, or 8
    
    def reset_projection_state(self) -> None:
        """
        Reset intensity projection state to defaults.
        
        Called when new series/file is opened, Reset View is selected, or file is closed.
        """
        self.projection_enabled = False
        self.projection_type = "aip"
        self.projection_slice_count = 4
    
    def set_projection_enabled(self, enabled: bool) -> None:
        """
        Set projection enabled state.
        
        Args:
            enabled: True to enable projection mode, False to disable
        """
        self.projection_enabled = enabled
    
    def set_projection_type(self, projection_type: str) -> None:
        """
        Set projection type.
        
        Args:
            projection_type: "aip", "mip", or "minip"
        """
        if projection_type in ["aip", "mip", "minip"]:
            self.projection_type = projection_type
    
    def set_projection_slice_count(self, count: int) -> None:
        """
        Set number of slices to combine for projection.
        
        Args:
            count: Number of slices (2, 3, 4, 6, or 8)
        """
        if count in [2, 3, 4, 6, 8]:
            self.projection_slice_count = count
    
    def _create_projection_image(
        self,
        dataset: Dataset,
        current_studies: dict,
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
        window_center: Optional[float],
        window_width: Optional[float],
        use_rescaled_values: bool,
        rescale_slope: Optional[float],
        rescale_intercept: Optional[float]
    ) -> Optional[Image.Image]:
        """
        Create a projection image from multiple slices.
        
        Args:
            dataset: Current dataset (for metadata)
            current_studies: Dictionary of studies
            current_study_uid: Current study UID
            current_series_uid: Current series UID
            current_slice_index: Current slice index
            window_center: Window center value
            window_width: Window width value
            use_rescaled_values: Whether to use rescaled values
            rescale_slope: Rescale slope
            rescale_intercept: Rescale intercept
            
        Returns:
            PIL Image or None if projection failed
        """
        # Get series datasets
        if not current_studies or not current_study_uid or not current_series_uid:
            return None
        
        if (current_study_uid not in current_studies or 
            current_series_uid not in current_studies[current_study_uid]):
            return None
        
        series_datasets = current_studies[current_study_uid][current_series_uid]
        total_slices = len(series_datasets)
        
        if total_slices < 2:
            # Need at least 2 slices for projection
            return None
        
        # Calculate slice range
        # Start from current_slice_index, gather projection_slice_count slices
        start_slice = max(0, current_slice_index)
        end_slice = min(total_slices - 1, current_slice_index + self.projection_slice_count - 1)
        
        # Ensure we have at least 2 slices
        if end_slice - start_slice + 1 < 2:
            # Not enough slices available
            return None
        
        # Gather slices for projection
        projection_slices = []
        for i in range(start_slice, end_slice + 1):
            if 0 <= i < total_slices:
                projection_slices.append(series_datasets[i])
        
        if len(projection_slices) < 2:
            return None
        
        # Calculate projection based on type
        projection_array = None
        if self.projection_type == "aip":
            projection_array = self.dicom_processor.average_intensity_projection(projection_slices)
        elif self.projection_type == "mip":
            projection_array = self.dicom_processor.maximum_intensity_projection(projection_slices)
        elif self.projection_type == "minip":
            projection_array = self.dicom_processor.minimum_intensity_projection(projection_slices)
        
        if projection_array is None:
            return None
        
        # Apply rescale if needed
        if use_rescaled_values and rescale_slope is not None and rescale_intercept is not None:
            projection_array = projection_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
        
        # Apply window/level
        if window_center is not None and window_width is not None:
            processed_array = self.dicom_processor.apply_window_level(
                projection_array,
                window_center,
                window_width
            )
        else:
            # No window/level, normalize to 0-255
            processed_array = projection_array.astype(np.float32)
            if processed_array.max() > processed_array.min():
                processed_array = ((processed_array - processed_array.min()) / 
                                 (processed_array.max() - processed_array.min()) * 255.0)
            processed_array = np.clip(processed_array, 0, 255).astype(np.uint8)
        
        # Convert to PIL Image
        try:
            if len(processed_array.shape) == 2:
                # Grayscale
                image = Image.fromarray(processed_array, mode='L')
            elif len(processed_array.shape) == 3 and processed_array.shape[2] == 3:
                # RGB
                image = Image.fromarray(processed_array, mode='RGB')
            else:
                # Fallback
                image = Image.fromarray(processed_array)
            return image
        except Exception as e:
            print(f"Error converting projection array to PIL Image: {e}")
            return None
    
    def display_slice(
        self,
        dataset: Dataset,
        current_studies: dict,
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
        preserve_view_override: Optional[bool] = None,
        update_controls: bool = True,
        update_metadata: bool = True
    ) -> None:
        """
        Display a DICOM slice.
        
        Args:
            dataset: pydicom Dataset
            current_studies: Dictionary of studies
            current_study_uid: Current study UID
            current_series_uid: Current series UID
            current_slice_index: Current slice index
            preserve_view_override: Optional override for preserving view state
            update_controls: If True, update the global window/level controls UI.
                           If False, only update internal ViewStateManager values.
                           Default is True for backward compatibility.
            update_metadata: If True, update the metadata panel with the new dataset.
                           If False, skip metadata panel update.
                           Default is True for backward compatibility.
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
            
            # Get composite series key from dataset to check if we're in the same series
            new_series_uid = get_composite_series_key(dataset)
            is_same_series = (new_series_uid == current_series_uid and current_series_uid != "")
            
            # Detect if this is a new study/series
            is_new_study_series = self.view_state_manager.is_new_study_or_series(dataset)
            series_identifier = self.view_state_manager.get_series_identifier(dataset)
            
            # Check for JPEGLS transfer syntax and show warning only for new series
            if is_new_study_series:
                jpegls_syntaxes = [
                    '1.2.840.10008.1.2.4.80',  # JPEG-LS Lossless
                    '1.2.840.10008.1.2.4.81',  # JPEG-LS Lossy
                ]
                if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                    transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                    if transfer_syntax in jpegls_syntaxes:
                        from PySide6.QtWidgets import QMessageBox
                        QMessageBox.warning(
                            self.image_viewer,
                            "JPEG-LS Image Warning",
                            "JPEG-LS transfer syntax detected.\n\n"
                            "Pixel values may not be correct, especially for color images.\n"
                            "This is a known issue with JPEG-LS compression."
                        )
            
            # DEBUG: Track series detection
            modality = getattr(dataset, 'Modality', 'Unknown')
            # print(f"[DEBUG-WL] display_slice: modality={modality}, is_new_study_series={is_new_study_series}, series_id={series_identifier[:20]}...")
            
            # Set default use_rescaled_values based on whether parameters exist
            # Default to True if parameters exist, False otherwise
            if is_new_study_series:
                use_rescaled = (rescale_slope is not None and rescale_intercept is not None)
                self.view_state_manager.use_rescaled_values = use_rescaled
                # print(f"[DEBUG-WL] NEW SERIES: Setting use_rescaled_values={use_rescaled} (slope={rescale_slope}, intercept={rescale_intercept})")
                # Update UI toggle state
                from gui.main_window import MainWindow
                if hasattr(self.view_state_manager, 'main_window'):
                    self.view_state_manager.main_window.set_rescale_toggle_state(use_rescaled)
                self.image_viewer.set_rescale_toggle_state(use_rescaled)
                # Update current series identifier
                self.view_state_manager.set_current_series_identifier(series_identifier)
                # Clear window/level state for new study/series to prevent stale values from previous study
                # This must be done before any recalculation to ensure we don't use old values
                self.view_state_manager.current_window_center = None
                self.view_state_manager.current_window_width = None
                self.view_state_manager.window_level_user_modified = False
            
            # Get window/level values from view state manager
            # For new series, these should be None (we just cleared them above)
            window_center = self.view_state_manager.current_window_center
            window_width = self.view_state_manager.current_window_width
            # print(f"[DEBUG-WL] display_slice: Using window_center={window_center}, window_width={window_width}")
            # print(f"[DEBUG-WL]   is_new_study_series={is_new_study_series}, is_same_series={is_same_series}")
            # For new series, use the rescale state we just set; for same series, use existing state
            if is_new_study_series:
                use_rescaled_values = (rescale_slope is not None and rescale_intercept is not None)
            else:
                use_rescaled_values = self.view_state_manager.use_rescaled_values
            
            # For new series, always recalculate window/level defaults from the current dataset
            # Never use stored defaults for new datasets - this ensures CT gets CT defaults, not MR defaults
            if is_new_study_series:
                # Ensure window/level values are None before recalculation
                # This prevents using any stale values from previous datasets
                window_center = None
                window_width = None
                stored_window_center = None
                stored_window_width = None
                
                # Calculate window/level from series or dataset using the correct rescale state
                # use_rescaled_values was set above based on current dataset's rescale parameters
                study_uid = getattr(dataset, 'StudyInstanceUID', '')
                if study_uid and new_series_uid and current_studies:
                    if study_uid in current_studies and new_series_uid in current_studies[study_uid]:
                        series_datasets = current_studies[study_uid][new_series_uid]
                        # Calculate pixel range for entire series
                        # Wrap in try-except to handle any errors from pixel array access
                        try:
                            series_pixel_min, series_pixel_max = self.dicom_processor.get_series_pixel_value_range(
                                series_datasets, apply_rescale=use_rescaled_values
                            )
                            # Store series pixel range in ViewStateManager for window width slider maximum
                            self.view_state_manager.set_series_pixel_range(series_pixel_min, series_pixel_max)
                        except Exception as e:
                            # If series pixel range calculation fails, log and continue with single slice
                            error_type = type(e).__name__
                            print(f"Error calculating series pixel range ({error_type}): {e}")
                            series_pixel_min = None
                            series_pixel_max = None
                            # Clear stored series pixel range on error
                            self.view_state_manager.clear_series_pixel_range()
                        # Check for window/level presets in DICOM metadata
                        presets = self.dicom_processor.get_window_level_presets_from_dataset(
                            dataset,
                            rescale_slope=rescale_slope,
                            rescale_intercept=rescale_intercept
                        )
                        
                        # print(f"[DEBUG-WL-PRESETS] SliceDisplayManager: Extracted {len(presets)} preset(s)")
                        # if presets:
                        #     for idx, (wc, ww, is_rescaled, name) in enumerate(presets):
                        #         print(f"[DEBUG-WL-PRESETS]   Preset {idx}: center={wc}, width={ww}, is_rescaled={is_rescaled}, name={name}")
                        
                        # Store presets in view state manager BEFORE setting window/level
                        # This ensures that handle_window_changed can match values to presets
                        # Rescale parameters were already set at line 153, so they're available for comparison
                        # print(f"[DEBUG-PRESET-MATCH] Storing {len(presets)} preset(s) in view_state_manager")
                        # print(f"[DEBUG-PRESET-MATCH] Current rescale state: use_rescaled={use_rescaled_values}, slope={rescale_slope}, intercept={rescale_intercept}")
                        # for idx, (wc, ww, is_rescaled, name) in enumerate(presets):
                        #     print(f"[DEBUG-PRESET-MATCH]   Preset {idx}: wc={wc:.2f}, ww={ww:.2f}, is_rescaled={is_rescaled}, name={name}")
                        self.view_state_manager.window_level_presets = presets
                        self.view_state_manager.current_preset_index = 0  # Use first preset by default
                        # Reset user-modified flag since we're loading presets
                        self.view_state_manager.window_level_user_modified = False
                        # print(f"[DEBUG-WL-PRESETS] SliceDisplayManager: Stored {len(presets)} preset(s) in view_state_manager")
                        
                        # Get window/level from first preset if available, otherwise use single value method
                        if presets:
                            # Use first preset (index 0)
                            wc, ww, is_rescaled, _ = presets[0]
                            # print(f"[DEBUG-WL-PRESETS] SliceDisplayManager: Using first preset: center={wc}, width={ww}")
                        else:
                            # Fall back to single value extraction
                            wc, ww, is_rescaled = self.dicom_processor.get_window_level_from_dataset(
                                dataset,
                                rescale_slope=rescale_slope,
                                rescale_intercept=rescale_intercept
                            )
                            # print(f"[DEBUG-WL-PRESETS] SliceDisplayManager: No presets found, using single value extraction: center={wc}, width={ww}")
                        # print(f"[DEBUG-WL] From DICOM tags: wc={wc}, ww={ww}, is_rescaled={is_rescaled}, need_use_rescaled={use_rescaled_values}")
                        if wc is not None and ww is not None:
                            # Convert if needed
                            if is_rescaled and not use_rescaled_values:
                                if (rescale_slope is not None and rescale_intercept is not None and rescale_slope != 0.0):
                                    orig_wc, orig_ww = wc, ww
                                    wc, ww = self.dicom_processor.convert_window_level_rescaled_to_raw(
                                        wc, ww, rescale_slope, rescale_intercept
                                    )
                                    # print(f"[DEBUG-WL] Converted rescaled->raw: ({orig_wc}, {orig_ww}) -> ({wc}, {ww})")
                            elif not is_rescaled and use_rescaled_values:
                                if (rescale_slope is not None and rescale_intercept is not None):
                                    orig_wc, orig_ww = wc, ww
                                    wc, ww = self.dicom_processor.convert_window_level_raw_to_rescaled(
                                        wc, ww, rescale_slope, rescale_intercept
                                    )
                                    # print(f"[DEBUG-WL] Converted raw->rescaled: ({orig_wc}, {orig_ww}) -> ({wc}, {ww})")
                            stored_window_center = wc
                            stored_window_width = ww
                            # print(f"[DEBUG-WL] Using DICOM tag values: stored_wc={stored_window_center}, stored_ww={stored_window_width}")
                        elif series_pixel_min is not None and series_pixel_max is not None:
                            # Calculate median from series for window center
                            # Get series datasets for median calculation (already have series_datasets from above)
                            midpoint = (series_pixel_min + series_pixel_max) / 2.0
                            if series_datasets:
                                median = self.dicom_processor.get_series_pixel_median(
                                    series_datasets, apply_rescale=use_rescaled_values
                                )
                                # If median calculation failed, use midpoint
                                if median is None:
                                    stored_window_center = midpoint
                                else:
                                    # Use the greater of median or midpoint
                                    stored_window_center = max(median, midpoint)
                            else:
                                stored_window_center = midpoint
                            
                            stored_window_width = series_pixel_max - series_pixel_min
                            if stored_window_width <= 0:
                                stored_window_width = 1.0
                            # print(f"[DEBUG-WL] Calculated from series pixel range: stored_wc={stored_window_center}, stored_ww={stored_window_width}")
                        else:
                            # Fallback to single slice
                            try:
                                pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                                    dataset, apply_rescale=use_rescaled_values
                                )
                                if pixel_min is not None and pixel_max is not None:
                                    # Calculate median from single slice pixel array
                                    pixel_array = self.dicom_processor.get_pixel_array(dataset)
                                    if pixel_array is not None:
                                        # Apply rescale if needed
                                        if use_rescaled_values:
                                            rescale_slope, rescale_intercept, _ = self.dicom_processor.get_rescale_parameters(dataset)
                                            if rescale_slope is not None and rescale_intercept is not None:
                                                pixel_array = pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
                                        # Calculate both median (excluding zeros) and midpoint, use the greater value
                                        midpoint = (pixel_min + pixel_max) / 2.0
                                        non_zero_values = pixel_array[pixel_array != 0]
                                        if len(non_zero_values) > 0:
                                            median = float(np.median(non_zero_values))
                                            stored_window_center = max(median, midpoint)
                                        else:
                                            # Fallback to midpoint if all values are zero
                                            stored_window_center = midpoint
                                    else:
                                        # Fall back to midpoint if pixel array unavailable
                                        stored_window_center = (pixel_min + pixel_max) / 2.0
                                    stored_window_width = pixel_max - pixel_min
                                    if stored_window_width <= 0:
                                        stored_window_width = 1.0
                            except Exception as e:
                                # If single slice pixel range calculation fails, use defaults
                                error_type = type(e).__name__
                                print(f"Error calculating single slice pixel range ({error_type}): {e}")
                                # Will fall through to use window/level from DICOM tags or defaults
                        self.view_state_manager.window_level_user_modified = False
                
                # Set window/level values - ensure we only use newly calculated values
                # stored_window_center and stored_window_width are calculated above with correct rescale state
                if stored_window_center is not None and stored_window_width is not None:
                    window_center = stored_window_center
                    window_width = stored_window_width
                    # print(f"[DEBUG-WL] Storing in view_state_manager: wc={window_center}, ww={window_width}, use_rescaled={use_rescaled_values}")
                    # Store in view state manager - these are the correct defaults for this dataset
                    self.view_state_manager.current_window_center = window_center
                    self.view_state_manager.current_window_width = window_width
                    
                    # Update status bar widget with zoom and preset info
                    current_zoom = self.image_viewer.current_zoom
                    if self.view_state_manager.window_level_presets:
                        preset_name = "Default" if self.view_state_manager.current_preset_index == 0 else (
                            self.view_state_manager.window_level_presets[self.view_state_manager.current_preset_index][3] or "Default"
                        )
                        # print(f"[DEBUG-PRESET-MATCH] Updating status bar with preset: {preset_name} (index={self.view_state_manager.current_preset_index})")
                        self.view_state_manager.main_window.update_zoom_preset_status(current_zoom, preset_name)
                    elif window_center is not None and window_width is not None:
                        # No presets found, using calculated values
                        # print(f"[DEBUG-PRESET-MATCH] Updating status bar with Auto-Calculated (no presets found)")
                        self.view_state_manager.main_window.update_zoom_preset_status(current_zoom, None)
                    
                    # Store defaults for this series (will be updated with zoom/pan after fit_to_view)
                    # Store with the rescale state that was used to calculate them
                    # Mark window/level as "initial defaults set" so store_initial_view_state doesn't overwrite
                    if series_identifier not in self.view_state_manager.series_defaults:
                        self.view_state_manager.series_defaults[series_identifier] = {}
                    self.view_state_manager.series_defaults[series_identifier].update({
                        'window_center': window_center,
                        'window_width': window_width,
                        'use_rescaled_values': use_rescaled_values,  # Store the rescale state used for calculation
                        'image_inverted': self.image_viewer.image_inverted,  # Store current inversion state
                        'window_level_defaults_set': True  # Flag to prevent overwriting by store_initial_view_state
                    })
                    # print(f"[DEBUG-WL] Stored INITIAL defaults in series_defaults with flag")
                else:
                    # If calculation failed, ensure window/level remains None
                    window_center = None
                    window_width = None
                    self.view_state_manager.current_window_center = None
                    self.view_state_manager.current_window_width = None
            
            # For same series, preserve existing window/level values (already set above)
            
            # Convert to image
            image = None
            # Check if projection mode is enabled
            if self.projection_enabled:
                # Projection mode: gather slices and calculate projection
                try:
                    image = self._create_projection_image(
                        dataset,
                        current_studies,
                        current_study_uid,
                        current_series_uid,
                        current_slice_index,
                        window_center,
                        window_width,
                        use_rescaled_values,
                        rescale_slope,
                        rescale_intercept
                    )
                    if image is None:
                        # Projection failed (e.g., not enough slices available near end of dataset)
                        # Fall back to normal display but keep projection enabled
                        # so it works again when scrolling to a valid position
                        # Continue with normal dataset conversion below
                        pass
                except Exception as e:
                    # Projection error - fall back to normal display
                    # Only disable on actual errors, not just insufficient slices
                    error_type = type(e).__name__
                    print(f"Error creating projection image ({error_type}): {e}")
                    # Don't disable projection mode for insufficient slices - only for actual errors
                    # Keep projection enabled so user can scroll back and it will work again
                    # Continue with normal dataset conversion below
                    pass
            
            # Normal mode or projection fallback: convert single dataset to image
            # If projection failed (image is None) or projection is disabled, convert normally
            if image is None:
                # If same series and we have preserved window/level values, use them
                # print(f"[DEBUG-WL] About to convert dataset to image...")
                # print(f"[DEBUG-WL]   Window center: {window_center}, Window width: {window_width}")
                # print(f"[DEBUG-WL]   Use rescaled values: {use_rescaled_values}")
                # print(f"[DEBUG-WL]   is_same_series: {is_same_series}")
                try:
                    if is_same_series and window_center is not None and window_width is not None:
                        # print(f"[DEBUG-WL] Converting with stored window/level: center={window_center}, width={window_width}")
                        image = self.dicom_processor.dataset_to_image(
                            dataset,
                            window_center=window_center,
                            window_width=window_width,
                            apply_rescale=use_rescaled_values
                        )
                    else:
                        # print(f"[DEBUG-WL] Converting with auto window/level (is_same_series={is_same_series}, window_center={window_center}, window_width={window_width})")
                        image = self.dicom_processor.dataset_to_image(
                            dataset,
                            apply_rescale=use_rescaled_values
                        )
                    # print(f"[DISPLAY] Image conversion complete: {image is not None}")
                    if image is None:
                        # Image conversion failed - this is already handled by dataset_to_image returning None
                        # print(f"[DISPLAY] Image is None, returning")
                        return
                except (MemoryError, ValueError, AttributeError, RuntimeError) as e:
                    # Pixel array access errors during image conversion
                    error_type = type(e).__name__
                    error_msg = f"Error converting dataset to image ({error_type}): {str(e)}"
                    # print(error_msg)
                    # Re-raise to be caught by outer exception handler
                    raise RuntimeError(error_msg) from e
                except Exception as e:
                    # Other unexpected errors
                    error_type = type(e).__name__
                    error_msg = f"Unexpected error converting dataset to image ({error_type}): {str(e)}"
                    # print(error_msg)
                    raise RuntimeError(error_msg) from e
            
            # Restore inversion state for this series if it exists
            # Only pass apply_inversion when preserve_view=False (new slice)
            # When preserve_view=True (scrolling), pass None so set_image() knows it's a new slice
            apply_inversion = None
            preserve_view = is_same_series and not is_new_study_series
            force_fit_to_view = False
            if preserve_view_override is not None:
                preserve_view = preserve_view_override
                force_fit_to_view = not preserve_view_override
            if not preserve_view:
                # New slice - apply stored inversion state if it exists
                if series_identifier and series_identifier in self.view_state_manager.series_defaults:
                    # Series has stored state - get inversion value
                    series_inverted = self.view_state_manager.get_series_inversion_state(series_identifier)
                    # Pass inversion state for new slice
                    apply_inversion = series_inverted
            # When preserve_view=True (scrolling), apply_inversion stays None
            # This allows set_image() to detect it's a new slice and store new original_image
            
            # Set image in viewer - preserve zoom/pan if same series
            # print(f"[DISPLAY] About to set image in viewer...")
            # print(f"[DISPLAY] Slice index: {current_slice_index}, Preserve view: {preserve_view}")
            # print(f"[DISPLAY] Image size: {image.size if image else 'None'}, mode: {image.mode if image else 'None'}")
            # print(f"[DISPLAY] Image id: {id(image) if image else 'None'}")
            # print(f"[DISPLAY] Apply inversion: {apply_inversion}")
            self.image_viewer.set_image(image, preserve_view=preserve_view, apply_inversion=apply_inversion)
            # print(f"[DISPLAY] Image set in viewer successfully")
            
            # If new study/series or explicitly requested, fit to view and center
            if is_new_study_series or force_fit_to_view:
                self.image_viewer.fit_to_view(center_image=True)
                if is_new_study_series:
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
            
            # Update metadata panel (only for focused subwindow)
            if update_metadata:
                self.metadata_panel.set_dataset(dataset)
            
            # Update tag viewer if open
            if self.update_tag_viewer_callback:
                self.update_tag_viewer_callback(dataset)
            
            # Calculate pixel value range for window/level controls
            pixel_min = None
            pixel_max = None
            try:
                pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                    dataset, apply_rescale=use_rescaled_values
                )
                if pixel_min is not None and pixel_max is not None:
                    # Get series pixel range for both center and width ranges
                    series_pixel_min, series_pixel_max = self.view_state_manager.get_series_pixel_range()
                    
                    if series_pixel_min is not None and series_pixel_max is not None:
                        # Use series range for both center and width ranges
                        center_range = (series_pixel_min, series_pixel_max)
                        width_range = (1.0, max(1.0, series_pixel_max - series_pixel_min))
                    else:
                        # Fallback to current slice range if series range not available
                        center_range = (pixel_min, pixel_max)
                        width_range = (1.0, max(1.0, pixel_max - pixel_min))
                    
                    if update_controls:
                        self.window_level_controls.set_ranges(center_range, width_range)
            except Exception as e:
                # If pixel value range calculation fails, use default ranges
                error_type = type(e).__name__
                print(f"Error calculating pixel value range for window/level controls ({error_type}): {e}")
                # Continue without setting ranges - controls will use defaults
            
            # Update window/level controls unit label
            unit = rescale_type if (use_rescaled_values and rescale_type) else None
            if update_controls:
                self.window_level_controls.set_unit(unit)
            
            # Update window/level controls with current values
            # Validate window/level values are within current dataset's pixel range
            # This ensures correct values when switching between different modalities
            # For new series, we've already calculated correct defaults above, so skip validation
            if not is_new_study_series and window_center is not None and window_width is not None and pixel_min is not None and pixel_max is not None:
                # Get current pixel range to validate window/level values
                series_pixel_min, series_pixel_max = self.view_state_manager.get_series_pixel_range()
                
                # Use series range if available, otherwise use current slice range
                if series_pixel_min is not None and series_pixel_max is not None:
                    valid_min = series_pixel_min
                    valid_max = series_pixel_max
                else:
                    valid_min = pixel_min
                    valid_max = pixel_max
                
                # Check if window/level values are within valid range
                # If not, recalculate defaults (this handles cases where values are from a different dataset)
                if (window_center < valid_min or window_center > valid_max or 
                    window_width < 1.0 or window_width > (valid_max - valid_min)):
                    # Values are outside valid range - recalculate defaults for same series
                    if valid_min is not None and valid_max is not None:
                        window_center = (valid_min + valid_max) / 2.0
                        window_width = valid_max - valid_min
                        if window_width <= 0:
                            window_width = 1.0
                        self.view_state_manager.current_window_center = window_center
                        self.view_state_manager.current_window_width = window_width
            
            if is_new_study_series and window_center is not None and window_width is not None:
                # New series - use calculated/stored defaults
                # print(f"[DEBUG-PRESET-MATCH] Setting window/level for new series: wc={window_center:.2f}, ww={window_width:.2f}, block_signals=True")
                if update_controls:
                    self.window_level_controls.set_window_level(
                        window_center, window_width, block_signals=True, unit=unit
                    )
            elif is_same_series and window_center is not None and window_width is not None:
                # Same series - preserve existing window/level values (if valid)
                # print(f"[DEBUG-PRESET-MATCH] Setting window/level for same series: wc={window_center:.2f}, ww={window_width:.2f}, block_signals=True")
                if update_controls:
                    self.window_level_controls.set_window_level(
                        window_center, window_width, block_signals=True, unit=unit
                    )
            else:
                # Only recalculate if values are truly missing (not for same series with valid values)
                if not is_same_series or (window_center is None or window_width is None):
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
                        # print(f"[DEBUG-PRESET-MATCH] Setting window/level from dataset: wc={wc:.2f}, ww={ww:.2f}, block_signals=True")
                        if update_controls:
                            self.window_level_controls.set_window_level(wc, ww, block_signals=True, unit=unit)
                        self.view_state_manager.current_window_center = wc
                        self.view_state_manager.current_window_width = ww
                    elif pixel_min is not None and pixel_max is not None:
                        # Use default window/level based on pixel range
                        default_center = (pixel_min + pixel_max) / 2.0
                        default_width = pixel_max - pixel_min
                        if default_width <= 0:
                            default_width = 1.0
                        # print(f"[DEBUG-PRESET-MATCH] Setting window/level from pixel range: wc={default_center:.2f}, ww={default_width:.2f}, block_signals=True")
                        if update_controls:
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
            
            # Calculate projection information if enabled
            projection_start_slice = None
            projection_end_slice = None
            projection_total_thickness = None
            
            if self.projection_enabled and total_slices > 0:
                # Calculate projection slice range using the same logic as _create_projection_image()
                projection_start_slice = max(0, current_slice_index)
                projection_end_slice = min(total_slices - 1, current_slice_index + self.projection_slice_count - 1)
                
                # Calculate total slice thickness by summing thickness from all slices in the range
                if (current_study_uid in current_studies and 
                    current_series_uid in current_studies[current_study_uid]):
                    series_datasets = current_studies[current_study_uid][current_series_uid]
                    
                    total_thickness = 0.0
                    thickness_count = 0
                    for i in range(projection_start_slice, projection_end_slice + 1):
                        if 0 <= i < len(series_datasets):
                            # series_datasets is a list of datasets (tuples were unpacked during organization)
                            slice_dataset = series_datasets[i]
                            thickness = get_slice_thickness(slice_dataset)
                            if thickness is not None:
                                total_thickness += thickness
                                thickness_count += 1
                    
                    # Only set total thickness if we found at least one valid thickness value
                    if thickness_count > 0:
                        projection_total_thickness = total_thickness
            
            self.overlay_manager.create_overlay_items(
                self.image_viewer.scene,
                parser,
                total_slices=total_slices if total_slices > 0 else None,
                projection_enabled=self.projection_enabled,
                projection_start_slice=projection_start_slice,
                projection_end_slice=projection_end_slice,
                projection_total_thickness=projection_total_thickness,
                projection_type=self.projection_type if self.projection_enabled else None
            )
            
            # Extract pixel spacing and set on measurement tool
            pixel_spacing = get_pixel_spacing(dataset)
            self.measurement_tool.set_pixel_spacing(pixel_spacing)
            
            # Set current slice context for ROI manager and measurements
            study_uid = getattr(dataset, 'StudyInstanceUID', '')
            series_uid = get_composite_series_key(dataset)
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
            
            # Display Presentation State and Key Object annotations
            if self.annotation_manager and self.dicom_organizer:
                try:
                    # Clear existing annotations first
                    self.annotation_manager.clear_annotations(self.image_viewer.scene)
                    
                    # Get annotations for this image
                    image_uid = getattr(dataset, 'SOPInstanceUID', 'unknown')
                    annotations = self.annotation_manager.get_annotations_for_image(
                        dataset, current_study_uid
                    )
                    
                    # DEBUG: Print what we found
                    # print(f"[ANNOTATIONS] Found {len(annotations)} annotation(s) for image {str(image_uid)[:30]}...")
                    # if annotations:
                    #     for i, ann in enumerate(annotations):
                    #         print(f"  Annotation {i}: type={ann.get('type')}, coords={ann.get('coordinates')}, text={ann.get('text', '')[:50]}, units={ann.get('units', 'N/A')}")
                    
                    if annotations:
                        # Get image dimensions for coordinate scaling
                        # Try to get actual image dimensions from dataset
                        image_width = 512  # Default
                        image_height = 512  # Default
                        
                        if hasattr(dataset, 'Columns') and hasattr(dataset, 'Rows'):
                            image_width = float(dataset.Columns)
                            image_height = float(dataset.Rows)
                        
                        # print(f"[ANNOTATIONS] Creating items with image size: {image_width}x{image_height}")
                        
                        # Create annotation graphics items
                        items = self.annotation_manager.create_presentation_state_items(
                            self.image_viewer.scene,
                            annotations,
                            image_width,
                            image_height
                        )
                        # print(f"[ANNOTATIONS] Created {len(items)} graphics item(s)")
                except Exception as e:
                    # Don't fail slice display if annotation display fails
                    import traceback
                    # print(f"[ANNOTATIONS] Error displaying annotations: {e}")
                    # traceback.print_exc()
                    pass
        
        except MemoryError as e:
            # Re-raise MemoryError with context for caller to handle
            error_msg = f"Memory error displaying slice: {str(e)}"
            # print(error_msg)
            raise MemoryError(error_msg) from e
        except Exception as e:
            # Re-raise with context for caller to handle
            error_type = type(e).__name__
            error_msg = f"Error displaying slice: {str(e)}"
            if error_type not in error_msg:
                error_msg = f"{error_type}: {error_msg}"
            # print(error_msg)
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
        series_uid = get_composite_series_key(dataset)
        # Use current_slice_index as instance identifier (array position)
        instance_identifier = self.current_slice_index
        # print(f"[ROI DEBUG] display_rois_for_slice retrieving ROIs with instance_identifier={instance_identifier} (self.current_slice_index)")
        
        # Get all ROIs for this slice using composite key
        rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
        # print(f"[DEBUG-OVERLAY] display_rois_for_slice: scene={id(self.image_viewer.scene)}, "
        #       f"roi_manager={id(self.roi_manager)}, found {len(rois)} ROIs for slice {instance_identifier}")
        
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
                    # Remove statistics overlay if present
                    if roi.statistics_overlay_item is not None:
                        if roi.statistics_overlay_item.scene() == self.image_viewer.scene:
                            self.image_viewer.scene.removeItem(roi.statistics_overlay_item)
                        roi.statistics_overlay_item = None
                    # Only remove if item actually belongs to this scene
                    if item.scene() == self.image_viewer.scene:
                        self.image_viewer.scene.removeItem(item)
        
        # Add ROIs for current slice to scene if not already there
        # Force refresh to ensure visibility after image changes
        for i, roi in enumerate(rois):
            roi_scene = roi.item.scene() if roi.item else None
            if roi_scene == self.image_viewer.scene:
                # Already in scene, but ensure it's visible and has correct Z-value
                roi.item.setZValue(100)  # Above image but below overlay
                roi.item.show()  # Ensure visible
                print(f"  ROI {i} already in scene {id(self.image_viewer.scene)}")
            else:
                # Not in scene, add it
                print(f"  ROI {i} not in scene, adding to scene {id(self.image_viewer.scene)} (was in {id(roi_scene)})")
                self.image_viewer.scene.addItem(roi.item)
                # Ensure ROI is visible (set appropriate Z-value)
                roi.item.setZValue(100)  # Above image but below overlay
        
        # Update ROI list panel to show only ROIs for current slice
        if self.roi_list_panel is not None:
            self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
        
        # Update ROI statistics overlays
        if self.update_roi_statistics_overlays_callback is not None:
            # print(f"[DEBUG-OVERLAY] display_rois_for_slice: Calling update_roi_statistics_overlays_callback")
            self.update_roi_statistics_overlays_callback()
        
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
        series_uid = get_composite_series_key(dataset)
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
        # print(f"[SLICE] handle_slice_changed called with slice_index: {slice_index}")
        if not self.current_studies or not self.current_series_uid:
            return
        
        datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
        if 0 <= slice_index < len(datasets):
            self.current_slice_index = slice_index
            dataset = datasets[slice_index]
            # print(f"[SLICE] Dataset SOPInstanceUID: {getattr(dataset, 'SOPInstanceUID', 'N/A')}")
            # print(f"[SLICE] Dataset InstanceNumber: {getattr(dataset, 'InstanceNumber', 'N/A')}")
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
            print(f"[DEBUG] handle_series_navigation: No studies or study_uid. "
                  f"studies={bool(self.current_studies)}, study_uid={self.current_study_uid[:20] if self.current_study_uid else 'None'}...")
            return None, None, None
        
        # Get all series for current study
        study_series = self.current_studies[self.current_study_uid]
        
        # Check if there are multiple series
        if len(study_series) <= 1:
            print(f"[DEBUG] handle_series_navigation: Only {len(study_series)} series in study, cannot navigate")
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
        
        print(f"[DEBUG] handle_series_navigation: Found {len(series_list)} series in study. "
              f"Looking for current_series_uid={self.current_series_uid[:20] if self.current_series_uid else 'None'}...")
        
        # Find current series in sorted list
        current_index = None
        for idx, (_, series_uid, _) in enumerate(series_list):
            if series_uid == self.current_series_uid:
                current_index = idx
                break
        
        if current_index is None:
            print(f"[DEBUG] handle_series_navigation: Current series not found in sorted list. "
                  f"Available series UIDs: {[uid[:20] + '...' for _, uid, _ in series_list[:3]]} (showing first 3)")
            return None, None, None  # Current series not found
        
        print(f"[DEBUG] handle_series_navigation: Current series found at index {current_index} of {len(series_list)}")
        
        # Calculate new series index
        new_index = current_index + direction
        
        # Clamp to valid range
        if new_index < 0 or new_index >= len(series_list):
            print(f"[DEBUG] handle_series_navigation: New index {new_index} out of range [0, {len(series_list)})")
            return None, None, None  # Already at first or last series
        
        # Get new series UID and datasets
        _, new_series_uid, datasets = series_list[new_index]
        
        if not datasets:
            print(f"[DEBUG] handle_series_navigation: New series {new_series_uid[:20] if new_series_uid else 'None'}... has no datasets")
            return None, None, None
        
        print(f"[DEBUG] handle_series_navigation: Successfully navigating from index {current_index} to {new_index}, "
              f"new_series_uid={new_series_uid[:20]}...")
        
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

