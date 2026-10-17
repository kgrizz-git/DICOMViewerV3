"""CSV import/export for the local study index — metadata + file paths only.

DICOM image pixel data is **never** written (the index stores none); the column
set is fixed and explicit so exports stay limited to clinical metadata and file
locations. Import de-duplicates on ``(study_uid, file_path)`` at the service layer.
Exported string cells are formula-neutralized; import restores that prefix.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from typing import Any

from core.spreadsheet_safety import neutralize_spreadsheet_value

# Must match ``spreadsheet_safety`` formula triggers. Import strips one leading
# apostrophe only when the next character is one of these, so a neutralized
# export round-trips to the text that was stored in the index.
_FORMULA_PREFIXES = ("=", "+", "-", "@")

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

    ``neutralize_spreadsheet_value`` prefixes formula triggers with ``'``. A stored
    value that already began with ``'=`` (or ``'+``, ``'-``, ``'@``) is
    indistinguishable after export and comes back without that apostrophe.
    """
    if len(value) >= 2 and value[0] == "'" and value[1] in _FORMULA_PREFIXES:
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
            row = {
                k: _restore_imported_text(raw.get(k) or "") for k in EXPORT_COLUMNS
            }
            if not row["study_uid"].strip() or not row["file_path"].strip():
                continue
            out.append(row)
    return out
