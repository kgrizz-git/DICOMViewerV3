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

from typing import Optional, Dict, Any
from pydicom.dataset import Dataset


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
