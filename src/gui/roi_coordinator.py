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
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Optional

import numpy as np
from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF, QRectF, QTimer

from gui.roi_list_panel import ROIListPanel
from gui.roi_statistics_panel import ROIStatisticsPanel
from tools.roi_manager import ROIItem, ROIManager
from utils.privacy.console import print_redacted

if TYPE_CHECKING:
    from gui.crosshair_coordinator import CrosshairCoordinator
    from utils.undo_redo import UndoRedoManager
import logging

from core.dicom_processor import DICOMProcessor
from gui.image_viewer import ImageViewer
from gui.main_window import MainWindow
from gui.window_level_controls import WindowLevelControls
from utils.dicom_utils import get_composite_series_key, get_pixel_spacing
from utils.log_sanitizer import sanitized_format_exc

_logger = logging.getLogger(__name__)


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
        get_current_dataset: Callable[[], Dataset | None],
        get_current_slice_index: Callable[[], int],
        get_rescale_params: Callable[[], tuple[float | None, float | None, str | None, bool]],
        set_mouse_mode_callback: Callable[[str], None] | None = None,
        get_projection_enabled: Callable[[], bool] | None = None,
        get_projection_type: Callable[[], str] | None = None,
        get_projection_slice_count: Callable[[], int] | None = None,
        get_current_studies: Callable[[], dict[str, Any]] | None = None,
        get_mpr_pixel_array: Callable[[], np.ndarray | None] | None = None,
        get_mpr_output_pixel_spacing: Callable[[], tuple[float, float] | None] | None = None,
        undo_redo_manager: Optional['UndoRedoManager'] = None,
        update_undo_redo_state_callback: Callable[[], None] | None = None,
        crosshair_coordinator: Optional['CrosshairCoordinator'] = None
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
        self.get_mpr_pixel_array = get_mpr_pixel_array
        self.get_mpr_output_pixel_spacing = get_mpr_output_pixel_spacing
        self.undo_redo_manager = undo_redo_manager
        self.update_undo_redo_state_callback = update_undo_redo_state_callback
        self.crosshair_coordinator = crosshair_coordinator

        # ROI move tracking with batching
        self._roi_move_tracking: dict[object, dict[str, Any]] = {}  # Tracks ongoing moves
        self._move_batch_timer: QTimer | None = None  # Timer for debouncing

    def _is_mpr_view(self) -> bool:
        """Return True when the active ImageViewer for this coordinator is in MPR mode."""
        cb = getattr(self.image_viewer, "is_mpr_view_callback", None)
        if cb is None:
            return False
        try:
            return bool(cb())
        except Exception:
            return False

    def _resolve_projection_enabled(self) -> bool:
        """Return whether intensity projection is enabled for ROI statistics."""
        if self.get_projection_enabled is None:
            return False
        try:
            return bool(self.get_projection_enabled())
        except Exception:
            _logger.debug("%s", sanitized_format_exc())
            return False

    def _projection_type_and_slice_count(self) -> tuple[str, int]:
        """Return (projection_type, slice_count) with the same defaults as before."""
        projection_type = "aip"
        if self.get_projection_type is not None:
            try:
                projection_type = self.get_projection_type()
            except Exception:
                pass
        projection_slice_count = 4
        if self.get_projection_slice_count is not None:
            try:
                projection_slice_count = self.get_projection_slice_count()
            except Exception:
                pass
        return projection_type, projection_slice_count

    def _gather_projection_slices(
        self,
        current_dataset: Dataset,
        projection_slice_count: int,
    ) -> list[Any] | None:
        """
        Gather consecutive series slices for projection, or None to fall back.

        Returns None when studies/series are missing or fewer than two slices
        can be gathered — callers then use the original slice pixel array.
        """
        if self.get_current_studies is None:
            return None
        current_studies = self.get_current_studies()
        if not current_studies:
            return None
        study_uid = getattr(current_dataset, "StudyInstanceUID", "")
        series_uid = get_composite_series_key(current_dataset)
        current_slice_index = self.get_current_slice_index()
        if (
            not study_uid
            or not series_uid
            or study_uid not in current_studies
            or series_uid not in current_studies[study_uid]
        ):
            return None
        series_datasets = current_studies[study_uid][series_uid]
        total_slices = len(series_datasets)
        if total_slices < 2:
            return None
        start_slice = max(0, current_slice_index)
        end_slice = min(total_slices - 1, current_slice_index + projection_slice_count - 1)
        if end_slice - start_slice + 1 < 2:
            return None
        projection_slices = [
            series_datasets[i]
            for i in range(start_slice, end_slice + 1)
            if 0 <= i < total_slices
        ]
        if len(projection_slices) < 2:
            return None
        return projection_slices

    def _compute_projection_array(
        self,
        projection_type: str,
        projection_slices: list[Any],
    ) -> np.ndarray | None:
        """Run AIP/MIP/MinIP for the gathered slices."""
        if projection_type == "aip":
            return self.dicom_processor.average_intensity_projection(projection_slices)
        if projection_type == "mip":
            return self.dicom_processor.maximum_intensity_projection(projection_slices)
        if projection_type == "minip":
            return self.dicom_processor.minimum_intensity_projection(projection_slices)
        return None

    def _build_projection_array_for_statistics(
        self,
        current_dataset: Dataset,
    ) -> np.ndarray | None:
        """
        Build a projection pixel array for statistics, or fall back to original.

        On any failure path returns ``dicom_processor.get_pixel_array(current_dataset)``.
        """
        try:
            projection_type, projection_slice_count = self._projection_type_and_slice_count()
            projection_slices = self._gather_projection_slices(
                current_dataset, projection_slice_count
            )
            if projection_slices is None:
                return self.dicom_processor.get_pixel_array(current_dataset)
            projection_array = self._compute_projection_array(
                projection_type, projection_slices
            )
            if projection_array is None:
                return self.dicom_processor.get_pixel_array(current_dataset)
            return projection_array
        except Exception:
            _logger.debug("%s", sanitized_format_exc())
            return self.dicom_processor.get_pixel_array(current_dataset)

    def _get_pixel_array_for_statistics(self) -> np.ndarray | None:
        """
        Get pixel array for ROI statistics calculation.

        If projection is enabled, returns the projection array.
        Otherwise, returns the original slice's pixel array.

        Returns:
            NumPy array (projection or original), or None if unavailable
        """
        # In MPR mode, use the MprBuilder-produced pixel arrays directly.
        if self._is_mpr_view() and self.get_mpr_pixel_array is not None:
            try:
                arr = self.get_mpr_pixel_array()
                if arr is not None:
                    return arr
            except Exception:
                return None

        current_dataset = self.get_current_dataset()
        if current_dataset is None:
            return None

        if not self._resolve_projection_enabled():
            return self.dicom_processor.get_pixel_array(current_dataset)

        return self._build_projection_array_for_statistics(current_dataset)

    def _roi_belongs_to_manager(self, roi: ROIItem) -> bool:
        """Return True when ``roi`` is registered in this coordinator's ROIManager."""
        return any(roi in roi_list for roi_list in self.roi_manager.rois.values())

    def _stats_spacing_and_rescale_params(
        self,
        current_dataset: Dataset,
    ) -> tuple[
        tuple[float, float] | None,
        float | None,
        float | None,
        str | None,
    ]:
        """
        Shared spacing + rescale arguments for ``calculate_statistics``.

        MPR pixel arrays are already in display space, so slope/intercept are
        forced to None (never re-apply rescale).
        """
        if self._is_mpr_view() and self.get_mpr_output_pixel_spacing is not None:
            pixel_spacing = self.get_mpr_output_pixel_spacing()
        else:
            pixel_spacing = get_pixel_spacing(current_dataset)
        rescale_slope, rescale_intercept, rescale_type, use_rescaled = self.get_rescale_params()
        display_rescale_type = rescale_type if use_rescaled else None
        if self._is_mpr_view():
            return pixel_spacing, None, None, display_rescale_type
        stats_slope = rescale_slope if use_rescaled else None
        stats_intercept = rescale_intercept if use_rescaled else None
        return pixel_spacing, stats_slope, stats_intercept, display_rescale_type

    def _roi_identifier_for_slice(
        self,
        roi: ROIItem,
        study_uid: str,
        series_uid: str,
        instance_identifier: int,
    ) -> str | None:
        """Return display label like ``ROI 1 (rectangle)`` for the ROI on this slice."""
        rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
        for i, registered in enumerate(rois):
            if registered == roi:
                return f"ROI {i + 1} ({roi.shape_type})"
        return None

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
        series_uid = get_composite_series_key(current_dataset)
        # Use current slice index as instance identifier (array position)
        instance_identifier = self.get_current_slice_index()

        self.roi_manager.set_current_slice(study_uid, series_uid, instance_identifier)
        shape_type = self.image_viewer.roi_drawing_mode or "rectangle"
        self.roi_manager.start_drawing(pos, shape_type)

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
        current_dataset, study_uid, series_uid, instance_identifier = (
            self._drawing_finish_slice_context()
        )

        if self.image_viewer.mouse_mode == "auto_window_level" and roi_item is not None:
            self._drawing_finish_auto_window_level(
                roi_item,
                current_dataset,
                study_uid,
                series_uid,
                instance_identifier,
            )
            return

        self._drawing_finish_normal_add(
            roi_item, current_dataset, study_uid, series_uid, instance_identifier
        )

    def _drawing_finish_slice_context(
        self,
    ) -> tuple[Any, str, str, int]:
        """Resolve current dataset and slice identifiers for a drawing finish."""
        current_dataset = self.get_current_dataset()
        study_uid = ""
        series_uid = ""
        instance_identifier = self.get_current_slice_index()
        if current_dataset is not None:
            study_uid = getattr(current_dataset, "StudyInstanceUID", "")
            series_uid = get_composite_series_key(current_dataset)
        return current_dataset, study_uid, series_uid, instance_identifier

    def _drawing_finish_restore_pan_mode(self) -> None:
        """Return mouse mode to pan after an auto-W/L ROI gesture."""
        if self.set_mouse_mode_callback:
            self.set_mouse_mode_callback("pan")
            return
        self.image_viewer.set_mouse_mode("pan")
        pa = self.main_window.mouse_mode_pan_action
        aw = self.main_window.mouse_mode_auto_window_level_action
        if pa is not None:
            pa.setChecked(True)
        if aw is not None:
            aw.setChecked(False)

    def _drawing_finish_discard_auto_wl_roi(
        self,
        roi_item,
        study_uid: str,
        series_uid: str,
        instance_identifier: int,
    ) -> None:
        """Delete a temporary auto-W/L ROI and refresh list/stats panels."""
        self.roi_manager.delete_roi(roi_item, self.image_viewer.scene)
        self.roi_statistics_panel.clear_statistics()
        self.roi_list_panel.update_roi_list(
            study_uid, series_uid, instance_identifier, self.roi_manager
        )

    def _drawing_finish_compute_auto_wl(
        self, roi, current_dataset
    ) -> tuple[float, float] | None:
        """
        Compute window center/width from an auto-W/L ROI.

        Returns:
            ``(center, width)`` or ``None`` when stats cannot be computed.
        """
        pixel_array = self._get_pixel_array_for_statistics()
        if pixel_array is None:
            return None
        if self._is_mpr_view() and self.get_mpr_output_pixel_spacing is not None:
            pixel_spacing = self.get_mpr_output_pixel_spacing()
        else:
            pixel_spacing = get_pixel_spacing(current_dataset)

        rescale_slope, rescale_intercept, _rescale_type, use_rescaled = (
            self.get_rescale_params()
        )
        if self._is_mpr_view():
            awl_slope, awl_intercept = None, None
        else:
            awl_slope = rescale_slope if use_rescaled else None
            awl_intercept = rescale_intercept if use_rescaled else None

        stats = self.roi_manager.calculate_statistics(
            roi,
            pixel_array,
            rescale_slope=awl_slope,
            rescale_intercept=awl_intercept,
            pixel_spacing=pixel_spacing,
            dataset=current_dataset,
        )
        min_v = stats.get("min")
        max_v = stats.get("max")
        if not stats or min_v is None or max_v is None:
            return None
        window_width = float(max_v) - float(min_v)
        window_center = (float(min_v) + float(max_v)) / 2.0
        return window_center, window_width

    def _drawing_finish_auto_window_level(
        self,
        roi_item,
        current_dataset,
        study_uid: str,
        series_uid: str,
        instance_identifier: int,
    ) -> None:
        """Apply auto window/level from a temporary ROI, then discard it."""
        try:
            roi = roi_item
            if roi is not None and current_dataset is not None:
                wl = self._drawing_finish_compute_auto_wl(roi, current_dataset)
                if wl is not None:
                    window_center, window_width = wl
                    self.window_level_controls.set_window_level(
                        window_center, window_width
                    )
                    self._drawing_finish_discard_auto_wl_roi(
                        roi, study_uid, series_uid, instance_identifier
                    )
                    self._drawing_finish_restore_pan_mode()
        except Exception as e:
            print_redacted(f"Error in auto window/level: {e}")
            _logger.debug("%s", sanitized_format_exc())
            if roi_item is not None:
                self._drawing_finish_discard_auto_wl_roi(
                    roi_item, study_uid, series_uid, instance_identifier
                )
            self._drawing_finish_restore_pan_mode()

    def _drawing_finish_normal_add(
        self,
        roi_item,
        current_dataset,
        study_uid: str,
        series_uid: str,
        instance_identifier: int,
    ) -> None:
        """Commit a normal ROI draw (undo-aware) and select it for stats."""
        if roi_item is not None and self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import ROICommand

            command = ROICommand(
                self.roi_manager,
                "add",
                roi_item,
                self.image_viewer.scene,
                study_uid,
                series_uid,
                instance_identifier,
                update_statistics_callback=self.update_roi_statistics_overlays,
            )
            self.undo_redo_manager.execute_command(command)
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()

        self.roi_list_panel.update_roi_list(
            study_uid, series_uid, instance_identifier, self.roi_manager
        )

        if roi_item is None:
            return
        roi_item.on_moved_callback = lambda r=roi_item: self._on_roi_moved(r)
        self.roi_list_panel.select_roi_in_list(roi_item)
        if current_dataset is not None:
            self.update_roi_statistics(roi_item)
        self._auto_show_resize_handles_after_select(roi_item)

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
            self._auto_show_resize_handles_after_select(roi)

    def _auto_show_resize_handles_after_select(self, roi: ROIItem | None) -> None:
        """Show corner/edge handles for the selected rectangle or ellipse ROI (no-op for other types)."""
        if roi is None or self.image_viewer.scene is None:
            return
        if roi.shape_type not in ("rectangle", "ellipse"):
            return
        self.roi_manager.enter_roi_geometry_edit_mode(
            roi,
            self.image_viewer.scene,
            on_commit=self._on_roi_geometry_resize_committed,
        )

    def handle_roi_geometry_edit_requested(self, roi: ROIItem) -> None:
        """Programmatic entry: select ROI and show resize handles (same as auto-select behavior)."""
        if self.image_viewer.scene is None:
            return
        self.roi_manager.select_roi(roi)
        self._auto_show_resize_handles_after_select(roi)

    def exit_roi_geometry_edit_mode(self) -> bool:
        """Leave ROI resize-handle mode if active (Escape, slice change, etc.)."""
        return self.roi_manager.exit_roi_geometry_edit_mode()

    def _on_roi_geometry_resize_committed(
        self, roi: ROIItem, old_rect: QRectF, new_rect: QRectF
    ) -> None:
        """Push undo command and refresh statistics after a completed resize gesture."""
        if self.undo_redo_manager and self.image_viewer.scene:
            from tools.roi_graphics_items import apply_roi_scene_bounding_rect
            from utils.undo_redo import ROIGeometryResizeCommand

            command = ROIGeometryResizeCommand(
                roi, old_rect, new_rect, self.image_viewer.scene,
                apply_fn=apply_roi_scene_bounding_rect,
            )
            self.undo_redo_manager.execute_command(command)
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()
        self.update_roi_statistics(roi)
        if self.image_viewer.scene is not None:
            self.roi_manager.update_statistics_overlay_position(roi, self.image_viewer.scene)

    def handle_image_clicked_no_roi(self) -> None:
        """Handle image click when not on an ROI - deselect current ROI."""
        self.roi_manager.exit_roi_geometry_edit_mode()

        # Deselect ROI
        self.roi_manager.select_roi(None)

        # Clear scene selection to prevent Qt's default mouse release behavior from re-selecting the ROI
        if self.image_viewer.scene is not None:
            list(self.image_viewer.scene.selectedItems())
            self.image_viewer.scene.clearSelection()
            list(self.image_viewer.scene.selectedItems())

        # Clear ROI list selection
        self.roi_list_panel.roi_list.currentItem()
        self.roi_list_panel.select_roi_in_list(None)
        self.roi_list_panel.roi_list.currentItem()

        # Clear ROI statistics panel
        self.roi_statistics_panel.clear_statistics()

    def handle_roi_selected(self, roi) -> None:
        """
        Handle ROI selection from list.
        
        Args:
            roi: Selected ROI item
        """
        # Validate ROI belongs to this manager
        if roi is not None:
            roi_belongs = False
            for roi_list in self.roi_manager.rois.values():
                if roi in roi_list:
                    roi_belongs = True
                    break

            if not roi_belongs:
                return

        self.update_roi_statistics(roi)
        self._auto_show_resize_handles_after_select(roi)

    def handle_roi_delete_requested(self, item) -> None:
        """
        Handle ROI deletion request from context menu.
        
        Args:
            item: QGraphicsItem to delete
        """
        roi = self.roi_manager.find_roi_by_item(item)
        if not roi:
            return

        self._delete_prepare_roi_for_removal(roi)
        current_dataset, study_uid, series_uid, instance_identifier = (
            self._drawing_finish_slice_context()
        )
        self._delete_execute_remove(roi, study_uid, series_uid, instance_identifier)
        self.handle_roi_deleted(roi)
        if current_dataset is not None:
            self.roi_list_panel.update_roi_list(
                study_uid, series_uid, instance_identifier, self.roi_manager
            )
        if self.roi_manager.get_selected_roi() is None:
            self.roi_statistics_panel.clear_statistics()

    def _delete_prepare_roi_for_removal(self, roi) -> None:
        """Hide resize handles and exit geometry-edit mode before ROI removal."""
        scene = self.image_viewer.scene
        if scene is not None:
            try:
                roi.hide_resize_handles(scene)
            except RuntimeError:
                pass
        self.roi_manager.exit_roi_geometry_edit_mode()

    def _delete_execute_remove(
        self,
        roi,
        study_uid: str,
        series_uid: str,
        instance_identifier: int,
    ) -> None:
        """Remove ROI via undo command when available, else delete directly."""
        if self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import ROICommand

            command = ROICommand(
                self.roi_manager,
                "remove",
                roi,
                self.image_viewer.scene,
                study_uid,
                series_uid,
                instance_identifier,
                update_statistics_callback=self.update_roi_statistics_overlays,
            )
            self.undo_redo_manager.execute_command(command)
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()
            return
        self.roi_manager.delete_roi(roi, self.image_viewer.scene)

    def handle_roi_deleted(self, roi) -> None:
        """
        Handle ROI deletion.
        
        Args:
            roi: Deleted ROI item
        """
        # Explicitly remove statistics overlay from scene
        if self.image_viewer.scene is not None:
            # Check if ROI still has overlay before trying to remove
            if hasattr(roi, 'statistics_overlay_item') and roi.statistics_overlay_item is not None:
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
            series_uid = get_composite_series_key(current_dataset)
            instance_identifier = self.get_current_slice_index()
            remaining_rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
            if remaining_rois:
                self.update_roi_statistics_overlays()

        # Clear statistics if this was the selected ROI
        if self.roi_manager.get_selected_roi() is None:
            self.roi_statistics_panel.clear_statistics()

    def delete_all_rois_current_slice(self) -> None:
        """
        Delete all ROIs and crosshairs on the current slice.
        
        Called by D key keyboard shortcut and Delete All button in ROI list panel.
        """
        current_dataset = self.get_current_dataset()
        if current_dataset is None:
            return

        study_uid = getattr(current_dataset, "StudyInstanceUID", "")
        series_uid = get_composite_series_key(current_dataset)
        if not study_uid or not series_uid:
            return

        instance_identifier = self.get_current_slice_index()
        rois_to_delete, crosshairs_to_delete = self._delete_all_collect_targets(
            study_uid, series_uid, instance_identifier
        )
        if not rois_to_delete and not crosshairs_to_delete:
            return

        self.roi_manager.exit_roi_geometry_edit_mode()
        self._delete_all_execute(
            rois_to_delete,
            crosshairs_to_delete,
            study_uid,
            series_uid,
            instance_identifier,
        )
        self.roi_list_panel.update_roi_list(
            study_uid, series_uid, instance_identifier, self.roi_manager
        )
        self.roi_statistics_panel.clear_statistics()

    def _delete_all_collect_targets(
        self, study_uid: str, series_uid: str, instance_identifier: int
    ) -> tuple[list[ROIItem], list[Any]]:
        """Collect ROIs and crosshairs on the current slice before bulk delete."""
        key = (study_uid, series_uid, instance_identifier)
        rois_to_delete: list[ROIItem] = []
        if key in self.roi_manager.rois:
            rois_to_delete = list(self.roi_manager.rois[key])

        crosshairs_to_delete: list[Any] = []
        if self.crosshair_coordinator and self.crosshair_coordinator.crosshair_manager:
            if key in self.crosshair_coordinator.crosshair_manager.crosshairs:
                crosshairs_to_delete = list(
                    self.crosshair_coordinator.crosshair_manager.crosshairs[key]
                )
        return rois_to_delete, crosshairs_to_delete

    def _delete_all_build_commands(
        self,
        rois_to_delete: list[ROIItem],
        crosshairs_to_delete: list[Any],
        study_uid: str,
        series_uid: str,
        instance_identifier: int,
    ) -> list[Any]:
        """Build undo commands for bulk ROI and crosshair removal."""
        from utils.undo_redo import CrosshairCommand, ROICommand

        commands: list[Any] = []
        for roi_item in rois_to_delete:
            commands.append(
                ROICommand(
                    self.roi_manager,
                    "remove",
                    roi_item,
                    self.image_viewer.scene,
                    study_uid,
                    series_uid,
                    instance_identifier,
                    update_statistics_callback=self.update_roi_statistics_overlays,
                )
            )
        if self.crosshair_coordinator and crosshairs_to_delete:
            for crosshair_item in crosshairs_to_delete:
                commands.append(
                    CrosshairCommand(
                        self.crosshair_coordinator.crosshair_manager,
                        "remove",
                        crosshair_item,
                        self.image_viewer.scene,
                        study_uid,
                        series_uid,
                        instance_identifier,
                    )
                )
        return commands

    def _delete_all_execute(
        self,
        rois_to_delete: list[ROIItem],
        crosshairs_to_delete: list[Any],
        study_uid: str,
        series_uid: str,
        instance_identifier: int,
    ) -> None:
        """Execute bulk delete via composite undo command or direct clear."""
        if self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import CompositeCommand

            commands = self._delete_all_build_commands(
                rois_to_delete,
                crosshairs_to_delete,
                study_uid,
                series_uid,
                instance_identifier,
            )
            if commands:
                self.undo_redo_manager.execute_command(CompositeCommand(commands))
                if self.update_undo_redo_state_callback:
                    self.update_undo_redo_state_callback()
            return

        if rois_to_delete:
            self.roi_manager.clear_slice_rois(
                study_uid, series_uid, instance_identifier, self.image_viewer.scene
            )
        if self.crosshair_coordinator and crosshairs_to_delete:
            self.crosshair_coordinator.handle_clear_crosshairs()

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

        if not self._roi_belongs_to_manager(roi):
            _logger.warning("ROI ownership validation failed; details withheld")
            return

        try:
            study_uid = getattr(current_dataset, "StudyInstanceUID", "")
            series_uid = get_composite_series_key(current_dataset)
            instance_identifier = self.get_current_slice_index()
            roi_identifier = self._roi_identifier_for_slice(
                roi, study_uid, series_uid, instance_identifier
            )

            pixel_array = self._get_pixel_array_for_statistics()
            if pixel_array is None:
                return

            (
                pixel_spacing,
                stats_slope,
                stats_intercept,
                display_rescale_type,
            ) = self._stats_spacing_and_rescale_params(current_dataset)

            stats = self.roi_manager.calculate_statistics(
                roi,
                pixel_array,
                rescale_slope=stats_slope,
                rescale_intercept=stats_intercept,
                pixel_spacing=pixel_spacing,
                dataset=current_dataset,
            )

            self.roi_statistics_panel.update_statistics(
                stats, roi_identifier, rescale_type=display_rescale_type
            )

            if self.image_viewer.scene is not None and roi.statistics_overlay_visible:
                self.roi_manager.update_statistics_overlay(
                    roi,
                    stats,
                    self.image_viewer.scene,
                    font_size=None,
                    font_color=None,
                    rescale_type=display_rescale_type,
                )
        except Exception:
            _logger.debug("%s", sanitized_format_exc())

    def handle_scene_selection_changed(self) -> None:
        """Handle scene selection change (e.g., when ROI is moved)."""
        try:
            if self.image_viewer.scene is None:
                return
            selected_items = self.image_viewer.scene.selectedItems()
            if selected_items:
                self._scene_selection_sync_selected_roi(selected_items)
            else:
                self._scene_selection_refresh_overlay_positions()
        except RuntimeError:
            # Scene has been deleted or is invalid, ignore
            return

    def _scene_selection_sync_selected_roi(self, selected_items) -> None:
        """Sync list/stats/handles for the first selected scene ROI."""
        for item in selected_items:
            roi = self.roi_manager.find_roi_by_item(item)
            if roi:
                self.update_roi_statistics(roi)
                self.roi_list_panel.select_roi_in_list(roi)
                self._auto_show_resize_handles_after_select(roi)
                break

    def _scene_selection_refresh_overlay_positions(self) -> None:
        """Refresh overlay positions for visible ROI stats after deselection."""
        current_dataset = self.get_current_dataset()
        if current_dataset is None:
            return
        study_uid = getattr(current_dataset, "StudyInstanceUID", "")
        series_uid = get_composite_series_key(current_dataset)
        instance_identifier = self.get_current_slice_index()
        rois = self.roi_manager.get_rois_for_slice(
            study_uid, series_uid, instance_identifier
        )
        for roi in rois:
            if (
                roi.statistics_overlay_item is not None
                and roi.statistics_overlay_visible
            ):
                self.roi_manager.update_statistics_overlay_position(
                    roi, self.image_viewer.scene
                )

    def hide_roi_graphics(self, hide: bool) -> None:
        """
        Hide or show ROI graphics (shapes).
        
        Args:
            hide: True to hide graphics, False to show them
        """
        if self.image_viewer.scene is None:
            return

        from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem
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

        study_uid = getattr(current_dataset, "StudyInstanceUID", "")
        series_uid = get_composite_series_key(current_dataset)
        instance_identifier = self.get_current_slice_index()
        rois = self.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)

        pixel_array = self._get_pixel_array_for_statistics()
        if pixel_array is None:
            return

        (
            pixel_spacing,
            stats_slope,
            stats_intercept,
            display_rescale_type,
        ) = self._stats_spacing_and_rescale_params(current_dataset)

        # Remove orphaned overlays from previous slices before recreating.
        self.roi_manager.remove_all_statistics_overlays_from_scene(self.image_viewer.scene)

        for roi in rois:
            if roi.on_moved_callback is None:
                roi.on_moved_callback = lambda r=roi: self._on_roi_moved(r)

            stats = self.roi_manager.calculate_statistics(
                roi,
                pixel_array,
                rescale_slope=stats_slope,
                rescale_intercept=stats_intercept,
                pixel_spacing=pixel_spacing,
                dataset=current_dataset,
            )

            if stats and roi.statistics_overlay_visible:
                self.roi_manager.create_statistics_overlay(
                    roi,
                    stats,
                    self.image_viewer.scene,
                    font_size=None,
                    font_color=None,
                    rescale_type=display_rescale_type,
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

    def handle_roi_statistics_selection(self, roi, statistics_to_show: set[str]) -> None:
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
        Handle ROI movement - track for undo/redo with batching and update statistics.
        
        Args:
            roi: ROI item that was moved
        """
        try:
            # Check if ROI is still valid
            if roi is None or not hasattr(roi, 'item') or roi.item is None:
                return

            # Get current position
            current_pos = roi.item.pos()

            # Check if ROI is being tracked for movement
            if roi not in self._roi_move_tracking:
                # Store initial position and start tracking
                self._roi_move_tracking[roi] = {
                    'initial_pos': current_pos,
                    'current_pos': current_pos
                }
            else:
                # Update current position (don't create command yet)
                self._roi_move_tracking[roi]['current_pos'] = current_pos

            # Start/restart batch timer (200ms delay)
            if self._move_batch_timer is not None:
                self._move_batch_timer.stop()

            self._move_batch_timer = QTimer()
            self._move_batch_timer.setSingleShot(True)
            self._move_batch_timer.timeout.connect(lambda: self._finalize_roi_move(roi))
            self._move_batch_timer.start(200)  # 200ms delay

            # Recalculate statistics for the moved ROI
            self.update_roi_statistics(roi)

            # Update overlay position
            if hasattr(roi, 'statistics_overlay_item') and roi.statistics_overlay_item is not None:
                if hasattr(roi, 'statistics_overlay_visible') and roi.statistics_overlay_visible:
                    if self.image_viewer.scene is not None:
                        self.roi_manager.update_statistics_overlay_position(roi, self.image_viewer.scene)

            # Update ROI statistics panel if this ROI is selected
            if self.roi_manager.get_selected_roi() == roi:
                # Statistics panel will be updated by update_roi_statistics
                pass
        except Exception:
            _logger.debug("%s", sanitized_format_exc())

    def _finalize_roi_move(self, roi) -> None:
        """
        Finalize ROI move by creating undo/redo command.
        
        Args:
            roi: ROI item that was moved
        """
        if roi not in self._roi_move_tracking:
            return

        tracking = self._roi_move_tracking[roi]
        initial_pos = tracking['initial_pos']
        final_pos = tracking['current_pos']

        # Only create command if position actually changed
        if initial_pos != final_pos and self.undo_redo_manager and self.image_viewer.scene:
            from utils.undo_redo import ROIMoveCommand
            command = ROIMoveCommand(roi, initial_pos, final_pos, self.image_viewer.scene)
            self.undo_redo_manager.execute_command(command)
            # Update undo/redo state after command execution
            if self.update_undo_redo_state_callback:
                self.update_undo_redo_state_callback()

        # Clear tracking
        del self._roi_move_tracking[roi]
