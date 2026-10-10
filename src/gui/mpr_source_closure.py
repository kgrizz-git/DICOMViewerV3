"""MPR source-closure release for ``MprController``.

Retires builds tied to a closed study or series, drops matching detached
payloads, and resets per-pane MPR tool/LUT/banner/navigator state without
touching study data (callers clear it). Close-all releases every worker,
payload, override, and spec. Matching uses authoritative build sources for
workers and displayed study/series for chrome — never one for the other.
"""

from __future__ import annotations

from typing import Any

from core.lut_series_state import clear_mpr_lut_override
from gui.mpr_worker_fencing import retire_pane_worker

# ---------------------------------------------------------------------------
# Source closure release
# ---------------------------------------------------------------------------


def _payload_source(payload: Any) -> tuple[str, str] | None:
    if not isinstance(payload, dict):
        return None
    return (
        str(payload.get("current_study_uid", "") or ""),
        str(payload.get("current_series_uid", "") or ""),
    )


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
    resets the MPR tool override, drops a matching detached payload, purges
    orphan navigator specs, and bumps source generations so late worker
    callbacks cannot resurrect closed data. Study data itself is untouched
    (callers clear it). Returns release counts.
    """
    app = controller._app
    released = {"panes": 0, "workers": 0, "detached": 0, "specs": 0}
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
        if _clear_navigator_spec(app, idx):
            released["specs"] += 1
        released["panes"] += 1
    if _source_matches(study_uid, series_uid, _payload_source(controller._detached_mpr_payload)):
        controller._detached_mpr_payload = None
        _clear_navigator_spec(app, -1)
        released["detached"] += 1
    _bump_closed_source_generations(controller, study_uid, series_uid)
    return released


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
    """Release every MPR build, session payload, override, and spec.

    Retires all registered workers (including pending builds on empty panes
    whose source no pane displays), drops any detached payload, bumps every
    source generation, and resets per-pane MPR chrome on every known pane.
    Study data itself is untouched (callers clear it).
    """
    app = controller._app
    released = {"panes": 0, "workers": 0, "detached": 0, "specs": 0}
    panes = set(app.subwindow_data) | set(controller._workers.keys())
    for idx in sorted(panes):
        if retire_pane_worker(controller, idx):
            released["workers"] += 1
        _reset_pane_mpr_chrome(controller, app, idx)
        if _clear_navigator_spec(app, idx):
            released["specs"] += 1
        released["panes"] += 1
    if controller._detached_mpr_payload is not None:
        controller._detached_mpr_payload = None
        _clear_navigator_spec(app, -1)
        released["detached"] += 1
    for key in list(controller._source_generations.keys()):
        controller._source_generations[key] += 1
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


def _clear_navigator_spec(app: Any, key: int) -> bool:
    """Purge one orphan navigator MPR spec; True when cleared."""
    navigator = getattr(app, "series_navigator", None)
    clearer = getattr(navigator, "clear_mpr_thumbnail", None)
    if not callable(clearer):
        return False
    try:
        clearer(key)
    except Exception:
        return False
    return True


def _bump_closed_source_generations(
    controller: Any, study_uid: str, series_uid: str | None
) -> None:
    """Invalidate late worker callbacks built from the closed source."""
    for key in [k for k in controller._source_generations if k[0] == study_uid
                and (series_uid is None or k[1] == series_uid)]:
        controller._source_generations[key] += 1



__all__ = [
    "release_all_mpr",
    "release_closed_source_sessions",
]
