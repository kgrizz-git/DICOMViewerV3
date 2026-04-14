"""
Slice sync linked-group colors (pure Python, no Qt).

**Palette helper:** small module that maps a **group list index** (and view→group
lookup) to stable **RGB tuples** so Qt code does not hard-code colors. The UI
draws those colors as a thin strip above each grouped pane.

Used by subwindow chrome to show which panes share an anatomic slice-sync group.
Groups in config are lists of **view indices** (0–3), matching ``subwindows[i]``,
``ImageViewer.subwindow_index``, and ``SliceSyncCoordinator`` — not grid **slot**
indices (``slot_to_view`` permutations do not change group membership).

Inputs:
    - Group index ``g`` (0-based position in ``get_slice_sync_groups()``).
    - A view index and the current group list (for membership lookup).

Outputs:
    - Distinct (R, G, B) tuples chosen for contrast on light and dark UI chrome
      (saturation + 1px contrasting outline drawn in Qt).

Requirements: none (stdlib only).
"""

from __future__ import annotations

from typing import List, Optional

# Saturated, distinct hues; outlined in the widget for light/dark title bars.
_SLICE_SYNC_GROUP_RGB: tuple[tuple[int, int, int], ...] = (
    (211, 47, 47),  # red
    (25, 118, 210),  # blue
    (56, 142, 60),  # green
    (245, 124, 0),  # orange
    (123, 31, 162),  # purple
    (0, 121, 107),  # teal
    (194, 24, 91),  # pink
    (255, 109, 0),  # deep orange
)


def slice_sync_group_rgb(group_index: int) -> tuple[int, int, int]:
    """
    Return a stable RGB for the given group list index.

    Args:
        group_index: Index into the persisted ``slice_sync_groups`` list (0-based).

    Returns:
        (r, g, b) each in 0..255.
    """
    if group_index < 0:
        group_index = 0
    return _SLICE_SYNC_GROUP_RGB[group_index % len(_SLICE_SYNC_GROUP_RGB)]


def view_index_to_group_index(
    groups: List[List[int]], view_index: int
) -> Optional[int]:
    """
    Return which group (by list order) contains ``view_index``, or None.

    If a view appears in more than one group (invalid config), the first match wins.
    """
    for gi, members in enumerate(groups):
        if view_index in members:
            return gi
    return None
