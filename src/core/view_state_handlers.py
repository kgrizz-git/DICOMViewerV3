"""
View-state, rescale, zoom, and status-bar handlers.

These functions handle rescale toggles, view resets, zoom/transform changes,
pixel-info updates, and zoom/preset status-bar formatting.  Extracted from
``main.py`` to reduce its coordination burden.
"""

from __future__ import annotations

from typing import Any

from utils.dicom_utils import get_composite_series_key


def on_rescale_toggle_changed(app: Any, checked: bool) -> None:
    """Handle rescale toggle change from toolbar or context menu."""
    app.view_state_manager.handle_rescale_toggle(checked)
    selected_roi = app.roi_manager.get_selected_roi()
    if selected_roi is not None and app.current_dataset is not None:
        study_uid = getattr(app.current_dataset, "StudyInstanceUID", "")
        series_uid = get_composite_series_key(app.current_dataset)
        instance_identifier = app.current_slice_index
        current_slice_rois = app.roi_manager.get_rois_for_slice(
            study_uid, series_uid, instance_identifier
        )
        if selected_roi in current_slice_rois:
            app.roi_coordinator.update_roi_statistics(selected_roi)
        else:
            app.roi_statistics_panel.clear_statistics()
    else:
        app.roi_statistics_panel.clear_statistics()

    if hasattr(app, "dialog_coordinator"):
        app.dialog_coordinator.update_histogram_for_subwindow(app.focused_subwindow_index)


def on_reset_all_views(app: Any) -> None:
    """Reset view for all subwindows in the layout."""
    for idx in app.subwindow_managers:
        managers = app.subwindow_managers[idx]
        view_state_manager = managers.get("view_state_manager")
        slice_display_manager = managers.get("slice_display_manager")

        if view_state_manager and view_state_manager.current_dataset is not None:
            view_state_manager.reset_view(skip_redisplay=True)

            if idx in app.subwindow_data:
                data = app.subwindow_data[idx]
                dataset = app._get_subwindow_dataset(idx)
                if dataset is None:
                    dataset = data.get("current_dataset")
                if dataset is not None and slice_display_manager is not None:
                    slice_display_manager.display_slice(
                        dataset,
                        app.current_studies,
                        data.get("current_study_uid", ""),
                        data.get("current_series_uid", ""),
                        data.get("current_slice_index", 0),
                        preserve_view_override=False,
                    )


def on_zoom_changed(app: Any, zoom_level: float) -> None:
    """Handle zoom level change."""
    app.view_state_manager.handle_zoom_changed(zoom_level)
    app.measurement_tool.update_all_measurement_text_offsets()
    update_zoom_preset_status_bar(app)


def on_transform_changed(app: Any) -> None:
    """Handle view transform change (zoom/pan)."""
    app.view_state_manager.handle_transform_changed()
    app.measurement_tool.update_all_measurement_text_offsets()


def on_viewport_resizing(app: Any) -> None:
    """Handle viewport resize start (when splitter starts moving)."""
    app.view_state_manager.handle_viewport_resizing()


def on_viewport_resized(app: Any) -> None:
    """Handle viewport resize (when splitter moves)."""
    app.view_state_manager.handle_viewport_resized()


def on_pixel_info_changed(app: Any, pixel_value_str: str, x: int, y: int, z: int) -> None:
    """Handle pixel info changed signal from image viewer."""
    if pixel_value_str:
        info_text = f"Pixel: {pixel_value_str}  (x: {x}, y: {y}, z: {z})"
    else:
        info_text = f"(x: {x}, y: {y}, z: {z})" if (x > 0 or y > 0 or z > 0) else ""

    if hasattr(app.main_window, "pixel_info_label"):
        app.main_window.pixel_info_label.setText(info_text)


def update_zoom_preset_status_bar(app: Any) -> None:
    """Update the zoom and current W/L values in the center status-bar segment."""
    current_zoom = app.image_viewer.current_zoom if app.image_viewer is not None else 1.0
    center, width = app.window_level_controls.get_window_level()
    unit = app.window_level_controls.unit
    app.main_window.update_zoom_preset_status(
        current_zoom, center, width, unit=unit
    )


def update_zoom_wl_status_from_view_state(vsm: Any) -> None:
    """Push focused pane W/L from a ViewStateManager to the status bar."""
    current_zoom = vsm.image_viewer.current_zoom if vsm.image_viewer is not None else 1.0
    center = vsm.current_window_center
    width = vsm.current_window_width
    if center is None or width is None:
        center, width = vsm.window_level_controls.get_window_level()
    unit = vsm.window_level_controls.unit
    vsm.main_window.update_zoom_preset_status(
        current_zoom, center, width, unit=unit
    )
