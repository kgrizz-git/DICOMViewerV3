"""Unit tests for study index metadata string coercion (no ``b'…'`` artifacts)."""

from __future__ import annotations

import os

from pydicom.dataset import Dataset

from core.study_index.metadata_extract import (
    _elem_to_str,
    dataset_to_index_row,
    repair_str_bytes_repr_artifact,
)


def test_elem_to_str_plain_bytes() -> None:
    assert _elem_to_str(b"DOE^JOHN") == "DOE^JOHN"


def test_elem_to_str_bytearray() -> None:
    assert _elem_to_str(bytearray(b"A^B")) == "A^B"


def test_elem_to_str_person_name_like_original_string_bytes() -> None:
    class _FakePN:
        original_string = b"SMITH^JANE"

    assert _elem_to_str(_FakePN()) == "SMITH^JANE"


def test_elem_to_str_none_empty() -> None:
    assert _elem_to_str(None) == ""


def test_repair_str_bytes_repr_artifact_double_quote() -> None:
    assert repair_str_bytes_repr_artifact('b"DOE^JOHN"') == "DOE^JOHN"


def test_elem_to_str_legacy_wrong_string_stored() -> None:
    """Simulates SQLite row where ``str(bytes)`` was stored as text."""
    assert _elem_to_str("b'DOE^JOHN'") == "DOE^JOHN"


def test_dataset_to_index_row_series_description() -> None:
    """``SeriesDescription`` is indexed for FTS-backed study search."""
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3"
    ds.SeriesInstanceUID = "1.2.3.4"
    ds.SOPInstanceUID = "1.2.3.4.5"
    ds.SeriesDescription = "AXIAL T2"
    ds.StudyDescription = "BRAIN"
    ds.Modality = "MR"
    fp = os.path.abspath("/tmp/x.dcm")
    root = os.path.abspath("/tmp")
    row = dataset_to_index_row(ds, file_path=fp, study_root_path=root)
    assert row["series_description"] == "AXIAL T2"
    assert row["study_description"] == "BRAIN"


def test_dataset_to_index_row_all_fields_and_paths() -> None:
    ds = Dataset()
    ds.StudyInstanceUID = "1.2.3"
    ds.SeriesInstanceUID = "1.2.3.4"
    ds.SOPInstanceUID = "1.2.3.4.5"
    ds.PatientName = "DOE^JOHN"
    ds.PatientID = "P123"
    ds.AccessionNumber = "A1"
    ds.StudyDate = "20240101"
    ds.StudyDescription = "BRAIN"
    ds.SeriesDescription = "AXIAL T2"
    ds.Modality = "MR"
    fp = os.path.abspath("/data/im.dcm")
    root = os.path.abspath("/data")
    row = dataset_to_index_row(ds, file_path=fp, study_root_path=root)
    assert row["file_path"] == fp
    assert row["study_root_path"] == root
    assert row["patient_name"] == "DOE^JOHN"
    assert row["patient_id"] == "P123"
    assert row["accession_number"] == "A1"
    assert row["study_date"] == "20240101"
    assert row["modality"] == "MR"
    assert set(row) == {
        "file_path",
        "study_root_path",
        "study_uid",
        "series_uid",
        "sop_instance_uid",
        "patient_name",
        "patient_id",
        "accession_number",
        "study_date",
        "study_description",
        "series_description",
        "modality",
    }


def test_dataset_to_index_row_missing_fields_empty() -> None:
    ds = Dataset()
    row = dataset_to_index_row(ds, file_path="/x.dcm", study_root_path="/")
    assert row["patient_name"] == ""
    assert row["modality"] == ""
    assert row["study_uid"] == ""


def test_repair_str_bytes_repr_artifact_single_quote() -> None:
    assert repair_str_bytes_repr_artifact("b'ABC'") == "ABC"


def test_repair_str_bytes_repr_artifact_too_short() -> None:
    # len < 3 cannot be a b'...' / b"..." literal; returned unchanged.
    assert repair_str_bytes_repr_artifact("b'") == "b'"


def test_repair_str_bytes_repr_artifact_no_b_prefix() -> None:
    assert repair_str_bytes_repr_artifact("hello") == "hello"


def test_repair_str_bytes_repr_artifact_invalid_literal() -> None:
    # b' followed by content that is not valid bytes literal -> original returned.
    assert repair_str_bytes_repr_artifact("b'\\xzz'") == "b'\\xzz'"


def test_elem_to_str_original_string_str() -> None:
    class _FakePN:
        original_string = "RAW^NAME"

    assert _elem_to_str(_FakePN()) == "RAW^NAME"


def test_elem_to_str_original_string_bytes_decoded() -> None:
    class _FakePN:
        original_string = b"BYTES^NAME"

    assert _elem_to_str(_FakePN()) == "BYTES^NAME"


def test_elem_to_str_original_string_raises_falls_back() -> None:
    class _FakePN:
        original_string = object()  # no .strip(); triggers except path

    # Should not raise; falls back to str(val).
    assert isinstance(_elem_to_str(_FakePN()), str)


def test_elem_to_str_str_value() -> None:
    assert _elem_to_str("plain text") == "plain text"


def test_elem_to_str_numeric_value() -> None:
    assert _elem_to_str(123) == "123"
