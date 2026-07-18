"""Tests for core.dicom_parser metadata extraction and frame-rate parsing."""

from __future__ import annotations

from pydicom.dataset import Dataset
from pydicom.sequence import Sequence
from pydicom.tag import Tag

from core import dicom_parser
from core.dicom_parser import DICOMParser, get_frame_rate_from_dicom


def _code_item(code="113100", scheme="DCM", meaning="Basic Application") -> Dataset:
    item = Dataset()
    item.CodeValue = code
    item.CodingSchemeDesignator = scheme
    item.CodeMeaning = meaning
    return item


def _basic_dataset() -> Dataset:
    ds = Dataset()
    ds.PatientName = "Doe^Jane"
    ds.PatientID = "PID1"
    ds.StudyDescription = "Head"
    ds.Modality = "CT"
    return ds


# --------------------------------------------------------------------------- #
# module helpers
# --------------------------------------------------------------------------- #

def test_is_code_sequence_true_and_false() -> None:
    assert dicom_parser._is_code_sequence([_code_item()]) is True
    assert dicom_parser._is_code_sequence([]) is False
    assert dicom_parser._is_code_sequence([Dataset()]) is False


def test_format_code_sequence_summary() -> None:
    out = dicom_parser._format_code_sequence_summary([_code_item(code="X", scheme="DCM", meaning="Foo")])
    assert out == "X DCM: Foo"


# --------------------------------------------------------------------------- #
# get_all_tags
# --------------------------------------------------------------------------- #

def test_get_all_tags_none_dataset() -> None:
    assert DICOMParser(None).get_all_tags() == {}


def test_get_all_tags_basic_and_cache() -> None:
    p = DICOMParser(_basic_dataset())
    tags = p.get_all_tags()
    assert any(row["keyword"] == "PatientName" for row in tags.values())
    # Second call returns the identical cached object.
    assert p.get_all_tags() is tags


def test_get_all_tags_privacy_mode_masks_patient() -> None:
    p = DICOMParser(_basic_dataset())
    tags = p.get_all_tags(privacy_mode=True)
    pn = next(row for row in tags.values() if row["keyword"] == "PatientName")
    assert pn["value"] == "PRIVACY MODE"


def test_get_all_tags_excludes_private_when_requested() -> None:
    ds = _basic_dataset()
    ds.add_new(Tag(0x0009, 0x0010), "LO", "ACME")  # private creator (odd group)
    with_priv = DICOMParser(ds).get_all_tags(include_private=True)
    without = DICOMParser(ds).get_all_tags(include_private=False)
    assert any(row["is_private"] for row in with_priv.values())
    assert not any(row["is_private"] for row in without.values())


def test_get_all_tags_sequence_summary_vs_expanded() -> None:
    ds = Dataset()
    seq_item = Dataset()
    seq_item.PatientName = "Inner"
    ds.ReferencedImageSequence = Sequence([seq_item])

    summary = DICOMParser(ds).get_all_tags(include_sequences=False)
    seq_row = next(row for row in summary.values() if row["row_kind"] == "sequence")
    assert "item(s)" in str(seq_row["value"])
    # No item/leaf rows when not expanding.
    assert not any(row["row_kind"] == "item" for row in summary.values())

    expanded = DICOMParser(ds).get_all_tags(include_sequences=True)
    assert any(row["row_kind"] == "item" for row in expanded.values())


def test_get_all_tags_code_sequence_summary() -> None:
    ds = Dataset()
    ds.ProcedureCodeSequence = Sequence([_code_item(code="P1", scheme="DCM", meaning="Proc")])
    tags = DICOMParser(ds).get_all_tags()
    row = next(r for r in tags.values() if r["row_kind"] == "sequence")
    assert "Proc" in str(row["value"])


# --------------------------------------------------------------------------- #
# tag lookups
# --------------------------------------------------------------------------- #

def test_get_tag_value_tuple_and_missing() -> None:
    ds = _basic_dataset()
    p = DICOMParser(ds)
    assert p.get_tag_value((0x0010, 0x0020)) == "PID1"  # PatientID
    assert p.get_tag_value((0x0010, 0x1234), default="X") == "X"
    assert DICOMParser(None).get_tag_value((0x0010, 0x0020), default="D") == "D"


def test_get_tag_by_keyword() -> None:
    p = DICOMParser(_basic_dataset())
    assert p.get_tag_by_keyword("Modality") == "CT"
    assert p.get_tag_by_keyword("Missing", default="d") == "d"
    assert DICOMParser(None).get_tag_by_keyword("Modality", default="d") == "d"


def test_info_dicts() -> None:
    p = DICOMParser(_basic_dataset())
    assert p.get_patient_info()["PatientID"] == "PID1"
    assert p.get_study_info()["StudyDescription"] == "Head"
    assert p.get_series_info()["Modality"] == "CT"
    assert "SOPInstanceUID" in p.get_image_info()


def test_update_tag_success_and_failure() -> None:
    ds = _basic_dataset()
    p = DICOMParser(ds)
    assert p.update_tag((0x0010, 0x0020), "NEW") is True
    assert ds.PatientID == "NEW"
    # Missing tag -> KeyError inside -> False
    assert p.update_tag((0x0010, 0x9999), "x") is False
    assert DICOMParser(None).update_tag((0x0010, 0x0020), "x") is False


def test_get_private_tags() -> None:
    ds = _basic_dataset()
    ds.add_new(Tag(0x0009, 0x0010), "LO", "ACME")
    priv = DICOMParser(ds).get_private_tags()
    assert all(row["is_private"] for row in priv.values())
    assert len(priv) >= 1


# --------------------------------------------------------------------------- #
# get_frame_rate_from_dicom
# --------------------------------------------------------------------------- #

def test_frame_rate_recommended() -> None:
    ds = Dataset()
    ds.RecommendedDisplayFrameRate = 30
    assert get_frame_rate_from_dicom(ds) == 30.0


def test_frame_rate_cine_rate() -> None:
    ds = Dataset()
    ds.CineRate = 15
    assert get_frame_rate_from_dicom(ds) == 15.0


def test_frame_rate_from_frame_time() -> None:
    ds = Dataset()
    ds.FrameTime = 50  # ms -> 20 fps
    assert get_frame_rate_from_dicom(ds) == 20.0


def test_frame_rate_from_frame_time_vector() -> None:
    ds = Dataset()
    ds.FrameTimeVector = [40, 40, 40]  # avg 40 ms -> 25 fps
    assert get_frame_rate_from_dicom(ds) == 25.0


def test_frame_rate_none_when_absent() -> None:
    assert get_frame_rate_from_dicom(Dataset()) is None
