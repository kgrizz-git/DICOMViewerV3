"""
GUI wrappers around per-series LUT state.

Lookup lives in ``core.lut_series_state`` so core thumbnail code can read the
same pane LUT without importing this package. ``show_slice_image`` stays here
because it calls viewer methods.

Inputs:
    - A view-state manager, an image viewer, and a series identifier

Outputs:
    - ``LookUpTable``, the user-invert flag, and a viewer update

Requirements:
    - core.lut_series_state
"""

from __future__ import annotations

from typing import Any

from core.lut_series_state import (
    active_image_inverted,
    get_series_lut,
    mpr_display_kwargs,
    set_series_lut,
    slice_lut_kwargs,
)

__all__ = [
    "active_image_inverted",
    "get_series_lut",
    "mpr_display_kwargs",
    "set_series_lut",
    "show_slice_image",
    "slice_lut_kwargs",
]


def show_slice_image(
    viewer: Any,
    image: Any,
    *,
    preserve_view: bool,
    apply_inversion: bool | None,
    display_final: bool,
    image_inverted: bool,
) -> None:
    """Grayscale pixels are already inverted. Color DICOM still inverts in ``set_image``."""
    if display_final:
        viewer.set_display_final_image(image, preserve_view=preserve_view, image_inverted=image_inverted)
        return
    viewer.set_image(image, preserve_view=preserve_view, apply_inversion=apply_inversion)
