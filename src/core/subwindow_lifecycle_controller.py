"""
Subwindow Lifecycle Controller

This module owns subwindow getters and (in later phases) focus/panel updates and
signal connect/disconnect/layout for the multi-subwindow DICOM viewer. Step 1
provides only getter methods; focus/panel and connect/disconnect methods are
added in Phase 3.3/3.4.

Purpose:
    - Provide a single place for subwindow index, dataset, slice, managers, and
      focused subwindow access so main.py and other coordinators can delegate here.

Inputs:
    - App reference (DICOMViewerApp instance) providing multi_window_layout,
      subwindow_managers, subwindow_data, focused_subwindow_index.

Outputs:
    - Subwindow/index and data: dataset, slice index, slice_display_manager,
      study_uid, series_uid; focused subwindow index; histogram callbacks per subwindow;
      focused subwindow container.

Requirements:
    - Typing for Optional, Dict. pydicom.dataset.Dataset for type hints.
"""

import warnings
from typing import Optional, Dict, Any
from pydicom.dataset import Dataset
from PySide6.QtCore import Qt, QPointF, QRectF, QSize, QTimer


class SubwindowLifecycleController:
    """
    Holds subwindow getter logic for the main application.

    Receives the app instance and delegates all state access through it.
    Used by main.py and other modules (e.g. file_series_loading_coordinator,
    dialog_coordinator) to resolve current subwindow, dataset, slice, and managers.
    """

    def __init__(self, app: Any) -> None:
        """
        Initialize the controller with a reference to the main application.

        Args:
            app: The DICOMViewerApp instance (or any object providing
                 multi_window_layout, subwindow_managers, subwindow_data,
                 focused_subwindow_index).
        """
        self.app = app

    def get_subwindow_dataset(self, idx: int) -> Optional[Dataset]:
        """Get current dataset for a subwindow."""
        if idx in self.app.subwindow_data:
            return self.app.subwindow_data[idx].get('current_dataset')
        return None

    def get_subwindow_slice_index(self, idx: int) -> int:
        """Get current slice index for a subwindow."""
        if idx in self.app.subwindow_data:
            return self.app.subwindow_data[idx].get('current_slice_index', 0)
        return 0

    def get_subwindow_slice_display_manager(self, idx: int):
        """Get slice display manager for a subwindow."""
        if idx in self.app.subwindow_managers:
            return self.app.subwindow_managers[idx].get('slice_display_manager')
        return None

    def get_subwindow_study_uid(self, idx: int) -> str:
        """Get current study UID for a subwindow."""
        if idx in self.app.subwindow_data:
            return self.app.subwindow_data[idx].get('current_study_uid', '')
        return ''

    def get_subwindow_series_uid(self, idx: int) -> str:
        """Get current series UID for a subwindow."""
        if idx in self.app.subwindow_data:
            return self.app.subwindow_data[idx].get('current_series_uid', '')
        return ''

    def get_focused_subwindow_index(self) -> int:
        """Return the currently focused subwindow index (0-3). Used for histogram and other per-view features."""
        return self.app.focused_subwindow_index

    def get_histogram_callbacks_for_subwindow(self, idx: int) -> Dict[str, Any]:
        """
        Return a dict of callbacks for the histogram dialog tied to subwindow idx.
        Used so each histogram always shows the image currently displayed in that subwindow.
        """
        if idx not in self.app.subwindow_managers:
            return {}
        vsm = self.app.subwindow_managers[idx].get('view_state_manager')
        if vsm is None:
            return {}
        return {
            'get_current_dataset': lambda i=idx: self.get_subwindow_dataset(i),
            'get_current_slice_index': lambda i=idx: self.get_subwindow_slice_index(i),
            'get_window_center': lambda: vsm.current_window_center,
            'get_window_width': lambda: vsm.current_window_width,
            'get_use_rescaled': lambda: vsm.use_rescaled_values,
            'get_rescale_params': lambda: (
                vsm.rescale_slope,
                vsm.rescale_intercept,
                getattr(vsm, 'rescale_type', None)
            ),
        }

    def get_focused_subwindow(self):
        """
        Get the currently focused subwindow.

        Returns:
            SubWindowContainer or None if no subwindow is focused
        """
        return self.app.multi_window_layout.get_focused_subwindow()

    # --- Phase 3.3: focus/panel update methods ---

    def update_focused_subwindow_references(self) -> None:
        """Update legacy references to point to focused subwindow's managers and data."""
        app = self.app
        focused_subwindow = app.multi_window_layout.get_focused_subwindow()
        if not focused_subwindow:
            return
        subwindows = app.multi_window_layout.get_all_subwindows()
        if focused_subwindow not in subwindows:
            return
        focused_idx = subwindows.index(focused_subwindow)
        app.focused_subwindow_index = focused_idx
        if focused_idx in app.subwindow_managers:
            managers = app.subwindow_managers[focused_idx]
            app.view_state_manager = managers['view_state_manager']
            app.slice_display_manager = managers['slice_display_manager']
            app.roi_coordinator = managers['roi_coordinator']
            app.measurement_coordinator = managers['measurement_coordinator']
            app.text_annotation_coordinator = managers.get('text_annotation_coordinator')
            app.arrow_annotation_coordinator = managers.get('arrow_annotation_coordinator')
            app.crosshair_coordinator = managers.get('crosshair_coordinator')
            app.fusion_coordinator = managers.get('fusion_coordinator')
            app.overlay_coordinator = managers['overlay_coordinator']
            app.roi_manager = managers['roi_manager']
            app.measurement_tool = managers['measurement_tool']
            app.text_annotation_tool = managers.get('text_annotation_tool')
            app.arrow_annotation_tool = managers.get('arrow_annotation_tool')
            app.crosshair_manager = managers.get('crosshair_manager')
            app.overlay_manager = managers['overlay_manager']
        previous_image_viewer = app.image_viewer if hasattr(app, 'image_viewer') else None
        app.image_viewer = focused_subwindow.image_viewer
        app.main_window.image_viewer = app.image_viewer
        if previous_image_viewer and previous_image_viewer != app.image_viewer:
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*Failed to disconnect.*')
                try:
                    previous_image_viewer.pixel_info_changed.disconnect(app._on_pixel_info_changed)
                except (TypeError, RuntimeError):
                    pass
        if app.image_viewer:
            app.image_viewer.pixel_info_changed.connect(app._on_pixel_info_changed)
            app.image_viewer.set_pixel_info_callbacks(
                get_dataset=lambda: app.current_dataset,
                get_slice_index=lambda: app.current_slice_index,
                get_use_rescaled=lambda: app.view_state_manager.use_rescaled_values if app.view_state_manager else False
            )
        if focused_idx in app.subwindow_data:
            data = app.subwindow_data[focused_idx]
            app.current_dataset = data.get('current_dataset')
            app.current_slice_index = data.get('current_slice_index', 0)
            app.current_series_uid = data.get('current_series_uid', '')
            app.current_study_uid = data.get('current_study_uid', '')
            app.current_datasets = data.get('current_datasets', [])
            if app.current_datasets:
                total_slices = len(app.current_datasets)
                app.slice_navigator.set_total_slices(total_slices)
                focused_slice_index = data.get('current_slice_index', 0)
                if 0 <= focused_slice_index < total_slices:
                    app.slice_navigator.blockSignals(True)
                    app.slice_navigator.current_slice_index = focused_slice_index
                    app.slice_navigator.blockSignals(False)
        if app.current_dataset and app.window_level_controls:
            from core.dicom_processor import DICOMProcessor
            rescale_slope, rescale_intercept, rescale_type = DICOMProcessor.get_rescale_parameters(app.current_dataset)
            inferred_type = DICOMProcessor.infer_rescale_type(
                app.current_dataset, rescale_slope, rescale_intercept, rescale_type
            )
            if inferred_type:
                app.window_level_controls.set_unit(inferred_type)
            else:
                app.window_level_controls.set_unit(None)
        self.update_right_panel_for_focused_subwindow()
        self.update_left_panel_for_focused_subwindow()
        if hasattr(app, 'keyboard_event_handler') and app.image_viewer:
            app.keyboard_event_handler.image_viewer = app.image_viewer
        if hasattr(app, 'mouse_mode_handler') and app.image_viewer:
            app.mouse_mode_handler.image_viewer = app.image_viewer
            current_mode = app.main_window.get_current_mouse_mode()
            if current_mode:
                app.image_viewer.set_mouse_mode(current_mode)
        if app.image_viewer:
            app.image_viewer.setFocus()

    def update_right_panel_for_focused_subwindow(self) -> None:
        """Update right panel controls to reflect focused subwindow's state."""
        app = self.app
        if app.image_viewer is None:
            return
        app.zoom_display_widget.update_zoom(app.image_viewer.current_zoom)
        if app.view_state_manager:
            unit = None
            if app.view_state_manager.use_rescaled_values:
                unit = app.view_state_manager.rescale_type
            if not unit and app.current_dataset:
                from core.dicom_processor import DICOMProcessor
                rescale_slope, rescale_intercept, rescale_type = DICOMProcessor.get_rescale_parameters(app.current_dataset)
                unit = DICOMProcessor.infer_rescale_type(
                    app.current_dataset, rescale_slope, rescale_intercept, rescale_type
                )
            if (app.view_state_manager.current_window_center is not None and
                app.view_state_manager.current_window_width is not None):
                app.window_level_controls.set_window_level(
                    app.view_state_manager.current_window_center,
                    app.view_state_manager.current_window_width,
                    block_signals=True,
                    unit=unit
                )
            else:
                app.window_level_controls.set_unit(unit)
        if app.slice_display_manager:
            app.intensity_projection_controls_widget.set_enabled(
                app.slice_display_manager.projection_enabled,
                keep_signals_blocked=False
            )
            app.intensity_projection_controls_widget.set_projection_type(
                app.slice_display_manager.projection_type
            )
            app.intensity_projection_controls_widget.set_slice_count(
                app.slice_display_manager.projection_slice_count
            )
        if hasattr(app, 'current_studies') and app.current_studies:
            focused_subwindow = app.multi_window_layout.get_focused_subwindow()
            if focused_subwindow:
                subwindows = app.multi_window_layout.get_all_subwindows()
                focused_idx = subwindows.index(focused_subwindow) if focused_subwindow in subwindows else -1
                if focused_idx >= 0 and focused_idx in app.subwindow_managers:
                    fusion_coordinator = app.subwindow_managers[focused_idx].get('fusion_coordinator')
                    if fusion_coordinator:
                        fusion_coordinator.update_fusion_controls_series_list()

    def update_left_panel_for_focused_subwindow(self) -> None:
        """Update left panel controls (metadata, cine) to reflect focused subwindow's state."""
        app = self.app
        if app.current_dataset is None:
            return
        app.metadata_panel.set_dataset(app.current_dataset)
        app._update_cine_player_context()

    # --- Phase 3.4: display/redisplay, connect/disconnect, layout, series assignment ---

    def display_rois_for_subwindow(self, idx: int, preserve_view: bool = False) -> None:
        """Display ROIs for a specific subwindow (subwindow-scoped; delegates to app state)."""
        app = self.app
        if idx not in app.subwindow_managers:
            return
        # Placeholder: ROI display for subwindow's current slice can be extended here
        pass

    def redisplay_subwindow_slice(self, idx: int, preserve_view: bool = False) -> None:
        """Redisplay slice for a specific subwindow using its managers and data."""
        app = self.app
        if idx not in app.subwindow_managers:
            return
        managers = app.subwindow_managers[idx]
        view_state_manager = managers.get('view_state_manager')
        slice_display_manager = managers['slice_display_manager']
        if idx not in app.subwindow_data:
            return
        data = app.subwindow_data[idx]
        dataset = data.get('current_dataset')
        study_uid = data.get('current_study_uid', '')
        series_uid = data.get('current_series_uid', '')
        slice_index = data.get('current_slice_index', 0)
        if dataset and study_uid and series_uid and app.current_studies:
            slice_display_manager.display_slice(
                dataset,
                app.current_studies,
                study_uid,
                series_uid,
                slice_index,
                preserve_view_override=preserve_view
            )
            app.dialog_coordinator.update_histogram_for_subwindow(idx)

    def ensure_all_subwindows_have_managers(self) -> None:
        """Ensure all visible subwindows have managers; create via app and reconnect transform signals."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx not in app.subwindow_managers:
                app._create_managers_for_subwindow(idx, subwindow)
        self.connect_all_subwindow_transform_signals()

    def connect_subwindow_signals(self) -> None:
        """Connect signals that apply to all subwindows (files dropped, layout, context menu, assign series)."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow:
                image_viewer = subwindow.image_viewer
                image_viewer.files_dropped.connect(app._open_files_from_paths)
                image_viewer.layout_change_requested.connect(app._on_layout_change_requested)
                image_viewer.privacy_view_toggled.connect(app._on_privacy_view_toggled)
                image_viewer.about_this_file_requested.connect(app._open_about_this_file)
                image_viewer.histogram_requested.connect(
                    lambda i=idx: app.dialog_coordinator.open_histogram(i)
                )
                image_viewer.get_file_path_callback = lambda i=idx: app._get_current_slice_file_path(i)
                subwindow.assign_series_requested.connect(app._on_assign_series_requested)
                image_viewer.assign_series_requested.connect(app._on_assign_series_from_context_menu)
        self.connect_all_subwindow_transform_signals()

    def connect_all_subwindow_transform_signals(self) -> None:
        """Connect transform_changed and zoom_changed for all subwindows to their ViewStateManager."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx in app.subwindow_managers:
                image_viewer = subwindow.image_viewer
                managers = app.subwindow_managers[idx]
                view_state_manager = managers.get('view_state_manager')
                if view_state_manager:
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*Failed to disconnect.*')
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

    def connect_all_subwindow_context_menu_signals(self) -> None:
        """Connect context menu scroll wheel mode signals for all subwindows."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow:
                image_viewer = subwindow.image_viewer
                image_viewer.context_menu_scroll_wheel_mode_changed.connect(
                    app.mouse_mode_handler.handle_context_menu_scroll_wheel_mode_changed
                )

    def disconnect_focused_subwindow_signals(self) -> None:
        """Disconnect signals from previously focused subwindow."""
        app = self.app
        if app.image_viewer is None:
            return
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*Failed to disconnect.*')
            try:
                app.image_viewer.annotation_options_requested.disconnect()
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
                app.image_viewer.roi_clicked.disconnect()
                app.image_viewer.image_clicked_no_roi.disconnect()
            except (TypeError, RuntimeError):
                pass
            try:
                app.image_viewer.roi_delete_requested.disconnect()
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

    def connect_focused_subwindow_signals(self) -> None:
        """Connect signals for the currently focused subwindow."""
        app = self.app
        self.disconnect_focused_subwindow_signals()
        if app.image_viewer is None:
            return
        focused_idx = app.focused_subwindow_index
        if app.view_state_manager:
            app.view_state_manager.set_redisplay_slice_callback(
                lambda preserve_view=False: self.redisplay_subwindow_slice(focused_idx, preserve_view)
            )
        app.image_viewer.annotation_options_requested.connect(app._open_annotation_options)
        app.image_viewer.roi_drawing_started.connect(app.roi_coordinator.handle_roi_drawing_started)
        app.image_viewer.roi_drawing_updated.connect(app.roi_coordinator.handle_roi_drawing_updated)
        app.image_viewer.roi_drawing_finished.connect(app.roi_coordinator.handle_roi_drawing_finished)
        app.image_viewer.measurement_started.connect(app.measurement_coordinator.handle_measurement_started)
        app.image_viewer.measurement_updated.connect(app.measurement_coordinator.handle_measurement_updated)
        app.image_viewer.measurement_finished.connect(app.measurement_coordinator.handle_measurement_finished)
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
        app.image_viewer.set_pixel_info_callbacks(
            get_dataset=lambda: app.current_dataset,
            get_slice_index=lambda: app.current_slice_index,
            get_use_rescaled=lambda: app.view_state_manager.use_rescaled_values if app.view_state_manager else False
        )

        def get_available_series() -> list:
            if not app.current_studies:
                return []
            series_list = []
            for study_uid, series_dict in app.current_studies.items():
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
        if app.keyboard_event_handler:
            app.keyboard_event_handler.delete_all_rois_callback = app.roi_coordinator.delete_all_rois_current_slice
            app.keyboard_event_handler.invert_image_callback = app.image_viewer.invert_image
            if hasattr(app, 'text_annotation_coordinator') and app.text_annotation_coordinator:
                app.keyboard_event_handler.delete_text_annotation_callback = app.text_annotation_coordinator.handle_text_annotation_delete_requested
            if hasattr(app, 'arrow_annotation_coordinator') and app.arrow_annotation_coordinator:
                app.keyboard_event_handler.delete_arrow_annotation_callback = app.arrow_annotation_coordinator.handle_arrow_annotation_delete_requested
        app.window_level_controls.window_changed.connect(app.view_state_manager.handle_window_changed)
        app.window_level_controls.window_changed.connect(app._update_histogram_for_focused_subwindow)
        app.image_viewer.window_level_preset_selected.connect(app._on_window_level_preset_selected)
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
        app.slice_navigator.slice_changed.connect(app._on_manual_slice_navigation)
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
            if app.current_dataset is not None:
                app._display_slice(app.current_dataset, preserve_view_override=False)
        app.main_window.reset_view_requested.connect(handle_reset_view)
        app.image_viewer.reset_view_requested.connect(handle_reset_view)
        app.main_window.reset_all_views_requested.connect(app._on_reset_all_views)
        app.image_viewer.reset_all_views_requested.connect(app._on_reset_all_views)
        app.main_window.clear_measurements_requested.connect(app.measurement_coordinator.handle_clear_measurements)
        app.image_viewer.clear_measurements_requested.connect(app.measurement_coordinator.handle_clear_measurements)
        app.image_viewer.histogram_requested.connect(app.dialog_coordinator.open_histogram)
        app.image_viewer.toggle_overlay_requested.connect(app.overlay_coordinator.handle_toggle_overlay)
        app.main_window.viewport_resizing.connect(app.view_state_manager.handle_viewport_resizing)
        app.main_window.viewport_resized.connect(app.view_state_manager.handle_viewport_resized)
        app.slice_navigator.slice_changed.connect(app._update_histogram_for_focused_subwindow)
        app.series_navigator.series_selected.connect(app._on_series_navigator_selected)
        app.series_navigator.show_file_requested.connect(app._on_show_file_from_series)
        app.series_navigator.about_this_file_requested.connect(app._on_about_this_file_from_series)
        app.image_viewer.toggle_series_navigator_requested.connect(app.main_window.toggle_series_navigator)

    def on_focused_subwindow_changed(self, subwindow: Any) -> None:
        """Handle focused subwindow change: disconnect old, update refs, connect new, update panels."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        focused_idx = subwindows.index(subwindow) if subwindow in subwindows else -1
        self.disconnect_focused_subwindow_signals()
        self.update_focused_subwindow_references()
        self.connect_focused_subwindow_signals()
        if focused_idx >= 0 and focused_idx in app.subwindow_managers:
            pass  # optional debug
        if app.keyboard_event_handler and app.view_state_manager:
            app.keyboard_event_handler.reset_view_callback = app.view_state_manager.reset_view
        if app.roi_list_panel and app.roi_manager:
            app.roi_list_panel.set_roi_manager(app.roi_manager)
        if focused_idx >= 0 and focused_idx in app.subwindow_data:
            data = app.subwindow_data[focused_idx]
            focused_series_uid = data.get('current_series_uid', '')
            focused_study_uid = data.get('current_study_uid', '')
            if focused_series_uid and focused_study_uid and app.series_navigator:
                app.series_navigator.set_current_series(focused_series_uid, focused_study_uid)
            if app.current_dataset is not None:
                from utils.dicom_utils import get_composite_series_key
                study_uid = getattr(app.current_dataset, 'StudyInstanceUID', '')
                series_uid = get_composite_series_key(app.current_dataset)
                instance_identifier = app.current_slice_index
                app.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
        if app.roi_manager:
            selected_roi = app.roi_manager.get_selected_roi()
            if selected_roi:
                roi_belongs = False
                for roi_list in app.roi_manager.rois.values():
                    if selected_roi in roi_list:
                        roi_belongs = True
                        break
                if not roi_belongs:
                    app.roi_manager.select_roi(None)
        self.update_right_panel_for_focused_subwindow()
        app._update_series_navigator_highlighting()
        app._update_about_this_file_dialog()

    def on_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from multi-window layout."""
        app = self.app
        app.config_manager.set_multi_window_layout(layout_mode)
        app.main_window.set_layout_mode(layout_mode)
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow and idx in app.subwindow_managers:
                managers = app.subwindow_managers[idx]
                if 'view_state_manager' in managers:
                    managers['view_state_manager'].handle_viewport_resizing()
        self.ensure_all_subwindows_have_managers()
        self.connect_subwindow_signals()

        def trigger_viewport_resized():
            subwindows = app.multi_window_layout.get_all_subwindows()
            for idx, subwindow in enumerate(subwindows):
                if subwindow and idx in app.subwindow_managers:
                    managers = app.subwindow_managers[idx]
                    if 'view_state_manager' in managers:
                        managers['view_state_manager'].handle_viewport_resized()
        QTimer.singleShot(100, trigger_viewport_resized)

    def on_main_window_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from main window menu."""
        self.app.multi_window_layout.set_layout(layout_mode)

    def capture_subwindow_view_states(self) -> Dict[int, Dict]:
        """Capture view state for all existing subwindows before layout change."""
        view_states = {}
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow is None:
                continue
            image_viewer = subwindow.image_viewer
            if image_viewer is None:
                continue
            if image_viewer.image_item is None:
                continue
            viewport_rect = image_viewer.viewport().rect()
            top_left = image_viewer.mapToScene(viewport_rect.topLeft())
            bottom_right = image_viewer.mapToScene(viewport_rect.bottomRight())
            viewport_rect_scene = QRectF(top_left, bottom_right)
            zoom = image_viewer.current_zoom
            viewport_center = QPointF(viewport_rect.width() / 2.0, viewport_rect.height() / 2.0)
            scene_center = image_viewer.mapToScene(viewport_center.toPoint())
            old_size = subwindow.size()
            view_states[idx] = {
                'viewport_rect': viewport_rect_scene,
                'zoom': zoom,
                'scene_center': scene_center,
                'old_size': old_size
            }
        return view_states

    def restore_subwindow_views(self, view_states: Dict[int, Dict]) -> None:
        """Restore subwindow views after layout change (fit to view)."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, view_state in view_states.items():
            try:
                if idx >= len(subwindows) or subwindows[idx] is None:
                    continue
                subwindow = subwindows[idx]
                image_viewer = subwindow.image_viewer
                if image_viewer is None:
                    continue
                if image_viewer.image_item is None:
                    continue

                def fit_image_to_viewport():
                    if image_viewer.image_item is not None:
                        viewport = image_viewer.viewport()
                        if viewport and viewport.width() > 0 and viewport.height() > 0:
                            image_viewer.fit_to_view(center_image=True)

                QTimer.singleShot(100, fit_image_to_viewport)
            except Exception:
                continue

    def on_layout_change_requested(self, layout_mode: str) -> None:
        """Handle layout change request from image viewer context menu."""
        self.app.multi_window_layout.set_layout(layout_mode)

    def assign_series_to_subwindow(self, subwindow: Any, series_uid: str, slice_index: int) -> None:
        """Assign a series/slice to a specific subwindow. Delegates to file/series loading coordinator."""
        self.app._file_series_coordinator.assign_series_to_subwindow(subwindow, series_uid, slice_index)
