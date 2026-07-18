"""
Subwindow signal connect / disconnect helpers.

Extracted from ``SubwindowLifecycleController`` so the controller can focus on
lifecycle orchestration (focus changes, layout transitions, panel updates)
while this module owns the verbose connect/disconnect boilerplate.

Every public function receives the controller instance (``ctrl``) and reaches
the app via ``ctrl.app``.
"""

from __future__ import annotations

import warnings
from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import Qt

_WARN_FILTER_ACTION = "ignore"
_WARN_DISCONNECT_MSG = ".*Failed to disconnect.*"

# ---------------------------------------------------------------------------
# Module-level utility
# ---------------------------------------------------------------------------

def _connect_unique(signal: Any, slot: Any) -> None:
    """Connect a Qt signal once by removing the same slot before reconnecting."""
    with warnings.catch_warnings():
        warnings.simplefilter(_WARN_FILTER_ACTION, RuntimeWarning)
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError):
            pass
    signal.connect(slot)


# ---------------------------------------------------------------------------
# Callback injection
# ---------------------------------------------------------------------------

def wire_pixel_info_callbacks_for_subwindow(
    ctrl: Any, image_viewer: Any, idx: int
) -> None:
    """Bind dataset/slice/rescale callbacks for pixel readout and direction labels."""
    app = ctrl.app

    def resolve_subwindow_index() -> int:
        si = getattr(image_viewer, "subwindow_index", None)
        if si is not None:
            return int(si)
        return int(idx)

    def get_dataset() -> Dataset | None:
        return app._get_subwindow_dataset(resolve_subwindow_index())

    def get_slice_index() -> int:
        return app._get_subwindow_slice_index(resolve_subwindow_index())

    def get_use_rescaled() -> bool:
        i = resolve_subwindow_index()
        vsm = app.subwindow_managers.get(i, {}).get("view_state_manager")
        return bool(getattr(vsm, "use_rescaled_values", False)) if vsm else False

    image_viewer.set_pixel_info_callbacks(
        get_dataset=get_dataset,
        get_slice_index=get_slice_index,
        get_use_rescaled=get_use_rescaled,
    )


# ---------------------------------------------------------------------------
# All-subwindow wiring (called on every layout change)
# ---------------------------------------------------------------------------

