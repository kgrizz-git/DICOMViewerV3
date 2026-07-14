"""
Tests for tag_export_catalog helpers used by the tag export dialog.
"""

from __future__ import annotations

from pydicom.dataset import Dataset
from pydicom.tag import Tag

from core.dicom_parser import DICOMParser
from core.tag_export_catalog import synthetic_tag_export_tree_entry


def test_synthetic_tag_export_tree_entry_keyword() -> None:
    result = synthetic_tag_export_tree_entry("PatientName")
    assert result is not None
    key, meta = result
    assert key.startswith("(")
    assert meta["value"] == ""
    assert meta.get("name")


def test_sq_catalog_tags_are_offered_regardless_of_the_sequences_flag() -> None:
    """A missing SQ tag is offerable in the picker whether or not sequence contents are on.

    A sequence is always a visible row now (valued with a summary), so gating the
    *catalog* on the sequences flag would make a missing sequence unselectable for no
    reason. The de-identification tag is the one that motivated this: it was absent from
    the picker by default, so a de-identified file couldn't be checked for provenance.
    """
    key = str(Tag("DeidentificationMethodCodeSequence"))
    for include_sequences in (False, True):
        tags = DICOMParser(Dataset()).get_all_tags(
            include_private=False,
            supplement_standard_tags=True,
            include_sequences=include_sequences,
        )
        assert key in tags
        assert tags[key]["VR"] == "SQ"
        assert tags[key]["name"] == "De-identification Method Code Sequence"
        # Synthetic rows must be tree-shaped like real ones, or the picker can't place them.
        assert tags[key]["row_kind"] == "sequence"
        assert tags[key]["depth"] == 0
        assert tags[key]["parent_key"] is None


def test_resolve_catalog_does_not_filter_by_vr() -> None:
    """The resolver used to drop every SQ row unless a flag was passed. Nothing about a
    tag's VR should decide whether it is offerable now."""
    from core.tag_export_catalog import _resolve_catalog

    catalog = _resolve_catalog()
    assert any(vr == "SQ" for _tag, _kw, _name, vr in catalog)
    assert any(vr not in ("SQ", "") for _tag, _kw, _name, vr in catalog)


def test_synthetic_tag_export_tree_entry_hex_variants_share_key() -> None:
    a = synthetic_tag_export_tree_entry("(0010,0010)")
    b = synthetic_tag_export_tree_entry("(0010, 0010)")
    assert a is not None and b is not None
    assert a[0] == b[0]


def test_synthetic_tag_export_tree_entry_survives_a_private_tag() -> None:
    """A private tag has no standard-dictionary description.

    ``dictionary_description`` raises ``KeyError`` for one, which was unguarded — so a
    saved preset containing any private tag crashed the whole preset load rather than
    just offering that tag with no name.
    """
    result = synthetic_tag_export_tree_entry("(0019, 1010)")
    assert result is not None
    key, meta = result
    assert meta["is_private"] is True
    assert meta["name"] == key  # falls back to the tag number, having no description


def test_synthetic_tag_export_tree_entry_unknown_string_returns_none() -> None:
    assert synthetic_tag_export_tree_entry("") is None
    assert synthetic_tag_export_tree_entry("not-a-tag-🙂") is None


def test_merged_dict_with_preset_tags_adds_missing() -> None:
    from gui.dialogs.tag_export_dialog import _merged_dict_with_preset_tags

    base = {}
    merged, changed = _merged_dict_with_preset_tags(base, ["PatientName", "PatientName"])
    assert changed is True
    assert len(merged) == 1
    assert merged[next(iter(merged))]["value"] == ""

    merged2, changed2 = _merged_dict_with_preset_tags(merged, ["PatientName"])
    assert changed2 is False
