"""
Unit tests for core.spreadsheet_safety (CSV/spreadsheet formula-injection
neutralization).
"""

from __future__ import annotations

import pytest

from core.spreadsheet_safety import SafeCsvWriter, neutralize_spreadsheet_value


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@"])
def test_neutralizes_formula_prefixed_strings(prefix):
    value = f"{prefix}SUM(A1:A2)"
    assert neutralize_spreadsheet_value(value) == f"'{value}"


def test_leaves_plain_strings_unchanged():
    assert neutralize_spreadsheet_value("John Doe") == "John Doe"


def test_leaves_empty_string_unchanged():
    assert neutralize_spreadsheet_value("") == ""


def test_leaves_non_string_values_unchanged():
    assert neutralize_spreadsheet_value(42) == 42
    assert neutralize_spreadsheet_value(None) is None
    assert neutralize_spreadsheet_value(3.14) == 3.14


class _FakeWriter:
    def __init__(self):
        self.rows = []

    def writerow(self, row):
        self.rows.append(row)
        return row


class TestSafeCsvWriter:
    def test_writerow_neutralizes_each_cell(self):
        fake = _FakeWriter()
        safe = SafeCsvWriter(fake)
        safe.writerow(["=cmd()", "normal", 42])
        assert fake.rows == [["'=cmd()", "normal", 42]]

    def test_writerows_neutralizes_all_rows(self):
        fake = _FakeWriter()
        safe = SafeCsvWriter(fake)
        safe.writerows([["=a"], ["+b"], ["plain"]])
        assert fake.rows == [["'=a"], ["'+b"], ["plain"]]
