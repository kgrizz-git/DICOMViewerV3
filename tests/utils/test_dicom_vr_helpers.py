"""Tests for utils.dicom_vr_helpers — date-VR classification."""

from __future__ import annotations

import pytest

from utils.dicom_vr_helpers import is_date_vr


@pytest.mark.parametrize("vr", ["DA", "TM", "DT"])
def test_is_date_vr_true(vr):
    assert is_date_vr(vr) is True


@pytest.mark.parametrize("vr", ["LO", "PN", "SQ", "OB", "CS", ""])
def test_is_date_vr_false(vr):
    assert is_date_vr(vr) is False


@pytest.mark.parametrize("vr", ["lo", "da", "tm"])
def test_is_date_vr_case_sensitive(vr):
    # DICOM VRs must be strictly uppercase; lowercase input must not match.
    assert is_date_vr(vr) is False
