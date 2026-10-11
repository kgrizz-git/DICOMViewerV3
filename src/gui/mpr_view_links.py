"""Canonical MPR slice navigation for one attached view.

``set_view_slice`` is the one path that changes an MPR view's slice position
for every *navigation* input: mouse wheel, keyboard, slider and cine (all of
which reach the focused pane through the slice navigator and
``core.slice_display_handlers.on_slice_changed``), and incoming anatomic
global sync (``SliceSyncCoordinator``). Redraw-only calls
(``MprController.display_mpr_slice``: overlay, W/L, reset-view, layout
refreshes) never call it.

Rules implemented here:

- The index is clamped to the shared result's stack. A view already at the
  clamped index is a no-op (early return).
- The registry is the canonical store. The setter first writes the view's
  registry index and live pane index, and only then redraws, so nothing
  observed during a redraw sees a half-updated view and a later pane flush
  (``refresh_view_from_pane``) can never overwrite a canonical index with a
  stale one, even when a redraw failed. Registry-only drift (the pane
  already shows the target) is repaired without a redraw.
- Re-entrancy is guarded by ``controller._slice_propagating``, independent of
  the global sync coordinator's ``_syncing``.
- The setter never calls the global sync coordinator. User/cine navigation
  starts outbound global sync once from the initiating pane
  (``on_slice_changed``); incoming global sync reaches the setter through the
  coordinator.

Session-local link groups (scrolling duplicates together) arrive with the
duplicates-and-links slice; this module currently moves exactly one view.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.mpr_session_types import UnknownViewError
from utils.privacy.console import print_redacted


@dataclass(frozen=True)
class SliceUpdate:
    """Outcome of one canonical slice update."""

    index: int  # clamped index now canonical for the view
    changed: bool  # False when the view already was at ``index`` (registry and pane)
    peers: tuple[int, ...] = ()  # reserved for linked views; always empty here


def _find_view(controller: Any, view_id: int) -> Any:
    """The live view for an exact ID, or None for stale/unknown IDs."""
    try:
        return controller._registry.get_view(view_id)
    except (UnknownViewError, TypeError):
        return None


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


def _write_view(controller: Any, view: Any, target: int) -> bool:
    """Phase 1: write the view's registry and live indices; no redraw yet.

    Returns True when the displayed slice actually changes (redraw needed).
    Registry-only drift (the pane already shows *target*) needs no redraw.
    """
    needs_redraw = _live_slice(controller, view) != target
    controller._registry.set_view_slice(view.view_id, target)
    if view.pane_index is not None:
        data = controller._app.subwindow_data.get(view.pane_index)
        if isinstance(data, dict):
            data["mpr_slice_index"] = target
    return needs_redraw


def set_view_slice(controller: Any, view_id: int, slice_index: int) -> SliceUpdate | None:
    """Make *slice_index* (clamped) canonical for a view.

    Returns ``None`` for an unknown view, an unusable result/index, or a
    re-entrant call; otherwise a :class:`SliceUpdate`.
    """
    if controller._slice_propagating:
        return None
    view = _find_view(controller, view_id)
    if view is None:
        return None
    clamped = _clamped_target(controller, view, slice_index)
    if clamped is None:
        return None
    target, n_slices = clamped
    if view.slice_index == target and _live_slice(controller, view) == target:
        return SliceUpdate(target, False)

    controller._slice_propagating = True
    try:
        # Phase 1 writes the view BEFORE the redraw, so nothing that runs
        # synchronously during a redraw observes a half-updated view, and a
        # failed redraw cannot leave drift behind. Phase 2 redraws only an
        # attached view whose displayed slice actually changed; a detached
        # view has no pane, so its registry index updates silently.
        needs_redraw = _write_view(controller, view, target)
        if needs_redraw and view.pane_index is not None:
            _redraw_view(controller, view.pane_index, target, n_slices)
    finally:
        controller._slice_propagating = False
    return SliceUpdate(target, True)


def _redraw_view(controller: Any, pane: int, target: int, n_slices: int) -> None:
    """Redraw one attached view whose live index is already *target*."""
    try:
        controller.display_mpr_slice(pane, target)  # redraw only: never re-enters the setter
        controller._sync_slice_navigator_for_mpr(pane, n_slices, target)
        _sync_cine_position(controller, pane, target, n_slices)
    except Exception:
        # Constant text on purpose: no exception-derived content reaches the log sink.
        print_redacted("[MprLinks] a linked member could not be redrawn")
    _sync_pane_slider(controller, pane)


def _sync_pane_slider(controller: Any, pane: int) -> None:
    """Make the pane's in-window slice slider show its current slice, focused or not.

    Uses the app's own per-pane seam (the one the display path uses), which
    sets the slider range and value with signals blocked, so it can never call
    ``slider_navigate_callback`` and start another navigation. Runs after every
    redraw attempt, so a pane whose redraw failed still shows the canonical
    slice on its slider rather than lagging behind it.
    """
    sync = getattr(controller._app, "_sync_navigation_slider_for_subwindow", None)
    if not callable(sync):
        return
    try:
        sync(pane)
    except Exception:
        print_redacted("[MprLinks] a linked member's slider could not be updated")


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


__all__ = [
    "SliceUpdate",
    "set_pane_slice",
    "set_view_slice",
]
