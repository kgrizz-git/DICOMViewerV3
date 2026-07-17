"""
MPR view/display math — Qt-free helpers (refactor Stream D).

**Scope note:** the actual per-plane *reslice* math already lives in
``core/mpr_builder.py`` and ``core/mpr_volume.py`` — the refactor plan's
assumption that it sat in ``gui/mpr_controller.py`` was outdated. This module
instead extracts the remaining **pure** view/display helpers from the controller
so they are unit-testable without Qt/VTK:

- :func:`compute_mpr_combine_range` — slab [start, end] for AIP/MIP/MinIP combine,
- :func:`build_mpr_banner_text` — active-MPR banner text,
- :func:`auto_window_level` — percentile (2–98) auto window/level,
- :func:`array_to_pil` — linear window/level mapping of a 2-D array to 8-bit gray.

The controller keeps thin static-method wrappers (preserving its public API and
existing tests) that delegate here.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PIL import Image

from utils.privacy.console import print_redacted


def compute_mpr_combine_range(
    n_slices: int, slice_index: int, n_planes: int
) -> tuple[int, int]:
    """Return ``[start, end]`` slab indices for MPR combine at *slice_index*.

    Centers an ``n_planes``-wide slab on *slice_index*, clamped into
    ``[0, n_slices-1]``. Returns ``(0, 0)`` when there are no slices.
    """
    if n_slices <= 0:
        return 0, 0
    n_planes = max(1, int(n_planes))
    i = max(0, min(n_slices - 1, int(slice_index)))
    start = i - (n_planes // 2)
    end = start + n_planes - 1
    if start < 0:
        start = 0
        end = min(n_slices - 1, n_planes - 1)
    if end >= n_slices:
        end = n_slices - 1
        start = max(0, end - (n_planes - 1))
    return start, end


def build_mpr_banner_text(data: dict[str, Any]) -> str:
    """Build the top banner text for the active MPR view.

    Appends the combine mode (AIP/MIP/MinIP) when combine is enabled.
    """
    orientation_label = str(data.get("mpr_orientation", "MPR") or "MPR")
    label = f"MPR - {orientation_label}"
    if bool(data.get("mpr_combine_enabled", False)):
        mode = str(data.get("mpr_combine_mode", "aip") or "aip").lower()
        type_map = {"aip": "AIP", "mip": "MIP", "minip": "MinIP"}
        label += f" ({type_map.get(mode, mode.upper())})"
    return label


def auto_window_level(array: np.ndarray) -> tuple[float, float]:
    """Percentile (2nd–98th) auto window/level over finite pixels.

    Returns ``(window_center, window_width)``; ``(0.0, 1.0)`` if the array has no
    finite values. Width is floored at 1.0.
    """
    flat = array.ravel()
    flat = flat[np.isfinite(flat)]
    if flat.size == 0:
        return 0.0, 1.0
    p2, p98 = float(np.percentile(flat, 2)), float(np.percentile(flat, 98))
    ww = max(p98 - p2, 1.0)
    wc = (p2 + p98) / 2.0
    return wc, ww


def array_to_pil(
    array: np.ndarray, window_center: float, window_width: float
) -> Image.Image | None:
    """Convert a 2-D array to an 8-bit grayscale PIL image via linear window/level.

    Mapping: ``out = clip((val - (wc - ww/2)) / ww * 255, 0, 255)``. Returns the
    image, or ``None`` on failure.
    """
    try:
        lo = window_center - window_width / 2.0
        scale = 255.0 / max(window_width, 1e-6)
        mapped = (array - lo) * scale  # array is already float
        np.clip(mapped, 0.0, 255.0, out=mapped)
        uint8_arr = mapped.astype(np.uint8)
        return Image.fromarray(uint8_arr, mode="L")
    except Exception as exc:
        print_redacted(f"[mpr_view_math] array_to_pil failed: {exc}")
        return None
