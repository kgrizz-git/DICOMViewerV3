"""
Study / series navigator state helpers.

These functions keep the focused-series highlighting, per-slot assignment map,
and 3D action enablement logic out of ``main.py`` while preserving the app's
public method surface for signal wiring and cross-controller callbacks.
"""

from __future__ import annotations

from typing import Any

from core.dataset_cache_utils import clear_cached_pixel_array


def get_subwindow_assignments(app: Any) -> dict[int, tuple[str, str, int]]:
    """
    Build the slot-index mapping used by ``SeriesNavigator``.

    Slot indices reflect the visible grid positions, while ``subwindow_data``
    stays keyed by the underlying view index. After window swaps, slot-to-view
    translation must come from ``multi_window_layout.get_slot_to_view()``.
    """
    slot_to_view = app.multi_window_layout.get_slot_to_view()
    assignments: dict[int, tuple[str, str, int]] = {}
    for slot_idx, view_idx in enumerate(slot_to_view):
        if slot_idx >= 4:
            break
        if not isinstance(view_idx, int) or view_idx < 0 or view_idx > 3:
            continue
        data = app.subwindow_data.get(view_idx, {})
        if data.get("current_dataset") is None:
            continue
        assignments[slot_idx] = (
            data["current_study_uid"],
            data["current_series_uid"],
            data.get("current_slice_index", 0),
        )
    return assignments


def update_series_navigator_highlighting(app: Any) -> None:
    """Sync navigator highlighting to the focused subwindow's current series."""
    focused_idx = app.focused_subwindow_index
    if focused_idx in app.subwindow_data:
        data = app.subwindow_data[focused_idx]
        focused_series_uid = data.get("current_series_uid", "")
        focused_study_uid = data.get("current_study_uid", "")
        focused_slice_index = data.get("current_slice_index", 0)
        if focused_series_uid and focused_study_uid:
            app.series_navigator.set_current_position(
                focused_series_uid,
                focused_study_uid,
                focused_slice_index,
            )
        elif focused_series_uid:
            app.series_navigator.set_current_position(
                focused_series_uid,
                slice_index=focused_slice_index,
            )
        else:
            app.series_navigator.set_current_position("", "", 0)
    refresh_series_navigator_state(app)


def refresh_series_navigator_state(app: Any) -> None:
    """Push current multiframe/navigation affordance state into the UI."""
    app.series_navigator.set_multiframe_info_map(
        app.dicom_organizer.series_multiframe_info
    )
    show_instances_separately = app.config_manager.get_show_instances_separately()
    app.series_navigator.set_show_instances_separately(show_instances_separately)
    app.main_window.set_show_instances_separately_checked(
        show_instances_separately
    )

    multiframe_info = None
    if app.current_study_uid and app.current_series_uid:
        multiframe_info = app.dicom_organizer.get_series_multiframe_info(
            app.current_study_uid,
            app.current_series_uid,
        )

    can_expand_instances = bool(
        multiframe_info is not None
        and multiframe_info.max_frame_count > 1
        and multiframe_info.instance_count > 1
    )
    app.main_window.set_show_instances_separately_enabled(
        can_expand_instances or show_instances_separately
    )
    update_3d_view_action_state(app)


def update_3d_view_action_state(app: Any) -> None:
    """Enable toolbar/menu 3D actions when the focused series is eligible."""
    from core.volume_render_eligibility import can_launch_3d_volume_render

    enabled, tooltip = can_launch_3d_volume_render(app)
    app.main_window.set_3d_view_actions_enabled(enabled, tooltip)


def clear_subwindow(app: Any, idx: int) -> None:
    """Clear all viewer-owned state for a single subwindow."""
    app._reset_fusion_handler_for_subwindow(idx)

    subwindow = app.multi_window_layout.get_subwindow(idx)
    if subwindow and subwindow.image_viewer:
        scene = subwindow.image_viewer.scene

        if idx in app.subwindow_managers:
            managers = app.subwindow_managers[idx]

            roi_manager = managers.get("roi_manager")
            measurement_tool = managers.get("measurement_tool")
            text_annotation_tool = managers.get("text_annotation_tool")
            arrow_annotation_tool = managers.get("arrow_annotation_tool")
            if roi_manager:
                roi_manager.clear_all_rois(scene)
            if measurement_tool:
                measurement_tool.clear_measurements(scene)
            if text_annotation_tool:
                text_annotation_tool.clear_annotations(scene)
            if arrow_annotation_tool:
                arrow_annotation_tool.clear_arrows(scene)

            overlay_manager = managers.get("overlay_manager")
            if overlay_manager:
                overlay_manager.clear_overlay_items(scene)

            slice_display_manager = managers.get("slice_display_manager")
            if slice_display_manager and hasattr(
                slice_display_manager, "clear_display_state"
            ):
                slice_display_manager.clear_display_state()

        scene.clear()
        subwindow.image_viewer.image_item = None
        subwindow.image_viewer.viewport().update()
        try:
            app._slice_location_line_coordinator.remove_manager(idx)
        except Exception:
            pass

    app.subwindow_data[idx] = {
        "current_dataset": None,
        "current_slice_index": 0,
        "current_series_uid": "",
        "current_study_uid": "",
        "current_datasets": [],
    }
    app._sync_navigation_slider_for_subwindow(idx)
    app._refresh_window_slot_map_widgets()


