"""Study-index CSV formula neutralization and import restore.

**Purpose:** Confirm exported metadata cannot open as a spreadsheet formula, and
that reading the same file returns the text that was stored.

**Inputs:** In-memory row dicts and a temp CSV path.

**Outputs:** Assertions on the raw CSV text and on ``read_entries_csv``.
"""

from __future__ import annotations

import csv

from core.study_index.portability import (
    EXPORT_COLUMNS,
    read_entries_csv,
    write_entries_csv,
)


def _row(**over: str) -> dict[str, str]:
    base = dict.fromkeys(EXPORT_COLUMNS, "")
    base.update(
        {
            "study_uid": "1.2.3",
            "file_path": "/data/study/1.dcm",
            "patient_name": "Port^Patient",
            "study_description": "Head",
        }
    )
    base.update(over)
    return base


def test_export_prefixes_formula_triggers_and_import_restores(tmp_path) -> None:
    src = _row(
        patient_name="=HYPERLINK(\"http://evil.example\")",
        patient_id="+cmd",
        accession_number="-1",
        study_description="@SUM(A1)",
        series_description="Head",
    )
    path = tmp_path / "index.csv"
    assert write_entries_csv(str(path), [src]) == 1

    with path.open(newline="", encoding="utf-8") as f:
        raw_rows = list(csv.DictReader(f))
    assert len(raw_rows) == 1
    raw = raw_rows[0]
    assert raw["patient_name"].startswith("'=")
    assert raw["patient_id"].startswith("'+")
    assert raw["accession_number"].startswith("'-")
    assert raw["study_description"].startswith("'@")
    assert raw["series_description"] == "Head"
    assert raw["study_uid"] == "1.2.3"

    restored = read_entries_csv(str(path))
    assert len(restored) == 1
    assert restored[0]["patient_name"] == src["patient_name"]
    assert restored[0]["patient_id"] == src["patient_id"]
    assert restored[0]["accession_number"] == src["accession_number"]
    assert restored[0]["study_description"] == src["study_description"]
    assert restored[0]["series_description"] == "Head"
    assert restored[0]["file_path"] == src["file_path"]


def test_import_keeps_a_leading_apostrophe_that_is_not_a_formula_escape(tmp_path) -> None:
    src = _row(patient_name="'Smith")
    path = tmp_path / "apostrophe.csv"
    write_entries_csv(str(path), [src])
    restored = read_entries_csv(str(path))
    assert restored[0]["patient_name"] == "'Smith"


def test_import_cannot_tell_a_prequoted_formula_from_a_neutralized_one(tmp_path) -> None:
    """A stored ``'=`` value and a neutralized ``=`` value share one CSV encoding."""
    src = _row(study_description="'=already")
    path = tmp_path / "collision.csv"
    write_entries_csv(str(path), [src])
    with path.open(newline="", encoding="utf-8") as f:
        raw = next(csv.DictReader(f))
    assert raw["study_description"] == "'=already"
    restored = read_entries_csv(str(path))
    assert restored[0]["study_description"] == "=already"
