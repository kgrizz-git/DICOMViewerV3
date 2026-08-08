"""
DICOMViewerApp subwindow and MPR navigation mixin module.

Owns subwindow lifecycle, dataset/slice accessors, manager registry, and MPR
thumbnail/navigation handlers for ``DICOMViewerApp`` (see MAIN_PY_REFACTOR_PLAN Appendix A).
Methods extracted from ``main.py`` in Phase 4.
"""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportUninitializedInstanceVariable=false
import logging
from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core.mpr_navigator_thumbnail import (
    clear_mpr_navigator_thumbnail as mpr_thumb_clear_navigator,
)
from core.mpr_navigator_thumbnail import (
    get_subwindow_mpr_pixel_array as mpr_thumb_get_subwindow_pixel_array,
)
from core.mpr_navigator_thumbnail import (
    get_subwindow_mpr_thumbnail_pixel_array as mpr_thumb_get_subwindow_thumbnail_pixel_array,
)
from core.mpr_navigator_thumbnail import (
    on_mpr_detached as mpr_thumb_on_mpr_detached,
)
from core.mpr_navigator_thumbnail import (
    update_floating_mpr_navigator_thumbnail as mpr_thumb_update_floating_navigator,
)
from core.mpr_navigator_thumbnail import (
    update_mpr_navigator_thumbnail as mpr_thumb_update_navigator,
)
from core.navigation_slider_state import navigation_slider_mode_label_for_dataset
from core.overlay_settings_handlers import refresh_overlay_all_subwindows
from core.session_reset_controller import (
    clear_data as session_reset_clear_data,
)
from core.session_reset_controller import (
    close_all_files as session_reset_close_all_files,
)
from core.study_navigation_handlers import (
    clear_subwindow,
    clear_subwindow_content,
    close_series,
    close_study,
    get_subwindow_assignments,
    reset_focused_subwindow_state_after_close,
)
from gui.layout_window_slot_controller import (
    capture_subwindow_view_states as layout_capture_subwindow_view_states,
)
from gui.layout_window_slot_controller import (
    ensure_all_subwindows_have_managers as layout_ensure_all_subwindows_have_managers,
)
from gui.layout_window_slot_controller import (
    restore_subwindow_views as layout_restore_subwindow_views,
)
from gui.sub_window_container import SubWindowContainer
from gui.subwindow_image_viewer_sync import apply_theme_viewer_background_all
from gui.subwindow_manager_factory import build_managers_for_subwindow
from gui.tag_export_union_host import StudiesNestedDict
from utils.log_sanitizer import sanitized_format_exc
from utils.privacy import safe_event_fields
from utils.slice_sync_group_palette import (
    slice_sync_group_rgb,
    view_index_to_group_index,
)

_logger = logging.getLogger(__name__)


