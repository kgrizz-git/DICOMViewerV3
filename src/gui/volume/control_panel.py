"""Sizing helpers for the 3D viewer's control panel column."""

from __future__ import annotations

from typing import Any

# Control-panel column sizing.  The width is derived from the panel's own size
# hint at build time; these bound it so an unusual font or theme can neither
# collapse the column nor let it swallow the viewport.
CONTROL_PANEL_MIN_WIDTH = 240
CONTROL_PANEL_MAX_WIDTH = 420
CONTROL_PANEL_PADDING_PX = 4


def control_panel_width(content_width: int, scrollbar_width: int) -> int:
    """Return the clamped column width for the given content and scrollbar."""
    needed = content_width + scrollbar_width + CONTROL_PANEL_PADDING_PX
    return max(CONTROL_PANEL_MIN_WIDTH, min(needed, CONTROL_PANEL_MAX_WIDTH))


def fit_control_panel_width(scroll: Any, panel: Any) -> None:
    """Size *scroll* to what *panel* needs, plus room for the scrollbar.

    A hardcoded width clipped the right edge of the widest controls, and with
    the horizontal scrollbar disabled the clipped part was unreachable no
    matter how large the window grew.
    """
    scroll.setFixedWidth(
        control_panel_width(
            panel.sizeHint().width(),
            scroll.verticalScrollBar().sizeHint().width(),
        )
    )
