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
import numpy as np
from PIL import Image
from pydicom.dataset import Dataset

from core.fusion_handler import FusionHandler
from core.fusion_processor import FusionProcessor
from gui.fusion_controls_widget import FusionControlsWidget
from PySide6.QtWidgets import QMessageBox


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
        request_display_update: Callable[[], None],
        check_notification_shown: Optional[Callable[[str], bool]] = None,
        mark_notification_shown: Optional[Callable[[str], None]] = None
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
            check_notification_shown: Optional callback to check if notification was shown for study UID
            mark_notification_shown: Optional callback to mark notification as shown for study UID
        """
        self.fusion_handler = fusion_handler
        self.fusion_processor = fusion_processor
        self.fusion_controls = fusion_controls
        self.get_current_studies = get_current_studies
        self.get_current_study_uid = get_current_study_uid
        self.get_current_series_uid = get_current_series_uid
        self.get_current_slice_index = get_current_slice_index
        self.request_display_update = request_display_update
        
        # Store notification tracking callbacks
        self._check_notification_shown = check_notification_shown
        self._mark_notification_shown = mark_notification_shown
        
        # Per-subwindow fusion status history. Each FusionCoordinator instance
        # owns its own log so that the shared FusionControlsWidget can display
        # messages specific to the currently focused subwindow only.
        # Stored as list of (message, is_error) tuples.
        self._status_history: List[Tuple[str, bool]] = []
        
        # Note: Signals are connected externally when subwindow gains focus
        # Do not auto-connect here to allow per-subwindow signal routing
    
    def connect_fusion_controls_signals(self) -> None:
        """Connect FusionControlsWidget signals to this coordinator."""
        self.fusion_controls.fusion_enabled_changed.connect(self.handle_fusion_enabled_changed)
        # Base series is read-only display, no signal connection needed
        self.fusion_controls.overlay_series_changed.connect(self.handle_overlay_series_changed)
        self.fusion_controls.opacity_changed.connect(self.handle_opacity_changed)
        self.fusion_controls.threshold_changed.connect(self.handle_threshold_changed)
        self.fusion_controls.colormap_changed.connect(self.handle_colormap_changed)
        self.fusion_controls.overlay_window_level_changed.connect(self.handle_overlay_window_level_changed)
        self.fusion_controls.translation_offset_changed.connect(self.handle_translation_offset_changed)
        self.fusion_controls.resampling_mode_changed.connect(self.handle_resampling_mode_changed)
        self.fusion_controls.interpolation_method_changed.connect(self.handle_interpolation_method_changed)

        # When connecting to a (newly) focused subwindow, refresh the controls
        # status area from this coordinator's history so only this subwindow's
        # messages are shown.
        self._restore_status_history_to_controls()

    def _append_status(self, message: str, is_error: bool = False) -> None:
        """
        Append a status message to this coordinator's history and update the
        shared FusionControlsWidget.

        This ensures each FusionCoordinator (one per subwindow) retains its own
        status log, while the visible widget always reflects the currently
        focused subwindow only.
        """
        self._status_history.append((message, is_error))
        # Update the shared controls widget (which currently belongs to the
        # focused subwindow when this coordinator is connected).
        if self.fusion_controls is not None:
            self.fusion_controls.set_status(message, is_error=is_error)

    def _restore_status_history_to_controls(self) -> None:
        """
        Restore this coordinator's status history into the shared
        FusionControlsWidget.

        Called whenever this coordinator is (re)connected for the newly focused
        subwindow so the status box appears per-subwindow.
        """
        if self.fusion_controls is None:
            return

        # Clear the current log for the shared controls, then replay this
        # coordinator's history so the status box reflects only this subwindow.
        if hasattr(self.fusion_controls, "status_text_edit"):
            self.fusion_controls.status_text_edit.clear()
        
        for msg, is_err in self._status_history:
            self.fusion_controls.set_status(msg, is_error=is_err)
    
    def disconnect_fusion_controls_signals(self) -> None:
        """Disconnect FusionControlsWidget signals from this coordinator."""
        try:
            self.fusion_controls.fusion_enabled_changed.disconnect(self.handle_fusion_enabled_changed)
        except TypeError:
            pass  # Not connected
        try:
            self.fusion_controls.overlay_series_changed.disconnect(self.handle_overlay_series_changed)
        except TypeError:
            pass
        try:
            self.fusion_controls.opacity_changed.disconnect(self.handle_opacity_changed)
        except TypeError:
            pass
        try:
            self.fusion_controls.threshold_changed.disconnect(self.handle_threshold_changed)
        except TypeError:
            pass
        try:
            self.fusion_controls.colormap_changed.disconnect(self.handle_colormap_changed)
        except TypeError:
            pass
        try:
            self.fusion_controls.overlay_window_level_changed.disconnect(self.handle_overlay_window_level_changed)
        except TypeError:
            pass
        try:
            self.fusion_controls.translation_offset_changed.disconnect(self.handle_translation_offset_changed)
        except TypeError:
            pass
        try:
            self.fusion_controls.resampling_mode_changed.disconnect(self.handle_resampling_mode_changed)
        except TypeError:
            pass
        try:
            self.fusion_controls.interpolation_method_changed.disconnect(self.handle_interpolation_method_changed)
        except TypeError:
            pass
    
    def handle_fusion_enabled_changed(self, enabled: bool) -> None:
        """
        Handle fusion enabled/disabled.
        
        Args:
            enabled: True if fusion is enabled
        """
        self.fusion_handler.fusion_enabled = enabled
        
        if enabled:
            # Validate series selection. Treat missing overlay as an
            # informational prompt rather than an error in the status box.
            if not self.fusion_handler.base_series_uid or not self.fusion_handler.overlay_series_uid:
                self._append_status("Please select overlay series", is_error=False)
                return
            
            # Update spatial alignment when first enabling fusion
            self._update_spatial_alignment()
            
            # Check Frame of Reference compatibility
            studies = self.get_current_studies()
            study_uid = self.get_current_study_uid()
            
            if study_uid in studies:
                base_datasets = studies[study_uid].get(self.fusion_handler.base_series_uid, [])
                overlay_datasets = studies[study_uid].get(self.fusion_handler.overlay_series_uid, [])
                
                if base_datasets and overlay_datasets:
                    if self.fusion_handler.check_frame_of_reference_match(base_datasets, overlay_datasets):
                        self._append_status("Aligned (Frame of Reference)", is_error=False)
                        # Update resampling status
                        self._update_resampling_status()
                    else:
                        self._append_status("Warning: Different Frame of Reference", is_error=True)
                        # Note: Still allow fusion, but warn user
                        # Update resampling status
                        self._update_resampling_status()
        else:
            self._append_status("Disabled", is_error=False)
        
        # Request display update
        self.request_display_update()
    
    def handle_base_series_changed(self, series_uid: str) -> None:
        """
        Handle base series change (programmatic only, base is read-only in UI).
        
        Args:
            series_uid: New base series UID
        """
        self.fusion_handler.set_base_series(series_uid)
        
        # Update base display
        self._update_base_display(series_uid)
        
        # Update resampling status when base changes
        self._update_resampling_status()
        
        # Update spatial alignment parameters
        self._update_spatial_alignment()
        
        # Re-validate if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.handle_fusion_enabled_changed(True)
    
    def _update_base_display(self, base_uid: str) -> None:
        """
        Update the read-only base series display.
        
        Args:
            base_uid: Base series UID
        """
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
        
        self.fusion_controls.set_base_display(display_name)
    
    def handle_overlay_series_changed(self, series_uid: str) -> None:
        """
        Handle overlay series selection change.
        
        Args:
            series_uid: New overlay series UID
        """
        self.fusion_handler.set_overlay_series(series_uid)
        
        # Update resampling status when overlay changes
        self._update_resampling_status()
        
        # Auto-set overlay window/level: try DICOM tags first, then auto-calculate from series
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        
        if study_uid in studies and series_uid in studies[study_uid]:
            datasets = studies[study_uid][series_uid]
            if datasets:
                from core.dicom_processor import DICOMProcessor
                
                # Debug: Show overlay series pixel value statistics
                # Get rescale parameters
                rescale_slope, rescale_intercept, rescale_type = DICOMProcessor.get_rescale_parameters(datasets[0])
                has_rescale = (rescale_slope is not None and rescale_intercept is not None)
                
                # Get raw pixel value range (entire series)
                raw_min, raw_max = DICOMProcessor.get_series_pixel_value_range(datasets, apply_rescale=False)
                if raw_min is not None and raw_max is not None:
                    raw_range = raw_max - raw_min
                    print(f"[OVERLAY PIXEL VALUES] Raw (entire series): min={raw_min:.2f}, max={raw_max:.2f}, range={raw_range:.2f}")
                
                # Get rescaled pixel value range (entire series) if rescale parameters exist
                if has_rescale:
                    rescaled_min, rescaled_max = DICOMProcessor.get_series_pixel_value_range(datasets, apply_rescale=True)
                    if rescaled_min is not None and rescaled_max is not None:
                        rescaled_range = rescaled_max - rescaled_min
                        print(f"[OVERLAY PIXEL VALUES] Rescaled (entire series): min={rescaled_min:.2f}, max={rescaled_max:.2f}, range={rescaled_range:.2f}")
                        print(f"[OVERLAY PIXEL VALUES] Rescale parameters: slope={rescale_slope}, intercept={rescale_intercept}")
                else:
                    print(f"[OVERLAY PIXEL VALUES] No rescale parameters (RescaleSlope/RescaleIntercept not present)")
                
                # Try to get window/level from DICOM tags (with auto-calculation fallback for single slice)
                window_center, window_width, is_rescaled = DICOMProcessor.get_window_level_from_dataset(
                    datasets[0],
                    rescale_slope=rescale_slope,
                    rescale_intercept=rescale_intercept
                )
                
                # If DICOM tags don't provide valid values, calculate from entire series
                if window_center is None or window_width is None:
                    # Get series-wide pixel range
                    apply_rescale = (rescale_slope is not None and rescale_intercept is not None)
                    series_min, series_max = DICOMProcessor.get_series_pixel_value_range(
                        datasets,
                        apply_rescale=apply_rescale
                    )
                    
                    if series_min is not None and series_max is not None:
                        # Calculate window/level from series distribution
                        window_center = (series_min + series_max) / 2.0
                        window_width = series_max - series_min
                        print(f"[OVERLAY W/L] Auto-calculated from series: window={window_width:.1f}, level={window_center:.1f}")
                    else:
                        # Fallback: use defaults
                        window_width = 1000.0
                        window_center = 500.0
                        print(f"[OVERLAY W/L] Using defaults: window={window_width:.1f}, level={window_center:.1f}")
                else:
                    print(f"[OVERLAY W/L] From DICOM tags: window={window_width:.1f}, level={window_center:.1f}")
                
                # Set window/level in controls and store in handler (for per-subwindow state)
                if window_center is not None and window_width is not None:
                    self.fusion_handler.overlay_window = window_width
                    self.fusion_handler.overlay_level = window_center
                    self.fusion_controls.set_overlay_window_level(window_width, window_center)
        
        # Update spatial alignment parameters
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
        # Store in handler for per-subwindow state
        self.fusion_handler.overlay_window = window
        self.fusion_handler.overlay_level = level
        
        # Request display update if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.request_display_update()
    
    def sync_ui_from_handler_state(self) -> None:
        """Update UI controls to match current FusionHandler state."""
        # Block signals to prevent recursive updates
        # Check if fusion_controls has an _updating flag, otherwise use signal blocking
        if hasattr(self.fusion_controls, '_updating'):
            self.fusion_controls._updating = True
        
        # Update checkbox
        if hasattr(self.fusion_controls, 'set_fusion_enabled'):
            # Check if method accepts keep_signals_blocked parameter
            try:
                self.fusion_controls.set_fusion_enabled(self.fusion_handler.fusion_enabled, keep_signals_blocked=True)
            except TypeError:
                self.fusion_controls.set_fusion_enabled(self.fusion_handler.fusion_enabled)
        
        # Update opacity, threshold, colormap (set directly on controls)
        if hasattr(self.fusion_controls, 'opacity_slider'):
            opacity_value = int(self.fusion_handler.opacity * 100)
            self.fusion_controls.opacity_slider.setValue(opacity_value)
            if hasattr(self.fusion_controls, 'opacity_value_label'):
                self.fusion_controls.opacity_value_label.setText(f"{opacity_value}%")
        if hasattr(self.fusion_controls, 'threshold_slider'):
            threshold_value = int(self.fusion_handler.threshold * 100)
            self.fusion_controls.threshold_slider.setValue(threshold_value)
            if hasattr(self.fusion_controls, 'threshold_value_label'):
                self.fusion_controls.threshold_value_label.setText(f"{threshold_value}%")
        if hasattr(self.fusion_controls, 'colormap_combo'):
            colormap_index = self.fusion_controls.colormap_combo.findText(self.fusion_handler.colormap)
            if colormap_index >= 0:
                self.fusion_controls.colormap_combo.setCurrentIndex(colormap_index)
        
        # Update window/level from handler (now stored per-subwindow)
        if hasattr(self.fusion_controls, 'set_overlay_window_level'):
            self.fusion_controls.set_overlay_window_level(
                self.fusion_handler.overlay_window,
                self.fusion_handler.overlay_level
            )
        
        # Update resampling mode and interpolation
        if hasattr(self.fusion_controls, 'set_resampling_mode'):
            self.fusion_controls.set_resampling_mode(self.fusion_handler.resampling_mode)
        if hasattr(self.fusion_controls, 'set_interpolation_method'):
            self.fusion_controls.set_interpolation_method(self.fusion_handler.interpolation_method)
        
        # Update base/overlay series displays
        if self.fusion_handler.base_series_uid:
            self._update_base_display(self.fusion_handler.base_series_uid)
        else:
            self._update_base_display("")
        
        if self.fusion_handler.overlay_series_uid:
            # Update overlay combo selection
            if hasattr(self.fusion_controls, 'overlay_series_combo'):
                combo = self.fusion_controls.overlay_series_combo
                for i in range(combo.count()):
                    if combo.itemData(i) == self.fusion_handler.overlay_series_uid:
                        combo.setCurrentIndex(i)
                        break
        
        # Unblock signals
        if hasattr(self.fusion_controls, '_updating'):
            self.fusion_controls._updating = False
    
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
    
    def handle_resampling_mode_changed(self, mode: str) -> None:
        """
        Handle resampling mode change.
        
        Args:
            mode: 'fast' or 'high_accuracy'
        """
        self.fusion_handler.resampling_mode = mode
        
        # Clear resampling decision cache to force re-evaluation
        self.fusion_handler._resampling_decision_cache = None
        
        # Update status display
        self._update_resampling_status()
        
        # Request display update if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.request_display_update()
    
    def handle_interpolation_method_changed(self, method: str) -> None:
        """
        Handle interpolation method change.
        
        Args:
            method: Interpolation method name
        """
        self.fusion_handler.interpolation_method = method
        
        # Clear resampled volume cache when interpolation method changes
        self.fusion_handler.image_resampler.clear_cache()
        
        # Request display update if fusion is enabled
        if self.fusion_handler.fusion_enabled:
            self.request_display_update()
    
    def _update_resampling_status(self) -> None:
        """Update resampling status display in UI."""
        if not self.fusion_handler.base_series_uid or not self.fusion_handler.overlay_series_uid:
            return
        
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        
        if study_uid not in studies:
            return
        
        base_datasets = studies[study_uid].get(self.fusion_handler.base_series_uid, [])
        overlay_datasets = studies[study_uid].get(self.fusion_handler.overlay_series_uid, [])
        
        if not base_datasets or not overlay_datasets:
            return
        
        # Get status from handler
        mode_display, reason = self.fusion_handler.get_resampling_status(base_datasets, overlay_datasets)
        
        # Check if 3D resampling will actually be used
        use_3d, _ = self.fusion_handler._should_use_3d_resampling(base_datasets, overlay_datasets)
        
        # Disable offset controls when 3D resampling is active (offset is not applied in 3D mode)
        if hasattr(self.fusion_controls, "set_offset_controls_enabled"):
            self.fusion_controls.set_offset_controls_enabled(not use_3d)
        
        # Update offset status text to indicate how alignment is determined
        if hasattr(self.fusion_controls, "set_offset_status_text"):
            self.fusion_controls.set_offset_status_text(use_3d)
        
        # Check if warning should be shown (2D selected but 3D recommended)
        show_warning = False
        warning_text = ""
        if self.fusion_handler.resampling_mode == 'fast':
            # Check if 3D would be recommended
            needs_3d, _ = self.fusion_handler.image_resampler.needs_resampling(
                overlay_datasets, base_datasets
            )
            if needs_3d:
                show_warning = True
                warning_text = "Warning: 3D resampling recommended for accuracy. Current mode may produce misalignment."
        
        # Update inline warning label in the resampling group only. We intentionally
        # do not log the \"Using: ...\" informational message in the fusion status
        # box to avoid unnecessary noise there.
        self.fusion_controls.set_resampling_status(mode_display, reason, show_warning, warning_text)
    
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
        
        # Phase 2: Check if 3D resampling will be used (before getting overlay array)
        use_3d, _ = self.fusion_handler._should_use_3d_resampling(base_datasets, overlay_datasets)
        
        # Get overlay array (with interpolation if needed, or 3D resampling)
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
        
        # Get spatial parameters (only needed for 2D mode)
        base_pixel_spacing = None
        overlay_pixel_spacing = None
        translation_offset = None
        
        if not use_3d:  # Only get spatial params for 2D mode
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
                    # Only for 2D mode - 3D resampling handles alignment automatically
                    translation_offset = self.fusion_controls.get_translation_offset()
                    print(f"[OFFSET DEBUG] get_fused_image (2D mode): Using offset from spinboxes: X={translation_offset[0]:.1f}, Y={translation_offset[1]:.1f}")
        else:
            # Phase 2: For 3D mode, translation offset is NOT applied
            # 3D resampling already handles spatial alignment through the resampling grid
            # Manual fine-tuning would require a different approach (e.g., transform matrix adjustment)
            translation_offset = None
            print(f"[OFFSET DEBUG] get_fused_image (3D mode): Offset not applied - 3D resampling handles alignment")
        
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
                translation_offset=translation_offset,
                skip_2d_resize=use_3d  # Phase 2: Skip 2D resize when 3D resampling was used
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
        
        Checks cache first, then calculates and stores if not cached.
        Updates the UI with calculated offset and scaling factors.
        """
        # Only proceed if both base and overlay series are selected
        if not self.fusion_handler.base_series_uid or not self.fusion_handler.overlay_series_uid:
            return
        
        # Check if we have cached alignment for this pair
        cached_alignment = self.fusion_handler.get_alignment(
            self.fusion_handler.base_series_uid,
            self.fusion_handler.overlay_series_uid
        )
        
        if cached_alignment:
            # Restore from cache
            scale = cached_alignment.get('scale')
            offset = cached_alignment.get('offset')
            
            if scale:
                self.fusion_controls.set_scaling_factors(scale[0], scale[1])
            
            if offset:
                # Only restore if user hasn't manually modified
                if not self.fusion_controls.has_user_modified_offset():
                    self.fusion_controls.set_calculated_offset(offset[0], offset[1])
                    print(f"[SPATIAL ALIGNMENT] Restored from cache: scale={scale}, offset={offset}")
                else:
                    print(f"[SPATIAL ALIGNMENT] Cache exists but user modified offset, keeping user values")
            
            # Still need to update resampling status to ensure offset controls are enabled/disabled correctly
            self._update_resampling_status()
            return  # Skip calculation
        
        # No cache, calculate fresh values
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
        
        # Get pixel spacings (with source metadata)
        base_spacing, base_source = self.fusion_handler.get_pixel_spacing_with_source(base_ds)
        overlay_spacing, overlay_source = self.fusion_handler.get_pixel_spacing_with_source(overlay_ds)

        base_pixel_spacing = base_spacing
        overlay_pixel_spacing = overlay_spacing
        
        # Decide which spacing to expose to the controls for mm/px conversion.
        # IMPORTANT: Offset is calculated in base pixel coordinates, so we MUST use
        # base pixel spacing for offset conversion, not overlay spacing.
        row_spacing_mm = None
        col_spacing_mm = None
        spacing_source = None
        if base_spacing is not None:
            # Use base spacing for offset conversion (offset is in base pixel coordinates)
            row_spacing_mm, col_spacing_mm = base_spacing
            spacing_source = base_source
        elif overlay_spacing is not None:
            # Fallback to overlay spacing if base spacing not available
            row_spacing_mm, col_spacing_mm = overlay_spacing
            spacing_source = overlay_source

        # Push spacing information into controls so the unit toggle and inline
        # spacing description beneath Spatial Alignment stay in sync.
        if hasattr(self.fusion_controls, "set_pixel_spacing"):
            self.fusion_controls.set_pixel_spacing(row_spacing_mm, col_spacing_mm, spacing_source)
        
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
            stored_scale = (1.0, 1.0)
            self.fusion_controls.set_scaling_factors(1.0, 1.0)
            self._append_status("Warning: Pixel spacing not available", is_error=True)
        
        # Calculate and display translation offset
        if base_pixel_spacing and overlay_pixel_spacing:
            offset = self.fusion_handler.calculate_translation_offset(
                base_ds, overlay_ds, base_pixel_spacing, overlay_pixel_spacing
            )
            
            if offset:
                offset_x, offset_y = offset
                stored_offset = (offset_x, offset_y)
                print(f"  calculated offset: ({offset_x:.2f}, {offset_y:.2f}) pixels")
                print(f"  base ImagePositionPatient: {self.fusion_handler.get_image_position_patient(base_ds)}")
                print(f"  overlay ImagePositionPatient: {self.fusion_handler.get_image_position_patient(overlay_ds)}")
                # Only set if user hasn't manually modified
                if not self.fusion_controls.has_user_modified_offset():
                    self.fusion_controls.set_calculated_offset(offset_x, offset_y)
            else:
                print(f"  offset calculation failed - no ImagePositionPatient")
                # No image position available
                stored_offset = (0.0, 0.0)
                if not self.fusion_controls.has_user_modified_offset():
                    self.fusion_controls.set_calculated_offset(0.0, 0.0)
                if not self.fusion_controls.status_label.text().startswith("Status: Warning"):
                    self._append_status("Warning: Image position not available", is_error=True)
        else:
            stored_offset = (0.0, 0.0)
            if not self.fusion_controls.has_user_modified_offset():
                self.fusion_controls.set_calculated_offset(0.0, 0.0)
        
        # Store calculated values in cache
        if stored_scale is not None and stored_offset is not None:
            self.fusion_handler.set_alignment(
                self.fusion_handler.base_series_uid,
                self.fusion_handler.overlay_series_uid,
                stored_scale,
                stored_offset
            )
            print(f"[SPATIAL ALIGNMENT] Stored in cache: scale={stored_scale}, offset={stored_offset}")
        
        # Update resampling status to ensure offset controls are enabled/disabled correctly
        self._update_resampling_status()
    
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
        current_base = self.fusion_handler.base_series_uid or ""
        current_overlay = self.fusion_handler.overlay_series_uid or ""
        
        # Auto-initialize base series to current viewing series if not set
        if not current_base:
            current_viewing_series = self.get_current_series_uid()
            if current_viewing_series:
                # Verify series exists in available series list
                if any(uid == current_viewing_series for uid, _ in series_list):
                    self.fusion_handler.set_base_series(current_viewing_series)
                    current_base = current_viewing_series
                    print(f"[FUSION DEBUG] Auto-initialized base series to current viewing series: {current_viewing_series[:20]}...")
        
        self.fusion_controls.update_series_lists(
            series_list,
            current_base_uid=current_base,
            current_overlay_uid=current_overlay
        )
        
        # Update base display (now guaranteed to have a value if series is loaded)
        if current_base:
            self._update_base_display(current_base)
        else:
            # No series loaded, show "Not set"
            self._update_base_display("")
        
        # DEBUG
        print(f"[FUSION DEBUG]   Overlay dropdown updated. Overlay items: {self.fusion_controls.overlay_series_combo.count()}")
        
        # Auto-detect compatible series (global check happens inside _auto_detect_fusion_candidates)
        self._auto_detect_fusion_candidates(studies, study_uid, series_list)
        
        # Update spatial alignment if both series are selected
        # (This handles the case where series list is updated and selections exist)
        if self.fusion_handler.base_series_uid and self.fusion_handler.overlay_series_uid:
            print(f"[FUSION DEBUG] update_fusion_controls_series_list: Calling _update_spatial_alignment")
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
        
        # Check if notification was already shown for this study (global check)
        if self._check_notification_shown and self._check_notification_shown(study_uid):
            return  # Already notified, skip
        
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
                    
                    # Mark study as notified (global tracking)
                    if self._mark_notification_shown:
                        self._mark_notification_shown(study_uid)
                    
                    return
    
    def _suggest_fusion(
        self,
        base_uid: str,
        base_name: str,
        overlay_uid: str,
        overlay_name: str
    ) -> None:
        """
        Inform user about compatible series for fusion.
        
        Args:
            base_uid: Base series UID
            base_name: Base series display name
            overlay_uid: Overlay series UID
            overlay_name: Overlay series display name
        """
        # Show informational message about compatible series
        QMessageBox.information(
            self.fusion_controls,
            "Image Fusion Available",
            f"Compatible series detected for image fusion:\n\n"
            f"Base: {base_name}\n"
            f"Overlay: {overlay_name}\n\n"
            f"You can enable fusion from the Combine/Fuse tab."
        )
        # Note: Do not auto-enable fusion - user must manually enable it

