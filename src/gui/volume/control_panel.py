"""Sizing helpers for the 3D viewer's control panel column."""

from __future__ import annotations

from typing import Any

# Control-panel column sizing.  The width is derived from the panel's own size
# hint at build time; these bound it so an unusual font or theme can neither
# collapse the column nor let it swallow the viewport.
CONTROL_PANEL_MIN_WIDTH = 240
CONTROL_PANEL_MAX_WIDTH = 420
CONTROL_PANEL_PADDING_PX = 4

# How far to blend normal text toward the background for muted labels.
# 0.70 measures ~8:1 against the window background — clearly de-emphasised but
# comfortably above the 4.5:1 WCAG AA floor.
MUTED_TEXT_MIX = 0.70


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


def muted_text_color(palette: Any) -> Any:
    """Return a de-emphasised but legible foreground for the given palette.

    ``palette(mid)`` was used here originally.  Mid is a 3D-bevel shading role,
    not a text role: it scores a ~1.7:1 contrast ratio against the window
    background in both light and dark themes, far below the 4.5:1 WCAG AA
    floor, leaving the help strip and status labels nearly invisible.  The
    Disabled text role is no better (~1.6:1) and is semantically wrong — these
    labels are informational, not disabled.

    Blending the normal text colour toward the background keeps the muted look
    while staying legible, and follows the theme automatically.
    """
    from PySide6.QtGui import QColor, QPalette

    text = palette.color(QPalette.ColorRole.WindowText)
    window = palette.color(QPalette.ColorRole.Window)
    return QColor(
        round(window.red() + (text.red() - window.red()) * MUTED_TEXT_MIX),
        round(window.green() + (text.green() - window.green()) * MUTED_TEXT_MIX),
        round(window.blue() + (text.blue() - window.blue()) * MUTED_TEXT_MIX),
    )


def muted_label_style(palette: Any, *, font_size_px: int, padding: str = "") -> str:
    """Return a stylesheet for a de-emphasised informational label."""
    rule = f"color: {muted_text_color(palette).name()}; font-size: {font_size_px}px;"
    return f"{rule} {padding}".strip()


def apply_muted_label_styles(widget: Any) -> None:
    """Recolour the viewer's informational labels for the current palette."""
    palette = widget.palette()
    for name, size, padding in (
        ("_help_strip", 10, "padding: 2px 4px;"),
        ("_scalar_domain_label", 11, ""),
        ("_render_status_label", 11, ""),
    ):
        label = getattr(widget, name, None)
        if label is not None:
            label.setStyleSheet(
                muted_label_style(palette, font_size_px=size, padding=padding)
            )
