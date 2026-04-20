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
from datetime import datetime
from utils.debug_flags import DEBUG_LAYOUT
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
        # Store histogram slot per image_viewer so we can disconnect before reconnecting
        # (connect_subwindow_signals is called on every layout change; without disconnect we accumulate duplicates)
        self._histogram_slots: Dict[int, Any] = {}  # id(image_viewer) -> callable
        self._mpr_open_slots: Dict[int, Any] = {}   # id(image_viewer) -> callable
        self._mpr_clear_slots: Dict[int, Any] = {}  # id(image_viewer) -> callable
        self._clear_window_slots: Dict[int, Any] = {}  # id(image_viewer) -> callable
        self._cine_toggle_slots: Dict[int, Any] = {}  # id(image_viewer) -> callable
        self._cine_stop_slots: Dict[int, Any] = {}  # id(image_viewer) -> callable
        self._rdsr_report_slots: Dict[int, Any] = {}  # id(image_viewer) -> callable (dose SR dialog)
        # Single restartable timer for 100ms viewport-resized callback; coalesces rapid layout changes.
        self._viewport_resized_timer: Optional[QTimer] = None

    def get_subwindow_dataset(self, idx: int) -> Optional[Dataset]:
        """
        Get the DICOM dataset that matches what this subwindow is showing.

        For **non-MPR** views, prefer ``current_studies[study][series][slice_index]``
        when available — the same list ``_on_slice_changed`` / ``display_slice`` use
        — so direction labels and scale markers cannot diverge from a stale or
        reordered ``subwindow_data['current_datasets']`` (e.g. after MPR elsewhere).
        Otherwise use ``current_datasets[slice_index]``, then ``current_dataset``.
        MPR views keep the synthetic overlay dataset.
        """
        if idx not in self.app.subwindow_data:
            return None
        data = self.app.subwindow_data[idx]
        is_mpr = bool(data.get("is_mpr"))
        si_raw = data.get("current_slice_index", 0)
        try:
            si = int(si_raw)
        except (TypeError, ValueError):
            si = 0
        ds_list = data.get("current_datasets")
        out: Optional[Dataset] = None
        if is_mpr:
            out = data.get("current_dataset")
        else:
            study_uid = str(data.get("current_study_uid", "") or "")
            series_uid = str(data.get("current_series_uid", "") or "")
            studies = getattr(self.app, "current_studies", None)
            if (
                studies
                and study_uid
                and series_uid
                and study_uid in studies
                and isinstance(studies[study_uid], dict)
                and series_uid in studies[study_uid]
            ):
                canon = studies[study_uid][series_uid]
                if isinstance(canon, list) and canon and 0 <= si < len(canon):
                    out = canon[si]
            if out is None and isinstance(ds_list, list) and ds_list and 0 <= si < len(ds_list):
                out = ds_list[si]
            if out is None:
                out = data.get("current_dataset")
        return out

    def get_subwindow_datasets(self, idx: int):
        """Get current dataset list for a subwindow's series, if available."""
        if idx in self.app.subwindow_data:
            return self.app.subwindow_data[idx].get('current_datasets')
        return None

    def get_subwindow_slice_index(self, idx: int) -> int:
        """Get current displayed slice index for a subwindow.

        For MPR panes this is ``mpr_slice_index``; for native panes this is
        ``current_slice_index``.
        """
        if idx in self.app.subwindow_data:
            data = self.app.subwindow_data[idx]
            if bool(data.get("is_mpr")):
                return int(data.get("mpr_slice_index", data.get("current_slice_index", 0)) or 0)
            return int(data.get("current_slice_index", 0) or 0)
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

    def wire_pixel_info_callbacks_for_subwindow(self, image_viewer: Any, idx: int) -> None:
        """
        Bind dataset/slice/rescale callbacks for pixel readout and direction labels.

        Each pane must use **this viewer's** subwindow row in ``subwindow_data``,
        not ``app.current_dataset`` / ``app.current_slice_index`` (focused pane).

        The subwindow index is read from ``image_viewer.subwindow_index`` whenever
        the callback runs so it stays aligned with ``set_subwindow_index`` (layout
        reconnect and swap). *idx* is only a fallback before the first
        ``connect_subwindow_signals`` pass.
        """
        app = self.app

        def resolve_subwindow_index() -> int:
            si = getattr(image_viewer, "subwindow_index", None)
            if si is not None:
                return int(si)
            return int(idx)

        def get_dataset() -> Optional[Dataset]:
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
        sdm = self.app.subwindow_managers[idx].get("slice_display_manager")
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
            'get_series_study_uid': lambda i=idx: self.get_subwindow_study_uid(i),
            'get_series_uid': lambda i=idx: self.get_subwindow_series_uid(i),
            'get_series_datasets': lambda i=idx: self.get_subwindow_datasets(i),
            'get_all_studies': lambda: getattr(self.app, 'current_studies', {}),
            'get_projection_enabled': lambda i=idx: self._get_histogram_projection_enabled(i),
            'get_current_pixel_array': lambda i=idx: self._get_histogram_current_pixel_array(i),
            'get_projection_pixel_array': lambda i=idx: self._get_histogram_projection_pixel_array(
                i
            ),
            'get_histogram_use_projection_pixels': self.app.config_manager.get_histogram_use_projection_pixels,
            'set_histogram_use_projection_pixels': self.app.config_manager.set_histogram_use_projection_pixels,
        }

    def _get_histogram_projection_enabled(self, idx: int) -> bool:
        """Return whether projection/combine is active for histogram in subwindow ``idx``."""
        data = self.app.subwindow_data.get(idx, {})
        if bool(data.get("is_mpr")):
            return bool(data.get("mpr_combine_enabled", False))
        sdm = self.app.subwindow_managers.get(idx, {}).get("slice_display_manager")
        return bool(getattr(sdm, "projection_enabled", False)) if sdm is not None else False

    def _get_histogram_current_pixel_array(self, idx: int):
        """
        Return raw pixels of what the pane is currently showing, without forcing projection mode.
        For MPR panes this is the uncombined current MPR slice.
        """
        import numpy as np

        data = self.app.subwindow_data.get(idx, {})
        if not bool(data.get("is_mpr")):
            return None
        result = data.get("mpr_result")
        if result is None:
            return None
        try:
            slice_index = int(data.get("mpr_slice_index", data.get("current_slice_index", 0)) or 0)
        except (TypeError, ValueError):
            slice_index = 0
        if slice_index < 0 or slice_index >= int(getattr(result, "n_slices", 0) or 0):
            return None
        try:
            from core.mpr_controller import apply_mpr_stack_combine

            arr = apply_mpr_stack_combine(
                result.slices,
                slice_index,
                enabled=False,
                mode=str(data.get("mpr_combine_mode", "aip") or "aip"),
                n_planes=int(data.get("mpr_combine_slice_count", 4) or 4),
            )
            return arr if isinstance(arr, np.ndarray) else None
        except Exception:
            return None

    def _get_histogram_projection_pixel_array(self, idx: int):
        """
        Raw 2D numpy projection for histogram when intensity projection is enabled
        for subwindow ``idx``. Returns ``None`` if not applicable.
        """
        import numpy as np

        data = self.app.subwindow_data.get(idx, {})
        if bool(data.get("is_mpr")):
            if not bool(data.get("mpr_combine_enabled", False)):
                return None
            result = data.get("mpr_result")
            if result is None:
                return None
            try:
                slice_index = int(data.get("mpr_slice_index", data.get("current_slice_index", 0)) or 0)
            except (TypeError, ValueError):
                return None
            if slice_index < 0 or slice_index >= int(getattr(result, "n_slices", 0) or 0):
                return None
            try:
                from core.mpr_controller import apply_mpr_stack_combine

                arr = apply_mpr_stack_combine(
                    result.slices,
                    slice_index,
                    enabled=True,
                    mode=str(data.get("mpr_combine_mode", "aip") or "aip"),
                    n_planes=int(data.get("mpr_combine_slice_count", 4) or 4),
                )
                return arr if isinstance(arr, np.ndarray) else None
            except Exception:
                return None

        if idx not in self.app.subwindow_managers:
            return None
        sdm = self.app.subwindow_managers[idx].get("slice_display_manager")
        if sdm is None or not sdm.projection_enabled:
            return None
        series = self.get_subwindow_datasets(idx)
        if not series or len(series) < 2:
            return None
        z = self.get_subwindow_slice_index(idx)
        from core.slice_display_pixels import compute_intensity_projection_raw_array

        arr = compute_intensity_projection_raw_array(
            self.app.dicom_processor,
            str(sdm.projection_type),
            int(sdm.projection_slice_count),
            list(series),
            z,
        )
        return arr if isinstance(arr, np.ndarray) else None

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
        if DEBUG_LAYOUT:
            vsm = app.subwindow_managers.get(focused_idx, {}).get('view_state_manager')
            ts = datetime.now().strftime("%H:%M:%S.%f")
            print(f"[DEBUG-LAYOUT] [{ts}] update_focused_subwindow_references: focused_idx={focused_idx} view_state_manager id={id(vsm) if vsm else None}")
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
            self.wire_pixel_info_callbacks_for_subwindow(app.image_viewer, focused_idx)
        if focused_idx in app.subwindow_data:
            data = app.subwindow_data[focused_idx]
            canon = self.get_subwindow_dataset(focused_idx)
            app.current_dataset = (
                canon if canon is not None else data.get("current_dataset")
            )
            app.current_slice_index = data.get('current_slice_index', 0)
            app.current_series_uid = data.get('current_series_uid', '')
            app.current_study_uid = data.get('current_study_uid', '')
            app.current_datasets = data.get('current_datasets', [])
            if data.get("is_mpr") and data.get("mpr_result") is not None:
                total_slices = data["mpr_result"].n_slices
                app.slice_navigator.set_total_slices(total_slices)
                focused_slice_index = data.get('current_slice_index', 0)
                if 0 <= focused_slice_index < total_slices:
                    app.slice_navigator.blockSignals(True)
                    app.slice_navigator.current_slice_index = focused_slice_index
                    app.slice_navigator.blockSignals(False)
            elif app.current_datasets:
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
        # Handlers may be unset until _initialize_handlers() (e.g. early init); do not use hasattr alone.
        if app.keyboard_event_handler is not None and app.image_viewer:
            app.keyboard_event_handler.image_viewer = app.image_viewer
            app.keyboard_event_handler.toggle_overlay_visibility_legacy_callback = (
                app.overlay_coordinator.handle_toggle_overlay
            )
        if app.mouse_mode_handler is not None and app.image_viewer:
            app.mouse_mode_handler.image_viewer = app.image_viewer
            if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(focused_idx):
                app.image_viewer.set_mouse_mode("pan")
                if hasattr(app.main_window, "set_mouse_mode_checked"):
                    app.main_window.set_mouse_mode_checked("pan")
            else:
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
            # Keep toolbar/context toggle text in sync with the focused subwindow,
            # even when two windows show the same series with different local state.
            app.main_window.set_rescale_toggle_state(
                bool(app.view_state_manager.use_rescaled_values)
            )
            app.image_viewer.set_rescale_toggle_state(
                bool(app.view_state_manager.use_rescaled_values)
            )
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
        focused_subwindow = app.multi_window_layout.get_focused_subwindow()
        subwindows = app.multi_window_layout.get_all_subwindows()
        focused_idx = (
            subwindows.index(focused_subwindow)
            if focused_subwindow and focused_subwindow in subwindows
            else -1
        )
        if (
            focused_idx >= 0
            and hasattr(app, "_mpr_controller")
            and app._mpr_controller.is_mpr(focused_idx)
        ):
            mp_data = app.subwindow_data.get(focused_idx, {})
            w = app.intensity_projection_controls_widget
            w.enable_checkbox.blockSignals(True)
            w.projection_combo.blockSignals(True)
            w.slice_count_combo.blockSignals(True)
            try:
                w.set_enabled(
                    bool(mp_data.get("mpr_combine_enabled", False)),
                    keep_signals_blocked=True,
                )
                w.set_projection_type(
                    str(mp_data.get("mpr_combine_mode", "aip") or "aip")
                )
                w.set_slice_count(
                    int(mp_data.get("mpr_combine_slice_count", 4) or 4)
                )
            finally:
                w.enable_checkbox.blockSignals(False)
                w.projection_combo.blockSignals(False)
                w.slice_count_combo.blockSignals(False)
        elif app.slice_display_manager:
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
            if focused_subwindow:
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
        app.cine_app_facade.update_cine_player_context()

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
        if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(idx):
            app._mpr_controller.display_mpr_slice(
                idx, app.subwindow_data.get(idx, {}).get("current_slice_index", 0)
            )
            return
        managers = app.subwindow_managers[idx]
        view_state_manager = managers.get('view_state_manager')
        slice_display_manager = managers['slice_display_manager']
        if idx not in app.subwindow_data:
            return
        data = app.subwindow_data[idx]
        # Match get_subwindow_dataset / direction labels: prefer slice list + index
        # so the pixmap is not driven by a stale current_dataset while HUD uses
        # current_datasets[current_slice_index].
        dataset = self.get_subwindow_dataset(idx)
        if dataset is None:
            dataset = data.get("current_dataset")
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
            # Keep stored pointer aligned with the slice list + index so other
            # readers of current_dataset match the pixmap and direction labels.
            data["current_dataset"] = dataset
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
        """Connect signals that apply to all subwindows (files dropped, layout, context menu, assign series).
        Disconnects before connecting to avoid duplicate connections when this runs on every layout change.
        """
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow:
                image_viewer = subwindow.image_viewer
                vid = id(image_viewer)
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', category=RuntimeWarning, message='.*Failed to disconnect.*')
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
                    vid = id(image_viewer)
                    if vid in self._rdsr_report_slots:
                        try:
                            image_viewer.structured_report_browser_requested.disconnect(
                                self._rdsr_report_slots[vid]
                            )
                        except (TypeError, RuntimeError):
                            pass
                        del self._rdsr_report_slots[vid]
                    # histogram_requested uses a lambda; disconnect stored slot if any
                    if vid in self._histogram_slots:
                        try:
                            image_viewer.histogram_requested.disconnect(self._histogram_slots[vid])
                        except (TypeError, RuntimeError):
                            pass
                        del self._histogram_slots[vid]
                    if vid in self._mpr_open_slots:
                        try:
                            image_viewer.create_mpr_view_requested.disconnect(self._mpr_open_slots[vid])
                        except (TypeError, RuntimeError):
                            pass
                        del self._mpr_open_slots[vid]
                    if vid in self._mpr_clear_slots:
                        try:
                            image_viewer.clear_mpr_view_requested.disconnect(self._mpr_clear_slots[vid])
                        except (TypeError, RuntimeError):
                            pass
                        del self._mpr_clear_slots[vid]
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
                    if vid in self._clear_window_slots:
                        try:
                            image_viewer.clear_window_content_requested.disconnect(
                                self._clear_window_slots[vid]
                            )
                        except (TypeError, RuntimeError):
                            pass
                        del self._clear_window_slots[vid]
                    if vid in self._cine_toggle_slots:
                        try:
                            image_viewer.cine_play_pause_toggle_requested.disconnect(
                                self._cine_toggle_slots[vid]
                            )
                        except (TypeError, RuntimeError):
                            pass
                        del self._cine_toggle_slots[vid]
                    if vid in self._cine_stop_slots:
                        try:
                            image_viewer.cine_stop_requested.disconnect(self._cine_stop_slots[vid])
                        except (TypeError, RuntimeError):
                            pass
                        del self._cine_stop_slots[vid]

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
                hist_slot = lambda i=idx: app.dialog_coordinator.open_histogram(i)
                image_viewer.histogram_requested.connect(hist_slot)
                self._histogram_slots[vid] = hist_slot
                sr_slot = lambda i=idx: app._open_structured_report_browser(i)
                image_viewer.structured_report_browser_requested.connect(sr_slot)
                self._rdsr_report_slots[vid] = sr_slot
                image_viewer.get_file_path_callback = lambda i=idx: app._get_current_slice_file_path(i)
                image_viewer.get_slice_location_lines_visible_callback = (
                    lambda: app.config_manager.get_slice_location_lines_visible()
                )
                image_viewer.set_subwindow_index(idx)
                self.wire_pixel_info_callbacks_for_subwindow(image_viewer, idx)
                layout = app.multi_window_layout
                image_viewer.get_slot_to_view_callback = lambda l=layout: l.get_slot_to_view()
                subwindow.assign_series_requested.connect(app._on_assign_series_requested)
                image_viewer.assign_series_requested.connect(app._on_assign_series_from_context_menu)
                subwindow.mpr_assign_requested.connect(app._on_mpr_assign_requested)
                subwindow.expand_to_1x1_requested.connect(app._on_expand_to_1x1_requested)
                image_viewer.swap_view_requested.connect(app._on_swap_view_requested)
                image_viewer.window_slot_map_popup_requested.connect(app._on_window_slot_map_popup_requested)

                clear_window_slot = lambda i=idx: app._on_clear_subwindow_content_requested(i)
                image_viewer.clear_window_content_requested.connect(clear_window_slot)
                self._clear_window_slots[vid] = clear_window_slot
                image_viewer.get_clear_this_window_enabled_callback = lambda i=idx: (
                    app.subwindow_data.get(i, {}).get("current_dataset") is not None
                    or bool(app.subwindow_data.get(i, {}).get("is_mpr"))
                )
                image_viewer.get_cine_loop_state_callback = (
                    lambda: app.cine_app_facade.get_cine_loop_state()
                )
                image_viewer.get_cine_is_playing_callback = lambda: app.cine_player.is_playing
                cine_toggle_slot = lambda: app.cine_app_facade.on_cine_play_pause_toggle()
                cine_stop_slot = lambda: app.cine_app_facade.on_cine_stop()
                image_viewer.cine_play_pause_toggle_requested.connect(cine_toggle_slot)
                image_viewer.cine_stop_requested.connect(cine_stop_slot)
                self._cine_toggle_slots[vid] = cine_toggle_slot
                self._cine_stop_slots[vid] = cine_stop_slot

                # MPR view actions.
                if hasattr(app, "_mpr_controller"):
                    open_mpr_slot = lambda i=idx: app._mpr_controller.open_mpr_dialog(i)
                    clear_mpr_slot = lambda i=idx: app._mpr_controller.clear_mpr(i)
                    image_viewer.create_mpr_view_requested.connect(open_mpr_slot)
                    image_viewer.clear_mpr_view_requested.connect(clear_mpr_slot)
                    self._mpr_open_slots[vid] = open_mpr_slot
                    self._mpr_clear_slots[vid] = clear_mpr_slot
                    image_viewer.is_mpr_view_callback = lambda i=idx: app._mpr_controller.is_mpr(i)
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
        """Connect context menu and export ROI statistics signals for all subwindows."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if subwindow:
                image_viewer = subwindow.image_viewer
                image_viewer.context_menu_scroll_wheel_mode_changed.connect(
                    app.mouse_mode_handler.handle_context_menu_scroll_wheel_mode_changed
                )
                image_viewer.export_roi_statistics_requested.connect(app._open_export_roi_statistics)

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
        self.wire_pixel_info_callbacks_for_subwindow(app.image_viewer, focused_idx)

        def get_available_series() -> list[Any]:
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
        if app.image_viewer is not None:
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

            # If the focused subwindow is in MPR mode, reset view using the MPR controller
            # instead of redisplaying the original series via _display_slice.
            try:
                focused_subwindow = app.multi_window_layout.get_focused_subwindow()
                subwindows = app.multi_window_layout.get_all_subwindows()
                focused_idx = subwindows.index(focused_subwindow) if focused_subwindow in subwindows else -1
            except Exception:
                focused_idx = -1

            is_mpr_view = False
            try:
                if (
                    hasattr(app, "_mpr_controller")
                    and focused_idx != -1
                    and app._mpr_controller.is_mpr(focused_idx)
                ):
                    is_mpr_view = True
            except Exception:
                is_mpr_view = False

            if is_mpr_view:
                data = app.subwindow_data.get(focused_idx, {})
                slice_index = data.get("mpr_slice_index", 0)
                try:
                    app._mpr_controller.display_mpr_slice(focused_idx, slice_index)
                    image_viewer = app._mpr_controller._get_image_viewer(focused_idx)
                    if image_viewer is not None:
                        image_viewer.fit_to_view(center_image=True)
                    return
                except Exception:
                    # Fall back to normal path on error.
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
        app.series_navigator.series_selected.connect(app._on_series_navigator_selected)
        app.series_navigator.instance_selected.connect(app._on_series_navigator_instance_selected)
        app.series_navigator.show_instances_separately_toggled.connect(app._on_show_instances_separately_toggled)
        app.series_navigator.show_file_requested.connect(app._on_show_file_from_series)
        app.series_navigator.about_this_file_requested.connect(app._on_about_this_file_from_series)
        app.image_viewer.toggle_series_navigator_requested.connect(app.main_window.toggle_series_navigator)

    def on_focused_subwindow_changed(self, subwindow: Any) -> None:
        """Handle focused subwindow change: disconnect old, update refs, connect new, update panels."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        focused_idx = subwindows.index(subwindow) if subwindow in subwindows else -1
        # Deselect any selected ROI in the outgoing subwindow before refs are swapped.
        # handle_image_clicked_no_roi() is the canonical full-cleanup path: it clears
        # selected_roi, the scene selection, the shared list panel, and the stats panel.
        if app.roi_coordinator:
            app.roi_coordinator.handle_image_clicked_no_roi()
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
                if hasattr(app, '_refresh_series_navigator_state'):
                    app._refresh_series_navigator_state()
            if app.current_dataset is not None:
                from utils.dicom_utils import get_composite_series_key
                study_uid = getattr(app.current_dataset, 'StudyInstanceUID', '')
                series_uid = get_composite_series_key(app.current_dataset)
                instance_identifier = app.current_slice_index
                app.roi_list_panel.update_roi_list(study_uid, series_uid, instance_identifier)
        if app.roi_manager:
            selected_roi = app.roi_manager.get_selected_roi()
            if selected_roi:
                # Check if the selected ROI belongs to the current focused slice/series.
                # Handles stale selections when a non-focused window was navigated to a
                # different slice while focus was elsewhere.
                roi_belongs_to_current_slice = False
                if app.current_dataset is not None:
                    from utils.dicom_utils import get_composite_series_key
                    study_uid = getattr(app.current_dataset, 'StudyInstanceUID', '')
                    series_uid = get_composite_series_key(app.current_dataset)
                    slice_index = app.current_slice_index
                    roi_key = (study_uid, series_uid, slice_index)
                    if roi_key in app.roi_manager.rois:
                        if selected_roi in app.roi_manager.rois[roi_key]:
                            roi_belongs_to_current_slice = True
                if not roi_belongs_to_current_slice:
                    # Use the coordinator's full-cleanup path: clears manager selection,
                    # scene selection, shared list panel, and statistics panel.
                    app.roi_coordinator.handle_image_clicked_no_roi()
        self.update_right_panel_for_focused_subwindow()
        app._update_series_navigator_highlighting()
        app._update_about_this_file_dialog()
        # Push current slice state to the newly focused viewer's edge-reveal slider
        self._sync_slider_state_for_focused_viewer(focused_idx)
        # 1×1 / 1×2 / 2×1: focus can change which pane is visible (window map, swap) without a
        # layout *mode* change, so on_layout_changed never runs. Reuse the same coalesced
        # viewport pass as layout changes so newly shown panes get fit_to_view for the new size.
        try:
            mode = app.multi_window_layout.get_layout_mode()
        except Exception:
            mode = ""
        # Require str so tests using MagicMock for layout do not treat mock == "1x1" as true.
        if isinstance(mode, str) and mode in ("1x1", "1x2", "2x1"):
            self._schedule_viewport_resized_timer()

    def _capture_viewport_centers_for_visible_subwindows(self) -> None:
        """
        Store each visible pane's viewport center in scene coordinates on its
        ViewStateManager (``handle_viewport_resizing`` → ``saved_scene_center``).

        Call immediately before scheduling the coalesced viewport-resized pass so
        ``handle_viewport_resized`` can refit to the new size and then
        ``centerOn(saved_scene_center)`` to preserve pan across focus and layout
        changes. Each subwindow has its own ViewStateManager state.
        """
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, subwindow in enumerate(subwindows):
            if not subwindow or not subwindow.isVisible():
                continue
            if idx not in app.subwindow_managers:
                continue
            managers = app.subwindow_managers[idx]
            vsm = managers.get("view_state_manager")
            if vsm is not None:
                vsm.handle_viewport_resizing()

    def _sync_slider_state_for_focused_viewer(self, focused_idx: int) -> None:
        """
        Push the current slice position and total count to the focused viewer's
        edge-reveal slider overlay.  Called whenever focus switches so the
        slider accurately reflects the new subwindow's content.

        Args:
            focused_idx: The index of the newly focused subwindow (may be -1).
        """
        app = self.app
        if focused_idx < 0:
            return
        sync = getattr(app, "_sync_navigation_slider_for_subwindow", None)
        if callable(sync):
            sync(focused_idx)

    def _trigger_viewport_resized(self) -> None:
        """Run viewport_resized for all visible subwindows (so unfocused panes resize when layout changes, e.g. 2x2→1x2) and sync cursor. Used by the coalesced 100ms timer."""
        app = self.app
        subwindows_list = app.multi_window_layout.get_all_subwindows()
        focused = app.multi_window_layout.get_focused_subwindow()
        focused_idx = subwindows_list.index(focused) if (focused is not None and focused.isVisible() and focused in subwindows_list) else None
        if DEBUG_LAYOUT:
            ts = datetime.now().strftime("%H:%M:%S.%f")
            print(f"[DEBUG-LAYOUT] [{ts}] trigger_viewport_resized (100ms): focused_idx={focused_idx} view_state_manager id={id(app.subwindow_managers.get(focused_idx, {}).get('view_state_manager')) if focused_idx is not None and focused_idx in app.subwindow_managers else None}")
        # Call handle_viewport_resized for every visible subwindow so unfocused panes (e.g. second pane in 1x2) also rescale after layout change
        for idx, subwindow in enumerate(subwindows_list):
            if subwindow and subwindow.isVisible() and idx in app.subwindow_managers:
                managers = app.subwindow_managers[idx]
                if 'view_state_manager' in managers:
                    managers['view_state_manager'].handle_viewport_resized()
        # Sync mouse mode (cursor) to all visible ImageViewers so cursor doesn't flicker
        current_mode = app.main_window.get_current_mouse_mode() if hasattr(app.main_window, 'get_current_mouse_mode') else "pan"
        tool_cursor = None
        for subwindow in subwindows_list:
            if subwindow and subwindow.isVisible() and subwindow.image_viewer:
                subwindow.image_viewer.set_mouse_mode(current_mode)
                subwindow.setCursor(subwindow.image_viewer.cursor())
                if tool_cursor is None:
                    tool_cursor = subwindow.image_viewer.cursor()
        if tool_cursor is not None:
            layout = app.multi_window_layout
            layout.setCursor(tool_cursor)
            if layout.layout_widget is not None:
                layout.layout_widget.setCursor(tool_cursor)

    def on_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from multi-window layout."""
        app = self.app
        app.config_manager.set_multi_window_layout(layout_mode)
        app.main_window.set_layout_mode(layout_mode)
        subwindows = app.multi_window_layout.get_all_subwindows()
        self.ensure_all_subwindows_have_managers()
        self.connect_subwindow_signals()

        # Sync mouse mode (cursor) to all visible ImageViewers immediately so cursor
        # doesn't flicker between arrow and tool when hovering over different panes.
        # Also set the same cursor on the SubWindowContainer so when hit-test lands on
        # the container (border/frame) we don't show default arrow.
        # Set cursor on MultiWindowLayout and its layout_widget so in 1x1 any "background"
        # region (e.g. during layout settle) shows the tool cursor instead of arrow.
        current_mode = app.main_window.get_current_mouse_mode() if hasattr(app.main_window, 'get_current_mouse_mode') else "pan"
        tool_cursor = None
        for subwindow in subwindows:
            if subwindow and subwindow.isVisible() and subwindow.image_viewer:
                subwindow.image_viewer.set_mouse_mode(current_mode)
                subwindow.setCursor(subwindow.image_viewer.cursor())
                if tool_cursor is None:
                    tool_cursor = subwindow.image_viewer.cursor()
        if tool_cursor is not None:
            layout = app.multi_window_layout
            layout.setCursor(tool_cursor)
            if layout.layout_widget is not None:
                layout.layout_widget.setCursor(tool_cursor)

        self._schedule_viewport_resized_timer()

    def schedule_viewport_resized(self) -> None:
        """
        Schedule a viewport resize for all visible subwindows (e.g. after a swap).
        Uses the same coalesced 100ms timer as layout changes so that views that
        were last shown in a smaller pane (e.g. 2x2) get fit_to_view in the
        current window size.
        """
        self._schedule_viewport_resized_timer()

    def _schedule_viewport_resized_timer(self) -> None:
        """Start or restart the coalesced 100ms timer that runs _trigger_viewport_resized."""
        # Preserve pan: each visible pane saves viewport center before refit runs.
        self._capture_viewport_centers_for_visible_subwindows()
        if self._viewport_resized_timer is None:
            self._viewport_resized_timer = QTimer()
            self._viewport_resized_timer.setSingleShot(True)
            self._viewport_resized_timer.timeout.connect(self._trigger_viewport_resized)
        if self._viewport_resized_timer.isActive():
            self._viewport_resized_timer.stop()
        self._viewport_resized_timer.start(100)

    def on_main_window_layout_changed(self, layout_mode: str) -> None:
        """Handle layout mode change from main window menu.
        Deferred with QTimer.singleShot(0, ...) to avoid recursion: setting layout
        calls container.show(), which can deliver events that re-enter the app's
        eventFilter and exceed the recursion limit.
        """
        mode = layout_mode
        if DEBUG_LAYOUT:
            ts = datetime.now().strftime("%H:%M:%S.%f")
            print(f"[DEBUG-LAYOUT] [{ts}] on_main_window_layout_changed: scheduling deferred set_layout({mode!r})")
        QTimer.singleShot(0, lambda: self.app.multi_window_layout.set_layout(mode))

    def capture_subwindow_view_states(self) -> Dict[int, Dict[str, Any]]:
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

    def restore_subwindow_views(self, view_states: Dict[int, Dict[str, Any]]) -> None:
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

    def assign_series_to_subwindow(
        self,
        subwindow: Any,
        series_uid: str,
        slice_index: int,
        target_study_uid: Optional[str] = None,
    ) -> None:
        """Assign a series/slice to a specific subwindow. Delegates to file/series loading coordinator."""
        self.app._file_series_coordinator.assign_series_to_subwindow(
            subwindow, series_uid, slice_index, target_study_uid=target_study_uid
        )
