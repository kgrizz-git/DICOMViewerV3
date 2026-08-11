"""Tests for core.tag_export_union — union of DICOM tag maps across datasets."""

from __future__ import annotations

import pytest
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from core.tag_export_union import union_tags_across_datasets


def _make_dataset(**attrs) -> Dataset:
    ds = Dataset()
    for key, value in attrs.items():
        setattr(ds, key, value)
    return ds


def _make_dataset_with_sequence() -> Dataset:
    ds = Dataset()
    ds.PatientID = "P001"
    inner = Dataset()
    inner.CodeValue = "A"
    ds.ReferencedStudySequence = Sequence([inner])
    return ds


def test_union_empty_datasets():
    result = union_tags_across_datasets([], include_private=False)
    assert result == {}


def test_union_single_dataset():
    ds = _make_dataset(PatientID="P001", StudyID="S001")
    result = union_tags_across_datasets([ds], include_private=False)
    assert "(0010, 0020)" in result
    assert "(0020, 0010)" in result


def test_union_merges_keys_across_datasets():
    ds1 = _make_dataset(PatientID="P001")
    ds2 = _make_dataset(StudyID="S001", Modality="CT")
    result = union_tags_across_datasets([ds1, ds2], include_private=False)
    assert "(0010, 0020)" in result
    assert "(0020, 0010)" in result
    assert "(0008, 0060)" in result


def test_union_first_occurrence_wins():
    ds1 = _make_dataset(PatientID="P001")
    ds2 = _make_dataset(PatientID="P002", StudyID="S001")
    result = union_tags_across_datasets([ds1, ds2], include_private=False)
    assert result["(0010, 0020)"]["value"] == "P001"
    assert "(0020, 0010)" in result


def test_union_preserves_order():
    ds1 = _make_dataset(StudyID="S001")
    ds2 = _make_dataset(PatientID="P001")
    result1 = union_tags_across_datasets([ds1, ds2], include_private=False)
    result2 = union_tags_across_datasets([ds2, ds1], include_private=False)
    assert "(0020, 0010)" in result1
    assert "(0010, 0020)" in result2
    assert next(iter(result1.keys())) == "(0020, 0010)"
    assert next(iter(result2.keys())) == "(0010, 0020)"


def test_union_supplement_standard_tags():
    ds = _make_dataset(PatientID="P001")
    result_without = union_tags_across_datasets([ds], include_private=False, supplement_standard_tags=False)
    result_with = union_tags_across_datasets([ds], include_private=False, supplement_standard_tags=True)
    assert len(result_with) > len(result_without)
    assert "(0010, 0010)" in result_with  # PatientName — standard catalog tag


def test_union_include_sequences():
    ds = _make_dataset_with_sequence()
    result_without = union_tags_across_datasets([ds], include_private=False, include_sequences=False)
    result_with = union_tags_across_datasets([ds], include_private=False, include_sequences=True)
    # Without sequences: only the SQ summary row appears
    assert "(0008, 1110)" in result_without
    assert not any("[0]" in k for k in result_without)
    # With sequences: item nodes and nested leaves appear
    assert any("[0]" in k for k in result_with)


def test_union_keyword_only_include_private():
    with pytest.raises(TypeError):
        union_tags_across_datasets([], True)  # type: ignore[misc]


def test_union_include_private_false():
    ds = _make_dataset(PatientID="P001")
    ds.add_new((0x0009, 0x0010), "LO", "Private Creator")
    result_no_private = union_tags_across_datasets([ds], include_private=False)
    result_with_private = union_tags_across_datasets([ds], include_private=True)
    assert "(0009, 0010)" not in result_no_private
    assert "(0009, 0010)" in result_with_private
    assert "(0010, 0020)" in result_no_private  # PatientID still present
