"""MPR session/view registry (pure core, no Qt).

First slice of the P1 multiple-MPR-sessions plan
(``dev-docs/plans/completed/MPR_MULTI_SESSION_AND_LINKED_VIEWS_PLAN.md``):
stable session/view ownership independent of pane assignment, shared-result
duplicates, session-local link groups, configurable admission caps with
idempotent pending reservations, and discard-last-view session lifetime.

Ownership rules implemented here:

- A session owns one immutable shared result object (held by reference, never
  copied). ``result`` is typed ``Any`` so tests may use synthetic sentinels;
  production passes ``MprResult`` without this module importing it.
- A view owns a stable view ID, its session ID, an optional pane assignment
  (``None`` means detached), slice/combine/display state and an optional
  session-local link-group ID.
- Pane-to-view mapping is one-to-one and maintained alongside the views.
  Attaching to an occupied pane detaches the occupant (no new slot);
  moves/detach/reattach never consume admission.
- Growth admission: ``session_cap`` bounds constructed sessions (attached,
  detached and pending builds); ``view_cap`` bounds total views (attached,
  detached and reserved). Reservations are live tokens removed on
  confirm/cancel; monotonic IDs make replay safe with no retained history.
  Lowering caps never evicts; it only blocks new growth.
- Lifetime: discarding a view leaves its session alive while sibling views
  remain; the session is released with its last view. Source/study closure
  removes dependent sessions, views and related pending reservations.
  ``clear_all`` releases everything. Nothing here persists across restarts.

Getter mutability contract: ``get_session``, ``get_view`` and
``view_for_pane`` return the live owned objects (no copies; never duplicate
volume arrays through them). Mutate only via registry methods, which copy
value state on entry; never replace a view's ``combine``/``display``
sub-objects directly (use the setters).

This module performs no GUI work and imports nothing from ``gui/``. Snapshot
helpers capture slice/combine/display value state only (no volume arrays).
Mutable manager adapters (``subwindow_data``, view-state managers) stay in
the controller layer; a later chunk wires this registry to it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from core.mpr_session_types import (
    DEFAULT_SESSION_CAP,
    DEFAULT_VIEW_CAP,
    AdmissionError,
    LinkGroupError,
    MprCombineState,
    MprDisplayState,
    MprSession,
    MprView,
    MprViewSnapshot,
    ReservationError,
    UnknownSessionError,
    UnknownViewError,
)


@dataclass
class _Reservation:
    reservation_id: int
    kind: str  # "build" (1 session + 1 view) or "view" (duplicate, 1 view)
    source_study_uid: str
    source_series_uid: str
    session_id: int | None  # set for "view" reservations


class MprSessionRegistry:
    """Owns MPR sessions, views, pane mapping, link groups and reservations."""

    def __init__(self, session_cap: int = DEFAULT_SESSION_CAP, view_cap: int = DEFAULT_VIEW_CAP) -> None:
        self._validate_caps(session_cap, view_cap)
        self._session_cap = session_cap
        self._view_cap = view_cap
        self._sessions: dict[int, MprSession] = {}
        self._views: dict[int, MprView] = {}
        self._pane_to_view: dict[int, int] = {}
        self._link_groups: dict[int, set[int]] = {}
        self._reservations: dict[int, _Reservation] = {}
        self._next_session_id = 1
        self._next_view_id = 1
        self._next_group_id = 1
        self._next_reservation_id = 1
        self._next_seq = 1

    # ------------------------------------------------------------------
    # Caps and counts
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_caps(session_cap: int, view_cap: int) -> None:
        if session_cap < 1 or view_cap < session_cap:
            raise ValueError("caps must satisfy view_cap >= session_cap >= 1")

    @property
    def session_cap(self) -> int:
        return self._session_cap

    @property
    def view_cap(self) -> int:
        return self._view_cap

    def set_caps(self, session_cap: int, view_cap: int) -> None:
        """Lower or raise caps. Never evicts; growth blocks until under limit."""
        self._validate_caps(session_cap, view_cap)
        self._session_cap = session_cap
        self._view_cap = view_cap

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def view_count(self) -> int:
        return len(self._views)

    @property
    def pending_session_count(self) -> int:
        # Map holds live pending tokens only; every "build" entry is pending.
        return sum(1 for r in self._reservations.values() if r.kind == "build")

    @property
    def pending_view_count(self) -> int:
        return len(self._reservations)

    def counts(self) -> dict[str, int]:
        return {
            "sessions": self.session_count,
            "session_cap": self._session_cap,
            "pending_sessions": self.pending_session_count,
            "views": self.view_count,
            "view_cap": self._view_cap,
            "pending_views": self.pending_view_count,
        }

    def admission_message(self) -> str:
        c = self.counts()
        return (
            f"MPR sessions {c['sessions']}/{c['session_cap']} "
            f"({c['pending_sessions']} pending), views {c['views']}/{c['view_cap']} "
            f"({c['pending_views']} pending)"
        )

    # ------------------------------------------------------------------
    # Reservations (admission before construction)
    # ------------------------------------------------------------------

    def reserve_build(self, source_study_uid: str = "", source_series_uid: str = "") -> int:
        """Reserve one session slot plus one view slot for a new build."""
        if self.session_count + self.pending_session_count >= self._session_cap:
            raise AdmissionError("session", self.session_count + self.pending_session_count, self._session_cap)
        if self.view_count + self.pending_view_count >= self._view_cap:
            raise AdmissionError("view", self.view_count + self.pending_view_count, self._view_cap)
        return self._add_reservation("build", source_study_uid, source_series_uid, None)

    def reserve_view(self, session_id: int) -> int:
        """Reserve one view slot for duplicating an existing session."""
        if session_id not in self._sessions:
            raise UnknownSessionError(session_id)
        if self.view_count + self.pending_view_count >= self._view_cap:
            raise AdmissionError("view", self.view_count + self.pending_view_count, self._view_cap)
        session = self._sessions[session_id]
        return self._add_reservation("view", session.source_study_uid, session.source_series_uid, session_id)

    def _add_reservation(self, kind: str, study_uid: str, series_uid: str, session_id: int | None) -> int:
        rid = self._next_reservation_id
        self._next_reservation_id += 1
        self._reservations[rid] = _Reservation(rid, kind, study_uid, series_uid, session_id)
        return rid

    def cancel_reservation(self, reservation_id: int) -> bool:
        """Release a pending reservation, removing its token. Unknown/consumed IDs return False."""
        return self._reservations.pop(reservation_id, None) is not None

    def _peek_pending(self, reservation_id: int, kind: str) -> _Reservation:
        reservation = self._reservations.get(reservation_id)
        if reservation is None or reservation.kind != kind:
            raise ReservationError(f"reservation {reservation_id} is not a pending {kind} reservation")
        return reservation

    def _consume_pending(self, reservation_id: int, kind: str) -> _Reservation:
        """Validate then remove a pending token. Call only after all other validation passed."""
        reservation = self._peek_pending(reservation_id, kind)
        del self._reservations[reservation_id]
        return reservation

    # ------------------------------------------------------------------
    # Creation (direct, or confirm a reservation)
    # ------------------------------------------------------------------

    def confirm_build(
        self,
        reservation_id: int,
        *,
        result: Any,
        orientation: str = "",
        slice_index: int = 0,
        pane_index: int | None = None,
        combine: MprCombineState | None = None,
        display: MprDisplayState | None = None,
    ) -> tuple[int, int]:
        """Convert a pending build reservation into a session plus its first view.

        Source identity comes from the reservation (authoritative for
        source-closure matching). All validation runs before any mutation:
        on failure the reservation stays pending and nothing is created.
        """
        reservation = self._peek_pending(reservation_id, "build")
        coerced_slice = int(slice_index)
        if pane_index is not None:
            self._check_pane(pane_index)
        self._consume_pending(reservation_id, "build")
        session_id = self._add_session(result, reservation.source_study_uid, reservation.source_series_uid, orientation)
        view_id = self._add_view(session_id, coerced_slice, pane_index, combine, display)
        return session_id, view_id

    def confirm_view(
        self,
        reservation_id: int,
        *,
        slice_index: int = 0,
        pane_index: int | None = None,
        combine: MprCombineState | None = None,
        display: MprDisplayState | None = None,
    ) -> int:
        """Convert a pending view reservation into a duplicate view sharing the session result.

        All validation runs before any mutation: on failure the reservation
        stays pending and nothing is created.
        """
        reservation = self._peek_pending(reservation_id, "view")
        assert reservation.session_id is not None
        if reservation.session_id not in self._sessions:
            raise UnknownSessionError(reservation.session_id)
        coerced_slice = int(slice_index)
        if pane_index is not None:
            self._check_pane(pane_index)
        self._consume_pending(reservation_id, "view")
        return self._add_view(reservation.session_id, coerced_slice, pane_index, combine, display)

    def create_session(
        self,
        result: Any,
        source_study_uid: str = "",
        source_series_uid: str = "",
        orientation: str = "",
        slice_index: int = 0,
        pane_index: int | None = None,
        combine: MprCombineState | None = None,
        display: MprDisplayState | None = None,
    ) -> tuple[int, int]:
        """Reserve-and-confirm in one step (cache hits / direct activation).

        Cancels its own reservation if confirmation fails (no slot leak).
        """
        rid = self.reserve_build(source_study_uid, source_series_uid)
        try:
            return self.confirm_build(
                rid, result=result, orientation=orientation,
                slice_index=slice_index, pane_index=pane_index, combine=combine, display=display,
            )
        except Exception:
            self.cancel_reservation(rid)
            raise

    def create_view(
        self,
        session_id: int,
        slice_index: int = 0,
        pane_index: int | None = None,
        combine: MprCombineState | None = None,
        display: MprDisplayState | None = None,
    ) -> int:
        """Reserve-and-confirm a duplicate view in one step.

        Cancels its own reservation if confirmation fails (no slot leak).
        """
        rid = self.reserve_view(session_id)
        try:
            return self.confirm_view(rid, slice_index=slice_index, pane_index=pane_index, combine=combine, display=display)
        except Exception:
            self.cancel_reservation(rid)
            raise

    def _add_session(self, result: Any, study_uid: str, series_uid: str, orientation: str) -> int:
        session_id = self._next_session_id
        self._next_session_id += 1
        seq = self._next_seq
        self._next_seq += 1
        self._sessions[session_id] = MprSession(session_id, seq, study_uid, series_uid, orientation, result)
        return session_id

    def _add_view(
        self,
        session_id: int,
        slice_index: int,
        pane_index: int | None,
        combine: MprCombineState | None,
        display: MprDisplayState | None,
    ) -> int:
        view_id = self._next_view_id
        self._next_view_id += 1
        seq = self._next_seq
        self._next_seq += 1
        # Copy value state on entry so siblings never alias a caller dataclass.
        # Shallow ``replace`` keeps the opaque LUT identity by design.
        view = MprView(
            view_id, session_id, seq, None, int(slice_index),
            combine=replace(combine) if combine is not None else MprCombineState(),
            display=replace(display) if display is not None else MprDisplayState(),
        )
        self._views[view_id] = view
        if pane_index is not None:
            self._assign_pane(view, pane_index)
        return view_id

    # ------------------------------------------------------------------
    # Pane mapping (moves consume no admission slot)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_pane(pane_index: int) -> None:
        if not isinstance(pane_index, int) or isinstance(pane_index, bool) or pane_index < 0:
            raise ValueError(f"invalid pane index: {pane_index!r}")

    def _assign_pane(self, view: MprView, pane_index: int) -> None:
        self._check_pane(pane_index)
        occupant_id = self._pane_to_view.get(pane_index)
        if occupant_id == view.view_id:
            return
        if occupant_id is not None:
            self._views[occupant_id].pane_index = None
        if view.pane_index is not None:
            self._pane_to_view.pop(view.pane_index, None)
        view.pane_index = pane_index
        self._pane_to_view[pane_index] = view.view_id

    def attach_view(self, view_id: int, pane_index: int) -> None:
        """Attach a view to a pane, detaching any occupant. Unknown IDs raise."""
        view = self._views.get(view_id)
        if view is None:
            raise UnknownViewError(view_id)
        self._assign_pane(view, pane_index)

    def detach_view(self, view_id: int) -> None:
        """Detach a view (keeps session alive). Already-detached is a no-op."""
        view = self._views.get(view_id)
        if view is None:
            raise UnknownViewError(view_id)
        if view.pane_index is not None:
            self._pane_to_view.pop(view.pane_index, None)
            view.pane_index = None

    # ------------------------------------------------------------------
    # Discard / closure lifetime
    # ------------------------------------------------------------------

    def discard_view(self, view_id: int) -> int | None:
        """Discard one view; returns the released session ID only for the last view."""
        view = self._views.pop(view_id, None)
        if view is None:
            raise UnknownViewError(view_id)
        if view.pane_index is not None:
            self._pane_to_view.pop(view.pane_index, None)
        self._remove_from_link_group(view)
        if not any(v.session_id == view.session_id for v in self._views.values()):
            self._sessions.pop(view.session_id, None)
            self._cancel_view_reservations(view.session_id)
            return view.session_id
        return None

    def discard_session(self, session_id: int) -> list[int]:
        """Discard a session and all its views. Unknown IDs raise."""
        if session_id not in self._sessions:
            raise UnknownSessionError(session_id)
        removed = [vid for vid, v in self._views.items() if v.session_id == session_id]
        for vid in removed:
            self.discard_view(vid)
        return removed

    def _cancel_view_reservations(self, session_id: int) -> int:
        """Remove pending duplicate-view tokens tied to a session. Returns the count removed."""
        tied = [rid for rid, r in self._reservations.items() if r.session_id == session_id]
        for rid in tied:
            del self._reservations[rid]
        return len(tied)

    def _close_source(self, study_uid: str | None, series_uid: str | None) -> dict[str, int]:
        """Remove dependent sessions/views and related pending reservations.

        Returns ``{"sessions", "views", "reservations"}``; ``reservations``
        counts every released token (duplicate-view tokens tied to discarded
        sessions plus matching build tokens), each exactly once.
        """
        matched = [
            sid for sid, s in self._sessions.items()
            if (study_uid is not None and s.source_study_uid == study_uid)
            or (series_uid is not None and s.source_series_uid == series_uid)
        ]
        views = 0
        released = 0
        for sid in matched:
            # Count tied duplicate-view tokens before discard_session removes them.
            released += sum(1 for r in self._reservations.values() if r.session_id == sid)
            views += len(self.discard_session(sid))
        for rid, reservation in list(self._reservations.items()):
            if (study_uid is not None and reservation.source_study_uid == study_uid) or (
                series_uid is not None and reservation.source_series_uid == series_uid
            ):
                del self._reservations[rid]
                released += 1
        return {"sessions": len(matched), "views": views, "reservations": released}

    def close_source_series(self, series_uid: str) -> dict[str, int]:
        """Remove every session/view/pending build for a source series."""
        return self._close_source(None, series_uid)

    def close_study(self, study_uid: str) -> dict[str, int]:
        """Remove every session/view/pending build for a study."""
        return self._close_source(study_uid, None)

    def clear_all(self) -> None:
        """Release every session, view, link group and pending reservation token."""
        self._sessions.clear()
        self._views.clear()
        self._pane_to_view.clear()
        self._link_groups.clear()
        self._reservations.clear()

    # ------------------------------------------------------------------
    # Per-view state
    # ------------------------------------------------------------------

    def set_view_slice(self, view_id: int, slice_index: int) -> None:
        view = self._views.get(view_id)
        if view is None:
            raise UnknownViewError(view_id)
        view.slice_index = int(slice_index)

    def set_view_combine(self, view_id: int, combine: MprCombineState) -> None:
        """Replace a view's combine state with a copy (LUT identity retained)."""
        view = self._views.get(view_id)
        if view is None:
            raise UnknownViewError(view_id)
        view.combine = replace(combine)

    def set_view_display(self, view_id: int, display: MprDisplayState) -> None:
        """Replace a view's display state with a copy (LUT identity retained)."""
        view = self._views.get(view_id)
        if view is None:
            raise UnknownViewError(view_id)
        view.display = replace(display)

    def capture_view_snapshot(self, view_id: int) -> MprViewSnapshot:
        """Copy a view's slice/combine/display state (shares no mutable state)."""
        view = self._views.get(view_id)
        if view is None:
            raise UnknownViewError(view_id)
        return MprViewSnapshot(view.view_id, view.session_id, view.slice_index, replace(view.combine), replace(view.display))

    def apply_view_snapshot(self, snapshot: MprViewSnapshot) -> None:
        """Restore slice/combine/display onto its view (identity/pane untouched).

        Copies snapshot value state, so later snapshot mutation is harmless.
        """
        view = self._views.get(snapshot.view_id)
        if view is None:
            raise UnknownViewError(snapshot.view_id)
        if view.session_id != snapshot.session_id:
            raise ValueError("snapshot session does not match view session")
        view.slice_index = int(snapshot.slice_index)
        view.combine = replace(snapshot.combine)
        view.display = replace(snapshot.display)

    # ------------------------------------------------------------------
    # Link groups (session-local slice scrolling)
    # ------------------------------------------------------------------

    def create_link_group(self, session_id: int, view_ids: list[int]) -> int:
        """Create a link group over views of one session. Detached members allowed.

        All checks run before any membership is touched, so rejection leaves
        prior groups intact. Members move out of any prior group.
        """
        if session_id not in self._sessions:
            raise UnknownSessionError(session_id)
        if len(set(view_ids)) != len(view_ids):
            raise LinkGroupError("duplicate view IDs in link group")
        if len(view_ids) < 2:
            raise LinkGroupError("a link group needs at least two distinct views")
        for vid in view_ids:
            view = self._views.get(vid)
            if view is None:
                raise UnknownViewError(vid)
            if view.session_id != session_id:
                raise LinkGroupError(f"view {vid} belongs to a different session")
        group_id = self._next_group_id
        self._next_group_id += 1
        self._link_groups[group_id] = set(view_ids)
        for vid in view_ids:
            self._leave_group_silent(self._views[vid])
            self._views[vid].link_group_id = group_id
        return group_id

    def join_link_group(self, view_id: int, group_id: int) -> None:
        """Join a view to a group of its own session; moves it out of any prior group."""
        view = self._views.get(view_id)
        if view is None:
            raise UnknownViewError(view_id)
        members = self._link_groups.get(group_id)
        if members is None:
            raise LinkGroupError(f"unknown link group {group_id}")
        anchor = self._views[next(iter(members))]
        if anchor.session_id != view.session_id:
            raise LinkGroupError("cannot link views of different sessions")
        if view.link_group_id == group_id:
            return
        self._leave_group_silent(view)
        view.link_group_id = group_id
        members.add(view_id)

    def leave_link_group(self, view_id: int) -> bool:
        """Remove a view from its link group. Returns False when not linked."""
        view = self._views.get(view_id)
        if view is None:
            raise UnknownViewError(view_id)
        if view.link_group_id is None:
            return False
        self._remove_from_link_group(view)
        return True

    def _leave_group_silent(self, view: MprView) -> None:
        if view.link_group_id is not None:
            self._remove_from_link_group(view)

    def _remove_from_link_group(self, view: MprView) -> None:
        group_id = view.link_group_id
        view.link_group_id = None
        if group_id is None:
            return
        members = self._link_groups.get(group_id)
        if members is None:
            return
        members.discard(view.view_id)
        if len(members) < 2:
            for vid in list(members):
                self._views[vid].link_group_id = None
            self._link_groups.pop(group_id, None)

    def link_members(self, group_id: int) -> list[int]:
        """Return sorted member view IDs of a link group."""
        members = self._link_groups.get(group_id)
        if members is None:
            raise LinkGroupError(f"unknown link group {group_id}")
        return sorted(members)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_session(self, session_id: int) -> MprSession:
        """Return the live owned session (see mutability contract in the module docstring)."""
        session = self._sessions.get(session_id)
        if session is None:
            raise UnknownSessionError(session_id)
        return session

    def get_view(self, view_id: int) -> MprView:
        """Return the live owned view (see mutability contract in the module docstring)."""
        view = self._views.get(view_id)
        if view is None:
            raise UnknownViewError(view_id)
        return view

    def view_for_pane(self, pane_index: int) -> MprView | None:
        """Return the live owned view attached to a pane, or None (see mutability contract)."""
        view_id = self._pane_to_view.get(pane_index)
        return self._views.get(view_id) if view_id is not None else None

    def views_for_session(self, session_id: int) -> list[MprView]:
        if session_id not in self._sessions:
            raise UnknownSessionError(session_id)
        return sorted(
            (v for v in self._views.values() if v.session_id == session_id),
            key=lambda v: v.creation_seq,
        )

    def sessions_for_series(self, series_uid: str) -> list[MprSession]:
        return sorted(
            (s for s in self._sessions.values() if s.source_series_uid == series_uid),
            key=lambda s: s.creation_seq,
        )

    def ordered_views(self) -> list[MprView]:
        """All views in creation order (navigator tile ordering contract)."""
        return sorted(self._views.values(), key=lambda v: v.creation_seq)
