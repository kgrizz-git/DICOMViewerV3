"""Helpers for the in-window slice/frame navigation slider."""

from __future__ import annotations

from typing import Any

from utils.navigation_slider_prefs import (
    DEFAULT_SLIDER_DIRECTION,
    DEFAULT_SLIDER_PLACEMENT,
    normalize_slider_direction,
    normalize_slider_placement,
)

__all__ = [
    "DEFAULT_SLIDER_DIRECTION",
    "DEFAULT_SLIDER_PLACEMENT",
    "normalize_slider_direction",
    "normalize_slider_placement",
]


def navigation_slider_mode_label_for_dataset(dataset: Any) -> str:
    """Return ``Frame`` for split multi-frame wrappers, otherwise ``Slice``."""
    if dataset is not None and hasattr(dataset, "_frame_index") and hasattr(dataset, "_original_dataset"):
        return "Frame"
    return "Slice"


def slider_value_to_logical_index(value: int, *, minimum: int = 1, maximum: int | None = None) -> int:
    """
    Convert a 1-based slider value to a 0-based logical navigation index.

    Direction inversion is handled by the Qt slider appearance/controls; this
    helper deliberately keeps the app callback value logical and uninverted.
    """
    low = int(minimum)
    raw_value = int(value)
    if maximum is not None:
        raw_value = min(raw_value, int(maximum))
    raw_value = max(raw_value, low)
    return raw_value - low
