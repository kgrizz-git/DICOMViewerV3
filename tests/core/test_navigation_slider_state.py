"""Tests for in-window navigation slider state helpers."""

from __future__ import annotations

from types import SimpleNamespace

from core.navigation_slider_state import (
    navigation_slider_mode_label_for_dataset,
    slider_value_to_logical_index,
)


def test_frame_wrapper_uses_frame_label() -> None:
    """Dataset with both _frame_index and _original_dataset returns 'Frame'."""
    dataset = SimpleNamespace(_frame_index=2, _original_dataset=object())

    assert navigation_slider_mode_label_for_dataset(dataset) == "Frame"


def test_regular_dataset_uses_slice_label() -> None:
    """Dataset without frame wrapper attributes returns 'Slice'."""
    dataset = SimpleNamespace(SOPInstanceUID="1.2.3")

    assert navigation_slider_mode_label_for_dataset(dataset) == "Slice"


def test_none_dataset_returns_slice_label() -> None:
    """None dataset returns 'Slice' label."""
    assert navigation_slider_mode_label_for_dataset(None) == "Slice"


def test_dataset_missing_frame_index_returns_slice_label() -> None:
    """Dataset with _original_dataset but missing _frame_index returns 'Slice'."""
    dataset = SimpleNamespace(_original_dataset=object())

    assert navigation_slider_mode_label_for_dataset(dataset) == "Slice"


def test_dataset_missing_original_dataset_returns_slice_label() -> None:
    """Dataset with _frame_index but missing _original_dataset returns 'Slice'."""
    dataset = SimpleNamespace(_frame_index=2)

    assert navigation_slider_mode_label_for_dataset(dataset) == "Slice"


def test_slider_value_to_logical_index_clamps_to_range() -> None:
    """Value is clamped to [minimum, maximum] range when maximum is provided."""
    assert slider_value_to_logical_index(1, minimum=1, maximum=5) == 0
    assert slider_value_to_logical_index(5, minimum=1, maximum=5) == 4
    assert slider_value_to_logical_index(99, minimum=1, maximum=5) == 4
    assert slider_value_to_logical_index(-10, minimum=1, maximum=5) == 0


def test_slider_value_to_logical_index_no_maximum() -> None:
    """When maximum is None, only minimum clamping is applied."""
    assert slider_value_to_logical_index(1, minimum=1) == 0
    assert slider_value_to_logical_index(5, minimum=1) == 4
    assert slider_value_to_logical_index(99, minimum=1) == 98
    assert slider_value_to_logical_index(-10, minimum=1) == 0


def test_slider_value_to_logical_index_at_minimum_boundary() -> None:
    """Value exactly at minimum returns 0."""
    assert slider_value_to_logical_index(1, minimum=1, maximum=10) == 0
    assert slider_value_to_logical_index(5, minimum=5, maximum=10) == 0


def test_slider_value_to_logical_index_below_minimum() -> None:
    """Value below minimum is clamped to minimum, returning 0."""
    assert slider_value_to_logical_index(0, minimum=1, maximum=10) == 0
    assert slider_value_to_logical_index(-5, minimum=1, maximum=10) == 0


def test_slider_value_to_logical_index_at_maximum_boundary() -> None:
    """Value exactly at maximum returns max - min."""
    assert slider_value_to_logical_index(10, minimum=1, maximum=10) == 9
    assert slider_value_to_logical_index(5, minimum=1, maximum=5) == 4


def test_slider_value_to_logical_index_above_maximum() -> None:
    """Value above maximum is clamped to maximum."""
    assert slider_value_to_logical_index(15, minimum=1, maximum=10) == 9
    assert slider_value_to_logical_index(100, minimum=1, maximum=10) == 9


def test_slider_value_to_logical_index_custom_minimum() -> None:
    """Custom minimum values are correctly handled."""
    assert slider_value_to_logical_index(10, minimum=10, maximum=20) == 0
    assert slider_value_to_logical_index(15, minimum=10, maximum=20) == 5
    assert slider_value_to_logical_index(20, minimum=10, maximum=20) == 10
    assert slider_value_to_logical_index(5, minimum=10, maximum=20) == 0
    assert slider_value_to_logical_index(25, minimum=10, maximum=20) == 10


def test_slider_value_to_logical_index_custom_minimum_no_maximum() -> None:
    """Custom minimum without maximum applies only lower bound."""
    assert slider_value_to_logical_index(10, minimum=10) == 0
    assert slider_value_to_logical_index(15, minimum=10) == 5
    assert slider_value_to_logical_index(100, minimum=10) == 90
    assert slider_value_to_logical_index(5, minimum=10) == 0


def test_slider_value_to_logical_index_zero_minimum() -> None:
    """Minimum of 0 is handled correctly."""
    assert slider_value_to_logical_index(0, minimum=0, maximum=10) == 0
    assert slider_value_to_logical_index(5, minimum=0, maximum=10) == 5
    assert slider_value_to_logical_index(10, minimum=0, maximum=10) == 10
    assert slider_value_to_logical_index(-5, minimum=0, maximum=10) == 0
