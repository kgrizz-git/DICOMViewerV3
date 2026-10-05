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
from core.photometric_polarity import dataset_photometric_interpretation


def pane_lut_overlay(view_state: Any, dataset: Any) -> tuple[LookUpTable, str, bool]:
    """Active LUT, photometric interpretation, and the live user-invert flag.

    The invert flag is the viewer's, which is the value ``set_image`` applies
    for this pane. It is not another pane's series default.
    """
    series_id = getattr(view_state, "current_series_identifier", None)
    lut = get_series_lut(view_state, series_id)
    viewer = getattr(view_state, "image_viewer", None)
    inverted = bool(getattr(viewer, "image_inverted", False))
    photometric = dataset_photometric_interpretation(dataset) if dataset is not None else ""
    return lut, photometric, inverted


def get_series_lut(view_state: Any, series_identifier: str | None) -> LookUpTable:
    """Return the series LUT; else the modality default for the shown series; else linear."""
    defaults = _defaults(view_state, series_identifier)
    stored = defaults.get("current_lut")
    if isinstance(stored, LookUpTable):
        return stored
    # A series that never chose takes its modality's default, when one is set.
    resolver = getattr(view_state, "lut_default_resolver", None)
    if callable(resolver) and series_identifier == getattr(view_state, "current_series_identifier", None):
        found = resolver()
        if isinstance(found, LookUpTable):
            return found
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


def get_series_voi_from_dicom(view_state: Any, series_identifier: str | None) -> bool:
    """True when the series displays through its embedded DICOM LUTs ("From DICOM")."""
    return bool(_defaults(view_state, series_identifier).get("voi_from_dicom", False))


def set_series_voi_from_dicom(view_state: Any, enabled: bool, series_identifier: str | None) -> None:
    """Store the series' "From DICOM" choice next to its LUT."""
    if not series_identifier:
        return
    view_state.series_defaults.setdefault(series_identifier, {})["voi_from_dicom"] = bool(enabled)


def focused_pane_voi_from_dicom(view_state: Any) -> bool:
    """The "From DICOM" choice for the series the pane shows. False without a pane."""
    if view_state is None:
        return False
    return get_series_voi_from_dicom(view_state, getattr(view_state, "current_series_identifier", None))


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
        "voi_from_dicom": get_series_voi_from_dicom(view_state, series_identifier),
    }


def _defaults(view_state: Any, series_identifier: str | None) -> dict[str, Any]:
    """Return the series default dict, or an empty dict when it is absent."""
    if not series_identifier:
        return {}
    found = view_state.series_defaults.get(series_identifier)
    if isinstance(found, dict):
        return found
    return {}
