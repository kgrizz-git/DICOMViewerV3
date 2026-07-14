"""Unit tests for core.study_index.fts_doc helpers."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from core.study_index.fts_doc import (
    FTS_USER_QUERY_MAX_LEN,
    index_row_to_search_doc,
    normalize_user_fts_query,
)


def test_index_row_to_search_doc_uses_declared_field_order_and_trims_values() -> None:
    row = {
        "series_description": "  Series B  ",
        "patient_name": " Alice ",
        "modality": "CT",
        "patient_id": 12345,
        "study_uid": "",
    }
    assert index_row_to_search_doc(row) == "Alice | 12345 | Series B | CT"


def test_index_row_to_search_doc_returns_single_space_for_empty_row() -> None:
    assert index_row_to_search_doc({}) == " "


def test_normalize_user_fts_query_trims_and_returns_empty_for_blank_input() -> None:
    assert normalize_user_fts_query("   ") == ""
    assert normalize_user_fts_query("") == ""


def test_normalize_user_fts_query_caps_length() -> None:
    raw = "x" * (FTS_USER_QUERY_MAX_LEN + 10)
    normalized = normalize_user_fts_query(raw)
    assert len(normalized) == FTS_USER_QUERY_MAX_LEN
    assert normalized == raw[:FTS_USER_QUERY_MAX_LEN]
