"""MPR source-closure release for ``MprController``.

Retires builds tied to a closed study or series (releasing their pending
admission reservations), discards the registry sessions and every view of the
closed source (attached and detached, with their navigator tiles), and resets
per-pane MPR tool/LUT/banner/navigator state without touching study data
(callers clear it). Close-all releases every worker, reservation, session,
view, override, and spec. Matching uses authoritative build sources for
workers, registry session sources for sessions, and displayed study/series
for chrome — never one for another.
"""

from __future__ import annotations

from typing import Any

from core.lut_series_state import clear_mpr_lut_override
from gui.mpr_controller_sessions import emit_tiles_changed
from gui.mpr_worker_fencing import bump_source_generation, retire_pane_worker

# ---------------------------------------------------------------------------
# Source closure release
# ---------------------------------------------------------------------------


def _source_matches(
    study_uid: str, series_uid: str | None, candidate: tuple[str, str] | None
) -> bool:
    if candidate is None:
        return False
    if candidate[0] != study_uid:
        return False
    return series_uid is None or candidate[1] == series_uid


def release_closed_source_sessions(
    controller: Any, study_uid: str, series_uid: str | None = None
) -> dict[str, int]:
    """Release MPR state tied to a closed study (or single series).

    Retires dependent builds, clears per-pane LUT overrides and MPR banners,
    resets the MPR tool override, discards every session (and so every attached
    and detached view) built from the source, announces one navigator tile
    reconcile, and bumps source generations so late worker callbacks cannot
    resurrect closed data. Study data itself is untouched (callers clear it).
    Returns release counts.
    """
    app = controller._app
    released = {"panes": 0, "workers": 0, "detached": 0}
    panes = set(app.subwindow_data) | set(controller._workers.keys())
    for idx in sorted(panes):
        data = app.subwindow_data.get(idx, {})
        displayed = (
            str(data.get("current_study_uid", "") or ""),
            str(data.get("current_series_uid", "") or ""),
        )
        display_match = _source_matches(study_uid, series_uid, displayed)
        if _build_matches_close(controller, idx, study_uid, series_uid, display_match):
            if retire_pane_worker(controller, idx):
                released["workers"] += 1
        if not display_match:
            continue
        _reset_pane_mpr_chrome(controller, app, idx)
        released["panes"] += 1
    released["detached"] += _discard_closed_sessions(controller, study_uid, series_uid)
    _bump_closed_source_generations(controller, study_uid, series_uid)
    emit_tiles_changed(controller)
    return released


def _discard_closed_sessions(
    controller: Any, study_uid: str, series_uid: str | None
) -> int:
    """Discard every session built from the closed source; return detached views released.

    Attached views leave through their panes (chrome reset and the caller's
    pane clear). Their navigator tiles go with the single tiles-changed
    announcement the caller emits. Foreign sessions are untouched.
    """
    registry = controller._registry
    session_ids: list[int] = []
    for view in registry.ordered_views():
        if view.session_id in session_ids:
            continue
        session = registry.get_session(view.session_id)
        if _source_matches(study_uid, series_uid, (session.source_study_uid, session.source_series_uid)):
            session_ids.append(view.session_id)
    detached = 0
    for session_id in session_ids:
        for view in registry.views_for_session(session_id):
            if view.pane_index is None:
                detached += 1
        registry.discard_session(session_id)
    return detached


def _build_matches_close(
    controller: Any, idx: int, study_uid: str, series_uid: str | None, display_match: bool
) -> bool:
    """True when the pane's active build belongs to the closed source.

    A known build source decides on its own: foreign builds survive even
    when the pane currently displays the closing source. An untracked build
    (no recorded source) defers to the display match so pending builds are
    never leaked by a close.
    """
    build_key = controller._build_sources.get(idx)
    if build_key is None:
        return display_match
    return _source_matches(study_uid, series_uid, build_key)


def release_all_mpr(controller: Any) -> dict[str, int]:
    """Release every MPR build, session, view, reservation, and override.

    Retires all registered workers (including pending builds on empty panes
    whose source no pane displays), clears the registry, bumps every source
    generation, and resets per-pane MPR chrome on every known pane.
    Study data itself is untouched (callers clear it).
    """
    app = controller._app
    released = {"panes": 0, "workers": 0, "detached": 0}
    panes = set(app.subwindow_data) | set(controller._workers.keys())
    for idx in sorted(panes):
        if retire_pane_worker(controller, idx):
            released["workers"] += 1
        _reset_pane_mpr_chrome(controller, app, idx)
        released["panes"] += 1
    registry = controller._registry
    detached = [v.view_id for v in registry.ordered_views() if v.pane_index is None]
    registry.clear_all()
    controller._build_reservations.clear()
    released["detached"] += len(detached)
    for study_uid, series_uid in list(controller._source_generations):
        bump_source_generation(controller, study_uid, series_uid)
    emit_tiles_changed(controller)
    return released


def _reset_pane_mpr_chrome(controller: Any, app: Any, idx: int) -> None:
    """Clear a pane's LUT override, MPR banner, and tool-mode override."""
    managers = app.subwindow_managers.get(idx, {})
    view_state_manager = managers.get("view_state_manager")
    if view_state_manager is not None:
        clear_mpr_lut_override(view_state_manager)
    try:
        viewer = controller._get_image_viewer(idx)
    except Exception:
        viewer = None
    if viewer is not None and getattr(viewer, "_mpr_mode_override", False):
        viewer._mpr_mode_override = False
    overlay_manager = managers.get("overlay_manager")
    banner = getattr(overlay_manager, "set_mpr_banner", None)
    if callable(banner):
        try:
            banner(None)
        except Exception:
            pass


def _bump_closed_source_generations(
    controller: Any, study_uid: str, series_uid: str | None
) -> None:
    """Invalidate late worker callbacks built from the closed source."""
    for key in [k for k in controller._source_generations if k[0] == study_uid
                and (series_uid is None or k[1] == series_uid)]:
        bump_source_generation(controller, *key)



__all__ = [
    "release_all_mpr",
    "release_closed_source_sessions",
]
