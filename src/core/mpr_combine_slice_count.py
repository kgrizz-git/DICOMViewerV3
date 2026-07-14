"""
MPR combine-slice count normalization (UI allowed values).

Extracted from ``mpr_controller`` so ``gui.dialogs.mpr_dialog`` can import this
helper without depending on ``MprController`` (breaks a Pyright import cycle:
``mpr_controller`` ↔ ``mpr_dialog``).
"""

from __future__ import annotations

_ALLOWED_MPR_COMBINE_COUNTS = (2, 3, 4, 6, 8)


def normalize_mpr_combine_slice_count(n: int) -> int:
    """Map a requested plane count to the nearest allowed UI value (2–8)."""
    n = max(2, min(8, int(n)))
    best = 4
    best_d = 999
    for c in _ALLOWED_MPR_COMBINE_COUNTS:
        d = abs(c - n)
        if d < best_d:
            best_d = d
            best = c
    return best
