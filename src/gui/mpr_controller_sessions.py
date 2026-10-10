"""Live MPR session/view registry adapters for ``MprController``.

The controller owns one ``core.mpr_session_registry.MprSessionRegistry``.
The registry owns every constructed ``MprResult`` (through its sessions), the
stable view IDs, the one-to-one pane mapping and the pending admission
reservations. Nothing here copies result arrays or keeps a second mutable
registry of the same facts.

Ownership split:

- While a view is attached, its pane's ``subwindow_data`` / view-state manager
  / viewer are the live state (the existing display, tool and slider code
  mutates them directly). ``refresh_view_from_pane`` flushes that live state
  into the owning view; call it before any transfer, detach, thumbnail read
  or public metadata read.
- While a view is detached, the registry view is the only owner of its
  slice/combine/display state; its session owns the result.
- Transfer payloads arrive with the parking slice; this module owns only
  admission and the live pane flush.

Admission: a pane's pending build holds one registry reservation
(``controller._build_reservations``: pane -> ``(reservation_id, source_key)``;
the source key lets activation check the resolved volume against what was
reserved). It is released exactly once by
cancel, error, source closure, close-all or activation failure
(``release_pane_reservation`` is idempotent) and consumed only by a
successful activation. Moves, detach and reattach never reserve.

``controller`` is duck-typed like the other MPR helpers; failures to show a
message never raise.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMessageBox

from core.mpr_session_types import (
    AdmissionError,
    MprView,
)
from core.mpr_view_display_state import (
    capture_mpr_combine_state,
    capture_mpr_display_state,
)
from gui.mpr_admission import (
    PaneReservation,
    admission_summary,
    refresh_session_caps,
    set_status,
)

_TITLE_MPR = "MPR"


# ---------------------------------------------------------------------------
# Registry construction and user messages
# ---------------------------------------------------------------------------


def notify_mpr(controller: Any, text: str) -> None:
    """Best-effort warning dialog; a missing/stubbed window never raises."""
    try:
        QMessageBox.warning(controller._app.main_window, _TITLE_MPR, text)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Pending-build reservations (admission before volume construction)
# ---------------------------------------------------------------------------


def reserve_pane_build(
    controller: Any, idx: int, source_key: tuple[str, str], pending_bytes: int = 0
) -> bool:
    """Reserve one session plus one view slot for a new build into *idx*.

    Persisted caps are refreshed first, so a Settings change governs this
    decision. A pane holds at most one pending reservation: a stale one is
    released first. On refusal the user sees the limiting cap with the current
    usage and nothing is reserved; on admission the status bar shows the new
    usage. ``pending_bytes`` is the build's source-volume estimate.
    """
    release_pane_reservation(controller, idx)
    refresh_session_caps(controller)
    registry = controller._registry
    try:
        reservation_id = registry.reserve_build(*source_key)
    except AdmissionError as exc:
        notify_mpr(controller, f"{exc}\n{admission_summary(controller)}")
        return False
    controller._build_reservations[idx] = PaneReservation(reservation_id, source_key, pending_bytes)
    set_status(controller, f"Building MPR. {admission_summary(controller)}")
    return True


def release_pane_reservation(controller: Any, idx: int) -> bool:
    """Release *idx*'s pending reservation. Idempotent; True when one was released."""
    held = controller._build_reservations.pop(idx, None)
    if held is None:
        return False
    return controller._registry.cancel_reservation(held[0])


# ---------------------------------------------------------------------------
# Pane <-> view adapters
# ---------------------------------------------------------------------------


def _viewer(controller: Any, idx: int) -> Any:
    try:
        return controller._get_image_viewer(idx)
    except Exception:
        return None


def refresh_view_from_pane(controller: Any, idx: int) -> MprView | None:
    """Flush pane *idx*'s live slice/combine/display state into its view.

    Returns the owning view (None when the pane holds none). Only value
    state moves; the result stays owned by the session.
    """
    registry = controller._registry
    view = registry.view_for_pane(idx)
    if view is None:
        return None
    app = controller._app
    data = app.subwindow_data.get(idx)
    if not isinstance(data, dict) or not data.get("is_mpr"):
        return view
    try:
        registry.set_view_slice(view.view_id, int(data.get("mpr_slice_index", view.slice_index)))
    except (TypeError, ValueError):
        pass
    registry.set_view_combine(view.view_id, capture_mpr_combine_state(data))
    managers = app.subwindow_managers.get(idx, {})
    registry.set_view_display(
        view.view_id,
        capture_mpr_display_state(managers.get("view_state_manager"), _viewer(controller, idx)),
    )
    return view




# ---------------------------------------------------------------------------
def detached_view_ids(controller: Any) -> list[int]:
    """Detached view IDs in creation order."""
    return [v.view_id for v in controller._registry.ordered_views() if v.pane_index is None]


def emit_tiles_changed(controller: Any, dirty: Any = ()) -> None:
    """Announce, once per transaction, that navigator tiles need reconciling."""
    controller.mpr_tiles_changed.emit(frozenset(dirty))


__all__ = [
    "detached_view_ids",
    "emit_tiles_changed",
    "notify_mpr",
    "refresh_view_from_pane",
    "release_pane_reservation",
    "reserve_pane_build",
]
