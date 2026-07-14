"""
Image viewer context menus (Phase 3 split).

QMenu construction for ROI / annotation / image background.

Requirements: PySide6; `viewer` is the ImageViewer instance.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QMenu


def toggle_roi_statistic(viewer: Any, roi: Any, stat_name: str, checked: bool) -> None:
    """Toggle a statistic in the ROI's visible_statistics set and notify coordinators."""
    if checked:
        roi.visible_statistics.add(stat_name)
    else:
        roi.visible_statistics.discard(stat_name)
    viewer.roi_statistics_selection_changed.emit(roi, roi.visible_statistics)


def handle_mouse_press_right_button(viewer: Any, event: Any) -> None:
    """
    ROI / measurement / annotation context menus on right press.
    Always fully handles the event; caller should return without calling super().
    """
    # Right click - prepare for potential drag or context menu
    scene_pos = viewer.mapToScene(event.position().toPoint())
    item = viewer.scene.itemAt(scene_pos, viewer.transform())

    from tools.roi_manager import ROIResizeHandleItem

    if isinstance(item, ROIResizeHandleItem):
        item = item.roi_graphics_shape_item()

    # Check if it's a ROI item or measurement item
    from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem

    from tools.angle_measurement_items import (
        AngleMeasurementItem,
        DraggableAngleMeasurementText,
    )
    from tools.measurement_items import DraggableMeasurementText
    from tools.measurement_tool import MeasurementItem

    # Check if item is directly a ROI or measurement
    is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
    is_measurement_item = isinstance(item, (MeasurementItem, AngleMeasurementItem))

    # If not directly a measurement, check if it's a child of a measurement
    if not is_measurement_item and item is not None:
        # Walk up parent chain to find MeasurementItem
        parent = item.parentItem()
        while parent is not None:
            if isinstance(parent, (MeasurementItem, AngleMeasurementItem)):
                is_measurement_item = True
                item = parent  # Use the parent MeasurementItem for the menu
                break
            parent = parent.parentItem()

    if not is_measurement_item and item is not None:
        if (isinstance(item, DraggableAngleMeasurementText) and item.measurement is not None) or (isinstance(item, DraggableMeasurementText) and item.measurement is not None):
            is_measurement_item = True
            item = item.measurement

    if is_roi_item:
        # Show context menu for ROI immediately
        context_menu = QMenu(viewer)

        # Delete action
        delete_action = context_menu.addAction("Delete ROI")
        delete_action.triggered.connect(lambda: viewer.roi_delete_requested.emit(item))

        # Delete all ROIs action
        delete_all_action = context_menu.addAction("Delete all ROIs (D)")
        if viewer.delete_all_rois_callback:
            delete_all_action.triggered.connect(viewer.delete_all_rois_callback)

        context_menu.addSeparator()

        # Statistics Overlay submenu
        stats_submenu = context_menu.addMenu("Statistics Overlay")

        # Get ROI from item using callback
        roi = None
        if viewer.get_roi_from_item_callback:
            roi = viewer.get_roi_from_item_callback(item)

        if roi is not None:
            # Toggle overlay visibility
            toggle_action = stats_submenu.addAction("Show Statistics Overlay")
            toggle_action.setCheckable(True)
            toggle_action.setChecked(roi.statistics_overlay_visible)
            toggle_action.triggered.connect(lambda checked: viewer.roi_statistics_overlay_toggle_requested.emit(roi, checked))

            stats_submenu.addSeparator()

            # Statistics checkboxes
            mean_action = stats_submenu.addAction("Show Mean")
            mean_action.setCheckable(True)
            mean_action.setChecked("mean" in roi.visible_statistics)
            mean_action.triggered.connect(lambda checked: viewer._toggle_statistic(roi, "mean", checked))

            std_action = stats_submenu.addAction("Show Std Dev")
            std_action.setCheckable(True)
            std_action.setChecked("std" in roi.visible_statistics)
            std_action.triggered.connect(lambda checked: viewer._toggle_statistic(roi, "std", checked))

            min_action = stats_submenu.addAction("Show Min")
            min_action.setCheckable(True)
            min_action.setChecked("min" in roi.visible_statistics)
            min_action.triggered.connect(lambda checked: viewer._toggle_statistic(roi, "min", checked))

            max_action = stats_submenu.addAction("Show Max")
            max_action.setCheckable(True)
            max_action.setChecked("max" in roi.visible_statistics)
            max_action.triggered.connect(lambda checked: viewer._toggle_statistic(roi, "max", checked))

            count_action = stats_submenu.addAction("Show Pixels")
            count_action.setCheckable(True)
            count_action.setChecked("count" in roi.visible_statistics)
            count_action.triggered.connect(lambda checked: viewer._toggle_statistic(roi, "count", checked))

            area_action = stats_submenu.addAction("Show Area")
            area_action.setCheckable(True)
            area_action.setChecked("area" in roi.visible_statistics)
            area_action.triggered.connect(lambda checked: viewer._toggle_statistic(roi, "area", checked))

        context_menu.addSeparator()

        # Annotation Options action
        annotation_options_action = context_menu.addAction("Annotation Options...")
        annotation_options_action.triggered.connect(viewer.annotation_options_requested.emit)

        context_menu.exec(event.globalPosition().toPoint())
        viewer.right_mouse_context_menu_shown = True
        return
    elif is_measurement_item:
        # Show context menu for measurement immediately
        context_menu = QMenu(viewer)
        delete_action = context_menu.addAction("Delete Measurement")
        delete_action.triggered.connect(lambda: viewer.measurement_delete_requested.emit(item))

        context_menu.addSeparator()

        # Annotation Options action
        annotation_options_action = context_menu.addAction("Annotation Options...")
        annotation_options_action.triggered.connect(viewer.annotation_options_requested.emit)

        context_menu.exec(event.globalPosition().toPoint())
        viewer.right_mouse_context_menu_shown = True
        return

    # Check if clicking on text annotation item
    from tools.text_annotation_tool import TextAnnotationItem
    is_text_annotation_item = isinstance(item, TextAnnotationItem)

    if is_text_annotation_item:
        # Show context menu for text annotation immediately
        context_menu = QMenu(viewer)
        delete_action = context_menu.addAction("Delete Text Annotation")
        delete_action.triggered.connect(lambda: viewer.text_annotation_delete_requested.emit(item))

        context_menu.addSeparator()

        # Annotation Options action
        annotation_options_action = context_menu.addAction("Annotation Options...")
        annotation_options_action.triggered.connect(viewer.annotation_options_requested.emit)

        context_menu.exec(event.globalPosition().toPoint())
        viewer.right_mouse_context_menu_shown = True
        return

    # Check if clicking on arrow annotation item
    from tools.arrow_annotation_tool import ArrowAnnotationItem
    is_arrow_annotation_item = isinstance(item, ArrowAnnotationItem)

    if is_arrow_annotation_item:
        # Show context menu for arrow annotation immediately
        context_menu = QMenu(viewer)
        delete_action = context_menu.addAction("Delete Arrow")
        delete_action.triggered.connect(lambda: viewer.arrow_annotation_delete_requested.emit(item))

        context_menu.addSeparator()

        # Annotation Options action
        annotation_options_action = context_menu.addAction("Annotation Options...")
        annotation_options_action.triggered.connect(viewer.annotation_options_requested.emit)

        context_menu.exec(event.globalPosition().toPoint())
        viewer.right_mouse_context_menu_shown = True
        return

    # Check if clicking on crosshair item
    from tools.crosshair_manager import CrosshairItem
    is_crosshair_item = (item is not None and
                       item != viewer.image_item and
                       isinstance(item, CrosshairItem))

    if is_crosshair_item:
        # Show context menu for crosshair immediately
        context_menu = QMenu(viewer)
        delete_action = context_menu.addAction("Delete Crosshair")
        delete_action.triggered.connect(lambda: viewer.crosshair_delete_requested.emit(item))

        context_menu.addSeparator()

        # Annotation Options action
        annotation_options_action = context_menu.addAction("Annotation Options...")
        annotation_options_action.triggered.connect(viewer.annotation_options_requested.emit)

        context_menu.exec(event.globalPosition().toPoint())
        viewer.right_mouse_context_menu_shown = True
        return
    else:
        # Not clicking on ROI - prepare for drag or context menu
        # Store initial position for potential drag
        viewer.right_mouse_drag_start_pos = event.position()
        viewer.right_mouse_context_menu_shown = False
        # Request window/level values from main.py
        viewer.right_mouse_press_for_drag.emit()


