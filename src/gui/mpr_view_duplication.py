"""Shared-result duplication (plain or linked) of an MPR view into a pane.

A duplicate is a new *view* of an existing session: it shares the session's
``MprResult`` by reference (no new session, no array copy) and takes its own
copy of the source view's slice, combine and display state, so later edits to
either view never alias the other. By default the duplicate is
unlinked; ``linked=True`` adds a session-local link group inside the same
transaction.

Transaction order (nothing is created until the pane really rendered):

1. Resolve the source view and build its install payload; validate the
   target pane/viewer/result. Duplicating into the source's own pane is
   refused.
2. Reserve one view slot (``reserve_view``). At the view cap this refuses and
   names the limit; moves, detach and reattach are unaffected by that cap.
3. Cancel a pending build in the target, flush an occupant's live state into
   its view, snapshot the target, then install through the normal transfer
   install (which rolls itself back and requires a rendered first slice).
4. Confirm the reservation from the target pane's *installed* state, which
   atomically detaches an occupant, so the displaced view survives.

Every step after the reservation runs inside one cleanup bracket, so an
exception from focusing, snapshotting, installing or confirming cancels the
reservation exactly once. A failure restores the target (reporting honestly
when the restore itself was incomplete), emits no success signals, and leaves
the registry as it was. The source view is never touched.
"""

from __future__ import annotations

from typing import Any

from core.mpr_session_types import AdmissionError
from core.mpr_view_display_state import (
    capture_mpr_combine_state,
    capture_mpr_display_state,
)
from gui.mpr_controller_sessions import (
    build_view_payload,
    capture_pane_payload,
    emit_tiles_changed,
    find_view,
    notify_mpr,
    refresh_view_from_pane,
)
from gui.mpr_controller_transactions import (
    capture_destination_snapshot,
    focus_destination,
    restore_failed_install,
    validate_install_request,
    validate_transfer_target,
)
from gui.mpr_view_links import link_after_duplicate


def _source_payload(controller: Any, view_id: int) -> tuple[Any, dict[str, Any]] | None:
    """``(view, payload)`` for the source, flushing live pane state first."""
    view = find_view(controller, view_id)
    if view is None:
        return None
    if view.pane_index is None:
        payload = build_view_payload(controller, view_id)
    else:
        payload = capture_pane_payload(controller, view.pane_index)
    return None if payload is None else (view, payload)


def _confirm_duplicate(controller: Any, to_idx: int, reservation_id: int) -> None:
    """Confirm the reservation from the target pane's installed state."""
    app = controller._app
    data = app.subwindow_data[to_idx]
    managers = app.subwindow_managers.get(to_idx, {})
    controller._registry.confirm_view(
        reservation_id,
        slice_index=int(data.get("mpr_slice_index", 0)),
        pane_index=to_idx,
        combine=capture_mpr_combine_state(data),
        display=capture_mpr_display_state(
            managers.get("view_state_manager"), controller._get_image_viewer(to_idx)
        ),
    )


def duplicate_view_into_pane(
    controller: Any, view_id: int, to_idx: int, *, linked: bool = False
) -> bool:
    """Duplicate view *view_id* into pane *to_idx*. Returns True on success.

    With ``linked=True`` the new view also joins the source's link group (the
    group is created from source + duplicate when the source was unlinked).
    Linking is part of the transaction: if it fails, the confirmed duplicate
    is discarded, a displaced occupant is re-attached, the pane is restored and
    existing links are untouched.
    """
    resolved = _source_payload(controller, view_id)
    if resolved is None:
        return False
    source, payload = resolved
    app = controller._app
    if source.pane_index == to_idx:
        return False  # the source's own pane is never a duplicate target
    if not validate_transfer_target(app, controller._get_image_viewer, to_idx):
        return False
    if validate_install_request(app, controller._get_image_viewer, to_idx, payload) is None:
        return False
    registry = controller._registry
    try:
        reservation_id = registry.reserve_view(source.session_id)
    except AdmissionError as exc:
        notify_mpr(controller, f"{exc}\n{registry.admission_message()}")
        return False

    confirmed = False
    snapshot = None
    occupant_id: int | None = None
    failure = ""
    try:
        focus_destination(controller, to_idx)
        controller._cancel_mpr_worker(to_idx)
        occupant = refresh_view_from_pane(controller, to_idx)
        occupant_id = None if occupant is None else occupant.view_id
        snapshot = capture_destination_snapshot(app, controller._get_image_viewer, to_idx)
        if not controller._install_mpr_payload_at_subwindow(to_idx, payload):
            # The install rolled itself back (and warned if it could not).
            failure = "Could not duplicate the MPR into this window."
        else:
            _confirm_duplicate(controller, to_idx, reservation_id)
            confirmed = True
            if linked:
                link_after_duplicate(controller, source.view_id, controller.attached_view_id(to_idx))
    except Exception:
        if confirmed:
            _undo_commit(controller, to_idx, occupant_id)
            confirmed = False
        failure = _restore_after_failure(controller, to_idx, snapshot)
    finally:
        if not confirmed:
            registry.cancel_reservation(reservation_id)  # idempotent; never strand the slot
    if not confirmed:
        notify_mpr(controller, failure)
        return False
    if occupant_id is not None:
        controller.mpr_detached.emit(to_idx)
    controller.mpr_activated.emit(to_idx)
    emit_tiles_changed(controller, {controller.attached_view_id(to_idx)})
    return True


def _undo_commit(controller: Any, to_idx: int, occupant_id: int | None) -> None:
    """Undo a confirmed duplicate: discard it, then re-attach the displaced occupant.

    Discarding a view also removes it from any link group it had joined, so no
    membership survives. Never raises; the caller restores the pane itself.
    """
    registry = controller._registry
    try:
        new_view = registry.view_for_pane(to_idx)
        if new_view is not None and new_view.view_id != occupant_id:
            registry.discard_view(new_view.view_id)
        if occupant_id is not None:
            registry.attach_view(occupant_id, to_idx)
    except Exception:
        pass


def _restore_after_failure(controller: Any, to_idx: int, snapshot: Any) -> str:
    """Restore the target after an exception and return an accurate user message.

    With no snapshot nothing in the pane was touched yet. Otherwise the
    message reports whether the restore really completed.
    """
    restored = True
    if snapshot is not None:
        try:
            restored = bool(
                restore_failed_install(controller, to_idx, snapshot, controller._get_image_viewer)
            )
        except Exception:
            restored = False
    if restored:
        return "Could not duplicate the MPR into this window; it was left as it was."
    return (
        "Could not duplicate the MPR and the window could not be fully restored. "
        "Reload this window's series."
    )


__all__ = ["duplicate_view_into_pane"]
