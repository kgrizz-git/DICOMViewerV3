"""
Helpers for clearing ad-hoc dataset caches safely.

``pydicom.Dataset`` custom attribute deletion can raise via ``__delattr__``
even when ``hasattr()`` looked truthy, so cache cleanup should remove values
from ``__dict__`` directly.
"""

from __future__ import annotations

from typing import Any


def clear_cached_pixel_array(dataset: Any) -> None:
    """Remove the transient ``_cached_pixel_array`` attribute if present."""
    dataset_dict = getattr(dataset, "__dict__", None)
    if isinstance(dataset_dict, dict):
        dataset_dict.pop("_cached_pixel_array", None)
