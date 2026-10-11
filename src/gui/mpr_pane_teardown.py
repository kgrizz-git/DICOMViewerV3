"""Pane-level MPR tear-down for ``MprController``.

Removes the MPR keys from one pane's ``subwindow_data``, restores the pre-MPR
2-D state when one was saved, and refreshes dependent chrome. It never touches
the session/view registry and never emits signals: callers decide whether the
view is detached (kept) or discarded, and emit the matching signal.

``controller`` is duck-typed (``_app``, ``_get_image_viewer``,
``_set_tools_enabled``); helpers swallow missing-widget failures like the
original controller methods did.
"""

from __future__ import annotations

from typing import Any

from core.mpr_view_display_state import clear_mpr_lut_override
from utils.privacy.console import print_redacted


def tear_down_mpr_at_subwindow(controller: Any, idx: int) -> None:
    """
    Remove MPR keys from *idx*, restore the pre-MPR 2-D state (if any), and
    refresh dependent UI. Does not emit signals.
    """
    data = controller._app.subwindow_data.get(idx)
    if data is None:
        return

    _remove_slice_location_manager(controller, idx)
    previous_state = data.get("mpr_previous_state")
    image_viewer = controller._get_image_viewer(idx)
    _clear_mpr_keys(data)
    _clear_mpr_lut_override(controller, idx)
    controller._set_tools_enabled(idx, enabled=True)
    _clear_mpr_banner(controller, idx)

    if isinstance(previous_state, dict):
        _restore_previous_state(controller, idx, data, previous_state)
    else:
        _clear_dataset_fields(data)

    if data.get("current_dataset") is None and image_viewer is not None:
        _clear_empty_viewer(controller, idx, image_viewer)

    _refresh_navigators_and_ui(controller, idx, data)

def _remove_slice_location_manager(controller: Any, idx: int) -> None:
    """Drop slice-location line manager before scene changes."""
    try:
        line_coord = getattr(controller._app, "_slice_location_line_coordinator", None)
        if line_coord is not None:
            line_coord.remove_manager(idx)
    except Exception:
        pass

def _clear_mpr_keys(data: dict[str, Any]) -> None:
    """Remove MPR-specific keys from subwindow data."""
    for key in (
        "is_mpr",
        "mpr_result",
        "mpr_orientation",
        "mpr_slice_index",
        "mpr_source_dataset",
        "mpr_previous_state",
        "mpr_combine_enabled",
        "mpr_combine_mode",
        "mpr_combine_slice_count",
    ):
        data.pop(key, None)

def _clear_mpr_lut_override(controller: Any, idx: int) -> None:
    """Drop a stale per-pane MPR LUT override when leaving MPR mode."""
    try:
        managers = controller._app.subwindow_managers.get(idx, {})
        clear_mpr_lut_override(managers.get("view_state_manager"))
    except Exception:
        pass

def _clear_mpr_banner(controller: Any, idx: int) -> None:
    """Clear the MPR banner on the overlay manager, if present."""
    managers = controller._app.subwindow_managers.get(idx, {})
    overlay_manager = managers.get("overlay_manager")
    if overlay_manager is not None and hasattr(overlay_manager, "set_mpr_banner"):
        overlay_manager.set_mpr_banner(None)

def _clear_dataset_fields(data: dict[str, Any]) -> None:
    """Reset current dataset fields when no previous state exists."""
    data["current_dataset"] = None
    data["current_slice_index"] = 0
    data["current_study_uid"] = ""
    data["current_series_uid"] = ""
    data["current_datasets"] = []

