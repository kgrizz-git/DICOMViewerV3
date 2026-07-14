"""Tests for the perceptual volume opacity model."""

from __future__ import annotations

import itertools

import pytest

from core.volume_opacity_model import (
    OPACITY_GAMMA,
    RESPONSE_GAMMA_MAX,
    RESPONSE_GAMMA_MIN,
    RESPONSE_NEUTRAL,
    SLIDER_MAX,
    format_opacity_percent,
    opacity_to_percent,
    opacity_to_slider,
    percent_to_opacity,
    response_to_gamma,
    slider_to_opacity,
)


def test_endpoints_map_exactly() -> None:
    assert slider_to_opacity(0) == 0.0
    assert slider_to_opacity(SLIDER_MAX) == pytest.approx(1.0)
    assert opacity_to_slider(0.0) == 0
    assert opacity_to_slider(1.0) == SLIDER_MAX


def test_slider_to_opacity_is_monotonic() -> None:
    prev = -1.0
    for v in range(0, SLIDER_MAX + 1, 25):
        cur = slider_to_opacity(v)
        assert cur >= prev
        prev = cur


def test_low_opacity_range_gets_more_slider_travel() -> None:
    # The whole 0-10% resolved-opacity band should occupy a large share of the
    # slider (the core requirement: fine control where faint structures live).
    slider_at_10pct = opacity_to_slider(0.10)
    assert slider_at_10pct > SLIDER_MAX * 0.30
    # And 5% vs 6% must be distinguishable by more than one slider step.
    assert opacity_to_slider(0.06) - opacity_to_slider(0.05) >= 2


def test_high_opacity_range_is_compressed() -> None:
    # 30%-75% should occupy less slider travel than 0%-10% does, confirming the
    # high range no longer wastes most of the travel.
    low_band = opacity_to_slider(0.10) - opacity_to_slider(0.0)
    high_band = opacity_to_slider(0.75) - opacity_to_slider(0.30)
    assert high_band < low_band


def test_round_trip_slider_opacity_slider() -> None:
    for v in range(0, SLIDER_MAX + 1, 50):
        assert abs(opacity_to_slider(slider_to_opacity(v)) - v) <= 1


def test_percent_helpers_clamp() -> None:
    assert percent_to_opacity(-5) == 0.0
    assert percent_to_opacity(150) == 1.0
    assert opacity_to_percent(0.5) == pytest.approx(50.0)


def test_format_opacity_percent_precision() -> None:
    assert format_opacity_percent(0.055) == "5.5%"
    assert format_opacity_percent(0.5) == "50%"


def test_gamma_is_greater_than_one() -> None:
    # The perceptual redistribution depends on gamma > 1.
    assert OPACITY_GAMMA > 1.0


# --- opacity-response (contrast-depth) gamma --------------------------------

def test_response_gamma_neutral_is_one():
    assert response_to_gamma(RESPONSE_NEUTRAL) == pytest.approx(1.0)


def test_response_gamma_endpoints():
    assert response_to_gamma(0) == pytest.approx(RESPONSE_GAMMA_MIN)
    assert response_to_gamma(100) == pytest.approx(RESPONSE_GAMMA_MAX)


def test_response_gamma_clamps_out_of_range():
    assert response_to_gamma(-50) == pytest.approx(RESPONSE_GAMMA_MIN)
    assert response_to_gamma(9999) == pytest.approx(RESPONSE_GAMMA_MAX)


def test_response_gamma_monotonic_nondecreasing():
    vals = [response_to_gamma(v) for v in range(0, 101, 5)]
    assert all(b >= a for a, b in itertools.pairwise(vals))
    # below neutral < 1.0 < above neutral
    assert response_to_gamma(25) < 1.0 < response_to_gamma(75)
