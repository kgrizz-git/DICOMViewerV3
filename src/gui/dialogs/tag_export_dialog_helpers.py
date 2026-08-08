"""
Shared helpers for the DICOM tag export dialog.

Inputs:
    - Preset tag string lists and optional base union dicts

Outputs:
    - Canonical preset match keys and merged union dicts with synthetic rows

Requirements:
    - core.tag_export_catalog.synthetic_tag_export_tree_entry
    - utils.dicom_utils.canonical_dicom_tag_string
"""

from __future__ import annotations

from typing import Any

from core.tag_export_catalog import synthetic_tag_export_tree_entry
from utils.dicom_utils import canonical_dicom_tag_string

_ITEM_NO_PRESET = "(No preset)"
_TITLE_NO_CONFIG_MANAGER = "No Config Manager"


def tag_export_preset_match_keys(preset_tags: list[str]) -> set[str]:
    """
    Build a set of strings that should match tree UserRole tag keys when loading
    a preset (exact + canonical pydicom str(Tag) forms).
    """
    keys: set[str] = set()
    for t in preset_tags:
        if not isinstance(t, str):
            continue
        keys.add(t)
        canonical = canonical_dicom_tag_string(t)
        if canonical:
            keys.add(canonical)
    return keys


def merged_dict_with_preset_tags(
    base: dict[str, Any] | None,
    preset_tags: list[str],
) -> tuple[dict[str, Any], bool]:
    """
    Return a shallow copy of *base* (or {}) with synthetic rows for any preset
    tag not already present. The second value is True when the dict changed.
    """
    merged: dict[str, Any] = dict(base or {})
    changed = False
    for raw in preset_tags:
        if not isinstance(raw, str):
            continue
        entry = synthetic_tag_export_tree_entry(raw)
        if entry is None:
            continue
        key, meta = entry
        if key not in merged:
            merged[key] = meta
            changed = True
    return merged, changed


# Backward-compatible private aliases used by older tests/imports.
_tag_export_preset_match_keys = tag_export_preset_match_keys
_merged_dict_with_preset_tags = merged_dict_with_preset_tags
