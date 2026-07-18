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
from typing import Any

from pydicom.dataset import Dataset
from PySide6.QtCore import QPointF, QRectF, QTimer

from core.subwindow_signal_wiring import (
    connect_all_subwindow_context_menu_signals as _wiring_connect_context_menu,
)
from core.subwindow_signal_wiring import (
    connect_all_subwindow_transform_signals as _wiring_connect_transforms,
)
from core.subwindow_signal_wiring import (
    connect_focused_subwindow_signals as _wiring_connect_focused,
)
from core.subwindow_signal_wiring import (
    connect_subwindow_signals as _wiring_connect_subwindow,
)
from core.subwindow_signal_wiring import (
    disconnect_focused_subwindow_signals as _wiring_disconnect_focused,
)
from core.subwindow_signal_wiring import (
    wire_pixel_info_callbacks_for_subwindow as _wiring_pixel_info,
)
from utils.debug_flags import DEBUG_LAYOUT


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
        self._histogram_slots: dict[int, Any] = {}  # id(image_viewer) -> callable
        self._mpr_open_slots: dict[int, Any] = {}   # id(image_viewer) -> callable
        self._mpr_clear_slots: dict[int, Any] = {}  # id(image_viewer) -> callable
        self._3d_view_slots: dict[int, Any] = {}    # id(image_viewer) -> callable
        self._clear_window_slots: dict[int, Any] = {}  # id(image_viewer) -> callable
        self._cine_toggle_slots: dict[int, Any] = {}  # id(image_viewer) -> callable
        self._cine_stop_slots: dict[int, Any] = {}  # id(image_viewer) -> callable
        self._rdsr_report_slots: dict[int, Any] = {}  # id(image_viewer) -> callable (dose SR dialog)
        # Single restartable timer for 100ms viewport-resized callback; coalesces rapid layout changes.
        self._viewport_resized_timer: QTimer | None = None

    def get_subwindow_dataset(self, idx: int) -> Dataset | None:
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
        out: Dataset | None = None
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
        """Bind dataset/slice/rescale callbacks for pixel readout and direction labels."""
        _wiring_pixel_info(self, image_viewer, idx)

    def get_focused_subwindow_index(self) -> int:
        """Return the currently focused subwindow index (0-3). Used for histogram and other per-view features."""
        return self.app.focused_subwindow_index

    def get_histogram_callbacks_for_subwindow(self, idx: int) -> dict[str, Any]:
        """
        Return a dict of callbacks for the histogram dialog tied to subwindow idx.
        Used so each histogram always shows the image currently displayed in that subwindow.
        """
        if idx not in self.app.subwindow_managers:
            return {}
        vsm = self.app.subwindow_managers[idx].get('view_state_manager')
        if vsm is None:
            return {}
        self.app.subwindow_managers[idx].get("slice_display_manager")
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
            from core.mpr_stack_combine import apply_mpr_stack_combine

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
                from core.mpr_stack_combine import apply_mpr_stack_combine

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
        _ = preserve_view  # retained for call-site compatibility
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
        managers.get('view_state_manager')
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
        """Connect signals that apply to all subwindows. Body in ``subwindow_signal_wiring``."""
        _wiring_connect_subwindow(self)

    def connect_all_subwindow_transform_signals(self) -> None:
        """Connect transform/zoom for all subwindows. Body in ``subwindow_signal_wiring``."""
        _wiring_connect_transforms(self)

    def connect_all_subwindow_context_menu_signals(self) -> None:
        """Connect context menu signals for all subwindows. Body in ``subwindow_signal_wiring``."""
        _wiring_connect_context_menu(self)

    def disconnect_focused_subwindow_signals(self) -> None:
        """Disconnect signals from previously focused subwindow. Body in ``subwindow_signal_wiring``."""
        _wiring_disconnect_focused(self)

    def connect_focused_subwindow_signals(self) -> None:
        """Connect signals for the currently focused subwindow. Body in ``subwindow_signal_wiring``."""
        _wiring_connect_focused(self)

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

    def capture_subwindow_view_states(self) -> dict[int, dict[str, Any]]:
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

    def restore_subwindow_views(self, view_states: dict[int, dict[str, Any]]) -> None:
        """Restore subwindow views after layout change (fit to view)."""
        app = self.app
        subwindows = app.multi_window_layout.get_all_subwindows()
        for idx, _view_state in view_states.items():
            try:
                if idx >= len(subwindows) or subwindows[idx] is None:
                    continue
                subwindow = subwindows[idx]
                image_viewer = subwindow.image_viewer
                if image_viewer is None:
                    continue
                if image_viewer.image_item is None:
                    continue

                # Bind image_viewer per iteration: the timer fires after this loop
                # ends, so a closure over the loop variable would fit only the last
                # subwindow, for every pane.
                def fit_image_to_viewport(image_viewer=image_viewer):
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
        target_study_uid: str | None = None,
    ) -> None:
        """Assign a series/slice to a specific subwindow. Delegates to file/series loading coordinator."""
        self.app._file_series_coordinator.assign_series_to_subwindow(
            subwindow, series_uid, slice_index, target_study_uid=target_study_uid
        )
