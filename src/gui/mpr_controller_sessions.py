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
- The transfer "payload" is an adapter built on demand from the view and
  session (``build_view_payload``). It is not stored.

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

from dataclasses import replace
from typing import Any

import numpy as np
from PySide6.QtWidgets import QMessageBox

from core.mpr_session_registry import MprSessionRegistry
from core.mpr_session_types import (
    DEFAULT_SESSION_CAP,
    DEFAULT_VIEW_CAP,
    AdmissionError,
    MprDisplayState,
    MprView,
    MprViewMetadata,
    UnknownViewError,
)
from core.mpr_stack_combine import apply_mpr_stack_combine
from core.mpr_view_display_state import (
    capture_mpr_combine_state,
    capture_mpr_display_state,
)

_TITLE_MPR = "MPR"


# ---------------------------------------------------------------------------
# Registry construction and user messages
# ---------------------------------------------------------------------------


def resolve_session_caps(app: Any) -> tuple[int, int]:
    """Validated ``(session_cap, view_cap)`` from config, else the defaults.

    Stubbed or broken config objects must not stop the controller from
    starting, so anything that is not an exact ``1 <= session <= view`` int
    pair falls back to the compiled defaults.
    """
    try:
        session_cap, view_cap = app.config_manager.get_mpr_caps()
    except Exception:
        return DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP
    if type(session_cap) is int and type(view_cap) is int and 1 <= session_cap <= view_cap:
        return session_cap, view_cap
    return DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP


def create_registry(app: Any) -> MprSessionRegistry:
    """Registry sized from the configured admission caps."""
    session_cap, view_cap = resolve_session_caps(app)
    return MprSessionRegistry(session_cap, view_cap)


def notify_mpr(controller: Any, text: str) -> None:
    """Best-effort warning dialog; a missing/stubbed window never raises."""
    try:
        QMessageBox.warning(controller._app.main_window, _TITLE_MPR, text)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Pending-build reservations (admission before volume construction)
# ---------------------------------------------------------------------------


def reserve_pane_build(controller: Any, idx: int, source_key: tuple[str, str]) -> bool:
    """Reserve one session plus one view slot for a new build into *idx*.

    A pane holds at most one pending reservation: a stale one is released
    first. On refusal the user sees the limiting cap with current/limit
    counts and nothing is reserved.
    """
    release_pane_reservation(controller, idx)
    registry = controller._registry
    try:
        reservation_id = registry.reserve_build(*source_key)
    except AdmissionError as exc:
        notify_mpr(controller, f"{exc}\n{registry.admission_message()}")
        return False
    controller._build_reservations[idx] = (reservation_id, source_key)
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


def build_view_payload(controller: Any, view_id: int) -> dict[str, Any] | None:
    """Install payload adapter for a view, built from its view and session.

    Holds the session's result by reference (never copied). Value state is
    copied so installing cannot alias the registry's sub-objects. Returns
    None for an unknown view or an unusable result.
    """
    registry = controller._registry
    view = find_view(controller, view_id)
    if view is None:
        return None
    session = registry.get_session(view.session_id)
    try:
        source_datasets = list(session.result.source_volume.source_datasets)
    except Exception:
        return None
    return {
        "mpr_result": session.result,
        "mpr_orientation": session.orientation,
        "mpr_slice_index": view.slice_index,
        "mpr_combine_enabled": view.combine.enabled,
        "mpr_combine_mode": view.combine.mode,
        "mpr_combine_slice_count": view.combine.slice_count,
        "mpr_combine": replace(view.combine),
        "mpr_display": replace(view.display),
        "mpr_source_dataset": source_datasets[0] if source_datasets else None,
        "current_study_uid": session.source_study_uid,
        "current_series_uid": session.source_series_uid,
        "current_datasets": source_datasets,
    }


def capture_pane_payload(controller: Any, idx: int) -> dict[str, Any] | None:
    """Payload for the view attached to pane *idx*, after flushing live state.

    None when the pane is not an MPR pane, holds no registry view, or its
    displayed result is not the session's own result (inconsistent state
    must never be transferred).
    """
    data = controller._app.subwindow_data.get(idx, {})
    if not data.get("is_mpr") or data.get("mpr_result") is None:
        return None
    view = refresh_view_from_pane(controller, idx)
    if view is None:
        return None
    if controller._registry.get_session(view.session_id).result is not data["mpr_result"]:
        return None
    return build_view_payload(controller, view.view_id)


