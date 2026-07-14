"""Tests for in-window navigation slider state helpers."""

from __future__ import annotations

from types import SimpleNamespace

from core.navigation_slider_state import (
    navigation_slider_mode_label_for_dataset,
    slider_value_to_logical_index,
)


def test_frame_wrapper_uses_frame_label() -> None:
    dataset = SimpleNamespace(_frame_index=2, _original_dataset=object())

    assert navigation_slider_mode_label_for_dataset(dataset) == "Frame"


def test_regular_dataset_uses_slice_label() -> None:
    dataset = SimpleNamespace(SOPInstanceUID="1.2.3")

    assert navigation_slider_mode_label_for_dataset(dataset) == "Slice"


def test_slider_value_to_logical_index_clamps_to_range() -> None:
    assert slider_value_to_logical_index(1, minimum=1, maximum=5) == 0
    assert slider_value_to_logical_index(5, minimum=1, maximum=5) == 4
    assert slider_value_to_logical_index(99, minimum=1, maximum=5) == 4
    assert slider_value_to_logical_index(-10, minimum=1, maximum=5) == 0
