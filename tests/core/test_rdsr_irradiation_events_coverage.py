"""Focused synthetic coverage for RDSR irradiation-event normalization guards."""

from __future__ import annotations

from types import SimpleNamespace

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence as DicomSequence
from pydicom.uid import EnhancedXRayRadiationDoseSRStorage, generate_uid

from core.rdsr_irradiation_events import (
    FlattenedSubtree,
    IrradiationEventExtraction,
    IrradiationEventRow,
    _best_code_display_for_concept,
    _best_text_for_concept,
    _code_value_display,
    _concept_column_title,
    _concept_meta,
    _datetime_value,
    _flatten_descendants,
    _format_item_value,
    _measurement_units_display_from_num_item,
    _mv_numeric_segment,
    _mv_with_units_segment,
    _num_value_from_item,
    _text_or_code_by_concept,
    _uidref_value,
    attach_tree_node_ids,
    extract_irradiation_events,
)


def _code(cv: str = "", scheme: str = "", meaning: str = "") -> Dataset:
    item = Dataset()
    if cv:
        item.CodeValue = cv
    if scheme:
        item.CodingSchemeDesignator = scheme
    if meaning:
        item.CodeMeaning = meaning
    return item


def _item(value_type: str, cv: str, meaning: str, *, value: str = "") -> Dataset:
    item = Dataset()
    item.ValueType = value_type
    item.ConceptNameCodeSequence = DicomSequence([_code(cv, "DCM", meaning)])
    item.RelationshipType = "CONTAINS"
    if value_type == "NUM":
        measured = Dataset()
        measured.NumericValue = value
        item.MeasuredValueSequence = DicomSequence([measured])
    elif value_type == "TEXT":
        item.TextValue = value
    return item


def _event(children: list[Dataset], *, code: str = "113706") -> Dataset:
    event = _item("CONTAINER", code, "Irradiation Event X-Ray Data")
    event.ContentSequence = DicomSequence(children)
    return event


def _dose_sr(children: list[Dataset]) -> Dataset:
    root = _item("CONTAINER", "113701", "CT Radiation Dose")
    root.ContentSequence = DicomSequence([_event(children)])
    ds = Dataset()
    ds.Modality = "SR"
    ds.SOPClassUID = str(EnhancedXRayRadiationDoseSRStorage)
    ds.SOPInstanceUID = generate_uid()
    ds.ContentSequence = DicomSequence([root])
    return ds


def test_concept_and_measurement_format_guards() -> None:
    assert _concept_meta(Dataset()) == ("", "", "")
    assert _concept_column_title(_item("TEXT", "", "", value="x")) == "Concept"
    partial = _item("TEXT", "9", "", value="x")
    partial.ConceptNameCodeSequence = DicomSequence([_code("9", "", "")])
    assert _concept_column_title(partial) == "Concept"

    mv = SimpleNamespace(FloatingPointValue=["2.5", "9.0"])
    assert _mv_numeric_segment(mv) == "2.5"
    mv.FloatingPointValue = "not-a-number"
    assert _mv_numeric_segment(mv) == "not-a-number"
    del mv.FloatingPointValue
    assert _mv_numeric_segment(mv) == ""

    mv.CodeValue = "bad"
    assert _mv_with_units_segment(mv) == ""
    assert _num_value_from_item(_item("TEXT", "1", "not numeric", value="x")) == ""
    assert _num_value_from_item(_item("NUM", "1", "empty")) == ""


def test_code_text_datetime_uid_and_unknown_value_format_guards() -> None:
    assert _code_value_display(_item("TEXT", "1", "not code", value="x")) == ""
    code = _item("CODE", "1", "Code")
    code.ConceptCodeSequence = DicomSequence([_code("", "", "Meaning")])
    assert _code_value_display(code) == "Meaning"
    code.ConceptCodeSequence = DicomSequence([_code("7", "SRT", "")])
    assert _code_value_display(code) == "7 — SRT"
    code.ConceptCodeSequence = DicomSequence([_code("7", "", "")])
    assert _code_value_display(code) == "7"
    code.ConceptCodeSequence = DicomSequence([])
    assert _code_value_display(code) == ""

    dt = _item("DATETIME", "1", "time")
    dt.Time = "1234"
    assert _datetime_value(dt) == "Time=1234"
    assert _format_item_value(dt) == "Time=1234"
    assert _format_item_value(_item("IMAGE", "1", "image")) == ""

    uid = _item("UIDREF", "1", "uid")
    uid.ReferencedSOPInstanceUID = "1.2.3"
    assert _uidref_value(uid) == "ReferencedSOPInstanceUID=1.2.3"
    uid.UID = "4.5.6"
    assert _uidref_value(uid) == "4.5.6"
    assert _format_item_value(uid) == "4.5.6"


