"""
MPR navigator tile reconciliation and pane pixel access.

Navigator tiles represent stable MPR *view IDs* (attached or detached alike);
the pane number is a spec field, never the identity. ``sync_mpr_navigator_tiles``
reads only the controller's public per-view API (metadata, display state,
bounded thumbnail pixels) and hands the navigator the complete tile set in one
call, so a transaction costs at most one navigator rebuild and none when
nothing changed.

Dirty seam: a tile's pixels are regenerated only when its view is named
``dirty`` (live pane state changed), is new, or its ``content_stamp`` differs
from the stamp already shown. A detached view whose slice later changes
through a linked group changes its stamp and refreshes with no extra wiring.

Inputs:
    ``app``: ``DICOMViewerApp`` composition root (``series_navigator``,
    ``_mpr_controller``, ``subwindow_data`` / managers for measurement pixels).
"""

from __future__ import annotations

# pyright: reportImportCycles=false
from typing import TYPE_CHECKING, Any

from core.lut_catalog import linear_lut
from core.lut_engine import LookUpTable
from core.mpr_session_types import MprDisplayState
from core.mpr_stack_combine import apply_mpr_stack_combine
from core.mpr_tile_label import tile_tag, tile_tooltip

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


def _carried_window_level(carried: MprDisplayState) -> tuple[float | None, float | None]:
    """Valid (center, width) from carried display state, else ``(None, None)``."""
    if carried.window_center is None or carried.window_width is None:
        return None, None
    if carried.window_width <= 0:
        return None, None
    return float(carried.window_center), float(carried.window_width)


def _tile_spec(controller: Any, view_id: int, meta: Any, *, regenerate: bool) -> dict[str, Any] | None:
    """Navigator spec for one view; ``pixel_array`` None means "keep the shown pixels"."""
    spec: dict[str, Any] = {
        "study_uid": meta.source_study_uid,
        "source_series_uid": meta.source_series_uid,
        "n_slices": meta.n_slices or None,
        "order": meta.creation_seq,
        "pane_index": meta.pane_index,
        "origin": controller.drag_origin,
        "linked": meta.link_group_id is not None,
        "tag": tile_tag(meta),
        "tooltip": tile_tooltip(
            meta, None if meta.pane_index is None else str(meta.pane_index + 1)
        ),
        "pixel_array": None,
    }
    if not regenerate:
        return spec
    carried = controller.get_view_display_state(view_id)
    if carried is None:
        return None
    pixels = controller.get_view_thumbnail_pixels(view_id, carried.use_rescaled)
    if pixels is None:
        return None
    wc, ww = _carried_window_level(carried)
    spec.update(
        pixel_array=pixels,
        window_center=wc,
        window_width=ww,
        photometric_interpretation=meta.photometric_interpretation,
        image_inverted=bool(carried.inverted),
        lut=carried.lut if isinstance(carried.lut, LookUpTable) else linear_lut(),
        stamp=meta.content_stamp,
    )
    return spec


def sync_mpr_navigator_tiles(app: DICOMViewerApp, dirty: Any = ()) -> None:
    """Reconcile the navigator's MPR tiles with the controller's views, once.

    *dirty* is a collection of view IDs whose pixels must be regenerated even
    if their stamp matches. Everything else regenerates only when new or
    changed; the navigator rebuilds at most once and not at all if the result
    equals what it already shows.
    """
    navigator = getattr(app, "series_navigator", None)
    controller = getattr(app, "_mpr_controller", None)
    if navigator is None or controller is None:
        return
    dirty_ids = {d for d in dirty if isinstance(d, int)}
    shown = navigator.mpr_tile_stamps()
    incoming: dict[int, dict[str, Any]] = {}
    for view_id in controller.all_view_ids():
        meta = controller.get_view_metadata(view_id)
        if meta is None:
            continue
        regenerate = view_id in dirty_ids or shown.get(view_id) != meta.content_stamp
        spec = _tile_spec(controller, view_id, meta, regenerate=regenerate)
        if spec is not None:
            incoming[view_id] = spec
    navigator.reconcile_mpr_thumbnails(incoming)


def refresh_pane_mpr_tile(app: DICOMViewerApp, idx: int) -> None:
    """Regenerate the tile of the view attached to pane *idx* (look-up table / W/L change)."""
    controller = getattr(app, "_mpr_controller", None)
    view_id = controller.attached_view_id(idx) if controller is not None else None
    if view_id is not None:
        sync_mpr_navigator_tiles(app, {view_id})
