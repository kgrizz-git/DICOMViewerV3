"""
Overlay, annotation, and settings-applied handlers.

These functions push overlay font/mode/visibility changes, annotation style
updates, and general settings-applied side-effects across all subwindows.
Extracted from ``main.py`` to reduce its coordination burden.
"""

from __future__ import annotations

from typing import Any


def apply_imported_customizations(app: Any) -> None:
    """Apply imported customization settings: overlay font, overlay refresh, annotations, theme, metadata columns."""
    font_size = app.config_manager.get_overlay_font_size()
    font_color = app.config_manager.get_overlay_font_color()
    font_family = app.config_manager.get_overlay_font_family()
    font_variant = app.config_manager.get_overlay_font_variant()
    scale_markers_color = app.config_manager.get_scale_markers_color()
    direction_labels_color = app.config_manager.get_direction_labels_color()
    direction_label_size = app.config_manager.get_direction_label_size()
    major_tick_interval_mm = app.config_manager.get_scale_markers_major_tick_interval_mm()
    minor_tick_interval_mm = app.config_manager.get_scale_markers_minor_tick_interval_mm()
    app.overlay_manager.set_font_size(font_size)
    app.overlay_manager.set_font_color(*font_color)
    app.overlay_manager.set_font_family(font_family)
    app.overlay_manager.set_font_variant(font_variant)
    subwindows = app.multi_window_layout.get_all_subwindows()
    for idx, subwindow in enumerate(subwindows):
        if subwindow and subwindow.image_viewer:
            subwindow.image_viewer.set_scale_markers_color_state(scale_markers_color)
            subwindow.image_viewer.set_direction_labels_color_state(direction_labels_color)
            subwindow.image_viewer.set_direction_label_size_state(direction_label_size)
            subwindow.image_viewer.set_scale_markers_tick_intervals_state(
                major_tick_interval_mm,
                minor_tick_interval_mm,
            )
        if subwindow and idx in app.subwindow_managers:
            om = app.subwindow_managers[idx].get("overlay_manager")
            if om:
                om.set_font_size(font_size)
                om.set_font_color(*font_color)
                om.set_font_family(font_family)
                om.set_font_variant(font_variant)
    refresh_overlay_all_subwindows(app)
    on_annotation_options_applied(app)
    theme = app.config_manager.get_theme()
    app.main_window._set_theme(theme)
    widths = app.config_manager.get_metadata_panel_column_widths()
    if len(widths) == 4:
        app.metadata_panel.tree_widget.setColumnWidth(0, widths[0])
        app.metadata_panel.tree_widget.setColumnWidth(1, widths[1])
        app.metadata_panel.tree_widget.setColumnWidth(2, widths[2])
        app.metadata_panel.tree_widget.setColumnWidth(3, widths[3])


def sync_all_overlay_managers_from_config(app: Any) -> None:
    """Apply persisted overlay mode and visibility state to every pane's OverlayManager."""
    mode = app.config_manager.get_overlay_mode()
    vis = app.config_manager.get_overlay_visibility_state()
    for managers in app.subwindow_managers.values():
        om = managers.get("overlay_manager")
        if om is not None:
            om.set_mode(mode)
            om.set_visibility_state(vis)


def cycle_overlay_detail_mode(app: Any) -> None:
    """Cycle corner overlay detail across all panes: minimal -> detailed -> hidden -> minimal."""
    order = ("minimal", "detailed", "hidden")
    cur = app.config_manager.get_overlay_mode()
    if cur not in order:
        cur = "minimal"
    nxt = order[(order.index(cur) + 1) % len(order)]
    app.config_manager.set_overlay_mode(nxt)
    app.config_manager.set_overlay_visibility_state(0)
    for managers in app.subwindow_managers.values():
        om = managers.get("overlay_manager")
        if om is not None:
            om.set_mode(nxt)
            om.set_visibility_state(0)
        oc = managers.get("overlay_coordinator")
        if oc is not None:
            oc.restore_measurement_and_roi_visibility()
    refresh_overlay_all_subwindows(app)


def on_overlay_config_applied(app: Any) -> None:
    """Handle overlay configuration being applied."""
    sync_all_overlay_managers_from_config(app)
    refresh_overlay_all_subwindows(app)
    app._refresh_slice_sync_group_indicators()


def refresh_overlay_all_subwindows(app: Any) -> None:
    """Recreate corner overlays in every subwindow that has overlay coordinators."""
    subwindows = app.multi_window_layout.get_all_subwindows()
    for idx, subwindow in enumerate(subwindows):
        if not subwindow or idx not in app.subwindow_managers:
            continue

        mpr_controller = getattr(app, "_mpr_controller", None)
        if mpr_controller is not None:
            try:
                if mpr_controller.is_mpr(idx):
                    data = app.subwindow_data.get(idx, {})
                    slice_index = data.get("mpr_slice_index", data.get("current_slice_index", 0))
                    mpr_controller.display_mpr_slice(idx, slice_index)
                    continue
            except Exception:
                pass

        oc = app.subwindow_managers[idx].get("overlay_coordinator")
        if oc:
            oc.handle_overlay_config_applied()


