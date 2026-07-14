"""Tests for path-addressed DICOM tag resolution."""

from __future__ import annotations

from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag

from core.tag_path import leaf_tag_from_key, resolve_tag_path

DEID_SEQ = Tag(0x0012, 0x0064)
CODE_MEANING = Tag(0x0008, 0x0104)
CONCEPT_NAME_SEQ = Tag(0x0040, 0xA043)
PATIENT_NAME = Tag(0x0010, 0x0010)


def _dataset_with_sequences() -> Dataset:
    ds = Dataset()
    ds.PatientName = "Root^Patient"
    ds.add_new(CODE_MEANING, "LO", "Root Code Meaning")

    first_item = Dataset()
    first_item.add_new(CODE_MEANING, "LO", "First nested meaning")

    deep_item = Dataset()
    deep_item.add_new(CODE_MEANING, "LO", "Deep nested meaning")
    first_item.add_new(CONCEPT_NAME_SEQ, "SQ", Sequence([deep_item]))

    second_item = Dataset()
    second_item.add_new(CODE_MEANING, "LO", "Second nested meaning")

    ds.add_new(DEID_SEQ, "SQ", Sequence([first_item, second_item]))
    return ds


def test_resolve_root_key_returns_root_dataset_and_tag() -> None:
    ds = _dataset_with_sequences()

    resolved = resolve_tag_path(ds, "(0010, 0010)")

    assert resolved == (ds, PATIENT_NAME)


def test_resolve_root_key_accepts_no_space_and_lowercase() -> None:
    ds = _dataset_with_sequences()

    resolved = resolve_tag_path(ds, "(0010,0010)")

    assert resolved == (ds, PATIENT_NAME)


def test_resolve_one_level_nested_key_returns_containing_item_and_leaf_tag() -> None:
    ds = _dataset_with_sequences()

    resolved = resolve_tag_path(ds, "(0012, 0064)[1].(0008, 0104)")

    assert resolved == (ds[DEID_SEQ].value[1], CODE_MEANING)


def test_resolve_three_level_nested_key() -> None:
    ds = _dataset_with_sequences()

    resolved = resolve_tag_path(
        ds,
        "(0012, 0064)[0].(0040, A043)[0].(0008, 0104)",
    )

    assert resolved == (
        ds[DEID_SEQ].value[0][CONCEPT_NAME_SEQ].value[0],
        CODE_MEANING,
    )


def test_resolve_returns_none_for_item_node_key() -> None:
    ds = _dataset_with_sequences()

    assert resolve_tag_path(ds, "(0012, 0064)[0]") is None


def test_resolve_returns_none_for_missing_intermediate_tag() -> None:
    ds = _dataset_with_sequences()

    assert resolve_tag_path(ds, "(0012, 0065)[0].(0008, 0104)") is None


def test_resolve_returns_none_for_scalar_intermediate() -> None:
    ds = _dataset_with_sequences()

    assert resolve_tag_path(ds, "(0008, 0104)[0].(0010, 0010)") is None


def test_resolve_returns_none_for_out_of_range_item() -> None:
    ds = _dataset_with_sequences()

    assert resolve_tag_path(ds, "(0012, 0064)[2].(0008, 0104)") is None


def test_resolve_returns_none_for_non_dataset_sequence_item() -> None:
    ds = Dataset()
    ds.add(DataElement(DEID_SEQ, "SQ", Sequence([])))
    ds[DEID_SEQ]._value = ["not a dataset"]

    assert resolve_tag_path(ds, "(0012, 0064)[0].(0008, 0104)") is None


def test_resolve_returns_none_for_invalid_key_shapes() -> None:
    ds = _dataset_with_sequences()

    invalid_keys = [
        "",
        "not-a-tag",
        "(0012, 0064)[-1].(0008, 0104)",
        "(0012, 0064)[].(0008, 0104)",
        "(0012, 0064)[0].(0008, 0104)#2",
        "(0012, 0064).<truncated>",
    ]

    for key in invalid_keys:
        assert resolve_tag_path(ds, key) is None


def test_leaf_tag_from_key_extracts_root_and_nested_leaf_tags() -> None:
    assert leaf_tag_from_key("(0010, 0010)") == PATIENT_NAME
    assert leaf_tag_from_key("(0012, 0064)[0].(0008, 0104)") == CODE_MEANING
    assert leaf_tag_from_key("(0012, 0064)[0]") is None
    assert leaf_tag_from_key("(0012, 0064)[0].<truncated>") is None
