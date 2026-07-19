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
import logging
from collections.abc import Callable
from typing import Any, Optional

import numpy as np
from PIL import Image
from pydicom.dataset import Dataset
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from core.fusion_handler import FusionHandler, OverlayMatchResult
from core.fusion_processor import FusionProcessor
from gui.fusion_controls_widget import FusionControlsWidget
from utils.debug_flags import DEBUG_OFFSET, DEBUG_SPATIAL_ALIGNMENT
from utils.log_sanitizer import sanitized_format_exc
from utils.privacy.console import print_redacted

_logger = logging.getLogger(__name__)


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
        get_current_studies: Callable[[], dict[str, Any]],
        get_current_study_uid: Callable[[], str],
        get_current_series_uid: Callable[[], str],
        get_current_slice_index: Callable[[], int],
        request_display_update: Callable[[], None],
        check_notification_shown: Callable[[str], bool] | None = None,
        mark_notification_shown: Callable[[str], None] | None = None
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
        # Stored as list of (message, severity) tuples where severity is "info", "warning", or "error".
        self._status_history: list[tuple[str, str]] = []

        # Tracks the last coverage-hint text emitted to FusionControlsWidget so
        # the hint is only logged once per state transition (change-only debounce,
        # T3/T4).  None means no coverage hint is currently active.
        self._last_fusion_hint: str | None = None

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

    def _append_status(self, message: str, severity: str = "info") -> None:
        """
        Append a status message to this coordinator's history and update the
        shared FusionControlsWidget.

        This ensures each FusionCoordinator (one per subwindow) retains its own
        status log, while the visible widget always reflects the currently
        focused subwindow only.
        
        Args:
            message: Status message text
            severity: Severity level - "info", "warning", or "error"
        """
        # Store as (message, severity) tuple for history
        self._status_history.append((message, severity))
        # Update the shared controls widget (which currently belongs to the
        # focused subwindow when this coordinator is connected).
        if self.fusion_controls is not None:
            self.fusion_controls.set_status(message, severity=severity)

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

        for msg, severity in self._status_history:
            self.fusion_controls.set_status(msg, severity=severity)

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
            if not self._fusion_enabled_has_series_selection():
                return
            self._update_spatial_alignment()
            self._fusion_enabled_report_frame_of_reference()
        else:
            self._append_status("Disabled", severity="info")

        self.request_display_update()

    def _fusion_enabled_has_series_selection(self) -> bool:
        """Return True when both series are selected; otherwise prompt and return False."""
        if self.fusion_handler.base_series_uid and self.fusion_handler.overlay_series_uid:
            return True
        self._append_status("Please select overlay series", severity="info")
        return False

    def _fusion_enabled_report_frame_of_reference(self) -> None:
        """Append FoR status and refresh resampling status when both series exist."""
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        if study_uid not in studies:
            return

        base_datasets = studies[study_uid].get(self.fusion_handler.base_series_uid, [])
        overlay_datasets = studies[study_uid].get(
            self.fusion_handler.overlay_series_uid, []
        )
        if not base_datasets or not overlay_datasets:
            return

        if self.fusion_handler.check_frame_of_reference_match(
            base_datasets, overlay_datasets
        ):
            self._append_status("Aligned (Frame of Reference)", severity="info")
        else:
            self._append_status("Different Frame of Reference", severity="warning")
        self._update_resampling_status()

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
        self.fusion_controls.set_base_display(
            self._format_base_series_display_name(base_uid)
        )

    def _format_base_series_display_name(self, base_uid: str) -> str:
        """Build the read-only base-series label for fusion controls."""
        if not base_uid:
            return "Not set"

        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        if study_uid not in studies or base_uid not in studies[study_uid]:
            return base_uid[:20]

        datasets = studies[study_uid][base_uid]
        if not datasets:
            return base_uid[:20]

        first_ds = datasets[0]
        series_number = getattr(first_ds, "SeriesNumber", None)
        series_desc = getattr(first_ds, "SeriesDescription", "")
        modality = getattr(first_ds, "Modality", "")
        parts = []
        if series_number is not None:
            parts.append(f"S{series_number}")
        if modality:
            parts.append(modality)
        if series_desc:
            parts.append(series_desc)
        if parts:
            return " - ".join(parts)
        return base_uid[:20]

    def handle_overlay_series_changed(self, series_uid: str) -> None:
        """
        Handle overlay series selection change.
        
        Updates handler state immediately so the UI reflects the selection, then
        defers heavy work (pixel value range, spatial alignment, display update)
        to the next event loop tick to avoid freezing the UI.
        
        Args:
            series_uid: New overlay series UID
        """
        self.fusion_handler.set_overlay_series(series_uid)
        # Defer expensive work so the dropdown and handler state update immediately.
        # Heavy work: duplicate check, pixel value range over full series, spatial
        # alignment, and fusion display update (which may run 3D resampling).
        QTimer.singleShot(0, self._finish_overlay_series_load)

    def _finish_overlay_series_load(self) -> None:
        """
        Run after overlay series is set: duplicate check, resampling status,
        auto window/level (may scan full series), spatial alignment, and display update.
        Called deferred from handle_overlay_series_changed to avoid main-thread freeze.
        """
        series_uid = self.fusion_handler.overlay_series_uid
        if not series_uid:
            return

        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        self._overlay_load_warn_duplicate_locations(studies, study_uid, series_uid)
        self._update_resampling_status()
        self._overlay_load_auto_window_level(studies, study_uid, series_uid)
        self._update_spatial_alignment()
        if self.fusion_handler.fusion_enabled:
            self.handle_fusion_enabled_changed(True)

    def _overlay_load_warn_duplicate_locations(
        self, studies: dict[str, Any], study_uid: str, series_uid: str
    ) -> None:
        """Warn when the overlay series has multiple slices at the same location."""
        if study_uid not in studies or series_uid not in studies[study_uid]:
            return
        overlay_datasets = studies[study_uid][series_uid]
        if not overlay_datasets:
            return
        has_duplicates, _duplicate_count = self.fusion_handler.has_duplicate_locations(
            overlay_datasets
        )
        if has_duplicates:
            self._append_status(
                "Overlay series has multiple slices at the same location. "
                "Only the first occurrence at each location will be used in 3D fusion.",
                severity="warning",
            )

    @staticmethod
    def _overlay_load_sample_datasets(datasets: list) -> list:
        """Sample large series so pixel-range scans stay responsive."""
        max_slices = 24
        if len(datasets) <= max_slices:
            return datasets
        step = (len(datasets) - 1) / (max_slices - 1) if max_slices > 1 else 0
        indices = (
            [0]
            + [int(round(step * i)) for i in range(1, max_slices - 1)]
            + [len(datasets) - 1]
        )
        return [datasets[i] for i in sorted(set(indices))]

    def _overlay_load_resolve_window_level(
        self, datasets: list, datasets_to_scan: list
    ) -> tuple[float, float] | None:
        """
        Resolve overlay window/level from DICOM tags or series pixel range.

        Returns:
            ``(window_center, window_width)`` or ``None`` when unresolved.
        """
        from core.dicom_processor import DICOMProcessor

        rescale_slope, rescale_intercept, _rescale_type = (
            DICOMProcessor.get_rescale_parameters(datasets[0])
        )
        has_rescale = rescale_slope is not None and rescale_intercept is not None
        self._overlay_load_debug_pixel_ranges(
            datasets_to_scan, has_rescale, rescale_slope, rescale_intercept
        )

        window_center, window_width, _is_rescaled = (
            DICOMProcessor.get_window_level_from_dataset(
                datasets[0],
                rescale_slope=rescale_slope,
                rescale_intercept=rescale_intercept,
            )
        )
        if window_center is None or window_width is None:
            window_center, window_width = self._overlay_load_fallback_window_level(
                datasets_to_scan, rescale_slope, rescale_intercept
            )
        elif DEBUG_OFFSET:
            print(
                f"[OVERLAY W/L] From DICOM tags: "
                f"window={window_width:.1f}, level={window_center:.1f}"
            )

        if window_center is None or window_width is None:
            return None
        return window_center, window_width

    @staticmethod
    def _overlay_load_debug_pixel_ranges(
        datasets_to_scan: list,
        has_rescale: bool,
        rescale_slope,
        rescale_intercept,
    ) -> None:
        """Emit optional DEBUG_OFFSET pixel-range diagnostics for overlay load."""
        if not DEBUG_OFFSET:
            return
        from core.dicom_processor import DICOMProcessor

        raw_min, raw_max = DICOMProcessor.get_series_pixel_value_range(
            datasets_to_scan, apply_rescale=False
        )
        if raw_min is not None and raw_max is not None:
            print(
                f"[OVERLAY PIXEL VALUES] Raw (entire series): "
                f"min={raw_min:.2f}, max={raw_max:.2f}, range={raw_max - raw_min:.2f}"
            )
        if not has_rescale:
            print(
                "[OVERLAY PIXEL VALUES] No rescale parameters "
                "(RescaleSlope/RescaleIntercept not present)"
            )
            return
        rescaled_min, rescaled_max = DICOMProcessor.get_series_pixel_value_range(
            datasets_to_scan, apply_rescale=True
        )
        if rescaled_min is None or rescaled_max is None:
            return
        print(
            f"[OVERLAY PIXEL VALUES] Rescaled (entire series): "
            f"min={rescaled_min:.2f}, max={rescaled_max:.2f}, "
            f"range={rescaled_max - rescaled_min:.2f}"
        )
        print(
            f"[OVERLAY PIXEL VALUES] Rescale parameters: "
            f"slope={rescale_slope}, intercept={rescale_intercept}"
        )

    @staticmethod
    def _overlay_load_fallback_window_level(
        datasets_to_scan: list, rescale_slope, rescale_intercept
    ) -> tuple[float, float]:
        """Compute window/level from series range or defaults when tags are absent."""
        from core.dicom_processor import DICOMProcessor

        apply_rescale = rescale_slope is not None and rescale_intercept is not None
        series_min, series_max = DICOMProcessor.get_series_pixel_value_range(
            datasets_to_scan, apply_rescale=apply_rescale
        )
        if series_min is not None and series_max is not None:
            window_center = (series_min + series_max) / 2.0
            window_width = series_max - series_min
            if DEBUG_OFFSET:
                print(
                    f"[OVERLAY W/L] Auto-calculated from series: "
                    f"window={window_width:.1f}, level={window_center:.1f}"
                )
            return window_center, window_width
        window_width = 1000.0
        window_center = 500.0
        if DEBUG_OFFSET:
            print(
                f"[OVERLAY W/L] Using defaults: "
                f"window={window_width:.1f}, level={window_center:.1f}"
            )
        return window_center, window_width

    def _overlay_load_auto_window_level(
        self, studies: dict[str, Any], study_uid: str, series_uid: str
    ) -> None:
        """Auto-set overlay window/level from DICOM tags or series pixel range."""
        if study_uid not in studies or series_uid not in studies[study_uid]:
            return
        datasets = studies[study_uid][series_uid]
        if not datasets:
            return
        datasets_to_scan = self._overlay_load_sample_datasets(datasets)
        wl = self._overlay_load_resolve_window_level(datasets, datasets_to_scan)
        if wl is None:
            return
        window_center, window_width = wl
        self.fusion_handler.overlay_window = window_width
        self.fusion_handler.overlay_level = window_center
        self.fusion_controls.set_overlay_window_level(window_width, window_center)

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
        if hasattr(self.fusion_controls, "_updating"):
            self.fusion_controls._updating = True

        self._sync_ui_enabled_and_blend_controls()
        self._sync_ui_window_level_and_resampling()
        self._sync_ui_series_displays()

        if hasattr(self.fusion_controls, "_updating"):
            self.fusion_controls._updating = False

    def _sync_ui_enabled_and_blend_controls(self) -> None:
        """Sync fusion enabled, opacity, threshold, and colormap controls."""
        if hasattr(self.fusion_controls, "set_fusion_enabled"):
            self.fusion_controls.set_fusion_enabled(self.fusion_handler.fusion_enabled)

        if hasattr(self.fusion_controls, "opacity_slider"):
            opacity_value = int(self.fusion_handler.opacity * 100)
            self.fusion_controls.opacity_slider.setValue(opacity_value)
            if hasattr(self.fusion_controls, "opacity_value_label"):
                self.fusion_controls.opacity_value_label.setText(f"{opacity_value}%")
        if hasattr(self.fusion_controls, "threshold_slider"):
            threshold_value = int(self.fusion_handler.threshold * 100)
            self.fusion_controls.threshold_slider.setValue(threshold_value)
            if hasattr(self.fusion_controls, "threshold_value_label"):
                self.fusion_controls.threshold_value_label.setText(f"{threshold_value}%")
        if hasattr(self.fusion_controls, "colormap_combo"):
            colormap_index = self.fusion_controls.colormap_combo.findText(
                self.fusion_handler.colormap
            )
            if colormap_index >= 0:
                self.fusion_controls.colormap_combo.setCurrentIndex(colormap_index)

    def _sync_ui_window_level_and_resampling(self) -> None:
        """Sync overlay W/L and resampling/interpolation controls."""
        if hasattr(self.fusion_controls, "set_overlay_window_level"):
            self.fusion_controls.set_overlay_window_level(
                self.fusion_handler.overlay_window,
                self.fusion_handler.overlay_level,
            )
        if hasattr(self.fusion_controls, "set_resampling_mode"):
            self.fusion_controls.set_resampling_mode(self.fusion_handler.resampling_mode)
        if hasattr(self.fusion_controls, "set_interpolation_method"):
            self.fusion_controls.set_interpolation_method(
                self.fusion_handler.interpolation_method
            )

    def _sync_ui_series_displays(self) -> None:
        """Sync base display and overlay combo selection from handler state."""
        if self.fusion_handler.base_series_uid:
            self._update_base_display(self.fusion_handler.base_series_uid)
        else:
            self._update_base_display("")

        if not self.fusion_handler.overlay_series_uid:
            return
        if not hasattr(self.fusion_controls, "overlay_series_combo"):
            return
        combo = self.fusion_controls.overlay_series_combo
        for i in range(combo.count()):
            if combo.itemData(i) == self.fusion_handler.overlay_series_uid:
                combo.setCurrentIndex(i)
                break

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
        self.fusion_handler.set_resampling_mode(mode)

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
        datasets = self._resampling_status_resolve_datasets()
        if datasets is None:
            return
        base_datasets, overlay_datasets = datasets

        mode_display, reason = self.fusion_handler.get_resampling_status(
            base_datasets, overlay_datasets
        )
        use_3d, _ = self.fusion_handler._should_use_3d_resampling(
            base_datasets, overlay_datasets
        )
        actual_mode = self.fusion_handler.get_actual_resampling_mode_used()
        actual_use_3d = actual_mode if actual_mode is not None else use_3d

        self._resampling_status_apply_offset_controls(actual_use_3d)
        show_warning, warning_text = self._resampling_status_compute_warning(
            base_datasets, overlay_datasets, use_3d, actual_mode
        )
        self.fusion_controls.set_resampling_status(
            mode_display, reason, show_warning, warning_text
        )

    def _resampling_status_resolve_datasets(
        self,
    ) -> tuple[list, list] | None:
        """Return base/overlay dataset lists when both series are available."""
        if (
            not self.fusion_handler.base_series_uid
            or not self.fusion_handler.overlay_series_uid
        ):
            return None
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        if study_uid not in studies:
            return None
        base_datasets = studies[study_uid].get(self.fusion_handler.base_series_uid, [])
        overlay_datasets = studies[study_uid].get(
            self.fusion_handler.overlay_series_uid, []
        )
        if not base_datasets or not overlay_datasets:
            return None
        return base_datasets, overlay_datasets

    def _resampling_status_apply_offset_controls(self, actual_use_3d: bool) -> None:
        """Enable/disable offset controls and update offset status text for 2D/3D."""
        if hasattr(self.fusion_controls, "set_offset_controls_enabled"):
            self.fusion_controls.set_offset_controls_enabled(not actual_use_3d)
        if hasattr(self.fusion_controls, "set_offset_status_text"):
            self.fusion_controls.set_offset_status_text(actual_use_3d)

    def _resampling_status_compute_warning(
        self,
        base_datasets: list,
        overlay_datasets: list,
        use_3d: bool,
        actual_mode: bool | None,
    ) -> tuple[bool, str]:
        """
        Compute resampling warning state and apply 3D-failure UI side effects.

        Returns:
            ``(show_warning, warning_text)`` for the resampling status label.
        """
        if actual_mode is False and use_3d:
            failure_reason = self.fusion_handler.get_resampling_failure_reason()
            if failure_reason:
                warning_msg = f"3D resampling failed ({failure_reason}), using 2D mode"
            else:
                warning_msg = "3D resampling failed, using 2D mode"
            self._append_status(warning_msg, severity="warning")
            self.fusion_handler.resampling_mode = "fast"
            if hasattr(self.fusion_controls, "set_resampling_mode"):
                self.fusion_controls.set_resampling_mode("fast")
            warning_text = (
                f"3D resampling failed "
                f"({failure_reason if failure_reason else 'unknown error'}), "
                f"using 2D fallback mode"
            )
            return True, warning_text

        if self.fusion_handler.resampling_mode == "fast":
            needs_3d, _ = self.fusion_handler.image_resampler.needs_resampling(
                overlay_datasets, base_datasets
            )
            if needs_3d:
                return (
                    True,
                    "Warning: 3D resampling recommended for accuracy. "
                    "Current mode may produce misalignment.",
                )
        return False, ""

    def get_fused_image(
        self,
        base_image: Image.Image,
        base_datasets: list[Dataset],
        current_slice_idx: int
    ) -> Image.Image | None:
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

        overlay_datasets = self._fused_resolve_overlay_datasets()
        if overlay_datasets is None:
            return None

        use_3d, _ = self.fusion_handler._should_use_3d_resampling(
            base_datasets, overlay_datasets
        )
        overlay_array = self.fusion_handler.interpolate_overlay_slice(
            current_slice_idx, base_datasets, overlay_datasets
        )
        if overlay_array is None:
            self._update_fusion_coverage_hint(
                self.fusion_handler._last_overlay_match_result
            )
            return None

        self._fused_clear_coverage_hint_if_needed()
        actual_use_3d = self._fused_resolve_actual_3d(use_3d)
        base_array = np.array(base_image)
        overlay_window, overlay_level = self.fusion_controls.get_overlay_window_level()
        (
            base_pixel_spacing,
            overlay_pixel_spacing,
            translation_offset,
        ) = self._fused_collect_spatial_params(
            base_datasets,
            overlay_datasets,
            current_slice_idx,
            actual_use_3d,
        )
        return self._fused_blend(
            base_array,
            overlay_array,
            overlay_window,
            overlay_level,
            base_pixel_spacing,
            overlay_pixel_spacing,
            translation_offset,
            actual_use_3d,
        )

    def _fused_resolve_overlay_datasets(self) -> list[Dataset] | None:
        """Return overlay datasets for the current study, or None when unavailable."""
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        if study_uid not in studies:
            return None
        overlay_datasets = studies[study_uid].get(
            self.fusion_handler.overlay_series_uid, []
        )
        if not overlay_datasets:
            return None
        return overlay_datasets

    def _fused_clear_coverage_hint_if_needed(self) -> None:
        """Clear a prior out-of-coverage hint once an overlay slice is available."""
        if self._last_fusion_hint is None:
            return
        self._last_fusion_hint = None
        if self.fusion_controls is not None:
            self.fusion_controls.set_status("Fusion overlay active.", severity="info")

    def _fused_resolve_actual_3d(self, use_3d: bool) -> bool:
        """Resolve whether 3D resampling was actually used; schedule UI refresh if set."""
        actual_use_3d = self.fusion_handler.get_actual_resampling_mode_used()
        if actual_use_3d is None:
            return use_3d
        QTimer.singleShot(0, self._update_resampling_status)
        return actual_use_3d

    def _fused_collect_spatial_params(
        self,
        base_datasets: list[Dataset],
        overlay_datasets: list[Dataset],
        current_slice_idx: int,
        actual_use_3d: bool,
    ) -> tuple[Any, Any, Any]:
        """Collect 2D spacing/offset params (None for 3D mode)."""
        if actual_use_3d:
            if DEBUG_OFFSET:
                print(
                    "[OFFSET DEBUG] get_fused_image (3D mode): Offset not applied - "
                    "3D resampling handles alignment"
                )
            return None, None, None

        base_pixel_spacing = None
        overlay_pixel_spacing = None
        translation_offset = None
        if 0 <= current_slice_idx < len(base_datasets):
            base_ds = base_datasets[current_slice_idx]
            base_pixel_spacing = self.fusion_handler.get_pixel_spacing(base_ds)
            overlay_idx, _ = self.fusion_handler.find_matching_slice(
                current_slice_idx, base_datasets, overlay_datasets
            )
            if overlay_idx is not None and overlay_idx < len(overlay_datasets):
                overlay_ds = overlay_datasets[overlay_idx]
                overlay_pixel_spacing = self.fusion_handler.get_pixel_spacing(overlay_ds)
                translation_offset = self.fusion_controls.get_translation_offset()
                if DEBUG_OFFSET:
                    print(
                        "[OFFSET DEBUG] get_fused_image (2D mode): "
                        f"Using offset from spinboxes: "
                        f"X={translation_offset[0]:.1f}, Y={translation_offset[1]:.1f}"
                    )
        return base_pixel_spacing, overlay_pixel_spacing, translation_offset

    def _fused_blend(
        self,
        base_array: np.ndarray,
        overlay_array: np.ndarray,
        overlay_window: float,
        overlay_level: float,
        base_pixel_spacing,
        overlay_pixel_spacing,
        translation_offset,
        actual_use_3d: bool,
    ) -> Image.Image | None:
        """Blend base/overlay arrays into a fused PIL image."""
        try:
            fused_array = self.fusion_processor.create_fusion_image(
                base_array=base_array,
                overlay_array=overlay_array,
                alpha=self.fusion_handler.opacity,
                colormap=self.fusion_handler.colormap,
                threshold=self.fusion_handler.threshold,
                base_wl=None,
                overlay_wl=(overlay_window, overlay_level),
                base_pixel_spacing=base_pixel_spacing,
                overlay_pixel_spacing=overlay_pixel_spacing,
                translation_offset=translation_offset,
                skip_2d_resize=actual_use_3d,
            )
            return self.fusion_processor.convert_array_to_pil_image(fused_array)
        except Exception as e:
            print_redacted(f"Error creating fused image: {e}")
            _logger.debug("%s", sanitized_format_exc())
            return None

    def _update_fusion_coverage_hint(
        self, match_result: Optional["OverlayMatchResult"]
    ) -> None:
        """
        Emit (or debounce) a status hint when the current base slice is outside
        the overlay stack coverage.

        Called only when interpolate_overlay_slice returns None.  Uses a
        change-only guard (self._last_fusion_hint) so the log entry is added
        once per state transition rather than on every slice repaint (T3/T4).

        Args:
            match_result: OverlayMatchResult from FusionHandler, or None if
                          interpolate_overlay_slice was never called.
        """
        _coverage_results = (
            OverlayMatchResult.below_stack,
            OverlayMatchResult.above_stack,
            OverlayMatchResult.no_geometry,
        )
        if match_result in _coverage_results:
            hint = "No overlay for this slice (outside overlay series coverage)."
        else:
            hint = None

        if hint is not None and hint != self._last_fusion_hint:
            self._last_fusion_hint = hint
            if self.fusion_controls is not None:
                self.fusion_controls.set_status(hint, severity="warning")

    def _update_spatial_alignment(self) -> None:
        """
        Calculate and update spatial alignment parameters when series change.
        
        Checks cache first, then calculates and stores if not cached.
        Updates the UI with calculated offset and scaling factors.
        """
        if (
            not self.fusion_handler.base_series_uid
            or not self.fusion_handler.overlay_series_uid
        ):
            return

        cached_alignment = self.fusion_handler.get_alignment(
            self.fusion_handler.base_series_uid,
            self.fusion_handler.overlay_series_uid,
        )
        if cached_alignment:
            self._spatial_restore_from_cache(cached_alignment)
            self._update_resampling_status()
            return

        datasets = self._spatial_resolve_series_datasets()
        if datasets is None:
            return
        base_ds, overlay_ds = datasets

        base_spacing, base_source = self.fusion_handler.get_pixel_spacing_with_source(
            base_ds
        )
        overlay_spacing, overlay_source = (
            self.fusion_handler.get_pixel_spacing_with_source(overlay_ds)
        )
        self._spatial_push_pixel_spacing(
            base_spacing, base_source, overlay_spacing, overlay_source
        )
        if DEBUG_SPATIAL_ALIGNMENT:
            self._spatial_debug_log_spacings(base_spacing, overlay_spacing)

        stored_scale = self._spatial_compute_and_apply_scale(
            base_spacing, overlay_spacing
        )
        stored_offset = self._spatial_compute_and_apply_offset(
            base_ds, overlay_ds, base_spacing, overlay_spacing
        )
        self.fusion_handler.set_alignment(
            self.fusion_handler.base_series_uid,
            self.fusion_handler.overlay_series_uid,
            stored_scale,
            stored_offset,
        )
        if DEBUG_SPATIAL_ALIGNMENT:
            print(
                f"[SPATIAL ALIGNMENT] Stored in cache: "
                f"scale={stored_scale}, offset={stored_offset}"
            )
        self._update_resampling_status()

    def _spatial_restore_from_cache(self, cached_alignment: dict) -> None:
        """Restore scale/offset UI from a cached alignment pair."""
        scale = cached_alignment.get("scale")
        offset = cached_alignment.get("offset")
        if scale:
            self.fusion_controls.set_scaling_factors(scale[0], scale[1])
        if not offset:
            return
        if not self.fusion_controls.has_user_modified_offset():
            self.fusion_controls.set_calculated_offset(offset[0], offset[1])
            if DEBUG_SPATIAL_ALIGNMENT:
                print(
                    f"[SPATIAL ALIGNMENT] Restored from cache: "
                    f"scale={scale}, offset={offset}"
                )
        elif DEBUG_SPATIAL_ALIGNMENT:
            print(
                "[SPATIAL ALIGNMENT] Cache exists but user modified offset, "
                "keeping user values"
            )

    def _spatial_resolve_series_datasets(
        self,
    ) -> tuple[Any, Any] | None:
        """Return first base/overlay datasets when both series are present."""
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()
        if study_uid not in studies:
            return None
        base_datasets = studies[study_uid].get(self.fusion_handler.base_series_uid, [])
        overlay_datasets = studies[study_uid].get(
            self.fusion_handler.overlay_series_uid, []
        )
        if not base_datasets or not overlay_datasets:
            return None
        return base_datasets[0], overlay_datasets[0]

    def _spatial_push_pixel_spacing(
        self,
        base_spacing,
        base_source,
        overlay_spacing,
        overlay_source,
    ) -> None:
        """Push spacing used for mm/px conversion into fusion controls."""
        row_spacing_mm = None
        col_spacing_mm = None
        spacing_source = None
        if base_spacing is not None:
            row_spacing_mm, col_spacing_mm = base_spacing
            spacing_source = base_source
        elif overlay_spacing is not None:
            row_spacing_mm, col_spacing_mm = overlay_spacing
            spacing_source = overlay_source
        if hasattr(self.fusion_controls, "set_pixel_spacing"):
            self.fusion_controls.set_pixel_spacing(
                row_spacing_mm, col_spacing_mm, spacing_source
            )

    def _spatial_debug_log_spacings(self, base_spacing, overlay_spacing) -> None:
        """Emit debug spacing details when DEBUG_SPATIAL_ALIGNMENT is enabled."""
        print("\n[SPATIAL ALIGNMENT DEBUG]")
        print_redacted(
            f"  base_series: "
            f"{self.fusion_handler.base_series_uid[:20] if self.fusion_handler.base_series_uid else 'None'}..."
        )
        print_redacted(
            f"  overlay_series: "
            f"{self.fusion_handler.overlay_series_uid[:20] if self.fusion_handler.overlay_series_uid else 'None'}..."
        )
        print(f"  base_pixel_spacing: {base_spacing}")
        print(f"  overlay_pixel_spacing: {overlay_spacing}")

    def _spatial_compute_and_apply_scale(
        self, base_spacing, overlay_spacing
    ) -> tuple[float, float]:
        """Compute scale factors, update controls, and return the stored tuple."""
        if base_spacing and overlay_spacing:
            scale_x = overlay_spacing[1] / base_spacing[1]
            scale_y = overlay_spacing[0] / base_spacing[0]
            if DEBUG_SPATIAL_ALIGNMENT:
                print(f"  scale_x: {scale_x:.4f}, scale_y: {scale_y:.4f}")
            self.fusion_controls.set_scaling_factors(scale_x, scale_y)
            return scale_x, scale_y
        self.fusion_controls.set_scaling_factors(1.0, 1.0)
        self._append_status("Pixel spacing not available", severity="warning")
        return 1.0, 1.0

    def _spatial_compute_and_apply_offset(
        self,
        base_ds,
        overlay_ds,
        base_spacing,
        overlay_spacing,
    ) -> tuple[float, float]:
        """Compute translation offset, update controls when allowed, return stored tuple."""
        if not (base_spacing and overlay_spacing):
            if not self.fusion_controls.has_user_modified_offset():
                self.fusion_controls.set_calculated_offset(0.0, 0.0)
            return 0.0, 0.0

        offset = self.fusion_handler.calculate_translation_offset(
            base_ds, overlay_ds, base_spacing, overlay_spacing
        )
        if offset:
            offset_x, offset_y = offset
            if DEBUG_SPATIAL_ALIGNMENT:
                print(f"  calculated offset: ({offset_x:.2f}, {offset_y:.2f}) pixels")
                print_redacted(
                    f"  base ImagePositionPatient: "
                    f"{self.fusion_handler.get_image_position_patient(base_ds)}"
                )
                print_redacted(
                    f"  overlay ImagePositionPatient: "
                    f"{self.fusion_handler.get_image_position_patient(overlay_ds)}"
                )
            if not self.fusion_controls.has_user_modified_offset():
                self.fusion_controls.set_calculated_offset(offset_x, offset_y)
            return offset_x, offset_y

        if DEBUG_SPATIAL_ALIGNMENT:
            print("  offset calculation failed - no ImagePositionPatient")
        if not self.fusion_controls.has_user_modified_offset():
            self.fusion_controls.set_calculated_offset(0.0, 0.0)
        status_lbl = getattr(self.fusion_controls, "status_label", None)
        if status_lbl is None or not status_lbl.text().startswith("Status: Warning"):
            self._append_status("Image position not available", severity="warning")
        return 0.0, 0.0

    def update_fusion_controls_series_list(self) -> None:
        """Update fusion controls with available series."""
        studies = self.get_current_studies()
        study_uid = self.get_current_study_uid()


        # Get available series
        series_list = self.fusion_handler.get_available_series_for_fusion(studies, study_uid)


        # Update controls
        current_base = self.fusion_handler.base_series_uid or ""
        current_overlay = self.fusion_handler.overlay_series_uid or ""
        current_viewing_series = self.get_current_series_uid()

        # Auto-initialize or update base series to current viewing series
        # Update base series if it's not set OR if it differs from the current viewing series
        if current_viewing_series:
            # Verify series exists in available series list
            if any(uid == current_viewing_series for uid, _ in series_list):
                if not current_base or current_base != current_viewing_series:
                    self.fusion_handler.set_base_series(current_viewing_series)
                    current_base = current_viewing_series

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


        # Auto-detect compatible series (global check happens inside _auto_detect_fusion_candidates)
        self._auto_detect_fusion_candidates(studies, study_uid, series_list)

        # Update spatial alignment if both series are selected
        # (This handles the case where series list is updated and selections exist)
        if self.fusion_handler.base_series_uid and self.fusion_handler.overlay_series_uid:
            self._update_spatial_alignment()

    def _auto_detect_fusion_candidates(
        self,
        studies: dict[str, Any],
        study_uid: str,
        series_list: list[tuple[str, str]]
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
        if self._check_notification_shown and self._check_notification_shown(study_uid):
            return

        pet_series, ct_series = self._auto_detect_partition_modalities(
            studies, study_uid, series_list
        )
        if not pet_series or not ct_series:
            return

        pair = self._auto_detect_find_compatible_pair(pet_series, ct_series)
        if pair is None:
            return
        ct_uid, ct_name, pet_uid, pet_name = pair
        self._suggest_fusion(ct_uid, ct_name, pet_uid, pet_name)
        if self._mark_notification_shown:
            self._mark_notification_shown(study_uid)

    def _auto_detect_partition_modalities(
        self,
        studies: dict[str, Any],
        study_uid: str,
        series_list: list[tuple[str, str]],
    ) -> tuple[list, list]:
        """Partition series into PET/NM and CT/MR candidate lists."""
        pet_series = []
        ct_series = []
        for series_uid, display_name in series_list:
            datasets = studies[study_uid].get(series_uid, [])
            if not datasets:
                continue
            modality = getattr(datasets[0], "Modality", "")
            if modality in ["PT", "NM"]:
                pet_series.append((series_uid, display_name, datasets))
            elif modality in ["CT", "MR"]:
                ct_series.append((series_uid, display_name, datasets))
        return pet_series, ct_series

    def _auto_detect_find_compatible_pair(
        self, pet_series: list, ct_series: list
    ) -> tuple[str, str, str, str] | None:
        """
        Find the first FoR-compatible PET/CT pair.

        Returns:
            ``(ct_uid, ct_name, pet_uid, pet_name)`` or ``None``.
        """
        for pet_uid, pet_name, pet_datasets in pet_series:
            for ct_uid, ct_name, ct_datasets in ct_series:
                if self.fusion_handler.check_frame_of_reference_match(
                    pet_datasets, ct_datasets
                ):
                    return ct_uid, ct_name, pet_uid, pet_name
        return None

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
        _ = (base_uid, overlay_uid)  # retained for future deep-link into fusion setup
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