def _restore_previous_state(
    controller: Any, idx: int, data: dict[str, Any], previous_state: dict[str, Any]
) -> None:
    """Restore pre-MPR 2-D state and redisplay the prior slice when possible."""
    data.update(previous_state)
    previous_dataset = previous_state.get("current_dataset")
    previous_slice_index = previous_state.get("current_slice_index", 0)
    previous_study_uid = previous_state.get("current_study_uid", "")
    previous_series_uid = previous_state.get("current_series_uid", "")

    sdm = controller._app.subwindow_managers.get(idx, {}).get("slice_display_manager")
    if sdm is not None and previous_dataset is not None:
        try:
            sdm.display_slice(
                previous_dataset,
                controller._app.current_studies,
                previous_study_uid,
                previous_series_uid,
                previous_slice_index,
                preserve_view_override=True,
                update_controls=(idx == getattr(controller._app, "focused_subwindow_index", -1)),
                update_metadata=(idx == getattr(controller._app, "focused_subwindow_index", -1)),
            )
        except Exception as exc:
            print_redacted(
                f"[MprController] Failed to restore prior slice in window {idx}: {exc}"
            )

    if idx == getattr(controller._app, "focused_subwindow_index", -1):
        controller._app.current_dataset = previous_dataset
        controller._app.current_slice_index = previous_slice_index
        controller._app.current_study_uid = previous_study_uid
        controller._app.current_series_uid = previous_series_uid
        controller._app.current_datasets = previous_state.get("current_datasets", [])

def _clear_empty_viewer(controller: Any, idx: int, image_viewer: Any) -> None:
    """Clear the viewer and view-state when no dataset remains after tear-down."""
    managers = controller._app.subwindow_managers.get(idx, {})
    overlay_manager = managers.get("overlay_manager")
    try:
        if overlay_manager is not None:
            overlay_manager.clear_overlay_items(image_viewer.scene)
        image_viewer.scene.clear()
        image_viewer.image_item = None
        image_viewer.original_image = None
        image_viewer.viewport().update()
    except Exception as exc:
        print_redacted(f"[MprController] Failed to clear MPR view in window {idx}: {exc}")

    view_state_manager = managers.get("view_state_manager")
    if view_state_manager is not None:
        try:
            view_state_manager.set_current_data_context(None, {}, "", "", 0)
            view_state_manager.set_current_series_identifier(None)
        except Exception as exc:
            print_redacted(
                f"[MprController] Failed to reset view state for window {idx}: {exc}"
            )

    if idx == getattr(controller._app, "focused_subwindow_index", -1):
        controller._app.current_dataset = None
        controller._app.current_slice_index = 0
        controller._app.current_study_uid = ""
        controller._app.current_series_uid = ""
        controller._app.current_datasets = []

def _refresh_navigators_and_ui(controller: Any, idx: int, data: dict[str, Any]) -> None:
    """Refresh navigators, slot map, lines, and slider after tear-down."""
    try:
        if (
            hasattr(controller._app, "slice_navigator")
            and idx == getattr(controller._app, "focused_subwindow_index", -1)
        ):
            datasets = data.get("current_datasets") or []
            controller._app.slice_navigator.set_total_slices(len(datasets))
            controller._app.slice_navigator.blockSignals(True)
            controller._app.slice_navigator.current_slice_index = data.get(
                "current_slice_index", 0
            )
            controller._app.slice_navigator.blockSignals(False)
    except Exception:
        pass

    try:
        if hasattr(controller._app, "series_navigator") and hasattr(
            controller._app, "_get_subwindow_assignments"
        ):
            assignments = controller._app._get_subwindow_assignments()
            controller._app.series_navigator.set_subwindow_assignments(assignments)
    except Exception:
        pass

    try:
        refresh_window_slot_map = getattr(
            controller._app, "_refresh_window_slot_map_widgets", None
        )
        if callable(refresh_window_slot_map):
            refresh_window_slot_map()
    except Exception:
        pass

    try:
        line_coord = getattr(controller._app, "_slice_location_line_coordinator", None)
        if line_coord is not None:
            line_coord.refresh_all()
    except Exception:
        pass

    try:
        sync = getattr(controller._app, "_sync_navigation_slider_for_subwindow", None)
        if callable(sync):
            sync(idx)
    except Exception:
        pass


__all__ = ["tear_down_mpr_at_subwindow"]