def test_flatten_depth_cap_and_units_codevalue_fallback() -> None:
    leaf = _item("TEXT", "9", "Leaf", value="value")
    middle = _event([leaf])
    root = _event([middle])
    flat = _flatten_descendants(root, max_depth=1)
    assert isinstance(flat, FlattenedSubtree)
    assert flat.truncated is True
    assert len(flat.items) == 1

    num = _item("NUM", "122130", "DAP", value="3.0")
    mv = num.MeasuredValueSequence[0]
    units = _code("Gy", "UCUM", "")
    mv.MeasurementUnitsCodeSequence = DicomSequence([units])
    assert _measurement_units_display_from_num_item(num) == "Gy"
    assert _format_item_value(num) == "3.0 Gy"


def test_concept_selection_ambiguity_and_reference_point_code_text() -> None:
    first = _item("CODE", "113721", "Event type")
    first.ConceptCodeSequence = DicomSequence([_code("A", "SRT", "First")])
    second = _item("CODE", "113721", "Event type")
    second.ConceptCodeSequence = DicomSequence([_code("B", "SRT", "Second")])
    notes: list[str] = []
    assert _best_code_display_for_concept(
        ((first, 1), (second, 1)), ("113721", "DCM"), label="event", notes=notes
    ) == "First — A — SRT"
    assert any("Ambiguous CODE" in note for note in notes)

    text1 = _item("TEXT", "113780", "Reference point", value="first")
    text2 = _item("TEXT", "113780", "Reference point", value="second")
    notes.clear()
    assert _best_text_for_concept(
        ((text1, 1), (text2, 1)), ("113780", "DCM"), label="reference", notes=notes
    ) == "first"
    assert any("Ambiguous TEXT" in note for note in notes)
    assert _text_or_code_by_concept(((text1, 1),), ("113780", "DCM"), []) == "first"


def test_public_extraction_normalization_fallbacks_and_guards() -> None:
    detector = _item("NUM", "private", "Final Source to Detector Distance", value="800")
    orientation = _item("TEXT", "private2", "Patient Orientation", value="head first")
    started = _item("DATETIME", "111526", "DateTime started")
    started.DateTime = "20260101120000"
    uid = _item("UIDREF", "113769", "Irradiation Event UID")
    uid.ReferencedSOPInstanceUID = "1.2.3"
    ex = extract_irradiation_events(_dose_sr([detector, orientation, started, uid]), node_id_start=8)
    row = ex.rows[0]
    assert row.node_id_placeholder == 8
    assert row.columns["Source-to-detector distance (mm)"] == "800.0"
    assert row.columns["Final source-to-detector distance (mm)"] == "800.0"
    assert row.columns["Patient orientation"] == "head first"
    assert row.columns["DateTime started"] == "DateTime=20260101120000"
    assert row.columns["Irradiation event UID"] == "ReferencedSOPInstanceUID=1.2.3"

    attach_tree_node_ids(ex, {(1, 0): 44})
    assert row.node_id_placeholder == 8
    attach_tree_node_ids(ex, {(0, 0): 44})
    assert row.node_id_placeholder == 44

    empty = Dataset()
    no_content = extract_irradiation_events(empty)
    assert no_content.rows == []
    assert no_content.notes == ["No ContentSequence."]
    ds = Dataset()
    ds.ContentSequence = DicomSequence([_item("TEXT", "1", "Not an event", value="x")])
    no_event = extract_irradiation_events(ds)
    assert no_event.rows == []
    assert any("No irradiation event containers" in note for note in no_event.notes)


def test_non_dose_sr_event_still_extracts_with_warning() -> None:
    ds = _dose_sr([_item("TEXT", "99", "Vendor note", value="kept")])
    ds.SOPClassUID = "1.2.3"
    ex = extract_irradiation_events(ds)
    assert len(ex.rows) == 1
    assert any("Not a recognized radiation dose SR" in note for note in ex.notes)
    assert ex.rows[0].columns["Vendor note (99, DCM)"] == "kept"


def test_attach_tree_node_ids_does_not_change_unmapped_rows() -> None:
    row = IrradiationEventRow(3, (2,), "DCM")
    extraction = IrradiationEventExtraction(rows=[row], notes=[])
    attach_tree_node_ids(extraction, {(1,): 9})
    assert row.node_id_placeholder == 3
