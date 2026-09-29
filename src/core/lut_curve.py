"""
Univariate LUT curves and freehand simplification.

Control-point curves are functions of normalized x (``y = f(x)``), never
parametric paths through the ``(x, y)`` pairs. Linear and Fritsch–Carlson
(monotone cubic) pass through every control point and do not need a range
clamp. Catmull–Rom also passes through every control point but may overshoot,
so callers that feed the display path clamp those samples to ``[0, 1]``.

Freehand strokes are simplified with Ramer–Douglas–Peucker in the unit square.
``epsilon`` is a fraction of that square. The first chord is the diagonal
between the pinned endpoints ``(0, 0)`` and ``(1, 1)``, and the farthest a
point can sit from that chord is ``1/sqrt(2)`` (about 0.707), not ``sqrt(2)``.

Inputs:
    - Control-point x/y arrays in ``[0, 1]``, query x, interpolation mode
    - Freehand ``(N, 2)`` strokes in normalized output-value space

Outputs:
    - Interpolated y values
    - Simplified ``(M, 2)`` strokes with endpoints pinned to ``(0, 0)`` and ``(1, 1)``

Requirements:
    - numpy
    - scipy (Fritsch–Carlson / PCHIP)
"""

from __future__ import annotations

import math

import numpy as np
from scipy.interpolate import (  # pyright: ignore[reportMissingTypeStubs]
    PchipInterpolator,
)

Interpolation = str

LINEAR = "linear"
MONOTONE_CUBIC = "monotone_cubic"
CATMULL_ROM = "catmull_rom"
INTERPOLATION_MODES = (LINEAR, MONOTONE_CUBIC, CATMULL_ROM)

# Starting freehand tolerance in unit-square coordinates. Perpendicular
# distance, so a vertical wiggle must be about 0.02 * sqrt(2) to survive.
FREEHAND_EPSILON = 0.02

# Distance from a unit-square corner to the diagonal. epsilon at or above
# this value collapses every stroke to its two pinned endpoints.
DIAGONAL_EPSILON_LIMIT = 1.0 / math.sqrt(2)


def evaluate_univariate(
    x_control: np.ndarray,
    y_control: np.ndarray,
    x_query: np.ndarray,
    interpolation: str,
) -> np.ndarray:
    """Evaluate ``y = f(x)`` at ``x_query``.

    ``x_control`` must be strictly increasing. Values outside the control
    span hold the nearest endpoint y. This function does not clamp
    Catmull–Rom overshoot; ``clamp_unit_interval`` does that for the
    display path only.
    """
    xs = np.asarray(x_control, dtype=np.float64)
    ys = np.asarray(y_control, dtype=np.float64)
    query = np.asarray(x_query, dtype=np.float64)
    if interpolation == LINEAR:
        return np.interp(query, xs, ys)
    if interpolation == MONOTONE_CUBIC:
        return _monotone_cubic(xs, ys, query)
    if interpolation == CATMULL_ROM:
        return _catmull_rom(xs, ys, query)
    raise ValueError(
        f"interpolation must be one of {INTERPOLATION_MODES}, got {interpolation!r}"
    )


def clamp_unit_interval(values: np.ndarray) -> np.ndarray:
    """Return ``values`` clipped to ``[0, 1]`` (Catmull–Rom display samples)."""
    return np.clip(np.asarray(values, dtype=np.float64), 0.0, 1.0)


def simplify_freehand(
    points: np.ndarray,
    epsilon: float = FREEHAND_EPSILON,
) -> np.ndarray:
    """Simplify a freehand stroke with Ramer–Douglas–Peucker.

    Endpoints are pinned to ``(0, 0)`` and ``(1, 1)`` before simplification
    and are never removed. ``epsilon`` is the maximum perpendicular distance,
    in unit-square coordinates, that a removed point may have from the chord
    that replaces it. The result is deterministic and idempotent.
    """
    if not math.isfinite(epsilon) or epsilon < 0.0:
        raise ValueError(f"epsilon must be a finite value >= 0, got {epsilon!r}")
    stroke = _as_stroke(points)
    if stroke.shape[0] == 0:
        return np.array([[0.0, 0.0], [1.0, 1.0]], dtype=np.float64)
    if stroke.shape[0] == 1:
        return np.array([[0.0, 0.0], [1.0, 1.0]], dtype=np.float64)
    pinned = stroke.copy()
    pinned[0] = (0.0, 0.0)
    pinned[-1] = (1.0, 1.0)
    return _rdp(pinned, epsilon)


def _as_stroke(points: np.ndarray) -> np.ndarray:
    """Return a finite ``(N, 2)`` float64 copy of a freehand stroke."""
    stroke = np.asarray(points, dtype=np.float64)
    if stroke.ndim != 2 or stroke.shape[1] != 2:
        raise ValueError(f"freehand points must have shape (N, 2), got {stroke.shape}")
    if stroke.size and not np.isfinite(stroke).all():
        raise ValueError("freehand points must be finite")
    return stroke


