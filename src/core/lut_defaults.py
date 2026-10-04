"""
Default LUT per modality, used when a series has not chosen one.

A default is stored in the config as a small entry keyed by the DICOM
Modality (``"PT"``, ``"CT"``, ...):

- ``{"kind": "colormap", "name": "hot"}`` selects a built-in color map;
- ``{"kind": "curve", "lut": {...}}`` holds a built-in grayscale curve with its
  parameter, in the ``core.lut_persistence`` entry format;
- ``{"kind": "saved", "name": "Mine"}`` points at a LUT in the user's library.
  A deleted saved LUT simply stops being a default.

A series that has chosen a LUT keeps it; the default only replaces Linear for
a series that never chose. Changing the default therefore updates open series
that are still on it.

Inputs:
    - A ``LookUpTable`` (to make an entry), or an entry plus the saved LUTs

Outputs:
    - A config entry, or the ``LookUpTable`` it names (``None`` when unusable)

Requirements:
    - core.lut_catalog, core.lut_persistence
"""

from __future__ import annotations

import dataclasses
from typing import Any

from core.lut_catalog import DISPLAY_COLORMAP_NAMES, colormap_lut
from core.lut_engine import LookUpTable
from core.lut_persistence import lut_from_dict, lut_to_dict


def default_entry(lut: LookUpTable) -> dict[str, Any] | None:
    """The config entry that names ``lut``, or ``None`` when it cannot be a default.

    An unsaved custom curve or edited color map has no stable name, so it must
    be saved first.
    """
    if lut.source == "custom":
        return {"kind": "saved", "name": lut.name}
    if lut.lut_type == "colormap":
        if lut.color_stops is None and lut.name in DISPLAY_COLORMAP_NAMES:
            return {"kind": "colormap", "name": lut.name}
        return None
    try:
        return {"kind": "curve", "lut": lut_to_dict(lut)}
    except ValueError:
        return None


def resolve_default(entry: Any, saved: list[LookUpTable]) -> LookUpTable | None:
    """The LUT an entry names, or ``None`` when the entry is malformed or stale."""
    if not isinstance(entry, dict):
        return None
    kind = entry.get("kind")
    name = entry.get("name")
    if kind == "colormap" and isinstance(name, str) and name in DISPLAY_COLORMAP_NAMES:
        return colormap_lut(name)
    if kind == "saved" and isinstance(name, str):
        return next((lut for lut in saved if lut.name == name), None)
    if kind == "curve":
        try:
            curve = lut_from_dict(entry.get("lut"))
        except (TypeError, ValueError, KeyError, IndexError):
            return None
        # lut_from_dict marks library entries custom; this one is a built-in kind.
        return dataclasses.replace(curve, source="built_in")
    return None
