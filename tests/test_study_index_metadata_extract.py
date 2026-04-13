"""Unit tests for study index metadata string coercion (no ``b'…'`` artifacts)."""

from __future__ import annotations

from core.study_index.metadata_extract import _elem_to_str, repair_str_bytes_repr_artifact


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
