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
from collections.abc import Callable
from datetime import datetime
from typing import Any

import numpy as np
from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF

from core.dicom_processor import DICOMProcessor
from gui.image_viewer import ImageViewer
from gui.main_window import MainWindow
from gui.window_level_controls import WindowLevelControls
from utils.debug_flags import DEBUG_DIAG, DEBUG_LAYOUT
from utils.dicom_utils import get_composite_series_key
from utils.privacy.console import print_redacted


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
        overlay_coordinator: Callable[..., None] | None = None,
        roi_coordinator: Callable[..., None] | None = None,
        display_rois_for_slice: Callable[..., None] | None = None
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
        self.current_window_center: float | None = None
        self.current_window_width: float | None = None
        self.window_level_user_modified = False  # Track if user has manually changed window/level

        # Window/level presets from DICOM tags
        self.window_level_presets: list[tuple[float, float, bool, str | None]] = []
        # Rich preset objects (from ``build_preset_list``) paralleling the legacy
        # tuple list above; populated by the slice W/L resolver. ``Any`` element
        # type avoids a GUI->core import cycle.
        self._wl_preset_objects: list[Any] = []
        self.current_preset_index: int = 0  # 0 = default/first preset

        # Initial view state for reset functionality
        self.initial_zoom: float | None = None
        self.initial_h_scroll: int | None = None
        self.initial_v_scroll: int | None = None
        self.initial_scene_center: QPointF | None = None  # Scene center point in scene coordinates
        self.initial_window_center: float | None = None
        self.initial_window_width: float | None = None
        self.initial_fit_zoom = 1.0  # Store the fit-to-view zoom factor for export font scaling

        # Series defaults storage: key is series identifier (StudyInstanceUID + composite_series_key)
        # Value is dict with: window_center, window_width, zoom, h_scroll, v_scroll, scene_center, image_inverted
        # composite_series_key includes SeriesNumber if available
        self.series_defaults: dict[str, dict[str, Any]] = {}
        # Last user-adjusted W/L per series (study+composite series key), for restore when switching back.
        self._user_wl_cache: dict[str, dict[str, float]] = {}

        # Track current series identifier for comparison
        self.current_series_identifier: str | None = None

        # Rescale state management
        self.use_rescaled_values: bool = False  # Default to False, will be set based on dataset
        self.rescale_slope: float | None = None
        self.rescale_intercept: float | None = None
        self.rescale_type: str | None = None

        # Viewport resize state - store scene center to preserve centered view
        self.saved_scene_center: QPointF | None = None
        # Viewport size (px) after last handle_viewport_resized image refit — optional no-op when unchanged + fit+centered
        self._viewport_pixel_size_at_last_resize: tuple[int, int] | None = None

        # Current dataset reference (needed for some operations)
        self.current_dataset: Dataset | None = None

        # Current studies and slice info (needed for reset view)
        self.current_studies: dict[str, dict[str, list[Dataset]]] = {}
        self.current_study_uid: str = ""
        self.current_series_uid: str = ""
        self.current_slice_index: int = 0

        # Series pixel range storage (for window width slider maximum)
        self.series_pixel_min: float | None = None
        self.series_pixel_max: float | None = None

        # Callback for redisplaying current slice via slice display manager
        self.redisplay_slice_callback: Callable[[bool], None] | None = None

    def set_series_navigator(self, series_navigator) -> None:
        """
        Set the series navigator reference.
        
        Args:
            series_navigator: SeriesNavigator instance
        """
        self.series_navigator = series_navigator

    def set_redisplay_slice_callback(self, callback: Callable[[bool], None]) -> None:
        """
        Set callback used to redisplay the current slice via SliceDisplayManager.
        
        Args:
            callback: Callable accepting preserve_view flag
        """
        self.redisplay_slice_callback = callback

    def _redisplay_current_slice(self, preserve_view: bool) -> None:
        """
        Redisplay the current slice via the registered callback.
        
        Args:
            preserve_view: True to preserve zoom/pan, False to refit
        """
        if self.redisplay_slice_callback:
            self.redisplay_slice_callback(preserve_view)

    def apply_window_level_from_context_menu_preset(
        self, center: float, width: float, preset_index: int
    ) -> None:
        """
        Apply window/level after the user picks a context-menu preset.

        Does not run ``handle_window_changed``: that path compares presets using
        ``match_center`` / ``match_width`` that may still reflect the *previous*
        W/L when ``window_changed`` fires immediately after a preset change, which
        incorrectly re-matched the old preset and reset ``current_preset_index``
        (context-menu checkmark one step behind).

        Inputs:
            - center, width: values already aligned with ``use_rescaled_values``
            - preset_index: index into ``window_level_presets``

        Outputs:
            - Updates ``current_window_center``, ``current_window_width``,
              ``current_preset_index``, ``window_level_user_modified``, then
              redisplays the current slice with ``preserve_view=True``.
        """
        self.current_preset_index = preset_index
        self.window_level_user_modified = False
        self.current_window_center = center
        self.current_window_width = width
        self._redisplay_current_slice(preserve_view=True)

    def get_initial_fit_zoom(self) -> float:
        """
        Get the initial fit-to-view zoom factor for the current series.
        This is the zoom level that would be used when Reset View is called.
        
        Returns:
            Initial fit zoom factor (default 1.0)
        """
        if self.current_dataset is None:
            return 1.0

        series_identifier = self.get_series_identifier(self.current_dataset)
        if series_identifier in self.series_defaults:
            return self.series_defaults[series_identifier].get('initial_fit_zoom', 1.0)

        return self.initial_fit_zoom

    def get_series_identifier(self, dataset: Dataset) -> str:
        """
        Get a unique identifier for a study/series combination.
        Uses StudyInstanceUID and composite series key (SeriesInstanceUID + SeriesNumber).
        
        Args:
            dataset: pydicom Dataset
            
        Returns:
            Series identifier string in format: "StudyInstanceUID_composite_series_key"
            where composite_series_key is "SeriesInstanceUID_SeriesNumber" or "SeriesInstanceUID"
        """
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        composite_series_key = get_composite_series_key(dataset)
        return f"{study_uid}_{composite_series_key}"

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
        return new_series_identifier != self.current_series_identifier

    def _capture_global_initial_view_fallbacks(self) -> None:
        """Store global fallback zoom, pan, and window/level for reset."""
        if self.initial_zoom is None:
            self.initial_zoom = self.image_viewer.current_zoom

        if self.initial_h_scroll is None:
            self.initial_h_scroll = self.image_viewer.horizontalScrollBar().value()
        if self.initial_v_scroll is None:
            self.initial_v_scroll = self.image_viewer.verticalScrollBar().value()

        if self.initial_scene_center is None:
            scene_center = self.image_viewer.get_viewport_center_scene()
            if scene_center is not None:
                self.initial_scene_center = scene_center

        if self.initial_window_center is None:
            self.initial_window_center = self.current_window_center
        if self.initial_window_width is None:
            self.initial_window_width = self.current_window_width

    def _upsert_series_defaults_from_current_view(self, scene_center: QPointF | None) -> None:
        """Update series defaults with current view state including window/level."""
        series_id = self.current_series_identifier
        if series_id is None:
            return
        self.series_defaults[series_id].update({
            'window_center': self.current_window_center,
            'window_width': self.current_window_width,
            'zoom': self.image_viewer.current_zoom,
            'h_scroll': self.image_viewer.horizontalScrollBar().value(),
            'v_scroll': self.image_viewer.verticalScrollBar().value(),
            'scene_center': scene_center,
            'use_rescaled_values': self.use_rescaled_values,
            'image_inverted': self.image_viewer.image_inverted
        })

    def _restore_stored_series_wl_and_refresh(self, scene_center: QPointF | None) -> None:
        """Restore stored W/L, redisplay, and update zoom/pan without overwriting W/L."""
        series_id = self.current_series_identifier
        if series_id is None:
            return
        series_entry = self.series_defaults[series_id]
        stored_wc = series_entry['window_center']
        stored_ww = series_entry['window_width']
        stored_rescaled = series_entry['use_rescaled_values']

        self.current_window_center = stored_wc
        self.current_window_width = stored_ww

        unit = self.rescale_type if (stored_rescaled and self.rescale_type) else None
        self.window_level_controls.set_window_level(
            stored_wc, stored_ww, block_signals=True, unit=unit
        )

        self._redisplay_current_slice(preserve_view=True)

        if (self.series_navigator and self.current_study_uid and self.current_series_uid and
                self.current_study_uid in self.current_studies and
                self.current_series_uid in self.current_studies[self.current_study_uid]):
            series_datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
            if series_datasets:
                first_dataset = series_datasets[0]
                self.series_navigator.regenerate_series_thumbnail(
                    self.current_study_uid,
                    self.current_series_uid,
                    first_dataset,
                    stored_wc,
                    stored_ww,
                    stored_rescaled
                )

        series_entry.update({
            'zoom': self.image_viewer.current_zoom,
            'h_scroll': self.image_viewer.horizontalScrollBar().value(),
            'v_scroll': self.image_viewer.verticalScrollBar().value(),
            'scene_center': scene_center,
            'image_inverted': self.image_viewer.image_inverted
        })
        series_entry['window_level_defaults_set'] = True

    def store_initial_view_state(self) -> None:
        """
        Store the initial view state (zoom, pan, window/level) for reset functionality.
        Stores per-series defaults in addition to global initial values.
        
        Called after the first image is displayed and the view has settled.
        """
        if self.image_viewer.image_item is None:
            return

        self._capture_global_initial_view_fallbacks()

        if self.current_series_identifier:
            scene_center = self.image_viewer.get_viewport_center_scene()

            if self.current_series_identifier not in self.series_defaults:
                self.series_defaults[self.current_series_identifier] = {
                    'window_center': self.current_window_center,
                    'window_width': self.current_window_width,
                    'zoom': self.image_viewer.current_zoom,
                    'h_scroll': self.image_viewer.horizontalScrollBar().value(),
                    'v_scroll': self.image_viewer.verticalScrollBar().value(),
                    'scene_center': scene_center,
                    'use_rescaled_values': self.use_rescaled_values,
                    'image_inverted': self.image_viewer.image_inverted
                }
            elif self.series_defaults[self.current_series_identifier].get('window_level_defaults_set', False):
                self._restore_stored_series_wl_and_refresh(scene_center)
            else:
                self._upsert_series_defaults_from_current_view(scene_center)

    def _load_reset_defaults_for_series(
        self, series_identifier: str
    ) -> tuple[Any, float | None, float | None, bool | None]:
        """Load zoom and W/L defaults for reset from series or global state."""
        if series_identifier in self.series_defaults:
            defaults = self.series_defaults[series_identifier]
            return (
                defaults.get('zoom'),
                defaults.get('window_center'),
                defaults.get('window_width'),
                defaults.get('use_rescaled_values'),
            )
        return (
            self.initial_zoom,
            self.initial_window_center,
            self.initial_window_width,
            None,
        )

    def _convert_reset_wl_for_current_rescale(
        self,
        reset_window_center: float,
        reset_window_width: float,
        reset_use_rescaled_values: bool,
    ) -> tuple[float, float]:
        """Convert stored W/L to match the current rescale display mode."""
        if reset_use_rescaled_values == self.use_rescaled_values:
            return reset_window_center, reset_window_width

        if reset_use_rescaled_values and not self.use_rescaled_values:
            if (self.rescale_slope is not None and self.rescale_intercept is not None and
                    self.rescale_slope != 0.0):  # NOSONAR(S1244)
                return self.dicom_processor.convert_window_level_rescaled_to_raw(
                    reset_window_center, reset_window_width,
                    self.rescale_slope, self.rescale_intercept
                )
        elif not reset_use_rescaled_values and self.use_rescaled_values:
            if self.rescale_slope is not None and self.rescale_intercept is not None:
                return self.dicom_processor.convert_window_level_raw_to_rescaled(
                    reset_window_center, reset_window_width,
                    self.rescale_slope, self.rescale_intercept
                )
        return reset_window_center, reset_window_width

    def _recalculate_missing_reset_wl(self) -> tuple[float | None, float | None]:
        """Recalculate window/level defaults from current dataset when missing."""
        if not (self.current_studies and self.current_study_uid and self.current_series_uid):
            return None, None
        if (self.current_study_uid not in self.current_studies or
                self.current_series_uid not in self.current_studies[self.current_study_uid]):
            return None, None

        series_datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
        if not series_datasets:
            return None, None

        dataset = series_datasets[0]
        use_rescaled = self.use_rescaled_values

        try:
            series_pixel_min, series_pixel_max = self.dicom_processor.get_series_pixel_value_range(
                series_datasets, apply_rescale=use_rescaled
            )
            self.set_series_pixel_range(series_pixel_min, series_pixel_max)
        except Exception:
            series_pixel_min = None
            series_pixel_max = None

        wc, ww, is_rescaled = self.dicom_processor.get_window_level_from_dataset(
            dataset,
            rescale_slope=self.rescale_slope,
            rescale_intercept=self.rescale_intercept
        )
        if wc is not None and ww is not None:
            return self._convert_dataset_wl_to_use_rescaled(wc, ww, is_rescaled, use_rescaled)

        if series_pixel_min is not None and series_pixel_max is not None:
            return self._wl_from_series_pixel_range(
                series_datasets, series_pixel_min, series_pixel_max, use_rescaled
            )

        return self._wl_from_single_slice_fallback(dataset, use_rescaled)

    def _convert_dataset_wl_to_use_rescaled(
        self,
        wc: float,
        ww: float,
        is_rescaled: bool,
        use_rescaled: bool,
    ) -> tuple[float, float]:
        """Convert dataset W/L values to the requested rescale display mode."""
        if is_rescaled and not use_rescaled:
            if (self.rescale_slope is not None and self.rescale_intercept is not None and
                    self.rescale_slope != 0.0):  # NOSONAR(S1244)
                return self.dicom_processor.convert_window_level_rescaled_to_raw(
                    wc, ww, self.rescale_slope, self.rescale_intercept
                )
        elif not is_rescaled and use_rescaled:
            if self.rescale_slope is not None and self.rescale_intercept is not None:
                return self.dicom_processor.convert_window_level_raw_to_rescaled(
                    wc, ww, self.rescale_slope, self.rescale_intercept
                )
        return wc, ww

    def _wl_from_series_pixel_range(
        self,
        series_datasets: list[Dataset],
        series_pixel_min: float,
        series_pixel_max: float,
        use_rescaled: bool,
    ) -> tuple[float, float]:
        """Derive W/L from series pixel range statistics."""
        midpoint = (series_pixel_min + series_pixel_max) / 2.0
        if series_datasets:
            median = self.dicom_processor.get_series_pixel_median(
                series_datasets, apply_rescale=use_rescaled
            )
            reset_window_center = midpoint if median is None else max(median, midpoint)
        else:
            reset_window_center = midpoint
        reset_window_width = series_pixel_max - series_pixel_min
        if reset_window_width <= 0:
            reset_window_width = 1.0
        return reset_window_center, reset_window_width

    def _wl_from_single_slice_fallback(
        self, dataset: Dataset, use_rescaled: bool
    ) -> tuple[float | None, float | None]:
        """Fallback W/L calculation from a single slice pixel range."""
        try:
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                dataset, apply_rescale=use_rescaled
            )
            if pixel_min is None or pixel_max is None:
                return None, None

            pixel_array = self.dicom_processor.get_pixel_array(dataset)
            midpoint = (pixel_min + pixel_max) / 2.0
            if pixel_array is not None:
                if use_rescaled:
                    rescale_slope, rescale_intercept, _ = self.dicom_processor.get_rescale_parameters(dataset)
                    if rescale_slope is not None and rescale_intercept is not None:
                        pixel_array = (
                            pixel_array.astype(np.float32) * float(rescale_slope) + float(rescale_intercept)
                        )
                non_zero_values = pixel_array[pixel_array != 0]
                if len(non_zero_values) > 0:
                    median = float(np.median(non_zero_values))
                    reset_window_center = max(median, midpoint)
                else:
                    reset_window_center = midpoint
            else:
                reset_window_center = midpoint

            reset_window_width = pixel_max - pixel_min
            if reset_window_width <= 0:
                reset_window_width = 1.0
            return reset_window_center, reset_window_width
        except Exception:
            return None, None

    def _wl_ranges_from_pixel_extrema(
        self, pixel_min: float, pixel_max: float
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Build center/width control ranges from slice extrema, preferring series range."""
        series_pixel_min, series_pixel_max = self.get_series_pixel_range()
        if series_pixel_min is not None and series_pixel_max is not None:
            center_range = (series_pixel_min, series_pixel_max)
            width_range = (1.0, max(1.0, series_pixel_max - series_pixel_min))
        else:
            center_range = (pixel_min, pixel_max)
            width_range = (1.0, max(1.0, pixel_max - pixel_min))
        return center_range, width_range

    def _apply_reset_window_level_values(
        self, reset_window_center: float | None, reset_window_width: float | None
    ) -> None:
        """Push reset W/L into controls and view-state fields when both values exist."""
        if reset_window_center is None or reset_window_width is None:
            return
        unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
        self.window_level_controls.set_window_level(
            reset_window_center,
            reset_window_width,
            block_signals=True,
            unit=unit,
        )
        self.current_window_center = reset_window_center
        self.current_window_width = reset_window_width
        self.window_level_user_modified = False

    def _apply_reset_rescale_and_wl_controls(
        self,
        reset_use_rescaled_values: bool,
        reset_window_center: float | None,
        reset_window_width: float | None,
    ) -> None:
        """Apply rescale state, control ranges, and window/level after reset."""
        self.use_rescaled_values = reset_use_rescaled_values
        self.main_window.set_rescale_toggle_state(reset_use_rescaled_values)
        self.image_viewer.set_rescale_toggle_state(reset_use_rescaled_values)

        if self.current_dataset is not None:
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                self.current_dataset, apply_rescale=self.use_rescaled_values
            )
            if pixel_min is not None and pixel_max is not None:
                center_range, width_range = self._wl_ranges_from_pixel_extrema(
                    pixel_min, pixel_max
                )
                self.window_level_controls.set_ranges(center_range, width_range)

            unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
            self.window_level_controls.set_unit(unit)

        self._apply_reset_window_level_values(reset_window_center, reset_window_width)

    def reset_view(self, skip_redisplay: bool = False) -> None:
        """
        Reset view to initial state (zoom, pan, window center/level).
        
        Uses series-specific defaults if available, otherwise falls back to global initial values.
        
        Args:
            skip_redisplay: If True, skip the internal redisplay (caller will handle it)
        """
        if self.current_dataset is None:
            return

        getattr(self.current_dataset, 'Modality', 'Unknown')

        series_identifier = self.get_series_identifier(self.current_dataset)
        self.clear_user_window_level(series_identifier)

        reset_zoom, reset_window_center, reset_window_width, reset_use_rescaled_values = (
            self._load_reset_defaults_for_series(series_identifier)
        )

        if (reset_window_center is not None and reset_window_width is not None and
                reset_use_rescaled_values is not None and
                reset_use_rescaled_values != self.use_rescaled_values):
            reset_window_center, reset_window_width = self._convert_reset_wl_for_current_rescale(
                reset_window_center, reset_window_width, reset_use_rescaled_values
            )

        if reset_window_center is None or reset_window_width is None:
            recalc_wc, recalc_ww = self._recalculate_missing_reset_wl()
            if recalc_wc is not None:
                reset_window_center = recalc_wc
            if recalc_ww is not None:
                reset_window_width = recalc_ww

        if reset_use_rescaled_values is None:
            reset_use_rescaled_values = (
                self.rescale_slope is not None and self.rescale_intercept is not None
            )

        if reset_zoom is None:
            return

        self._apply_reset_rescale_and_wl_controls(
            reset_use_rescaled_values, reset_window_center, reset_window_width
        )

        if skip_redisplay:
            return

        self._redisplay_current_slice(preserve_view=False)

    def _resolve_match_center_width_for_presets(
        self, center: float, width: float
    ) -> tuple[float, float]:
        """Resolve W/L values used for preset matching (handles stale series values)."""
        match_tolerance = 0.1
        values_match_stored = (
            self.current_window_center is not None and
            self.current_window_width is not None and
            abs(self.current_window_center - center) < match_tolerance and
            abs(self.current_window_width - width) < match_tolerance
        )

        if (self.window_level_presets and not values_match_stored and
                self.current_window_center is not None and self.current_window_width is not None):
            match_center = self.current_window_center
            match_width = self.current_window_width
            self.current_window_center = center
            self.current_window_width = width
            return match_center, match_width

        self.current_window_center = center
        self.current_window_width = width
        return center, width

    def _convert_preset_wl_for_current_rescale(
        self, preset_wc: float, preset_ww: float, preset_is_rescaled: bool
    ) -> tuple[float, float]:
        """Convert preset W/L values to match the current rescale display mode."""
        if preset_is_rescaled and not self.use_rescaled_values:
            if (self.rescale_slope is not None and self.rescale_intercept is not None and
                    self.rescale_slope != 0.0):  # NOSONAR(S1244)
                return self.dicom_processor.convert_window_level_rescaled_to_raw(
                    preset_wc, preset_ww, self.rescale_slope, self.rescale_intercept
                )
        elif not preset_is_rescaled and self.use_rescaled_values:
            if self.rescale_slope is not None and self.rescale_intercept is not None:
                return self.dicom_processor.convert_window_level_raw_to_rescaled(
                    preset_wc, preset_ww, self.rescale_slope, self.rescale_intercept
                )
        return preset_wc, preset_ww

    def _match_window_to_presets(self, match_center: float, match_width: float) -> bool:
        """Return True if W/L matches a loaded preset."""
        center_tolerance = max(0.1, abs(match_center) * 0.001)
        width_tolerance = max(0.1, abs(match_width) * 0.001)

        for idx, (preset_wc, preset_ww, preset_is_rescaled, _preset_name_val) in enumerate(
            self.window_level_presets
        ):
            compare_wc, compare_ww = self._convert_preset_wl_for_current_rescale(
                preset_wc, preset_ww, preset_is_rescaled
            )
            if (abs(compare_wc - match_center) < center_tolerance and
                    abs(compare_ww - match_width) < width_tolerance):
                self.current_preset_index = idx
                self.window_level_user_modified = False
                return True
        return False

    def handle_window_changed(self, center: float, width: float) -> None:
        """
        Handle window/level change.
        
        Args:
            center: Window center
            width: Window width
        """
        if DEBUG_LAYOUT:
            ts = datetime.now().strftime("%H:%M:%S.%f")
            print(f"[DEBUG-LAYOUT] [{ts}] handle_window_changed: view_state_manager id={id(self)} image_viewer id={id(self.image_viewer)} center={center:.2f} width={width:.2f}")

        match_center, match_width = self._resolve_match_center_width_for_presets(center, width)

        if not self.window_level_presets:
            self.window_level_user_modified = True
            matched_preset = False
        else:
            matched_preset = self._match_window_to_presets(match_center, match_width)

        if not matched_preset:
            self.window_level_user_modified = True

        from core.view_state_handlers import update_zoom_wl_status_from_view_state

        update_zoom_wl_status_from_view_state(self)

        self._redisplay_current_slice(preserve_view=True)

    def _convert_wl_for_rescale_toggle(
        self, checked: bool, current_center: float | None, current_width: float | None
    ) -> tuple[float | None, float | None]:
        """Convert W/L values when toggling rescale display mode."""
        if (current_center is None or current_width is None or
                self.rescale_slope is None or self.rescale_intercept is None or
                self.rescale_slope == 0.0):  # NOSONAR(S1244)
            return current_center, current_width

        if self.use_rescaled_values and not checked:
            return self.dicom_processor.convert_window_level_rescaled_to_raw(
                current_center, current_width, self.rescale_slope, self.rescale_intercept
            )
        if not self.use_rescaled_values and checked:
            return self.dicom_processor.convert_window_level_raw_to_rescaled(
                current_center, current_width, self.rescale_slope, self.rescale_intercept
            )
        return current_center, current_width

    def _compute_rescale_toggle_control_ranges(
        self, pixel_min: float, pixel_max: float
    ) -> tuple[tuple[float, float], tuple[float, float]]:
        """Compute W/L control ranges after a rescale toggle."""
        if self.current_studies and self.current_study_uid and self.current_series_uid:
            if (self.current_study_uid in self.current_studies and
                    self.current_series_uid in self.current_studies[self.current_study_uid]):
                series_datasets = self.current_studies[self.current_study_uid][self.current_series_uid]
                try:
                    series_pixel_min, series_pixel_max = self.dicom_processor.get_series_pixel_value_range(
                        series_datasets, apply_rescale=self.use_rescaled_values
                    )
                    self.set_series_pixel_range(series_pixel_min, series_pixel_max)
                    if series_pixel_min is not None and series_pixel_max is not None:
                        return (
                            (series_pixel_min, series_pixel_max),
                            (1.0, max(1.0, series_pixel_max - series_pixel_min)),
                        )
                except Exception as e:
                    error_type = type(e).__name__
                    print_redacted(
                        f"Error recalculating series pixel range for rescale toggle ({error_type}): {e}"
                    )
                    self.clear_series_pixel_range()

        return (
            (pixel_min, pixel_max),
            (1.0, max(1.0, pixel_max - pixel_min)),
        )

    def _refresh_ranges_after_rescale_toggle(
        self, current_center: float | None, current_width: float | None
    ) -> None:
        """Recalculate control ranges and W/L after rescale toggle."""
        dataset = self.current_dataset
        if dataset is None:
            return
        pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
            dataset, apply_rescale=self.use_rescaled_values
        )
        if pixel_min is not None and pixel_max is not None:
            center_range, width_range = self._compute_rescale_toggle_control_ranges(
                pixel_min, pixel_max
            )
            self.window_level_controls.set_ranges(center_range, width_range)

        unit = self.rescale_type if (self.use_rescaled_values and self.rescale_type) else None
        self.window_level_controls.set_unit(unit)

        if current_center is not None and current_width is not None:
            self.current_window_center = current_center
            self.current_window_width = current_width
            self.window_level_controls.set_window_level(
                current_center, current_width, block_signals=True, unit=unit
            )

        self._redisplay_current_slice(preserve_view=True)

    def handle_rescale_toggle(self, checked: bool) -> None:
        """
        Handle rescale toggle change from toolbar or context menu.
        
        Converts current window/level values to preserve image appearance when toggling.
        
        Args:
            checked: True to use rescaled values, False to use raw values
        """
        current_center = self.current_window_center
        current_width = self.current_window_width

        current_center, current_width = self._convert_wl_for_rescale_toggle(
            checked, current_center, current_width
        )

        self.use_rescaled_values = checked
        self.main_window.set_rescale_toggle_state(checked)
        self.image_viewer.set_rescale_toggle_state(checked)

        if self.current_dataset is not None:
            self._refresh_ranges_after_rescale_toggle(current_center, current_width)

        from core.view_state_handlers import update_zoom_wl_status_from_view_state

        update_zoom_wl_status_from_view_state(self)

    def _is_subwindow_focused(self) -> bool:
        """Return True when this viewer's subwindow is focused (or not in a subwindow)."""
        from gui.sub_window_container import SubWindowContainer
        parent = self.image_viewer.parent()
        if isinstance(parent, SubWindowContainer):
            return parent.is_focused
        return True

    def _refit_image_after_viewport_resize(self, vw: int, vh: int) -> None:
        """Fit or recenter image after viewport size change."""
        if self.saved_scene_center is not None:
            self.image_viewer.fit_to_view(center_image=False)
            self.image_viewer.centerOn(self.saved_scene_center)
            self.saved_scene_center = None
            return

        skip_fit = (
            self._viewport_pixel_size_at_last_resize is not None
            and self._viewport_pixel_size_at_last_resize == (vw, vh)
            and self.image_viewer.is_effectively_fit_and_centered()
        )
        if not skip_fit:
            self.image_viewer.fit_to_view(center_image=True)

    def _update_overlays_after_viewport_resize(self, is_focused: bool) -> None:
        """Update overlay positions after viewport resize."""
        if self.current_dataset is None:
            return
        if self.overlay_manager.use_widget_overlays or is_focused:
            self.overlay_manager.update_overlay_positions(self.image_viewer.scene)

    def handle_zoom_changed(self, _zoom_level: float) -> None:
        """
        Handle zoom level change.
        
        Updates overlay positions immediately to keep text anchored to viewport edges
        during zoom operations, eliminating jitter.
        
        Updates overlay for all subwindows (focused and unfocused) to ensure
        overlays stay fixed relative to viewport, not the image.
        
        Args:
            zoom_level: Current zoom level
        """

        # Update overlay positions immediately when zoom changes
        # This eliminates jitter by updating synchronously with zoom changes,
        # rather than waiting for the delayed transform_changed signal
        # We update for ALL subwindows (focused and unfocused) so overlays
        # stay anchored to viewport edges, not the image
        if self.current_dataset is not None:
            self.overlay_manager.update_overlay_positions(self.image_viewer.scene)

    def handle_transform_changed(self) -> None:
        """
        Handle view transform change (zoom/pan).
        
        Updates overlay positions to keep text anchored to viewport edges.
        This is called after the transform is fully applied.
        
        Updates overlay for all subwindows (focused and unfocused) to ensure
        overlays stay fixed relative to viewport, not the image.
        """
        # Diagnostic logging: Transform change event (only log panning, not zoom)
        view_transform = self.image_viewer.transform()
        translation_x = view_transform.m31()
        translation_y = view_transform.m32()
        # Only log if there's actual translation (panning) to reduce noise
        if abs(translation_x) > 0.01 or abs(translation_y) > 0.01:
            if DEBUG_DIAG:
                print(f"[DEBUG-DIAG] handle_transform_changed: PAN - transform_scale={view_transform.m11():.6f}, "
                      f"translation=({translation_x:.2f}, {translation_y:.2f})")

        # Update overlay positions when transform changes
        # We update for ALL subwindows (focused and unfocused) so overlays
        # stay anchored to viewport edges, not the image
        if self.current_dataset is not None:
            self.overlay_manager.update_overlay_positions(self.image_viewer.scene)

    def handle_viewport_resizing(self) -> None:
        """
        Handle viewport resize start (when splitter starts moving, series navigator visibility changes, or layout changes).
        
        Captures the current viewport center in scene coordinates before the resize
        completes, so we can restore it after resize to maintain the centered view.
        """
        # Debug: trace which viewer captures center (drift investigation)
        scene_center = None
        if self.image_viewer.image_item is not None:
            scene_center = self.image_viewer.get_viewport_center_scene()
            if scene_center is not None:
                self.saved_scene_center = scene_center
        if DEBUG_LAYOUT:
            ts = datetime.now().strftime("%H:%M:%S.%f")
            print(f"[DEBUG-LAYOUT] [{ts}] handle_viewport_resizing: view_state_manager id={id(self)} image_viewer id={id(self.image_viewer)} saved_scene_center={scene_center}")

    def handle_viewport_resized(self) -> None:
        """
        Handle viewport resize (when splitter moves, series navigator visibility changes, or layout changes).
        
        Updates overlay positions to keep text anchored to viewport edges
        when the left or right panels are resized.
        Also rescales the image to fill the viewport and restores the centered view
        if a scene center was captured (preserves viewport center for all resize scenarios).
        
        Only updates overlay if the subwindow is focused, preventing overlay movement
        when hovering over unfocused subwindows.
        """
        is_focused = self._is_subwindow_focused()
        if DEBUG_LAYOUT:
            had_center = self.saved_scene_center is not None
            center_val = self.saved_scene_center
            ts = datetime.now().strftime("%H:%M:%S.%f")
            if DEBUG_LAYOUT:
                print(f"[DEBUG-LAYOUT] [{ts}] handle_viewport_resized: view_state_manager id={id(self)} image_viewer id={id(self.image_viewer)} is_focused={is_focused} had_saved_scene_center={had_center} center={center_val}")

        if self.image_viewer.image_item is not None:
            vp = self.image_viewer.viewport()
            vw = int(vp.width()) if vp is not None else 0
            vh = int(vp.height()) if vp is not None else 0
            self._refit_image_after_viewport_resize(vw, vh)
            self._viewport_pixel_size_at_last_resize = (vw, vh)
        else:
            self._viewport_pixel_size_at_last_resize = None

        self._update_overlays_after_viewport_resize(is_focused)

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

    def save_user_window_level(self) -> None:
        """
        Cache current W/L in RAM for ``current_series_identifier`` when the user changed it.

        Session-only: not written to config; cleared in ``reset_series_tracking`` (e.g. new
        load / close-all paths) and when the app exits.
        """
        sid = self.current_series_identifier
        if not sid:
            return
        if not self.window_level_user_modified:
            return
        if self.current_window_center is None or self.current_window_width is None:
            return
        self._user_wl_cache[sid] = {
            "window_center": float(self.current_window_center),
            "window_width": float(self.current_window_width),
        }

    def get_user_window_level(self, series_id: str) -> dict[str, float] | None:
        """Return cached user W/L for *series_id*, or None."""
        return self._user_wl_cache.get(series_id)

    def clear_user_window_level(self, series_id: str) -> None:
        """Drop cached user W/L for one series (e.g. after Reset View)."""
        self._user_wl_cache.pop(series_id, None)

    def clear_all_user_window_levels(self) -> None:
        """Clear all cached user W/L (e.g. when closing all studies)."""
        self._user_wl_cache.clear()

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
        self._wl_preset_objects = []  # type: ignore[attr-defined]
        self.current_preset_index = 0

    def reset_series_tracking(self) -> None:
        """Reset series tracking when loading new files."""
        self.current_series_identifier = None
        # Clear series pixel range when resetting series tracking
        self.clear_series_pixel_range()
        # Clear series defaults when loading new files so window/level resets to defaults
        # even if the same series is loaded again
        self.series_defaults.clear()
        self._user_wl_cache.clear()

    def set_rescale_parameters(self, slope: float | None, intercept: float | None, rescale_type: str | None) -> None:
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

    def set_current_series_identifier(self, identifier: str | None) -> None:
        """
        Set current series identifier.
        
        Args:
            identifier: Series identifier string
        """
        self.current_series_identifier = identifier

    def get_series_inversion_state(self, series_identifier: str | None = None) -> bool:
        """
        Get inversion state for a series.
        
        Args:
            series_identifier: Optional series identifier. If None, uses current series identifier.
            
        Returns:
            True if image is inverted for this series, False otherwise
        """
        if series_identifier is None:
            series_identifier = self.current_series_identifier

        if series_identifier and series_identifier in self.series_defaults:
            return self.series_defaults[series_identifier].get('image_inverted', False)
        return False

    def set_series_inversion_state(self, series_identifier: str | None = None, inverted: bool = False) -> None:
        """
        Set inversion state for a series.
        
        Args:
            series_identifier: Optional series identifier. If None, uses current series identifier.
            inverted: True if image should be inverted, False otherwise
        """
        if series_identifier is None:
            series_identifier = self.current_series_identifier

        if series_identifier:
            if series_identifier not in self.series_defaults:
                self.series_defaults[series_identifier] = {}
            self.series_defaults[series_identifier]['image_inverted'] = inverted

    def set_current_data_context(
        self,
        current_dataset: Dataset | None,
        current_studies: dict[str, dict[str, list[Dataset]]],
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

    def set_series_pixel_range(self, pixel_min: float | None, pixel_max: float | None) -> None:
        """
        Set the pixel value range for the current series.
        
        Args:
            pixel_min: Minimum pixel value across the series
            pixel_max: Maximum pixel value across the series
        """
        self.series_pixel_min = pixel_min
        self.series_pixel_max = pixel_max

    def get_series_pixel_range(self) -> tuple[float | None, float | None]:
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

    # ------------------------------------------------------------------
    # Orientation persistence (flip / rotate) — per-series
    # ------------------------------------------------------------------

    def save_orientation(self, series_identifier: str | None = None) -> None:
        """
        Persist the current flip/rotation state for a series.

        Reads ``_flip_h``, ``_flip_v``, and ``_rotation_deg`` directly from the
        associated ``ImageViewer`` and stores them under ``series_defaults`` so
        they survive a series switch and can be restored via ``restore_orientation``.

        Args:
            series_identifier: Key for the series.  Defaults to
                ``self.current_series_identifier`` when ``None``.
        """
        if series_identifier is None:
            series_identifier = self.current_series_identifier
        if not series_identifier:
            return
        if series_identifier not in self.series_defaults:
            self.series_defaults[series_identifier] = {}
        self.series_defaults[series_identifier].update({
            'flip_h': self.image_viewer._flip_h,
            'flip_v': self.image_viewer._flip_v,
            'rotation_deg': self.image_viewer._rotation_deg,
        })

    def restore_orientation(self, series_identifier: str | None = None) -> None:
        """
        Restore the saved flip/rotation state for a series, or reset to defaults.

        If no orientation data has been saved for *series_identifier* the viewer is
        reset to the neutral orientation (no flip, rotation 0°) without triggering
        the orientation-changed callback (to avoid a redundant save).

        Args:
            series_identifier: Key for the series.  Defaults to
                ``self.current_series_identifier`` when ``None``.
        """
        if series_identifier is None:
            series_identifier = self.current_series_identifier
        defaults = self.series_defaults.get(series_identifier or '', {}) if series_identifier else {}
        flip_h = defaults.get('flip_h', False)
        flip_v = defaults.get('flip_v', False)
        rotation_deg = defaults.get('rotation_deg', 0)
        # Apply without going through the public helpers so we avoid a
        # spurious orientation_changed_callback call before the image is fully loaded.
        self.image_viewer._flip_h = flip_h
        self.image_viewer._flip_v = flip_v
        self.image_viewer._rotation_deg = rotation_deg
        self.image_viewer._apply_view_transform()

