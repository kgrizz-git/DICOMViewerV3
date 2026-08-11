"""Tests for utils.dicom_vr_helpers — VR classification helpers."""

from __future__ import annotations

import pytest

from utils.dicom_vr_helpers import is_date_vr, is_text_vr


@pytest.mark.parametrize("vr", ["LO", "PN", "SH", "ST", "LT", "UT", "CS", "IS", "DS"])
def test_is_text_vr_true(vr):
    assert is_text_vr(vr) is True


@pytest.mark.parametrize("vr", ["DA", "TM", "DT", "SQ", "OB", "OW", "UN", ""])
def test_is_text_vr_false(vr):
    assert is_text_vr(vr) is False


@pytest.mark.parametrize("vr", ["DA", "TM", "DT"])
def test_is_date_vr_true(vr):
    assert is_date_vr(vr) is True


@pytest.mark.parametrize("vr", ["LO", "PN", "SQ", "OB", "CS", ""])
def test_is_date_vr_false(vr):
    assert is_date_vr(vr) is False


@pytest.mark.parametrize("vr", ["lo", "pn", "da", "tm"])
def test_vr_helpers_case_sensitive(vr):
    # DICOM VRs must be strictly uppercase; lowercase input must not match.
    assert is_text_vr(vr) is False
    assert is_date_vr(vr) is False
