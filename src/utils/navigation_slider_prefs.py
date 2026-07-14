"""Shared helpers for slice/frame slider placement and direction settings."""

from __future__ import annotations

from typing import Any

SLIDER_PLACEMENTS = frozenset(("bottom", "top", "left", "right"))
SLIDER_DIRECTIONS = frozenset(("first_at_start", "first_at_end"))
DEFAULT_SLIDER_PLACEMENT = "bottom"
DEFAULT_SLIDER_DIRECTION = "first_at_start"


def normalize_slider_placement(value: Any) -> str:
    """Return a valid slider placement, falling back to the default."""
    text = str(value or "").strip().lower()
    return text if text in SLIDER_PLACEMENTS else DEFAULT_SLIDER_PLACEMENT


def normalize_slider_direction(value: Any) -> str:
    """Return a valid slider direction, falling back to the default."""
    text = str(value or "").strip().lower()
    return text if text in SLIDER_DIRECTIONS else DEFAULT_SLIDER_DIRECTION
