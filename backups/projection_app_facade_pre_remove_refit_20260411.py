"""
Intensity projection / MPR combine UI logic for DICOMViewerApp.

Holds handlers previously on ``DICOMViewerApp`` in ``main.py``: syncing the
right-pane Combine Slices widget from MPR subwindow state, and reacting to
projection enabled/type/slice-count changes. ``DICOMViewerApp`` keeps one-line
delegates so existing Qt signal connections (e.g. in ``SubwindowLifecycleController``)
need not retarget.

Inputs:
    - App reference passed at construction (expects the same attributes the
      former methods used: ``intensity_projection_controls_widget``,
      ``slice_display_manager``, ``subwindow_data``, ``_mpr_controller``, etc.).

Outputs:
    - Mutates slice display manager, widgets, and may call ``_display_slice`` /
      ``_mpr_controller.display_mpr_slice`` on the app.

Requirements:
    - PySide6 widgets and managers as constructed by ``DICOMViewerApp`` init order.
"""

from __future__ import annotations

from typing import Any, Dict

from utils.debug_flags import DEBUG_PROJECTION


class ProjectionAppFacade:
    """Cohesive projection / combine-slices behavior cut from ``DICOMViewerApp``."""

    __slots__ = ("_app",)

    def __init__(self, app: Any) -> None:
        self._app = app

    def sync_intensity_projection_widget_from_mpr_data(self, data: Dict[str, Any]) -> None:
        """Push ``mpr_combine_*`` from *data* to the right-pane Combine Slices widget."""
        app = self._app
        w = app.intensity_projection_controls_widget
        w.enable_checkbox.blockSignals(True)
        w.projection_combo.blockSignals(True)
        w.slice_count_combo.blockSignals(True)
        try:
            w.set_enabled(
                bool(data.get("mpr_combine_enabled", False)),
                keep_signals_blocked=True,
            )
            w.set_projection_type(str(data.get("mpr_combine_mode", "aip") or "aip"))
            w.set_slice_count(int(data.get("mpr_combine_slice_count", 4) or 4))
        finally:
            w.enable_checkbox.blockSignals(False)
            w.projection_combo.blockSignals(False)
            w.slice_count_combo.blockSignals(False)

    def on_projection_enabled_changed(self, enabled: bool) -> None:
        """
        Handle projection enabled state change.

        This handler is called when the checkbox state changes (either user-initiated or programmatic).
        When user clicks checkbox, signal is emitted and we should update manager to match user's intent.
        When programmatically set (e.g., during reset), signals are blocked so this shouldn't be called.

        Args:
            enabled: True if projection mode enabled, False otherwise
        """
        app = self._app
        if DEBUG_PROJECTION:
            print(
                f"[DEBUG-PROJECTION] _on_projection_enabled_changed: enabled={enabled}, "
                f"_resetting_projection_state={app._resetting_projection_state}"
            )

        # Check current states BEFORE updating manager
        current_widget_state = app.intensity_projection_controls_widget.get_enabled()
        current_manager_state = app.slice_display_manager.projection_enabled
        checkbox_visual_state = app.intensity_projection_controls_widget.enable_checkbox.isChecked()
        if DEBUG_PROJECTION:
            print(
                f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Current widget state={current_widget_state}, "
                f"checkbox visual state={checkbox_visual_state}, manager state={current_manager_state}, signal enabled={enabled}"
            )

        # If we're resetting and signal doesn't match manager state, sync widget to manager (ignore signal)
        if app._resetting_projection_state and current_manager_state != enabled:
            if DEBUG_PROJECTION:
                print(
                    f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Reset in progress: ignoring signal ({enabled}), "
                    f"syncing widget to manager ({current_manager_state})"
                )
            app.intensity_projection_controls_widget.set_enabled(current_manager_state)
        else:
            # Normal case: update manager state to match the signal (user's intent)
            if DEBUG_PROJECTION:
                print(
                    f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Updating manager state to match signal ({enabled})"
                )
            app.slice_display_manager.set_projection_enabled(enabled)

            # Verify the update took effect
            updated_state = app.slice_display_manager.projection_enabled
            if DEBUG_PROJECTION:
                print(
                    f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Manager state after update: {updated_state}, "
                    f"manager object ID: {id(app.slice_display_manager)}"
                )

            # Verify ROI coordinator is using the same manager
            if hasattr(app, "roi_coordinator") and app.roi_coordinator is not None:
                if app.roi_coordinator.get_projection_enabled is not None:
                    try:
                        # Check what the callback returns
                        callback_result = app.roi_coordinator.get_projection_enabled()
                        if DEBUG_PROJECTION:
                            print(
                                f"[DEBUG-PROJECTION] _on_projection_enabled_changed: ROI coordinator callback returns: {callback_result}"
                            )

                        # Try to inspect the closure to see what manager it references
                        if (
                            hasattr(app.roi_coordinator.get_projection_enabled, "__closure__")
                            and app.roi_coordinator.get_projection_enabled.__closure__
                        ):
                            # The closure should contain the managers dict
                            closure_vars = [
                                cell.cell_contents
                                for cell in app.roi_coordinator.get_projection_enabled.__closure__
                            ]
                            if DEBUG_PROJECTION:
                                print(
                                    f"[DEBUG-PROJECTION] _on_projection_enabled_changed: ROI coordinator callback closure vars: {[type(v).__name__ for v in closure_vars]}"
                                )

                            # Check if the manager in the closure is the same as app.slice_display_manager
                            for var in closure_vars:
                                if isinstance(var, dict) and "slice_display_manager" in var:
                                    manager_from_closure = var["slice_display_manager"]
                                    if DEBUG_PROJECTION:
                                        print(
                                            f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Manager from closure ID: {id(manager_from_closure)}, "
                                            f"self.slice_display_manager ID: {id(app.slice_display_manager)}, "
                                            f"same object: {manager_from_closure is app.slice_display_manager}, "
                                            f"closure manager projection_enabled: {manager_from_closure.projection_enabled}, "
                                            f"self.slice_display_manager projection_enabled: {app.slice_display_manager.projection_enabled}"
                                        )
                                    if manager_from_closure is not app.slice_display_manager:
                                        if DEBUG_PROJECTION:
                                            print(
                                                "[DEBUG-PROJECTION] _on_projection_enabled_changed: WARNING - Manager objects are different! "
                                                "This could cause synchronization issues."
                                            )
                                    break
                    except Exception as e:
                        if DEBUG_PROJECTION:
                            print(
                                f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Error checking ROI coordinator callback: {e}"
                            )
                            import traceback

                            traceback.print_exc()

            # Widget state should already match signal, but verify and sync if needed
            if current_widget_state != enabled:
                if DEBUG_PROJECTION:
                    print(
                        f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Widget state ({current_widget_state}) != signal ({enabled}), syncing widget"
                    )
                app.intensity_projection_controls_widget.set_enabled(enabled)
            else:
                pass

        # Redisplay current slice with new projection state
        if app.current_dataset is not None:
            if hasattr(app, "roi_coordinator") and app.roi_coordinator is not None:
                if app.roi_coordinator.get_projection_enabled is not None:
                    callback_state = app.roi_coordinator.get_projection_enabled()
                    if callback_state != app.slice_display_manager.projection_enabled:
                        if DEBUG_PROJECTION:
                            print(
                                f"[DEBUG-PROJECTION] _on_projection_enabled_changed: WARNING - Callback state mismatch! "
                                f"Callback={callback_state}, Manager={app.slice_display_manager.projection_enabled}"
                            )

        # MPR combine refresh must run even when app.current_dataset is None (MPR uses subwindow_data).
        focused_idx = app.focused_subwindow_index
        if (
            hasattr(app, "_mpr_controller")
            and app._mpr_controller.is_mpr(focused_idx)
            and not app._resetting_projection_state
        ):
            mp_data = app.subwindow_data.get(focused_idx)
            if mp_data is not None:
                w = app.intensity_projection_controls_widget
                mp_data["mpr_combine_enabled"] = w.get_enabled()
                mp_data["mpr_combine_mode"] = w.get_projection_type()
                mp_data["mpr_combine_slice_count"] = w.get_slice_count()
                app._mpr_controller.display_mpr_slice(
                    focused_idx,
                    mp_data.get("mpr_slice_index", 0),
                    refit_window_level_for_combine=True,
                )
            selected_roi = app.roi_manager.get_selected_roi()
            if selected_roi is not None and DEBUG_PROJECTION:
                print(
                    "[DEBUG-PROJECTION] _on_projection_enabled_changed: "
                    "Selected ROI after MPR combine refresh"
                )
            return

        if app.current_dataset is not None:
            app._display_slice(app.current_dataset)

            selected_roi = app.roi_manager.get_selected_roi()
            if selected_roi is not None:
                if DEBUG_PROJECTION:
                    print(
                        f"[DEBUG-PROJECTION] _on_projection_enabled_changed: Selected ROI exists, statistics should be updated by _display_rois_for_slice"
                    )
        elif DEBUG_PROJECTION:
            print(
                "[DEBUG-PROJECTION] _on_projection_enabled_changed: current_dataset is None, cannot redisplay"
            )

    def on_projection_type_changed(self, projection_type: str) -> None:
        """
        Handle projection type change.

        Args:
            projection_type: "aip", "mip", or "minip"
        """
        app = self._app
        app.slice_display_manager.set_projection_type(projection_type)
        app.intensity_projection_controls_widget.set_projection_type(projection_type)
        focused_idx = app.focused_subwindow_index
        if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(focused_idx):
            mp_data = app.subwindow_data.get(focused_idx)
            if mp_data is not None:
                mp_data["mpr_combine_mode"] = projection_type
                combine_on = bool(mp_data.get("mpr_combine_enabled"))
                app._mpr_controller.display_mpr_slice(
                    focused_idx,
                    mp_data.get("mpr_slice_index", 0),
                    refit_window_level_for_combine=combine_on,
                )
            return
        if app.current_dataset is not None and app.slice_display_manager.projection_enabled:
            app._display_slice(app.current_dataset)

    def on_projection_slice_count_changed(self, count: int) -> None:
        """
        Handle projection slice count change.

        Args:
            count: Number of slices to combine (2, 3, 4, 6, or 8)
        """
        app = self._app
        if DEBUG_PROJECTION:
            print(
                f"[DEBUG-PROJECTION] _on_projection_slice_count_changed: count={count}, "
                f"projection_enabled={app.slice_display_manager.projection_enabled}"
            )
        app.slice_display_manager.set_projection_slice_count(count)
        app.intensity_projection_controls_widget.set_slice_count(count)
        focused_idx = app.focused_subwindow_index
        if hasattr(app, "_mpr_controller") and app._mpr_controller.is_mpr(focused_idx):
            mp_data = app.subwindow_data.get(focused_idx)
            if mp_data is not None:
                mp_data["mpr_combine_slice_count"] = count
                combine_on = bool(mp_data.get("mpr_combine_enabled"))
                app._mpr_controller.display_mpr_slice(
                    focused_idx,
                    mp_data.get("mpr_slice_index", 0),
                    refit_window_level_for_combine=combine_on,
                )
            return
        if app.current_dataset is not None and app.slice_display_manager.projection_enabled:
            if DEBUG_PROJECTION:
                print("[DEBUG-PROJECTION] _on_projection_slice_count_changed: Redisplaying slice")
            app._display_slice(app.current_dataset)
