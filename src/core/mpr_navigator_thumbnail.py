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

from typing import TYPE_CHECKING, Optional

from core.mpr_controller import apply_mpr_stack_combine

if TYPE_CHECKING:  # pragma: no cover
    from main import DICOMViewerApp


def get_subwindow_mpr_pixel_array(
    app: "DICOMViewerApp", idx: int, slice_index: Optional[int] = None
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


def get_subwindow_mpr_thumbnail_pixel_array(app: "DICOMViewerApp", idx: int):
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


def update_mpr_navigator_thumbnail(app: "DICOMViewerApp", idx: int) -> None:
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
    n_slices: Optional[int] = None
    if result is not None:
        try:
            n_raw = int(getattr(result, "n_slices", 0) or 0)
            n_slices = n_raw if n_raw > 0 else None
        except (TypeError, ValueError):
            n_slices = None

    wc: Optional[float] = None
    ww: Optional[float] = None
    wl_controls = getattr(app, "window_level_controls", None)
    if wl_controls is not None:
        try:
            wc_val = float(wl_controls.window_center)
            ww_val = float(wl_controls.window_width)
            if ww_val > 0:
                wc, ww = wc_val, ww_val
        except (AttributeError, TypeError, ValueError):
            pass

    app.series_navigator.set_mpr_thumbnail(
        idx,
        pixel_array,
        str(data.get("current_study_uid", "") or ""),
        str(data.get("current_series_uid", "") or ""),
        wc,
        ww,
        n_slices,
    )


def clear_mpr_navigator_thumbnail(app: "DICOMViewerApp", idx: int) -> None:
    """
    Remove the MPR thumbnail from the series navigator for subwindow *idx*.

    Called automatically when ``MprController.mpr_cleared`` is emitted.

    Args:
        idx: Zero-based subwindow index whose MPR was cleared.
    """
    if hasattr(app, "series_navigator"):
        app.series_navigator.clear_mpr_thumbnail(idx)


def update_floating_mpr_navigator_thumbnail(app: "DICOMViewerApp") -> None:
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
    focused = getattr(app, "focused_subwindow_index", 0)
    vsm = app.subwindow_managers.get(focused, {}).get("view_state_manager")
    use_rescaled = bool(getattr(vsm, "use_rescaled_values", True))
    pixel_array = app._mpr_controller.get_detached_mpr_thumbnail_pixels(
        use_rescaled
    )
    if pixel_array is None:
        return
    payload = getattr(app._mpr_controller, "_detached_mpr_payload", None)
    study_uid = ""
    series_uid = ""
    n_slices: Optional[int] = None
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
    wc: Optional[float] = None
    ww: Optional[float] = None
    wl_controls = getattr(app, "window_level_controls", None)
    if wl_controls is not None:
        try:
            wc_val = float(wl_controls.window_center)
            ww_val = float(wl_controls.window_width)
            if ww_val > 0:
                wc, ww = wc_val, ww_val
        except (AttributeError, TypeError, ValueError):
            pass
    app.series_navigator.set_mpr_thumbnail(
        -1,
        pixel_array,
        study_uid,
        series_uid,
        wc,
        ww,
        n_slices,
    )


def on_mpr_detached(app: "DICOMViewerApp", former_idx: int) -> None:
    """MPR was detached from a pane; refresh navigator thumbnails."""
    clear_mpr_navigator_thumbnail(app, former_idx)
    update_floating_mpr_navigator_thumbnail(app)
