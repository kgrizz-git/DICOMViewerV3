"""Per-pane MPR combine/display capture, restore, and LUT-override helpers.

Pure core support for the P1 multiple-MPR-sessions plan: display state
(W/L, user-modified flag, rescale parameters/mode, inversion, LUT) travels
with a detached/moved MPR view instead of being reset to source defaults or
borrowed from whichever unrelated pane currently has focus.

Focus independence: capture reads only the given pane's own view-state
manager and image viewer — never the shared toolbar controls or the focused
pane. Restore writes only that pane's manager/viewer; syncing the shared
toolbar stays in the controller layer, which applies it for the focused pane
only (same policy as the existing W/L reset).

LUT independence: the active LUT for ordinary display lives in a
per-pane ``series_defaults[series_id]["current_lut"]`` slot, so writing a
moved view's LUT there would recolor that pane's 2-D series state as well.
MPR views instead keep their LUT in the dedicated per-pane override slot
from ``core.lut_series_state`` (``MPR_LUT_OVERRIDE_KEY``), which the MPR
display path prefers. Only the destination pane's own manager is ever
written; a source pane's slots are read-only during capture.

Like ``core.lut_series_state``, managers and viewers are duck-typed so unit
tests can use fakes; Qt stays out of this module.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.lut_series_state import (
    MPR_LUT_OVERRIDE_KEY,
    clear_mpr_lut_override,
    get_mpr_effective_lut,
    get_mpr_lut_override,
    set_mpr_lut_override,
)
from core.mpr_session_types import MprCombineState, MprDisplayState

__all__ = [
    "MPR_LUT_OVERRIDE_KEY",
    "capture_mpr_combine_state",
    "capture_mpr_display_state",
    "clear_mpr_lut_override",
    "get_mpr_effective_lut",
    "get_mpr_lut_override",
    "restore_mpr_combine_state",
    "restore_mpr_display_state",
    "set_mpr_lut_override",
]


def _opt_float(value: Any) -> float | None:
    """Return ``float(value)`` or None for missing/non-numeric input."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Combine state
# ---------------------------------------------------------------------------


def capture_mpr_combine_state(data: Mapping[str, Any]) -> MprCombineState:
    """Snapshot slab-combine settings from ``subwindow_data``-style mappings."""
    mode = data.get("mpr_combine_mode", "aip")
    if not isinstance(mode, str) or not mode.strip():
        mode = "aip"
    try:
        slice_count = int(data.get("mpr_combine_slice_count", 4))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        slice_count = 4
    return MprCombineState(
        enabled=bool(data.get("mpr_combine_enabled", False)),
        mode=mode,
        slice_count=slice_count,
    )


def restore_mpr_combine_state(data: dict[str, Any], state: MprCombineState | None) -> None:
    """Write combine settings back into a ``subwindow_data``-style dict.

    ``None`` keeps the existing keys (legacy payload fallback); invalid
    values fall back to disabled/aip/4 without raising.
    """
    if state is None:
        return
    data["mpr_combine_enabled"] = bool(state.enabled)
    data["mpr_combine_mode"] = state.mode if isinstance(state.mode, str) and state.mode.strip() else "aip"
    try:
        data["mpr_combine_slice_count"] = int(state.slice_count)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        data["mpr_combine_slice_count"] = 4


# ---------------------------------------------------------------------------
# Display state
# ---------------------------------------------------------------------------


def capture_mpr_display_state(view_state_manager: Any, image_viewer: Any) -> MprDisplayState:
    """Snapshot a pane's MPR display state (focus-independent).

    Reads only the given pane's manager/viewer. Missing or non-numeric
    W/L degrades to ``None`` (restore then skips the W/L write); a ``None``
    rescale type degrades to ``""``. The LUT is the effective MPR LUT
    (pane override when set, else the series LUT), held by reference —
    ``LookUpTable`` is frozen, so sharing the reference is safe.
    """
    rescale_type = getattr(view_state_manager, "rescale_type", "")
    return MprDisplayState(
        window_center=_opt_float(getattr(view_state_manager, "current_window_center", None)),
        window_width=_opt_float(getattr(view_state_manager, "current_window_width", None)),
        wl_user_modified=bool(getattr(view_state_manager, "window_level_user_modified", False)),
        use_rescaled=bool(getattr(view_state_manager, "use_rescaled_values", True)),
        rescale_slope=_opt_float(getattr(view_state_manager, "rescale_slope", None)),
        rescale_intercept=_opt_float(getattr(view_state_manager, "rescale_intercept", None)),
        rescale_type=rescale_type if isinstance(rescale_type, str) else "",
        inverted=bool(getattr(image_viewer, "image_inverted", False)) if image_viewer is not None else False,
        lut=get_mpr_effective_lut(view_state_manager),
    )


def restore_mpr_display_state(
    view_state_manager: Any, image_viewer: Any, state: MprDisplayState | None
) -> None:
    """Restore carried display state onto a pane (focus-independent).

    ``None`` is a no-op (legacy payload fallback is the caller's reset
    path). W/L is written only when both values are present and width is
    positive, mirroring the new-build reset guard; every other field is
    always restored, including the per-pane LUT override. Shared toolbar
    sync is intentionally left to the controller's focused-pane handling.
    """
    if state is None:
        return
    if view_state_manager is not None:
        if (
            state.window_center is not None
            and state.window_width is not None
            and state.window_width > 0
        ):
            view_state_manager.current_window_center = float(state.window_center)
            view_state_manager.current_window_width = float(state.window_width)
        view_state_manager.window_level_user_modified = bool(state.wl_user_modified)
        setter = getattr(view_state_manager, "set_rescale_parameters", None)
        if callable(setter):
            setter(state.rescale_slope, state.rescale_intercept, state.rescale_type)
        else:
            view_state_manager.rescale_slope = state.rescale_slope
            view_state_manager.rescale_intercept = state.rescale_intercept
            view_state_manager.rescale_type = state.rescale_type
        view_state_manager.use_rescaled_values = bool(state.use_rescaled)
    if image_viewer is not None:
        image_viewer.image_inverted = bool(state.inverted)
        # Keep the viewer's rescale toggle in step with the restored mode,
        # mirroring the new-build reset path; otherwise menus show stale state.
        toggle = getattr(image_viewer, "set_rescale_toggle_state", None)
        if callable(toggle):
            toggle(bool(state.use_rescaled))
    set_mpr_lut_override(view_state_manager, state.lut)
