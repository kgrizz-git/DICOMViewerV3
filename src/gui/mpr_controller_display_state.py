"""Per-pane MPR display-state application for ``MprController``.

Owns the window/level reset, carried-state restore, and shared-toolbar sync
that ``MprController`` invokes during install/activate/display. Extracted so
``gui/mpr_controller.py`` stays within its line budget; behavior is
unchanged. The controller keeps thin delegates (``_reset_window_level_for_mpr``,
``_get_preferred_mpr_window_level``, ``_install_apply_display_state``) so
existing call sites and test seams keep working.

Conventions match the controller: ``app`` is duck-typed, the shared toolbar
syncs only for the focused pane, and failures inside the reset path are
reported without raising.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from core.mpr_session_types import MprDisplayState
from core.mpr_view_display_state import (
    clear_mpr_lut_override,
    restore_mpr_display_state,
)
from core.mpr_view_math import auto_window_level
from utils.debug_flags import DEBUG_MPR
from utils.privacy.console import print_redacted


def _display_log(message: str) -> None:
    """Print an MPR display debug message when DEBUG_MPR is enabled."""
    if DEBUG_MPR:
        print(f"[DEBUG-MPR] {message}")


def reset_window_level_for_mpr(
    app: Any,
    get_image_viewer: Callable[[int], Any],
    idx: int,
    source_dataset: Any,
) -> None:
    """
    Reset window/level controls to defaults from the MPR source dataset.

    This ensures that when a new MPR is created, we use the window/level
    from the new source series, not stale values from a previous series.

    Per-pane rescale / HU alignment: ``ViewStateManager`` and the target
    ``ImageViewer`` rescale toggle are **always** updated for *idx* so MPR
    created in an unfocused pane still applies slope/intercept before the
    first ``display_mpr_slice``. Global toolbar W/L spinboxes and the main
    window rescale toggle are updated only when *idx* is the focused pane.
    """
    focused = getattr(app, "focused_subwindow_index", -1)
    wl_controls = getattr(app, "window_level_controls", None)

    try:
        from core.dicom_processor import DICOMProcessor
        from core.dicom_rescale import get_rescale_parameters
        from core.dicom_window_level import (
            get_window_level_from_dataset,
            get_window_level_presets_from_dataset,
        )

        # Fresh defaults carry no LUT: drop any override a previous MPR
        # view left on this pane before rebuilding pane state.
        clear_mpr_lut_override(
            app.subwindow_managers.get(idx, {}).get("view_state_manager")
        )
        rescale_slope, rescale_intercept, rescale_type = get_rescale_parameters(
            source_dataset
        )
        if (
            rescale_type is None
            and rescale_slope is not None
            and rescale_intercept is not None
        ):
            rescale_type = DICOMProcessor.infer_rescale_type(
                source_dataset, rescale_slope, rescale_intercept, None
            )

        view_state_manager = sync_pane_rescale(
            app, get_image_viewer, idx, focused, rescale_slope, rescale_intercept, rescale_type
        )
        wc, ww, is_rescaled = resolve_center_width(
            source_dataset,
            rescale_slope,
            rescale_intercept,
            get_window_level_presets_from_dataset,
            get_window_level_from_dataset,
        )
        apply_window_level_values(
            idx,
            focused,
            wl_controls,
            view_state_manager,
            wc,
            ww,
            is_rescaled,
            rescale_slope,
            rescale_intercept,
            rescale_type,
        )
    except Exception as exc:
        print_redacted(f"[MprController] Failed to reset W/L for MPR in window {idx}: {exc}")


def sync_pane_rescale(
    app: Any,
    get_image_viewer: Callable[[int], Any],
    idx: int,
    focused: int,
    rescale_slope: Any,
    rescale_intercept: Any,
    rescale_type: Any,
) -> Any:
    """Sync per-pane rescale state; also sync main-window toggle when focused."""
    managers = app.subwindow_managers.get(idx, {})
    view_state_manager = managers.get("view_state_manager")
    if view_state_manager is None:
        return None
    view_state_manager.set_rescale_parameters(
        rescale_slope, rescale_intercept, rescale_type
    )
    use_rescaled_default = (
        rescale_slope is not None and rescale_intercept is not None
    )
    view_state_manager.use_rescaled_values = use_rescaled_default
    if idx == focused and hasattr(app, "main_window"):
        app.main_window.set_rescale_toggle_state(use_rescaled_default)
    image_viewer = get_image_viewer(idx)
    if image_viewer is not None:
        image_viewer.set_rescale_toggle_state(use_rescaled_default)
    return view_state_manager


def resolve_center_width(
    source_dataset: Any,
    rescale_slope: Any,
    rescale_intercept: Any,
    get_presets: Callable[..., Any],
    get_single_wl: Callable[..., Any],
) -> tuple[Any, Any, Any]:
    """Resolve window center/width from presets or single-tag fallback."""
    presets = get_presets(source_dataset, rescale_slope, rescale_intercept)
    if presets:
        wc, ww, is_rescaled, _preset_name = presets[0]
        return wc, ww, is_rescaled
    wc, ww, is_rescaled = get_single_wl(
        source_dataset, rescale_slope, rescale_intercept
    )
    return wc, ww, is_rescaled


def apply_window_level_values(
    idx: int,
    focused: int,
    wl_controls: Any,
    view_state_manager: Any,
    wc: Any,
    ww: Any,
    is_rescaled: Any,
    rescale_slope: Any,
    rescale_intercept: Any,
    rescale_type: Any,
) -> None:
    """Write W/L into pane view state and optionally sync shared toolbar."""
    if wc is None or ww is None or ww <= 0:
        return
    if view_state_manager is not None:
        view_state_manager.current_window_center = wc
        view_state_manager.current_window_width = ww
        view_state_manager.window_level_user_modified = False
    if idx != focused or wl_controls is None:
        return
    unit = None
    if rescale_slope is not None and rescale_intercept is not None:
        unit = rescale_type
    wl_controls.set_window_level(wc, ww, block_signals=False, unit=unit)
    _display_log(f"Reset W/L for MPR: center={wc:.1f} width={ww:.1f} rescaled={is_rescaled}")


def preferred_mpr_window_level(
    view_state_manager: Any, wl_controls: Any, array: np.ndarray
) -> Any:
    """
    Return the window/level to use for MPR display.

    Preference order:
    1. The target pane's own stored window/level in ``ViewStateManager``.
    2. The shared toolbar controls (focused pane behavior).
    3. Auto window/level from the current pixel data.
    """
    if view_state_manager is not None:
        try:
            wc = float(view_state_manager.current_window_center)
            ww = float(view_state_manager.current_window_width)
            if ww > 0:
                return wc, ww
        except (AttributeError, TypeError, ValueError):
            pass
    return controls_window_level(wl_controls, array)


def controls_window_level(wl_controls: Any, array: np.ndarray) -> Any:
    """
    Read the current window centre/width from the window-level controls.

    Falls back to (percentile-based) auto W/L from the array if controls
    are unavailable.
    """
    if wl_controls is not None:
        try:
            wc = float(wl_controls.window_center)
            ww = float(wl_controls.window_width)
            if ww > 0:
                return wc, ww
        except (AttributeError, TypeError, ValueError):
            pass

    # Auto W/L (percentile) — delegates to core.mpr_view_math.
    return auto_window_level(array)


def install_apply_display_state(
    app: Any,
    get_image_viewer: Callable[[int], Any],
    idx: int,
    payload: dict[str, Any],
    source_ds: Any,
    reset: Callable[[int, Any], None],
) -> None:
    """Restore carried display state, or reset to source defaults.

    Payloads carrying an ``MprDisplayState`` snapshot restore the view's
    own W/L, rescale, inversion and LUT. Older payloads without one keep
    the previous reset-to-source-defaults behavior (plus stale-override
    cleanup) via *reset*. New builds always use the reset path.
    """
    managers = app.subwindow_managers.get(idx, {})
    view_state_manager = managers.get("view_state_manager")
    state = payload.get("mpr_display")
    if isinstance(state, MprDisplayState):
        restore_mpr_display_state(
            view_state_manager, get_image_viewer(idx), state
        )
        sync_shared_mpr_controls(app, idx, state)
        return
    clear_mpr_lut_override(view_state_manager)
    reset(idx, source_ds)


def sync_shared_mpr_controls(app: Any, idx: int, state: MprDisplayState) -> None:
    """Sync the shared W/L toolbar for carried state when *idx* is focused.

    Mirrors the focused-only policy of the new-build reset path; unfocused
    panes keep their carried values pane-local until focused. Signals stay
    blocked so the shared ``window_changed`` handlers cannot reprocess
    these values back into the pane (which would snap W/L to presets and
    clobber the carried user-modified flag). The rescale unit shows only
    when the carried state actually uses rescaled values.
    """
    if idx != getattr(app, "focused_subwindow_index", -1):
        return
    if (
        state.window_center is not None
        and state.window_width is not None
        and state.window_width > 0
    ):
        wl_controls = getattr(app, "window_level_controls", None)
        if wl_controls is not None:
            unit = None
            if (
                state.use_rescaled
                and state.rescale_slope is not None
                and state.rescale_intercept is not None
            ):
                unit = state.rescale_type or None
            wl_controls.set_window_level(
                state.window_center, state.window_width,
                block_signals=True, unit=unit,
            )
            if unit is None:
                # set_window_level leaves a prior unit label in place
                # when unit is None; clear it so a stale HU does not
                # linger on raw (non-rescaled) state.
                wl_controls.set_unit(None)
    if hasattr(app, "main_window"):
        app.main_window.set_rescale_toggle_state(bool(state.use_rescaled))
