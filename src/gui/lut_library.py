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
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QWidget

from core.lut_engine import LookUpTable
from core.lut_persistence import luts_from_payload, luts_to_payload, payload_is_writable


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


def _writable_document(store: Any) -> tuple[bool, Any]:
    """The current document, and whether rewriting it would lose nothing.

    Not writable when the file exists but could not be read, when it comes from
    a newer schema or is malformed, or when any entry fails to parse: a rewrite
    would drop that entry. A missing file is writable.
    """
    document = store.load_custom_luts_document()
    if document is None:
        path_of = getattr(store, "custom_luts_path", None)
        path = path_of() if callable(path_of) else None
        exists = isinstance(path, Path) and path.exists()
        return (not exists), None
    if not payload_is_writable(document):
        return False, document
    entries = document.get("luts", [])
    if not isinstance(entries, list) or len(luts_from_payload(document)) != len(entries):
        return False, document
    return True, document


def save_lut(store: Any, lut: LookUpTable, name: str) -> LookUpTable | None:
    """Save ``lut`` under ``name``. Returns the saved LUT, or None when nothing was written.

    An entry with the same name is replaced in place, keeping its position.
    A file that is unreadable, from a newer build, or holds an entry this build
    cannot parse is left alone, because rewriting it would drop that content.
    """
    clean = name.strip()
    if store is None or not clean or not is_savable(lut):
        return None
    writable, document = _writable_document(store)
    if not writable:
        return None
    named = dataclasses.replace(lut, name=clean, source="custom")
    current = luts_from_payload(document)
    names = [existing.name for existing in current]
    if clean in names:
        current[names.index(clean)] = named
    else:
        current.append(named)
    try:
        payload = luts_to_payload(current)
    except ValueError:
        return None
    return named if store.save_custom_luts_document(payload) else None


def delete_lut(store: Any, name: str) -> bool:
    """Remove the saved LUT called ``name``. False when absent or the write fails."""
    if store is None:
        return False
    writable, document = _writable_document(store)
    if not writable:
        return False
    current = luts_from_payload(document)
    kept = [existing for existing in current if existing.name != name]
    if len(kept) == len(current):
        return False
    return bool(store.save_custom_luts_document(luts_to_payload(kept)))