def connect_subwindow_signals(ctrl: Any) -> None:
    """Connect signals that apply to all subwindows.

    Disconnects before connecting to avoid duplicate connections when this
    runs on every layout change.
    """
    app = ctrl.app
    subwindows = app.multi_window_layout.get_all_subwindows()
    for idx, subwindow in enumerate(subwindows):
        if subwindow:
            image_viewer = subwindow.image_viewer
            vid = id(image_viewer)
            with warnings.catch_warnings():
                warnings.filterwarnings(_WARN_FILTER_ACTION, category=RuntimeWarning, message=_WARN_DISCONNECT_MSG)
                try:
                    image_viewer.files_dropped.disconnect(app._open_files_from_paths)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.layout_change_requested.disconnect(app._on_layout_change_requested)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.privacy_view_toggled.disconnect(app._on_privacy_view_toggled)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.smooth_when_zoomed_toggled.disconnect(app._on_smooth_when_zoomed_toggled)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.scale_markers_toggled.disconnect(app._on_scale_markers_toggled)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.direction_labels_toggled.disconnect(app._on_direction_labels_toggled)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.slice_sync_toggled.disconnect(app._on_slice_sync_toggled)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.slice_sync_manage_requested.disconnect(app._open_slice_sync_dialog)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.slice_location_lines_toggled.disconnect(app._on_slice_location_lines_toggled)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.slice_location_lines_same_group_only_toggled.disconnect(
                        app._on_slice_location_lines_same_group_only_toggled
                    )
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.slice_location_lines_focused_only_toggled.disconnect(
                        app._on_slice_location_lines_focused_only_toggled
                    )
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.slice_location_lines_mode_toggled.disconnect(
                        app._on_slice_location_lines_mode_toggled
                    )
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.left_pane_toggle_requested.disconnect(app.main_window._toggle_left_pane)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.right_pane_toggle_requested.disconnect(app.main_window._toggle_right_pane)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.about_this_file_requested.disconnect(app._open_about_this_file)
                except (TypeError, RuntimeError):
                    pass
                if vid in ctrl._rdsr_report_slots:
                    try:
                        image_viewer.structured_report_browser_requested.disconnect(
                            ctrl._rdsr_report_slots[vid]
                        )
                    except (TypeError, RuntimeError):
                        pass
                    del ctrl._rdsr_report_slots[vid]
                if vid in ctrl._histogram_slots:
                    try:
                        image_viewer.histogram_requested.disconnect(ctrl._histogram_slots[vid])
                    except (TypeError, RuntimeError):
                        pass
                    del ctrl._histogram_slots[vid]
                if vid in ctrl._mpr_open_slots:
                    try:
                        image_viewer.create_mpr_view_requested.disconnect(ctrl._mpr_open_slots[vid])
                    except (TypeError, RuntimeError):
                        pass
                    del ctrl._mpr_open_slots[vid]
                if vid in ctrl._mpr_clear_slots:
                    try:
                        image_viewer.clear_mpr_view_requested.disconnect(ctrl._mpr_clear_slots[vid])
                    except (TypeError, RuntimeError):
                        pass
                    del ctrl._mpr_clear_slots[vid]
                if vid in ctrl._3d_view_slots:
                    try:
                        image_viewer.create_3d_view_requested.disconnect(ctrl._3d_view_slots[vid])
                    except (TypeError, RuntimeError):
                        pass
                    del ctrl._3d_view_slots[vid]
                try:
                    subwindow.assign_series_requested.disconnect(app._on_assign_series_requested)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.assign_series_requested.disconnect(app._on_assign_series_from_context_menu)
                except (TypeError, RuntimeError):
                    pass
                try:
                    subwindow.expand_to_1x1_requested.disconnect(app._on_expand_to_1x1_requested)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.swap_view_requested.disconnect(app._on_swap_view_requested)
                except (TypeError, RuntimeError):
                    pass
                try:
                    image_viewer.window_slot_map_popup_requested.disconnect(app._on_window_slot_map_popup_requested)
                except (TypeError, RuntimeError):
                    pass
                if vid in ctrl._clear_window_slots:
                    try:
                        image_viewer.clear_window_content_requested.disconnect(
                            ctrl._clear_window_slots[vid]
                        )
                    except (TypeError, RuntimeError):
                        pass
                    del ctrl._clear_window_slots[vid]
                if vid in ctrl._cine_toggle_slots:
                    try:
                        image_viewer.cine_play_pause_toggle_requested.disconnect(
                            ctrl._cine_toggle_slots[vid]
                        )
                    except (TypeError, RuntimeError):
                        pass
                    del ctrl._cine_toggle_slots[vid]
                if vid in ctrl._cine_stop_slots:
                    try:
                        image_viewer.cine_stop_requested.disconnect(ctrl._cine_stop_slots[vid])
                    except (TypeError, RuntimeError):
                        pass
                    del ctrl._cine_stop_slots[vid]

            image_viewer.files_dropped.connect(app._open_files_from_paths)
            image_viewer.layout_change_requested.connect(app._on_layout_change_requested)
            image_viewer.privacy_view_toggled.connect(app._on_privacy_view_toggled)
            image_viewer.smooth_when_zoomed_toggled.connect(app._on_smooth_when_zoomed_toggled)
            image_viewer.scale_markers_toggled.connect(app._on_scale_markers_toggled)
            image_viewer.direction_labels_toggled.connect(app._on_direction_labels_toggled)
            image_viewer.slice_sync_toggled.connect(app._on_slice_sync_toggled)
            image_viewer.slice_sync_manage_requested.connect(app._open_slice_sync_dialog)
            image_viewer.slice_location_lines_toggled.connect(app._on_slice_location_lines_toggled)
            image_viewer.slice_location_lines_same_group_only_toggled.connect(
                app._on_slice_location_lines_same_group_only_toggled
            )
            image_viewer.get_slice_location_lines_same_group_only_callback = (
                lambda: app.config_manager.get_slice_location_lines_same_group_only()
            )
            image_viewer.get_slice_location_lines_focused_only_callback = (
                lambda: app.config_manager.get_slice_location_lines_focused_only()
            )
            image_viewer.slice_location_lines_focused_only_toggled.connect(
                app._on_slice_location_lines_focused_only_toggled
            )
            image_viewer.slice_location_lines_mode_toggled.connect(
                app._on_slice_location_lines_mode_toggled
            )
            image_viewer.get_slice_location_lines_mode_callback = (
                lambda: app.config_manager.get_slice_location_line_mode()
            )
            image_viewer.left_pane_toggle_requested.connect(app.main_window._toggle_left_pane)
            image_viewer.right_pane_toggle_requested.connect(app.main_window._toggle_right_pane)
            image_viewer.about_this_file_requested.connect(app._open_about_this_file)
            def hist_slot(i=idx):
                return app.dialog_coordinator.open_histogram(i)
            image_viewer.histogram_requested.connect(hist_slot)
            ctrl._histogram_slots[vid] = hist_slot
            def sr_slot(i=idx):
                return app._open_structured_report_browser(i)
            image_viewer.structured_report_browser_requested.connect(sr_slot)
            ctrl._rdsr_report_slots[vid] = sr_slot
            image_viewer.get_file_path_callback = lambda i=idx: app._get_current_slice_file_path(i)
            image_viewer.get_slice_location_lines_visible_callback = (
                lambda: app.config_manager.get_slice_location_lines_visible()
            )
            image_viewer.set_subwindow_index(idx)
            wire_pixel_info_callbacks_for_subwindow(ctrl, image_viewer, idx)
            layout = app.multi_window_layout
            image_viewer.get_slot_to_view_callback = lambda lay=layout: lay.get_slot_to_view()
            subwindow.assign_series_requested.connect(app._on_assign_series_requested)
            image_viewer.assign_series_requested.connect(app._on_assign_series_from_context_menu)
            subwindow.mpr_assign_requested.connect(app._on_mpr_assign_requested)
            subwindow.expand_to_1x1_requested.connect(app._on_expand_to_1x1_requested)
            image_viewer.swap_view_requested.connect(app._on_swap_view_requested)
            image_viewer.window_slot_map_popup_requested.connect(app._on_window_slot_map_popup_requested)

            def clear_window_slot(i=idx):
                return app._on_clear_subwindow_content_requested(i)
            image_viewer.clear_window_content_requested.connect(clear_window_slot)
            ctrl._clear_window_slots[vid] = clear_window_slot
            image_viewer.get_clear_this_window_enabled_callback = lambda i=idx: (
                app.subwindow_data.get(i, {}).get("current_dataset") is not None
                or bool(app.subwindow_data.get(i, {}).get("is_mpr"))
            )
            image_viewer.get_cine_loop_state_callback = (
                lambda: app.cine_app_facade.get_cine_loop_state()
            )
            image_viewer.get_cine_is_playing_callback = lambda: app.cine_player.is_playing
            def cine_toggle_slot():
                return app.cine_app_facade.on_cine_play_pause_toggle()
            def cine_stop_slot():
                return app.cine_app_facade.on_cine_stop()
            image_viewer.cine_play_pause_toggle_requested.connect(cine_toggle_slot)
            image_viewer.cine_stop_requested.connect(cine_stop_slot)
            ctrl._cine_toggle_slots[vid] = cine_toggle_slot
            ctrl._cine_stop_slots[vid] = cine_stop_slot

            # MPR view actions.
            if hasattr(app, "_mpr_controller"):
                def open_mpr_slot(i=idx):
                    return app._mpr_controller.open_mpr_dialog(i)
                def clear_mpr_slot(i=idx):
                    return app._mpr_controller.clear_mpr(i)
                image_viewer.create_mpr_view_requested.connect(open_mpr_slot)
                image_viewer.clear_mpr_view_requested.connect(clear_mpr_slot)
                ctrl._mpr_open_slots[vid] = open_mpr_slot
                ctrl._mpr_clear_slots[vid] = clear_mpr_slot
                image_viewer.is_mpr_view_callback = lambda i=idx: app._mpr_controller.is_mpr(i)

            # 3D Volume Render action (context menu).
            if hasattr(app, "_volume_render_facade"):
                from core.volume_render_eligibility import can_launch_3d_volume_render

                def view_3d_slot(i=idx):
                    return app._volume_render_facade.launch_3d_view(i)
                image_viewer.create_3d_view_requested.connect(view_3d_slot)
                ctrl._3d_view_slots[vid] = view_3d_slot
                image_viewer.get_3d_volume_render_enabled_callback = (
                    lambda i=idx: can_launch_3d_volume_render(app, i)[0]
                )
    connect_all_subwindow_transform_signals(ctrl)