# ---------------------------------------------------------------------------
# Public per-view metadata and pixel access (navigator-facing)
# ---------------------------------------------------------------------------


def find_view(controller: Any, view_id: int) -> MprView | None:
    """The live view for an exact ID, or None for stale/unknown IDs."""
    try:
        return controller._registry.get_view(view_id)
    except (UnknownViewError, TypeError):
        return None


def _result_photometric(result: Any) -> str | None:
    """Source-series PI carried on a result (tile polarity), else None."""
    value = getattr(result, "photometric_interpretation", None)
    return str(value) if value else None


def _metadata(controller: Any, view: MprView) -> MprViewMetadata:
    session = controller._registry.get_session(view.session_id)
    try:
        n_slices = max(0, int(getattr(session.result, "n_slices", 0) or 0))
    except (TypeError, ValueError):
        n_slices = 0
    return MprViewMetadata(
        view_id=view.view_id,
        session_id=view.session_id,
        creation_seq=view.creation_seq,
        pane_index=view.pane_index,
        orientation=session.orientation,
        source_study_uid=session.source_study_uid,
        source_series_uid=session.source_series_uid,
        n_slices=n_slices,
        slice_index=view.slice_index,
        photometric_interpretation=_result_photometric(session.result),
    )


def view_metadata(controller: Any, view_id: int) -> MprViewMetadata | None:
    """Metadata for an exact view ID (attached views are refreshed first)."""
    view = find_view(controller, view_id)
    if view is None:
        return None
    if view.pane_index is not None:
        refresh_view_from_pane(controller, view.pane_index)
    return _metadata(controller, view)


def pane_view_metadata(controller: Any, idx: int) -> MprViewMetadata | None:
    """Metadata for the view attached to pane *idx*, or None."""
    view = refresh_view_from_pane(controller, idx)
    return None if view is None else _metadata(controller, view)


def detached_view_ids(controller: Any) -> list[int]:
    """Detached view IDs in creation order."""
    return [v.view_id for v in controller._registry.ordered_views() if v.pane_index is None]


def view_display_state(controller: Any, view_id: int) -> MprDisplayState | None:
    """Copy of a view's display state (attached views are refreshed first)."""
    view = find_view(controller, view_id)
    if view is None:
        return None
    if view.pane_index is not None:
        refresh_view_from_pane(controller, view.pane_index)
    return replace(view.display)


def view_thumbnail_pixels(
    controller: Any, view_id: int, use_rescaled: bool | None = None
) -> np.ndarray | None:
    """Mid-stack slice for a view's navigator tile, honouring its combine state.

    ``use_rescaled`` defaults to the view's own display state. The returned
    array may share memory with the session's slices only when no rescale or
    cast is needed; callers must not mutate it.
    """
    view = find_view(controller, view_id)
    if view is None:
        return None
    if view.pane_index is not None:
        refresh_view_from_pane(controller, view.pane_index)
    result = controller._registry.get_session(view.session_id).result
    n_slices = int(getattr(result, "n_slices", 0) or 0)
    if n_slices <= 0:
        return None
    raw = apply_mpr_stack_combine(
        result.slices,
        n_slices // 2,
        enabled=view.combine.enabled,
        mode=view.combine.mode or "aip",
        n_planes=int(view.combine.slice_count or 4),
    )
    rescaled = view.display.use_rescaled if use_rescaled is None else use_rescaled
    return result.apply_rescale(raw) if rescaled else raw.astype(np.float32)


def discard_detached(controller: Any, view_id: int) -> bool:
    """Discard one detached view (and its session with the last view).

    Stale, unknown or attached IDs are harmless no-ops returning False; an
    attached view must be cleared through its pane.
    """
    view = find_view(controller, view_id)
    if view is None or view.pane_index is not None:
        return False
    controller._registry.discard_view(view_id)
    return True


__all__ = [
    "build_view_payload",
    "capture_pane_payload",
    "create_registry",
    "detached_view_ids",
    "discard_detached",
    "find_view",
    "notify_mpr",
    "pane_view_metadata",
    "refresh_view_from_pane",
    "release_pane_reservation",
    "reserve_pane_build",
    "resolve_session_caps",
    "view_display_state",
    "view_metadata",
    "view_thumbnail_pixels",
]
