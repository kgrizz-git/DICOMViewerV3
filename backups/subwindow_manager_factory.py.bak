"""
Per-subwindow manager graph construction for DICOM Viewer V3.

Builds the full dict of ROI, measurement, annotation, overlay, view-state,
slice-display, fusion, and coordinator objects for one ``SubWindowContainer``.
Extracted from ``main.DICOMViewerApp`` so the composition root stays smaller
while preserving identical wiring and lambda closures.

Inputs:
    app: ``DICOMViewerApp`` instance (duck-typed: attributes referenced below).
    idx: Subwindow index (0..N-1) used in lambdas and callbacks.
    subwindow: ``SubWindowContainer`` with ``image_viewer`` set.

Outputs:
    ``managers`` dict keyed by string names (``roi_manager``, ``slice_display_manager``, etc.).

Requirements:
    PySide6; same modules as ``main.py`` for managers and coordinators.
    This module does **not** import ``main`` (avoids circular import).
"""

from __future__ import annotations

from typing import Any, Dict

from gui.sub_window_container import SubWindowContainer
from gui.overlay_manager import OverlayManager
from gui.roi_coordinator import ROICoordinator
from gui.measurement_coordinator import MeasurementCoordinator
from gui.crosshair_coordinator import CrosshairCoordinator
from gui.overlay_coordinator import OverlayCoordinator
from gui.text_annotation_coordinator import TextAnnotationCoordinator
from gui.arrow_annotation_coordinator import ArrowAnnotationCoordinator
from gui.fusion_coordinator import FusionCoordinator

from tools.roi_manager import ROIManager
from tools.measurement_tool import MeasurementTool
from tools.crosshair_manager import CrosshairManager
from tools.text_annotation_tool import TextAnnotationTool
from tools.arrow_annotation_tool import ArrowAnnotationTool

from core.view_state_manager import ViewStateManager
from core.slice_display_manager import SliceDisplayManager
from core.fusion_handler import FusionHandler


