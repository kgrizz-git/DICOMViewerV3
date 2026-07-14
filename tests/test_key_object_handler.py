"""Unit tests for core.key_object_handler.KeyObjectHandler."""

from __future__ import annotations

from types import SimpleNamespace

from core.key_object_handler import KeyObjectHandler


def _content_item(**kwargs):
    return SimpleNamespace(**kwargs)


class TestParseKeyObject:
    def test_no_content_sequence_returns_empty_annotations(self):
        handler = KeyObjectHandler()
        dataset = SimpleNamespace()
        result = handler.parse_key_object(dataset)
        assert result == {"annotations": [], "referenced_images": []}

    def test_with_content_sequence_parses_annotations_and_images(self):
        handler = KeyObjectHandler()
        ref_item = _content_item(ReferencedSOPInstanceUID="1.2.3")
        content_item = _content_item(
            ConceptNameCodeSequence=[_content_item(CodeMeaning="Finding")],
            TextValue="hello",
            ReferencedSOPSequence=[ref_item],
        )
        dataset = SimpleNamespace(ContentSequence=[content_item])
        result = handler.parse_key_object(dataset)
        assert result["referenced_images"] == ["1.2.3"]
        assert len(result["annotations"]) == 1
        assert result["annotations"][0]["type"] == "Finding"
        assert result["annotations"][0]["text"] == "hello"


class TestGetReferencedImages:
    def test_no_content_sequence_returns_empty_list(self):
        handler = KeyObjectHandler()
        assert handler.get_referenced_images(SimpleNamespace()) == []

    def test_exception_during_extraction_returns_empty_list(self):
        handler = KeyObjectHandler()
        # A non-iterable ContentSequence triggers a TypeError during iteration,
        # which get_referenced_images swallows and reports as an empty list.
        dataset = SimpleNamespace(ContentSequence=object())
        result = handler.get_referenced_images(dataset)
        assert result == []

    def test_hasattr_check_raising_non_attribute_error_is_caught(self):
        handler = KeyObjectHandler()

        class BadDataset:
            @property
            def ContentSequence(self):
                raise RuntimeError("boom")

        result = handler.get_referenced_images(BadDataset())
        assert result == []


class TestExtractUidsFromContentSequence:
    def test_extracts_uids_and_dedupes(self):
        handler = KeyObjectHandler()
        ref_seq = [
            _content_item(ReferencedSOPInstanceUID="1.1"),
            _content_item(ReferencedSOPInstanceUID="1.1"),
            _content_item(ReferencedSOPInstanceUID="1.2"),
        ]
        content_seq = [_content_item(ReferencedSOPSequence=ref_seq)]
        uids = handler._extract_uids_from_content_sequence(content_seq)
        assert uids == ["1.1", "1.2"]

    def test_recurses_into_nested_content_sequence(self):
        handler = KeyObjectHandler()
        nested = [_content_item(ReferencedSOPSequence=[_content_item(ReferencedSOPInstanceUID="2.1")])]
        content_seq = [_content_item(ContentSequence=nested)]
        uids = handler._extract_uids_from_content_sequence(content_seq)
        assert uids == ["2.1"]

    def test_nested_duplicate_uid_not_added_twice(self):
        handler = KeyObjectHandler()
        nested = [_content_item(ReferencedSOPSequence=[_content_item(ReferencedSOPInstanceUID="3.1")])]
        content_seq = [
            _content_item(
                ReferencedSOPSequence=[_content_item(ReferencedSOPInstanceUID="3.1")],
                ContentSequence=nested,
            )
        ]
        uids = handler._extract_uids_from_content_sequence(content_seq)
        assert uids == ["3.1"]

    def test_item_without_referenced_sop_uid_attr_skipped(self):
        handler = KeyObjectHandler()
        content_seq = [_content_item(ReferencedSOPSequence=[_content_item()])]
        uids = handler._extract_uids_from_content_sequence(content_seq)
        assert uids == []

    def test_exception_on_bad_iteration_returns_partial_list(self):
        handler = KeyObjectHandler()

        class ExplodingSeq:
            def __iter__(self):
                raise TypeError("not iterable")

        uids = handler._extract_uids_from_content_sequence(ExplodingSeq())
        assert uids == []


