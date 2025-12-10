"""
Fusion Coordinator

This module coordinates image fusion operations between the fusion handler,
processor, controls, and display components.

Inputs:
    - Fusion control changes from UI
    - Series and slice changes from application
    
Outputs:
    - Fused images for display
    - Status updates to UI
    
Requirements:
    - FusionHandler for state management
    - FusionProcessor for image blending
    - FusionControlsWidget for UI
"""

from typing import Optional, Callable, Dict, List, Tuple
from collections.abc import Sequence
import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

from core.fusion_handler import FusionHandler
from core.fusion_processor import FusionProcessor
from core.dicom_processor import DICOMProcessor
from gui.fusion_controls_widget import FusionControlsWidget


class FusionCoordinator:
    """
    Coordinates image fusion operations and UI updates.
    
    Responsibilities:
    - Handle fusion control changes
    - Generate fused images
    - Update series lists
    - Manage fusion state
    - Auto-detect compatible series
    """
    
    def __init__(
        self,
        fusion_handler: FusionHandler,
        fusion_processor: FusionProcessor,
        fusion_controls: FusionControlsWidget,
        get_current_studies: Callable[[], Dict],
        get_current_study_uid: Callable[[], str],
        get_current_series_uid: Callable[[], str],
        get_current_slice_index: Callable[[], int],
        request_display_update: Callable[[], None]
    ):
        """
        Initialize fusion coordinator.
        
        Args:
            fusion_handler: FusionHandler instance
            fusion_processor: FusionProcessor instance
            fusion_controls: FusionControlsWidget instance
            get_current_studies: Callback to get current studies dict
            get_current_study_uid: Callback to get current study UID
            get_current_series_uid: Callback to get current series UID
            get_current_slice_index: Callback to get current slice index
            request_display_update: Callback to request display refresh
        """
        self.fusion_handler = fusion_handler
        self.fusion_processor = fusion_processor
        self.fusion_controls = fusion_controls
        self.get_current_studies = get_current_studies
        self.get_current_study_uid = get_current_study_uid
        self.get_current_series_uid = get_current_series_uid
        self.get_current_slice_index = get_current_slice_index
        self.request_display_update = request_display_update
        
        # Connect signals
        self._connect_signals()
        
        # Track last auto-detection to avoid repeated prompts
        self._last_auto_detection_study = ""
        self._last_base_display = ""
    
    def set_base_series(self, series_uid: str) -> None:
        """Set base series programmatically (read-only in UI)."""
        if not series_uid:
            return
        if self.fusion_handler.base_series_uid == series_uid:
            return
        self.fusion_handler.set_base_series(series_uid)
        self._update_base_display(series_uid)
        self.fusion_controls.reset_user_modified_offset()
        if (
            self.fusion_handler.fusion_enabled
            and self.fusion_handler.overlay_series_uid
        ):
            if not self._apply_cached_alignment(reset_user_override=True):
                self._update_spatial_alignment()
    
    def _connect_signals(self) -> None:
        """Connect fusion control signals to handlers."""
        self.fusion_controls.fusion_enabled_changed.connect(self.handle_fusion_enabled_changed)
        self.fusion_controls.overlay_series_changed.connect(self.handle_overlay_series_changed)
        self.fusion_controls.opacity_changed.connect(self.handle_opacity_changed)
        self.fusion_controls.threshold_changed.connect(self.handle_threshold_changed)
        self.fusion_controls.colormap_changed.connect(self.handle_colormap_changed)
        self.fusion_controls.overlay_window_level_changed.connect(self.handle_overlay_window_level_changed)
        self.fusion_controls.translation_offset_changed.connect(self.handle_translation_offset_changed)
    
    def handle_fusion_enabled_changed(self, enabled: bool) -> None:
        """
        Handle fusion enabled/disabled.
        
        Args:
            enabled: True if fusion is enabled
        """
        self.fusion_handler.fusion_enabled = enabled
        
        if enabled:
            # Validate series selection
            if not self.fusion_handler.base_series_uid or not self.fusion_handler.overlay_series_uid:
                self.fusion_controls.set_status("Please select base and overlay series", is_error=True)
                return
            
            # Refresh window/level for overlay series if it's already set
            # This ensures correct values when enabling fusion with an existing overlay selection
            if self.fusion_handler.overlay_series_uid:
                self._refresh_overlay_window_level()
            
            # Apply cached alignment if available, otherwise calculate now
            applied_cached_alignment = self._apply_cached_alignment(reset_user_override=True)
            if not applied_cached_alignment:
                self._update_spatial_alignment()
            
            # Check Frame of Reference compatibility
            studies = self.get_current_studies()
            study_uid = self.get_current_study_uid()
            
            if study_uid in studies:
                base_datasets = studies[study_uid].get(self.fusion_handler.base_series_uid, [])
                overlay_datasets = studies[study_uid].get(self.fusion_handler.overlay_series_uid, [])
                
                if base_datasets and overlay_datasets:
                    if self.fusion_handler.check_frame_of_reference_match(base_datasets, overlay_datasets):
                        self.fusion_controls.set_status("Aligned (Frame of Reference)")
                    else:
                        self.fusion_controls.set_status("Warning: Different Frame of Reference", is_error=True)
                        # Note: Still allow fusion, but warn user
        else:
            self.fusion_controls.set_status("Disabled")
        
        # Request display update
        self.request_display_update()
    
    def _refresh_overlay_window_level(self) -> None:
        """
        Refresh window/level for the current overlay series.
        
        This is called when fusion is enabled to ensure window/level is correctly
        set for the overlay series, even if it was selected before fusion was enabled.
        """
        overlay_series_uid = self.fusion_handler.overlay_series_uid
        if not overlay_series_uid:
            return
        
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        
        if study_uid not in studies or overlay_series_uid not in studies[study_uid]:
            return
        
        datasets = studies[study_uid][overlay_series_uid]
        if not datasets:
            return
        
        # Use shared method with debugging and series-wide pixel ranges
        self._setup_overlay_window_level_with_debugging(overlay_series_uid, datasets)
    
    def _setup_overlay_window_level_with_debugging(self, series_uid: str, datasets: List[Dataset]) -> None:
        """
        Setup overlay window/level with comprehensive debugging and series-wide pixel range validation.
        
        This method extracts window/level from DICOM tags, validates against series-wide pixel ranges,
        and recalculates if needed. Uses entire series pixel range instead of just first slice.
        
        Args:
            series_uid: Overlay series UID (for debugging output)
            datasets: List of DICOM datasets for the overlay series
        """
        if not datasets:
            return
        
        first_dataset = datasets[0]
        
        # Extract rescale parameters to determine if W/L should be in rescaled units
        rescale_slope, rescale_intercept, rescale_type = DICOMProcessor.get_rescale_parameters(first_dataset)
        
        # Use DICOMProcessor's standard W/L extraction logic
        # This handles: DICOM tags first, then auto-calculates from pixel data if missing
        window_center, window_width, is_rescaled = DICOMProcessor.get_window_level_from_dataset(
            first_dataset,
            rescale_slope=rescale_slope,
            rescale_intercept=rescale_intercept
        )
        
        print(f"\n[OVERLAY W/L DEBUG] Overlay series: {series_uid[:28]}...")
        print(f"  Modality: {getattr(first_dataset, 'Modality', 'Unknown')}")
        print(f"  Rescale params: slope={rescale_slope}, intercept={rescale_intercept}, type={rescale_type}")
        print(f"  W/L from dataset: center={window_center}, width={window_width}, is_rescaled={is_rescaled}")
        
        if window_center is not None and window_width is not None:
            # Determine if we should apply rescale transformation for display/processing
            # Note: Pixel arrays from DICOM are always raw; rescale parameters indicate
            # we should apply rescale transformation (raw * slope + intercept) for display
            should_apply_rescale = (rescale_slope is not None and 
                                   rescale_intercept is not None and 
                                   rescale_slope != 0.0)
            
            final_window_width = window_width
            final_window_center = window_center
            
            # Convert window/level to match the units we'll use after applying rescale (if applicable)
            # DICOM window/level tags are typically in rescaled units when rescale parameters exist
            if should_apply_rescale:
                if is_rescaled:
                    # W/L tags are in rescaled units, and we'll apply rescale, so use directly
                    print(f"  Using W/L directly (W/L in rescaled units, will apply rescale to pixels)")
                else:
                    # W/L tags are in raw units, but we'll apply rescale, so convert W/L to rescaled units
                    final_window_center, final_window_width = DICOMProcessor.convert_window_level_raw_to_rescaled(
                        window_center, window_width, rescale_slope, rescale_intercept
                    )
                    print(f"  Converted W/L from raw to rescaled: ({window_center:.1f}, {window_width:.1f}) -> ({final_window_center:.1f}, {final_window_width:.1f})")
            else:
                if is_rescaled:
                    # W/L tags are in rescaled units, but we won't apply rescale, so convert W/L to raw units
                    final_window_center, final_window_width = DICOMProcessor.convert_window_level_rescaled_to_raw(
                        window_center, window_width, rescale_slope or 1.0, rescale_intercept or 0.0
                    )
                    print(f"  Converted W/L from rescaled to raw: ({window_center:.1f}, {window_width:.1f}) -> ({final_window_center:.1f}, {final_window_width:.1f})")
                else:
                    # W/L tags are in raw units, and we won't apply rescale, so use directly
                    print(f"  Using W/L directly (W/L in raw units, no rescale to apply)")
            
            # Validate window/level against series-wide pixel data
            # Use series-wide pixel range instead of just first slice
            series_raw_min, series_raw_max = DICOMProcessor.get_series_pixel_value_range(
                datasets, apply_rescale=False
            )
            
            if series_raw_min is not None and series_raw_max is not None:
                series_raw_range = series_raw_max - series_raw_min
                print(f"  [W/L VALIDATION] Raw pixel range (series-wide): [{series_raw_min:.1f}, {series_raw_max:.1f}] (range: {series_raw_range:.1f})")
                
                # Get rescaled series range if rescale should be applied
                series_rescaled_min = None
                series_rescaled_max = None
                if should_apply_rescale and rescale_slope is not None and rescale_intercept is not None:
                    series_rescaled_min, series_rescaled_max = DICOMProcessor.get_series_pixel_value_range(
                        datasets, apply_rescale=True
                    )
                    
                    if series_rescaled_min is not None and series_rescaled_max is not None:
                        series_rescaled_range = series_rescaled_max - series_rescaled_min
                        print(f"  [W/L VALIDATION] Rescaled pixel range (series-wide): [{series_rescaled_min:.1f}, {series_rescaled_max:.1f}] (range: {series_rescaled_range:.1f})")
                        print(f"  [W/L VALIDATION] Rescale formula: raw * {rescale_slope:.6f} + {rescale_intercept:.6f}")
                        # Verification: raw_max * slope + intercept should equal rescaled_max
                        expected_rescaled_max = series_raw_max * float(rescale_slope) + float(rescale_intercept)
                        print(f"  [W/L VALIDATION] Verification: raw_max * slope + intercept = {series_raw_max:.1f} * {rescale_slope:.6f} + {rescale_intercept:.6f} = {expected_rescaled_max:.1f} (matches rescaled_max {series_rescaled_max:.1f})")
                
                # Determine which pixel range to use for validation (rescaled if applicable, otherwise raw)
                pixel_min = series_rescaled_min if (should_apply_rescale and series_rescaled_min is not None) else series_raw_min
                pixel_max = series_rescaled_max if (should_apply_rescale and series_rescaled_max is not None) else series_raw_max
                pixel_range = pixel_max - pixel_min
                
                # Show DICOM W/L in both units for comparison
                print(f"  [W/L VALIDATION] DICOM W/L (from tags): center={window_center:.1f}, width={window_width:.1f}, is_rescaled={is_rescaled}")
                if should_apply_rescale:
                    if is_rescaled:
                        # DICOM tags are in rescaled units, show what they'd be in raw units
                        wl_raw = DICOMProcessor.convert_window_level_rescaled_to_raw(
                            window_center, window_width, rescale_slope, rescale_intercept
                        )
                        print(f"  [W/L VALIDATION] DICOM W/L in raw units: center={wl_raw[0]:.1f}, width={wl_raw[1]:.1f}")
                    else:
                        # DICOM tags are in raw units, show what they'd be in rescaled units
                        wl_rescaled = DICOMProcessor.convert_window_level_raw_to_rescaled(
                            window_center, window_width, rescale_slope, rescale_intercept
                        )
                        print(f"  [W/L VALIDATION] DICOM W/L in rescaled units: center={wl_rescaled[0]:.1f}, width={wl_rescaled[1]:.1f}")
                else:
                    if is_rescaled:
                        # DICOM tags are in rescaled units, show what they'd be in raw units
                        wl_raw = DICOMProcessor.convert_window_level_rescaled_to_raw(
                            window_center, window_width, rescale_slope or 1.0, rescale_intercept or 0.0
                        )
                        print(f"  [W/L VALIDATION] DICOM W/L in raw units: center={wl_raw[0]:.1f}, width={wl_raw[1]:.1f}")
                
                # Calculate window bounds
                window_min = final_window_center - final_window_width / 2.0
                window_max = final_window_center + final_window_width / 2.0
                
                # Show final W/L and validation checks
                print(f"  [W/L VALIDATION] Final W/L (after conversion): center={final_window_center:.1f}, width={final_window_width:.1f}")
                print(f"  [W/L VALIDATION] Final W/L range: [{window_min:.1f}, {window_max:.1f}]")
                final_units = "rescaled" if should_apply_rescale else "raw"
                print(f"  [W/L VALIDATION] Final W/L units: {final_units}")
                
                # Check if window/level is reasonable for the pixel range
                # If window is way outside pixel range or width is orders of magnitude larger, recalculate
                needs_recalculation = False
                if pixel_range > 0:
                    check1 = window_min > pixel_max * 1.5
                    check2 = window_max < pixel_min * 0.5
                    check3 = final_window_width > pixel_range * 10
                    
                    if check1 or check2 or check3:
                        needs_recalculation = True
                        print(f"  [W/L VALIDATION] WARNING: Window/level doesn't match pixel range!")
                        print(f"  [W/L VALIDATION]   - Window min ({window_min:.1f}) > pixel max * 1.5 ({pixel_max * 1.5:.1f}): {check1}")
                        print(f"  [W/L VALIDATION]   - Window max ({window_max:.1f}) < pixel min * 0.5 ({pixel_min * 0.5:.1f}): {check2}")
                        print(f"  [W/L VALIDATION]   - Window width ({final_window_width:.1f}) > pixel range * 10 ({pixel_range * 10:.1f}): {check3}")
                        print(f"  [W/L VALIDATION] Recalculating from pixel data...")
                
                if needs_recalculation:
                    # Recalculate from series-wide pixel data
                    # Use series min/max directly (no median calculation across all slices for performance)
                    array_type = "rescaled (after transformation)" if should_apply_rescale else "raw"
                    print(f"  [W/L VALIDATION] Recalculating from {array_type} pixel array (series-wide)...")
                    midpoint = (pixel_min + pixel_max) / 2.0
                    # Use midpoint directly (median across all slices would be too memory-intensive)
                    final_window_center = midpoint
                    final_window_width = pixel_range if pixel_range > 0 else (pixel_max - pixel_min)
                    print(f"  [W/L VALIDATION] Recalculated W/L from pixel data: window={final_window_width:.1f}, level={final_window_center:.1f}")
            
                # Set window/level (whether validated or recalculated)
                self.fusion_controls.set_overlay_window_level(final_window_width, final_window_center)
                print(f"  Applied overlay W/L: window={final_window_width:.1f}, level={final_window_center:.1f}")
            else:
                # Pixel range calculation failed, but we still have W/L from DICOM tags
                # Set it anyway (validation will happen on first display)
                self.fusion_controls.set_overlay_window_level(final_window_width, final_window_center)
                print(f"  Applied overlay W/L (no pixel validation): window={final_window_width:.1f}, level={final_window_center:.1f}")
        else:
            # Fallback if extraction failed (shouldn't happen with auto-calculation)
            print(f"  WARNING: Could not determine W/L for overlay, using defaults")
            self.fusion_controls.set_overlay_window_level(1000.0, 500.0)
    
    def handle_overlay_series_changed(self, series_uid: str) -> None:
        """
        Handle overlay series selection change.
        
        Args:
            series_uid: New overlay series UID
        """
        current_base_uid = self.fusion_handler.base_series_uid
        previous_overlay_uid = self.fusion_handler.overlay_series_uid
        
        if current_base_uid and series_uid == current_base_uid:
            self.fusion_controls.set_status(
                "Overlay series must differ from base", is_error=True
            )
            self.fusion_controls.revert_overlay_selection(
                preferred_uid=previous_overlay_uid,
                exclude_uid=current_base_uid
            )
            return
        
        # Always update overlay series and window/level, even if series_uid hasn't changed
        # This ensures window/level is refreshed when re-selecting the same series
        self.fusion_handler.set_overlay_series(series_uid)
        self.fusion_controls.reset_user_modified_offset()
        
        # Auto-set overlay window/level using DICOM tags or auto-calculation
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        
        if study_uid in studies and series_uid in studies[study_uid]:
            datasets = studies[study_uid][series_uid]
            if datasets:
                print(f"\n[OVERLAY W/L DEBUG] Overlay series changed: {series_uid[:28]}...")
                self._setup_overlay_window_level_with_debugging(series_uid, datasets)
        
        # Update spatial alignment parameters only when fusion is active
        if self.fusion_handler.fusion_enabled:
            if not self._apply_cached_alignment(reset_user_override=True):
                self._update_spatial_alignment()
        
        # Re-validate if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.handle_fusion_enabled_changed(True)
    
    def handle_opacity_changed(self, opacity: float) -> None:
        """
        Handle opacity change.
        
        Args:
            opacity: New opacity value (0.0-1.0)
        """
        self.fusion_handler.opacity = opacity
        
        # Request display update if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.request_display_update()
    
    def _apply_cached_alignment(self, reset_user_override: bool = False) -> bool:
        """Apply cached scaling/offset values for current base/overlay pair."""
        if self.fusion_handler.base_series_uid == self.fusion_handler.overlay_series_uid:
            return False
        
        alignment = self.fusion_handler.get_alignment(
            self.fusion_handler.base_series_uid,
            self.fusion_handler.overlay_series_uid
        )
        if not alignment:
            return False
        
        scale = alignment.get('scale')
        offset = alignment.get('offset')
        
        if scale and all(value is not None for value in scale):
            self.fusion_controls.set_scaling_factors(scale[0], scale[1])
        
        if reset_user_override:
            self.fusion_controls.reset_user_modified_offset()
        
        if offset and not self.fusion_controls.has_user_modified_offset():
            self.fusion_controls.set_calculated_offset(offset[0], offset[1])
        
        return True
    
    def update_base_display_from_series(self, series_uid: str) -> None:
        """External hook to update base display without changing selection."""
        short_uid = (series_uid[:28] + '...') if series_uid and len(series_uid) > 31 else (series_uid or 'None')
        print(f"[FUSION DEBUG] FusionCoordinator.update_base_display_from_series -> {short_uid}")
        self._update_base_display(series_uid)
    
    def _update_base_display(self, base_uid: str) -> None:
        """Update the read-only base display text."""
        display_name = "Not set"
        if base_uid:
            studies = self.get_current_studies()
            study_uid = self.get_current_study_uid()
            if study_uid in studies and base_uid in studies[study_uid]:
                datasets = studies[study_uid][base_uid]
                if datasets:
                    first_ds = datasets[0]
                    series_number = getattr(first_ds, 'SeriesNumber', None)
                    series_desc = getattr(first_ds, 'SeriesDescription', '')
                    modality = getattr(first_ds, 'Modality', '')
                    parts = []
                    if series_number is not None:
                        parts.append(f"S{series_number}")
                    if modality:
                        parts.append(modality)
                    if series_desc:
                        parts.append(series_desc)
                    if parts:
                        display_name = " - ".join(parts)
                    else:
                        display_name = base_uid[:20]
            else:
                display_name = base_uid[:20]
        
        if display_name != self._last_base_display:
            self.fusion_controls.set_base_display(display_name)
            self._last_base_display = display_name
    
    def _extract_first_float(self, value) -> Optional[float]:
        """Extract first numeric value from DICOM tag (handles MultiValue)."""
        if value is None:
            return None
        
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if len(value) == 0:
                return None
            value = value[0]
        
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    
    def handle_threshold_changed(self, threshold: float) -> None:
        """
        Handle threshold change.
        
        Args:
            threshold: New threshold value (0.0-1.0)
        """
        self.fusion_handler.threshold = threshold
        
        # Request display update if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.request_display_update()
    
    def handle_colormap_changed(self, colormap: str) -> None:
        """
        Handle colormap change.
        
        Args:
            colormap: New colormap name
        """
        self.fusion_handler.colormap = colormap
        
        # Request display update if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.request_display_update()
    
    def handle_overlay_window_level_changed(self, window: float, level: float) -> None:
        """
        Handle overlay window/level change.
        
        Args:
            window: Window width
            level: Window center/level
        """
        # Request display update if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.request_display_update()
    
    def handle_translation_offset_changed(self, x_offset: float, y_offset: float) -> None:
        """
        Handle translation offset change.
        
        Args:
            x_offset: X offset in pixels
            y_offset: Y offset in pixels
        """
        # Request display update if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.request_display_update()
    
    def export_state(self) -> Dict[str, object]:
        """Return a snapshot of the current fusion state."""
        return {
            "base_series_uid": self.fusion_handler.base_series_uid or "",
            "overlay_series_uid": self.fusion_handler.overlay_series_uid or "",
            "fusion_enabled": self.fusion_handler.fusion_enabled,
        }
    
    def restore_state(self, state: Optional[Dict[str, object]]) -> None:
        """Restore fusion selections and enabled state from a snapshot."""
        if not state:
            return
        
        base_uid = state.get("base_series_uid") or ""
        overlay_uid = state.get("overlay_series_uid") or ""
        fusion_enabled = bool(state.get("fusion_enabled", False))
        
        if base_uid:
            self.fusion_handler.set_base_series(base_uid)
            self._update_base_display(base_uid)
        if overlay_uid:
            self.fusion_handler.set_overlay_series(overlay_uid)
            # Refresh window/level for the restored overlay series
            self._refresh_overlay_window_level()
        
        self.fusion_handler.fusion_enabled = fusion_enabled
        self.fusion_controls.set_fusion_enabled(fusion_enabled)
        
        if fusion_enabled and overlay_uid:
            if not self._apply_cached_alignment(reset_user_override=True):
                self._update_spatial_alignment()
    
    def get_fused_image(
        self,
        base_image: Image.Image,
        base_datasets: List[Dataset],
        current_slice_idx: int
    ) -> Optional[Image.Image]:
        """
        Generate fused image for current slice.
        
        Args:
            base_image: Base (anatomical) PIL Image
            base_datasets: List of base series datasets
            current_slice_idx: Current slice index in base series
            
        Returns:
            Fused PIL Image, or None if fusion not possible
        """
        if not self.fusion_handler.fusion_enabled:
            return None
        
        if not self.fusion_handler.overlay_series_uid:
            return None
        
        # Get overlay datasets
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        
        if study_uid not in studies:
            return None
        
        overlay_datasets = studies[study_uid].get(self.fusion_handler.overlay_series_uid, [])
        if not overlay_datasets:
            return None
        
        # Get overlay array (with interpolation if needed)
        overlay_array = self.fusion_handler.interpolate_overlay_slice(
            current_slice_idx,
            base_datasets,
            overlay_datasets
        )
        
        if overlay_array is None:
            return None
        
        # Convert base image to array
        base_array = np.array(base_image)
        
        # Get overlay window/level from controls
        overlay_window, overlay_level = self.fusion_controls.get_overlay_window_level()
        
        # Get spatial parameters
        base_pixel_spacing = None
        overlay_pixel_spacing = None
        translation_offset = None
        
        if current_slice_idx < len(base_datasets) and current_slice_idx >= 0:
            base_ds = base_datasets[current_slice_idx]
            base_pixel_spacing = self.fusion_handler.get_pixel_spacing(base_ds)
            
            # Find corresponding overlay dataset for offset calculation
            overlay_idx, _ = self.fusion_handler.find_matching_slice(
                current_slice_idx, base_datasets, overlay_datasets
            )
            
            if overlay_idx is not None and overlay_idx < len(overlay_datasets):
                overlay_ds = overlay_datasets[overlay_idx]
                overlay_pixel_spacing = self.fusion_handler.get_pixel_spacing(overlay_ds)
                
                # Get translation offset from controls (user's current setting)
                translation_offset = self.fusion_controls.get_translation_offset()
                # DEBUG - commented out
                # print(f"[OFFSET DEBUG] get_fused_image: Using offset from spinboxes: X={translation_offset[0]:.1f}, Y={translation_offset[1]:.1f}")
        
        # Create fused image
        try:
            fused_array = self.fusion_processor.create_fusion_image(
                base_array=base_array,
                overlay_array=overlay_array,
                alpha=self.fusion_handler.opacity,
                colormap=self.fusion_handler.colormap,
                threshold=self.fusion_handler.threshold,
                base_wl=None,  # Base image already windowed/leveled
                overlay_wl=(overlay_window, overlay_level),
                base_pixel_spacing=base_pixel_spacing,
                overlay_pixel_spacing=overlay_pixel_spacing,
                translation_offset=translation_offset
            )
            
            # Convert to PIL Image
            fused_image = self.fusion_processor.convert_array_to_pil_image(fused_array)
            return fused_image
            
        except Exception as e:
            print(f"Error creating fused image: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _update_spatial_alignment(self) -> None:
        """
        Calculate and update spatial alignment parameters when series change.
        
        Updates the UI with calculated offset and scaling factors.
        """
        # Only proceed if both base and overlay series are selected
        if not self.fusion_handler.base_series_uid or not self.fusion_handler.overlay_series_uid:
            return
        
        # Get datasets
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        
        if study_uid not in studies:
            return
        
        base_datasets = studies[study_uid].get(self.fusion_handler.base_series_uid, [])
        overlay_datasets = studies[study_uid].get(self.fusion_handler.overlay_series_uid, [])
        
        if not base_datasets or not overlay_datasets:
            return
        
        # Get first slices for spatial metadata
        base_ds = base_datasets[0]
        overlay_ds = overlay_datasets[0]
        
        # Get pixel spacings
        base_pixel_spacing = self.fusion_handler.get_pixel_spacing(base_ds)
        overlay_pixel_spacing = self.fusion_handler.get_pixel_spacing(overlay_ds)
        
        # DEBUG
        print(f"\n[SPATIAL ALIGNMENT DEBUG]")
        print(f"  base_series: {self.fusion_handler.base_series_uid[:20] if self.fusion_handler.base_series_uid else 'None'}...")
        print(f"  overlay_series: {self.fusion_handler.overlay_series_uid[:20] if self.fusion_handler.overlay_series_uid else 'None'}...")
        print(f"  base_pixel_spacing: {base_pixel_spacing}")
        print(f"  overlay_pixel_spacing: {overlay_pixel_spacing}")
        
        stored_scale: Optional[Tuple[float, float]] = None
        stored_offset: Optional[Tuple[float, float]] = None
        
        # Calculate and display scaling factors
        if base_pixel_spacing and overlay_pixel_spacing:
            scale_x = overlay_pixel_spacing[1] / base_pixel_spacing[1]  # column spacing
            scale_y = overlay_pixel_spacing[0] / base_pixel_spacing[0]  # row spacing
            print(f"  scale_x: {scale_x:.4f}, scale_y: {scale_y:.4f}")
            stored_scale = (scale_x, scale_y)
            self.fusion_controls.set_scaling_factors(scale_x, scale_y)
        else:
            # No pixel spacing available
            self.fusion_controls.set_scaling_factors(1.0, 1.0)
            self.fusion_controls.set_status("Warning: Pixel spacing not available", is_error=True)
        
        # Calculate and display translation offset
        if base_pixel_spacing and overlay_pixel_spacing:
            offset = self.fusion_handler.calculate_translation_offset(
                base_ds, overlay_ds, base_pixel_spacing, overlay_pixel_spacing
            )
            
            if offset:
                offset_x, offset_y = offset
                stored_offset = (offset_x, offset_y)
                # DEBUG - commented out
                # print(f"  calculated offset: ({offset_x:.2f}, {offset_y:.2f}) pixels")
                # print(f"  base ImagePositionPatient: {self.fusion_handler.get_image_position_patient(base_ds)}")
                # print(f"  overlay ImagePositionPatient: {self.fusion_handler.get_image_position_patient(overlay_ds)}")
                self.fusion_controls.reset_user_modified_offset()
                self.fusion_controls.set_calculated_offset(offset_x, offset_y)
            else:
                # DEBUG - commented out
                # print(f"  offset calculation failed - no ImagePositionPatient")
                stored_offset = (0.0, 0.0)
                self.fusion_controls.reset_user_modified_offset()
                self.fusion_controls.set_calculated_offset(0.0, 0.0)
                if not self.fusion_controls.status_label.text().startswith("Status: Warning"):
                    self.fusion_controls.set_status("Warning: Image position not available", is_error=True)
        else:
            stored_offset = (0.0, 0.0)
            self.fusion_controls.reset_user_modified_offset()
            self.fusion_controls.set_calculated_offset(0.0, 0.0)
        
        if self.fusion_handler.base_series_uid != self.fusion_handler.overlay_series_uid:
            self.fusion_handler.set_alignment(
                self.fusion_handler.base_series_uid,
                self.fusion_handler.overlay_series_uid,
                stored_scale,
                stored_offset
            )
    
    def update_fusion_controls_series_list(self) -> None:
        """Update fusion controls with available series."""
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        
        # DEBUG
        print(f"[FUSION DEBUG] update_fusion_controls_series_list called")
        print(f"[FUSION DEBUG]   studies exists: {studies is not None}")
        if studies:
            print(f"[FUSION DEBUG]   studies count: {len(studies)}")
        print(f"[FUSION DEBUG]   study_uid: {study_uid[:20] if study_uid else 'None'}...")
        
        # Get available series
        series_list = self.fusion_handler.get_available_series_for_fusion(studies, study_uid)
        
        # DEBUG
        print(f"[FUSION DEBUG]   series_list count: {len(series_list)}")
        for uid, name in series_list:
            print(f"[FUSION DEBUG]     - {name}")
        
        # Update controls
        current_overlay = self.fusion_handler.overlay_series_uid or ""
        
        self.fusion_controls.update_series_lists(
            series_list,
            current_overlay_uid=current_overlay
        )
        # NOTE: Do NOT update base display here - it should only be updated by
        # update_base_display_from_series() when called with the focused subwindow's series
        
        # DEBUG
        print(f"[FUSION DEBUG]   Dropdown updated. Overlay items: {self.fusion_controls.overlay_series_combo.count()}")
        
        # Auto-detect compatible series if enabled
        if study_uid != self._last_auto_detection_study:
            self._last_auto_detection_study = study_uid
            self._auto_detect_fusion_candidates(studies, study_uid, series_list)
        
        # Update spatial alignment if both series are selected
        # (This handles the case where series list is updated and selections exist)
        if self.fusion_handler.base_series_uid and self.fusion_handler.overlay_series_uid:
            print(f"[FUSION DEBUG] update_fusion_controls_series_list: Calling _update_spatial_alignment")
            if not self._apply_cached_alignment(reset_user_override=True):
                self._update_spatial_alignment()
    
    def _auto_detect_fusion_candidates(
        self,
        studies: Dict,
        study_uid: str,
        series_list: List[Tuple[str, str]]
    ) -> None:
        """
        Auto-detect and suggest fusion for compatible series.
        
        Args:
            studies: Studies dictionary
            study_uid: Current study UID
            series_list: List of available series
        """
        if study_uid not in studies or len(series_list) < 2:
            return
        
        # Look for PET/SPECT and CT/MR combinations
        pet_series = []
        ct_series = []
        
        for series_uid, display_name in series_list:
            datasets = studies[study_uid].get(series_uid, [])
            if not datasets:
                continue
            
            modality = getattr(datasets[0], 'Modality', '')
            
            if modality in ['PT', 'NM']:  # PET or Nuclear Medicine
                pet_series.append((series_uid, display_name, datasets))
            elif modality in ['CT', 'MR']:  # CT or MR
                ct_series.append((series_uid, display_name, datasets))
        
        # Check if we have compatible pairs
        if not pet_series or not ct_series:
            return
        
        # Find first compatible pair (same Frame of Reference)
        for pet_uid, pet_name, pet_datasets in pet_series:
            for ct_uid, ct_name, ct_datasets in ct_series:
                if self.fusion_handler.check_frame_of_reference_match(pet_datasets, ct_datasets):
                    # Found compatible pair - suggest fusion
                    self._suggest_fusion(ct_uid, ct_name, pet_uid, pet_name)
                    return
    
    def _suggest_fusion(
        self,
        base_uid: str,
        base_name: str,
        overlay_uid: str,
        overlay_name: str
    ) -> None:
        """
        Pre-select compatible fusion series without auto-enabling the mode.
        
        Args:
            base_uid: Base series UID
            base_name: Base series display name
            overlay_uid: Overlay series UID
            overlay_name: Overlay series display name
        """
        self.fusion_handler.set_base_series(base_uid)
        self._update_base_display(base_uid)
        self.fusion_handler.set_overlay_series(overlay_uid)
        self.fusion_controls.reset_user_modified_offset()
        
        # Get datasets for the overlay series and setup W/L with debugging
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        if study_uid in studies and overlay_uid in studies[study_uid]:
            datasets = studies[study_uid][overlay_uid]
            if datasets:
                self._setup_overlay_window_level_with_debugging(overlay_uid, datasets)
        
        self.fusion_controls.update_series_lists(
            self.fusion_handler.get_available_series_for_fusion(
                self.get_current_studies(),
                self.get_current_study_uid()
            ),
            current_overlay_uid=overlay_uid
        )
            
        # Leave fusion disabled but inform the user that a compatible pair was found
        self.fusion_handler.fusion_enabled = False
        self.fusion_controls.set_fusion_enabled(False)
        self.fusion_controls.set_status(
            f"Fusion-ready: {base_name} + {overlay_name}. Enable to view overlay."
        )

