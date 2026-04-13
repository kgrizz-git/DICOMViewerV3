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
