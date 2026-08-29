"""
DICOMViewerApp UI signal handlers and file operations mixin module.

Owns UI signal slot handlers (focus, layout, privacy toggles, etc.) and file
open/save/recent operations for ``DICOMViewerApp`` (see MAIN_PY_REFACTOR_PLAN Appendix A).
Methods extracted from ``main.py`` in Phase 5.
"""

from __future__ import annotations

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportUninitializedInstanceVariable=false
from typing import Any

from pydicom.dataset import Dataset

from core.actions import customization_actions
from core.overlay_settings_handlers import on_annotation_options_applied
from core.study_navigation_handlers import update_3d_view_action_state
from core.view_state_handlers import (
    on_pixel_info_changed,
    on_rescale_toggle_changed,
    on_reset_all_views,
    on_transform_changed,
    on_viewport_resized,
    on_viewport_resizing,
)
from gui.actions import dialog_actions, view_actions
from gui.file_series_loading_coordinator import show_cancelled_index_skip_toast
from gui.layout_window_slot_controller import (
    on_window_slot_map_cell_clicked as layout_on_window_slot_map_cell_clicked,
)
from gui.layout_window_slot_controller import (
    on_window_slot_map_popup_requested as layout_on_window_slot_map_popup_requested,
)
from gui.study_index_consent import (
    StudyIndexOpenChoice,
    prompt_study_index_first_open,
)
from gui.sub_window_container import SubWindowContainer
from gui.tag_export_union_host import StudiesNestedDict
from qa.analysis_types import (
    MRIBatchResult,
    MRICompareRequest,
    QARequest,
    QAResult,
)


