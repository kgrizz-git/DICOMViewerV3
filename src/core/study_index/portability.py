"""CSV import/export for the local study index — metadata + file paths only.

DICOM image pixel data is **never** written (the index stores none); the column
set is fixed and explicit so exports stay limited to clinical metadata and file
locations. Import de-duplicates on ``(study_uid, file_path)`` at the service layer.
Exported string cells are formula-neutralized; import restores that prefix when
appropriate (see :func:`_restore_imported_text`).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from typing import Any

from core.spreadsheet_safety import (
    ignorable_before_formula_trigger,
    neutralize_spreadsheet_value,
)

# Must match ``spreadsheet_safety`` formula triggers. Import may strip one leading
# export-time apostrophe when a trigger appears after optional ignorable characters.
_FORMULA_PREFIXES = frozenset("=+-@")

# Column order for exported CSV files. Mirrors ``StudyIndexStore._PORTABLE_COLUMNS``.
EXPORT_COLUMNS: tuple[str, ...] = (
    "study_uid",
    "file_path",
    "study_root_path",
    "series_uid",
    "sop_instance_uid",
    "patient_name",
    "patient_id",
    "accession_number",
    "study_date",
    "study_description",
    "series_description",
    "modality",
    "indexed_at",
)

# Shown next to the Export action so the user knows exactly what leaves the app.
PIXEL_DATA_DISCLAIMER = (
    "This CSV contains PHI, including clinical metadata and file paths. "
    "Handle it securely. DICOM image pixel data is never included."
)


def _cell_for_export(value: Any) -> Any:
    """Blank out missing cells, then make formula-like text inert for spreadsheets."""
    if value is None:
        value = ""
    return neutralize_spreadsheet_value(value)


def _restore_imported_text(value: str) -> str:
    """Undo one export-time apostrophe so index import matches the stored text.

    If *value* begins with ``'``, scan forward after that character: skip leading
    Unicode whitespace and C0 controls (``ord`` < 32), same rule as
    :func:`core.spreadsheet_safety.neutralize_spreadsheet_value`. If the next
    character is ``=``, ``+``, ``-``, or ``@``, return *value* without that single
    leading apostrophe; the remainder is unchanged.

    **Collision:** A value already stored as ``'=…`` matches the CSV encoding of a
    neutralized bare formula trigger and imports without the apostrophe. The same
    applies when a trigger follows only whitespace or C0 controls after that leading
    apostrophe (e.g. stored ``'\\t=…`` is indistinguishable from a neutralized
    ``\\t=…`` after export).
    """
    if not value or value[0] != "'":
        return value
    i = 1
    n = len(value)
    while i < n and ignorable_before_formula_trigger(value[i]):
        i += 1
    if i < n and value[i] in _FORMULA_PREFIXES:
        return value[1:]
    return value


def write_entries_csv(path: str, rows: Iterable[dict[str, Any]]) -> int:
    """Write ``rows`` to ``path`` as CSV using :data:`EXPORT_COLUMNS`. Returns row count.

    String cells are neutralized so spreadsheet apps do not treat leading ``=``,
    ``+``, ``-``, or ``@`` as formulas. :func:`read_entries_csv` restores that prefix.
    """
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(EXPORT_COLUMNS), extrasaction="ignore"
        )
        writer.writeheader()
        for r in rows:
            writer.writerow({k: _cell_for_export(r.get(k)) for k in EXPORT_COLUMNS})
            n += 1
    return n


def read_entries_csv(path: str) -> list[dict[str, Any]]:
    """Read a prior CSV export into row dicts.

    Rows missing a ``study_uid`` or ``file_path`` are skipped (they cannot be keyed
    or upserted). Only the known export columns are retained. A single leading
    apostrophe added by :func:`write_entries_csv` for formula-like text is removed.
    """
    out: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {k: _restore_imported_text(raw.get(k) or "") for k in EXPORT_COLUMNS}
            if not row["study_uid"].strip() or not row["file_path"].strip():
                continue
            out.append(row)
    return out
