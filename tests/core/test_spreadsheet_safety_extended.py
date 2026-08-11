"""Extended tests for core.spreadsheet_safety — missing branches not covered by tests/test_spreadsheet_safety.py."""

from __future__ import annotations

from core.spreadsheet_safety import SafeCsvWriter, neutralize_spreadsheet_value


def test_neutralize_equals_prefix():
    assert neutralize_spreadsheet_value("=SUM(A1)") == "'=SUM(A1)"


def test_neutralize_at_sign_prefix():
    assert neutralize_spreadsheet_value("@SUM") == "'@SUM"


def test_neutralize_minus_prefix():
    assert neutralize_spreadsheet_value("-1") == "'-1"


def test_neutralize_plus_prefix():
    assert neutralize_spreadsheet_value("+1") == "'+1"


def test_neutralize_preserves_already_neutralized():
    assert neutralize_spreadsheet_value("'=foo") == "'=foo"


def test_neutralize_unicode_formula():
    assert neutralize_spreadsheet_value("=Атака") == "'=Атака"


def test_neutralize_non_string_passthrough():
    assert neutralize_spreadsheet_value(42) == 42
    assert neutralize_spreadsheet_value(None) is None
    assert neutralize_spreadsheet_value(3.14) == 3.14


class _FakeWriter:
    def __init__(self):
        self.rows = []

    def writerow(self, row):
        self.rows.append(row)
        return row


class TestSafeCsvWriterExtended:
    def test_writerow_returns_value(self):
        fake = _FakeWriter()
        safe = SafeCsvWriter(fake)
        result = safe.writerow(["=cmd()", "normal"])
        assert result == ["'=cmd()", "normal"]

    def test_writerow_empty_row(self):
        fake = _FakeWriter()
        safe = SafeCsvWriter(fake)
        safe.writerow([])
        assert fake.rows == [[]]

    def test_writerows_multi(self):
        fake = _FakeWriter()
        safe = SafeCsvWriter(fake)
        safe.writerows([["=a", "+b"], ["-c", "@d"], ["plain"]])
        assert fake.rows == [["'=a", "'+b"], ["'-c", "'@d"], ["plain"]]
