"""
Runtime slab combine for MPR views — pure numpy, no GUI dependency.

Extracted from ``mpr_controller`` so core modules can import this
without pulling in GUI dialog imports.
"""

from __future__ import annotations

import numpy as np


def apply_mpr_stack_combine(
    stack: list[np.ndarray],
    slice_index: int,
    *,
    enabled: bool,
    mode: str,
    n_planes: int,
) -> np.ndarray:
    """
    Return one 2-D slice array, optionally averaged/max/min over *n_planes*
    neighboring planes in *stack* (same algorithm as legacy builder slab).

    Args:
        stack:        Uncombined MPR planes (float32 2-D arrays).
        slice_index:  Center plane index.
        enabled:      If False, return stack[slice_index] unchanged.
        mode:         ``aip`` | ``mip`` | ``minip``.
        n_planes:     Number of planes in the slab window.
    """
    n_slices = len(stack)
    if not enabled or n_slices == 0:
        return stack[slice_index]
    n_planes = max(1, int(n_planes))
    mode_l = (mode or "aip").lower()
    i = slice_index
    start = i - (n_planes // 2)
    end = start + n_planes - 1
    if start < 0:
        start = 0
        end = min(n_slices - 1, n_planes - 1)
    if end >= n_slices:
        end = n_slices - 1
        start = max(0, end - (n_planes - 1))
    window = stack[start : end + 1]
    if len(window) == 1:
        return window[0]
    arr = np.stack(window, axis=0)
    if mode_l == "mip":
        out = np.max(arr, axis=0)
    elif mode_l == "minip":
        out = np.min(arr, axis=0)
    else:
        out = np.mean(arr, axis=0)
    return out.astype(np.float32)