class UIHandlersMixin:
    """
    Mixin: UI signal handlers for focus, layout changes, privacy view, and related
    main-window events on ``DICOMViewerApp``.
    """

    def _set_mouse_mode_via_handler(self, mode: str) -> None:
        """Set mouse mode via mouse mode handler."""
        self.mouse_mode_handler.set_mouse_mode(mode)

    def _on_undo_requested(self) -> None:
        """Handle undo request (unified for all operations)."""
        if self.undo_redo_manager and self.undo_redo_manager.can_undo():
            success = self.undo_redo_manager.undo()
            if success:
                # Update UI after undo
                self._update_undo_redo_state()
                # Refresh ROI list and statistics
                self._update_roi_list()
                # Update crosshair visibility if needed
                if hasattr(self, 'crosshair_coordinator') and self.crosshair_coordinator:
                    self.crosshair_coordinator.update_crosshairs_for_slice()

    def _on_redo_requested(self) -> None:
        """Handle redo request (unified for all operations)."""
        if self.undo_redo_manager and self.undo_redo_manager.can_redo():
            success = self.undo_redo_manager.redo()
            if success:
                # Update UI after redo
                self._update_undo_redo_state()
                # Refresh ROI list and statistics
                self._update_roi_list()
                # Update crosshair visibility if needed
                if hasattr(self, 'crosshair_coordinator') and self.crosshair_coordinator:
                    self.crosshair_coordinator.update_crosshairs_for_slice()

    def _update_3d_view_action_state(self) -> None:
        """Enable toolbar/menu 3D actions when the focused series can volume-render."""
        update_3d_view_action_state(self)

    def _on_window_slot_map_cell_clicked(self, slot: int) -> None:
        """Focus the subwindow in grid slot *slot* (0–3); 1×2 / 2×1 re-arrange via layout."""
        layout_on_window_slot_map_cell_clicked(self, slot)

    def _on_window_slot_map_popup_requested(self) -> None:
        """Show or hide a small popup with the window-slot map near the cursor (toggle)."""
        layout_on_window_slot_map_popup_requested(self)

    def _on_assign_series_requested(
        self, series_uid: str, slice_index: int, study_uid: str = ""
    ) -> None:
        """Handle series assignment request from subwindow; sender() identifies which subwindow."""
        sender = self.sender()
        if isinstance(sender, SubWindowContainer):
            target_study = study_uid if study_uid else None
            self._subwindow_lifecycle_controller.assign_series_to_subwindow(
                sender, series_uid, slice_index, target_study_uid=target_study
            )

    def _on_series_navigation_requested(self, direction: int) -> None:
        """
        Handle series navigation request from image viewer (focused subwindow only).
        Delegates to file/series loading coordinator.
        """
        self._file_series_coordinator.on_series_navigation_requested(direction)

    def _on_assign_series_from_context_menu(self, series_uid: str) -> None:
        """Handle series assignment request from context menu. Delegates to coordinator."""
        self._file_series_coordinator.on_assign_series_from_context_menu(series_uid)

    def _on_study_index_after_load(
        self,
        datasets,
        _studies,
        merge_result,
        source_dir,
        merge_paths,
        *,
        was_cancelled: bool = False,
    ) -> None:
        """Record opened files in the local study index when enabled in settings."""
        force_index = False
        if was_cancelled:
            show_cancelled_index_skip_toast(self)
        elif (
            self.study_index_service.is_backend_available()
            and self.config_manager.needs_study_index_auto_add_consent()
        ):
            choice = prompt_study_index_first_open(
                self.config_manager,
                self.main_window,
            )
            # "Add this one time" indexes this batch without recording consent.
            force_index = choice is StudyIndexOpenChoice.ADD_ONCE
        self.study_index_service.schedule_index_after_load(
            datasets,
            merge_paths,
            source_dir,
            merge_result,
            was_cancelled=was_cancelled,
            force=force_index,
        )

    def _on_show_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Handle 'Show file' request from series navigator thumbnail. Delegates to coordinator."""
        self._file_series_coordinator.on_show_file_from_series(study_uid, series_uid)

    def _on_slice_location_lines_toggled(self, visible: bool) -> None:
        """Handle View → Show Slice Location Lines → Enable/Disable toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_location_lines_toggled(self, visible)

    def _on_slice_location_lines_same_group_only_toggled(self, same_group_only: bool) -> None:
        """Handle slice location lines same-group-only toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_location_lines_same_group_only_toggled(self, same_group_only)

    def _on_slice_location_lines_focused_only_toggled(self, focused_only: bool) -> None:
        """Handle slice location lines focused-only toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_location_lines_focused_only_toggled(self, focused_only)

    def _on_slice_location_lines_mode_toggled(self, mode: str) -> None:
        """Handle View → Show Slice Location Lines → slab mode toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_location_lines_mode_toggled(self, mode)

    def _on_orientation_flip_h(self) -> None:
        """Toggle horizontal flip on the currently focused image viewer."""
        view_actions.on_orientation_flip_h(self)

    def _on_orientation_flip_v(self) -> None:
        """Toggle vertical flip on the currently focused image viewer."""
        view_actions.on_orientation_flip_v(self)

    def _on_orientation_rotate_cw(self) -> None:
        """Rotate the currently focused image viewer 90° clockwise."""
        view_actions.on_orientation_rotate_cw(self)

    def _on_orientation_rotate_ccw(self) -> None:
        """Rotate the currently focused image viewer 90° counter-clockwise."""
        view_actions.on_orientation_rotate_ccw(self)

    def _on_orientation_rotate_180(self) -> None:
        """Rotate the currently focused image viewer 180°."""
        view_actions.on_orientation_rotate_180(self)

    def _on_orientation_reset(self) -> None:
        """Reset orientation of the currently focused image viewer to default."""
        view_actions.on_orientation_reset(self)

    def _on_scale_markers_toggled(self, enabled: bool) -> None:
        """Handle scale markers toggle. Delegates to ``view_actions``."""
        view_actions.on_scale_markers_toggled(self, enabled)

    def _on_direction_labels_toggled(self, enabled: bool) -> None:
        """Handle direction labels toggle. Delegates to ``view_actions``."""
        view_actions.on_direction_labels_toggled(self, enabled)

    def _on_slice_slider_toggled(self, enabled: bool) -> None:
        """Handle the in-view slice/frame slider toggle. Delegates to ``view_actions``."""
        view_actions.on_slice_slider_toggled(self, enabled)

    def _on_slice_slider_placement_changed(self, placement: str) -> None:
        """Handle the in-view slice/frame slider placement. Delegates to ``view_actions``."""
        view_actions.on_slice_slider_placement_changed(self, placement)

    def _on_slice_slider_direction_changed(self, direction: str) -> None:
        """Handle the in-view slice/frame slider direction. Delegates to ``view_actions``."""
        view_actions.on_slice_slider_direction_changed(self, direction)

    def _on_scale_markers_color_changed(self, r: int, g: int, b: int) -> None:
        """Handle scale markers color change from the View menu."""
        view_actions.on_scale_markers_color_changed(self, r, g, b)

    def _on_direction_labels_color_changed(self, r: int, g: int, b: int) -> None:
        """Handle direction labels color change from the View menu."""
        view_actions.on_direction_labels_color_changed(self, r, g, b)

    def _on_show_instances_separately_toggled(self, enabled: bool) -> None:
        """Handle the View → Show Instances Separately toggle."""
        view_actions.on_show_instances_separately_toggled(self, enabled)

    def _on_keyboard_shortcuts_requested(self) -> None:
        """Handle Keyboard Shortcuts dialog request (Help menu / F1)."""
        from gui.dialogs.keyboard_shortcuts_dialog import KeyboardShortcutsDialog
        dlg = KeyboardShortcutsDialog(self.main_window)
        dlg.exec()

    def _qa_build_preflight_warnings(
        self,
        expected_modality: str,
        use_focused: bool,
        folder_path: str | None,
        datasets: list[Dataset],
        modality: str,
    ) -> list[str]:
        """Collect Stage 1c preflight warnings. Delegates to ``QAAppFacade``."""
        return self._qa_app_facade.build_preflight_warnings(
            expected_modality, use_focused, folder_path, datasets, modality
        )

    def _qa_user_confirms_preflight(self, warnings: list[str]) -> bool:
        """If warnings exist, show them and return True only if the user continues."""
        return self._qa_app_facade.user_confirms_preflight(warnings)

    def _show_qa_result_dialog(self, title: str, result: QAResult) -> None:
        """Show a compact final status dialog for Stage 1 QA runs."""
        self._qa_app_facade.show_qa_result_dialog(title, result)

    def _export_qa_json(
        self,
        result: QAResult,
        default_stem: str,
        inputs: dict[str, Any] | None = None,
    ) -> None:
        """Offer JSON export for a finished Stage 1 QA run."""
        self._qa_app_facade.export_qa_json(result, default_stem, inputs)

    def _qa_offer_extent_retry(
        self,
        request: QARequest,
        json_inputs: dict[str, Any] | None,
        *,
        progress_title: str,
        progress_label: str,
        result_dialog_title: str,
        json_default_stem: str,
    ) -> None:
        """After a strict scan-extent failure, offer a relaxed retry (one tier)."""
        self._qa_app_facade.offer_extent_retry(
            request,
            json_inputs,
            progress_title=progress_title,
            progress_label=progress_label,
            result_dialog_title=result_dialog_title,
            json_default_stem=json_default_stem,
        )

    def _start_qa_worker(
        self,
        request: QARequest,
        *,
        progress_title: str,
        progress_label: str,
        result_dialog_title: str,
        json_default_stem: str,
        json_inputs: dict[str, Any] | None = None,
        allow_extent_retry: bool = True,
    ) -> None:
        """Show progress, run QA in a background thread, then summary + JSON export."""
        self._qa_app_facade.start_qa_worker(
            request,
            progress_title=progress_title,
            progress_label=progress_label,
            result_dialog_title=result_dialog_title,
            json_default_stem=json_default_stem,
            json_inputs=json_inputs,
            allow_extent_retry=allow_extent_retry,
        )

    def _start_mri_batch_worker(
        self,
        base_request: QARequest,
        compare_request: MRICompareRequest,
        *,
        json_inputs: dict[str, Any] | None,
    ) -> None:
        """Launch compare-mode MRI batch analysis. Delegates to ``QAAppFacade``."""
        self._qa_app_facade.start_mri_batch_worker(
            base_request, compare_request, json_inputs=json_inputs
        )

    def _note_mri_compare_dialog_closed(self, *_args: Any) -> None:
        """Clear compare-results dialog reference after WA_DeleteOnClose."""
        self._qa_app_facade.note_mri_compare_dialog_closed(*_args)

    def _show_mri_compare_result_dialog(
        self,
        batch: MRIBatchResult,
        *,
        json_inputs: dict[str, Any] | None = None,
    ) -> None:
        """Show ACR MRI compare results. Delegates to ``QAAppFacade``."""
        self._qa_app_facade.show_mri_compare_result_dialog(batch, json_inputs=json_inputs)

    def _export_mri_compare_json(
        self,
        batch: MRIBatchResult,
        inputs: dict[str, Any] | None = None,
    ) -> None:
        """Offer JSON export for a finished compare-mode MRI batch. Delegates to ``QAAppFacade``."""
        self._qa_app_facade.export_mri_compare_json(batch, inputs)

    def _on_export_customizations(self) -> None:
        """Handle Export Customizations request."""
        customization_actions.on_export_customizations(self)

    def _on_import_customizations(self) -> None:
        """Handle Import Customizations request."""
        customization_actions.on_import_customizations(self)

    def _on_annotation_options_applied(self) -> None:
        """Handle annotation options applied - refresh all annotations."""
        on_annotation_options_applied(self)

    def _on_window_changed(self, center: float, width: float) -> None:
        """
        Handle window/level change.
        
        Args:
            center: Window center
            width: Window width
        """
        self.view_state_manager.handle_window_changed(center, width)

    def _on_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change from toolbar.
        
        Args:
            mode: Mouse mode
        """
        self.mouse_mode_handler.handle_mouse_mode_changed(mode)

    def _set_mouse_mode(self, mode: str) -> None:
        """
        Set mouse mode programmatically (e.g., from keyboard shortcuts).
        
        Args:
            mode: Mouse mode
        """
        self.mouse_mode_handler.set_mouse_mode(mode)

    def _on_scroll_wheel_mode_changed(self, mode: str) -> None:
        """
        Handle scroll wheel mode change.
        
        Args:
            mode: "slice" or "zoom"
        """
        self.mouse_mode_handler.handle_scroll_wheel_mode_changed(mode)
        # Also update all subwindows to make scroll wheel mode global
        subwindows = self.multi_window_layout.get_all_subwindows()
        for subwindow in subwindows:
            if subwindow:
                subwindow.image_viewer.set_scroll_wheel_mode(mode)

    def _on_context_menu_mouse_mode_changed(self, mode: str) -> None:
        """
        Handle mouse mode change from context menu.
        
        Args:
            mode: Mouse mode string
        """
        self.mouse_mode_handler.handle_context_menu_mouse_mode_changed(mode)

    def _on_context_menu_scroll_wheel_mode_changed(self, mode: str) -> None:
        """
        Handle scroll wheel mode change from context menu.
        
        Args:
            mode: "slice" or "zoom"
        """
        self.mouse_mode_handler.handle_context_menu_scroll_wheel_mode_changed(mode)

    def _on_rescale_toggle_changed(self, checked: bool) -> None:
        """Handle rescale toggle change from toolbar or context menu."""
        on_rescale_toggle_changed(self, checked)

    def _on_reset_all_views(self) -> None:
        """Reset view for all subwindows in the layout."""
        on_reset_all_views(self)

    def _on_transform_changed(self) -> None:
        """Handle view transform change (zoom/pan)."""
        on_transform_changed(self)

    def _on_viewport_resizing(self) -> None:
        """Handle viewport resize start (when splitter starts moving)."""
        on_viewport_resizing(self)

    def _on_viewport_resized(self) -> None:
        """Handle viewport resize (when splitter moves)."""
        on_viewport_resized(self)

    def _on_pixel_info_changed(self, pixel_value_str: str, x: int, y: int, z: int) -> None:
        """Handle pixel info changed signal from image viewer."""
        on_pixel_info_changed(self, pixel_value_str, x, y, z)

    def _on_arrow_key_pressed(self, direction: int) -> None:
        """
        Handle arrow key press from image viewer.
        
        Args:
            direction: 1 for up (next slice), -1 for down (previous slice)
        """
        self.slice_display_manager.handle_arrow_key_pressed(direction)


