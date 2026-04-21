"""
Session-wide teardown: clear ROIs/measurements, close all files, and quit-time cleanup.

Bodies moved from ``DICOMViewerApp._clear_data``, ``_close_files``, and
``_on_app_about_to_quit`` so ``main.py`` stays smaller. Callers keep stable
``DICOMViewerApp`` method names that delegate here.

Inputs:
    ``app``: ``DICOMViewerApp`` instance (full composition root).

Outputs:
    Mutates ``app`` and shared widgets; stops cine; clears studies and subwindow state.

Requirements:
    PySide6; no runtime ``import main`` (``TYPE_CHECKING`` only).
"""

from __future__ import annotations

# pyright: reportImportCycles=false

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from main import DICOMViewerApp


def clear_data(app: "DICOMViewerApp") -> None:
    """Clear all ROIs, measurements, and related data for all subwindows."""
    # Clear slice_display_manager state for all subwindows so no stale cached state
    # is used when opening new folder/files (e.g. by refresh_overlays on privacy toggle).
    for idx in app.subwindow_managers:
        managers = app.subwindow_managers[idx]
        slice_display_manager = managers.get("slice_display_manager")
        if slice_display_manager and hasattr(slice_display_manager, "clear_display_state"):
            slice_display_manager.clear_display_state()
    # Clear data for ALL subwindows, not just focused one
    subwindows = app.multi_window_layout.get_all_subwindows()
    for idx, subwindow in enumerate(subwindows):
        if subwindow and subwindow.image_viewer and subwindow.image_viewer.scene:
            # Get the managers for this subwindow
            if idx in app.subwindow_managers:
                managers = app.subwindow_managers[idx]
                roi_manager = managers.get("roi_manager")
                measurement_tool = managers.get("measurement_tool")
                text_annotation_tool = managers.get("text_annotation_tool")
                arrow_annotation_tool = managers.get("arrow_annotation_tool")
                if roi_manager:
                    roi_manager.clear_all_rois(subwindow.image_viewer.scene)
                if measurement_tool:
                    measurement_tool.clear_measurements(subwindow.image_viewer.scene)
                if text_annotation_tool:
                    text_annotation_tool.clear_annotations(subwindow.image_viewer.scene)
                if arrow_annotation_tool:
                    arrow_annotation_tool.clear_arrows(subwindow.image_viewer.scene)

    # Update shared panels (these show focused subwindow's data)
    app.roi_list_panel.update_roi_list("", "", 0)  # Clear list
    app.roi_statistics_panel.clear_statistics()


