"""
Unit tests for slice-sync group color palette and view→group lookup.

No Qt required: validates stable colors and indexing contract with config docs.
"""

from __future__ import annotations

from utils.slice_sync_group_palette import (
    slice_sync_group_rgb,
    view_index_to_group_index,
)


def test_slice_sync_group_rgb_cycles_and_stable() -> None:
    assert slice_sync_group_rgb(0) == (211, 47, 47)
    assert slice_sync_group_rgb(1) == (25, 118, 210)
    # Large index wraps palette
    assert slice_sync_group_rgb(100) == slice_sync_group_rgb(100 % 8)


def test_slice_sync_group_rgb_negative_clamped_to_zero_bucket() -> None:
    assert slice_sync_group_rgb(-1) == slice_sync_group_rgb(0)


def test_view_index_to_group_index() -> None:
    groups = [[0, 2], [1, 3]]
    assert view_index_to_group_index(groups, 0) == 0
    assert view_index_to_group_index(groups, 2) == 0
    assert view_index_to_group_index(groups, 1) == 1
    assert view_index_to_group_index(groups, 3) == 1
    assert view_index_to_group_index(groups, 99) is None


def test_view_index_to_group_index_first_match_wins() -> None:
    groups = [[0, 1], [1, 2]]  # invalid overlap; first group wins for view 1
    assert view_index_to_group_index(groups, 1) == 0