class SubwindowManagementMixin:
    """
    Mixin: subwindow manager registry, lifecycle, and per-subwindow dataset/slice
    accessor methods for ``DICOMViewerApp``.
    """

    def _build_managers_for_subwindow(self, idx: int, subwindow: SubWindowContainer) -> dict[str, Any]:
        """
        Build the full set of per-subwindow managers for the given subwindow.
        Delegates to ``gui.subwindow_manager_factory.build_managers_for_subwindow``.
        """
        return build_managers_for_subwindow(self, idx, subwindow)

    def _create_managers_for_subwindow(self, idx: int, subwindow: SubWindowContainer) -> None:
        """Create managers for a specific subwindow (e.g. when layout adds a new pane)."""
        if subwindow is None:
            return
        managers = self._build_managers_for_subwindow(idx, subwindow)
        image_viewer = subwindow.image_viewer
        image_viewer.set_subwindow_index(idx)
        image_viewer.set_slice_sync_enabled_state(self.config_manager.get_slice_sync_enabled())
        image_viewer.set_smooth_when_zoomed_state(self.config_manager.get_smooth_image_when_zoomed())
        image_viewer.set_scale_markers_state(self.config_manager.get_show_scale_markers())
        image_viewer.set_direction_labels_state(self.config_manager.get_show_direction_labels())
        image_viewer.set_scale_markers_color_state(self.config_manager.get_scale_markers_color())
        image_viewer.set_direction_labels_color_state(self.config_manager.get_direction_labels_color())
        image_viewer.set_direction_label_size_state(self.config_manager.get_direction_label_size())
        image_viewer.set_scale_markers_tick_intervals_state(
            self.config_manager.get_scale_markers_major_tick_interval_mm(),
            self.config_manager.get_scale_markers_minor_tick_interval_mm(),
        )
        image_viewer.get_file_path_callback = lambda i=idx: self._get_current_slice_file_path(i)
        self.subwindow_managers[idx] = managers
        if idx not in self.subwindow_data:
            self.subwindow_data[idx] = {
                'current_dataset': None,
                'current_slice_index': 0,
                'current_series_uid': '',
                'current_study_uid': '',
                'current_datasets': []
            }
        image_viewer.set_mouse_mode("pan")
        apply_theme_viewer_background_all(self)
        self._refresh_slice_sync_group_indicators()

    def _refresh_slice_sync_group_indicators(self) -> None:
        """
        Update per-pane title-strip colors for slice-sync linked groups.

        Uses **view** indices (0–3) from config, matching ``SliceSyncCoordinator``
        and ``ImageViewer.subwindow_index``. The strip is hidden when sync is off
        or the pane is not in a multi-member group.
        """
        sync_on = self.config_manager.get_slice_sync_enabled()
        groups = list(self.config_manager.get_slice_sync_groups()) if sync_on else []
        strip_h = self.config_manager.get_slice_sync_group_strip_height_px()
        for sub in self.multi_window_layout.get_all_subwindows():
            if sub is None:
                continue
            sub.set_slice_sync_strip_height(strip_h)
            iv = sub.image_viewer
            idx = getattr(iv, "subwindow_index", None) if iv is not None else None
            if idx is None:
                sub.set_slice_sync_group_indicator(None)
                continue
            gi = view_index_to_group_index(groups, int(idx))
            if gi is None:
                sub.set_slice_sync_group_indicator(None)
            else:
                r, g, b = slice_sync_group_rgb(gi)
                sub.set_slice_sync_group_indicator(QColor(r, g, b))

    def _get_subwindow_dataset(self, idx: int) -> Dataset | None:
        """Get current dataset for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_dataset(idx)

    def _get_subwindow_slice_index(self, idx: int) -> int:
        """Get current slice index for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_slice_index(idx)

    def _get_subwindow_slice_display_manager(self, idx: int):
        """Get slice display manager for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_slice_display_manager(idx)

    def _sync_navigation_slider_for_subwindow(self, idx: int) -> None:
        """
        Align one pane's edge-reveal slice slider with its current content.

        Hides the overlay and resets internal range to 1/1 when the pane has no
        navigable stack (empty, single-slice native series, or invalid UIDs).
        For MPR, uses ``mpr_result.n_slices`` and ``mpr_slice_index``. For native
        2-D, uses ``current_studies[study][series]`` length and ``current_slice_index``.
        """
        if idx < 0:
            return
        subwindow = self.multi_window_layout.get_subwindow(idx)
        if subwindow is None or subwindow.image_viewer is None:
            return
        viewer = subwindow.image_viewer
        data = self.subwindow_data.get(idx, {})

        if hasattr(self, "_mpr_controller") and self._mpr_controller.is_mpr(idx):
            result = data.get("mpr_result")
            n_slices = int(getattr(result, "n_slices", 0) or 0) if result is not None else 0
            if n_slices > 1:
                si = int(data.get("mpr_slice_index", 0))
                viewer.set_navigation_slider_state(
                    enabled=True,
                    minimum=1,
                    maximum=n_slices,
                    value=si + 1,
                    mode_label="Slice",
                )
            else:
                viewer.set_navigation_slider_state(
                    enabled=False, minimum=1, maximum=1, value=1
                )
            return

        study_uid = data.get("current_study_uid", "")
        series_uid = data.get("current_series_uid", "")
        if not series_uid or not study_uid:
            viewer.set_navigation_slider_state(
                enabled=False, minimum=1, maximum=1, value=1
            )
            return

        datasets = self.current_studies.get(study_uid, {}).get(series_uid, [])
        total = len(datasets)
        current_idx = int(data.get("current_slice_index", 0))
        if total > 1:
            current_dataset = data.get("current_dataset")
            if current_dataset is None and 0 <= current_idx < total:
                current_dataset = datasets[current_idx]
            viewer.set_navigation_slider_state(
                enabled=True,
                minimum=1,
                maximum=total,
                value=current_idx + 1,
                mode_label=navigation_slider_mode_label_for_dataset(current_dataset),
            )
        else:
            viewer.set_navigation_slider_state(
                enabled=False, minimum=1, maximum=1, value=1
            )

    def _get_subwindow_study_uid(self, idx: int) -> str:
        """Get current study UID for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_study_uid(idx)

    def _get_subwindow_series_uid(self, idx: int) -> str:
        """Get current series UID for a subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_subwindow_series_uid(idx)

    def get_focused_subwindow_index(self) -> int:
        """Return the currently focused subwindow index (0-3). Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_focused_subwindow_index()

    def get_histogram_callbacks_for_subwindow(self, idx: int) -> dict[str, Any]:
        """Return callbacks for the histogram dialog for subwindow idx. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_histogram_callbacks_for_subwindow(idx)

    def _update_focused_subwindow_references(self) -> None:
        """Update legacy references to point to focused subwindow's managers and data. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.update_focused_subwindow_references()
        # Keep ROI measurement controller in sync with the active subwindow's managers.
        if hasattr(self, 'roi_measurement_controller') and self.roi_measurement_controller:
            self.roi_measurement_controller.update_focused_managers(
                getattr(self, 'roi_manager', None),
                getattr(self, 'measurement_tool', None),
            )

    def has_shown_fusion_notification(self, study_uid: str) -> bool:
        """
        Check if fusion notification has already been shown for a study.
        
        Args:
            study_uid: Study UID to check
            
        Returns:
            True if notification was already shown, False otherwise
        """
        return study_uid in self._fusion_notified_studies

    def mark_fusion_notification_shown(self, study_uid: str) -> None:
        """
        Mark that fusion notification has been shown for a study.
        
        Args:
            study_uid: Study UID to mark as notified
        """
        if study_uid:
            self._fusion_notified_studies.add(study_uid)

    def _update_right_panel_for_focused_subwindow(self) -> None:
        """Update right panel controls to reflect focused subwindow's state. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.update_right_panel_for_focused_subwindow()

    def _update_left_panel_for_focused_subwindow(self) -> None:
        """Update left panel controls (metadata, cine) to reflect focused subwindow's state. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.update_left_panel_for_focused_subwindow()

    def _redisplay_subwindow_slice(self, idx: int, preserve_view: bool = False) -> None:
        """Redisplay slice for a specific subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.redisplay_subwindow_slice(idx, preserve_view)
        self._slice_location_line_coordinator.refresh_all()

    def _clear_data(self) -> None:
        """Clear all ROIs, measurements, and related data for all subwindows."""
        session_reset_clear_data(self)

    def _close_files(self) -> None:
        """Close currently open files/folder and clear all data."""
        session_reset_close_all_files(self)

    def _get_subwindow_assignments(self) -> dict[int, tuple[str, str, int]]:
        """
        Build a mapping of grid **slot** index → (study_uid, series_key, slice_index) for each
        slot that has a loaded series.

        Slot indices (0–3) match the colored window dots in SeriesNavigator and the 2×2 grid
        positions. ``multi_window_layout.get_slot_to_view()[s]`` is the **view** index shown
        in slot ``s``; dataset state for that view lives in ``subwindow_data[view_idx]``.
        After **Swap Windows**, slot→view changes while ``subwindow_data`` stays keyed by view,
        so assignments must be derived from ``slot_to_view`` (not raw ``subwindow_data`` keys).

        Returns:
            Dict mapping slot index (0–3) to
            (current_study_uid, current_series_uid, current_slice_index).
        """
        return get_subwindow_assignments(self)

    def _reset_fusion_handler_for_subwindow(self, idx: int) -> None:
        """
        Disable fusion and clear caches for one subwindow's FusionHandler only.

        Does not change the shared fusion controls widget (that remains for
        ``_reset_fusion_for_all_subwindows`` on full close/open).

        Args:
            idx: Zero-based subwindow index (0–3).
        """
        if idx not in self.subwindow_managers:
            return
        managers = self.subwindow_managers[idx]
        fusion_handler = managers.get("fusion_handler")
        if not fusion_handler:
            return
        fusion_handler.fusion_enabled = False
        fusion_handler._slice_location_cache.clear()
        fusion_handler._resampling_decision_cache = None
        fusion_handler._resampling_decision_cache_key = None
        fusion_handler.clear_alignment_cache()
        if hasattr(fusion_handler, "image_resampler") and fusion_handler.image_resampler:
            fusion_handler.image_resampler.clear_cache()

    def _clear_subwindow(self, idx: int) -> None:
        """
        Clear scene, overlays, ROIs, measurements, and annotations for a single
        subwindow by index.  Resets subwindow_data[idx] to the empty template.

        Does NOT touch focused-subwindow app-level attributes (current_dataset, etc.)
        — callers are responsible for those when the closed subwindow was focused.

        Args:
            idx: Zero-based subwindow index (0–3).
        """
        clear_subwindow(self, idx)

    def _reset_focused_subwindow_state_after_close(self) -> None:
        """
        Update the focused-subwindow app-level attributes after its content was
        cleared by _close_series or _close_study.

        Resets current_dataset/study/series/slice, clears the slice navigator,
        metadata panel, cine player, and re-wires focused-subwindow signals.
        """
        reset_focused_subwindow_state_after_close(self)

    def _on_clear_subwindow_content_requested(self, idx: int) -> None:
        """
        Clear one image pane from the context menu; loaded studies/series are unchanged.

        Args:
            idx: Subwindow index (0–3) for the viewer that requested the action.
        """
        clear_subwindow_content(self, idx)

    def _close_series(self, study_uid: str, series_key: str) -> None:
        """
        Close a single series: free pixel caches, remove it from the organizer,
        clear any subwindows that were showing it, and refresh the navigator.

        Focus stays on the now-empty subwindow if the closed series was focused.

        Args:
            study_uid:  StudyInstanceUID of the series to close.
            series_key: Composite series key (SeriesInstanceUID + SeriesNumber).
        """
        close_series(self, study_uid, series_key)

    def _close_study(self, study_uid: str) -> None:
        """
        Close an entire study: free pixel caches for all its series, remove it
        from the organizer, clear all affected subwindows, and refresh the
        navigator in one pass (no per-series navigator refreshes).

        Focus stays on the now-empty subwindow if any focused series was closed.

        Args:
            study_uid: StudyInstanceUID of the study to close.
        """
        close_study(self, study_uid)

    def _reset_fusion_for_all_subwindows(self) -> None:
        """
        Disable fusion and clear status for all subwindows.

        This is called when files are closed or when new files are opened
        to ensure fusion is disabled and status messages are cleared.
        """
        for idx in self.subwindow_managers:
            self._reset_fusion_handler_for_subwindow(idx)

        # Disable fusion in UI widget and clear status messages
        self.fusion_controls_widget.set_fusion_enabled(False)
        self.fusion_controls_widget.clear_status()

    def _handle_load_first_slice(self, studies: StudiesNestedDict) -> None:
        """
        Handle loading first slice after file operations.

        Delegates to the file/series loading coordinator. Clears edited tags
        for the previous dataset and updates display/state via the coordinator.
        """
        self._file_series_coordinator.handle_load_first_slice(studies)

    def _get_rescale_params(self) -> tuple[float | None, float | None, str | None, bool]:
        """Get rescale parameters for ROI operations (focused subwindow's view state)."""
        return (
            self.view_state_manager.rescale_slope,
            self.view_state_manager.rescale_intercept,
            self.view_state_manager.rescale_type,
            self.view_state_manager.use_rescaled_values
        )

    def _get_subwindow_rescale_params(
        self, idx: int
    ) -> tuple[float | None, float | None, str | None, bool]:
        """
        Rescale parameters for the given subwindow (ROI / statistics must match
        that pane's ``ViewStateManager``, not the legacy focused-window alias).
        """
        managers = self.subwindow_managers.get(idx, {})
        vsm = managers.get("view_state_manager")
        if vsm is None:
            return None, None, None, True
        return (
            getattr(vsm, "rescale_slope", None),
            getattr(vsm, "rescale_intercept", None),
            getattr(vsm, "rescale_type", None),
            bool(getattr(vsm, "use_rescaled_values", True)),
        )

    def _on_focused_subwindow_changed(self, subwindow: SubWindowContainer) -> None:
        """Handle focused subwindow change. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.on_focused_subwindow_changed(subwindow)
        self._update_3d_view_action_state()
        # When "Show Only For Focused Window" is on, refresh slice location lines so they track focus.
        if self.config_manager.get_slice_location_lines_focused_only():
            self._slice_location_line_coordinator.refresh_all()
        # Refresh window-slot thumbnail(s) so focus outline updates.
        self._refresh_window_slot_map_widgets()

    def _capture_subwindow_view_states(self) -> dict[int, dict[str, Any]]:
        """Capture view state for all subwindows before layout change."""
        return layout_capture_subwindow_view_states(self)

    def _restore_subwindow_views(self, view_states: dict[int, dict[str, Any]]) -> None:
        """Restore subwindow views after layout change."""
        layout_restore_subwindow_views(self, view_states)

    def _ensure_all_subwindows_have_managers(self) -> None:
        """Ensure all visible subwindows have managers."""
        layout_ensure_all_subwindows_have_managers(self)

    def _assign_series_to_subwindow(self, subwindow: SubWindowContainer, series_uid: str, slice_index: int) -> None:
        """Assign a series/slice to a specific subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.assign_series_to_subwindow(subwindow, series_uid, slice_index)

    def _disconnect_focused_subwindow_signals(self) -> None:
        """Disconnect signals from previously focused subwindow. Delegates to subwindow lifecycle controller."""
        self._subwindow_lifecycle_controller.disconnect_focused_subwindow_signals()

    def _refresh_overlay_all_subwindows(self) -> None:
        """Recreate corner overlays in every subwindow that has overlay coordinators."""
        refresh_overlay_all_subwindows(self)

    def _update_histogram_for_focused_subwindow(self) -> None:
        """Schedule a throttled full histogram update (pixel refetch) for slice/series changes."""
        if not hasattr(self, "dialog_coordinator"):
            return
        self._restart_single_shot_timer(
            "_histogram_update_timer",
            300,
            self._do_update_histogram_for_focused_subwindow,
        )

    def _do_update_histogram_for_focused_subwindow(self) -> None:
        """Update the histogram dialog for the currently focused subwindow (called after throttle delay)."""
        if hasattr(self, "dialog_coordinator"):
            self.dialog_coordinator.update_histogram_for_subwindow(self.focused_subwindow_index)

    def _get_focused_subwindow(self) -> SubWindowContainer | None:
        """Get the currently focused subwindow. Delegates to subwindow lifecycle controller."""
        return self._subwindow_lifecycle_controller.get_focused_subwindow()

    def _get_thumbnail_for_view(self, view_index: int):
        """
        Return a small pixmap of the current image displayed in the given view (0–3),
        for use in the window-slot map thumbnail. Returns None if the view has no image.
        """
        subwindows = self.multi_window_layout.get_all_subwindows()
        if view_index < 0 or view_index >= len(subwindows):
            return None
        sub = subwindows[view_index]
        if not sub or not sub.image_viewer:
            return None
        view = sub.image_viewer
        vp = view.viewport()
        if vp is None or vp.width() <= 0 or vp.height() <= 0:
            return None
        pix = vp.grab(vp.rect())
        if pix.isNull():
            return None
        cell = 40
        return pix.scaled(
            cell, cell,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )



class MPRNavigationMixin:
    """
    Mixin: MPR navigator thumbnail updates, detached MPR handling, and MPR thumbnail
    click navigation for ``DICOMViewerApp``.
    """

    def _get_subwindow_mpr_pixel_array(self, idx: int, slice_index: int | None = None):
        """Return an MPR pixel array for subwindow *idx* (if any). Body in ``core.mpr_navigator_thumbnail``."""
        return mpr_thumb_get_subwindow_pixel_array(self, idx, slice_index)

    def _get_subwindow_mpr_thumbnail_pixel_array(self, idx: int):
        """Return a representative MPR thumbnail slice, preferring the stack midpoint."""
        return mpr_thumb_get_subwindow_thumbnail_pixel_array(self, idx)

    def _update_mpr_navigator_thumbnail(self, idx: int) -> None:
        """
        Show or refresh the MPR thumbnail in the series navigator for subwindow *idx*.

        Called automatically when ``MprController.mpr_activated`` is emitted.
        The thumbnail is built from the currently-displayed MPR slice pixel
        array with the active W/L values so it matches what is on screen.

        Args:
            idx: Zero-based subwindow index hosting the MPR view.
        """
        mpr_thumb_update_navigator(self, idx)

    def _clear_mpr_navigator_thumbnail(self, idx: int) -> None:
        """
        Remove the MPR thumbnail from the series navigator for subwindow *idx*.

        Called automatically when ``MprController.mpr_cleared`` is emitted.

        Args:
            idx: Zero-based subwindow index whose MPR was cleared.
        """
        mpr_thumb_clear_navigator(self, idx)

    def _update_floating_mpr_navigator_thumbnail(self) -> None:
        """
        Show or refresh detached MPR under navigator key -1 (internal id only).

        Layout matches attached MPR: same study/series keys place the thumbnail
        immediately after the source series row.
        """
        mpr_thumb_update_floating_navigator(self)

    def _on_mpr_detached(self, former_idx: int) -> None:
        """MPR was detached from a pane; refresh navigator thumbnails."""
        mpr_thumb_on_mpr_detached(self, former_idx)

    def _on_mpr_thumbnail_clicked(self, subwindow_index: int) -> None:
        """
        Focus the subwindow that hosts the MPR view when its thumbnail is clicked.

        Args:
            subwindow_index: Zero-based index of the MPR subwindow, or -1 if detached.
        """
        if subwindow_index < 0:
            return
        try:
            subwindow = self.multi_window_layout.get_subwindow(subwindow_index)
            if subwindow is not None and not subwindow.is_focused:
                subwindow.set_focused(True)
        except Exception as exc:
            _logger.error(  # NOSONAR (python:S8572): raw logging.exception is prohibited by the PHI/PII sink gate.
                "MPR thumbnail focus failed",
                extra=safe_event_fields("mpr.thumbnail_focus", error=exc),
            )
            _logger.debug("%s", sanitized_format_exc())

    def _on_mpr_assign_requested(
        self, source_subwindow_index: int, target_subwindow_index: int
    ) -> None:
        """
        Handle MPR thumbnail drop onto a subwindow: relocate active MPR or
        attach a detached session (source index -1).
        """
        if source_subwindow_index < 0:
            self._mpr_controller.attach_floating_mpr(target_subwindow_index)
            return
        self._mpr_controller.relocate_mpr_subwindow(
            source_subwindow_index, target_subwindow_index
        )

    def _on_mpr_clear_from_navigator_thumbnail(self, subwindow_index: int) -> None:
        """Clear MPR from the navigator context menu (attached or detached)."""
        if subwindow_index < 0:
            self._mpr_controller.clear_detached_mpr()
            if hasattr(self, "series_navigator"):
                self.series_navigator.clear_mpr_thumbnail(-1)
            return
        if self._mpr_controller.is_mpr(subwindow_index):
            self._mpr_controller.clear_mpr(subwindow_index)

    def _sync_intensity_projection_widget_from_mpr_data(self, data: dict[str, Any]) -> None:
        """Push ``mpr_combine_*`` from *data* to the right-pane Combine Slices widget."""
        self._projection_app_facade.sync_intensity_projection_widget_from_mpr_data(data)

    def _get_subwindow_mpr_output_pixel_spacing(self, idx: int):
        """Return the (row, col) pixel spacing mm for the MPR output grid for subwindow *idx*."""
        try:
            data = self.subwindow_data.get(idx, {})
            if not data.get("is_mpr"):
                return None
            result = data.get("mpr_result")
            if result is None:
                return None
            return getattr(result, "output_spacing_mm", None)
        except Exception:
            return None

    def _on_save_mpr_as_dicom(self) -> None:
        """File → Save MPR as DICOM… — requires focused subwindow in MPR mode."""
        self._mpr_controller.prompt_save_mpr_as_dicom()