def _monotone_cubic(
    xs: np.ndarray,
    ys: np.ndarray,
    query: np.ndarray,
) -> np.ndarray:
    """Fritsch–Carlson monotone cubic via SciPy PCHIP. Two-point spans are linear."""
    if xs.shape[0] < 3:
        return np.interp(query, xs, ys)
    spline = PchipInterpolator(xs, ys, extrapolate=False)
    sampled = np.asarray(spline(query), dtype=np.float64)
    sampled = np.where(query < xs[0], ys[0], sampled)
    return np.where(query > xs[-1], ys[-1], sampled)


def _catmull_rom(xs: np.ndarray, ys: np.ndarray, query: np.ndarray) -> np.ndarray:
    """Univariate Catmull–Rom: cubic Hermite with central-difference tangents."""
    tangents = _catmull_tangents(xs, ys)
    return _hermite(xs, ys, tangents, query)


def _catmull_tangents(xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    """Endpoint one-sided slopes and interior ``(y[i+1] - y[i-1]) / (x[i+1] - x[i-1])``."""
    count = xs.shape[0]
    slopes = np.empty(count, dtype=np.float64)
    slopes[0] = (ys[1] - ys[0]) / (xs[1] - xs[0])
    slopes[-1] = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
    for index in range(1, count - 1):
        slopes[index] = (ys[index + 1] - ys[index - 1]) / (xs[index + 1] - xs[index - 1])
    return slopes


def _hermite(
    xs: np.ndarray,
    ys: np.ndarray,
    slopes: np.ndarray,
    query: np.ndarray,
) -> np.ndarray:
    """Evaluate a cubic Hermite spline. Queries outside the span hold the endpoint."""
    flat = query.reshape(-1)
    out = np.empty(flat.shape, dtype=np.float64)
    inside = (flat >= xs[0]) & (flat <= xs[-1])
    out[~inside & (flat < xs[0])] = ys[0]
    out[~inside & (flat > xs[-1])] = ys[-1]
    if not np.any(inside):
        return out.reshape(query.shape)
    out[inside] = _hermite_inside(xs, ys, slopes, flat[inside])
    return out.reshape(query.shape)


def _hermite_inside(
    xs: np.ndarray,
    ys: np.ndarray,
    slopes: np.ndarray,
    query: np.ndarray,
) -> np.ndarray:
    """Cubic Hermite on queries already known to lie inside ``[xs[0], xs[-1]]``."""
    interval = np.searchsorted(xs, query, side="right") - 1
    interval = np.clip(interval, 0, xs.shape[0] - 2)
    x0 = xs[interval]
    span = xs[interval + 1] - x0
    t = (query - x0) / span
    t2 = t * t
    t3 = t2 * t
    h00 = 2.0 * t3 - 3.0 * t2 + 1.0
    h10 = t3 - 2.0 * t2 + t
    h01 = -2.0 * t3 + 3.0 * t2
    h11 = t3 - t2
    return (
        h00 * ys[interval]
        + h10 * span * slopes[interval]
        + h01 * ys[interval + 1]
        + h11 * span * slopes[interval + 1]
    )


def _rdp(points: np.ndarray, epsilon: float) -> np.ndarray:
    """Iterative Ramer–Douglas–Peucker. Keeps a point only when distance > epsilon."""
    count = points.shape[0]
    if count < 3:
        return points.copy()
    keep = np.zeros(count, dtype=bool)
    keep[0] = True
    keep[-1] = True
    stack: list[tuple[int, int]] = [(0, count - 1)]
    while stack:
        _keep_farthest(points, epsilon, keep, stack)
    return points[keep]


def _keep_farthest(
    points: np.ndarray,
    epsilon: float,
    keep: np.ndarray,
    stack: list[tuple[int, int]],
) -> None:
    """Pop one chord and, if a point exceeds ``epsilon``, keep it and split."""
    start, end = stack.pop()
    if end <= start + 1:
        return
    distances = _perpendicular_distance(points[start + 1 : end], points[start], points[end])
    offset = int(np.argmax(distances))
    if distances[offset] <= epsilon:
        return
    index = start + 1 + offset
    keep[index] = True
    stack.append((start, index))
    stack.append((index, end))


def _perpendicular_distance(
    points: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
) -> np.ndarray:
    """Perpendicular distance from each point to the chord ``start``–``end``."""
    delta = end - start
    length = float(np.hypot(delta[0], delta[1]))
    if length <= 0.0:
        return np.hypot(points[:, 0] - start[0], points[:, 1] - start[1])
    cross = delta[1] * (points[:, 0] - start[0]) - delta[0] * (points[:, 1] - start[1])
    return np.abs(cross) / length