def on_annotation_options_applied(app: Any) -> None:
    """Handle annotation options applied - refresh all annotations."""
    default_stats_list = app.config_manager.get_roi_default_visible_statistics()
    default_stats_set = set(default_stats_list)

    subwindows = app.multi_window_layout.get_all_subwindows()
    for idx, _subwindow in enumerate(subwindows):
        if idx not in app.subwindow_managers:
            continue
        managers = app.subwindow_managers[idx]
        roi_mgr = managers.get("roi_manager")
        if roi_mgr:
            for _key, roi_list in roi_mgr.rois.items():
                for roi in roi_list:
                    roi.visible_statistics = default_stats_set.copy()
            roi_mgr.update_all_roi_styles(app.config_manager)
        meas_tool = managers.get("measurement_tool")
        if meas_tool:
            meas_tool.update_all_measurement_styles(app.config_manager)
        text_tool = managers.get("text_annotation_tool")
        if text_tool:
            text_tool.update_all_annotation_styles(app.config_manager)
        arrow_tool = managers.get("arrow_annotation_tool")
        if arrow_tool:
            arrow_tool.update_all_arrow_styles(app.config_manager)
        data = app.subwindow_data.get(idx, {})
        current_ds = data.get("current_dataset")
        sdm = managers.get("slice_display_manager")
        if sdm and current_ds is not None:
            sdm.display_rois_for_slice(current_ds)
            sdm.display_measurements_for_slice(current_ds)


def on_settings_applied(app: Any) -> None:
    """Handle settings being applied."""
    from utils.debug_log import configure_debug_logging

    configure_debug_logging(
        app.config_manager.get_diagnostics_enabled(),
        path=app.config_manager.get_diagnostics_log_path(),
    )
    if hasattr(app, "_mpr_controller"):
        app._mpr_controller.apply_cache_settings()
    app.main_window._apply_theme()
    if app.main_window.apply_toolbar_label_style is not None:
        app.main_window.apply_toolbar_label_style(
            app.config_manager.get_toolbar_label_style()
        )
    font_size = app.config_manager.get_overlay_font_size()
    font_color = app.config_manager.get_overlay_font_color()
    font_family = app.config_manager.get_overlay_font_family()
    font_variant = app.config_manager.get_overlay_font_variant()
    direction_label_size = app.config_manager.get_direction_label_size()
    major_tick_interval_mm = app.config_manager.get_scale_markers_major_tick_interval_mm()
    minor_tick_interval_mm = app.config_manager.get_scale_markers_minor_tick_interval_mm()

    app.overlay_manager.set_font_size(font_size)
    app.overlay_manager.set_font_color(*font_color)
    app.overlay_manager.set_font_family(font_family)
    app.overlay_manager.set_font_variant(font_variant)

    show_scale_markers = app.config_manager.get_show_scale_markers()
    show_direction_labels = app.config_manager.get_show_direction_labels()
    subwindows = app.multi_window_layout.get_all_subwindows()
    for idx, subwindow in enumerate(subwindows):
        if subwindow and idx in app.subwindow_managers:
            om = app.subwindow_managers[idx].get('overlay_manager')
            if om:
                om.set_font_size(font_size)
                om.set_font_color(*font_color)
                om.set_font_family(font_family)
                om.set_font_variant(font_variant)
            subwindow.image_viewer.set_scale_markers_state(show_scale_markers)
            subwindow.image_viewer.set_direction_labels_state(show_direction_labels)
            subwindow.image_viewer.set_scale_markers_color_state(
                app.config_manager.get_scale_markers_color()
            )
            subwindow.image_viewer.set_direction_labels_color_state(
                app.config_manager.get_direction_labels_color()
            )
            subwindow.image_viewer.set_direction_label_size_state(direction_label_size)
            subwindow.image_viewer.set_scale_markers_tick_intervals_state(
                major_tick_interval_mm,
                minor_tick_interval_mm,
            )

    refresh_overlay_all_subwindows(app)
    app._slice_location_line_coordinator.refresh_all()
    app._refresh_slice_sync_group_indicators()


def on_overlay_font_size_changed(app: Any, font_size: int) -> None:
    """Handle overlay font size change from toolbar - update ALL subwindows."""
    subwindows = app.multi_window_layout.get_all_subwindows()
    for idx, subwindow in enumerate(subwindows):
        if subwindow and idx in app.subwindow_managers:
            managers = app.subwindow_managers[idx]
            overlay_manager = managers.get('overlay_manager')
            overlay_coordinator = managers.get('overlay_coordinator')

            if overlay_manager:
                overlay_manager.set_font_size(font_size)

                if overlay_coordinator:
                    overlay_coordinator.handle_overlay_font_size_changed(font_size)


def on_overlay_font_color_changed(app: Any, r: int, g: int, b: int) -> None:
    """Handle overlay font color change from toolbar - update ALL subwindows."""
    subwindows = app.multi_window_layout.get_all_subwindows()
    for idx, subwindow in enumerate(subwindows):
        if subwindow and idx in app.subwindow_managers:
            managers = app.subwindow_managers[idx]
            overlay_manager = managers.get('overlay_manager')
            overlay_coordinator = managers.get('overlay_coordinator')

            if overlay_manager:
                overlay_manager.set_font_color(r, g, b)

                if overlay_coordinator:
                    overlay_coordinator.handle_overlay_font_color_changed(r, g, b)
