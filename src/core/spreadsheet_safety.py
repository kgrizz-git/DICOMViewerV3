"""
Spreadsheet (CSV/TXT/XLSX) formula-injection neutralization.

DICOM text values (e.g. PatientName, SeriesDescription, private tags) are
attacker-controllable. When written verbatim into a spreadsheet cell that begins
with ``=``, ``+``, ``-``, or ``@``, Excel/LibreOffice may evaluate it as a formula
on open, enabling phishing callbacks and local-environment disclosure (CSV / formula
injection). Prefixing such cells with an apostrophe forces the client to treat the
value as literal text.

This is the single source of truth for that neutralization; all tag/ROI/dose export
writers route their string cells through here.
"""

from typing import Any

# Leading characters that make a spreadsheet client interpret a cell as a formula.
_FORMULA_PREFIXES = ("=", "+", "-", "@")


def neutralize_spreadsheet_value(value: Any) -> Any:
    """Return *value* with formula-like string cells made inert.

    String cells whose first character is a formula trigger are prefixed with a
    single apostrophe; all other values (including non-strings) are returned
    unchanged.
    """
    if isinstance(value, str) and value[:1] in _FORMULA_PREFIXES:
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
