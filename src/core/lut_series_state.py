"""
Per-series LUT lookup on a pane's ``ViewStateManager.series_defaults``.

The active LUT is the ``current_lut`` entry. A missing entry is the built-in
linear ramp, which matches today's window/level picture. The user invert flag
still lives in ``image_inverted``; this module only reads it so the display
path can apply it before the LUT.

Inputs:
    - A view-state manager (duck typed) and a series identifier

Outputs:
    - ``LookUpTable`` and the boolean user-invert flag for that pane

Requirements:
    - core.lut_catalog.linear_lut
    - core.lut_engine.LookUpTable
"""

from __future__ import annotations

from typing import Any

from core.lut_catalog import linear_lut
from core.lut_engine import LookUpTable


def get_series_lut(view_state: Any, series_identifier: str | None) -> LookUpTable:
    """Return the series LUT, or linear when the series has not chosen one."""
    defaults = _defaults(view_state, series_identifier)
    stored = defaults.get("current_lut")
    if isinstance(stored, LookUpTable):
        return stored
    return linear_lut()


def set_series_lut(
    view_state: Any,
    lut: LookUpTable,
    series_identifier: str | None,
) -> None:
    """Store ``lut`` on the series defaults. Replaces; does not mutate ``lut``."""
    if not series_identifier:
        return
    bucket = view_state.series_defaults.setdefault(series_identifier, {})
    bucket["current_lut"] = lut


def active_image_inverted(
    view_state: Any,
    *,
    series_identifier: str | None,
    preserve_view: bool,
    photometric_interpretation: Any,
) -> bool:
    """User-invert flag for this draw: the live viewer flag, or the stored one.

    While scrolling (``preserve_view``), the viewer's flag is the one the last
    toggle set. A new series load reads the persisted value instead.
    """
    viewer = getattr(view_state, "image_viewer", None)
    if preserve_view and viewer is not None:
        return bool(getattr(viewer, "image_inverted", False))
    getter = getattr(view_state, "get_series_inversion_state", None)
    if getter is None:
        return False
    return bool(getter(series_identifier, pi=photometric_interpretation))


def mpr_display_kwargs(managers: dict[str, Any] | None, photometric_interpretation: str | None) -> dict[str, Any]:
    """LUT and user-invert kwargs for an MPR pane. Linear and False when the pane has no view state."""
    view_state = (managers or {}).get("view_state_manager")
    if view_state is None:
        return {"image_inverted": False, "lut": linear_lut()}
    series_id = getattr(view_state, "current_series_identifier", None)
    return {
        "image_inverted": active_image_inverted(
            view_state,
            series_identifier=series_id,
            preserve_view=True,
            photometric_interpretation=photometric_interpretation,
        ),
        "lut": get_series_lut(view_state, series_id),
    }


def focused_pane_lut(view_state: Any) -> tuple[bool, LookUpTable]:
    """Live user-invert flag and series LUT for the pane currently on screen."""
    if view_state is None:
        return False, linear_lut()
    series_id = getattr(view_state, "current_series_identifier", None)
    return (
        active_image_inverted(
            view_state,
            series_identifier=series_id,
            preserve_view=True,
            photometric_interpretation=None,
        ),
        get_series_lut(view_state, series_id),
    )


def slice_lut_kwargs(
    view_state: Any,
    series_identifier: str | None,
    preserve_view: bool,
    photometric_interpretation: Any,
) -> dict[str, Any]:
    """LUT and user-invert kwargs for a 2-D slice draw."""
    if isinstance(photometric_interpretation, (list, tuple)) and photometric_interpretation:
        photometric_interpretation = photometric_interpretation[0]
    return {
        "image_inverted": active_image_inverted(
            view_state,
            series_identifier=series_identifier,
            preserve_view=preserve_view,
            photometric_interpretation=photometric_interpretation,
        ),
        "lut": get_series_lut(view_state, series_identifier),
    }


def _defaults(view_state: Any, series_identifier: str | None) -> dict[str, Any]:
    """Return the series default dict, or an empty dict when it is absent."""
    if not series_identifier:
        return {}
    found = view_state.series_defaults.get(series_identifier)
    if isinstance(found, dict):
        return found
    return {}