def reset_focused_subwindow_state_after_close(app: Any) -> None:
    """Reset app-level focused-view state after clearing the focused subwindow."""
    app.current_dataset = None
    app.current_study_uid = ""
    app.current_series_uid = ""
    app.current_slice_index = 0
    app.current_datasets = []

    app.slice_navigator.set_total_slices(0)
    app.slice_navigator.set_current_slice(0)

    app.metadata_panel.set_dataset(None)
    app.cine_app_facade.update_cine_player_context()

    app._disconnect_focused_subwindow_signals()
    app._connect_focused_subwindow_signals()

    app.roi_list_panel.update_roi_list("", "", 0)
    app.roi_statistics_panel.clear_statistics()


def clear_subwindow_content(app: Any, idx: int) -> None:
    """Clear one pane while keeping loaded studies/series intact."""
    data = app.subwindow_data.get(idx, {})
    if data.get("current_dataset") is None and not data.get("is_mpr"):
        return
    if idx == app.focused_subwindow_index and getattr(app, "cine_player", None):
        app.cine_player.stop_playback()
    if hasattr(app, "_mpr_controller") and data.get("is_mpr"):
        app._mpr_controller.detach_mpr_from_subwindow(idx)
        if idx == app.focused_subwindow_index:
            app._update_focused_subwindow_references()
        app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())
        return
    clear_subwindow(app, idx)
    if idx == app.focused_subwindow_index:
        reset_focused_subwindow_state_after_close(app)
    app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())


def close_series(app: Any, study_uid: str, series_key: str) -> None:
    """Close a single series and refresh navigator state in one place."""
    series_datasets = app.current_studies.get(study_uid, {}).get(series_key, [])
    if not series_datasets:
        return

    affected_indices = [
        idx
        for idx, data in app.subwindow_data.items()
        if data.get("current_study_uid") == study_uid
        and data.get("current_series_uid") == series_key
    ]

    for ds in series_datasets:
        clear_cached_pixel_array(ds)

    app.dicom_organizer.remove_series(study_uid, series_key)
    if study_uid not in app.dicom_organizer.studies:
        app.annotation_manager.remove_study_annotations(study_uid)

    app.current_studies = app.dicom_organizer.studies
    app._schedule_tag_export_union_rebuild()

    for idx in affected_indices:
        clear_subwindow(app, idx)

    if app.focused_subwindow_index in affected_indices:
        reset_focused_subwindow_state_after_close(app)

    app.series_navigator.update_series_list(
        app.current_studies,
        app.current_study_uid,
        app.current_series_uid,
    )
    app._refresh_series_navigator_state()
    app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())
    app._slice_sync_coordinator.invalidate_cache(study_uid, series_key)


def close_study(app: Any, study_uid: str) -> None:
    """Close a whole study and refresh navigator state in one pass."""
    study_series = app.current_studies.get(study_uid, {})
    if not study_series:
        return

    affected_indices = [
        idx
        for idx, data in app.subwindow_data.items()
        if data.get("current_study_uid") == study_uid
    ]

    for datasets in study_series.values():
        for ds in datasets:
            clear_cached_pixel_array(ds)

    app.dicom_organizer.remove_study(study_uid)
    app.annotation_manager.remove_study_annotations(study_uid)

    app.current_studies = app.dicom_organizer.studies
    app._schedule_tag_export_union_rebuild()

    for idx in affected_indices:
        clear_subwindow(app, idx)

    if app.focused_subwindow_index in affected_indices:
        reset_focused_subwindow_state_after_close(app)

    app.series_navigator.update_series_list(
        app.current_studies,
        app.current_study_uid,
        app.current_series_uid,
    )
    app._refresh_series_navigator_state()
    app.series_navigator.set_subwindow_assignments(app._get_subwindow_assignments())
    app._slice_sync_coordinator.invalidate_cache(study_uid)
