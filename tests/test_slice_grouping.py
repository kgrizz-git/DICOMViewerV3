"""
Unit tests for core.slice_grouping (grouping multi-frame datasets by original slice).

Uses plain ``SimpleNamespace`` stand-ins for datasets since these functions only
rely on ``hasattr``/``getattr`` for ``_original_dataset`` and ``_frame_index``,
not on pydicom-specific behavior.
"""

from __future__ import annotations

from types import SimpleNamespace

from core.slice_grouping import (
    get_first_frame_index_for_slice,
    get_frame_index_in_slice,
    get_slice_frame_count,
    get_slice_index_for_dataset,
    get_total_slices,
    group_datasets_by_slice,
)


def _build_series():
    """Two single-frame slices flanking one 2-frame multi-frame slice."""
    single1 = SimpleNamespace(name="single1")
    original_a = SimpleNamespace(name="original_a")
    # Constructed out of frame-index order to verify sort-by-frame-index behavior.
    frame_a1 = SimpleNamespace(_original_dataset=original_a, _frame_index=1)
    frame_a0 = SimpleNamespace(_original_dataset=original_a, _frame_index=0)
    single2 = SimpleNamespace(name="single2")
    datasets = [single1, frame_a1, frame_a0, single2]
    return datasets, single1, original_a, frame_a0, frame_a1, single2


class TestGroupDatasetsBySlice:
    def test_single_frame_datasets_map_to_themselves(self):
        single1 = SimpleNamespace(name="a")
        single2 = SimpleNamespace(name="b")
        groups = group_datasets_by_slice([single1, single2])
        assert groups == {id(single1): [single1], id(single2): [single2]}

    def test_frames_grouped_by_original_dataset_and_sorted(self):
        datasets, _, original_a, frame_a0, frame_a1, _ = _build_series()
        groups = group_datasets_by_slice(datasets)
        assert groups[id(original_a)] == [frame_a0, frame_a1]

    def test_mixed_series_produces_three_groups(self):
        datasets, single1, original_a, _, _, single2 = _build_series()
        groups = group_datasets_by_slice(datasets)
        assert len(groups) == 3
        assert set(groups.keys()) == {id(single1), id(original_a), id(single2)}

    def test_empty_input_returns_empty_dict(self):
        assert group_datasets_by_slice([]) == {}


class TestGetSliceIndexForDataset:
    def test_single_frame_indices_map_directly(self):
        datasets, *_ = _build_series()
        assert get_slice_index_for_dataset(datasets, 0) == 0
        assert get_slice_index_for_dataset(datasets, 3) == 2

    def test_frames_from_same_original_share_slice_index(self):
        datasets, *_ = _build_series()
        assert get_slice_index_for_dataset(datasets, 1) == 1
        assert get_slice_index_for_dataset(datasets, 2) == 1

    def test_out_of_range_index_returns_zero(self):
        datasets, *_ = _build_series()
        assert get_slice_index_for_dataset(datasets, -1) == 0
        assert get_slice_index_for_dataset(datasets, len(datasets)) == 0


class TestGetFrameIndexInSlice:
    def test_single_frame_dataset_returns_zero(self):
        datasets, *_ = _build_series()
        assert get_frame_index_in_slice(datasets, 0) == 0

    def test_frame_dataset_returns_its_frame_index(self):
        datasets, *_ = _build_series()
        # datasets[1] is frame_a1 (_frame_index=1), datasets[2] is frame_a0 (_frame_index=0)
        assert get_frame_index_in_slice(datasets, 1) == 1
        assert get_frame_index_in_slice(datasets, 2) == 0

    def test_out_of_range_index_returns_zero(self):
        datasets, *_ = _build_series()
        assert get_frame_index_in_slice(datasets, 99) == 0


class TestGetSliceFrameCount:
    def test_single_frame_slice_has_one_frame(self):
        datasets, *_ = _build_series()
        assert get_slice_frame_count(datasets, 0) == 1

    def test_multiframe_slice_has_two_frames(self):
        datasets, *_ = _build_series()
        assert get_slice_frame_count(datasets, 1) == 2

    def test_out_of_range_slice_index_returns_zero(self):
        datasets, *_ = _build_series()
        assert get_slice_frame_count(datasets, 99) == 0
        assert get_slice_frame_count(datasets, -1) == 0


class TestGetTotalSlices:
    def test_counts_slice_groups_not_datasets(self):
        datasets, *_ = _build_series()
        assert len(datasets) == 4
        assert get_total_slices(datasets) == 3

    def test_empty_series_has_zero_slices(self):
        assert get_total_slices([]) == 0


class TestGetFirstFrameIndexForSlice:
    def test_single_frame_slice_returns_its_own_index(self):
        datasets, *_ = _build_series()
        assert get_first_frame_index_for_slice(datasets, 0) == 0

    def test_multiframe_slice_returns_index_of_lowest_frame_index(self):
        datasets, _, _, frame_a0, _, _ = _build_series()
        # frame_a0 (_frame_index=0) sorts first even though it appears at datasets[2].
        assert get_first_frame_index_for_slice(datasets, 1) == datasets.index(frame_a0)

    def test_out_of_range_slice_index_returns_zero(self):
        datasets, *_ = _build_series()
        assert get_first_frame_index_for_slice(datasets, 99) == 0
