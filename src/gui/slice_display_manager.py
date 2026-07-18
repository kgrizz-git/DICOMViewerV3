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
from collections.abc import Callable
from typing import Any

from PIL import Image
from pydicom.dataset import Dataset
from PySide6.QtWidgets import QMessageBox

from core.dicom_organizer import DICOMOrganizer
from core.dicom_parser import DICOMParser
from core.dicom_processor import DICOMProcessor
from core.slice_display_lut import apply_window_level_rescale_conversion
from core.slice_display_pixels import create_slice_projection_pil_image
from core.slice_window_level_resolver import (
    compute_series_transition_state as _wl_compute_transition_state,
)
from core.slice_window_level_resolver import (
    resolve_window_level_for_series_transition as _wl_resolve_transition,
)
from gui.image_viewer import ImageViewer
from gui.metadata_panel import MetadataPanel
from gui.overlay_manager import OverlayManager
from gui.roi_list_panel import ROIListPanel
from gui.roi_statistics_panel import ROIStatisticsPanel
from gui.slice_navigator import SliceNavigator
from gui.window_level_controls import WindowLevelControls
from tools.annotation_manager import AnnotationManager
from tools.measurement_tool import MeasurementTool
from tools.roi_manager import ROIManager
from utils.debug_flags import DEBUG_MEASUREMENT_SERIES, DEBUG_SERIES, DEBUG_WL
from utils.dicom_utils import (
    get_composite_series_key,
    get_pixel_spacing,
    get_slice_thickness,
)
from utils.perf_timer import perf_timer
from utils.privacy.console import print_redacted


