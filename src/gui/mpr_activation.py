"""Atomic activation of a completed MPR build for ``MprController``.

A built (or cache-loaded) ``MprResult`` becomes a new registry session plus
its first view, installed into the target pane. Admission was reserved before
volume construction; this module validates the target and result first, then
consumes the reservation only after the first slice rendered, so a failed
activation:

- restores the pane's prior state (an ordinary image or an existing MPR),
- releases the reservation, and
- creates no session, view, or success signal.

A successful activation over an occupied MPR pane keeps the displaced view
alive as a detached registry view (its live pane state is flushed into it
first). Activation never discards another view. With no pending reservation
(direct activation) it reserves first, so the caps apply uniformly to cache
hits and direct calls.
"""

from __future__ import annotations

from typing import Any

from core.mpr_view_display_state import (
    capture_mpr_combine_state,
    capture_mpr_display_state,
)
from gui.mpr_admission import admission_summary, set_status
from gui.mpr_controller_sessions import (
    emit_tiles_changed,
    notify_mpr,
    refresh_view_from_pane,
    release_pane_reservation,
    reserve_pane_build,
)
from gui.mpr_controller_transactions import (
    capture_destination_snapshot,
    restore_failed_install,
    validate_install_request,
)
from gui.mpr_worker_fencing import volume_source_key
from utils.debug_flags import DEBUG_MPR


def _confirm_first_view(
    controller: Any, idx: int, reservation_id: int, result: Any, orientation_label: str,
    data: dict[str, Any],
) -> None:
    """Turn the pending reservation into the session plus pane-attached first view."""
    managers = controller._app.subwindow_managers.get(idx, {})
    controller._registry.confirm_build(
        reservation_id,
        result=result,
        orientation=orientation_label,
        slice_index=0,
        pane_index=idx,
        combine=capture_mpr_combine_state(data),
        display=capture_mpr_display_state(
            managers.get("view_state_manager"), controller._get_image_viewer(idx)
        ),
    )


def _reject(controller: Any, idx: int, text: str) -> bool:
    """Refuse an activation before any mutation: release the pane's reservation, tell the user."""
    release_pane_reservation(controller, idx)
    notify_mpr(controller, text)
    return False


def activate_built_mpr(
    controller: Any, idx: int, result: Any, orientation_label: str, request: Any | None = None
) -> bool:
    """Install *result* as a new session's first view in pane *idx*.

    Returns True on success. Preconditions are checked before anything is
    reserved, snapshotted or written: a real target pane with an image
    viewer, a usable result (source datasets and at least one slice), and a
    resolved volume whose source matches the held reservation. The first
    slice must actually render (``display_mpr_slice`` returns True) before a
    session is confirmed, so a viewer-less or unrenderable target never gets
    a ghost view. Every failure path releases the reservation and leaves the
    pane and registry as they were.
    """
    app = controller._app
    if validate_install_request(app, controller._get_image_viewer, idx, {"mpr_result": result}) is None:
        return _reject(
            controller, idx, "The MPR could not be activated: the target window or result is unavailable."
        )
    data = app.subwindow_data[idx]
    source_key = volume_source_key(result.source_volume)
    held = controller._build_reservations.get(idx)
    if held is not None and held[1] != source_key:
        return _reject(controller, idx, "The MPR could not be activated: its source does not match the request.")
    if held is None and not reserve_pane_build(controller, idx, source_key):
        return False
    reservation_id = controller._build_reservations.pop(idx)[0]
    # Preserve an occupant's live state in its view before the pane is reused.
    displaced = refresh_view_from_pane(controller, idx) is not None
    snapshot = capture_destination_snapshot(app, controller._get_image_viewer, idx)
    if DEBUG_MPR:
        print(f"[DEBUG-MPR] Activating MPR: window={idx} displaced_view={displaced}")
    try:
        source_ds = result.source_volume.source_datasets[0]
        controller._ensure_mpr_previous_state(data)
        controller._activate_write_mpr_fields(
            idx, data, result, orientation_label, request, source_ds
        )
        controller._sync_slice_navigator_for_mpr(idx, result.n_slices, 0)
        controller._set_tools_enabled(idx, enabled=False)
        controller._reset_window_level_for_mpr(idx, source_ds)
        if controller.display_mpr_slice(idx, 0) is False:
            raise RuntimeError("MPR slice could not be rendered")
        controller._fit_image_viewer_after_mpr(idx)
        controller._apply_mpr_banner(idx, data)
        controller._sync_intensity_projection_if_focused(idx, data)
        _confirm_first_view(controller, idx, reservation_id, result, orientation_label, data)
    except Exception:
        controller._registry.cancel_reservation(reservation_id)
        restored = restore_failed_install(controller, idx, snapshot, controller._get_image_viewer)
        if DEBUG_MPR:
            print("[DEBUG-MPR] activation failed; destination restored where possible")
        notify_mpr(
            controller,
            "The MPR could not be activated; the window was left as it was."
            if restored
            else "The MPR could not be activated and the window could not be fully "
            "restored. Reload this window's series.",
        )
        return False
    controller._activate_focus_subwindow(idx)
    if displaced:
        controller.mpr_detached.emit(idx)
    controller.mpr_activated.emit(idx)
    emit_tiles_changed(controller, {controller.attached_view_id(idx)})
    set_status(controller, f"MPR added. {admission_summary(controller)}")
    return True


__all__ = ["activate_built_mpr"]
