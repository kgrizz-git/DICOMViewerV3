"""Synthetic round-three coverage for subwindow signal wiring."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from core.subwindow_signal_wiring import (
    connect_all_subwindow_context_menu_signals,
    connect_all_subwindow_transform_signals,
    connect_focused_subwindow_signals,
    connect_subwindow_signals,
    disconnect_focused_subwindow_signals,
)


class _Signal:
    """Minimal signal double that models missing Qt connections."""

    def __init__(self) -> None:
        self.slots: list[object] = []

    def connect(self, slot: object, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.slots.append(slot)

    def disconnect(self, slot: object | None = None) -> None:
        if slot is None:
            if not self.slots:
                raise TypeError("signal has no connections")
            self.slots.clear()
            return
        if slot not in self.slots:
            raise TypeError("slot is not connected")
        self.slots.remove(slot)

    def emit(self, *args: object) -> None:
        for slot in list(self.slots):
            slot(*args)  # type: ignore[operator]


_LAYOUT_VIEWER_SIGNALS = ["files_dropped", "layout_change_requested", "privacy_view_toggled", "smooth_when_zoomed_toggled", "scale_markers_toggled", "direction_labels_toggled", "slice_sync_toggled", "slice_sync_manage_requested", "slice_location_lines_toggled", "slice_location_lines_same_group_only_toggled", "slice_location_lines_focused_only_toggled", "slice_location_lines_mode_toggled", "left_pane_toggle_requested", "right_pane_toggle_requested", "about_this_file_requested", "assign_series_requested", "swap_view_requested", "window_slot_map_popup_requested", "overlay_font_size_adjust_requested", "histogram_requested", "structured_report_browser_requested", "clear_window_content_requested", "cine_play_pause_toggle_requested", "cine_stop_requested", "create_mpr_view_requested", "clear_mpr_view_requested", "create_3d_view_requested", "transform_changed", "zoom_changed", "context_menu_scroll_wheel_mode_changed", "export_roi_statistics_requested"]

_FOCUSED_VIEWER_SIGNALS = ["annotation_options_requested", "overlay_settings_requested", "overlay_config_requested", "roi_drawing_started", "roi_drawing_updated", "roi_drawing_finished", "measurement_started", "measurement_updated", "measurement_finished", "angle_measurement_clicked", "angle_measurement_preview", "angle_draw_cancel_requested", "roi_clicked", "image_clicked_no_roi", "roi_delete_requested", "roi_geometry_edit_requested", "measurement_delete_requested", "roi_statistics_overlay_toggle_requested", "roi_statistics_selection_changed", "wheel_event_for_slice", "pixel_info_changed", "window_level_preset_selected", "quick_window_level_requested", "projection_enabled_changed", "projection_type_changed", "projection_slice_count_changed", "context_menu_mouse_mode_changed", "context_menu_scroll_wheel_mode_changed", "context_menu_rescale_toggle_changed", "arrow_key_pressed", "right_mouse_press_for_drag", "window_level_drag_changed", "series_navigation_requested", "reset_view_requested", "reset_all_views_requested", "clear_measurements_requested", "histogram_requested", "toggle_overlay_requested", "toggle_series_navigator_requested", "zoom_changed", "transform_changed"]


def _signals(names: list[str] | tuple[str, ...]) -> SimpleNamespace:
    return SimpleNamespace(**{name: _Signal() for name in names})


def _layout_app(viewer: SimpleNamespace, subwindow: SimpleNamespace) -> tuple[SimpleNamespace, SimpleNamespace]:
    callbacks = ["_open_files_from_paths", "_on_layout_change_requested", "_on_privacy_view_toggled", "_on_smooth_when_zoomed_toggled", "_on_scale_markers_toggled", "_on_direction_labels_toggled", "_on_slice_sync_toggled", "_open_slice_sync_dialog", "_on_slice_location_lines_toggled", "_on_slice_location_lines_same_group_only_toggled", "_on_slice_location_lines_focused_only_toggled", "_on_slice_location_lines_mode_toggled", "_open_about_this_file", "_on_assign_series_requested", "_on_assign_series_from_context_menu", "_on_expand_to_1x1_requested", "_on_swap_view_requested", "_on_window_slot_map_popup_requested", "_on_mpr_assign_requested", "_open_structured_report_browser", "_get_current_slice_file_path", "_on_clear_subwindow_content_requested", "_get_subwindow_dataset", "_get_subwindow_slice_index"]
    app = SimpleNamespace(
        multi_window_layout=SimpleNamespace(
            get_all_subwindows=MagicMock(return_value=[subwindow]),
            get_slot_to_view=MagicMock(return_value=0),
        ),
        subwindow_managers={},
        subwindow_data={0: {"current_dataset": object(), "is_mpr": False}},
        main_window=SimpleNamespace(
            _toggle_left_pane=MagicMock(), _toggle_right_pane=MagicMock(), adjust_overlay_font_size=MagicMock()
        ),
        config_manager=SimpleNamespace(
            get_slice_location_lines_same_group_only=MagicMock(return_value=True),
            get_slice_location_lines_focused_only=MagicMock(return_value=False),
            get_slice_location_line_mode=MagicMock(return_value="all"),
            get_slice_location_lines_visible=MagicMock(return_value=True),
        ),
        dialog_coordinator=SimpleNamespace(open_histogram=MagicMock()),
        cine_app_facade=SimpleNamespace(
            get_cine_loop_state=MagicMock(return_value=True),
            on_cine_play_pause_toggle=MagicMock(),
            on_cine_stop=MagicMock(),
        ),
        cine_player=SimpleNamespace(is_playing=False),
    )
    for name in callbacks:
        setattr(app, name, MagicMock(return_value=None))
    app._get_subwindow_slice_index.return_value = 0
    app._mpr_controller = SimpleNamespace(
        open_mpr_dialog=MagicMock(), clear_mpr=MagicMock(), is_mpr=MagicMock(return_value=False)
    )
    app._volume_render_facade = SimpleNamespace(launch_3d_view=MagicMock())
    viewer.set_subwindow_index = MagicMock()
    viewer.set_pixel_info_callbacks = MagicMock()
    ctrl = SimpleNamespace(
        app=app,
        _rdsr_report_slots={}, _histogram_slots={}, _mpr_open_slots={}, _mpr_clear_slots={},
        _3d_view_slots={}, _clear_window_slots={}, _cine_toggle_slots={}, _cine_stop_slots={},
    )
    return app, ctrl


def test_layout_reconnect_is_idempotent_and_tracks_all_optional_slots() -> None:
    viewer = _signals(_LAYOUT_VIEWER_SIGNALS)
    subwindow = SimpleNamespace(
        image_viewer=viewer, assign_series_requested=_Signal(), expand_to_1x1_requested=_Signal(), mpr_assign_requested=_Signal()
    )
    app, ctrl = _layout_app(viewer, subwindow)
    app.subwindow_managers[0] = {"view_state_manager": SimpleNamespace(handle_transform_changed=MagicMock(), handle_zoom_changed=MagicMock())}

    connect_subwindow_signals(ctrl)
    first = {name: next(iter(getattr(ctrl, name).values())) for name in (
        "_histogram_slots", "_rdsr_report_slots", "_mpr_open_slots", "_mpr_clear_slots",
        "_3d_view_slots", "_clear_window_slots", "_cine_toggle_slots", "_cine_stop_slots"
    )}
    viewer.histogram_requested.emit()
    viewer.cine_play_pause_toggle_requested.emit()
    viewer.create_mpr_view_requested.emit()
    viewer.create_3d_view_requested.emit()
    app.dialog_coordinator.open_histogram.assert_called_once_with(0)
    app.cine_app_facade.on_cine_play_pause_toggle.assert_called_once_with()
    app._mpr_controller.open_mpr_dialog.assert_called_once_with(0)
    app._volume_render_facade.launch_3d_view.assert_called_once_with(0)

    connect_subwindow_signals(ctrl)
    assert len(viewer.histogram_requested.slots) == 1
    assert all(getattr(ctrl, name)[id(viewer)] is not first[name] for name in first)


def test_transform_and_context_connections_reconnect_without_duplicates() -> None:
    viewer = _signals(["transform_changed", "zoom_changed", "context_menu_scroll_wheel_mode_changed", "export_roi_statistics_requested"])
    subwindow = SimpleNamespace(image_viewer=viewer)
    vsm = SimpleNamespace(handle_transform_changed=MagicMock(), handle_zoom_changed=MagicMock())
    app = SimpleNamespace(
        multi_window_layout=SimpleNamespace(get_all_subwindows=MagicMock(return_value=[subwindow])),
        subwindow_managers={0: {"view_state_manager": vsm}},
        mouse_mode_handler=SimpleNamespace(handle_context_menu_scroll_wheel_mode_changed=MagicMock()),
        _open_export_roi_statistics=MagicMock(),
    )
    ctrl = SimpleNamespace(app=app)
    connect_all_subwindow_transform_signals(ctrl)
    connect_all_subwindow_transform_signals(ctrl)
    connect_all_subwindow_context_menu_signals(ctrl)
    assert viewer.transform_changed.slots == [vsm.handle_transform_changed]
    assert len(viewer.context_menu_scroll_wheel_mode_changed.slots) == 1
    assert viewer.export_roi_statistics_requested.slots == [app._open_export_roi_statistics]


def test_focused_setup_binds_callback_and_reconnects_after_disconnect() -> None:
    viewer = _signals(_FOCUSED_VIEWER_SIGNALS)
    viewer.scene = SimpleNamespace(selectionChanged=_Signal())
    viewer.set_zoom = MagicMock()
    viewer.set_pixel_info_callbacks = MagicMock()
    app = SimpleNamespace(
        image_viewer=viewer, focused_subwindow_index=2, current_studies={}, current_dataset=None,
        view_state_manager=SimpleNamespace(
            set_redisplay_slice_callback=MagicMock(), handle_zoom_changed=MagicMock(), handle_transform_changed=MagicMock(),
            handle_right_mouse_press_for_drag=MagicMock(), handle_window_level_drag=MagicMock(), handle_rescale_toggle=MagicMock(),
            handle_window_changed=MagicMock(), handle_viewport_resizing=MagicMock(), handle_viewport_resized=MagicMock(),
            reset_view=MagicMock(), window_level_presets=[], current_preset_index=0,
        ),
        roi_coordinator=SimpleNamespace(**{name: MagicMock() for name in ["handle_roi_drawing_started", "handle_roi_drawing_updated", "handle_roi_drawing_finished", "handle_roi_clicked", "handle_image_clicked_no_roi", "handle_roi_delete_requested", "handle_roi_geometry_edit_requested", "handle_roi_statistics_overlay_toggle", "handle_roi_statistics_selection", "handle_scene_selection_changed", "handle_clear_measurements", "handle_roi_selected", "handle_roi_deleted", "delete_all_rois_current_slice"]}),
        measurement_coordinator=SimpleNamespace(**{name: MagicMock() for name in ["handle_measurement_started", "handle_measurement_updated", "handle_measurement_finished", "handle_angle_measurement_clicked", "handle_angle_measurement_preview", "handle_angle_draw_cancel_requested", "handle_measurement_delete_requested", "handle_clear_measurements"]}),
        roi_manager=SimpleNamespace(find_roi_by_item=MagicMock()),
        roi_list_panel=SimpleNamespace(**{name: _Signal() for name in ("roi_selected", "roi_deleted", "delete_all_requested", "roi_statistics_selection")}),
        slice_navigator=SimpleNamespace(slice_changed=_Signal(), handle_wheel_event=MagicMock(), set_current_slice=MagicMock()),
        window_level_controls=SimpleNamespace(window_changed=_Signal()),
        intensity_projection_controls_widget=SimpleNamespace(**{name: _Signal() for name in ("enabled_changed", "projection_type_changed", "slice_count_changed")}),
        zoom_display_widget=SimpleNamespace(zoom_changed=_Signal(), update_zoom=MagicMock()),
        main_window=_signals(["mouse_mode_changed", "scroll_wheel_mode_changed", "rescale_toggle_changed", "series_navigation_requested", "overlay_font_size_changed", "overlay_font_color_changed", "reset_view_requested", "reset_all_views_requested", "clear_measurements_requested", "viewport_resizing", "viewport_resized"]),
        series_navigator=SimpleNamespace(**{name: _Signal() for name in ("series_navigation_requested", "series_selected", "instance_selected", "show_instances_separately_toggled", "show_file_requested", "about_this_file_requested")}),
        mouse_mode_handler=SimpleNamespace(**{name: MagicMock() for name in ("handle_mouse_mode_changed", "handle_context_menu_mouse_mode_changed", "handle_context_menu_scroll_wheel_mode_changed")}),
        keyboard_event_handler=None, fusion_coordinator=None,
        slice_display_manager=SimpleNamespace(projection_enabled=False, projection_type="", projection_slice_count=0, handle_arrow_key_pressed=MagicMock()),
        cine_app_facade=SimpleNamespace(on_manual_slice_navigation=MagicMock()),
        dialog_coordinator=SimpleNamespace(open_histogram=MagicMock()),
        _get_subwindow_dataset=MagicMock(return_value=None), _get_subwindow_slice_index=MagicMock(return_value=0),
    )
    app.main_window._get_wl_preset_menu_context = MagicMock(return_value=None)
    app.main_window.toggle_series_navigator = MagicMock()
    callbacks = ["_open_annotation_options", "_open_overlay_settings", "_open_overlay_config", "_on_pixel_info_changed", "_on_window_level_preset_selected", "_open_quick_window_level", "_on_projection_enabled_changed", "_on_projection_type_changed", "_on_projection_slice_count_changed", "_on_slice_changed", "_schedule_histogram_wl_only", "_on_series_navigation_requested", "_on_series_navigator_selected", "_on_series_navigator_instance_selected", "_on_show_instances_separately_toggled", "_on_show_file_from_series", "_on_about_this_file_from_series", "_on_overlay_font_size_changed", "_on_overlay_font_color_changed", "_on_zoom_changed", "_on_reset_all_views", "_cycle_overlay_detail_mode", "_open_wl_preset_manager", "_update_histogram_for_focused_subwindow", "_on_scroll_wheel_mode_changed"]
    for name in callbacks:
        setattr(app, name, MagicMock())
    ctrl = SimpleNamespace(app=app, redisplay_subwindow_slice=MagicMock())

    connect_focused_subwindow_signals(ctrl)
    app.view_state_manager.set_redisplay_slice_callback.assert_called_once()
    viewer.annotation_options_requested.emit()
    app._open_annotation_options.assert_called_once_with()
    callback = app.view_state_manager.set_redisplay_slice_callback.call_args.args[0]
    callback(True)
    ctrl.redisplay_subwindow_slice.assert_called_once_with(2, True)
    disconnect_focused_subwindow_signals(ctrl)
    assert viewer.annotation_options_requested.slots == []
    connect_focused_subwindow_signals(ctrl)
    assert len(viewer.annotation_options_requested.slots) == 1


def test_focused_disconnect_tolerates_unconnected_signals_and_none_viewer() -> None:
    viewer = _signals(_FOCUSED_VIEWER_SIGNALS)
    viewer.scene = SimpleNamespace(selectionChanged=_Signal())
    app = SimpleNamespace(image_viewer=viewer)
    disconnect_focused_subwindow_signals(SimpleNamespace(app=app))
    assert viewer.slider_navigate_callback is None
    disconnect_focused_subwindow_signals(SimpleNamespace(app=SimpleNamespace(image_viewer=None)))