class FileOperationsMixin:
    """
    Mixin: file open/save/recent and related dialog/export entry points for
    ``DICOMViewerApp``.
    """

    def _open_wl_preset_manager(self) -> None:
        """Open Manage W/L Presets dialog."""
        dialog_actions.open_wl_preset_manager(self)

    def _open_files(self) -> None:
        """Handle open files request. Delegates to ``dialog_actions.open_files``."""
        dialog_actions.open_files(self)

    def _open_folder(self) -> None:
        """Handle open folder request. Delegates to ``dialog_actions.open_folder``."""
        dialog_actions.open_folder(self)

    def _open_recent_file(self, file_path: str) -> None:
        """Handle open recent file/folder request. Delegates to ``dialog_actions.open_recent_file``."""
        dialog_actions.open_recent_file(self, file_path)

    def _open_files_from_paths(self, paths: list[str]) -> None:
        """Handle open files/folders from drag-and-drop. Delegates to ``dialog_actions.open_files_from_paths``."""
        dialog_actions.open_files_from_paths(self, paths)

    def _build_flat_series_list(self, studies: StudiesNestedDict) -> list[tuple[int, str, str, Dataset]]:
        """Build flat list of all series from all studies in navigator display order. Delegates to coordinator."""
        return self._file_series_coordinator.build_flat_series_list(studies)

    def _open_settings(self) -> None:
        """Handle settings dialog request. Delegates to ``dialog_actions.open_settings``."""
        dialog_actions.open_settings(self)

    def _open_study_index_search(self) -> None:
        """Open the local study index browser (File menu and Tools menu)."""
        dialog_actions.open_study_index_search(self)

    def _open_overlay_settings(self) -> None:
        """Handle Overlay Settings dialog request. Delegates to ``dialog_actions.open_overlay_settings``."""
        dialog_actions.open_overlay_settings(self)

    def _open_about_this_file(self) -> None:
        """Handle About This File dialog request."""
        dialog_actions.open_about_this_file(self)

    def _get_file_path_for_dataset(self, dataset, study_uid: str, series_uid: str, slice_index: int) -> str | None:
        """Get file path for a dataset. Delegates to file/series loading coordinator."""
        return self._file_series_coordinator.get_file_path_for_dataset(dataset, study_uid, series_uid, slice_index)

    def _on_about_this_file_from_series(self, study_uid: str, series_uid: str) -> None:
        """Handle 'About This File' request from series navigator thumbnail. Delegates to coordinator."""
        self._file_series_coordinator.on_about_this_file_from_series(study_uid, series_uid)

    def _get_current_slice_file_path(self, subwindow_idx: int | None = None) -> str | None:
        """Get file path for the currently displayed slice in a subwindow. Delegates to coordinator."""
        return self._file_series_coordinator.get_current_slice_file_path(subwindow_idx)

    def _update_about_this_file_dialog(self) -> None:
        """Update About This File dialog with current dataset and file path. Delegates to coordinator."""
        self._file_series_coordinator.update_about_this_file_dialog()

    def _open_slice_sync_dialog(self) -> None:
        """Open the Manage Sync Groups dialog."""
        dialog_actions.open_slice_sync_dialog(self)

    def _open_overlay_config(self) -> None:
        """Handle overlay configuration dialog request."""
        dialog_actions.open_overlay_config(self)

    def _open_annotation_options(self) -> None:
        """Handle annotation options dialog request."""
        dialog_actions.open_annotation_options(self)

    def _open_quick_window_level(self) -> None:
        """Open Quick Window/Level dialog for the focused subwindow."""
        dialog_actions.open_quick_window_level(self)

    def _open_quick_start_guide(self) -> None:
        """Handle Quick Start Guide dialog request."""
        dialog_actions.open_quick_start_guide(self)

    def _open_user_documentation_in_browser(self) -> None:
        """Open the user guide hub (Markdown on GitHub) in the system browser."""
        dialog_actions.open_user_documentation_in_browser(self)

    def _open_fusion_technical_doc(self) -> None:
        """Handle Fusion Technical Documentation dialog request."""
        dialog_actions.open_fusion_technical_doc(self)

    def _open_export(self) -> None:
        """Handle Export dialog request. Resolution options are in the dialog."""
        self._export_app_facade.open_export()

    def _open_deep_anonymizer_export(self) -> None:
        """Handle File → Export with Deep Anonymization… request."""
        self._export_app_facade.open_deep_anonymizer_export()

    def _open_export_screenshots(self) -> None:
        """Handle Export Screenshots dialog request. One file per selected subwindow."""
        self._export_app_facade.open_export_screenshots()

    def _open_structured_report_browser(self, subwindow_idx: int | None = None) -> None:
        """
        Tools → Structured Report… — open the SR document browser for the focused pane's
        current dataset when it is a Structured Report (SR storage class or Modality SR).
        """
        dialog_actions.open_structured_report_browser(self, subwindow_idx)

    def _on_export_cine_video(self) -> None:
        """
        File → Export Cine As… — GIF / AVI / MP4 / MPG for the focused 2D multi-frame pane.

        Delegates to ``dialog_actions.open_export_cine_video`` (same PIL render path and
        threaded encode as before).
        """
        dialog_actions.open_export_cine_video(self)

    def _resolve_focused_series_ordered_paths(
        self,
    ) -> tuple[str, str, str, list[str], list[Dataset]]:
        """
        Resolve focused-subwindow series identity and ordered source file paths.

        Returns:
            Tuple of (study_uid, series_uid, modality, ordered_file_paths, datasets).
        """
        return self._export_app_facade.resolve_focused_series_ordered_paths()

    def _prompt_save_path(
        self,
        title: str,
        default_name: str,
        filter_text: str,
        *,
        remember_pylinac_output_dir: bool = False,
    ) -> str:
        """Open a Save dialog that appears on top initially and return selected path."""
        return self._export_app_facade.prompt_save_path(
            title,
            default_name,
            filter_text,
            remember_pylinac_output_dir=remember_pylinac_output_dir,
        )

    def _open_acr_ct_phantom_analysis(self) -> None:
        """Open the Stage 1 ACR CT (pylinac) analysis flow (menu / signal slot)."""
        dialog_actions.open_acr_ct_phantom_analysis(self)

    def _open_acr_ct_batch_analysis(self) -> None:
        """Open the batch ACR CT (pylinac) analysis flow (menu / signal slot)."""
        dialog_actions.open_acr_ct_batch_analysis(self)

    def _open_acr_mri_phantom_analysis(self) -> None:
        """Open the Stage 1 ACR MRI Large (pylinac) analysis flow (menu / signal slot)."""
        dialog_actions.open_acr_mri_phantom_analysis(self)

    def _open_acr_mri_batch_analysis(self) -> None:
        """Open the multi-series ACR MRI Large (pylinac) batch flow (menu / signal slot)."""
        dialog_actions.open_acr_mri_batch_analysis(self)

    def _open_nuclear_qc_analysis(self) -> None:
        """Open the nuclear-medicine QC (pylinac.nuclear) flow (menu / signal slot)."""
        dialog_actions.open_nuclear_qc_analysis(self)

    def _open_path_in_system_viewer(self, path: str) -> None:
        """Open a file path with the OS default application (PDF viewer, etc.)."""
        dialog_actions.open_path_in_system_viewer(self, path)

    def _on_right_mouse_press_for_drag(self) -> None:
        """
        Handle right mouse press for drag - provide window/level values to image viewer.
        """
        self.view_state_manager.handle_right_mouse_press_for_drag()

    def _on_window_level_drag_changed(self, center_delta: float, width_delta: float) -> None:
        """
        Handle window/level drag adjustment from image viewer.
        
        Args:
            center_delta: Change in window center
            width_delta: Change in window width
        """
        self.view_state_manager.handle_window_level_drag(center_delta, width_delta)

