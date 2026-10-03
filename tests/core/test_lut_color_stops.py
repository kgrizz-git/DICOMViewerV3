"""Phase 4b color stops: validation and sampling to the shared (256, 3) table."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from core.lut_color_stops import normalize_color_stops, sample_color_stops
from core.lut_engine import LookUpTable, apply_lut_to_uint8


def test_stops_are_sorted() -> None:
    stops = normalize_color_stops([(1.0, (255, 255, 255)), (0.0, (0, 0, 0))])
    assert stops == ((0.0, (0, 0, 0)), (1.0, (255, 255, 255)))


@pytest.mark.parametrize(
    "stops",
    [
        [(0.0, (0, 0, 0))],
        [(0.0, (0, 0, 0)), (0.0, (1, 1, 1))],
        [(0.0, (0, 0, 0)), (1.5, (1, 1, 1))],
        [(0.0, (0, 0, 0)), (1.0, (256, 0, 0))],
        [(0.0, (0, 0, 0)), (1.0, (1.5, 0, 0))],
        [(0.0, (0, 0)), (1.0, (0, 0, 0))],
        [(float("nan"), (0, 0, 0)), (1.0, (0, 0, 0))],
    ],
)
def test_malformed_stops_are_rejected(stops) -> None:
    with pytest.raises(ValueError):
        normalize_color_stops(stops)


def test_linear_two_stop_map_matches_the_gray_ramp() -> None:
    table = sample_color_stops(normalize_color_stops([(0.0, (0, 0, 0)), (1.0, (255, 255, 255))]))
    assert table.shape == (256, 3)
    assert table.dtype == np.uint8
    assert np.array_equal(table[:, 0], np.arange(256, dtype=np.uint8))
    assert not table.flags.writeable


def test_step_holds_each_color_until_the_next_stop() -> None:
    stops = normalize_color_stops([(0.0, (10, 0, 0)), (0.5, (0, 20, 0)), (1.0, (0, 0, 30))])
    table = sample_color_stops(stops, "step")
    assert tuple(table[0]) == (10, 0, 0)
    assert tuple(table[127]) == (10, 0, 0)
    assert tuple(table[128]) == (0, 20, 0)
    assert tuple(table[254]) == (0, 20, 0)
    assert tuple(table[255]) == (0, 0, 30)


def test_colors_hold_outside_the_first_and_last_stop() -> None:
    stops = normalize_color_stops([(0.25, (100, 0, 0)), (0.75, (0, 0, 100))])
    table = sample_color_stops(stops)
    assert tuple(table[0]) == (100, 0, 0)
    assert tuple(table[255]) == (0, 0, 100)


def test_lut_with_stops_drives_the_display_path() -> None:
    lut = LookUpTable(
        name="RG",
        lut_type="colormap",
        source="custom",
        color_stops=((0.0, (255, 0, 0)), (1.0, (0, 255, 0))),
    )
    image = np.array([[0, 255]], dtype=np.uint8)
    out = apply_lut_to_uint8(image, lut)
    assert out.shape == (1, 2, 3)
    assert tuple(out[0, 0]) == (255, 0, 0)
    assert tuple(out[0, 1]) == (0, 255, 0)


def test_stops_require_a_colormap_and_affect_equality() -> None:
    with pytest.raises(ValueError, match="require lut_type"):
        LookUpTable(name="x", color_stops=((0.0, (0, 0, 0)), (1.0, (1, 1, 1))))
    base: dict[str, Any] = {"name": "m", "lut_type": "colormap", "source": "custom"}
    a = LookUpTable(**base, color_stops=((0.0, (0, 0, 0)), (1.0, (9, 9, 9))))
    b = LookUpTable(**base, color_stops=((0.0, (0, 0, 0)), (1.0, (9, 9, 9))))
    c = LookUpTable(**base, color_stops=((0.0, (0, 0, 0)), (1.0, (9, 9, 9))), color_interpolation="step")
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
