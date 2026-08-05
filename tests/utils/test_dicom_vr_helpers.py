"""Tests for dicom_vr_helpers: DICOM Value Representation classifiers."""

from __future__ import annotations

from utils.dicom_vr_helpers import is_date_vr, is_text_vr


def test_is_text_vr_returns_true_for_text_vrs() -> None:
    text_vrs = ("LO", "PN", "SH", "ST", "LT", "UT", "CS", "IS", "DS")
    for vr in text_vrs:
        assert is_text_vr(vr) is True


def test_is_text_vr_returns_false_for_non_text_vrs() -> None:
    non_text_vrs = ("OB", "OW", "FL", "FD", "DA", "TM", "DT", "UI", "SQ")
    for vr in non_text_vrs:
        assert is_text_vr(vr) is False


def test_is_date_vr_returns_true_for_date_vrs() -> None:
    date_vrs = ("DA", "TM", "DT")
    for vr in date_vrs:
        assert is_date_vr(vr) is True


def test_is_date_vr_returns_false_for_non_date_vrs() -> None:
    non_date_vrs = ("LO", "PN", "SH", "OB", "OW", "FL", "FD", "UI", "SQ")
    for vr in non_date_vrs:
        assert is_date_vr(vr) is False


def test_vr_helpers_case_sensitivity() -> None:
    # DICOM VRs must be strictly uppercase
    assert is_text_vr("lo") is False
    assert is_text_vr("pn") is False
    assert is_date_vr("da") is False
    assert is_date_vr("tm") is False