class TestParseContentSequence:
    def test_concept_name_uses_code_meaning(self):
        handler = KeyObjectHandler()
        content_seq = [_content_item(ConceptNameCodeSequence=[_content_item(CodeMeaning="Finding")])]
        annotations = handler.parse_content_sequence(content_seq)
        assert annotations[0]["type"] == "Finding"

    def test_concept_name_falls_back_to_code_value(self):
        handler = KeyObjectHandler()
        content_seq = [_content_item(ConceptNameCodeSequence=[_content_item(CodeValue="121071")])]
        annotations = handler.parse_content_sequence(content_seq)
        assert annotations[0]["type"] == "121071"

    def test_empty_concept_name_sequence_leaves_type_blank(self):
        handler = KeyObjectHandler()
        content_seq = [_content_item(ConceptNameCodeSequence=[], TextValue="note")]
        annotations = handler.parse_content_sequence(content_seq)
        assert annotations[0]["type"] == ""
        assert annotations[0]["text"] == "note"

    def test_measured_value_numeric_conversion_success(self):
        handler = KeyObjectHandler()
        measured = _content_item(NumericValue="12.5")
        content_seq = [_content_item(MeasuredValueSequence=[measured], TextValue="x")]
        annotations = handler.parse_content_sequence(content_seq)
        assert annotations[0]["value"] == 12.5

    def test_measured_value_numeric_conversion_failure_keeps_value_none(self):
        handler = KeyObjectHandler()
        measured = _content_item(NumericValue="not-a-number")
        content_seq = [_content_item(MeasuredValueSequence=[measured], TextValue="x")]
        annotations = handler.parse_content_sequence(content_seq)
        assert annotations[0]["value"] is None

    def test_measurement_units_extracted(self):
        handler = KeyObjectHandler()
        units = _content_item(CodeMeaning="mm")
        measured = _content_item(NumericValue="5", MeasurementUnitsCodeSequence=[units])
        content_seq = [_content_item(MeasuredValueSequence=[measured], TextValue="x")]
        annotations = handler.parse_content_sequence(content_seq)
        assert annotations[0]["units"] == "mm"

    def test_empty_measured_value_sequence_leaves_value_none(self):
        handler = KeyObjectHandler()
        content_seq = [_content_item(MeasuredValueSequence=[], TextValue="x")]
        annotations = handler.parse_content_sequence(content_seq)
        assert annotations[0]["value"] is None

    def test_referenced_images_attached_to_annotation(self):
        handler = KeyObjectHandler()
        ref_item = _content_item(ReferencedSOPInstanceUID="9.9")
        content_seq = [_content_item(TextValue="x", ReferencedSOPSequence=[ref_item])]
        annotations = handler.parse_content_sequence(content_seq)
        assert annotations[0]["referenced_images"] == ["9.9"]

    def test_item_with_no_content_is_not_added(self):
        handler = KeyObjectHandler()
        content_seq = [_content_item()]
        annotations = handler.parse_content_sequence(content_seq)
        assert annotations == []

    def test_recurses_into_nested_content_sequence(self):
        handler = KeyObjectHandler()
        nested = [_content_item(TextValue="nested-text")]
        content_seq = [_content_item(TextValue="outer", ContentSequence=nested)]
        annotations = handler.parse_content_sequence(content_seq)
        assert len(annotations) == 2
        assert annotations[0]["text"] == "outer"
        assert annotations[1]["text"] == "nested-text"

    def test_exception_on_bad_iteration_returns_partial_list(self):
        handler = KeyObjectHandler()

        class ExplodingSeq:
            def __iter__(self):
                raise TypeError("not iterable")

        annotations = handler.parse_content_sequence(ExplodingSeq())
        assert annotations == []
