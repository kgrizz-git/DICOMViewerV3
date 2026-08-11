"""Tests for core.sr_concept_identity — SR coded-concept normalization."""

from __future__ import annotations

import pytest
from pydicom.dataset import Dataset

from core.sr_concept_identity import (
    coded_entry_effective_code_value,
    concept_identity_matches,
    concept_name_identity_pair,
    normalize_coding_scheme_designator,
    normalized_expected_tuple,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("dcm", "DCM"),
        ("DCM", "DCM"),
        ("Dcm", "DCM"),
    ],
)
def test_normalize_designator_uppercases_short(raw, expected):
    assert normalize_coding_scheme_designator(raw) == expected


@pytest.mark.parametrize(
    "urn",
    [
        "urn:example",
        "URN:example",
        "urn:foo:bar",
    ],
)
def test_normalize_designator_preserves_urn(urn):
    assert normalize_coding_scheme_designator(urn) == urn


@pytest.mark.parametrize(
    "designator",
    [
        "1.2.840.10008.1.2.4.50",
        "ISO_IEC_12087-5",
    ],
)
def test_normalize_designator_uppercases_opaque_string(designator):
    assert normalize_coding_scheme_designator(designator) == designator


@pytest.mark.parametrize(
    "designator",
    [
        "2.16.840.1.113883.6.1",
        "foo:bar",
    ],
)
def test_normalize_designator_preserves_colon(designator):
    assert normalize_coding_scheme_designator(designator) == designator


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" dcm ", "DCM"),
        ("  DCM  ", "DCM"),
        ("\tDCM\n", "DCM"),
    ],
)
def test_normalize_designator_strips_whitespace(raw, expected):
    assert normalize_coding_scheme_designator(raw) == expected


@pytest.mark.parametrize("value", ["", None])
def test_normalize_designator_empty(value):
    assert normalize_coding_scheme_designator(value) == ""


def test_effective_code_value_prefers_code_value():
    coded = Dataset()
    coded.CodeValue = "T-D1213"
    coded.LongCodeValue = "ignored"
    assert coded_entry_effective_code_value(coded) == "T-D1213"


def test_effective_code_value_falls_back_to_long():
    coded = Dataset()
    coded.CodeValue = "   "
    coded.LongCodeValue = "1.2.840.10008.1.2.4.50"
    assert coded_entry_effective_code_value(coded) == "1.2.840.10008.1.2.4.50"


def test_effective_code_value_empty_when_both_missing():
    coded = Dataset()
    assert coded_entry_effective_code_value(coded) == ""


def test_effective_code_value_strips_whitespace():
    coded = Dataset()
    coded.CodeValue = "  ABC  "
    assert coded_entry_effective_code_value(coded) == "ABC"


def test_concept_identity_matches_equal():
    item = Dataset()
    c0 = Dataset()
    c0.CodeValue = "T-D1213"
    c0.CodingSchemeDesignator = "DCM"
    item.ConceptNameCodeSequence = [c0]
    assert concept_identity_matches(item, ("T-D1213", "DCM")) is True


def test_concept_identity_matches_case_insensitive_scheme():
    item = Dataset()
    c0 = Dataset()
    c0.CodeValue = "T-D1213"
    c0.CodingSchemeDesignator = "dcm"
    item.ConceptNameCodeSequence = [c0]
    assert concept_identity_matches(item, ("T-D1213", "DCM")) is True


def test_concept_identity_matches_whitespace_stripping():
    item = Dataset()
    c0 = Dataset()
    c0.CodeValue = "T-D1213  "
    c0.CodingSchemeDesignator = "dcm "
    item.ConceptNameCodeSequence = [c0]
    assert concept_identity_matches(item, ("  T-D1213", " DCM ")) is True


def test_concept_identity_mismatch():
    item = Dataset()
    c0 = Dataset()
    c0.CodeValue = "T-D1213"
    c0.CodingSchemeDesignator = "DCM"
    item.ConceptNameCodeSequence = [c0]
    assert concept_identity_matches(item, ("X-OTHER", "DCM")) is False


def test_concept_identity_mismatch_scheme():
    item = Dataset()
    c0 = Dataset()
    c0.CodeValue = "T-D1213"
    c0.CodingSchemeDesignator = "DCM"
    item.ConceptNameCodeSequence = [c0]
    assert concept_identity_matches(item, ("T-D1213", "LN")) is False


def test_concept_identity_missing_sequence():
    item = Dataset()
    assert concept_identity_matches(item, ("T-D1213", "DCM")) is False


def test_concept_name_identity_pair_missing_sequence():
    item = Dataset()
    assert concept_name_identity_pair(item) == ("", "")


def test_concept_name_identity_pair_empty_sequence():
    item = Dataset()
    item.ConceptNameCodeSequence = []
    assert concept_name_identity_pair(item) == ("", "")


def test_normalized_expected_tuple():
    assert normalized_expected_tuple((" T-D1213 ", "dcm")) == ("T-D1213", "DCM")


def test_normalized_expected_tuple_urn():
    assert normalized_expected_tuple(("val", "urn:example")) == ("val", "urn:example")


def test_normalized_expected_tuple_colon():
    assert normalized_expected_tuple(("val", "foo:bar")) == ("val", "foo:bar")
