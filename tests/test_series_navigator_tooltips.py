"""
Unit tests for series navigator tooltip string builders (``series_navigator_model``).

No Qt; uses minimal pydicom datasets.
"""

from __future__ import annotations

from pydicom.dataset import Dataset

from gui.series_navigator_model import (
    PRIVACY_TAG_DISPLAY_VALUE,
    build_instance_navigator_tooltip,
    build_series_navigator_tooltip,
    build_study_navigator_tooltip,
    format_study_date,
    safe_dicom_attribute_text,
)


def test_format_study_date_yyyymmdd() -> None:
    assert format_study_date("20240115") == "2024-01-15"


def test_format_study_date_raw_when_invalid_calendar() -> None:
    assert format_study_date("20249999") == "20249999"


def test_format_study_date_unknown() -> None:
    assert format_study_date(None) == "Unknown"
    assert format_study_date("") == "Unknown"
    assert format_study_date("   ") == "Unknown"


def test_safe_dicom_attribute_text_missing() -> None:
    ds = Dataset()
    assert safe_dicom_attribute_text(ds, "StudyDescription") == "Unknown"


def test_build_study_navigator_tooltip_privacy_masks_patient_only() -> None:
    ds = Dataset()
    ds.StudyDescription = "CT Head"
    ds.StudyDate = "20200101"
    ds.PatientName = "Doe^John"
    text = build_study_navigator_tooltip(ds, privacy_mode=True)
    assert "Study description: CT Head" in text
    assert "Study date: 2020-01-01" in text
    assert PRIVACY_TAG_DISPLAY_VALUE in text
    assert "Doe" not in text


def test_build_series_navigator_tooltip_includes_series_description() -> None:
    ds = Dataset()
    ds.StudyDescription = "MR"
    ds.StudyDate = "20150630"
    ds.PatientName = "Anonymous"
    ds.SeriesDescription = "T1 AX"
    text = build_series_navigator_tooltip(ds, privacy_mode=False)
    assert "Series description: T1 AX" in text
    assert "Patient name: Anonymous" in text


def test_build_instance_navigator_tooltip_appends_instance_line() -> None:
    ds = Dataset()
    ds.StudyDescription = "X"
    ds.StudyDate = "20000101"
    ds.PatientName = "P"
    ds.SeriesDescription = "S"
    text = build_instance_navigator_tooltip(ds, "I3", privacy_mode=False)
    assert text.endswith("Instance: I3")


def test_build_instance_empty_label_uses_unknown() -> None:
    ds = Dataset()
    ds.StudyDescription = "X"
    ds.StudyDate = "20000101"
    ds.PatientName = "P"
    ds.SeriesDescription = "S"
    text = build_instance_navigator_tooltip(ds, "  ", privacy_mode=False)
    assert "Instance: Unknown" in text