def close_all_files(app: "DICOMViewerApp") -> None:
    """Close currently open files/folder and clear all data."""
    # Clear MPR from any subwindow before clearing overlays and data.
    # This removes the MPR banner and restores or clears the view.
    if hasattr(app, "_mpr_controller"):
        for idx in list(app.subwindow_data.keys()):
            if app.subwindow_data.get(idx, {}).get("is_mpr"):
                app._mpr_controller.clear_mpr(idx)

    # Clear all ROIs, measurements, and related data for all subwindows
    clear_data(app)

    # Clear image viewers for ALL subwindows
    subwindows = app.multi_window_layout.get_all_subwindows()
    for subwindow in subwindows:
        if subwindow and subwindow.image_viewer:
            # Clear scene
            subwindow.image_viewer.scene.clear()
            subwindow.image_viewer.image_item = None
            # Force viewport update to ensure cleared scene is visible
            subwindow.image_viewer.viewport().update()

    # Clear overlay items for all subwindows (including viewport corner overlays)
    for idx in app.subwindow_managers:
        managers = app.subwindow_managers[idx]
        overlay_manager = managers.get("overlay_manager")
        if overlay_manager:
            # Get the scene from the corresponding subwindow to properly clear overlays
            if idx < len(subwindows) and subwindows[idx] and subwindows[idx].image_viewer:
                scene = subwindows[idx].image_viewer.scene
                overlay_manager.clear_overlay_items(scene)
            else:
                # Fallback: just clear the items list if scene not available
                overlay_manager.overlay_items.clear()

    # Reset fusion for all subwindows (disable fusion, clear status, clear caches)
    # This is called when opening new files to ensure fusion is disabled
    app._reset_fusion_for_all_subwindows()

    # Clear metadata panel (shared)
    app.metadata_panel.set_dataset(None)

    # Reset view state and clear display state for all subwindows
    for idx in app.subwindow_managers:
        managers = app.subwindow_managers[idx]
        view_state_manager = managers.get("view_state_manager")
        slice_display_manager = managers.get("slice_display_manager")
        if view_state_manager:
            view_state_manager.reset_window_level_state()
            view_state_manager.reset_series_tracking()
        if slice_display_manager and hasattr(slice_display_manager, "clear_display_state"):
            slice_display_manager.clear_display_state()

    # Update shared widget state
    app.intensity_projection_controls_widget.set_enabled(False)
    app.intensity_projection_controls_widget.set_projection_type("aip")
    app.intensity_projection_controls_widget.set_slice_count(4)

    # Clear all subwindow data structures
    app.subwindow_data.clear()

    # Clear cached pixel arrays from datasets to free memory (before clearing studies dict)
    if app.current_studies:
        for study_uid, series_dict in app.current_studies.items():
            for series_uid, datasets in series_dict.items():
                for dataset in datasets:
                    # Remove cached pixel arrays if they exist
                    if hasattr(dataset, "_cached_pixel_array"):
                        delattr(dataset, "_cached_pixel_array")

    # Reset organizer state (loaded_file_paths, series_source_dirs, disambiguation_counters, etc.)
    app.dicom_organizer.clear()
    # Clear all PS/KO from annotation manager (studies gone)
    app.annotation_manager.clear_all_ps_ko()

    # Clear current dataset references (legacy, points to focused subwindow)
    app.current_dataset = None
    app.current_studies = {}
    app.current_study_uid = ""
    app.current_series_uid = ""
    app.current_slice_index = 0

    app._schedule_tag_export_union_rebuild()

    # Dissolve slice sync groups (no linked groups when no files loaded)
    app.config_manager.set_slice_sync_groups([])
    app._slice_sync_coordinator.set_groups([])
    app._slice_sync_coordinator.invalidate_cache()
    app._slice_location_line_coordinator.refresh_all()

    # Reset slice navigator (shared)
    app.slice_navigator.set_total_slices(0)
    app.slice_navigator.set_current_slice(0)

    # Clear series navigator (shared) and dot indicators
    app.series_navigator.update_series_list({}, "", "")
    app._refresh_series_navigator_state()
    app.series_navigator.set_subwindow_assignments({})

    # Clear tag edit history
    if hasattr(app, "metadata_controller") and app.metadata_controller:
        app.metadata_controller.clear_tag_history()

    # Reset undo/redo state
    app._update_undo_redo_state()

    # Stop cine player if active (prevents timer leaks)
    if hasattr(app, "cine_player") and app.cine_player:
        app.cine_player.stop_playback()

    # Clear tag viewer filter
    if app.dialog_coordinator:
        app.dialog_coordinator.clear_tag_viewer_filter()

    # Update status
    app.main_window.update_status("Ready")

    # Reassign views A–D to default windows 1–4 (slot order [0,1,2,3])
    app.multi_window_layout.reset_slot_to_view_default()
    app._refresh_window_slot_map_widgets()


def finalize_for_application_quit(app: "DICOMViewerApp") -> None:
    """Reset view–slot mapping and dissolve slice sync groups when the application is exiting."""
    app._drain_tag_export_union_worker(timeout_sec=30.0)
    app.multi_window_layout.reset_slot_to_view_default()
    app.config_manager.set_slice_sync_groups([])
    app._slice_sync_coordinator.set_groups([])
    app._slice_sync_coordinator.invalidate_cache()
