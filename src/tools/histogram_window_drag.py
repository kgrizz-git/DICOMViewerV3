"""
Window/level from dragging an edge of the composed curve on the histogram.

The composed curve ``LUT(P_inv(uint8(WL(x))))`` is flat outside the window, so
its two bends sit at the window's low and high edges. Dragging one bend moves
that edge and leaves the other where it was. Center and width follow from the
two edges.

Inputs:
    - Current window center/width, the grabbed edge, the pointer's data x

Outputs:
    - The edge under the pointer, and the replacement (center, width)

Requirements:
    - None beyond the standard library
"""

from __future__ import annotations

from typing import Literal

Edge = Literal["low", "high"]

#: Narrowest window a drag can produce, in stored or rescaled units. The W/L
#: controls reject a zero width, and a crossing drag would invert the window.
MIN_WIDTH = 1.0


def window_edges(center: float, width: float) -> tuple[float, float]:
    """Low and high edges of the window."""
    half = width / 2.0
    return center - half, center + half


def edge_near(
    pointer_px: float,
    low_px: float,
    high_px: float,
    tolerance_px: float = 8.0,
) -> Edge | None:
    """The edge within ``tolerance_px`` screen pixels of the pointer, nearest first."""
    low_gap = abs(pointer_px - low_px)
    high_gap = abs(pointer_px - high_px)
    if min(low_gap, high_gap) > tolerance_px:
        return None
    return "low" if low_gap <= high_gap else "high"


def dragged_window(edge: Edge, x: float, center: float, width: float) -> tuple[float, float]:
    """Move ``edge`` to ``x`` and return the new (center, width).

    The other edge stays fixed. The moving edge cannot cross it: the result is
    at least ``MIN_WIDTH`` wide.
    """
    low, high = window_edges(center, width)
    if edge == "low":
        low = min(x, high - MIN_WIDTH)
    else:
        high = max(x, low + MIN_WIDTH)
    return (low + high) / 2.0, high - low
