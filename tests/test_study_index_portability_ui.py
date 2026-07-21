"""Backend tests for the About-this-index panel's Move / Export / Import actions.

No Qt required — exercises ``LocalStudyIndexService`` and ``portability`` directly,
the same way ``tests/test_study_index_store.py`` builds temp encrypted stores.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")
pytest.importorskip("keyring", reason="keyring not installed")

from core.study_index.index_service import LocalStudyIndexService
from core.study_index.portability import read_entries_csv, write_entries_csv
from core.study_index.sqlcipher_store import StudyIndexStore


class _FakeConfig:
    """Minimal stand-in for ConfigManager's study-index path accessors."""

    def __init__(self, initial_path: str) -> None:
        self._path = initial_path

    def get_study_index_db_path(self) -> str:
        return self._path

    def set_study_index_db_path(self, path: str) -> bool:
        self._path = path
        return True


def _service_for(db_path: str, passphrase: str) -> LocalStudyIndexService:
    svc = LocalStudyIndexService(config_manager=_FakeConfig(db_path))
    svc._passphrase = lambda: passphrase  # type: ignore[method-assign]
    svc.is_backend_available = lambda: True  # type: ignore[method-assign]
    return svc


def _row(root: str, file_path: str, study_uid: str, **over) -> dict:
    base = {
        "file_path": file_path,
        "study_root_path": root,
        "study_uid": study_uid,
        "series_uid": f"{study_uid}.s",
        "sop_instance_uid": f"{study_uid}.i",
        "patient_name": "Port^Patient",
        "patient_id": "PP1",
        "accession_number": "A1",
        "study_date": "20200101",
        "study_description": "Head",
        "modality": "CT",
    }
    base.update(over)
    return base


def _seed_rows(tmp_path, n: int = 3) -> list[dict]:
    root = os.path.abspath(str(tmp_path))
    rows = []
    for i in range(n):
        rows.append(
            _row(
                root,
                os.path.abspath(str(tmp_path / f"file{i}.dcm")),
                f"1.study.{i}",
            )
        )
    return rows


def test_move_database_switches_path_and_removes_old(tmp_path) -> None:
    old_db = tmp_path / "orig.sqlite"
    passphrase = "pw-move"
    store = StudyIndexStore(str(old_db), passphrase)
    store.init_schema()
    rows = _seed_rows(tmp_path, 3)
    store.upsert_rows(rows)

    svc = _service_for(str(old_db), passphrase)

    new_db = tmp_path / "moved_here" / "index.sqlite"
    result_path = svc.move_database(str(new_db))

    assert os.path.abspath(result_path) == os.path.abspath(str(new_db))
    assert os.path.exists(new_db)
    assert not os.path.exists(old_db)
    assert not os.path.exists(f"{old_db}-wal")
    assert not os.path.exists(f"{old_db}-shm")

    # Config path was updated to the new location.
    assert os.path.abspath(svc._db_path()) == os.path.abspath(str(new_db))

    # Search/row_count still work against the moved DB.
    assert svc.row_count() == 3
    grouped = svc.search_grouped_studies(limit=50, offset=0)
    assert len(grouped) == 3


def test_move_database_verifies_before_swapping_config(tmp_path) -> None:
    """A destination that already exists is rejected without touching the original."""
    old_db = tmp_path / "orig2.sqlite"
    passphrase = "pw-move2"
    store = StudyIndexStore(str(old_db), passphrase)
    store.init_schema()
    store.upsert_rows(_seed_rows(tmp_path, 1))

    existing_dest = tmp_path / "already_here.sqlite"
    existing_dest.write_bytes(b"not a real db")

    svc = _service_for(str(old_db), passphrase)

    with pytest.raises(FileExistsError):
        svc.move_database(str(existing_dest))

    # Original DB untouched, config path unchanged.
    assert os.path.exists(old_db)
    assert svc._db_path() == str(old_db)
    assert svc.row_count() == 1


def test_export_import_round_trip_dedupes_on_second_import(tmp_path) -> None:
    src_db = tmp_path / "source.sqlite"
    src_passphrase = "pw-src"
    src_store = StudyIndexStore(str(src_db), src_passphrase)
    src_store.init_schema()
    seeded_rows = _seed_rows(tmp_path, 4)
    src_store.upsert_rows(seeded_rows)

    src_svc = _service_for(str(src_db), src_passphrase)
    exported = src_svc.export_entries()
    assert len(exported) == 4

    csv_path = tmp_path / "export.csv"
    n_written = write_entries_csv(str(csv_path), exported)
    assert n_written == 4

    # Fresh, empty destination DB.
    dst_db = tmp_path / "dest.sqlite"
    dst_passphrase = "pw-dst"
    dst_store = StudyIndexStore(str(dst_db), dst_passphrase)
    dst_store.init_schema()
    assert dst_store.row_count() == 0

    dst_svc = _service_for(str(dst_db), dst_passphrase)

    imported_rows = read_entries_csv(str(csv_path))
    assert len(imported_rows) == 4

    added, skipped = dst_svc.import_entries(imported_rows)
    assert (added, skipped) == (4, 0)

    src_keys = src_store.existing_study_file_keys()
    dst_keys = dst_store.existing_study_file_keys()
    assert dst_keys == src_keys
    assert len(dst_keys) == 4

    # A second import of the same file adds 0 new rows (dedupe on study_uid + file_path).
    added2, skipped2 = dst_svc.import_entries(read_entries_csv(str(csv_path)))
    assert (added2, skipped2) == (0, 4)
    assert dst_store.row_count() == 4
