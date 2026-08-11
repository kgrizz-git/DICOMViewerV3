"""Tests for utils.dicom_tag_keys — DICOM tag display key parsing."""

from __future__ import annotations

import pytest
from pydicom.tag import BaseTag, Tag

from utils.dicom_tag_keys import leaf_tag_from_key


def test_leaf_tag_from_key_simple():
    result = leaf_tag_from_key("(0010,0010)")
    assert result == Tag(0x0010, 0x0010)
    assert isinstance(result, BaseTag)


def test_leaf_tag_from_key_nested_path():
    result = leaf_tag_from_key("Patient.(0010,0010)")
    assert result == Tag(0x0010, 0x0010)


def test_leaf_tag_from_key_deeply_nested_path():
    result = leaf_tag_from_key("Study.Series.(0010,0010)")
    assert result == Tag(0x0010, 0x0010)


def test_leaf_tag_from_key_whitespace():
    result = leaf_tag_from_key("( 0010 , 0010 )")
    assert result == Tag(0x0010, 0x0010)


@pytest.mark.parametrize(
    "invalid",
    [
        "not_a_tag",
        "0010,0010",
        "(0010,0010",
        "0010,0010)",
        "PatientName",
        "(GGGG,0010)",
        "(0010,GGGG)",
    ],
)
def test_leaf_tag_from_key_invalid(invalid):
    assert leaf_tag_from_key(invalid) is None


@pytest.mark.parametrize("value", ["", "   "])
def test_leaf_tag_from_key_empty(value):
    assert leaf_tag_from_key(value) is None


def test_leaf_tag_from_key_none():
    assert leaf_tag_from_key(None) is None


def test_leaf_tag_from_key_wrong_group_length():
    assert leaf_tag_from_key("(001,0010)") is None


def test_leaf_tag_from_key_wrong_element_length():
    assert leaf_tag_from_key("(0010,001)") is None
