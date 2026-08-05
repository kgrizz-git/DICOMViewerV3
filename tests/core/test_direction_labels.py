"""
Tests for ``core.direction_labels`` — LPS direction labels from IOP.

Uses numpy only; no Qt.
"""

from __future__ import annotations

import math

import numpy as np

from core.direction_labels import (
    DEFAULT_SIGNIFICANCE_THRESHOLD,
    compute_direction_labels_from_iop,
    label_lps_direction_vector,
)


def test_compute_direction_labels_cardinal_lps() -> None:
    """Row +L, col +P (typical axial-style IOP in LPS)."""
    # Pure row along +L, col along +P
    iop = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    d = compute_direction_labels_from_iop(iop)
    assert d is not None
    assert d["right"] == "L"
    assert d["left"] == "R"
    assert d["bottom"] == "P"
    assert d["top"] == "A"


def test_compute_direction_labels_oblique_row_shows_two_letters() -> None:
    """Row bisects L and A so left/right edges get two significant LPS components."""
    s = 1.0 / math.sqrt(2.0)
    iop = [s, -s, 0.0, 0.0, 0.0, 1.0]
    d = compute_direction_labels_from_iop(iop)
    assert d is not None
    # -row = (-s, s, 0): dominant toward R and P
    assert d["left"] == "R P"
    assert d["right"] == "L A"
    assert d["top"] == "I"
    assert d["bottom"] == "S"


def test_compute_direction_labels_invalid_iop() -> None:
    assert compute_direction_labels_from_iop(None) is None
    assert compute_direction_labels_from_iop([]) is None
    assert compute_direction_labels_from_iop([1, 2, 3]) is None


def test_label_fallback_when_all_below_threshold() -> None:
    """If no |vk| >= T, fall back to single dominant letter."""
    # Pure +L; threshold above 1.0 yields no 'significant' axis → dominant path.
    lab = label_lps_direction_vector(
        np.array([1.0, 0.0, 0.0], dtype=np.float64),
        threshold=1.01,
    )
    assert lab == "L"


def test_threshold_constant() -> None:
    assert DEFAULT_SIGNIFICANCE_THRESHOLD == 0.5
