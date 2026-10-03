"""
Apply a window/level chosen on a pane's histogram to that pane.

The right-panel W/L controls drive the focused pane, so a histogram for an
unfocused pane focuses it first. ``set_window_level`` then emits
``window_changed``, the same path a slider drag takes.

Inputs:
    - The app (duck typed), the histogram's pane index, the focused index,
      and the new center/width

Outputs:
    - None; the pane redisplays through the normal W/L signal path

Requirements:
    - None beyond the app's ``multi_window_layout`` and ``window_level_controls``
"""

from __future__ import annotations

from typing import Any


def apply_pane_window_level(
    app: Any, idx: int, focused_idx: int, center: float, width: float
) -> None:
    """Focus pane ``idx`` when needed, then set its window through the controls."""
    if focused_idx != idx:
        layout = getattr(app, "multi_window_layout", None)
        subwindows = layout.get_all_subwindows() if layout is not None else []
        if idx >= len(subwindows) or subwindows[idx] is None:
            return
        layout.set_focused_subwindow(subwindows[idx])
    controls = getattr(app, "window_level_controls", None)
    if controls is not None:
        controls.set_window_level(center, width)
