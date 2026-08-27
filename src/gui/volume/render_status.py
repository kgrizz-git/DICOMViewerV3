"""Pure formatting helpers for the volume-render advanced status panel."""

from __future__ import annotations

from typing import Any

_MEBIBYTE = 1024 * 1024


def memory_guard_status_lines(renderer: Any) -> list[str]:
    """Format memory-guard provenance stored by ``VolumeRenderer``.

    The renderer attributes are intentionally private: this helper preserves
    the existing widget-to-renderer coupling while isolating status formatting
    from the Qt/VTK widget.
    """
    downsample_factor = max(1, int(getattr(renderer, "_downsample_factor", 1)))
    if downsample_factor == 1:
        return []

    source_dims = getattr(renderer, "_source_dimensions", None)
    source_text = (
        f" from {source_dims[0]}×{source_dims[1]}×{source_dims[2]}"
        if isinstance(source_dims, (tuple, list)) and len(source_dims) == 3
        else ""
    )
    lines = [f"Memory guard: {downsample_factor}× downsampled{source_text}"]
    estimated_peak = getattr(renderer, "_estimated_peak_bytes", None)
    budget = getattr(renderer, "_memory_budget_bytes", None)
    if isinstance(estimated_peak, int) and isinstance(budget, int):
        lines.append(
            "Predicted peak: "
            f"~{estimated_peak / _MEBIBYTE:.0f} MB "
            f"/ {budget / _MEBIBYTE:.0f} MB budget"
        )
    return lines