def _make_no_pixel_placeholder_pil(width: int = 640, height: int = 480) -> Image.Image:
    """
    Gray canvas with centered **No Image** text for instances without pixel data (e.g. SR).
    """
    from PIL import ImageDraw, ImageFont

    img = Image.new("RGB", (width, height), (72, 72, 72))
    draw = ImageDraw.Draw(img)
    title = "No Image"
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), title, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(((width - tw) // 2, (height - th) // 2), title, fill=(220, 220, 220), font=font)
    return img


def _overlay_metadata_dataset_for_slice(
    dataset: Dataset,
    current_studies: dict[str, Any],
    current_study_uid: str,
    current_series_uid: str,
    current_slice_index: int,
) -> Dataset:
    """
    Dataset used for corner overlay tags (InstanceNumber, SliceLocation, …).

    Some call paths pass a stale *dataset* (e.g. privacy refresh using
    ``slice_display_manager.current_dataset``) while *current_slice_index* was
    updated from ``subwindow_data``, so InstanceNumber can match another slice
    (e.g. MPR index) while the pixmap is correct. When the study list has a
    slice at *current_slice_index* whose SOPInstanceUID differs from *dataset*,
    use that canonical row for overlay text only (pixel buffer still uses *dataset*).

    MPR views do not use this path for the main reformatted image (they use
    ``MprController`` + synthetic overlay datasets). When *dataset* already
    matches the list row (same SOP), *dataset* is returned unchanged.
    """
    if (
        not current_studies
        or not current_study_uid
        or not current_series_uid
        or current_study_uid not in current_studies
        or current_series_uid not in current_studies[current_study_uid]
    ):
        return dataset
    slist = current_studies[current_study_uid][current_series_uid]
    if not isinstance(slist, list) or not slist:
        return dataset
    if not (0 <= current_slice_index < len(slist)):
        return dataset
    cand = slist[current_slice_index]
    if cand is dataset:
        return dataset
    ds_sop = getattr(dataset, "SOPInstanceUID", None)
    cd_sop = getattr(cand, "SOPInstanceUID", None)
    if ds_sop is None or cd_sop is None:
        return dataset
    if ds_sop != cd_sop:
        return cand
    return dataset


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
        text_annotation_tool=None,
        arrow_annotation_tool=None,
        update_tag_viewer_callback: Callable[..., None] | None = None,
        open_structured_report_browser_callback: Callable[[Dataset], None] | None = None,
        display_rois_callback: Callable[..., None] | None = None,
        display_measurements_callback: Callable[..., None] | None = None,
        roi_list_panel: ROIListPanel | None = None,
        roi_statistics_panel: ROIStatisticsPanel | None = None,
        update_roi_statistics_overlays_callback: Callable[..., None] | None = None,
        annotation_manager: AnnotationManager | None = None,
        dicom_organizer: DICOMOrganizer | None = None,
        fusion_coordinator = None,
        config_manager = None,
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
            open_structured_report_browser_callback: Optional callback ``(dataset,)`` — SR browser or tag viewer
                opens the radiation **summary** dialog; other SR may open the tag viewer until a tree UI exists.
            display_rois_callback: Optional callback to display ROIs
            display_measurements_callback: Optional callback to display measurements
            roi_list_panel: Optional ROI list panel for updating ROI list
            roi_statistics_panel: Optional ROI statistics panel for updating statistics
            annotation_manager: Optional annotation manager for Presentation State and Key Object annotations
            dicom_organizer: Optional DICOM organizer for accessing Presentation States and Key Objects
            fusion_coordinator: Optional fusion coordinator for image fusion
        """
        self.dicom_processor = dicom_processor
        self.image_viewer = image_viewer
        self.metadata_panel = metadata_panel
        self.slice_navigator = slice_navigator
        self.window_level_controls = window_level_controls
        self.roi_manager = roi_manager
        self.measurement_tool = measurement_tool
        self.text_annotation_tool = text_annotation_tool
        self.arrow_annotation_tool = arrow_annotation_tool
        self.overlay_manager = overlay_manager
        self.view_state_manager = view_state_manager
        self.update_tag_viewer_callback = update_tag_viewer_callback
        self.open_structured_report_browser_callback = open_structured_report_browser_callback
        self.display_rois_callback = display_rois_callback
        self.display_measurements_callback = display_measurements_callback
        self.roi_list_panel = roi_list_panel
        self.roi_statistics_panel = roi_statistics_panel
        self.update_roi_statistics_overlays_callback = update_roi_statistics_overlays_callback
        self.annotation_manager = annotation_manager
        self.dicom_organizer = dicom_organizer
        self.fusion_coordinator = fusion_coordinator
        self.config_manager = config_manager

        # Current data context
        self.current_studies: dict[str, dict[str, list[Dataset]]] = {}
        self.current_study_uid: str = ""
        self.current_series_uid: str = ""
        self.current_slice_index: int = 0
        self.current_dataset: Dataset | None = None

        # Intensity projection state
        self.projection_enabled: bool = False
        self.projection_type: str = "aip"  # "aip", "mip", or "minip"
        self.projection_slice_count: int = 4  # 2, 3, 4, 6, or 8

    def get_multiframe_overlay_context(
        self,
        dataset: Dataset | None = None,
        study_uid: str | None = None,
        series_uid: str | None = None,
    ) -> dict[str, int] | None:
        """Return the current dataset's multiframe overlay context, if applicable."""
        if self.dicom_organizer is None:
            return None
        target_dataset = dataset if dataset is not None else self.current_dataset
        if target_dataset is None:
            return None
        target_study_uid = study_uid if study_uid is not None else self.current_study_uid
        target_series_uid = series_uid if series_uid is not None else self.current_series_uid
        if not target_study_uid or not target_series_uid:
            return None
        return self.dicom_organizer.get_multiframe_display_context(
            target_study_uid,
            target_series_uid,
            target_dataset,
        )

    def _measurement_debug_prefix(self, dataset: Dataset, current_slice_index: int) -> str:
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = get_composite_series_key(dataset)
        return f"dataset_key={(study_uid, series_uid, current_slice_index)}"

    def reset_projection_state(self) -> None:
        """
        Reset intensity projection state to defaults.
        
        Called when new series/file is opened, Reset View is selected, or file is closed.
        """
        self.projection_enabled = False
        self.projection_type = "aip"
        self.projection_slice_count = 4

    def clear_display_state(self) -> None:
        """
        Clear current display state (dataset, studies, UIDs, slice index).
        
        Called when closing files or opening new folder/files so that refresh_overlays
        and other code do not redisplay from stale cached state in non-focused windows.
        Also hides the no-pixel SR bottom bar; render paths only toggle it when a dataset
        is shown, so clears must reset it explicitly.
        """
        self.current_studies = {}
        self.current_study_uid = ""
        self.current_series_uid = ""
        self.current_slice_index = 0
        self.current_dataset = None
        self.reset_projection_state()
        self.image_viewer.set_no_pixel_placeholder_bar(False)

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
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
        window_center: float | None,
        window_width: float | None,
        use_rescaled_values: bool,
        rescale_slope: float | None,
        rescale_intercept: float | None
    ) -> Image.Image | None:
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
        return create_slice_projection_pil_image(
            self.dicom_processor,
            self.projection_type,
            self.projection_slice_count,
            current_studies,
            current_study_uid,
            current_series_uid,
            current_slice_index,
            window_center,
            window_width,
            use_rescaled_values,
            rescale_slope,
            rescale_intercept,
        )

    def _resolve_canonical_dataset_for_slice(
        self,
        dataset: Dataset,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
    ) -> Dataset:
        """Resolve stale dataset references to the canonical dataset for the active slice."""
        return _overlay_metadata_dataset_for_slice(
            dataset,
            current_studies,
            current_study_uid,
            current_series_uid,
            current_slice_index,
        )

    def _update_current_context(
        self,
        dataset: Dataset,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
    ) -> None:
        """Update manager context and mirror it to the view-state manager."""
        self.current_studies = current_studies
        self.current_study_uid = current_study_uid
        self.current_series_uid = current_series_uid
        self.current_slice_index = current_slice_index
        self.current_dataset = dataset
        self.view_state_manager.set_current_data_context(
            dataset, current_studies, current_study_uid, current_series_uid, current_slice_index
        )

    def _sync_view_state_rescale_context(
        self, dataset: Dataset
    ) -> tuple[float | None, float | None, str | None]:
        """Extract/infer rescale params and sync them into the view-state manager."""
        rescale_slope, rescale_intercept, rescale_type = self.dicom_processor.get_rescale_parameters(dataset)
        rescale_type = self.dicom_processor.infer_rescale_type(
            dataset, rescale_slope, rescale_intercept, rescale_type
        )
        self.view_state_manager.set_rescale_parameters(rescale_slope, rescale_intercept, rescale_type)
        return rescale_slope, rescale_intercept, rescale_type

    def rebuild_window_level_presets_for_current_series(self) -> None:
        """
        Rebuild merged W/L presets after user edits custom presets (Manage dialog).

        Preserves ``current_preset_index`` when the same name+source still exists.
        """
        dataset = self.current_dataset
        vsm = self.view_state_manager
        if dataset is None or vsm is None:
            return
        from core.wl_preset_catalog import build_preset_list, presets_to_legacy

        old_index = vsm.current_preset_index
        old_name: str | None = None
        old_source: str | None = None
        old_objects = getattr(vsm, "_wl_preset_objects", None)
        if old_objects and 0 <= old_index < len(old_objects):
            old_p = old_objects[old_index]
            old_name = old_p.name
            old_source = old_p.source

        rescale_slope, rescale_intercept, _ = self._sync_view_state_rescale_context(dataset)
        merged = build_preset_list(
            dataset,
            self.dicom_processor,
            self.config_manager,
            rescale_slope=rescale_slope,
            rescale_intercept=rescale_intercept,
        )
        vsm.window_level_presets = presets_to_legacy(merged)
        vsm._wl_preset_objects = merged  # type: ignore[attr-defined]

        new_index = 0
        if old_name is not None:
            for idx, preset in enumerate(merged):
                if preset.name == old_name and (
                    old_source is None or preset.source == old_source
                ):
                    new_index = idx
                    break
        vsm.current_preset_index = new_index

    def _compute_series_transition_state(
        self, dataset: Dataset, current_series_uid: str, current_slice_index: int
    ) -> tuple[str, bool, bool, str]:
        """Compute same-series and new-series transition flags. Body in ``slice_window_level_resolver``."""
        return _wl_compute_transition_state(self, dataset, current_series_uid, current_slice_index)

    def _resolve_window_level_for_series_transition(
        self,
        dataset: Dataset,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_series_uid: str,
        new_series_uid: str,
        is_same_series: bool,
        is_new_study_series: bool,
        series_identifier: str,
        rescale_slope: float | None,
        rescale_intercept: float | None,
    ) -> tuple[float | None, float | None, bool]:
        """Resolve window/level and rescale mode across series transitions. Body in ``slice_window_level_resolver``."""
        return _wl_resolve_transition(
            self, dataset, current_studies, current_series_uid, new_series_uid,
            is_same_series, is_new_study_series, series_identifier,
            rescale_slope, rescale_intercept,
        )

    def _try_build_projection_image(
        self,
        dataset: Dataset,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
        window_center: float | None,
        window_width: float | None,
        use_rescaled_values: bool,
        rescale_slope: float | None,
        rescale_intercept: float | None,
    ):
        """Return a projection PIL image when enabled, else None on skip/failure."""
        if not self.projection_enabled:
            return None
        try:
            return self._create_projection_image(
                dataset,
                current_studies,
                current_study_uid,
                current_series_uid,
                current_slice_index,
                window_center,
                window_width,
                use_rescaled_values,
                rescale_slope,
                rescale_intercept,
            )
        except Exception as e:
            error_type = type(e).__name__
            print_redacted(f"Error creating projection image ({error_type}): {e}")
            return None

    def _dataset_to_image_or_placeholder(
        self,
        dataset: Dataset,
        window_center: float | None,
        window_width: float | None,
        use_rescaled_values: bool,
    ) -> tuple[Image.Image, bool]:
        """Convert dataset to PIL image, or a no-pixel placeholder when conversion yields None."""
        if DEBUG_WL:
            print(
                f"[DEBUG-WL] dataset_to_image: window_center={window_center} window_width={window_width} "
                f"apply_rescale={use_rescaled_values}"
            )
        try:
            if window_center is not None and window_width is not None:
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    window_center=window_center,
                    window_width=window_width,
                    apply_rescale=use_rescaled_values,
                )
            else:
                image = self.dicom_processor.dataset_to_image(
                    dataset,
                    apply_rescale=use_rescaled_values,
                )
            if image is None:
                return _make_no_pixel_placeholder_pil(), True
            return image, False
        except (MemoryError, ValueError, AttributeError, RuntimeError) as e:
            error_type = type(e).__name__
            error_msg = f"Error converting dataset to image ({error_type}): {e!s}"
            raise RuntimeError(error_msg) from e
        except Exception as e:
            error_type = type(e).__name__
            error_msg = f"Unexpected error converting dataset to image ({error_type}): {e!s}"
            raise RuntimeError(error_msg) from e

    def _resolve_view_preserve_and_inversion(
        self,
        is_same_series: bool,
        is_new_study_series: bool,
        series_identifier: str,
        preserve_view_override: bool | None,
    ) -> tuple[bool, bool, bool | None]:
        """Return (preserve_view, force_fit_to_view, apply_inversion)."""
        apply_inversion = None
        preserve_view = is_same_series and not is_new_study_series
        force_fit_to_view = False
        if preserve_view_override is not None:
            preserve_view = preserve_view_override
            force_fit_to_view = not preserve_view_override
        if not preserve_view:
            if series_identifier and series_identifier in self.view_state_manager.series_defaults:
                apply_inversion = self.view_state_manager.get_series_inversion_state(series_identifier)
            self.view_state_manager.restore_orientation(series_identifier)
        return preserve_view, force_fit_to_view, apply_inversion

    def _maybe_apply_fusion(
        self,
        image: Image.Image | None,
        no_pixel_placeholder: bool,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
    ):
        """Blend fusion overlay into image when a fusion coordinator is active."""
        if (
            self.fusion_coordinator is None
            or image is None
            or no_pixel_placeholder
        ):
            return image
        try:
            base_datasets = current_studies.get(current_study_uid, {}).get(current_series_uid, [])
            if base_datasets:
                fused_image = self.fusion_coordinator.get_fused_image(
                    image,
                    base_datasets,
                    current_slice_index,
                )
                if fused_image is not None:
                    return fused_image
        except Exception as e:
            print_redacted(f"Error applying fusion: {e}")
        return image

    def _configure_no_pixel_sr_bar(self, dataset: Dataset, no_pixel_placeholder: bool) -> None:
        """Show or hide the SR no-pixel placeholder action bar on the viewer."""
        modality = getattr(dataset, "Modality", None) or ""
        show_sr_bar = bool(no_pixel_placeholder and modality == "SR")
        if show_sr_bar and self.open_structured_report_browser_callback is not None:
            _sr_cb = self.open_structured_report_browser_callback

            def _open_sr_browser_for_current() -> None:
                _sr_cb(dataset)

            self.image_viewer.set_no_pixel_placeholder_bar(
                True,
                open_callback=_open_sr_browser_for_current,
                show_open_button=True,
            )
        elif show_sr_bar:
            self.image_viewer.set_no_pixel_placeholder_bar(
                True,
                open_callback=None,
                show_open_button=False,
            )
        else:
            self.image_viewer.set_no_pixel_placeholder_bar(False)

    def _apply_image_to_viewer_and_fit(
        self,
        image,
        preserve_view: bool,
        apply_inversion: bool | None,
        is_new_study_series: bool,
        force_fit_to_view: bool,
        series_identifier: str,
    ) -> None:
        """Push image to the viewer and optionally fit / store initial zoom."""
        self.image_viewer.set_image(image, preserve_view=preserve_view, apply_inversion=apply_inversion)

        if is_new_study_series or force_fit_to_view:
            self.image_viewer.fit_to_view(center_image=True)
            if is_new_study_series:
                stored_zoom = self.image_viewer.current_zoom
                stored_h_scroll = self.image_viewer.horizontalScrollBar().value()
                stored_v_scroll = self.image_viewer.verticalScrollBar().value()
                self.view_state_manager.initial_fit_zoom = stored_zoom
                if series_identifier in self.view_state_manager.series_defaults:
                    self.view_state_manager.series_defaults[series_identifier].update(
                        {
                            "zoom": stored_zoom,
                            "h_scroll": stored_h_scroll,
                            "v_scroll": stored_v_scroll,
                            "initial_fit_zoom": stored_zoom,
                        }
                    )

    def _render_base_image_pipeline(
        self,
        dataset: Dataset,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
        window_center: float | None,
        window_width: float | None,
        use_rescaled_values: bool,
        rescale_slope: float | None,
        rescale_intercept: float | None,
        is_same_series: bool,
        is_new_study_series: bool,
        series_identifier: str,
        preserve_view_override: bool | None,
    ) -> None:
        """Projection, single-slice render, fusion, viewer image + fit (same order as prior display_slice)."""
        image = self._try_build_projection_image(
            dataset,
            current_studies,
            current_study_uid,
            current_series_uid,
            current_slice_index,
            window_center,
            window_width,
            use_rescaled_values,
            rescale_slope,
            rescale_intercept,
        )
        no_pixel_placeholder = False
        if image is None:
            image, no_pixel_placeholder = self._dataset_to_image_or_placeholder(
                dataset, window_center, window_width, use_rescaled_values
            )

        preserve_view, force_fit_to_view, apply_inversion = self._resolve_view_preserve_and_inversion(
            is_same_series, is_new_study_series, series_identifier, preserve_view_override
        )
        image = self._maybe_apply_fusion(
            image,
            no_pixel_placeholder,
            current_studies,
            current_study_uid,
            current_series_uid,
            current_slice_index,
        )
        self._configure_no_pixel_sr_bar(dataset, no_pixel_placeholder)
        self._apply_image_to_viewer_and_fit(
            image,
            preserve_view,
            apply_inversion,
            is_new_study_series,
            force_fit_to_view,
            series_identifier,
        )

    def _compute_pixel_wl_ranges(
        self, dataset: Dataset, use_rescaled_values: bool
    ) -> tuple[float | None, float | None, tuple[float, float] | None, tuple[float, float] | None]:
        """Return pixel_min, pixel_max, center_range, width_range for W/L controls."""
        pixel_min = None
        pixel_max = None
        center_range = None
        width_range = None
        try:
            pixel_min, pixel_max = self.dicom_processor.get_pixel_value_range(
                dataset, apply_rescale=use_rescaled_values
            )
            if pixel_min is not None and pixel_max is not None:
                series_pixel_min, series_pixel_max = self.view_state_manager.get_series_pixel_range()
                if series_pixel_min is not None and series_pixel_max is not None:
                    center_range = (series_pixel_min, series_pixel_max)
                    width_range = (1.0, max(1.0, series_pixel_max - series_pixel_min))
                else:
                    center_range = (pixel_min, pixel_max)
                    width_range = (1.0, max(1.0, pixel_max - pixel_min))
        except Exception as e:
            error_type = type(e).__name__
            print_redacted(f"Error calculating pixel value range for window/level controls ({error_type}): {e}")
        return pixel_min, pixel_max, center_range, width_range

    def _apply_wl_ranges_values_and_unit(
        self,
        update_controls: bool,
        is_new_study_series: bool,
        window_center: float | None,
        window_width: float | None,
        center_range: tuple[float, float] | None,
        width_range: tuple[float, float] | None,
        unit: str | None,
    ) -> None:
        """Push W/L ranges, optional new-series values, and unit to the controls widget."""
        if update_controls and center_range is not None and width_range is not None:
            self.window_level_controls.set_ranges(center_range, width_range)
        if update_controls and is_new_study_series and window_center is not None and window_width is not None:
            self.window_level_controls.set_window_level(
                window_center, window_width, block_signals=True, unit=unit
            )
        if update_controls:
            self.window_level_controls.set_unit(unit)

    def _clamp_stored_window_level_if_out_of_range(
        self,
        is_new_study_series: bool,
        window_center: float | None,
        window_width: float | None,
        pixel_min: float | None,
        pixel_max: float | None,
    ) -> tuple[float | None, float | None]:
        """Clamp stored W/L to the valid pixel/series range when continuing within a series."""
        if (
            is_new_study_series
            or window_center is None
            or window_width is None
            or pixel_min is None
            or pixel_max is None
        ):
            return window_center, window_width
        series_pixel_min, series_pixel_max = self.view_state_manager.get_series_pixel_range()
        if series_pixel_min is not None and series_pixel_max is not None:
            valid_min = series_pixel_min
            valid_max = series_pixel_max
        else:
            valid_min = pixel_min
            valid_max = pixel_max
        if (
            window_center < valid_min
            or window_center > valid_max
            or window_width < 1.0
            or window_width > (valid_max - valid_min)
        ):
            if valid_min is not None and valid_max is not None:
                window_center = (valid_min + valid_max) / 2.0
                window_width = valid_max - valid_min
                if window_width <= 0:
                    window_width = 1.0
                self.view_state_manager.current_window_center = window_center
                self.view_state_manager.current_window_width = window_width
        return window_center, window_width

    def _store_window_level(
        self,
        window_center: float,
        window_width: float,
        update_controls: bool,
        unit: str | None,
    ) -> None:
        """Persist W/L on view state and optionally push to the controls widget."""
        if update_controls:
            self.window_level_controls.set_window_level(
                window_center, window_width, block_signals=True, unit=unit
            )
        self.view_state_manager.current_window_center = window_center
        self.view_state_manager.current_window_width = window_width

    def _apply_fallback_window_level_from_dataset_or_defaults(
        self,
        dataset: Dataset,
        update_controls: bool,
        use_rescaled_values: bool,
        rescale_slope: float | None,
        rescale_intercept: float | None,
        pixel_min: float | None,
        pixel_max: float | None,
        unit: str | None,
    ) -> None:
        """Resolve W/L from the dataset tags, else from pixel min/max defaults."""
        wc, ww, is_rescaled = self.dicom_processor.get_window_level_from_dataset(
            dataset,
            rescale_slope=rescale_slope,
            rescale_intercept=rescale_intercept,
        )
        if wc is not None and ww is not None:
            wc, ww = apply_window_level_rescale_conversion(
                wc,
                ww,
                is_rescaled=is_rescaled,
                use_rescaled_values=use_rescaled_values,
                rescale_slope=rescale_slope,
                rescale_intercept=rescale_intercept,
                dicom_processor=self.dicom_processor,
            )
            self._store_window_level(wc, ww, update_controls, unit)
        elif pixel_min is not None and pixel_max is not None:
            default_center = (pixel_min + pixel_max) / 2.0
            default_width = pixel_max - pixel_min
            if default_width <= 0:
                default_width = 1.0
            self._store_window_level(default_center, default_width, update_controls, unit)
        self.view_state_manager.window_level_user_modified = False

    def _sync_wl_for_continuing_or_fallback_series(
        self,
        dataset: Dataset,
        update_controls: bool,
        use_rescaled_values: bool,
        is_new_study_series: bool,
        is_same_series: bool,
        window_center: float | None,
        window_width: float | None,
        rescale_slope: float | None,
        rescale_intercept: float | None,
        pixel_min: float | None,
        pixel_max: float | None,
        unit: str | None,
    ) -> None:
        """Update W/L for same-series continue, or resolve fallback W/L from dataset/defaults."""
        if is_new_study_series and window_center is not None and window_width is not None:
            return
        if is_same_series and window_center is not None and window_width is not None:
            if update_controls:
                self.window_level_controls.set_window_level(
                    window_center, window_width, block_signals=True, unit=unit
                )
            return
        if not is_same_series or window_center is None or window_width is None:
            self._apply_fallback_window_level_from_dataset_or_defaults(
                dataset,
                update_controls,
                use_rescaled_values,
                rescale_slope,
                rescale_intercept,
                pixel_min,
                pixel_max,
                unit,
            )

    def _sync_controls_and_metadata(
        self,
        dataset: Dataset,
        update_metadata: bool,
        update_controls: bool,
        use_rescaled_values: bool,
        is_new_study_series: bool,
        is_same_series: bool,
        window_center: float | None,
        window_width: float | None,
        rescale_type: str | None,
        rescale_slope: float | None,
        rescale_intercept: float | None,
    ) -> None:
        """Apply metadata and W/L control synchronization after image rendering."""
        if update_metadata:
            self.metadata_panel.set_dataset(dataset)

        if self.update_tag_viewer_callback:
            self.update_tag_viewer_callback(dataset)

        pixel_min, pixel_max, center_range, width_range = self._compute_pixel_wl_ranges(
            dataset, use_rescaled_values
        )
        unit = rescale_type if (use_rescaled_values and rescale_type) else None
        self._apply_wl_ranges_values_and_unit(
            update_controls,
            is_new_study_series,
            window_center,
            window_width,
            center_range,
            width_range,
            unit,
        )
        window_center, window_width = self._clamp_stored_window_level_if_out_of_range(
            is_new_study_series, window_center, window_width, pixel_min, pixel_max
        )
        self._sync_wl_for_continuing_or_fallback_series(
            dataset,
            update_controls,
            use_rescaled_values,
            is_new_study_series,
            is_same_series,
            window_center,
            window_width,
            rescale_slope,
            rescale_intercept,
            pixel_min,
            pixel_max,
            unit,
        )

    def _resolve_total_slices(
        self,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
    ) -> int:
        """Count slices in the active series, or 0 when context is incomplete."""
        if current_studies and current_study_uid and current_series_uid:
            if (
                current_study_uid in current_studies
                and current_series_uid in current_studies[current_study_uid]
            ):
                return len(current_studies[current_study_uid][current_series_uid])
        return 0

    def _sum_slice_thickness_over_range(
        self,
        series_datasets: list[Dataset],
        start_index: int,
        end_index: int,
    ) -> float | None:
        """Sum SliceThickness over inclusive indices; return None when no values found."""
        total_thickness = 0.0
        thickness_count = 0
        for i in range(start_index, end_index + 1):
            if 0 <= i < len(series_datasets):
                thickness = get_slice_thickness(series_datasets[i])
                if thickness is not None:
                    total_thickness += thickness
                    thickness_count += 1
        if thickness_count > 0:
            return total_thickness
        return None

    def _projection_overlay_thickness_meta(
        self,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
        total_slices: int,
    ) -> tuple[int | None, int | None, float | None]:
        """Return projection start/end indices and summed slice thickness for overlays."""
        if not (self.projection_enabled and total_slices > 0):
            return None, None, None
        projection_start_slice = max(0, current_slice_index)
        projection_end_slice = min(
            total_slices - 1, current_slice_index + self.projection_slice_count - 1
        )
        projection_total_thickness = None
        if (
            current_study_uid in current_studies
            and current_series_uid in current_studies[current_study_uid]
        ):
            projection_total_thickness = self._sum_slice_thickness_over_range(
                current_studies[current_study_uid][current_series_uid],
                projection_start_slice,
                projection_end_slice,
            )
        return projection_start_slice, projection_end_slice, projection_total_thickness

    def _bind_tools_to_current_slice(
        self, dataset: Dataset, current_slice_index: int
    ) -> tuple[str, str, int]:
        """Set current-slice context on ROI/measurement/annotation tools."""
        study_uid = getattr(dataset, "StudyInstanceUID", "")
        series_uid = get_composite_series_key(dataset)
        instance_identifier = current_slice_index
        self.roi_manager.set_current_slice(study_uid, series_uid, instance_identifier)
        self.measurement_tool.set_current_slice(study_uid, series_uid, instance_identifier)
        if self.text_annotation_tool:
            self.text_annotation_tool.set_current_slice(study_uid, series_uid, instance_identifier)
        if self.arrow_annotation_tool:
            self.arrow_annotation_tool.set_current_slice(study_uid, series_uid, instance_identifier)
        return study_uid, series_uid, instance_identifier

    def _clear_tools_on_new_series(
        self,
        is_new_study_series: bool,
        study_uid: str,
        series_uid: str,
        instance_identifier: int,
    ) -> None:
        """Clear measurement/annotation scene items when entering a new study/series."""
        if is_new_study_series:
            if DEBUG_MEASUREMENT_SERIES:
                print(
                    "[DEBUG-MEAS-SERIES] display_slice new series: clearing measurement/annotation scene items. "
                    f"scene_id={id(self.image_viewer.scene)}, measurement_summary_before_clear="
                    f"{self.measurement_tool.get_debug_summary(self.image_viewer.scene)}"
                )
            self.measurement_tool.clear_measurements_from_other_slices(
                study_uid,
                series_uid,
                instance_identifier,
                self.image_viewer.scene,
            )
            if self.text_annotation_tool:
                self.text_annotation_tool.clear_annotations(self.image_viewer.scene)
            if self.arrow_annotation_tool:
                self.arrow_annotation_tool.clear_arrows(self.image_viewer.scene)
        elif DEBUG_MEASUREMENT_SERIES:
            print(
                "[DEBUG-MEAS-SERIES] display_slice same series path: skipping clear_measurements. "
                f"measurement_summary={self.measurement_tool.get_debug_summary(self.image_viewer.scene)}"
            )

    def _invoke_slice_annotation_displays(self, dataset: Dataset) -> None:
        """Display ROIs, measurements, and text/arrow annotations for the active slice."""
        if self.display_rois_callback:
            self.display_rois_callback(dataset)
        else:
            self.display_rois_for_slice(dataset)

        if self.display_measurements_callback:
            self.display_measurements_callback(dataset)
        else:
            self.display_measurements_for_slice(dataset)

        if self.text_annotation_tool:
            self.display_text_annotations_for_slice(dataset)
        if self.arrow_annotation_tool:
            self.display_arrow_annotations_for_slice(dataset)

    def _render_presentation_state_items(
        self, dataset: Dataset, current_study_uid: str
    ) -> None:
        """Clear and recreate presentation-state annotation items when available."""
        if not (self.annotation_manager and self.dicom_organizer):
            return
        try:
            self.annotation_manager.clear_annotations(self.image_viewer.scene)
            annotations = self.annotation_manager.get_annotations_for_image(dataset, current_study_uid)
            if annotations:
                image_width = 512.0
                image_height = 512.0
                if hasattr(dataset, "Columns") and hasattr(dataset, "Rows"):
                    image_width = float(dataset.Columns)
                    image_height = float(dataset.Rows)
                self.annotation_manager.create_presentation_state_items(
                    self.image_viewer.scene,
                    annotations,
                    image_width,
                    image_height,
                )
        except Exception:
            pass

    def _render_scene_overlays_annotations(
        self,
        dataset: Dataset,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
        is_new_study_series: bool,
    ) -> None:
        """Render overlay, ROI/measurement, and annotation scene items for the active slice."""
        parser = DICOMParser(dataset)
        total_slices = self._resolve_total_slices(
            current_studies, current_study_uid, current_series_uid
        )
        projection_start_slice, projection_end_slice, projection_total_thickness = (
            self._projection_overlay_thickness_meta(
                current_studies,
                current_study_uid,
                current_series_uid,
                current_slice_index,
                total_slices,
            )
        )

        self.overlay_manager.create_overlay_items(
            self.image_viewer.scene,
            parser,
            total_slices=total_slices if total_slices > 0 else None,
            projection_enabled=self.projection_enabled,
            projection_start_slice=projection_start_slice,
            projection_end_slice=projection_end_slice,
            projection_total_thickness=projection_total_thickness,
            projection_type=self.projection_type if self.projection_enabled else None,
            multiframe_context=self.get_multiframe_overlay_context(
                dataset=dataset,
                study_uid=current_study_uid,
                series_uid=current_series_uid,
            ),
            stack_position=(current_slice_index + 1) if total_slices > 0 else None,
        )

        pixel_spacing = get_pixel_spacing(dataset)
        self.measurement_tool.set_pixel_spacing(pixel_spacing)

        study_uid, series_uid, instance_identifier = self._bind_tools_to_current_slice(
            dataset, current_slice_index
        )
        self._clear_tools_on_new_series(
            is_new_study_series, study_uid, series_uid, instance_identifier
        )
        self._invoke_slice_annotation_displays(dataset)
        self._render_presentation_state_items(dataset, current_study_uid)

    def display_slice(  # pyright: ignore[reportGeneralTypeIssues]
        self,
        dataset: Dataset,
        current_studies: dict[str, dict[str, list[Dataset]]],
        current_study_uid: str,
        current_series_uid: str,
        current_slice_index: int,
        preserve_view_override: bool | None = None,
        update_controls: bool = True,
        update_metadata: bool = True
    ) -> None:
        # DEBUG: Log when display_slice is called
        # print(f"[WL UNIT DEBUG] display_slice called")
        # print(f"[WL UNIT DEBUG]   current_slice_index: {current_slice_index}")
        # if self.view_state_manager:
        #     print(f"[WL UNIT DEBUG]   view_state_manager.rescale_type (before): {self.view_state_manager.rescale_type}")
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
            with perf_timer("first_paint.slice.resolve_dataset"):
                dataset = self._resolve_canonical_dataset_for_slice(
                    dataset,
                    current_studies,
                    current_study_uid,
                    current_series_uid,
                    current_slice_index,
                )
            with perf_timer("first_paint.slice.context_and_rescale"):
                self._update_current_context(
                    dataset,
                    current_studies,
                    current_study_uid,
                    current_series_uid,
                    current_slice_index,
                )
                rescale_slope, rescale_intercept, rescale_type = self._sync_view_state_rescale_context(dataset)
                new_series_uid, is_same_series, is_new_study_series, series_identifier = (
                    self._compute_series_transition_state(dataset, current_series_uid, current_slice_index)
                )

            # Check for JPEGLS transfer syntax and show warning only for new series
            if is_new_study_series:
                jpegls_syntaxes = [
                    '1.2.840.10008.1.2.4.80',  # JPEG-LS Lossless
                    '1.2.840.10008.1.2.4.81',  # JPEG-LS Lossy
                ]
                if hasattr(dataset, 'file_meta') and hasattr(dataset.file_meta, 'TransferSyntaxUID'):
                    transfer_syntax = str(dataset.file_meta.TransferSyntaxUID)
                    if transfer_syntax in jpegls_syntaxes:
                        QMessageBox.warning(
                            self.image_viewer,
                            "JPEG-LS Image Warning",
                            "JPEG-LS transfer syntax detected.\n\n"
                            "Pixel values may not be correct, especially for color images.\n"
                            "This is a known issue with JPEG-LS compression."
                        )

            # DEBUG: Track series detection
            getattr(dataset, 'Modality', 'Unknown')
            # print(f"[DEBUG-WL] display_slice: modality={modality}, is_new_study_series={is_new_study_series}, series_id={series_identifier[:20]}...")

            with perf_timer("first_paint.slice.window_level_resolution"):
                window_center, window_width, use_rescaled_values = self._resolve_window_level_for_series_transition(
                    dataset=dataset,
                    current_studies=current_studies,
                    current_series_uid=current_series_uid,
                    new_series_uid=new_series_uid,
                    is_same_series=is_same_series,
                    is_new_study_series=is_new_study_series,
                    series_identifier=series_identifier,
                    rescale_slope=rescale_slope,
                    rescale_intercept=rescale_intercept,
                )

            with perf_timer("first_paint.slice.render_base_image_pipeline"):
                self._render_base_image_pipeline(
                    dataset=dataset,
                    current_studies=current_studies,
                    current_study_uid=current_study_uid,
                    current_series_uid=current_series_uid,
                    current_slice_index=current_slice_index,
                    window_center=window_center,
                    window_width=window_width,
                    use_rescaled_values=use_rescaled_values,
                    rescale_slope=rescale_slope,
                    rescale_intercept=rescale_intercept,
                    is_same_series=is_same_series,
                    is_new_study_series=is_new_study_series,
                    series_identifier=series_identifier,
                    preserve_view_override=preserve_view_override,
                )

            with perf_timer("first_paint.slice.controls_and_metadata"):
                self._sync_controls_and_metadata(
                    dataset=dataset,
                    update_metadata=update_metadata,
                    update_controls=update_controls,
                    use_rescaled_values=use_rescaled_values,
                    is_new_study_series=is_new_study_series,
                    is_same_series=is_same_series,
                    window_center=window_center,
                    window_width=window_width,
                    rescale_type=rescale_type,
                    rescale_slope=rescale_slope,
                    rescale_intercept=rescale_intercept,
                )
            with perf_timer("first_paint.slice.overlays_annotations"):
                self._render_scene_overlays_annotations(
                    dataset=dataset,
                    current_studies=current_studies,
                    current_study_uid=current_study_uid,
                    current_series_uid=current_series_uid,
                    current_slice_index=current_slice_index,
                    is_new_study_series=is_new_study_series,
                )

        except MemoryError as e:
            # Re-raise MemoryError with context for caller to handle
            error_msg = f"Memory error displaying slice: {e!s}"
            # print(error_msg)
            raise MemoryError(error_msg) from e
        except Exception as e:
            # Re-raise with context for caller to handle
            error_type = type(e).__name__
            error_msg = f"Error displaying slice: {e!s}"
            if error_type not in error_msg:
                error_msg = f"{error_type}: {error_msg}"
            # print(error_msg)
            raise

    def _roi_belongs_to_slice(
        self, roi, study_uid: str, series_uid: str, instance_identifier: int
    ) -> bool:
        """Return True when the ROI is stored under the current slice composite key."""
        slice_key = (study_uid, series_uid, instance_identifier)
        for key, roi_list in self.roi_manager.rois.items():
            if roi in roi_list:
                return key == slice_key
        return False

    def _remove_roi_graphics_from_scene(self, roi, item) -> None:
        """Remove an ROI's statistics overlay and graphics item from the viewer scene."""
        if roi.statistics_overlay_item is not None:
            if roi.statistics_overlay_item.scene() == self.image_viewer.scene:
                self.image_viewer.scene.removeItem(roi.statistics_overlay_item)
            roi.statistics_overlay_item = None
        if item.scene() == self.image_viewer.scene:
            self.image_viewer.scene.removeItem(item)

    def _remove_rois_not_on_current_slice(
        self, study_uid: str, series_uid: str, instance_identifier: int
    ) -> None:
        """Remove ROI graphics (and stats overlays) that belong to other slices."""
        for item in list(self.image_viewer.scene.items()):
            roi = self.roi_manager.find_roi_by_item(item)
            if roi is None:
                continue
            if self._roi_belongs_to_slice(roi, study_uid, series_uid, instance_identifier):
                continue
            self._remove_roi_graphics_from_scene(roi, item)

    def _ensure_current_rois_in_scene(self, rois) -> None:
        """Add current-slice ROIs to the scene and ensure they are visible."""
        for roi in rois:
            roi_scene = roi.item.scene() if roi.item else None
            if roi_scene == self.image_viewer.scene:
                roi.item.setZValue(100)
                roi.item.show()
            else:
                self.image_viewer.scene.addItem(roi.item)
                roi.item.setZValue(100)

    def _sync_roi_list_selection_and_stats(self, rois, study_uid: str, series_uid: str, instance_identifier: int) -> None:
        """Refresh ROI list, overlays, and selection/statistics for the current slice."""
        if self.roi_list_panel is not None:
            self.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)

        if self.update_roi_statistics_overlays_callback is not None:
            self.update_roi_statistics_overlays_callback()

        selected_roi = self.roi_manager.get_selected_roi()
        if selected_roi is not None and selected_roi in rois:
            if self.roi_list_panel is not None:
                self.roi_list_panel.select_roi_in_list(selected_roi)
        else:
            if selected_roi is not None:
                self.roi_manager.select_roi(None)
            if self.roi_list_panel is not None:
                self.roi_list_panel.select_roi_in_list(None)
            if self.roi_statistics_panel is not None:
                self.roi_statistics_panel.clear_statistics()

    def display_rois_for_slice(self, dataset: Dataset) -> None:
        """
        Display ROIs for a slice.
        
        Ensures all ROIs for the current slice are visible in the scene.
        
        Args:
            dataset: pydicom Dataset for the current slice
        """
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = get_composite_series_key(dataset)
        instance_identifier = self.current_slice_index

        rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
        self._remove_rois_not_on_current_slice(study_uid, series_uid, instance_identifier)
        self._ensure_current_rois_in_scene(rois)
        self._sync_roi_list_selection_and_stats(rois, study_uid, series_uid, instance_identifier)

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
        if DEBUG_MEASUREMENT_SERIES:
            print_redacted(
                "[DEBUG-MEAS-SERIES] display_measurements_for_slice: "
                f"key={(study_uid, series_uid, instance_identifier)}, "
                f"measurement_summary_before={self.measurement_tool.get_debug_summary(self.image_viewer.scene)}"
            )

        # Clear measurements from other slices first
        self.measurement_tool.clear_measurements_from_other_slices(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )

        # Display measurements for this slice
        self.measurement_tool.display_measurements_for_slice(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )
        if DEBUG_MEASUREMENT_SERIES:
            print_redacted(
                "[DEBUG-MEAS-SERIES] display_measurements_for_slice complete: "
                f"key={(study_uid, series_uid, instance_identifier)}, "
                f"measurement_summary_after={self.measurement_tool.get_debug_summary(self.image_viewer.scene)}"
            )

    def display_text_annotations_for_slice(self, dataset: Dataset) -> None:
        """
        Display text annotations for a slice.
        
        Ensures all text annotations for the current slice are visible in the scene.
        Removes text annotations from other slices before displaying current slice annotations.
        
        Args:
            dataset: pydicom Dataset for the current slice
        """
        if not self.text_annotation_tool:
            return

        # Extract DICOM identifiers
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = get_composite_series_key(dataset)
        # Use current_slice_index as instance identifier (array position)
        instance_identifier = self.current_slice_index

        # Clear annotations from other slices first
        self.text_annotation_tool.clear_annotations_from_other_slices(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )

        # Display annotations for this slice
        self.text_annotation_tool.display_annotations_for_slice(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )

    def display_arrow_annotations_for_slice(self, dataset: Dataset) -> None:
        """
        Display arrow annotations for a slice.
        
        Ensures all arrow annotations for the current slice are visible in the scene.
        Removes arrow annotations from other slices before displaying current slice annotations.
        
        Args:
            dataset: pydicom Dataset for the current slice
        """
        if not self.arrow_annotation_tool:
            return

        # Extract DICOM identifiers
        study_uid = getattr(dataset, 'StudyInstanceUID', '')
        series_uid = get_composite_series_key(dataset)
        # Use current_slice_index as instance identifier (array position)
        instance_identifier = self.current_slice_index

        # Clear arrows from other slices first
        self.arrow_annotation_tool.clear_arrows_from_other_slices(
            study_uid, series_uid, instance_identifier, self.image_viewer.scene
        )

        # Display arrows for this slice
        self.arrow_annotation_tool.display_arrows_for_slice(
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

    def _build_sorted_series_list(
        self, study_series: dict[str, list[Dataset]]
    ) -> list[tuple[int, str, list[Dataset]]]:
        """Build (SeriesNumber, series_uid, datasets) rows sorted by SeriesNumber ascending."""
        series_list: list[tuple[int, str, list[Dataset]]] = []
        for series_uid, datasets in study_series.items():
            if datasets:
                first_dataset = datasets[0]
                series_number = getattr(first_dataset, 'SeriesNumber', None)
                try:
                    series_num = int(series_number) if series_number is not None else 0
                except (ValueError, TypeError):
                    series_num = 0
                series_list.append((series_num, series_uid, datasets))
        series_list.sort(key=lambda x: x[0])
        return series_list

    def _index_of_series_uid(
        self, series_list: list[tuple[int, str, list[Dataset]]], series_uid: str
    ) -> int | None:
        """Return the index of series_uid in the sorted series list, or None."""
        for idx, (_, uid, _) in enumerate(series_list):
            if uid == series_uid:
                return idx
        return None

    def _series_nav_debug(self, message: str, *, redacted: bool = False) -> None:
        """Emit a series-navigation debug line when DEBUG_SERIES is enabled."""
        if not DEBUG_SERIES:
            return
        if redacted:
            print_redacted(message)
        else:
            print(message)

    def _resolve_adjacent_series(
        self, direction: int
    ) -> tuple[str | None, int | None, Dataset | None]:
        """Resolve the adjacent series by SeriesNumber order, or None when navigation is impossible."""
        if not self.current_studies or not self.current_study_uid:
            print_redacted(
                f"[DEBUG] handle_series_navigation: No studies or study_uid. "
                f"studies={bool(self.current_studies)}, "
                f"study_uid={self.current_study_uid[:20] if self.current_study_uid else 'None'}..."
            )
            return None, None, None

        study_series = self.current_studies[self.current_study_uid]
        if len(study_series) <= 1:
            self._series_nav_debug(
                f"[DEBUG] handle_series_navigation: Only {len(study_series)} series in study, cannot navigate"
            )
            return None, None, None

        series_list = self._build_sorted_series_list(study_series)
        self._series_nav_debug(
            f"[DEBUG] handle_series_navigation: Found {len(series_list)} series in study. "
            f"Looking for current_series_uid="
            f"{self.current_series_uid[:20] if self.current_series_uid else 'None'}...",
            redacted=True,
        )

        current_index = self._index_of_series_uid(series_list, self.current_series_uid)
        if current_index is None:
            self._series_nav_debug(
                f"[DEBUG] handle_series_navigation: Current series not found in sorted list. "
                f"Available series UIDs: {[uid[:20] + '...' for _, uid, _ in series_list[:3]]} "
                f"(showing first 3)",
                redacted=True,
            )
            return None, None, None

        self._series_nav_debug(
            f"[DEBUG] handle_series_navigation: Current series found at index "
            f"{current_index} of {len(series_list)}"
        )
        new_index = current_index + direction
        if new_index < 0 or new_index >= len(series_list):
            self._series_nav_debug(
                f"[DEBUG] handle_series_navigation: New index {new_index} out of range "
                f"[0, {len(series_list)})"
            )
            return None, None, None

        _, new_series_uid, datasets = series_list[new_index]
        if not datasets:
            self._series_nav_debug(
                f"[DEBUG] handle_series_navigation: New series "
                f"{new_series_uid[:20] if new_series_uid else 'None'}... has no datasets",
                redacted=True,
            )
            return None, None, None

        self._series_nav_debug(
            f"[DEBUG] handle_series_navigation: Successfully navigating from index "
            f"{current_index} to {new_index}, new_series_uid={new_series_uid[:20]}...",
            redacted=True,
        )
        return new_series_uid, 0, datasets[0]

    def handle_series_navigation(self, direction: int) -> tuple[str | None, int | None, Dataset | None]:
        """
        Handle series navigation request.
        
        Args:
            direction: -1 for left/previous series, 1 for right/next series
            
        Returns:
            Tuple of (new_series_uid, slice_index, dataset) or (None, None, None) if navigation not possible
        """
        return self._resolve_adjacent_series(direction)

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
        current_studies: dict[str, dict[str, list[Dataset]]],
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
