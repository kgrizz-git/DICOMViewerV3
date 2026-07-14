"""Viewport overlay text for the 3D volume viewer (refactor Stream B).

Pure, Qt/VTK-free string builder extracted from ``gui/volume_viewer_widget.py``
so it can be unit-tested directly.
"""

from __future__ import annotations


def build_overlay_text(
    *,
    preset_name: str,
    opacity_pct: float,
    detail: str,
    blend: str,
) -> str:
    """Build the upper-left viewport overlay text from current 3D state.

    Args:
        preset_name: Display name of the active preset. Empty string when no
            preset is resolved (e.g. a separator row) — no preset line is emitted.
        opacity_pct: Resolved global opacity percent (0–100). An "Opacity …" line
            is added only when below 100.
        detail: Detail / quality mode name. A "Detail: …" line is added only when
            this is not the neutral ``"Normal"`` mode.
        blend: Render/blend mode name. A line is added only when this is not the
            default ``"Composite"`` mode.

    Returns:
        Newline-joined overlay text (may be empty).
    """
    lines = []
    if preset_name:
        lines.append(preset_name)
    if opacity_pct < 100.0:
        lines.append(f"Opacity {opacity_pct:.1f}%")
    if detail and detail != "Normal":
        lines.append(f"Detail: {detail}")
    if blend and blend != "Composite":
        lines.append(blend)
    return "\n".join(lines)
