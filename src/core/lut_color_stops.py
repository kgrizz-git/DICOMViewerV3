"""
Color stops for an editable colormap LUT.

A stop is ``(x, (r, g, b))`` with ``x`` in ``[0, 1]`` and 8-bit channels. Stops
sample to the same ``(256, 3)`` uint8 table every built-in colormap uses, at
``x = i / 255``, so ``apply_lut_to_uint8`` needs no special case. ``linear``
blends each channel between the neighboring stops in RGB; ``step`` holds a
stop's color until the next stop.

Inputs:
    - A sequence of ``(x, (r, g, b))`` stops and an interpolation mode

Outputs:
    - A normalized stop tuple, and a read-only ``(256, 3)`` uint8 table

Requirements:
    - numpy
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

import numpy as np

ColorInterpolation = Literal["linear", "step"]
ColorStop = tuple[float, tuple[int, int, int]]
COLOR_INTERPOLATIONS: tuple[str, ...] = ("linear", "step")


def normalize_color_stops(stops: Sequence[Sequence[object]]) -> tuple[ColorStop, ...]:
    """Sort and validate stops. Raises ``ValueError`` on a malformed stop.

    At least two stops are required, ``x`` values must be finite, inside
    ``[0, 1]`` and distinct, and each channel must be an integer in ``0..255``.
    """
    normalized: list[ColorStop] = []
    for stop in stops:
        if len(stop) != 2:
            raise ValueError("a color stop is (x, (r, g, b))")
        x_value, color = stop
        if isinstance(x_value, bool) or not isinstance(x_value, (int, float, np.floating, np.integer)):
            raise ValueError(f"color stop x must be a number, got {x_value!r}")
        x = float(x_value)
        if not math.isfinite(x) or not 0.0 <= x <= 1.0:
            raise ValueError(f"color stop x must be in [0, 1], got {x_value!r}")
        normalized.append((x, _channels(color)))
    if len(normalized) < 2:
        raise ValueError("a colormap needs at least two color stops")
    normalized.sort(key=lambda item: item[0])
    xs = [x for x, _rgb in normalized]
    if len(set(xs)) != len(xs):
        raise ValueError("color stops must have distinct x values")
    return tuple(normalized)


def sample_color_stops(
    stops: Sequence[ColorStop], interpolation: ColorInterpolation = "linear"
) -> np.ndarray:
    """Sample normalized stops at ``i / 255``. Outside the first/last stop, hold its color."""
    if interpolation not in COLOR_INTERPOLATIONS:
        raise ValueError(f"unknown color interpolation {interpolation!r}")
    xs = np.array([x for x, _rgb in stops], dtype=np.float64)
    rgb = np.array([color for _x, color in stops], dtype=np.float64)
    query = np.arange(256, dtype=np.float64) / 255.0
    if interpolation == "step":
        index = np.clip(np.searchsorted(xs, query, side="right") - 1, 0, len(xs) - 1)
        table = rgb[index]
    else:
        table = np.column_stack([np.interp(query, xs, rgb[:, c]) for c in range(3)])
    sampled = np.clip(np.rint(table), 0, 255).astype(np.uint8)
    sampled.setflags(write=False)
    return sampled


def _channels(color: object) -> tuple[int, int, int]:
    """Three integer channels in ``0..255``."""
    if not isinstance(color, Sequence) or isinstance(color, str) or len(color) != 3:
        raise ValueError("a color stop color is (r, g, b)")
    channels = []
    for value in color:
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
            raise ValueError(f"color channels must be integers, got {value!r}")
        if not 0 <= int(value) <= 255:
            raise ValueError(f"color channels must be in 0..255, got {value!r}")
        channels.append(int(value))
    return channels[0], channels[1], channels[2]
