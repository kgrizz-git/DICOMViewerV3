"""Tests for core.navigation_slider_state and core.dataset_cache_utils."""

from __future__ import annotations

from core.dataset_cache_utils import clear_cached_pixel_array
from core.navigation_slider_state import (
    DEFAULT_SLIDER_DIRECTION,
    DEFAULT_SLIDER_PLACEMENT,
    navigation_slider_mode_label_for_dataset,
    slider_value_to_logical_index,
)


def test_navigation_slider_mode_label_for_dataset():
    class FrameDataset:
        _frame_index = 0
        _original_dataset = None

    class SliceDataset:
        pass

    assert navigation_slider_mode_label_for_dataset(FrameDataset()) == "Frame"
    assert navigation_slider_mode_label_for_dataset(SliceDataset()) == "Slice"
    assert navigation_slider_mode_label_for_dataset(None) == "Slice"


def test_slider_value_to_logical_index():
    assert slider_value_to_logical_index(1, minimum=1) == 0
    assert slider_value_to_logical_index(5, minimum=1) == 4
    assert slider_value_to_logical_index(0, minimum=1) == 0
    assert slider_value_to_logical_index(10, minimum=1, maximum=5) == 4
    assert slider_value_to_logical_index(5, minimum=3) == 2


def test_import_defaults():
    assert DEFAULT_SLIDER_DIRECTION == "first_at_start"
    assert DEFAULT_SLIDER_PLACEMENT == "bottom"


def test_clear_cached_pixel_array():
    class Dataset:
        def __init__(self):
            self._cached_pixel_array = [1, 2, 3]
            self.other = "keep"

    ds = Dataset()
    clear_cached_pixel_array(ds)
    assert not hasattr(ds, "_cached_pixel_array")
    assert hasattr(ds, "other")

    ds_clean = Dataset()
    del ds_clean._cached_pixel_array
    clear_cached_pixel_array(ds_clean)

    class SlotDataset:
        __slots__ = ['_cached_pixel_array']
        def __init__(self):
            self._cached_pixel_array = 1

    s_ds = SlotDataset()
    clear_cached_pixel_array(s_ds)
    # clear_cached_pixel_array is deliberately __dict__-only (see its docstring:
    # delattr() on a real pydicom.Dataset was a prior production regression), so
    # __slots__-only objects -- which no real caller passes -- are left untouched.
    assert s_ds._cached_pixel_array == 1
