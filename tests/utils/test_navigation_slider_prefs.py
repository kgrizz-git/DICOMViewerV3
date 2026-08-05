"""Tests for navigation_slider_prefs: normalizers for placement and directions."""

from __future__ import annotations

from utils.navigation_slider_prefs import (
    normalize_slider_direction,
    normalize_slider_placement,
)


def test_normalize_slider_placement_valid() -> None:
    for val in ("bottom", "top", "left", "right"):
        assert normalize_slider_placement(val) == val


def test_normalize_slider_placement_normalization() -> None:
    assert normalize_slider_placement("  Bottom  ") == "bottom"
    assert normalize_slider_placement("TOP") == "top"
    assert normalize_slider_placement("lEfT") == "left"


def test_normalize_slider_placement_invalid_fallback() -> None:
    assert normalize_slider_placement("invalid") == "bottom"
    assert normalize_slider_placement("") == "bottom"
    assert normalize_slider_placement(None) == "bottom"


def test_normalize_slider_direction_valid() -> None:
    for val in ("first_at_start", "first_at_end"):
        assert normalize_slider_direction(val) == val


def test_normalize_slider_direction_normalization_and_fallback() -> None:
    assert normalize_slider_direction("  First_At_Start  ") == "first_at_start"
    assert normalize_slider_direction("FIRST_AT_END") == "first_at_end"
    assert normalize_slider_direction("invalid") == "first_at_start"
    assert normalize_slider_direction("") == "first_at_start"
    assert normalize_slider_direction(None) == "first_at_start"
