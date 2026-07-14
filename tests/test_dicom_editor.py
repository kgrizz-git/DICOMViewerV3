"""Unit tests for core.dicom_editor.DICOMEditor."""

from __future__ import annotations

import pytest
from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag

from core.dicom_editor import DICOMEditor


def _dataset_with_patient_name(name="Doe^John"):
    ds = Dataset()
    ds.PatientName = name
    return ds


def _dataset_with_nested_code_meaning():
    ds = Dataset()
    ds.add_new(Tag(0x0008, 0x0104), "LO", "Root meaning")
    item = Dataset()
    item.add_new(Tag(0x0008, 0x0104), "LO", "Nested meaning")
    ds.add_new(Tag(0x0012, 0x0064), "SQ", Sequence([item]))
    return ds


class TestInitAndSetDataset:
    def test_init_without_dataset(self):
        editor = DICOMEditor()
        assert editor.dataset is None

    def test_init_with_dataset(self):
        ds = _dataset_with_patient_name()
        editor = DICOMEditor(ds)
        assert editor.dataset is ds

    def test_set_dataset(self):
        editor = DICOMEditor()
        ds = _dataset_with_patient_name()
        editor.set_dataset(ds)
        assert editor.dataset is ds


class TestGetTargetDataset:
    def test_no_dataset_raises(self):
        editor = DICOMEditor()
        with pytest.raises(ValueError, match="No dataset set"):
            editor.get_target_dataset()

    def test_regular_dataset_returns_itself(self):
        ds = _dataset_with_patient_name()
        editor = DICOMEditor(ds)
        assert editor.get_target_dataset() is ds

    def test_frame_wrapper_returns_original_dataset(self):
        original = _dataset_with_patient_name()
        wrapper = Dataset()
        wrapper._original_dataset = original
        editor = DICOMEditor(wrapper)
        assert editor.get_target_dataset() is original


class TestParseTag:
    def test_base_tag_passthrough(self):
        editor = DICOMEditor()
        tag = Tag(0x0010, 0x0010)
        assert editor.parse_tag(tag) is tag

    def test_tuple_input(self):
        editor = DICOMEditor()
        result = editor.parse_tag((0x0010, 0x0010))
        assert result == Tag(0x0010, 0x0010)

    def test_string_with_parens(self):
        editor = DICOMEditor()
        result = editor.parse_tag("(0010,0010)")
        assert result == Tag(0x0010, 0x0010)

    def test_string_without_parens(self):
        editor = DICOMEditor()
        result = editor.parse_tag("0010,0010")
        assert result == Tag(0x0010, 0x0010)

    def test_string_with_0x_prefix(self):
        editor = DICOMEditor()
        result = editor.parse_tag("0x0010,0x0010")
        assert result == Tag(0x0010, 0x0010)

    def test_string_with_whitespace(self):
        editor = DICOMEditor()
        result = editor.parse_tag(" (0010, 0010) ")
        assert result == Tag(0x0010, 0x0010)

    def test_invalid_format_wrong_part_count_raises(self):
        editor = DICOMEditor()
        with pytest.raises(ValueError, match="Invalid tag format"):
            editor.parse_tag("0010")

    def test_invalid_hex_raises(self):
        editor = DICOMEditor()
        with pytest.raises(ValueError, match="Invalid tag format"):
            editor.parse_tag("zzzz,0010")

    def test_invalid_type_raises(self):
        editor = DICOMEditor()
        with pytest.raises(ValueError, match="Invalid tag identifier type"):
            editor.parse_tag(12345)


