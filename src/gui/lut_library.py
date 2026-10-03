"""
The user's saved LUTs, read from and written to ``custom_luts.json``.

The store is the ``ConfigManager`` on the host's top-level window, so a menu
built for any pane reaches the same file. Saving a LUT whose name already
exists replaces that entry.

Inputs:
    - A host widget (pane or main window) and ``LookUpTable`` values

Outputs:
    - The saved LUT list, and success flags for save/delete

Requirements:
    - PySide6
    - core.lut_persistence
"""

from __future__ import annotations

import dataclasses
from typing import Any

from PySide6.QtWidgets import QWidget

from core.lut_engine import LookUpTable
from core.lut_persistence import luts_from_payload, luts_to_payload


def library_store(host: Any) -> Any:
    """The ``ConfigManager`` that owns ``custom_luts.json``, or ``None``."""
    widget = host if isinstance(host, QWidget) else getattr(host, "image_viewer", None)
    if not isinstance(widget, QWidget):
        return getattr(host, "config_manager", None)
    store = getattr(widget.window(), "config_manager", None)
    if store is None:
        store = getattr(host, "config_manager", None)
    return store if callable(getattr(store, "load_custom_luts_document", None)) else None


def saved_luts(store: Any) -> list[LookUpTable]:
    """Saved LUTs in file order. Empty when there is no store or no file."""
    if store is None:
        return []
    return luts_from_payload(store.load_custom_luts_document())


def is_savable(lut: LookUpTable | None) -> bool:
    """A grayscale curve, or a colormap that has color stops (built-in maps do not)."""
    if lut is None:
        return False
    return lut.lut_type == "grayscale_ramp" or lut.color_stops is not None


def save_lut(store: Any, lut: LookUpTable, name: str) -> LookUpTable | None:
    """Save ``lut`` under ``name``, replacing an entry of that name. Returns the saved LUT."""
    clean = name.strip()
    if store is None or not clean or not is_savable(lut):
        return None
    named = dataclasses.replace(lut, name=clean, source="custom")
    kept = [existing for existing in saved_luts(store) if existing.name != clean]
    kept.append(named)
    return named if store.save_custom_luts_document(luts_to_payload(kept)) else None


def delete_lut(store: Any, name: str) -> bool:
    """Remove the saved LUT called ``name``. False when absent or the write fails."""
    if store is None:
        return False
    current = saved_luts(store)
    kept = [existing for existing in current if existing.name != name]
    if len(kept) == len(current):
        return False
    return bool(store.save_custom_luts_document(luts_to_payload(kept)))
