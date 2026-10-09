"""
MPR navigator thumbnail helpers for the series navigator.

Holds pixel-array extraction and thumbnail update/clear logic moved from
``DICOMViewerApp`` so ``main.py`` stays smaller. ``app_signal_wiring`` and
other callers still use ``DICOMViewerApp._update_mpr_navigator_thumbnail`` etc.
as one-line delegates into this module.

Inputs:
    ``app``: ``DICOMViewerApp`` composition root (subwindow_data, managers,
    series_navigator, window_level_controls, ``_mpr_controller``).

Outputs:
    Mutates series navigator MPR thumbnail state; read-only on pixel arrays
    except through MPR combine helpers.

Requirements:
    PySide6 GUI app context; ``apply_mpr_stack_combine`` from ``mpr_controller``.
"""

from __future__ import annotations

# pyright: reportImportCycles=false
from typing import TYPE_CHECKING, Any

from core.lut_catalog import linear_lut
from core.lut_engine import LookUpTable
from core.lut_series_state import mpr_display_kwargs
from core.mpr_session_types import MprDisplayState
from core.mpr_stack_combine import apply_mpr_stack_combine

if TYPE_CHECKING:  # pragma: no cover
    from main import DICOMViewerApp


def get_subwindow_mpr_pixel_array(
    app: DICOMViewerApp, idx: int, slice_index: int | None = None
):
    """Return an MPR pixel array for subwindow *idx* (if any)."""
    try:
        data = app.subwindow_data.get(idx, {})
        if not data.get("is_mpr"):
            return None
        result = data.get("mpr_result")
        if result is None:
            return None
        if slice_index is None:
            slice_index = data.get("mpr_slice_index", 0)
        if slice_index is None:
            return None
        slice_index = int(slice_index)
        if slice_index < 0 or slice_index >= getattr(result, "n_slices", 0):
            return None
        raw = apply_mpr_stack_combine(
            result.slices,
            slice_index,
            enabled=bool(data.get("mpr_combine_enabled", False)),
            mode=str(data.get("mpr_combine_mode", "aip") or "aip"),
            n_planes=int(data.get("mpr_combine_slice_count", 4) or 4),
        )
        managers = app.subwindow_managers.get(idx, {})
        view_state_manager = managers.get("view_state_manager")
        use_rescaled = bool(
            getattr(view_state_manager, "use_rescaled_values", True)
        )
        if use_rescaled:
            return result.apply_rescale(raw)
        return raw
    except Exception:
        return None


def get_subwindow_mpr_thumbnail_pixel_array(app: DICOMViewerApp, idx: int):
    """Return a representative MPR thumbnail slice, preferring the stack midpoint."""
    data = app.subwindow_data.get(idx, {})
    result = data.get("mpr_result")
    if result is None:
        return None
    n_slices = int(getattr(result, "n_slices", 0) or 0)
    if n_slices <= 0:
        return None
    middle_index = n_slices // 2
    return get_subwindow_mpr_pixel_array(app, idx, middle_index)


def _result_photometric_interpretation(result: object | None) -> str | None:
    """Source-series PI carried on an MprResult, or None when unavailable.

    Keeps the thumbnail at the same polarity as the pane it previews.
    """
    if result is None:
        return None
    value = getattr(result, "photometric_interpretation", None)
    return str(value) if value else None


def _pane_managers(app: DICOMViewerApp, idx: int) -> dict[str, Any] | None:
    """Return one pane's manager dict. Missing on stubs that predate the LUT wiring."""
    managers = getattr(app, "subwindow_managers", None)
    if not isinstance(managers, dict):
        return None
    found = managers.get(idx)
    return found if isinstance(found, dict) else None


def update_mpr_navigator_thumbnail(app: DICOMViewerApp, idx: int) -> None:
    """
    Show or refresh the MPR thumbnail in the series navigator for subwindow *idx*.

    Called automatically when ``MprController.mpr_activated`` is emitted.
    The thumbnail is built from the currently-displayed MPR slice pixel
    array with the active W/L values so it matches what is on screen.

    Args:
        idx: Zero-based subwindow index hosting the MPR view.
    """
    if not hasattr(app, "series_navigator"):
        return
    data = app.subwindow_data.get(idx, {})
    if not data.get("is_mpr") or data.get("mpr_result") is None:
        app.series_navigator.clear_mpr_thumbnail(idx)
        return

    pixel_array = get_subwindow_mpr_thumbnail_pixel_array(app, idx)
    if pixel_array is None:
        return

    result = data.get("mpr_result")
    n_slices: int | None = None
    if result is not None:
        try:
            n_raw = int(getattr(result, "n_slices", 0) or 0)
            n_slices = n_raw if n_raw > 0 else None
        except (TypeError, ValueError):
            n_slices = None

    wc, ww = _prefer_pane_window_level(app, idx)

    photometric = _result_photometric_interpretation(result)
    display = mpr_display_kwargs(_pane_managers(app, idx), photometric)
    app.series_navigator.set_mpr_thumbnail(
        idx,
        pixel_array,
        str(data.get("current_study_uid", "") or ""),
        str(data.get("current_series_uid", "") or ""),
        wc,
        ww,
        n_slices,
        photometric,
        image_inverted=display["image_inverted"],
        lut=display["lut"],
    )


def _prefer_pane_window_level(app: DICOMViewerApp, idx: int) -> tuple[float | None, float | None]:
    """Attached tile W/L from the pane's own view state, else the shared toolbar.

    The toolbar fallback only serves panes without usable view state.
    """
    pane_vsm = (_pane_managers(app, idx) or {}).get("view_state_manager")
    own = _window_level_from_view_state(pane_vsm)
    if own != (None, None):
        return own
    return _window_level_from_controls(getattr(app, "window_level_controls", None))


