"""
Backward-compatible re-exports for 3D volume render eligibility.

The dialog-launching facade lives in ``gui.volume_render_facade`` (Qt / dialogs).
"""

from core.volume_render_eligibility import (
    MIN_SLICES_FOR_VOLUME,
    can_launch_3d_volume_render,
    get_datasets_for_subwindow,
    series_has_volume_geometry,
)

# Legacy name used in tests.
_MIN_SLICES_FOR_VOLUME = MIN_SLICES_FOR_VOLUME

__all__ = [
    "MIN_SLICES_FOR_VOLUME",
    "_MIN_SLICES_FOR_VOLUME",
    "can_launch_3d_volume_render",
    "get_datasets_for_subwindow",
    "series_has_volume_geometry",
]
