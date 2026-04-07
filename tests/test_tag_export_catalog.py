"""
Tests for tag_export_catalog helpers used by the tag export dialog.
"""

from __future__ import annotations

from core.tag_export_catalog import synthetic_tag_export_tree_entry


def test_synthetic_tag_export_tree_entry_keyword() -> None:
    result = synthetic_tag_export_tree_entry("PatientName")
    assert result is not None
    key, meta = result
    assert key.startswith("(")
    assert meta["value"] == ""
    assert meta.get("name")


def test_synthetic_tag_export_tree_entry_hex_variants_share_key() -> None:
    a = synthetic_tag_export_tree_entry("(0010,0010)")
    b = synthetic_tag_export_tree_entry("(0010, 0010)")
    assert a is not None and b is not None
    assert a[0] == b[0]


def test_synthetic_tag_export_tree_entry_unknown_string_returns_none() -> None:
    assert synthetic_tag_export_tree_entry("") is None
    assert synthetic_tag_export_tree_entry("not-a-tag-🙂") is None


def test_merged_dict_with_preset_tags_adds_missing() -> None:
    from gui.dialogs.tag_export_dialog import _merged_dict_with_preset_tags

    base = {}
    merged, changed = _merged_dict_with_preset_tags(base, ["PatientName", "PatientName"])
    assert changed is True
    assert len(merged) == 1
    assert merged[list(merged.keys())[0]]["value"] == ""

    merged2, changed2 = _merged_dict_with_preset_tags(merged, ["PatientName"])
    assert changed2 is False

