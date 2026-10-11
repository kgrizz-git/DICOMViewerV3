"""
MPR pane pixel access for measurement and preview paths.

In this slice the navigator carries no MPR representation; this module keeps
only the pane-level pixel accessor that non-navigator features (measurement
spacing, per-pane LUT preview) need for an MPR subwindow.
"""

from __future__ import annotations

# pyright: reportImportCycles=false
from typing import TYPE_CHECKING

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
