"""
Unit tests for core.mpr_combine_slice_count.normalize_mpr_combine_slice_count.
"""

import pytest

from core.mpr_combine_slice_count import normalize_mpr_combine_slice_count


@pytest.mark.parametrize(
    "requested, expected",
    [
        (2, 2),
        (3, 3),
        (4, 4),
        (6, 6),
        (8, 8),
        (1, 2),  # clamped up to min 2, exact match
        (0, 2),  # clamped up to min 2
        (-5, 2),  # clamped up to min 2
        (9, 8),  # clamped down to max 8
        (100, 8),  # clamped down to max 8
        (5, 4),  # nearest of {4, 6} -- ties/closer go to 4 (d=1 vs d=1: first wins)
        (7, 6),  # nearest of {6, 8} -- d=1 vs d=1: 6 found first
    ],
)
def test_normalize_mpr_combine_slice_count(requested, expected):
    assert normalize_mpr_combine_slice_count(requested) == expected


def test_accepts_non_int_numeric_input():
    # int(3.7) truncates to 3 before clamping/matching, giving an exact hit.
    assert normalize_mpr_combine_slice_count(3.7) == 3
