"""
Unit tests for ``utils.dicom_tag_path.resolve_tag_path``.

Resolves parser path keys like ``(0010,0010)`` or nested sequence paths like
``(0012,0064)[0].(0008,0104)`` back to the containing dataset and final tag.
Invalid/stale paths return ``None``.
"""

from __future__ import annotations

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence

from utils.dicom_tag_path import resolve_tag_path


def _seq_dataset() -> Dataset:
    root = Dataset()
    root.PatientName = "DOE^JOHN"
    inner = Dataset()
    inner.CodeValue = "A"
    outer_seq = Sequence([inner])
    # (0008,1110) is ReferencedStudySequence; use its tag in the path under test.
    root.ReferencedStudySequence = outer_seq
    return root


class TestResolveTagPath:
    def test_none_dataset(self):
        assert resolve_tag_path(None, "(0010,0010)") is None

    def test_non_string_key(self):
        assert resolve_tag_path(Dataset(), 12345) is None  # type: ignore[arg-type]

    def test_empty_key(self):
        assert resolve_tag_path(Dataset(), "   ") is None
        assert resolve_tag_path(Dataset(), "") is None

    def test_simple_leaf_tag(self):
        ds = Dataset()
        ds.PatientName = "X"
        result = resolve_tag_path(ds, "(0010,0010)")
        assert result is not None
        container, tag = result
        assert container is ds
        assert str(tag) == "(0010, 0010)"

    def test_simple_leaf_tag_lowercase_hex(self):
        ds = Dataset()
        ds.PatientName = "X"
        container, tag = resolve_tag_path(ds, "(0010, 0010)")  # type: ignore[misc]
        assert str(tag) == "(0010, 0010)"

    def test_invalid_leaf_not_a_tag(self):
        assert resolve_tag_path(Dataset(), "not-a-tag") is None

    def test_nested_sequence_path(self):
        # (0008,1110) is ReferencedStudySequence, set in _seq_dataset.
        root = _seq_dataset()
        result = resolve_tag_path(root, "(0008,1110)[0].(0008,0104)")
        assert result is not None
        container, tag = result
        assert container is root.ReferencedStudySequence[0]
        assert str(tag) == "(0008, 0104)"

    def test_nested_sequence_index_out_of_range(self):
        root = _seq_dataset()
        assert resolve_tag_path(root, "(0008,1110)[5].(0008,0104)") is None

    def test_nested_non_sequence_element(self):
        root = Dataset()
        root.PatientName = "X"  # not a sequence
        assert resolve_tag_path(root, "(0010,0010)[0].(0008,0104)") is None

    def test_missing_tag_in_path(self):
        root = Dataset()
        assert resolve_tag_path(root, "(9999,9999)[0].(0008,0104)") is None

    def test_intermediate_tag_not_sequence(self):
        root = _seq_dataset()
        # (0010,0010) is a leaf, not a sequence; cannot index into it.
        assert resolve_tag_path(root, "(0010,0010)[0].(0008,0104)") is None