def _window_level_from_view_state(view_state: Any) -> tuple[float | None, float | None]:
    """Valid (center, width) from view state, else ``(None, None)``."""
    raw_wc: Any = getattr(view_state, "current_window_center", None)
    raw_ww: Any = getattr(view_state, "current_window_width", None)
    return _valid_window_level(raw_wc, raw_ww)


def _window_level_from_controls(wl_controls: Any) -> tuple[float | None, float | None]:
    """Valid (center, width) from shared toolbar controls, else ``(None, None)``."""
    if wl_controls is None:
        return None, None
    raw_wc: Any = getattr(wl_controls, "window_center", None)
    raw_ww: Any = getattr(wl_controls, "window_width", None)
    return _valid_window_level(raw_wc, raw_ww)


def _valid_window_level(raw_wc: Any, raw_ww: Any) -> tuple[float | None, float | None]:
    """Valid (center, width) pair, else ``(None, None)`` for missing/invalid input."""
    try:
        wc = float(raw_wc)
        ww = float(raw_ww)
    except (TypeError, ValueError):
        return None, None
    if ww <= 0:
        return None, None
    return wc, ww


def _carried_window_level(carried: MprDisplayState) -> tuple[float | None, float | None]:
    """Valid (center, width) from carried display state, else ``(None, None)``."""
    if carried.window_center is None or carried.window_width is None:
        return None, None
    if carried.window_width <= 0:
        return None, None
    return float(carried.window_center), float(carried.window_width)


def clear_mpr_navigator_thumbnail(app: DICOMViewerApp, idx: int) -> None:
    """
    Remove the MPR thumbnail from the series navigator for subwindow *idx*.

    Called automatically when ``MprController.mpr_cleared`` is emitted.

    Args:
        idx: Zero-based subwindow index whose MPR was cleared.
    """
    if hasattr(app, "series_navigator"):
        app.series_navigator.clear_mpr_thumbnail(idx)


def update_floating_mpr_navigator_thumbnail(app: DICOMViewerApp) -> None:
    """
    Show or refresh detached MPR under navigator key -1 (internal id only).

    Layout matches attached MPR: same study/series keys place the thumbnail
    immediately after the source series row.
    """
    if not hasattr(app, "series_navigator"):
        return
    if not app._mpr_controller.has_detached_mpr():
        app.series_navigator.clear_mpr_thumbnail(-1)
        return
    payload = getattr(app._mpr_controller, "_detached_mpr_payload", None)
    use_rescaled, wc, ww, image_inverted, lut = _floating_display_choice(app, payload)
    pixel_array = app._mpr_controller.get_detached_mpr_thumbnail_pixels(
        use_rescaled
    )
    if pixel_array is None:
        return
    study_uid, series_uid, n_slices = _floating_source_parts(payload)
    photometric = _result_photometric_interpretation(
        payload.get("mpr_result") if isinstance(payload, dict) else None
    )
    app.series_navigator.set_mpr_thumbnail(
        -1,
        pixel_array,
        study_uid,
        series_uid,
        wc,
        ww,
        n_slices,
        photometric,
        image_inverted=image_inverted,
        lut=lut,
    )


def _floating_display_choice(
    app: DICOMViewerApp, payload: Any
) -> tuple[bool, float | None, float | None, bool, Any]:
    """Detached tile display values: rescale flag, W/L, inversion, LUT.

    A detached view carries its own display state, which supplies everything
    and never consults the focused pane. Legacy payloads predate carried
    state and keep the focused fallback.
    """
    carried = payload.get("mpr_display") if isinstance(payload, dict) else None
    if isinstance(carried, MprDisplayState):
        wc, ww = _carried_window_level(carried)
        lut = carried.lut if isinstance(carried.lut, LookUpTable) else linear_lut()
        return bool(carried.use_rescaled), wc, ww, bool(carried.inverted), lut
    focused = getattr(app, "focused_subwindow_index", 0)
    vsm = app.subwindow_managers.get(focused, {}).get("view_state_manager")
    wc, ww = _window_level_from_controls(getattr(app, "window_level_controls", None))
    display = mpr_display_kwargs(
        _pane_managers(app, focused),
        _result_photometric_interpretation(
            payload.get("mpr_result") if isinstance(payload, dict) else None
        ),
    )
    return (
        bool(getattr(vsm, "use_rescaled_values", True)),
        wc,
        ww,
        display["image_inverted"],
        display["lut"],
    )


def _floating_source_parts(payload: Any) -> tuple[str, str, int | None]:
    """Detached tile identity: study UID, series UID, slice count."""
    study_uid = ""
    series_uid = ""
    n_slices: int | None = None
    if isinstance(payload, dict):
        study_uid = str(payload.get("current_study_uid", "") or "")
        series_uid = str(payload.get("current_series_uid", "") or "")
        res = payload.get("mpr_result")
        if res is not None:
            try:
                n_raw = int(getattr(res, "n_slices", 0) or 0)
                n_slices = n_raw if n_raw > 0 else None
            except (TypeError, ValueError):
                n_slices = None
    return study_uid, series_uid, n_slices


def on_mpr_detached(app: DICOMViewerApp, former_idx: int) -> None:
    """MPR was detached from a pane; refresh navigator thumbnails."""
    clear_mpr_navigator_thumbnail(app, former_idx)
    update_floating_mpr_navigator_thumbnail(app)
