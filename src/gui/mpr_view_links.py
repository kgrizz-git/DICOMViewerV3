"""Session-local linked scrolling and the canonical MPR slice setter.

``set_view_slice`` is the one path that changes an MPR view's slice position
for every *navigation* input: mouse wheel, keyboard, slider and cine (all of
which reach the focused pane through the slice navigator and
``core.slice_display_handlers.on_slice_changed``), and incoming anatomic
global sync (``SliceSyncCoordinator``). Redraw-only calls
(``MprController.display_mpr_slice``: overlay, W/L, combine, reset-view,
layout refreshes) never call it and so can never propagate a link.

Rules implemented here:

- The index is clamped to the shared result's stack. A view already at the
  clamped index with all its linked peers there is a no-op (early return).
- A view that belongs to a link group moves its whole group once. Members are
  views of one session, so they share one stack and take the same clamped
  index. Attached members are redrawn through ``display_mpr_slice`` (their own
  combine / W/L / LUT / inversion stay independent); detached members only
  record the canonical index, so reattaching one adopts it.
- The registry is the canonical store for every member. The setter first
  writes every stale member's registry index and live pane index, and only
  then redraws, so nothing observed during a redraw sees a half-updated
  group, and a later pane flush (``refresh_view_from_pane``) can never
  overwrite a canonical index with a stale one, even when a redraw failed. A
  member whose pane already shows the target but whose registry index drifted
  is repaired without a redraw.
- Re-entrancy is guarded by ``controller._slice_propagating``, independent of
  the global sync coordinator's ``_syncing``. The setter does not consult the
  global-sync toggle: explicit links always apply.
- The setter never calls the global sync coordinator. User/cine navigation
  starts outbound global sync once from the initiating pane
  (``on_slice_changed``); incoming global sync reaches the setter through the
  coordinator, which moves each explicit group once and does not cascade into
  other global groups.
- A detached member whose slice moved schedules one debounced tile refresh
  (its tooltip shows its dormant position); attached tiles show a fixed
  mid-stack slice and are untouched by scrolling.

Linking itself: ``link_after_duplicate`` joins a freshly confirmed duplicate
to the source's group (or creates the group from source + duplicate);
``unlink_view`` removes a view, dissolving a group down to one member.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QTimer

from gui.mpr_controller_sessions import emit_tiles_changed, find_view
from utils.privacy.console import print_redacted

#: Debounce for tile refreshes caused by scrolling a linked group (milliseconds).
TILE_REFRESH_DEBOUNCE_MS = 120


@dataclass(frozen=True)
class SliceUpdate:
    """Outcome of one canonical slice update."""

    index: int  # clamped index now canonical for the view (and its link group)
    changed: bool  # False when every member already was at ``index`` (registry and pane)
    peers: tuple[int, ...] = ()  # linked view IDs moved alongside the source


# ---------------------------------------------------------------------------
# Reading the canonical position
# ---------------------------------------------------------------------------


def _live_slice(controller: Any, view: Any) -> int:
    """Current index of *view*: the live pane value when attached, else the registry's."""
    if view.pane_index is not None:
        data = controller._app.subwindow_data.get(view.pane_index)
        if isinstance(data, dict):
            try:
                return int(data.get("mpr_slice_index", view.slice_index))
            except (TypeError, ValueError):
                pass
    return int(view.slice_index)


def group_members(controller: Any, view: Any) -> list[Any]:
    """Views that scroll together with *view* (itself first, then peers in creation order)."""
    registry = controller._registry
    if view.link_group_id is None:
        return [view]
    peers = [
        registry.get_view(vid)
        for vid in registry.link_members(view.link_group_id)
        if vid != view.view_id
    ]
    peers.sort(key=lambda v: v.creation_seq)
    return [view, *peers]


def canonical_slice(controller: Any, view: Any) -> int:
    """The index *view* should show now: its own, or its group's when linked.

    A linked view adopts the group's position (an attached member's live
    index wins, since the pane is what the user last saw); an unlinked view
    keeps its own.
    """
    if view.link_group_id is None:
        return _live_slice(controller, view)
    for member in group_members(controller, view):
        if member.pane_index is not None:
            return _live_slice(controller, member)
    return int(view.slice_index)


def link_group_of_pane(controller: Any, idx: int) -> int | None:
    """Explicit link-group ID of the view attached to pane *idx* (None if unlinked/empty)."""
    view = controller._registry.view_for_pane(idx)
    return None if view is None else view.link_group_id


# ---------------------------------------------------------------------------
# Canonical setter
# ---------------------------------------------------------------------------


def _clamped_target(controller: Any, view: Any, slice_index: int) -> tuple[int, int] | None:
    """``(clamped_target, n_slices)`` for *view*'s shared stack, or None if unusable."""
    result = controller._registry.get_session(view.session_id).result
    try:
        n_slices = int(getattr(result, "n_slices", 0) or 0)
        if n_slices < 1:
            return None
        return max(0, min(int(slice_index), n_slices - 1)), n_slices
    except (TypeError, ValueError):
        return None


def _write_members(controller: Any, stale: list[Any], target: int) -> tuple[list[int], list[int]]:
    """Phase 1: write every stale member's registry and live indices; no redraw yet.

    Returns ``(panes_to_redraw, detached_view_ids)``. Registry-only drift
    (the pane already shows *target*) needs no redraw.
    """
    redraw: list[int] = []
    detached: list[int] = []
    for member in stale:
        needs_redraw = _live_slice(controller, member) != target
        controller._registry.set_view_slice(member.view_id, target)
        if member.pane_index is None:
            detached.append(member.view_id)
            continue
        data = controller._app.subwindow_data.get(member.pane_index)
        if isinstance(data, dict):
            data["mpr_slice_index"] = target
        if needs_redraw:
            redraw.append(member.pane_index)
    return redraw, detached


