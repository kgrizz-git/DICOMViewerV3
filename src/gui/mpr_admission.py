"""Runtime admission policy for MPR: live caps, usage summary, status text.

Seams used by the rest of the MPR controller:

- ``refresh_session_caps`` re-reads the persisted caps and applies them to the
  live registry *before an admission decision* (and from the settings-applied
  callback via ``MprController.apply_session_caps``), so a change in Settings
  governs the next new build or duplicate without a restart. It only changes
  the limits: existing sessions and views are never evicted, and builds that
  were already admitted (pending reservations) are honored. A refresh applies
  only when the persisted pair is valid and differs from the pair last seen,
  so a value set directly on the registry is not clobbered by an unchanged
  (or unreadable) config.
- ``admission_summary`` is the concise "counts / limits / approximate memory"
  line used in refusals and status messages. The memory figure is the
  approximate estimate from ``core.mpr_memory_estimate``: a visibility aid,
  not a limit, and no extra confirmation is ever required.

``controller`` is duck-typed like the other MPR helpers; status text never
raises.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from core.mpr_memory_estimate import (
    MemoryEstimate,
    estimate_memory,
    format_mib,
)
from core.mpr_session_registry import MprSessionRegistry
from core.mpr_session_types import DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP


class PaneReservation(NamedTuple):
    """A pane's pending build admission (indexable like the original 2-tuple)."""

    reservation_id: int
    source_key: tuple[str, str]
    pending_bytes: int = 0  # source-volume estimate while the build runs


def strict_session_caps(app: Any) -> tuple[int, int] | None:
    """The configured ``(session_cap, view_cap)`` if it is a valid pair, else None."""
    try:
        session_cap, view_cap = app.config_manager.get_mpr_caps()
    except Exception:
        return None
    if type(session_cap) is int and type(view_cap) is int and 1 <= session_cap <= view_cap:
        return session_cap, view_cap
    return None


def resolve_session_caps(app: Any) -> tuple[int, int]:
    """Validated caps from config, else the defaults (stubbed/broken config must not stop startup)."""
    return strict_session_caps(app) or (DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP)


def create_registry(app: Any) -> MprSessionRegistry:
    """Registry sized from the configured admission caps."""
    session_cap, view_cap = resolve_session_caps(app)
    return MprSessionRegistry(session_cap, view_cap)


def refresh_session_caps(controller: Any) -> bool:
    """Apply changed persisted caps to the live registry; True when the limits changed.

    Never evicts: the registry only starts refusing growth until usage falls
    below the new limits.
    """
    caps = strict_session_caps(controller._app)
    if caps is None or caps == controller._seen_caps:
        return False
    controller._seen_caps = caps
    controller._registry.set_caps(*caps)
    return True


def memory_estimate(controller: Any) -> MemoryEstimate:
    """Approximate marginal MPR memory right now (see ``core.mpr_memory_estimate``)."""
    registry = controller._registry
    views = registry.ordered_views()
    results: list[Any] = []
    seen_sessions: set[int] = set()
    for view in views:
        if view.session_id not in seen_sessions:
            seen_sessions.add(view.session_id)
            results.append(registry.get_session(view.session_id).result)
    pending = sum(getattr(held, "pending_bytes", 0) for held in controller._build_reservations.values())
    return estimate_memory(results, len(views), pending)


def admission_summary(controller: Any) -> str:
    """One concise line: sessions/views against their limits, plus approximate memory."""
    counts = controller._registry.counts()
    building = f" (+{counts['pending_sessions']} building)" if counts["pending_sessions"] else ""
    memory = format_mib(memory_estimate(controller).total_bytes)
    return (
        f"MPR: {counts['sessions']}/{counts['session_cap']} sessions{building}, "
        f"{counts['views']}/{counts['view_cap']} views, about {memory} (estimate)"
    )


def set_status(controller: Any, text: str) -> None:
    """Best-effort main-window status message."""
    try:
        controller._app.main_window.update_status(text)
    except Exception:
        pass


__all__ = [
    "PaneReservation",
    "admission_summary",
    "create_registry",
    "memory_estimate",
    "refresh_session_caps",
    "resolve_session_caps",
    "set_status",
    "strict_session_caps",
]
