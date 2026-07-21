"""CSV import/export for the local study index — metadata + file paths only.

DICOM image pixel data is **never** written (the index stores none); the column
set is fixed and explicit so exports stay limited to clinical metadata and file
locations. Import de-duplicates on ``(study_uid, file_path)`` at the service layer.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from typing import Any

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
    "Exports contain clinical metadata and file paths only — "
    "DICOM image pixel data is never included."
)


def write_entries_csv(path: str, rows: Iterable[dict[str, Any]]) -> int:
    """Write ``rows`` to ``path`` as CSV using :data:`EXPORT_COLUMNS`. Returns row count."""
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=list(EXPORT_COLUMNS), extrasaction="ignore"
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {k: ("" if r.get(k) is None else r.get(k)) for k in EXPORT_COLUMNS}
            )
            n += 1
    return n


def read_entries_csv(path: str) -> list[dict[str, Any]]:
    """Read a prior CSV export into row dicts.

    Rows missing a ``study_uid`` or ``file_path`` are skipped (they cannot be keyed
    or upserted). Only the known export columns are retained.
    """
    out: list[dict[str, Any]] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            row = {k: (raw.get(k) or "") for k in EXPORT_COLUMNS}
            if not row["study_uid"].strip() or not row["file_path"].strip():
                continue
            out.append(row)
    return out
