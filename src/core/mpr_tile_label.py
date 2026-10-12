"""Navigator tile labels for MPR views (pure core, no Qt, no PHI).

Text is built only from registry facts: the user-chosen orientation label,
session/view numbers, window number, and link state. Never from DICOM
attributes, so tiles and tooltips are safe to show in privacy mode.
"""

from __future__ import annotations

from core.mpr_session_types import MprViewMetadata

_MAX_ORIENTATION_CHARS = 24


def _orientation_text(meta: MprViewMetadata) -> str:
    text = "".join(ch for ch in str(meta.orientation) if ch.isprintable()).strip()
    return text[:_MAX_ORIENTATION_CHARS]


def tile_tag(meta: MprViewMetadata) -> str:
    """Compact tag painted on the tile: ``S2``, ``S2.1`` (shared result), ``S2.1L`` (linked)."""
    tag = f"S{meta.session_id}"
    if meta.view_count > 1:
        tag += f".{meta.view_number}"
    if meta.link_group_id is not None:
        tag += "L"
    return tag


def tile_tooltip(meta: MprViewMetadata, window_number: str | None) -> str:
    """Full tile description; *window_number* is the user-visible window label or None."""
    lines = [
        " ".join(part for part in ("MPR", _orientation_text(meta)) if part),
        f"Session {meta.session_id} · view {meta.view_number} of {meta.view_count}",
    ]
    if meta.link_group_id is not None:
        lines.append("Linked scrolling")
    if window_number is not None:
        lines.append(f"Window {window_number} — click to focus, drag to move")
    else:
        # A detached view is dormant, but a linked one still follows its group: show where.
        lines.append(f"Not in a window (slice {meta.slice_index + 1} of {meta.n_slices}) — drag onto a pane to show")
    menu = "Duplicate into Window… / Duplicate Linked into Window… / "
    lines.append(f"Right-click: {menu}{'Unlink View / ' if meta.link_group_id is not None else ''}Clear MPR")
    return "\n".join(lines)


__all__ = ["tile_tag", "tile_tooltip"]
