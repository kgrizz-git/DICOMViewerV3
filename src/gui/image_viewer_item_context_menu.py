"""
Image viewer item context menus (split out of image_viewer_context_menu).

Immediate right-press QMenu construction for ROI / measurement / annotation /
crosshair items. See ``image_viewer_context_menu`` for the image-background
context menu shown on right-release.

Requirements: PySide6; `viewer` is the ImageViewer instance.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMenu

_ACTION_ANNOTATION_OPTIONS = "Annotation Options..."


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
        annotation_options_action = context_menu.addAction(_ACTION_ANNOTATION_OPTIONS)
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
        annotation_options_action = context_menu.addAction(_ACTION_ANNOTATION_OPTIONS)
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
        annotation_options_action = context_menu.addAction(_ACTION_ANNOTATION_OPTIONS)
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
        annotation_options_action = context_menu.addAction(_ACTION_ANNOTATION_OPTIONS)
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
        annotation_options_action = context_menu.addAction(_ACTION_ANNOTATION_OPTIONS)
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
