"""Round-three coverage for the synthetic SR document tree helpers."""

from __future__ import annotations

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence

from core.sr_document_tree import (
    _concept_display,
    _concept_tuple,
    _format_code,
    _format_composite_ref,
    _format_container,
    _format_datetime_like,
    _format_image_ref,
    _format_num,
    _format_pname,
    _format_sc_coord,
    _format_text,
    _format_uid_reference,
    _format_waveform,
    _relationship_str,
    _value_and_reference,
    _value_type_str,
    build_sr_document_tree,
    path_to_node_id_map,
    sr_tree_to_json_dict,
)


def _code(value: str = "C-1", scheme: str = "99SYN", meaning: str = "Synthetic concept") -> Dataset:
    item = Dataset()
    item.CodeValue = value
    item.CodingSchemeDesignator = scheme
    item.CodeMeaning = meaning
    return item


def _item(value_type: str, **attrs: object) -> Dataset:
    item = Dataset()
    if value_type != value_type.strip():
        # Exercise the formatter's normalization without pydicom validating
        # the deliberately non-DICOM fixture value as VR CS.
        object.__setattr__(item, "ValueType", value_type)
    else:
        item.ValueType = value_type
    for name, value in attrs.items():
        if name in {"ReferencedStudyInstanceUID", "ReferencedSeriesInstanceUID", "StringValue"}:
            # These are formatter-only fallbacks, not pydicom dictionary
            # keywords; keep them as in-memory attributes without warnings.
            object.__setattr__(item, name, value)
            continue
        try:
            setattr(item, name, value)
        except ValueError:
            # A few formatter-facing keywords are ambiguous in pydicom's
            # dictionary; keep this fixture in-memory without adding a file.
            object.__setattr__(item, name, value)
    return item


def test_concept_and_scalar_formatters_cover_present_and_missing_values() -> None:
    coded = _item("TEXT", ConceptNameCodeSequence=DicomSequence([_code()]))
    assert _concept_tuple(coded) == ("C-1", "99SYN")
    assert _concept_display(coded) == "Synthetic concept (C-1, 99SYN)"
    assert _concept_tuple(Dataset()) == (None, None)
    assert _concept_display(Dataset()) == "(no concept name)"

    partial = _item("TEXT", ConceptNameCodeSequence=DicomSequence([_code("C-2", "", "")]))
    assert _concept_display(partial) == "C-2, ?"
    assert _relationship_str(_item("TEXT", RelationshipType=" CONTAINS ")) == "CONTAINS"
    assert _relationship_str(Dataset()) == ""
    assert _value_type_str(_item(" text ")) == "text"
    assert _value_type_str(Dataset()) == ""

    assert _format_text(_item("TEXT", TextValue="  hello  ")) == "hello"
    assert _format_text(Dataset()) == ""
    assert _format_pname(_item("PNAME", PersonName="  Synthetic^Person  ")) == "Synthetic^Person"
    assert _format_pname(Dataset()) == ""


def test_value_formatters_cover_num_code_datetime_uid_and_references() -> None:
    units = _code("mm", "UCUM", "millimeter")
    measured = Dataset()
    measured.NumericValue = "12.5"
    measured.FloatingPointValue = 12.5
    measured.MeasurementUnitsCodeSequence = DicomSequence([units])
    num = _item("NUM", MeasuredValueSequence=DicomSequence([measured]))
    assert _format_num(num) == "12.5 12.5 millimeter"
    assert _format_num(_item("NUM", MeasuredValueSequence=DicomSequence())) == ""

    code = _item("CODE", ConceptCodeSequence=DicomSequence([_code("C-3", "99SYN", "A code")]))
    assert _format_code(code) == "A code — C-3 — 99SYN"
    assert _format_code(_item("CODE", ConceptCodeSequence=DicomSequence())) == ""

    assert _format_datetime_like(_item("DATE", Date="20260101")) == "Date=20260101"
    assert _format_datetime_like(_item("TIME", Time="120000")) == "Time=120000"
    assert _format_datetime_like(Dataset()) == ""
    uid_item = _item(
        "IMAGE",
        ReferencedStudyInstanceUID="1.2.3",
        ReferencedSeriesInstanceUID="1.2.3.4",
        ReferencedSOPInstanceUID="1.2.3.4.5",
    )
    expected = "Study=1.2.3; Series=1.2.3.4; SOP=1.2.3.4.5"
    assert _format_uid_reference(uid_item) == expected
    assert _format_image_ref(uid_item) == expected
    assert _format_composite_ref(uid_item) == expected
    assert _value_and_reference(_item("UIDREF", UID="9.8.7")) == ("9.8.7", "")
    assert _value_and_reference(uid_item) == ("", expected)


