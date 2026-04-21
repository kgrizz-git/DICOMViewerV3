"""Tests for local study index SQLCipher store (MVP schema)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")
pytest.importorskip("keyring", reason="keyring not installed")

from core.study_index.sqlcipher_store import (  # noqa: E402
    StudyIndexStore,
    is_plain_sqlite_readable,
    verify_encrypted_header,
)


def test_study_index_store_upsert_and_search(tmp_path) -> None:
    db = tmp_path / "idx.sqlite"
    passphrase = "test-passphrase-unique"
    store = StudyIndexStore(str(db), passphrase)
    store.init_schema()
    rows = [
        {
            "file_path": os.path.abspath(str(tmp_path / "a.dcm")),
            "study_root_path": os.path.abspath(str(tmp_path)),
            "study_uid": "1.2.3",
            "series_uid": "1.2.3.4",
            "sop_instance_uid": "1.2.3.4.5",
            "patient_name": "Test^Patient",
            "patient_id": "PID1",
            "accession_number": "ACC1",
            "study_date": "20200101",
            "study_description": "CT HEAD",
            "modality": "CT",
        }
    ]
    store.upsert_rows(rows)
    assert db.is_file()
    assert not is_plain_sqlite_readable(str(db))
    assert verify_encrypted_header(str(db))

    found = store.search(patient_name_contains="Patient", modality="CT")
    assert len(found) == 1
    assert found[0]["study_uid"] == "1.2.3"
    assert found[0]["patient_id"] == "PID1"

    empty = store.search(patient_name_contains="Nobody")
    assert empty == []


def test_study_index_store_idempotent_upsert(tmp_path) -> None:
    db = tmp_path / "idx2.sqlite"
    store = StudyIndexStore(str(db), "pw2")
    store.init_schema()
    row = {
        "file_path": os.path.abspath(str(tmp_path / "b.dcm")),
        "study_root_path": os.path.abspath(str(tmp_path)),
        "study_uid": "9.9.9",
        "series_uid": "",
        "sop_instance_uid": "",
        "patient_name": "A",
        "patient_id": "1",
        "accession_number": "",
        "study_date": "",
        "study_description": "Old",
        "modality": "MR",
    }
    store.upsert_rows([row])
    row2 = dict(row)
    row2["study_description"] = "New"
    store.upsert_rows([row2])
    found = store.search(modality="MR")
    assert len(found) == 1
    assert found[0]["study_description"] == "New"


def test_study_index_store_grouped_aggregates_and_pagination(tmp_path) -> None:
    """Grouped query: counts, modalities, LIMIT/OFFSET pages do not overlap."""
    db = tmp_path / "grouped.sqlite"
    store = StudyIndexStore(str(db), "pw-grouped")
    store.init_schema()
    root = os.path.abspath(str(tmp_path))
    base = {
        "study_root_path": root,
        "study_uid": "1.2.3.study",
        "patient_name": "Group^Test",
        "patient_id": "G1",
        "accession_number": "A1",
        "study_date": "20200202",
        "study_description": "Chest",
    }
    rows = [
        {
            **base,
            "file_path": os.path.abspath(str(tmp_path / "s1_i1.dcm")),
            "series_uid": "1.2.3.s1",
            "sop_instance_uid": "1.2.3.1.1",
            "modality": "CT",
        },
        {
            **base,
            "file_path": os.path.abspath(str(tmp_path / "s1_i2.dcm")),
            "series_uid": "1.2.3.s1",
            "sop_instance_uid": "1.2.3.1.2",
            "modality": "CT",
        },
        {
            **base,
            "file_path": os.path.abspath(str(tmp_path / "s2_i1.dcm")),
            "series_uid": "1.2.3.s2",
            "sop_instance_uid": "1.2.3.2.1",
            "modality": "MR",
        },
    ]
    store.upsert_rows(rows)
    g = store.search_grouped_studies(limit=50, offset=0)
    assert len(g) == 1
    row0 = g[0]
    assert row0["instance_count"] == 3
    assert row0["series_count"] == 2
    assert row0["modalities"] == "CT, MR"
    assert row0["open_file_path"] in {r["file_path"] for r in rows}

    # Second study same root, different UID — two groups; page size 1
    rows2 = {
        "file_path": os.path.abspath(str(tmp_path / "other.dcm")),
        "study_root_path": root,
        "study_uid": "9.9.9.other",
        "series_uid": "9.9.9.1",
        "sop_instance_uid": "9.9.9.1.1",
        "patient_name": "Other",
        "patient_id": "O1",
        "accession_number": "",
        "study_date": "20210101",
        "study_description": "Other study",
        "modality": "PT",
    }
    store.upsert_rows([rows2])
    p1 = store.search_grouped_studies(limit=1, offset=0)
    p2 = store.search_grouped_studies(limit=1, offset=1)
    assert len(p1) == 1 and len(p2) == 1
    uids = {p1[0]["study_uid"], p2[0]["study_uid"]}
    assert uids == {"1.2.3.study", "9.9.9.other"}


def test_study_index_store_delete_study_group(tmp_path) -> None:
    db = tmp_path / "del.sqlite"
    store = StudyIndexStore(str(db), "pw-del")
    store.init_schema()
    root = os.path.abspath(str(tmp_path))
    rows_a = [
        {
            "file_path": os.path.abspath(str(tmp_path / "d1.dcm")),
            "study_root_path": root,
            "study_uid": "1.1.1",
            "series_uid": "1.1.1.1",
            "sop_instance_uid": "1.1.1.1.1",
            "patient_name": "A",
            "patient_id": "1",
            "accession_number": "",
            "study_date": "20200101",
            "study_description": "A",
            "modality": "CT",
        },
        {
            "file_path": os.path.abspath(str(tmp_path / "d2.dcm")),
            "study_root_path": root,
            "study_uid": "1.1.1",
            "series_uid": "1.1.1.1",
            "sop_instance_uid": "1.1.1.1.2",
            "patient_name": "A",
            "patient_id": "1",
            "accession_number": "",
            "study_date": "20200101",
            "study_description": "A",
            "modality": "CT",
        },
    ]
    rows_b = {
        "file_path": os.path.abspath(str(tmp_path / "d3.dcm")),
        "study_root_path": root,
        "study_uid": "2.2.2",
        "series_uid": "2.2.2.1",
        "sop_instance_uid": "2.2.2.1.1",
        "patient_name": "B",
        "patient_id": "2",
        "accession_number": "",
        "study_date": "20200202",
        "study_description": "B",
        "modality": "MR",
    }
    store.upsert_rows(rows_a)
    store.upsert_rows([rows_b])
    assert len(store.search(limit=20)) == 3
    n = store.delete_study_group("1.1.1", root)
    assert n == 2
    assert len(store.search(limit=20)) == 1
    g = store.search_grouped_studies(limit=20, offset=0)
    assert len(g) == 1
    assert g[0]["study_uid"] == "2.2.2"
