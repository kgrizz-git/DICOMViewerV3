"""Tests for study index DICOM date display and filter parsing."""

from __future__ import annotations

from core.study_index.study_date_format import (
    format_partial_mdy_digits,
    format_study_date_display_us,
    parse_study_date_filter_field,
)


def test_format_study_date_display_us() -> None:
    assert format_study_date_display_us("20200115") == "01/15/2020"
    assert format_study_date_display_us("") == ""
    assert format_study_date_display_us("bad") == "bad"


def test_parse_empty_ok() -> None:
    assert parse_study_date_filter_field("") == ("", True)
    assert parse_study_date_filter_field("   ") == ("", True)


def test_parse_yyyymmdd() -> None:
    assert parse_study_date_filter_field("20200202") == ("20200202", True)


def test_parse_mm_dd_yyyy() -> None:
    assert parse_study_date_filter_field("1/5/2020") == ("20200105", True)
    assert parse_study_date_filter_field("12/31/1999") == ("19991231", True)


def test_format_partial_mdy_digits_typing() -> None:
    assert format_partial_mdy_digits("01") == "01"
    assert format_partial_mdy_digits("0115") == "01/15"
    assert format_partial_mdy_digits("01152020") == "01/15/2020"


def test_format_partial_mdy_digits_yyyymmdd_paste() -> None:
    assert format_partial_mdy_digits("20200115") == "01/15/2020"


def test_parse_invalid() -> None:
    assert parse_study_date_filter_field("13/01/2020") == ("", False)
    assert parse_study_date_filter_field("20201301") == ("", False)
    assert parse_study_date_filter_field("not a date") == ("", False)