def build_managers_for_subwindow(
    app: Any,
    idx: int,
    subwindow: SubWindowContainer,
) -> Dict[str, Any]:
    """
    Build the full set of per-subwindow managers for the given subwindow.
    Used by ``_initialize_subwindow_managers`` and ``_create_managers_for_subwindow``.
    """
    image_viewer = subwindow.image_viewer
    scroll_mode = app.config_manager.get_scroll_wheel_mode()
    image_viewer.set_scroll_wheel_mode(scroll_mode)

    managers: Dict[str, Any] = {}
    managers["roi_manager"] = ROIManager(config_manager=app.config_manager)
    managers["measurement_tool"] = MeasurementTool(config_manager=app.config_manager)
    managers["text_annotation_tool"] = TextAnnotationTool(config_manager=app.config_manager)
    managers["arrow_annotation_tool"] = ArrowAnnotationTool(config_manager=app.config_manager)
    managers["crosshair_manager"] = CrosshairManager(config_manager=app.config_manager)
    managers["crosshair_manager"].set_privacy_mode(app.privacy_view_enabled)
    font_size = app.config_manager.get_overlay_font_size()
    font_color = app.config_manager.get_overlay_font_color()
    font_family = app.config_manager.get_overlay_font_family()
    font_variant = app.config_manager.get_overlay_font_variant()
    managers["overlay_manager"] = OverlayManager(
        font_size=font_size,
        font_color=font_color,
        font_family=font_family,
        font_variant=font_variant,
        config_manager=app.config_manager,
    )
    managers["overlay_manager"].set_privacy_mode(app.privacy_view_enabled)
    managers["view_state_manager"] = ViewStateManager(
        app.dicom_processor,
        image_viewer,
        app.window_level_controls,
        app.main_window,
        managers["overlay_manager"],
        overlay_coordinator=None,
        roi_coordinator=None,
        display_rois_for_slice=None,
    )
    managers["slice_display_manager"] = SliceDisplayManager(
        app.dicom_processor,
        image_viewer,
        app.metadata_panel,
        app.slice_navigator,
        app.window_level_controls,
        managers["roi_manager"],
        managers["measurement_tool"],
        overlay_manager=managers["overlay_manager"],
        view_state_manager=managers["view_state_manager"],
        text_annotation_tool=managers.get("text_annotation_tool"),
        arrow_annotation_tool=managers.get("arrow_annotation_tool"),
        update_tag_viewer_callback=app._update_tag_viewer,
        display_rois_callback=None,
        display_measurements_callback=None,
        roi_list_panel=app.roi_list_panel,
        roi_statistics_panel=app.roi_statistics_panel,
        update_roi_statistics_overlays_callback=None,
        annotation_manager=app.annotation_manager,
        dicom_organizer=app.dicom_organizer,
    )
    managers["crosshair_coordinator"] = CrosshairCoordinator(
        managers["crosshair_manager"],
        image_viewer,
        get_current_dataset=lambda i=idx: app._get_subwindow_dataset(i),
        get_current_slice_index=lambda i=idx: app._get_subwindow_slice_index(i),
        undo_redo_manager=app.undo_redo_manager,
        update_undo_redo_state_callback=app._update_undo_redo_state,
        get_use_rescaled_values=lambda i=idx: (
            managers["view_state_manager"].use_rescaled_values
            if managers["view_state_manager"]
            else False
        ),
    )
    managers["roi_coordinator"] = ROICoordinator(
        managers["roi_manager"],
        app.roi_list_panel,
        app.roi_statistics_panel,
        image_viewer,
        app.dicom_processor,
        app.window_level_controls,
        app.main_window,
        get_current_dataset=lambda i=idx: app._get_subwindow_dataset(i),
        get_current_slice_index=lambda i=idx: app._get_subwindow_slice_index(i),
        get_rescale_params=lambda i=idx: app._get_subwindow_rescale_params(i),
        set_mouse_mode_callback=app._set_mouse_mode_via_handler,
        get_projection_enabled=lambda i=idx: (
            m.projection_enabled if (m := app._get_subwindow_slice_display_manager(i)) else False
        ),
        get_projection_type=lambda i=idx: (
            m.projection_type if (m := app._get_subwindow_slice_display_manager(i)) else "aip"
        ),
        get_projection_slice_count=lambda i=idx: (
            m.projection_slice_count if (m := app._get_subwindow_slice_display_manager(i)) else 4
        ),
        get_current_studies=lambda: app.current_studies,
        get_mpr_pixel_array=lambda i=idx: app._get_subwindow_mpr_pixel_array(i),
        get_mpr_output_pixel_spacing=lambda i=idx: app._get_subwindow_mpr_output_pixel_spacing(i),
        undo_redo_manager=app.undo_redo_manager,
        update_undo_redo_state_callback=app._update_undo_redo_state,
        crosshair_coordinator=managers["crosshair_coordinator"],
    )
    managers["measurement_coordinator"] = MeasurementCoordinator(
        managers["measurement_tool"],
        image_viewer,
        get_current_dataset=lambda i=idx: app._get_subwindow_dataset(i),
        get_current_slice_index=lambda i=idx: app._get_subwindow_slice_index(i),
        undo_redo_manager=app.undo_redo_manager,
        update_undo_redo_state_callback=app._update_undo_redo_state,
    )
    managers["text_annotation_coordinator"] = TextAnnotationCoordinator(
        managers["text_annotation_tool"],
        image_viewer,
        get_current_dataset=lambda i=idx: app._get_subwindow_dataset(i),
        get_current_slice_index=lambda i=idx: app._get_subwindow_slice_index(i),
        undo_redo_manager=app.undo_redo_manager,
        update_undo_redo_state_callback=app._update_undo_redo_state,
    )
    managers["arrow_annotation_coordinator"] = ArrowAnnotationCoordinator(
        managers["arrow_annotation_tool"],
        image_viewer,
        get_current_dataset=lambda i=idx: app._get_subwindow_dataset(i),
        get_current_slice_index=lambda i=idx: app._get_subwindow_slice_index(i),
        undo_redo_manager=app.undo_redo_manager,
        update_undo_redo_state_callback=app._update_undo_redo_state,
    )
    managers["overlay_coordinator"] = OverlayCoordinator(
        managers["overlay_manager"],
        image_viewer,
        get_current_dataset=lambda i=idx: app._get_subwindow_dataset(i),
        get_current_studies=lambda: app.current_studies,
        get_current_study_uid=lambda i=idx: app._get_subwindow_study_uid(i),
        get_current_series_uid=lambda i=idx: app._get_subwindow_series_uid(i),
        get_current_slice_index=lambda i=idx: app._get_subwindow_slice_index(i),
        get_multiframe_overlay_context=lambda dataset=None, study_uid=None, series_uid=None, i=idx: (
            app.subwindow_managers[i]["slice_display_manager"].get_multiframe_overlay_context(
                dataset=dataset,
                study_uid=study_uid,
                series_uid=series_uid,
            )
            if i in app.subwindow_managers
            and app.subwindow_managers[i].get("slice_display_manager")
            else None
        ),
        hide_measurement_labels=managers["measurement_coordinator"].hide_measurement_labels,
        hide_measurement_graphics=managers["measurement_coordinator"].hide_measurement_graphics,
        hide_roi_graphics=(
            managers["roi_coordinator"].hide_roi_graphics
            if hasattr(managers["roi_coordinator"], "hide_roi_graphics")
            else None
        ),
        hide_roi_statistics_overlays=managers["roi_coordinator"].hide_roi_statistics_overlays,
    )
    managers["fusion_handler"] = FusionHandler()
    managers["fusion_coordinator"] = FusionCoordinator(
        managers["fusion_handler"],
        app.fusion_processor,
        app.fusion_controls_widget,
        get_current_studies=lambda: app.current_studies,
        get_current_study_uid=lambda: app.current_study_uid,
        get_current_series_uid=lambda: app.current_series_uid,
        get_current_slice_index=lambda: app.current_slice_index,
        request_display_update=lambda i=idx: app._redisplay_subwindow_slice(i, preserve_view=True),
        check_notification_shown=lambda uid: app.has_shown_fusion_notification(uid),
        mark_notification_shown=lambda uid: app.mark_fusion_notification_shown(uid),
    )
    managers["slice_display_manager"].fusion_coordinator = managers["fusion_coordinator"]
    managers["view_state_manager"].overlay_coordinator = (
        managers["overlay_coordinator"].handle_overlay_config_applied
    )
    managers["view_state_manager"].roi_coordinator = lambda dataset: managers[
        "roi_coordinator"
    ].update_roi_statistics(managers["roi_manager"].get_selected_roi()) if managers[
        "roi_manager"
    ].get_selected_roi() else None
    managers["view_state_manager"].display_rois_for_slice = (
        lambda preserve_view=False: app._display_rois_for_subwindow(idx, preserve_view)
    )
    managers["view_state_manager"].set_redisplay_slice_callback(
        lambda preserve_view=False: app._redisplay_subwindow_slice(idx, preserve_view)
    )
    managers["view_state_manager"].set_series_navigator(app.series_navigator)
    managers["slice_display_manager"].update_roi_statistics_overlays_callback = managers[
        "roi_coordinator"
    ].update_roi_statistics_overlays

    def on_inversion_state_changed(inverted: bool, i=idx) -> None:
        if managers["view_state_manager"].current_series_identifier:
            managers["view_state_manager"].set_series_inversion_state(
                managers["view_state_manager"].current_series_identifier,
                inverted,
            )

    image_viewer.inversion_state_changed_callback = on_inversion_state_changed
    return managers