def connect_all_subwindow_transform_signals(ctrl: Any) -> None:
    """Connect transform_changed and zoom_changed for all subwindows to their ViewStateManager."""
    app = ctrl.app
    subwindows = app.multi_window_layout.get_all_subwindows()
    for idx, subwindow in enumerate(subwindows):
        if subwindow and idx in app.subwindow_managers:
            image_viewer = subwindow.image_viewer
            managers = app.subwindow_managers[idx]
            view_state_manager = managers.get('view_state_manager')
            if view_state_manager:
                with warnings.catch_warnings():
                    warnings.filterwarnings(_WARN_FILTER_ACTION, category=RuntimeWarning, message=_WARN_DISCONNECT_MSG)
                    try:
                        image_viewer.transform_changed.disconnect(view_state_manager.handle_transform_changed)
                    except (TypeError, RuntimeError):
                        pass
                    try:
                        image_viewer.zoom_changed.disconnect(view_state_manager.handle_zoom_changed)
                    except (TypeError, RuntimeError):
                        pass
                image_viewer.transform_changed.connect(view_state_manager.handle_transform_changed)
                image_viewer.zoom_changed.connect(view_state_manager.handle_zoom_changed)


def connect_all_subwindow_context_menu_signals(ctrl: Any) -> None:
    """Connect context menu and export ROI statistics signals for all subwindows."""
    app = ctrl.app
    subwindows = app.multi_window_layout.get_all_subwindows()
    for _idx, subwindow in enumerate(subwindows):
        if subwindow:
            image_viewer = subwindow.image_viewer
            image_viewer.context_menu_scroll_wheel_mode_changed.connect(
                app.mouse_mode_handler.handle_context_menu_scroll_wheel_mode_changed
            )
            image_viewer.export_roi_statistics_requested.connect(app._open_export_roi_statistics)