def test_value_formatters_cover_waveform_scoord_container_and_fallbacks() -> None:
    waveform = _item(
        "WAVEFORM",
        NumberOfChannels=2,
        NumberOfWaveformSamples=100,
        ReferencedSOPInstanceUID="1.2.840.1",
    )
    assert _format_waveform(waveform) == "channels=2, samples=100, SOP=1.2.840.1"
    assert _format_waveform(_item("WAVEFORM")) == "(waveform)"

    coord = _item("SCOORD", GraphicType="POLYLINE", GraphicData=[0.0, 1.0, 2.0, 3.0])
    assert _format_sc_coord(coord) == "type=POLYLINE, values=4"
    assert _format_sc_coord(_item("SCOORD")) == "type=?, values=0"

    template = Dataset()
    template.MappingResource = "99SYN"
    template.TemplateIdentifier = "T1"
    container = _item(
        "CONTAINER",
        ContinuityOfContent="SEPARATE",
        ContentTemplateSequence=DicomSequence([template]),
    )
    assert _format_container(container) == "continuity=SEPARATE; template=99SYN:T1"
    assert _value_and_reference(container) == (_format_container(container), "")
    assert _value_and_reference(_item("TCOORD")) == ("(temporal coordinates)", "")
    assert _value_and_reference(_item("OTHER", StringValue="fallback")) == ("fallback", "")
    assert _value_and_reference(_item("OTHER")) == ("", "")


def test_tree_walk_tracks_parents_depth_paths_and_serializes_nested_content() -> None:
    child = _item("TEXT", TextValue="child", RelationshipType="CONTAINS")
    root = _item(
        "CONTAINER",
        RelationshipType="CONTAINS",
        ConceptNameCodeSequence=DicomSequence([_code("ROOT", "99SYN", "Root")]),
        ContentSequence=DicomSequence([child]),
    )
    sibling = _item("PNAME", PersonName="Synthetic^Name", RelationshipType="HAS OBS CONTEXT")
    ds = Dataset()
    ds.ContentSequence = DicomSequence([root, sibling])

    tree = build_sr_document_tree(ds)
    assert tree.total_nodes == 3
    assert [node.path_indices for node in tree.roots] == [(0,), (1,)]
    nested = tree.roots[0].children[0]
    assert nested.parent is tree.roots[0]
    assert nested.depth == 1
    assert nested.path_indices == (0, 0)
    assert path_to_node_id_map(tree) == {(0,): 0, (0, 0): 1, (1,): 2}

    exported = sr_tree_to_json_dict(tree)
    assert exported["truncated"] is False
    assert exported["total_nodes"] == 3
    assert exported["warnings"] == []
    assert exported["roots"][0]["children"][0]["value"] == "child"
    assert exported["roots"][0]["path_indices"] == [0]


def test_tree_walk_sets_warnings_for_missing_empty_and_depth_limited_sequences() -> None:
    missing = build_sr_document_tree(Dataset())
    assert missing.roots == []
    assert missing.truncated is False
    assert "no ContentSequence" in missing.warnings[0]

    empty = Dataset()
    empty.ContentSequence = DicomSequence()
    assert "no ContentSequence" in build_sr_document_tree(empty).warnings[0]

    grandchild = _item("TEXT", TextValue="grandchild")
    child = _item("CONTAINER", ContentSequence=DicomSequence([grandchild]))
    root = _item("CONTAINER", ContentSequence=DicomSequence([child]))
    ds = Dataset()
    ds.ContentSequence = DicomSequence([root])
    depth_limited = build_sr_document_tree(ds, max_depth=1)
    assert depth_limited.total_nodes == 2
    assert depth_limited.truncated is True
    assert any("max_depth=1" in warning for warning in depth_limited.warnings)


def test_tree_walk_stops_at_node_cap_and_reports_total() -> None:
    ds = Dataset()
    ds.ContentSequence = DicomSequence([_item("TEXT", TextValue=str(index)) for index in range(3)])
    tree = build_sr_document_tree(ds, max_nodes=2)
    assert tree.total_nodes == 2
    assert len(tree.roots) == 2
    assert tree.truncated is True
    assert tree.node_by_id.keys() == {0, 1}
    assert any("max_nodes=2" in warning for warning in tree.warnings)
