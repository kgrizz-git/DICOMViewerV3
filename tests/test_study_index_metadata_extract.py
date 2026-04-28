"""Unit tests for study index metadata string coercion (no ``b'…'`` artifacts)."""

from __future__ import annotations

import os

import pydicom
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