# ---------------------------------------------------------------------------
# Focused-subwindow wiring
# ---------------------------------------------------------------------------

def disconnect_focused_subwindow_signals(ctrl: Any) -> None:
    """Disconnect signals from previously focused subwindow."""
    app = ctrl.app
    if app.image_viewer is None:
        return
    with warnings.catch_warnings():
        warnings.filterwarnings(_WARN_FILTER_ACTION, category=RuntimeWarning, message=_WARN_DISCONNECT_MSG)
        try:
            app.image_viewer.annotation_options_requested.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.overlay_settings_requested.disconnect()
            app.image_viewer.overlay_config_requested.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.toggle_overlay_requested.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.roi_drawing_started.disconnect()
            app.image_viewer.roi_drawing_updated.disconnect()
            app.image_viewer.roi_drawing_finished.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.measurement_started.disconnect()
            app.image_viewer.measurement_updated.disconnect()
            app.image_viewer.measurement_finished.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.angle_measurement_clicked.disconnect()
            app.image_viewer.angle_measurement_preview.disconnect()
            app.image_viewer.angle_draw_cancel_requested.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.roi_clicked.disconnect()
            app.image_viewer.image_clicked_no_roi.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.roi_delete_requested.disconnect()
            app.image_viewer.roi_geometry_edit_requested.disconnect()
            app.image_viewer.measurement_delete_requested.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.roi_statistics_overlay_toggle_requested.disconnect()
            app.image_viewer.roi_statistics_selection_changed.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            if app.image_viewer.scene is not None:
                app.image_viewer.scene.selectionChanged.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.image_viewer.wheel_event_for_slice.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.pixel_info_changed.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.window_level_preset_selected.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.quick_window_level_requested.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.projection_enabled_changed.disconnect()
            app.image_viewer.projection_type_changed.disconnect()
            app.image_viewer.projection_slice_count_changed.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.context_menu_mouse_mode_changed.disconnect()
            app.image_viewer.context_menu_scroll_wheel_mode_changed.disconnect()
            app.image_viewer.context_menu_rescale_toggle_changed.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.zoom_changed.disconnect(app.view_state_manager.handle_zoom_changed)
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.image_viewer.zoom_changed.disconnect(app.zoom_display_widget.update_zoom)
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.image_viewer.zoom_changed.disconnect(app._on_zoom_changed)
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.image_viewer.transform_changed.disconnect(app.view_state_manager.handle_transform_changed)
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.image_viewer.arrow_key_pressed.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.right_mouse_press_for_drag.disconnect()
            app.image_viewer.window_level_drag_changed.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.image_viewer.series_navigation_requested.disconnect()
        except (TypeError, RuntimeError):
            pass
        try:
            app.roi_list_panel.roi_selected.disconnect()
            app.roi_list_panel.roi_deleted.disconnect()
            app.roi_list_panel.delete_all_requested.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            if hasattr(app, 'image_viewer') and app.image_viewer:
                app.image_viewer.crosshair_clicked.disconnect()
                app.image_viewer.crosshair_delete_requested.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.slice_navigator.slice_changed.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        # Clear the edge-reveal slider navigate callback from the outgoing viewer
        try:
            if hasattr(app, "image_viewer") and app.image_viewer is not None:
                app.image_viewer.slider_navigate_callback = None
        except Exception:
            pass
        try:
            app.window_level_controls.window_changed.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.intensity_projection_controls_widget.enabled_changed.disconnect()
            app.intensity_projection_controls_widget.projection_type_changed.disconnect()
            app.intensity_projection_controls_widget.slice_count_changed.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.main_window.mouse_mode_changed.disconnect()
            app.main_window.scroll_wheel_mode_changed.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.main_window.rescale_toggle_changed.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.main_window.series_navigation_requested.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.main_window.overlay_font_size_changed.disconnect()
            app.main_window.overlay_font_color_changed.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
        try:
            app.zoom_display_widget.zoom_changed.disconnect()
        except (TypeError, RuntimeError, AttributeError):
            pass
    try:
        if hasattr(app, '_previous_fusion_coordinator') and app._previous_fusion_coordinator is not None:
            app._previous_fusion_coordinator.disconnect_fusion_controls_signals()
            app._previous_fusion_coordinator = None
    except (TypeError, RuntimeError, AttributeError):
        pass


