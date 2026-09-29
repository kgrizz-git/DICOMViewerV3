"""
Tests for univariate LUT curves and freehand Ramer–Douglas–Peucker.

Linear, Fritsch–Carlson, and Catmull–Rom are all ``y = f(x)``. Only
Catmull–Rom is clamped, and only to ``[0, 1]``. Freehand epsilon is in the
unit square; ``1/sqrt(2)`` (about 0.707) is already degenerate.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from core.lut_curve import (
    DIAGONAL_EPSILON_LIMIT,
    FREEHAND_EPSILON,
    _perpendicular_distance,
    evaluate_univariate,
    simplify_freehand,
)
from core.lut_engine import Interpolation, LookUpTable, apply_lut_to_uint8, evaluate_lut

_NON_MONOTONE = ((0.0, 0.2), (0.5, 0.9), (1.0, 0.3))
_SPIKE = ((0.0, 0.0), (0.25, 0.0), (0.5, 1.0), (0.75, 0.0), (1.0, 0.0))


def _curve(points: tuple[tuple[float, float], ...], interpolation: Interpolation) -> LookUpTable:
    """Build a custom curve LUT. Built-in markers are not involved."""
    return LookUpTable(
        name="curve",
        source="custom",
        control_points=points,
        interpolation=interpolation,
    )


def _s_curve() -> np.ndarray:
    """81-point logistic S-curve. Max perpendicular distance to the diagonal is ~0.104.

    Steepness 8 keeps 6 points at epsilon 0.02 and 4 at 0.05.
    """
    x = np.linspace(0.0, 1.0, 81)
    k = 8.0
    logistic = 1.0 / (1.0 + np.exp(-k * (x - 0.5)))
    start = 1.0 / (1.0 + np.exp(k * 0.5))
    end = 1.0 / (1.0 + np.exp(-k * 0.5))
    y = (logistic - start) / (end - start)
    return np.column_stack((x, y))


def test_piecewise_linear_is_exact_between_breakpoints() -> None:
    """Samples on a linear span hit the straight line, not a smoothed one."""
    lut = _curve(((0.0, 0.0), (0.5, 1.0), (1.0, 0.0)), "linear")
    samples = evaluate_lut(lut, np.array([0.0, 0.25, 0.5, 0.75, 1.0]))
    np.testing.assert_allclose(samples, [0.0, 0.5, 1.0, 0.5, 0.0])


@pytest.mark.parametrize("interpolation", ["linear", "monotone_cubic", "catmull_rom"])
def test_every_mode_passes_through_control_points(interpolation: Interpolation) -> None:
    """Each mode is a univariate spline, so every dragged breakpoint stays on the curve."""
    lut = _curve(_NON_MONOTONE, interpolation)
    xs = np.array([point[0] for point in _NON_MONOTONE])
    ys = np.array([point[1] for point in _NON_MONOTONE])
    np.testing.assert_allclose(evaluate_lut(lut, xs), ys, atol=1e-12)


def test_fritsch_carlson_stays_inside_the_control_point_range() -> None:
    """No new extrema. Clamping to the first/last span [0.2, 0.3] would be wrong."""
    lut = _curve(_NON_MONOTONE, "monotone_cubic")
    samples = evaluate_lut(lut, np.linspace(0.0, 1.0, 1001))
    assert samples.min() >= 0.2 - 1e-12
    assert samples.max() <= 0.9 + 1e-12
    assert samples.max() > 0.5


def test_catmull_rom_overshoots_then_clamps_without_leaving_control_points() -> None:
    """The spike reaches about -0.074. Clamping to [0, 1] still hits every knot."""
    lut = _curve(_SPIKE, "catmull_rom")
    xs = np.array([0.0, 0.25, 0.5, 0.75, 1.0])
    ys = np.array([0.0, 0.0, 1.0, 0.0, 0.0])
    unclamped = evaluate_univariate(xs, ys, np.array([1.0 / 6.0]), "catmull_rom")
    assert unclamped[0] == pytest.approx(-2.0 / 27.0)
    clamped = evaluate_lut(lut, np.linspace(0.0, 1.0, 501))
    assert clamped.min() >= 0.0
    assert clamped.max() <= 1.0
    np.testing.assert_allclose(evaluate_lut(lut, xs), ys, atol=1e-12)


def test_catmull_rom_non_monotone_overshoot_is_about_0_9004() -> None:
    """The interior peak is allowed to pass 0.9. Endpoint-span clamping would flatten it."""
    xs = np.array([0.0, 0.5, 1.0])
    ys = np.array([0.2, 0.9, 0.3])
    samples = evaluate_univariate(xs, ys, np.linspace(0.0, 1.0, 2001), "catmull_rom")
    assert samples.max() == pytest.approx(0.900485, abs=1e-4)
    clamped = evaluate_lut(_curve(_NON_MONOTONE, "catmull_rom"), np.linspace(0.0, 1.0, 2001))
    assert clamped.max() <= 1.0
    assert evaluate_lut(_curve(_NON_MONOTONE, "catmull_rom"), np.array([0.5]))[0] == pytest.approx(0.9)


def test_uint8_sampling_is_deterministic_and_in_range() -> None:
    """The 256-entry display table does not depend on call order."""
    lut = _curve(_SPIKE, "catmull_rom")
    ramp = np.arange(256, dtype=np.uint8).reshape(16, 16)
    first = apply_lut_to_uint8(ramp, lut)
    second = apply_lut_to_uint8(ramp, lut)
    np.testing.assert_array_equal(first, second)
    assert first.dtype == np.uint8
    assert int(first.min()) >= 0
    assert int(first.max()) <= 255


def test_vertical_bump_threshold_and_small_sine_are_dropped() -> None:
    """A +0.03 bump survives. A +0.02 bump and a 1.5% sine do not."""
    kept = simplify_freehand(np.array([[0.0, 0.0], [0.5, 0.53], [1.0, 1.0]]))
    dropped = simplify_freehand(np.array([[0.0, 0.0], [0.5, 0.52], [1.0, 1.0]]))
    assert len(kept) == 3
    assert kept[1, 1] == pytest.approx(0.53)
    assert len(dropped) == 2
    x = np.linspace(0.0, 1.0, 81)
    sine = np.column_stack((x, x + 0.015 * np.sin(2.0 * np.pi * x)))
    assert len(simplify_freehand(sine)) == 2


def test_zero_length_chord_uses_distance_to_endpoint() -> None:
    """A collapsed chord has no line direction but still has point distances."""
    endpoint = np.array([0.25, 0.5])
    points = np.array([[0.25, 0.5], [0.25, 0.8], [0.65, 0.8]])
    distances = _perpendicular_distance(points, endpoint, endpoint.copy())
    np.testing.assert_allclose(distances, [0.0, 0.3, 0.5])


def test_s_curve_survives_and_large_epsilon_collapses() -> None:
    """More than two points must remain at 0.02, or freehand is a silent no-op.

    The same stroke keeps 6 points at 0.02 and 4 at 0.05. epsilon at or above
    ``1/sqrt(2)`` collapses it to the pinned endpoints, including 0.707, 1,
    1.414, and 2.
    """
    stroke = _s_curve()
    perpendicular = np.abs(stroke[:, 0] - stroke[:, 1]) / math.sqrt(2.0)
    assert perpendicular.max() == pytest.approx(0.104, abs=1e-3)
    assert len(simplify_freehand(stroke, FREEHAND_EPSILON)) == 6
    assert len(simplify_freehand(stroke, 0.05)) == 4
    for epsilon in (DIAGONAL_EPSILON_LIMIT, 0.707, 1.0, math.sqrt(2.0), 2.0):
        assert len(simplify_freehand(stroke, epsilon)) == 2


def test_freehand_is_deterministic_idempotent_and_pins_endpoints() -> None:
    """RDP keeps the same points on a second run, and the ends are (0, 0) and (1, 1)."""
    raw = np.array([[0.2, 0.4], [0.3, 0.9], [0.6, 0.1], [0.8, 0.7]])
    once = simplify_freehand(raw)
    twice = simplify_freehand(once)
    again = simplify_freehand(raw)
    np.testing.assert_allclose(once, again)
    np.testing.assert_allclose(once, twice)
    np.testing.assert_allclose(once[0], [0.0, 0.0])
    np.testing.assert_allclose(once[-1], [1.0, 1.0])
    assert len(once) > 2