def show_image_background_context_menu_on_right_release(viewer: Any, event: Any) -> None:
    """After short right-click release on image: scene pick + full image context menu."""
    scene_pos = viewer.mapToScene(event.position().toPoint())
    item = viewer.scene.itemAt(scene_pos, viewer.transform())

    from tools.roi_manager import ROIResizeHandleItem

    if isinstance(item, ROIResizeHandleItem):
        item = item.roi_graphics_shape_item()

    from PySide6.QtWidgets import QGraphicsEllipseItem, QGraphicsRectItem

    from tools.angle_measurement_items import (
        AngleMeasurementItem,
        DraggableAngleMeasurementText,
    )
    from tools.measurement_items import DraggableMeasurementText
    from tools.measurement_tool import MeasurementItem

    # Check if item is directly a ROI or measurement
    is_roi_item = isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem))
    is_measurement_item = isinstance(item, (MeasurementItem, AngleMeasurementItem))

    # If not directly a measurement, check if it's a child of a measurement
    if not is_measurement_item and item is not None:
        # Walk up parent chain to find MeasurementItem
        parent = item.parentItem()
        while parent is not None:
            if isinstance(parent, (MeasurementItem, AngleMeasurementItem)):
                is_measurement_item = True
                item = parent  # Use the parent MeasurementItem for the menu
                break
            parent = parent.parentItem()

    if not is_measurement_item and item is not None:
        if (isinstance(item, DraggableAngleMeasurementText) and item.measurement is not None) or (isinstance(item, DraggableMeasurementText) and item.measurement is not None):
            is_measurement_item = True
            item = item.measurement

    if not is_roi_item and not is_measurement_item:
        # Show context menu for image (not on ROI)
        context_menu = QMenu(viewer)

        # ── Navigation / View ─────────────────────────────────────────────
        reset_action = context_menu.addAction("Reset View (V, Shift+V)")
        reset_action.triggered.connect(viewer.reset_view_requested.emit)

        if hasattr(viewer, 'reset_all_views_requested'):
            reset_all_action = context_menu.addAction("Reset All Views (Shift+A)")
            reset_all_action.triggered.connect(viewer.reset_all_views_requested.emit)

        orientation_menu = context_menu.addMenu("Orientation")
        flip_h_action = orientation_menu.addAction("Flip Horizontal (Alt+H)")
        flip_h_action.triggered.connect(viewer.flip_h)
        flip_v_action = orientation_menu.addAction("Flip Vertical (Alt+V)")
        flip_v_action.triggered.connect(viewer.flip_v)
        orientation_menu.addSeparator()
        rotate_cw_action = orientation_menu.addAction("Rotate 90° CW (Alt+R)")
        rotate_cw_action.triggered.connect(viewer.rotate_cw)
        rotate_ccw_action = orientation_menu.addAction("Rotate 90° CCW (Shift+Alt+R)")
        rotate_ccw_action.triggered.connect(viewer.rotate_ccw)
        rotate_180_action = orientation_menu.addAction("Rotate 180°")
        rotate_180_action.triggered.connect(viewer.rotate_180)
        orientation_menu.addSeparator()
        reset_orientation_action = orientation_menu.addAction("Reset Orientation (Shift+Alt+O)")
        reset_orientation_action.triggered.connect(viewer.reset_orientation)

        context_menu.addSeparator()

        # Layout submenu
        layout_menu = context_menu.addMenu("Layout")
        layout_1x1_action = layout_menu.addAction("1×1  (1)")
        layout_1x1_action.setCheckable(True)
        layout_1x1_action.triggered.connect(lambda: viewer.layout_change_requested.emit("1x1"))

        layout_1x2_action = layout_menu.addAction("1×2  (2 toggles with 2×1)")
        layout_1x2_action.setCheckable(True)
        layout_1x2_action.triggered.connect(lambda: viewer.layout_change_requested.emit("1x2"))

        layout_2x1_action = layout_menu.addAction("2×1")
        layout_2x1_action.setCheckable(True)
        layout_2x1_action.triggered.connect(lambda: viewer.layout_change_requested.emit("2x1"))

        layout_menu.addSeparator()

        layout_1p2r = layout_menu.addAction("Large left + 2 right  (3)")
        layout_1p2r.setCheckable(True)
        layout_1p2r.triggered.connect(lambda: viewer.layout_change_requested.emit("1+2R"))

        layout_2l1 = layout_menu.addAction("2 left + large right")
        layout_2l1.setCheckable(True)
        layout_2l1.triggered.connect(lambda: viewer.layout_change_requested.emit("2L+1"))

        layout_2t1 = layout_menu.addAction("Large top + 2 bottom")
        layout_2t1.setCheckable(True)
        layout_2t1.triggered.connect(lambda: viewer.layout_change_requested.emit("2T+1"))

        layout_1p2b = layout_menu.addAction("2 top + large bottom")
        layout_1p2b.setCheckable(True)
        layout_1p2b.triggered.connect(lambda: viewer.layout_change_requested.emit("1+2B"))

        layout_menu.addSeparator()

        layout_2x2_action = layout_menu.addAction("2×2  (4)")
        layout_2x2_action.setCheckable(True)
        layout_2x2_action.triggered.connect(lambda: viewer.layout_change_requested.emit("2x2"))

        # Swap submenu
        if viewer.subwindow_index is not None:
            swap_menu = context_menu.addMenu("Swap")
            show_map_action = swap_menu.addAction("Show Window Map")
            show_map_action.triggered.connect(viewer.window_slot_map_popup_requested.emit)
            swap_menu.addSeparator()

            slot_to_view = [0, 1, 2, 3]
            if viewer.get_slot_to_view_callback:
                try:
                    stv = viewer.get_slot_to_view_callback()
                    if isinstance(stv, list) and len(stv) >= 4:
                        slot_to_view = stv[:4]
                except Exception:
                    pass
            for k in range(1, 5):
                other_view_index = slot_to_view[k - 1]
                action = swap_menu.addAction(f"Swap with Window {k}")
                if other_view_index == viewer.subwindow_index:
                    action.setEnabled(False)
                else:
                    action.triggered.connect(
                        lambda checked, o=other_view_index: viewer.swap_view_requested.emit(o)
                    )

        clear_cb = getattr(viewer, "get_clear_this_window_enabled_callback", None)
        if clear_cb is not None:
            clear_window_action = context_menu.addAction("Clear This Window")
            clear_window_action.setToolTip(
                "Remove the series from this pane only; studies and series stay in the navigator."
            )
            try:
                clear_window_action.setEnabled(bool(clear_cb()))
            except Exception:
                clear_window_action.setEnabled(False)
            clear_window_action.triggered.connect(viewer.clear_window_content_requested.emit)

        context_menu.addSeparator()

        prev_series_action = context_menu.addAction("Prev Series (←)")
        prev_series_action.triggered.connect(lambda: viewer.series_navigation_requested.emit(-1))
        next_series_action = context_menu.addAction("Next Series (→)")
        next_series_action.triggered.connect(lambda: viewer.series_navigation_requested.emit(1))

        assign_series_menu = context_menu.addMenu("Assign Series to Focused Window")
        if hasattr(viewer, 'get_available_series_callback') and viewer.get_available_series_callback:
            series_list = viewer.get_available_series_callback()
            if series_list:
                for series_uid, series_name in series_list:
                    action = assign_series_menu.addAction(series_name)
                    action.triggered.connect(lambda checked, uid=series_uid: viewer.assign_series_requested.emit(uid))
            else:
                assign_series_menu.setEnabled(False)
        else:
            assign_series_menu.setEnabled(False)

        # MPR view actions (Create or Clear, depending on current mode)
        context_menu.addSeparator()
        _is_mpr = False
        if viewer.is_mpr_view_callback is not None:
            try:
                _is_mpr = bool(viewer.is_mpr_view_callback())
            except Exception:
                pass
        if _is_mpr:
            clear_mpr_action = context_menu.addAction("Clear MPR View")
            clear_mpr_action.triggered.connect(viewer.clear_mpr_view_requested.emit)
        else:
            create_mpr_action = context_menu.addAction("Create MPR View\u2026")
            create_mpr_action.triggered.connect(viewer.create_mpr_view_requested.emit)

        # 3D Volume Render
        view_3d_action = context_menu.addAction("3D Volume Render\u2026")
        view_3d_cb = getattr(viewer, "get_3d_volume_render_enabled_callback", None)
        if view_3d_cb is not None:
            try:
                view_3d_action.setEnabled(bool(view_3d_cb()))
            except Exception:
                view_3d_action.setEnabled(False)
        else:
            view_3d_action.setEnabled(False)
        view_3d_action.triggered.connect(viewer.create_3d_view_requested.emit)

        # ── Tools ► (interaction modes) ───────────────────────────────────
        context_menu.addSeparator()

        # MPR mode restricts interaction types. Crosshair ROI stays off;
        # text/arrow annotations are allowed (see MPR annotations plan).
        _mpr_disabled_modes = (
            {"crosshair"} if viewer._mpr_mode_override else set()
        )
        tools_menu = context_menu.addMenu("Tools")

        _tool_groups = [
            [
                ("Pan (P)", "pan"),
                ("Zoom (Z)", "zoom"),
                ("Select (S)", "select"),
                ("Magnifier (G)", "magnifier"),
            ],
            [
                ("Ellipse ROI (E)", "roi_ellipse"),
                ("Rectangle ROI (R)", "roi_rectangle"),
                ("Crosshair ROI (H)", "crosshair"),
            ],
            [
                ("Measure Distance (M)", "measure"),
                ("Measure Angle (Shift+M)", "measure_angle"),
                ("Window/Level ROI (W)", "auto_window_level"),
            ],
            [
                ("Text Annotation (T)", "text_annotation"),
                ("Arrow Annotation (A)", "arrow_annotation"),
            ],
        ]
        first_group = True
        for group in _tool_groups:
            if not first_group:
                tools_menu.addSeparator()
            first_group = False
            for action_text, mode in group:
                action = tools_menu.addAction(action_text)
                action.setCheckable(True)
                if mode in _mpr_disabled_modes:
                    action.setEnabled(False)
                    action.setToolTip("Not available on MPR views.")
                else:
                    if viewer.mouse_mode == mode:
                        action.setChecked(True)
                    action.triggered.connect(
                        lambda checked, m=mode: viewer.context_menu_mouse_mode_changed.emit(m)
                    )

        # ── Annotations ► ─────────────────────────────────────────────────
        annotations_menu = context_menu.addMenu("Annotations")

        annotation_options_action = annotations_menu.addAction("Annotation Options…")
        annotation_options_action.triggered.connect(viewer.annotation_options_requested.emit)

        annotations_menu.addSeparator()

        delete_all_action = annotations_menu.addAction("Delete all ROIs (D)")
        if viewer.delete_all_rois_callback:
            delete_all_action.triggered.connect(viewer.delete_all_rois_callback)

        clear_measurements_action = annotations_menu.addAction("Clear Measurements (C)")
        clear_measurements_action.triggered.connect(viewer.clear_measurements_requested.emit)

        export_roi_stats_action = annotations_menu.addAction("Export ROI Statistics…")
        export_roi_stats_action.triggered.connect(viewer.export_roi_statistics_requested.emit)

        # ── Display ───────────────────────────────────────────────────────
        context_menu.addSeparator()

        toggle_overlay_action = context_menu.addAction("Toggle Overlay Detail (Space)")
        toggle_overlay_action.triggered.connect(viewer.toggle_overlay_requested.emit)

        privacy_view_action = context_menu.addAction("Privacy View (Ctrl+P)")
        privacy_view_action.setCheckable(True)
        privacy_view_action.setChecked(viewer._privacy_view_enabled)
        privacy_view_action.triggered.connect(lambda checked: viewer.privacy_view_toggled.emit(checked))

        smooth_when_zoomed_action = context_menu.addAction("Image Smoothing")
        smooth_when_zoomed_action.setCheckable(True)
        smooth_when_zoomed_action.setChecked(viewer._smooth_when_zoomed)
        smooth_when_zoomed_action.triggered.connect(lambda checked: viewer.smooth_when_zoomed_toggled.emit(checked))

        scale_markers_action = context_menu.addAction("Show Scale Markers")
        scale_markers_action.setCheckable(True)
        scale_markers_action.setChecked(viewer._show_scale_markers)
        scale_markers_action.triggered.connect(
            lambda checked: viewer.scale_markers_toggled.emit(checked)
        )

        direction_labels_action = context_menu.addAction("Show Direction Labels")
        direction_labels_action.setCheckable(True)
        direction_labels_action.setChecked(viewer._show_direction_labels)
        direction_labels_action.triggered.connect(
            lambda checked: viewer.direction_labels_toggled.emit(checked)
        )

        overlay_config_action = context_menu.addAction("Overlay Tags Configuration…")
        overlay_config_action.triggered.connect(viewer.overlay_config_requested.emit)

        overlay_settings_action = context_menu.addAction("Overlay Settings…")
        overlay_settings_action.triggered.connect(viewer.overlay_settings_requested.emit)

        context_menu.addSeparator()

        # Slice Sync submenu
        slice_sync_menu = context_menu.addMenu("Slice Sync")
        slice_sync_action = slice_sync_menu.addAction("Enable Slice Sync")
        slice_sync_action.setCheckable(True)
        slice_sync_action.setChecked(viewer._slice_sync_enabled)
        slice_sync_action.triggered.connect(
            lambda checked: viewer.slice_sync_toggled.emit(checked)
        )
        manage_sync_groups_action = slice_sync_menu.addAction("Manage Sync Groups…")
        manage_sync_groups_action.triggered.connect(
            viewer.slice_sync_manage_requested.emit
        )

        # Show Lines submenu (slice location lines across views)
        show_lines_menu = context_menu.addMenu("Show Slice Location Lines")
        enable_lines_action = show_lines_menu.addAction("Enable/Disable")
        enable_lines_action.setCheckable(True)
        cb_vis = viewer.get_slice_location_lines_visible_callback
        enable_lines_action.setChecked(cb_vis() if cb_vis is not None else False)
        enable_lines_action.triggered.connect(
            lambda checked: viewer.slice_location_lines_toggled.emit(checked)
        )
        same_group_action = show_lines_menu.addAction("Only Show For Same Group")
        same_group_action.setCheckable(True)
        cb_sg = viewer.get_slice_location_lines_same_group_only_callback
        same_group_action.setChecked(cb_sg() if cb_sg is not None else False)
        same_group_action.triggered.connect(
            lambda checked: viewer.slice_location_lines_same_group_only_toggled.emit(checked)
        )
        focused_only_action = show_lines_menu.addAction("Show Only For Focused Window")
        focused_only_action.setCheckable(True)
        cb_fo = viewer.get_slice_location_lines_focused_only_callback
        focused_only_action.setChecked(cb_fo() if cb_fo is not None else False)
        focused_only_action.triggered.connect(
            lambda checked: viewer.slice_location_lines_focused_only_toggled.emit(checked)
        )
        show_lines_menu.addSeparator()
        slab_bounds_action = show_lines_menu.addAction("Show Slab Boundaries (Begin/End) Instead of Centre")
        slab_bounds_action.setCheckable(True)
        cb_mode = viewer.get_slice_location_lines_mode_callback
        slab_bounds_action.setChecked((cb_mode() if cb_mode is not None else "middle") == "begin_end")
        slab_bounds_action.triggered.connect(
            lambda checked: viewer.slice_location_lines_mode_toggled.emit("begin_end" if checked else "middle")
        )

        show_hide_left_pane_action = context_menu.addAction("Show/Hide Left Pane")
        show_hide_left_pane_action.triggered.connect(viewer.left_pane_toggle_requested.emit)
        show_hide_right_pane_action = context_menu.addAction("Show/Hide Right Pane")
        show_hide_right_pane_action.triggered.connect(viewer.right_pane_toggle_requested.emit)
        show_hide_series_navigator_action = context_menu.addAction("Show/Hide Series Navigator")
        show_hide_series_navigator_action.triggered.connect(viewer.toggle_series_navigator_requested.emit)

        # ── Window / Level ────────────────────────────────────────────────
        context_menu.addSeparator()

        # Window/Level Presets submenu (grouped by source)
        preset_menu = context_menu.addMenu("Window/Level Presets")
        ctx_cb: Callable[[], Any] | None = getattr(viewer, "get_wl_preset_menu_context_callback", None)
        manage_cb: Callable[[], None] | None = getattr(viewer, "manage_wl_presets_callback", None)
        if callable(ctx_cb):
            from gui.wl_preset_menu import WLPresetMenuContext, populate_wl_preset_menu

            ctx = ctx_cb()
            if ctx is None:
                ctx = WLPresetMenuContext(preset_objects=[], current_index=0)
            populate_wl_preset_menu(
                preset_menu,
                ctx,
                lambda i: viewer.window_level_preset_selected.emit(i),
                on_manage=manage_cb if callable(manage_cb) else None,
            )
        elif (
            hasattr(viewer, "get_window_level_presets_callback")
            and viewer.get_window_level_presets_callback
        ):
            presets = viewer.get_window_level_presets_callback()
            if presets:
                from gui.wl_preset_menu import (
                    context_from_legacy_presets,
                    populate_wl_preset_menu,
                )

                current_index = 0
                if (
                    hasattr(viewer, "get_current_preset_index_callback")
                    and viewer.get_current_preset_index_callback
                ):
                    current_index = viewer.get_current_preset_index_callback()
                ctx = context_from_legacy_presets(presets, current_index=current_index)
                populate_wl_preset_menu(
                    preset_menu,
                    ctx,
                    lambda i: viewer.window_level_preset_selected.emit(i),
                    on_manage=manage_cb if callable(manage_cb) else None,
                )
            elif callable(manage_cb):
                from gui.wl_preset_menu import (
                    WLPresetMenuContext,
                    populate_wl_preset_menu,
                )

                populate_wl_preset_menu(
                    preset_menu,
                    WLPresetMenuContext(preset_objects=[], current_index=0),
                    lambda i: viewer.window_level_preset_selected.emit(i),
                    on_manage=manage_cb,
                )

        quick_wl_action = context_menu.addAction("Quick Window/Level (Q)")
        quick_wl_action.triggered.connect(viewer.quick_window_level_requested.emit)

        invert_action = context_menu.addAction("Invert Image (I)")
        invert_action.setCheckable(True)
        invert_action.setChecked(viewer.image_inverted)
        invert_action.triggered.connect(viewer.invert_image)

        use_raw_action = context_menu.addAction("Use Raw Pixel Values")
        use_raw_action.setCheckable(True)
        use_raw_action.setChecked(not viewer.use_rescaled_values)
        use_raw_action.triggered.connect(
            lambda: viewer.context_menu_rescale_toggle_changed.emit(False)
        )

        use_rescaled_action = context_menu.addAction("Use Rescaled Values")
        use_rescaled_action.setCheckable(True)
        use_rescaled_action.setChecked(viewer.use_rescaled_values)
        use_rescaled_action.triggered.connect(
            lambda: viewer.context_menu_rescale_toggle_changed.emit(True)
        )

        scroll_wheel_menu = context_menu.addMenu("Scroll Wheel Mode")
        slice_action = scroll_wheel_menu.addAction("Slice")
        slice_action.setCheckable(True)
        if viewer.scroll_wheel_mode == "slice":
            slice_action.setChecked(True)
        slice_action.triggered.connect(
            lambda: viewer.context_menu_scroll_wheel_mode_changed.emit("slice")
        )
        zoom_action = scroll_wheel_menu.addAction("Zoom")
        zoom_action.setCheckable(True)
        if viewer.scroll_wheel_mode == "zoom":
            zoom_action.setChecked(True)
        zoom_action.triggered.connect(
            lambda: viewer.context_menu_scroll_wheel_mode_changed.emit("zoom")
        )

        # Combine Slices submenu
        combine_menu = context_menu.addMenu("Combine Slices…")
        enable_action = combine_menu.addAction("Enable Combine Slices")
        enable_action.setCheckable(True)
        if viewer.get_projection_enabled_callback:
            enable_action.setChecked(viewer.get_projection_enabled_callback())
        enable_action.triggered.connect(
            lambda checked: viewer.projection_enabled_changed.emit(checked)
        )
        combine_menu.addSeparator()

        projection_type_menu = combine_menu.addMenu("Projection Type")
        from PySide6.QtGui import QActionGroup
        projection_type_group = QActionGroup(projection_type_menu)
        projection_type_group.setExclusive(True)

        aip_action = projection_type_menu.addAction("Average (AIP)")
        aip_action.setCheckable(True)
        projection_type_group.addAction(aip_action)
        if viewer.get_projection_type_callback:
            aip_action.setChecked(viewer.get_projection_type_callback() == "aip")
        aip_action.triggered.connect(lambda: viewer.projection_type_changed.emit("aip"))

        mip_action = projection_type_menu.addAction("Maximum (MIP)")
        mip_action.setCheckable(True)
        projection_type_group.addAction(mip_action)
        if viewer.get_projection_type_callback:
            mip_action.setChecked(viewer.get_projection_type_callback() == "mip")
        mip_action.triggered.connect(lambda: viewer.projection_type_changed.emit("mip"))

        minip_action = projection_type_menu.addAction("Minimum (MinIP)")
        minip_action.setCheckable(True)
        projection_type_group.addAction(minip_action)
        if viewer.get_projection_type_callback:
            minip_action.setChecked(viewer.get_projection_type_callback() == "minip")
        minip_action.triggered.connect(lambda: viewer.projection_type_changed.emit("minip"))

        slice_count_menu = combine_menu.addMenu("Slice Count")
        slice_count_group = QActionGroup(slice_count_menu)
        slice_count_group.setExclusive(True)
        for count in [2, 3, 4, 6, 8]:
            count_action = slice_count_menu.addAction(str(count))
            count_action.setCheckable(True)
            slice_count_group.addAction(count_action)
            if viewer.get_projection_slice_count_callback:
                count_action.setChecked(viewer.get_projection_slice_count_callback() == count)
            count_action.triggered.connect(
                lambda checked, c=count: viewer.projection_slice_count_changed.emit(c) if checked else None
            )

        # ── Cine ─────────────────────────────────────────────────────────
        if viewer.cine_controls_enabled:
            context_menu.addSeparator()
            playing = False
            gcp = getattr(viewer, "get_cine_is_playing_callback", None)
            if gcp is not None:
                try:
                    playing = bool(gcp())
                except Exception:
                    playing = False
            pp_label = "⏸ Pause Cine" if playing else "▶ Play Cine"
            cine_pp_action = context_menu.addAction(pp_label)
            cine_pp_action.setToolTip("Play or pause cine playback (same as the left pane control)")
            cine_pp_action.triggered.connect(viewer.cine_play_pause_toggle_requested.emit)

            cine_stop_action = context_menu.addAction("⏹ Stop Cine")
            cine_stop_action.triggered.connect(viewer.cine_stop_requested.emit)

            cine_loop_action = context_menu.addAction("Loop Cine")
            cine_loop_action.setCheckable(True)
            if viewer.get_cine_loop_state_callback is not None:
                loop_enabled = viewer.get_cine_loop_state_callback()
                cine_loop_action.setChecked(loop_enabled)
            cine_loop_action.triggered.connect(
                lambda checked: viewer.cine_loop_toggled.emit(checked)
            )

        # ── Info / File ───────────────────────────────────────────────────
        context_menu.addSeparator()

        import sys
        shortcut_text = "Cmd+Shift+H" if sys.platform == "darwin" else "Ctrl+Shift+H"
        histogram_action = context_menu.addAction(f"Histogram ({shortcut_text})")
        histogram_action.triggered.connect(viewer.histogram_requested.emit)

        sr_action = context_menu.addAction("Structured Report…")
        sr_visible = False
        gds = getattr(viewer, "get_current_dataset_callback", None)
        if gds is not None:
            try:
                _ds = gds()
                if _ds is not None:
                    from core.sr_sop_classes import is_structured_report_dataset
                    sr_visible = bool(is_structured_report_dataset(_ds))
            except Exception:
                sr_visible = False
        sr_action.setVisible(sr_visible)
        sr_action.triggered.connect(viewer.structured_report_browser_requested.emit)

        about_this_file_action = context_menu.addAction("DICOM File Info…")
        about_this_file_action.triggered.connect(viewer.about_this_file_requested.emit)

        show_file_action = context_menu.addAction("Show File in File Explorer")
        show_file_enabled = False
        if viewer.get_file_path_callback:
            try:
                file_path = viewer.get_file_path_callback()
                if file_path:
                    show_file_enabled = True
                    show_file_action.triggered.connect(
                        lambda: viewer._on_show_file_requested()
                    )
            except Exception:
                pass
        show_file_action.setEnabled(show_file_enabled)

        context_menu.exec(event.globalPosition().toPoint())