def connect_focused_subwindow_signals(ctrl: Any) -> None:
    """Connect signals for the currently focused subwindow."""
    app = ctrl.app
    disconnect_focused_subwindow_signals(ctrl)
    if app.image_viewer is None:
        return
    focused_idx = app.focused_subwindow_index
    if app.view_state_manager:
        app.view_state_manager.set_redisplay_slice_callback(
            lambda preserve_view=False: ctrl.redisplay_subwindow_slice(focused_idx, preserve_view)
        )
    app.image_viewer.annotation_options_requested.connect(app._open_annotation_options)
    app.image_viewer.overlay_settings_requested.connect(app._open_overlay_settings)
    app.image_viewer.overlay_config_requested.connect(app._open_overlay_config)
    app.image_viewer.roi_drawing_started.connect(app.roi_coordinator.handle_roi_drawing_started)
    app.image_viewer.roi_drawing_updated.connect(app.roi_coordinator.handle_roi_drawing_updated)
    app.image_viewer.roi_drawing_finished.connect(app.roi_coordinator.handle_roi_drawing_finished)
    app.image_viewer.measurement_started.connect(app.measurement_coordinator.handle_measurement_started)
    app.image_viewer.measurement_updated.connect(app.measurement_coordinator.handle_measurement_updated)
    app.image_viewer.measurement_finished.connect(app.measurement_coordinator.handle_measurement_finished)
    app.image_viewer.angle_measurement_clicked.connect(
        app.measurement_coordinator.handle_angle_measurement_clicked
    )
    app.image_viewer.angle_measurement_preview.connect(
        app.measurement_coordinator.handle_angle_measurement_preview
    )
    app.image_viewer.angle_draw_cancel_requested.connect(
        app.measurement_coordinator.handle_angle_draw_cancel_requested
    )
    if hasattr(app, 'text_annotation_coordinator') and app.text_annotation_coordinator is not None:
        app.image_viewer.text_annotation_started.connect(app.text_annotation_coordinator.handle_text_annotation_started)
        app.image_viewer.text_annotation_finished.connect(app.text_annotation_coordinator.handle_text_annotation_finished)
    if hasattr(app, 'arrow_annotation_coordinator') and app.arrow_annotation_coordinator is not None:
        app.image_viewer.arrow_annotation_started.connect(app.arrow_annotation_coordinator.handle_arrow_annotation_started)
        app.image_viewer.arrow_annotation_updated.connect(app.arrow_annotation_coordinator.handle_arrow_annotation_updated)
        app.image_viewer.arrow_annotation_finished.connect(app.arrow_annotation_coordinator.handle_arrow_annotation_finished)
    if hasattr(app, 'crosshair_coordinator') and app.crosshair_coordinator is not None:
        app.image_viewer.crosshair_clicked.connect(app.crosshair_coordinator.handle_crosshair_clicked)
    app.image_viewer.roi_clicked.connect(app.roi_coordinator.handle_roi_clicked)
    app.image_viewer.image_clicked_no_roi.connect(app.roi_coordinator.handle_image_clicked_no_roi)
    app.image_viewer.roi_delete_requested.connect(app.roi_coordinator.handle_roi_delete_requested)
    app.image_viewer.roi_geometry_edit_requested.connect(
        app.roi_coordinator.handle_roi_geometry_edit_requested
    )
    app.image_viewer.measurement_delete_requested.connect(app.measurement_coordinator.handle_measurement_delete_requested)
    if hasattr(app, 'text_annotation_coordinator') and app.text_annotation_coordinator is not None:
        app.image_viewer.text_annotation_delete_requested.connect(app.text_annotation_coordinator.handle_text_annotation_delete_requested)
    if hasattr(app, 'arrow_annotation_coordinator') and app.arrow_annotation_coordinator is not None:
        app.image_viewer.arrow_annotation_delete_requested.connect(app.arrow_annotation_coordinator.handle_arrow_annotation_delete_requested)
    if hasattr(app, 'crosshair_coordinator') and app.crosshair_coordinator is not None:
        app.image_viewer.crosshair_delete_requested.connect(app.crosshair_coordinator.handle_crosshair_delete_requested)
    app.image_viewer.roi_statistics_overlay_toggle_requested.connect(app.roi_coordinator.handle_roi_statistics_overlay_toggle)
    app.image_viewer.roi_statistics_selection_changed.connect(app.roi_coordinator.handle_roi_statistics_selection)
    app.image_viewer.get_roi_from_item_callback = app.roi_manager.find_roi_by_item
    app.image_viewer.delete_all_rois_callback = app.roi_coordinator.delete_all_rois_current_slice
    app.roi_list_panel.roi_selected.connect(app.roi_coordinator.handle_roi_selected)
    app.roi_list_panel.roi_deleted.connect(app.roi_coordinator.handle_roi_deleted)
    app.roi_list_panel.delete_all_requested.connect(app.roi_coordinator.delete_all_rois_current_slice)
    app.roi_list_panel.roi_delete_callback = lambda roi: app.roi_coordinator.handle_roi_delete_requested(roi.item) if roi.item else None
    app.roi_list_panel.delete_all_rois_callback = app.roi_coordinator.delete_all_rois_current_slice
    app.roi_list_panel.roi_statistics_overlay_toggle_callback = app.roi_coordinator.handle_roi_statistics_overlay_toggle

    def handle_statistic_toggle(roi, stat_name: str, checked: bool) -> None:
        if checked:
            roi.visible_statistics.add(stat_name)
        else:
            roi.visible_statistics.discard(stat_name)
        app.roi_coordinator.handle_roi_statistics_selection(roi, roi.visible_statistics)
    app.roi_list_panel.roi_statistics_selection_callback = handle_statistic_toggle
    app.roi_list_panel.annotation_options_callback = app._open_annotation_options
    app.image_viewer.scene.selectionChanged.connect(app.roi_coordinator.handle_scene_selection_changed)
    app.image_viewer.wheel_event_for_slice.connect(lambda delta: app.slice_navigator.handle_wheel_event(delta))
    app.image_viewer.pixel_info_changed.connect(app._on_pixel_info_changed)
    wire_pixel_info_callbacks_for_subwindow(ctrl, app.image_viewer, focused_idx)

    def get_available_series() -> list[Any]:
        if not app.current_studies:
            return []
        series_list = []
        for _study_uid, series_dict in app.current_studies.items():
            for series_uid, datasets in series_dict.items():
                if datasets:
                    first_dataset = datasets[0]
                    series_num = getattr(first_dataset, 'SeriesNumber', '')
                    series_desc = getattr(first_dataset, 'SeriesDescription', 'Unknown Series')
                    modality = getattr(first_dataset, 'Modality', '')
                    series_list.append((series_uid, f"Series {series_num}: {series_desc} ({modality})"))
        return series_list
    app.image_viewer.get_available_series_callback = get_available_series
    app.image_viewer.right_mouse_press_for_drag.connect(app.view_state_manager.handle_right_mouse_press_for_drag)
    app.image_viewer.window_level_drag_changed.connect(app.view_state_manager.handle_window_level_drag)
    app.image_viewer.get_window_level_presets_callback = (
        lambda: app.view_state_manager.window_level_presets if app.view_state_manager else []
    )
    app.image_viewer.get_current_preset_index_callback = (
        lambda: app.view_state_manager.current_preset_index if app.view_state_manager else 0
    )
    app.image_viewer.get_wl_preset_menu_context_callback = (
        lambda: app.main_window._get_wl_preset_menu_context()
        if getattr(app.main_window, "_get_wl_preset_menu_context", None) is not None
        else None
    )
    app.image_viewer.manage_wl_presets_callback = app._open_wl_preset_manager
    if app.keyboard_event_handler:
        app.keyboard_event_handler.roi_manager = app.roi_manager
        app.keyboard_event_handler.measurement_tool = app.measurement_tool
        app.keyboard_event_handler.overlay_manager = app.overlay_manager
        app.keyboard_event_handler.clear_measurements_callback = (
            app.measurement_coordinator.handle_clear_measurements
        )
        app.keyboard_event_handler.toggle_overlay_callback = (
            app.overlay_coordinator.handle_toggle_overlay
        )
        app.keyboard_event_handler.cycle_overlay_detail_callback = (
            app._cycle_overlay_detail_mode
        )
        app.keyboard_event_handler.toggle_overlay_visibility_legacy_callback = (
            app.overlay_coordinator.handle_toggle_overlay
        )
        app.keyboard_event_handler.delete_measurement_callback = (
            app.measurement_coordinator.handle_measurement_delete_requested
        )
        app.keyboard_event_handler.delete_all_rois_callback = app.roi_coordinator.delete_all_rois_current_slice
        app.keyboard_event_handler.invert_image_callback = app.image_viewer.invert_image
        if hasattr(app, 'text_annotation_coordinator') and app.text_annotation_coordinator:
            app.keyboard_event_handler.delete_text_annotation_callback = app.text_annotation_coordinator.handle_text_annotation_delete_requested
        if hasattr(app, 'arrow_annotation_coordinator') and app.arrow_annotation_coordinator:
            app.keyboard_event_handler.delete_arrow_annotation_callback = app.arrow_annotation_coordinator.handle_arrow_annotation_delete_requested
    app.window_level_controls.window_changed.connect(app.view_state_manager.handle_window_changed)
    app.window_level_controls.window_changed.connect(app._schedule_histogram_wl_only)
    app.image_viewer.window_level_preset_selected.connect(app._on_window_level_preset_selected)
    app.image_viewer.quick_window_level_requested.connect(app._open_quick_window_level)
    app.intensity_projection_controls_widget.enabled_changed.connect(app._on_projection_enabled_changed)
    app.intensity_projection_controls_widget.projection_type_changed.connect(app._on_projection_type_changed)
    app.intensity_projection_controls_widget.slice_count_changed.connect(app._on_projection_slice_count_changed)
    if app.fusion_coordinator is not None:
        app.fusion_coordinator.connect_fusion_controls_signals()
        app.fusion_coordinator.sync_ui_from_handler_state()
        app._previous_fusion_coordinator = app.fusion_coordinator
    app.image_viewer.projection_enabled_changed.connect(app._on_projection_enabled_changed)
    app.image_viewer.projection_type_changed.connect(app._on_projection_type_changed)
    app.image_viewer.projection_slice_count_changed.connect(app._on_projection_slice_count_changed)
    app.image_viewer.get_projection_enabled_callback = lambda: app.slice_display_manager.projection_enabled
    app.image_viewer.get_projection_type_callback = lambda: app.slice_display_manager.projection_type
    app.image_viewer.get_projection_slice_count_callback = lambda: app.slice_display_manager.projection_slice_count
    app.slice_navigator.slice_changed.connect(app._on_slice_changed)
    app.slice_navigator.slice_changed.connect(app.cine_app_facade.on_manual_slice_navigation)
    # Wire the edge-reveal slider overlay so dragging it navigates slices.
    app.image_viewer.slider_navigate_callback = app.slice_navigator.set_current_slice
    app.main_window.mouse_mode_changed.connect(app.mouse_mode_handler.handle_mouse_mode_changed)
    app.main_window.scroll_wheel_mode_changed.connect(app._on_scroll_wheel_mode_changed)
    app.image_viewer.context_menu_mouse_mode_changed.connect(app.mouse_mode_handler.handle_context_menu_mouse_mode_changed)
    app.image_viewer.context_menu_scroll_wheel_mode_changed.connect(app.mouse_mode_handler.handle_context_menu_scroll_wheel_mode_changed)
    app.image_viewer.context_menu_rescale_toggle_changed.connect(app.view_state_manager.handle_rescale_toggle)
    app.main_window.rescale_toggle_changed.connect(app.view_state_manager.handle_rescale_toggle)
    app.image_viewer.zoom_changed.connect(app.view_state_manager.handle_zoom_changed)
    app.image_viewer.zoom_changed.connect(app.zoom_display_widget.update_zoom)
    app.image_viewer.zoom_changed.connect(app._on_zoom_changed)
    app.zoom_display_widget.zoom_changed.connect(app.image_viewer.set_zoom)
    app.image_viewer.transform_changed.connect(app.view_state_manager.handle_transform_changed)
    app.image_viewer.arrow_key_pressed.connect(app.slice_display_manager.handle_arrow_key_pressed)
    app.image_viewer.right_mouse_press_for_drag.connect(app.view_state_manager.handle_right_mouse_press_for_drag)
    app.image_viewer.window_level_drag_changed.connect(app.view_state_manager.handle_window_level_drag)
    app.image_viewer.series_navigation_requested.connect(app._on_series_navigation_requested)
    app.main_window.series_navigation_requested.connect(app._on_series_navigation_requested)
    app.series_navigator.series_navigation_requested.connect(
        app._on_series_navigation_requested,
        Qt.ConnectionType.UniqueConnection
    )
    app.main_window.overlay_font_size_changed.connect(app._on_overlay_font_size_changed)
    app.main_window.overlay_font_color_changed.connect(app._on_overlay_font_color_changed)

    def handle_reset_view():
        app.view_state_manager.reset_view(skip_redisplay=True)

        try:
            focused_subwindow = app.multi_window_layout.get_focused_subwindow()
            subwindows = app.multi_window_layout.get_all_subwindows()
            fi = subwindows.index(focused_subwindow) if focused_subwindow in subwindows else -1
        except Exception:
            fi = -1

        is_mpr_view = False
        try:
            if (
                hasattr(app, "_mpr_controller")
                and fi != -1
                and app._mpr_controller.is_mpr(fi)
            ):
                is_mpr_view = True
        except Exception:
            is_mpr_view = False

        if is_mpr_view:
            data = app.subwindow_data.get(fi, {})
            slice_index = data.get("mpr_slice_index", 0)
            try:
                app._mpr_controller.display_mpr_slice(fi, slice_index)
                iv = app._mpr_controller._get_image_viewer(fi)
                if iv is not None:
                    iv.fit_to_view(center_image=True)
                return
            except Exception:
                pass

        if app.current_dataset is not None:
            app._display_slice(app.current_dataset, preserve_view_override=False)
    app.main_window.reset_view_requested.connect(handle_reset_view)
    app.image_viewer.reset_view_requested.connect(handle_reset_view)
    app.main_window.reset_all_views_requested.connect(app._on_reset_all_views)
    app.image_viewer.reset_all_views_requested.connect(app._on_reset_all_views)
    app.main_window.clear_measurements_requested.connect(app.measurement_coordinator.handle_clear_measurements)
    app.image_viewer.clear_measurements_requested.connect(app.measurement_coordinator.handle_clear_measurements)
    app.image_viewer.histogram_requested.connect(app.dialog_coordinator.open_histogram)
    app.image_viewer.toggle_overlay_requested.connect(app._cycle_overlay_detail_mode)
    app.main_window.viewport_resizing.connect(app.view_state_manager.handle_viewport_resizing)
    app.main_window.viewport_resized.connect(app.view_state_manager.handle_viewport_resized)
    app.slice_navigator.slice_changed.connect(app._update_histogram_for_focused_subwindow)
    _connect_unique(app.series_navigator.series_selected, app._on_series_navigator_selected)
    _connect_unique(app.series_navigator.instance_selected, app._on_series_navigator_instance_selected)
    _connect_unique(
        app.series_navigator.show_instances_separately_toggled,
        app._on_show_instances_separately_toggled,
    )
    _connect_unique(app.series_navigator.show_file_requested, app._on_show_file_from_series)
    _connect_unique(app.series_navigator.about_this_file_requested, app._on_about_this_file_from_series)
    app.image_viewer.toggle_series_navigator_requested.connect(app.main_window.toggle_series_navigator)
