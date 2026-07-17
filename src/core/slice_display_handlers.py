"""
Slice display, ROI display, and slice-change handlers.

These functions own the focused-subwindow slice display pipeline and the
slice-navigator ``on_slice_changed`` logic.  Extracted from ``main.py`` so
``DICOMViewerApp`` delegates rather than implementing the display path inline.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QTimer

from core.navigation_slider_state import navigation_slider_mode_label_for_dataset
from utils.dicom_utils import get_composite_series_key
from utils.log_sanitizer import sanitized_format_exc
from utils.privacy.console import print_redacted

_logger = logging.getLogger(__name__)


def _show_display_error(app: Any, title: str, message: str) -> None:
    """Delegate slice display errors to the injected app dialog handler when available."""
    file_dialog = getattr(app, "file_dialog", None)
    if file_dialog is not None and hasattr(file_dialog, "show_error"):
        file_dialog.show_error(app.main_window, title, message)


def display_slice(app: Any, dataset: Any, preserve_view_override: bool | None = None) -> None:
    """Display a DICOM slice in the focused subwindow."""
    try:
        app.current_dataset = dataset

        app.slice_display_manager.set_current_data_context(
            app.current_studies,
            app.current_study_uid,
            app.current_series_uid,
            app.current_slice_index,
        )

        app.slice_display_manager.display_slice(
            dataset,
            app.current_studies,
            app.current_study_uid,
            app.current_series_uid,
            app.current_slice_index,
            preserve_view_override=preserve_view_override,
        )

        display_rois_for_slice(app, dataset)

        app._update_series_navigator_highlighting()
        app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())

        if app.view_state_manager.initial_zoom is None:
            QTimer.singleShot(100, app.view_state_manager.store_initial_view_state)
    except MemoryError as e:
        error_msg = f"Memory error displaying slice: {e}"
        app.main_window.update_status(error_msg)
        _show_display_error(
            app,
            "Memory Error",
            f"{error_msg}\n\nTry closing other applications or use a system with more memory.",
        )
    except Exception as e:
        error_type = type(e).__name__
        error_msg = f"Error displaying slice: {e}"
        if error_type not in error_msg:
            error_msg = f"{error_type}: {error_msg}"
        app.main_window.update_status(error_msg)
        print_redacted(f"Error displaying slice: {error_msg}")
        _logger.debug("%s", sanitized_format_exc())


def redisplay_current_slice(app: Any, preserve_view: bool = True) -> None:
    """Redisplay the current slice via SliceDisplayManager with optional preserve_view override."""
    focused_idx = app.focused_subwindow_index
    if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(focused_idx):
        data = app.subwindow_data.get(focused_idx, {})
        app._mpr_controller.display_mpr_slice(focused_idx, data.get("mpr_slice_index", 0))
        return
    if app.current_dataset is not None:
        display_slice(app, app.current_dataset, preserve_view_override=preserve_view)


def display_rois_for_slice(app: Any, dataset: Any) -> None:
    """Display ROIs for a slice and update the statistics panel."""
    app.slice_display_manager.display_rois_for_slice(dataset)
    study_uid = getattr(dataset, "StudyInstanceUID", "")
    series_uid = get_composite_series_key(dataset)
    instance_identifier = app.current_slice_index
    rois = app.roi_manager.get_rois_for_slice(study_uid, series_uid, instance_identifier)
    selected_roi = app.roi_manager.get_selected_roi()
    if selected_roi is not None:
        selected_in_slice = selected_roi in rois
        if selected_in_slice:
            app.roi_list_panel.select_roi_in_list(selected_roi)
            app.roi_coordinator.update_roi_statistics(selected_roi)
        else:
            app.roi_statistics_panel.clear_statistics()
    else:
        app.roi_statistics_panel.clear_statistics()


def display_measurements_for_slice(app: Any, dataset: Any) -> None:
    """Display measurements for a slice."""
    app.slice_display_manager.display_measurements_for_slice(dataset)


def update_roi_list(app: Any) -> None:
    """Update ROI list panel for the focused subwindow's current slice."""
    if app.current_dataset is not None:
        study_uid = getattr(app.current_dataset, "StudyInstanceUID", "")
        series_uid = get_composite_series_key(app.current_dataset)
        instance_identifier = app.current_slice_index
        app.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)


def on_slice_changed(app: Any, slice_index: int) -> None:
    """Handle slice change from slice navigator (affects focused subwindow only)."""
    was_cine_advancing = app.cine_player.is_cine_advancing()

    focused_idx = app.focused_subwindow_index
    if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(focused_idx):
        app._mpr_controller.display_mpr_slice(focused_idx, slice_index)
        result = app.subwindow_data.get(focused_idx, {}).get("mpr_result")
        if result is not None:
            app.cine_controls_widget.update_frame_position(slice_index, result.n_slices)
            if app.image_viewer is not None:
                app.image_viewer.set_navigation_slider_state(
                    enabled=True,
                    minimum=1,
                    maximum=result.n_slices,
                    value=slice_index + 1,
                    mode_label="Slice",
                    reveal=True,
                )
        app._slice_sync_coordinator.on_slice_changed(focused_idx)
        app._slice_location_line_coordinator.refresh_all()
        if was_cine_advancing:
            QTimer.singleShot(0, app.cine_player.reset_cine_advancing_flag)
        return

    if focused_idx in app.subwindow_data and focused_idx in app.subwindow_managers:
        data = app.subwindow_data[focused_idx]
        managers = app.subwindow_managers[focused_idx]

        series_uid = data.get("current_series_uid", "")
        study_uid = data.get("current_study_uid", "")

        if not series_uid or not study_uid:
            return

        if study_uid not in app.current_studies or series_uid not in app.current_studies[study_uid]:
            return

        series_datasets = app.current_studies[study_uid][series_uid]
        if not series_datasets or slice_index < 0 or slice_index >= len(series_datasets):
            return

        data["current_slice_index"] = slice_index
        data["current_datasets"] = series_datasets
        data["current_dataset"] = series_datasets[slice_index]

        app.current_slice_index = slice_index
        app.current_dataset = series_datasets[slice_index]

        slice_display_manager = managers["slice_display_manager"]
        slice_display_manager.display_slice(
            series_datasets[slice_index],
            app.current_studies,
            study_uid,
            series_uid,
            slice_index,
        )

        app._update_series_navigator_highlighting()
        app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())

        app._update_about_this_file_dialog()

        if managers.get("crosshair_coordinator"):
            managers["crosshair_coordinator"].update_crosshairs_for_slice()

        total_slices = len(series_datasets)
        if total_slices > 0:
            app.cine_controls_widget.update_frame_position(slice_index, total_slices)

        if app.image_viewer is not None and total_slices > 0:
            app.image_viewer.set_navigation_slider_state(
                enabled=True,
                minimum=1,
                maximum=total_slices,
                value=slice_index + 1,
                mode_label=navigation_slider_mode_label_for_dataset(series_datasets[slice_index]),
                reveal=True,
            )

    if was_cine_advancing:
        QTimer.singleShot(0, app.cine_player.reset_cine_advancing_flag)

    app._slice_sync_coordinator.on_slice_changed(app.focused_subwindow_index)
    app._slice_location_line_coordinator.refresh_all()
