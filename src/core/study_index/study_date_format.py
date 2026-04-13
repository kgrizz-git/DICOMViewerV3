"""
DICOM Study Date (DA) formatting for the local study index.

Index rows store ``study_date`` as DICOM ``YYYYMMDD`` (string) for correct SQL
ordering and range filters. The UI shows **MM/DD/YYYY** and accepts the same
(or legacy ``YYYYMMDD``) in filter fields.
"""

from __future__ import annotations

import re
from datetime import datetime


def format_study_date_display_us(yyyymmdd: str) -> str:
    """
    Format a stored DICOM study date for display (US: MM/DD/YYYY).

    Non-conforming values are returned unchanged (after strip) so odd data is
    still visible.
    """
    s = (yyyymmdd or "").strip()
    if len(s) != 8 or not s.isdigit():
        return s
    try:
        dt = datetime.strptime(s, "%Y%m%d")
        return dt.strftime("%m/%d/%Y")
    except ValueError:
        return s


def parse_study_date_filter_field(raw: str) -> tuple[str, bool]:
    """
    Parse a user-entered study date filter into ``YYYYMMDD`` for SQL bounds.

    Returns ``(canonical, ok)``. Empty or whitespace input → ``("", True)``.
    Accepted forms:

    - ``MM/DD/YYYY`` or ``M/D/YYYY`` (slashes)
    - ``YYYYMMDD`` (8 digits, valid calendar date)

    Non-empty input that does not match a valid date → ``("", False)``.
    """
    s = (raw or "").strip()
    if not s:
        return "", True
    if re.fullmatch(r"\d{8}", s):
        try:
            datetime.strptime(s, "%Y%m%d")
            return s, True
        except ValueError:
            return "", False
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dt = datetime(year, month, day)
            return dt.strftime("%Y%m%d"), True
        except ValueError:
            return "", False
    return "", False