def set_view_slice(controller: Any, view_id: int, slice_index: int) -> SliceUpdate | None:
    """Make *slice_index* (clamped) canonical for a view and its whole link group.

    Returns ``None`` for an unknown view, an unusable result/index, or a
    re-entrant call; otherwise a :class:`SliceUpdate`.
    """
    if controller._slice_propagating:
        return None
    view = find_view(controller, view_id)
    if view is None:
        return None
    clamped = _clamped_target(controller, view, slice_index)
    if clamped is None:
        return None
    target, n_slices = clamped
    members = group_members(controller, view)
    # A member needs work when its registry index OR its live pane index is off target.
    stale = [m for m in members if m.slice_index != target or _live_slice(controller, m) != target]
    if not stale:
        return SliceUpdate(target, False)

    controller._slice_propagating = True
    try:
        # Phase 1 writes every member BEFORE any redraw, so nothing that runs
        # synchronously during a redraw can observe a half-updated group, and a
        # failed redraw cannot leave drift behind. Phase 2 redraws attached
        # members whose displayed slice actually changed.
        redraw, detached = _write_members(controller, stale, target)
        for pane in redraw:
            _redraw_member(controller, pane, target, n_slices)
    finally:
        controller._slice_propagating = False
    if detached:
        schedule_tile_refresh(controller, detached)
    peers = tuple(m.view_id for m in members if m is not view)
    return SliceUpdate(target, True, peers)


def _redraw_member(controller: Any, pane: int, target: int, n_slices: int) -> None:
    """Redraw one attached member whose live index is already *target*."""
    try:
        controller.display_mpr_slice(pane, target)  # redraw only: never re-enters the setter
        controller._sync_slice_navigator_for_mpr(pane, n_slices, target)
        _sync_cine_position(controller, pane, target, n_slices)
    except Exception:
        # Constant text on purpose: no exception-derived content reaches the log sink.
        print_redacted("[MprLinks] a linked member could not be redrawn")


def _sync_cine_position(controller: Any, pane: int, target: int, n_slices: int) -> None:
    """Keep the cine frame readout current when the focused pane moved by a link."""
    app = controller._app
    if pane != getattr(app, "focused_subwindow_index", -1):
        return
    widget = getattr(app, "cine_controls_widget", None)
    updater = getattr(widget, "update_frame_position", None)
    if callable(updater):
        updater(target, n_slices)


def set_pane_slice(controller: Any, idx: int, slice_index: int) -> SliceUpdate | None:
    """:func:`set_view_slice` for the view attached to pane *idx* (None if the pane has none)."""
    view = controller._registry.view_for_pane(idx)
    if view is None:
        return None
    return set_view_slice(controller, view.view_id, slice_index)


# ---------------------------------------------------------------------------
# Debounced tile refresh for detached members
# ---------------------------------------------------------------------------


def schedule_tile_refresh(controller: Any, view_ids: Any) -> None:
    """Coalesce tile refreshes for detached views whose slice moved (one per window)."""
    controller._tile_refresh_dirty.update(view_ids)
    timer = controller._tile_refresh_timer
    if timer is None:
        timer = QTimer(controller)
        timer.setSingleShot(True)
        timer.setInterval(TILE_REFRESH_DEBOUNCE_MS)
        timer.timeout.connect(lambda: flush_tile_refresh(controller))
        controller._tile_refresh_timer = timer
    if not timer.isActive():
        timer.start()


def flush_tile_refresh(controller: Any) -> None:
    """Emit the pending tile refresh now (also used by tests and shutdown paths)."""
    timer = controller._tile_refresh_timer
    if timer is not None and timer.isActive():
        timer.stop()
    dirty = frozenset(controller._tile_refresh_dirty)
    controller._tile_refresh_dirty.clear()
    if dirty:
        emit_tiles_changed(controller, dirty)


# ---------------------------------------------------------------------------
# Link membership
# ---------------------------------------------------------------------------


def link_after_duplicate(controller: Any, source_view_id: int, new_view_id: int) -> int:
    """Join *new_view_id* to the source's link group, creating it from both if needed.

    Returns the group ID. Validation inside the registry runs before any
    membership changes, so a refusal leaves existing links untouched.
    """
    registry = controller._registry
    source = registry.get_view(source_view_id)
    if source.link_group_id is not None:
        registry.join_link_group(new_view_id, source.link_group_id)
        return source.link_group_id
    return registry.create_link_group(source.session_id, [source_view_id, new_view_id])


def unlink_view(controller: Any, view_id: int) -> bool:
    """Remove a view from its link group (a pair dissolves). False if it was not linked."""
    view = find_view(controller, view_id)
    if view is None or view.link_group_id is None:
        return False
    controller._registry.leave_link_group(view_id)
    emit_tiles_changed(controller)
    return True


__all__ = [
    "SliceUpdate",
    "canonical_slice",
    "flush_tile_refresh",
    "group_members",
    "link_after_duplicate",
    "link_group_of_pane",
    "schedule_tile_refresh",
    "set_pane_slice",
    "set_view_slice",
    "unlink_view",
]