class TestUpdateTag:
    def test_no_dataset_returns_false(self):
        editor = DICOMEditor()
        assert editor.update_tag("(0010,0010)", "Doe") is False

    def test_update_existing_tag_by_tuple(self):
        ds = _dataset_with_patient_name("Doe^John")
        editor = DICOMEditor(ds)
        result = editor.update_tag((0x0010, 0x0010), "Smith^Jane")
        assert result is True
        assert str(ds.PatientName) == "Smith^Jane"

    def test_create_new_tag_with_explicit_vr(self):
        ds = Dataset()
        editor = DICOMEditor(ds)
        result = editor.update_tag((0x0010, 0x0010), "Doe^John", vr="PN")
        assert result is True
        assert str(ds.PatientName) == "Doe^John"

    def test_create_new_tag_infers_vr_from_dictionary(self):
        ds = Dataset()
        editor = DICOMEditor(ds)
        # (0010,0020) is PatientID, dictionary VR is LO
        result = editor.update_tag((0x0010, 0x0020), "12345")
        assert result is True
        assert str(ds.PatientID) == "12345"

    def test_create_new_tag_unknown_defaults_to_lo(self):
        ds = Dataset()
        editor = DICOMEditor(ds)
        # Private/unassigned tag group+element unlikely to be in the dictionary
        result = editor.update_tag((0x0009, 0x0001), "value")
        assert result is True
        elem = ds[Tag(0x0009, 0x0001)]
        assert elem.VR == "LO"

    def test_update_syncs_frame_wrapper_existing_tag(self):
        original = _dataset_with_patient_name("Doe^John")
        wrapper = Dataset()
        wrapper.PatientName = "Doe^John"
        wrapper._original_dataset = original
        editor = DICOMEditor(wrapper)
        result = editor.update_tag((0x0010, 0x0010), "Smith^Jane")
        assert result is True
        assert str(original.PatientName) == "Smith^Jane"
        assert str(wrapper.PatientName) == "Smith^Jane"

    def test_update_adds_to_frame_wrapper_when_missing(self):
        original = Dataset()
        wrapper = Dataset()
        wrapper._original_dataset = original
        editor = DICOMEditor(wrapper)
        result = editor.update_tag((0x0010, 0x0020), "12345")
        assert result is True
        assert str(original.PatientID) == "12345"
        assert str(wrapper.PatientID) == "12345"

    def test_update_infers_vr_when_adding_missing_tag_to_wrapper(self):
        original = Dataset()
        original.PatientID = "old-id"
        wrapper = Dataset()
        wrapper._original_dataset = original
        editor = DICOMEditor(wrapper)
        result = editor.update_tag((0x0010, 0x0020), "new-id")
        assert result is True
        assert str(original.PatientID) == "new-id"
        assert str(wrapper.PatientID) == "new-id"
        assert wrapper[Tag(0x0010, 0x0020)].VR == "LO"

    def test_update_wrapper_add_falls_back_to_lo_when_vr_lookup_fails(self):
        original = Dataset()
        original.add_new((0x0009, 0x0001), "LO", "old-value")
        wrapper = Dataset()
        wrapper._original_dataset = original
        editor = DICOMEditor(wrapper)
        result = editor.update_tag((0x0009, 0x0001), "new-value")
        assert result is True
        assert wrapper[Tag(0x0009, 0x0001)].VR == "LO"
        assert str(wrapper[Tag(0x0009, 0x0001)].value) == "new-value"

    def test_update_adds_to_frame_wrapper_unknown_vr_defaults_lo(self):
        original = Dataset()
        wrapper = Dataset()
        wrapper._original_dataset = original
        editor = DICOMEditor(wrapper)
        result = editor.update_tag((0x0009, 0x0001), "value")
        assert result is True
        assert wrapper[Tag(0x0009, 0x0001)].VR == "LO"

    def test_invalid_tag_identifier_returns_false(self):
        ds = Dataset()
        editor = DICOMEditor(ds)
        result = editor.update_tag("invalid-format", "value")
        assert result is False

    def test_update_nested_path_writes_containing_sequence_item_only(self):
        ds = _dataset_with_nested_code_meaning()
        editor = DICOMEditor(ds)

        result = editor.update_tag("(0012, 0064)[0].(0008, 0104)", "New nested meaning", vr="LO")

        assert result is True
        assert ds[Tag(0x0008, 0x0104)].value == "Root meaning"
        assert ds[Tag(0x0012, 0x0064)].value[0][Tag(0x0008, 0x0104)].value == (
            "New nested meaning"
        )

    def test_update_unresolvable_nested_path_returns_false_and_mutates_nothing(self):
        ds = _dataset_with_nested_code_meaning()
        editor = DICOMEditor(ds)

        result = editor.update_tag("(0012, 0064)[1].(0008, 0104)", "Should not write", vr="LO")

        assert result is False
        assert ds[Tag(0x0008, 0x0104)].value == "Root meaning"
        assert ds[Tag(0x0012, 0x0064)].value[0][Tag(0x0008, 0x0104)].value == (
            "Nested meaning"
        )

    def test_update_sequence_parent_returns_false(self):
        ds = _dataset_with_nested_code_meaning()
        editor = DICOMEditor(ds)

        result = editor.update_tag("(0012, 0064)", "Not a sequence", vr="LO")

        assert result is False
        assert isinstance(ds[Tag(0x0012, 0x0064)].value, Sequence)


