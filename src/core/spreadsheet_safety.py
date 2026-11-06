"""
Spreadsheet (CSV/TXT/XLSX) formula-injection neutralization.

DICOM text values (e.g. PatientName, SeriesDescription, private tags) are
attacker-controllable. When written verbatim into a spreadsheet cell whose first
*meaningful* character is ``=``, ``+``, ``-``, or ``@``, Excel/LibreOffice may
evaluate it as a formula on open, enabling phishing callbacks and local-environment
disclosure (CSV / formula injection). Leading Unicode whitespace (``str.isspace()``)
and C0 control characters (code points with ``ord(ch) < 32``) are ignored for that
check; DEL (U+007F) is not treated as a control here. Prefixing such cells with one
apostrophe forces the client to treat the value as literal text; the original string
is preserved (nothing is stripped).

This is the single source of truth for that neutralization. Tag, ROI, QA, dose
summary, study-index, and SR dose-event export writers route their string cells
through here.
"""

from typing import Any

# Leading characters that make a spreadsheet client interpret a cell as a formula.
_FORMULA_PREFIXES = frozenset("=+-@")


def ignorable_before_formula_trigger(ch: str) -> bool:
    """True if *ch* is skipped when locating the first significant character.

    Spreadsheet clients may still treat a cell as formula-like when a trigger
    appears after leading Unicode whitespace or C0 controls (``ord`` < 32), but not
    after DEL (127).
    """
    return ch.isspace() or ord(ch) < 32


def _string_has_formula_trigger_after_ignorable_leading(value: str) -> bool:
    """Whether *value* needs a leading apostrophe for safe spreadsheet export."""
    for ch in value:
        if ignorable_before_formula_trigger(ch):
            continue
        return ch in _FORMULA_PREFIXES
    return False


def neutralize_spreadsheet_value(value: Any) -> Any:
    """Return *value* with formula-like string cells made inert.

    For strings, if the first character that is not Unicode whitespace and not a C0
    control (``ord`` < 32) is ``=``, ``+``, ``-``, or ``@``, the **original** string
    is prefixed with one apostrophe. Strings that already start with a non-ignorable
    character other than those triggers (including a leading apostrophe) are unchanged.
    Non-strings are returned unchanged.
    """
    if not isinstance(value, str):
        return value
    if _string_has_formula_trigger_after_ignorable_leading(value):
        return "'" + value
    return value


class SafeCsvWriter:
    """``csv.writer`` wrapper that neutralizes formula-like cells in every row.

    Wrap any ``csv.writer`` (any dialect/delimiter) so existing ``writerow`` /
    ``writerows`` call sites get formula-injection protection without change.
    """

    def __init__(self, writer: Any) -> None:
        self._writer = writer

    def writerow(self, row: Any) -> Any:
        return self._writer.writerow([neutralize_spreadsheet_value(c) for c in row])

    def writerows(self, rows: Any) -> None:
        for row in rows:
            self.writerow(row)
