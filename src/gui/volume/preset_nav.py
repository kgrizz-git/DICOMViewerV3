"""Keyboard navigation across the 3D preset combo.

The combo interleaves modality heading rows ("— CT —", "— MR —", ...) with real
presets.  Those headings are not selectable presets: ``_on_preset_changed``
early-returns on them, so stepping onto one leaves the combo displaying a
heading with no preset applied.  Stepping must skip them.
"""

from __future__ import annotations

from collections.abc import Callable


def preset_step_index(
    current: int,
    step: int,
    count: int,
    is_preset_row: Callable[[int], bool],
) -> int | None:
    """Return the next selectable preset row, or ``None`` if there is none.

    Args:
        current: Current combo row index.
        step: ``+1`` to move forward, ``-1`` to move back.
        count: Total combo row count.
        is_preset_row: Returns ``True`` when a row is a real preset.
    """
    if step == 0 or count <= 0:
        return None
    index = current + step
    while 0 <= index < count:
        if is_preset_row(index):
            return index
        index += step
    return None