class TestConvertValue:
    def test_none_vr_returns_value_unchanged(self):
        editor = DICOMEditor()
        assert editor._convert_value("abc", None) == "abc"

    def test_float_vr_valid(self):
        editor = DICOMEditor()
        assert editor._convert_value("3.5", "FL") == 3.5
        assert editor._convert_value("3.5", "FD") == 3.5

    def test_float_vr_invalid_returns_original(self):
        editor = DICOMEditor()
        assert editor._convert_value("not-a-number", "FL") == "not-a-number"

    def test_integer_vr_valid(self):
        editor = DICOMEditor()
        for vr in ("SL", "SS", "UL", "US"):
            assert editor._convert_value("42", vr) == 42

    def test_integer_vr_invalid_returns_original(self):
        editor = DICOMEditor()
        assert editor._convert_value("not-a-number", "US") == "not-a-number"

    def test_string_vr_converts_to_str(self):
        editor = DICOMEditor()
        assert editor._convert_value(123, "LO") == "123"

    def test_string_vr_none_value_becomes_empty_string(self):
        editor = DICOMEditor()
        assert editor._convert_value(None, "LO") == ""

    def test_unknown_vr_returns_value_unchanged(self):
        editor = DICOMEditor()
        assert editor._convert_value([1, 2, 3], "SQ") == [1, 2, 3]

    def test_vr_case_insensitive(self):
        editor = DICOMEditor()
        assert editor._convert_value("3.5", "fl") == 3.5


class TestDeleteTag:
    def test_no_dataset_returns_false(self):
        editor = DICOMEditor()
        assert editor.delete_tag((0x0010, 0x0010)) is False

    def test_required_group_0000_cannot_delete(self):
        ds = Dataset()
        editor = DICOMEditor(ds)
        assert editor.delete_tag((0x0000, 0x0001)) is False

    def test_required_group_0002_cannot_delete(self):
        ds = Dataset()
        editor = DICOMEditor(ds)
        assert editor.delete_tag((0x0002, 0x0001)) is False

    def test_required_group_0008_cannot_delete(self):
        ds = Dataset()
        editor = DICOMEditor(ds)
        assert editor.delete_tag((0x0008, 0x0001)) is False

    def test_delete_existing_tag(self):
        ds = _dataset_with_patient_name("Doe^John")
        editor = DICOMEditor(ds)
        result = editor.delete_tag((0x0010, 0x0010))
        assert result is True
        assert "PatientName" not in ds

    def test_delete_missing_tag_returns_false(self):
        ds = Dataset()
        editor = DICOMEditor(ds)
        assert editor.delete_tag((0x0010, 0x0010)) is False

    def test_delete_syncs_frame_wrapper(self):
        original = _dataset_with_patient_name("Doe^John")
        wrapper = Dataset()
        wrapper.PatientName = "Doe^John"
        wrapper._original_dataset = original
        editor = DICOMEditor(wrapper)
        result = editor.delete_tag((0x0010, 0x0010))
        assert result is True
        assert "PatientName" not in original
        assert "PatientName" not in wrapper

    def test_invalid_tag_identifier_returns_false(self):
        ds = Dataset()
        editor = DICOMEditor(ds)
        assert editor.delete_tag("invalid-format") is False

    def test_delete_from_original_skips_wrapper_when_tag_not_in_wrapper(self):
        original = _dataset_with_patient_name("Doe^John")
        wrapper = Dataset()
        wrapper._original_dataset = original
        editor = DICOMEditor(wrapper)
        result = editor.delete_tag((0x0010, 0x0010))
        assert result is True
        assert "PatientName" not in original
