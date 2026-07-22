"""Backend tests for the study-index integrity scan, relocate, and remove (no Qt)."""

from __future__ import annotations

import os

import pytest

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")
pytest.importorskip("keyring", reason="keyring not installed")

from unittest.mock import MagicMock

from core.study_index.index_service import LocalStudyIndexService, MissingStudyRecord
from core.study_index.sqlcipher_store import StudyIndexStore


def _row(root: str, file_path: str, study_uid: str, **over) -> dict:
    base = {
        "file_path": file_path,
        "study_root_path": root,
        "study_uid": study_uid,
        "series_uid": f"{study_uid}.s",
        "sop_instance_uid": f"{study_uid}.i",
        "patient_name": "Scan^Patient",
        "patient_id": "SP1",
        "accession_number": "A1",
        "study_date": "20200101",
        "study_description": "Head",
        "modality": "CT",
    }
    base.update(over)
    return base


def _seed(tmp_path):
    """Create a real study folder + files and index them. Returns (store, root, files)."""
    root = tmp_path / "study_present"
    root.mkdir()
    files = []
    for name in ("a.dcm", "b.dcm", "c.dcm"):
        p = root / name
        p.write_bytes(b"DICM")
        files.append(str(p))
    db = tmp_path / "idx.sqlite"
    store = StudyIndexStore(str(db), "pw-integrity")
    store.init_schema()
    store.upsert_rows(
        [_row(os.path.abspath(str(root)), os.path.abspath(f), "1.2.3") for f in files]
    )
    return store, root, files


def _service_for(store) -> LocalStudyIndexService:
    svc = LocalStudyIndexService(config_manager=MagicMock())
    svc._get_ready_store = lambda: store  # type: ignore[method-assign]
    svc.is_backend_available = lambda: True  # type: ignore[method-assign]
    return svc


def test_iter_study_groups_returns_unique_groups(tmp_path) -> None:
    store, root, _files = _seed(tmp_path)
    groups = store.iter_study_groups()
    assert len(groups) == 1
    g = groups[0]
    assert g["study_uid"] == "1.2.3"
    assert g["instance_count"] == 3
    assert g["modalities"] == "CT"


def test_scan_reports_partial_missing(tmp_path) -> None:
    store, root, files = _seed(tmp_path)
    os.remove(files[0])  # one of three now missing
    svc = _service_for(store)
    seen: list[tuple[int, int]] = []
    records = svc.integrity_scan(progress=lambda d, t: seen.append((d, t)))
    assert len(records) == 1
    rec = records[0]
    assert isinstance(rec, MissingStudyRecord)
    assert rec.study_uid == "1.2.3"
    assert rec.missing_count == 1
    assert rec.total_count == 3
    assert seen[-1] == (1, 1)


def test_scan_reports_root_gone(tmp_path) -> None:
    store, root, files = _seed(tmp_path)
    for f in files:
        os.remove(f)
    os.rmdir(root)
    svc = _service_for(store)
    records = svc.integrity_scan()
    assert len(records) == 1
    assert records[0].missing_count == 3
    assert records[0].total_count == 3


def test_scan_empty_when_all_present(tmp_path) -> None:
    store, _root, _files = _seed(tmp_path)
    svc = _service_for(store)
    assert svc.integrity_scan() == []


def test_scan_empty_when_backend_unavailable(tmp_path) -> None:
    store, _root, files = _seed(tmp_path)
    os.remove(files[0])
    svc = _service_for(store)
    svc.is_backend_available = lambda: False  # type: ignore[method-assign]
    assert svc.integrity_scan() == []


def test_relocate_rewrites_paths_and_counts(tmp_path) -> None:
    store, root, files = _seed(tmp_path)
    # Move the folder to a new location on disk.
    new_root = tmp_path / "study_moved"
    new_root.mkdir()
    for f in files:
        (new_root / os.path.basename(f)).write_bytes(b"DICM")
        os.remove(f)
    os.rmdir(root)

    svc = _service_for(store)
    n = svc.relocate_study(
        "1.2.3", os.path.abspath(str(root)), os.path.abspath(str(new_root))
    )
    assert n == 3

    # Paths now point under the new root and exist; scan is clean.
    paths = store.get_file_paths_for_study("1.2.3", os.path.abspath(str(new_root)))
    assert len(paths) == 3
    assert all(os.path.isfile(p) for p in paths)
    assert svc.integrity_scan() == []


def test_relocate_preserves_similarly_prefixed_unrelated_paths(tmp_path) -> None:
    """A root such as ``ar`` must not rewrite a sibling ``archive`` path."""
    studies = tmp_path / "studies"
    old_root = studies / "ar"
    archive = studies / "archive"
    new_root = studies / "new"
    old_root.mkdir(parents=True)
    archive.mkdir()
    new_root.mkdir()
    old_file = old_root / "present.dcm"
    archive_file = archive / "unrelated.dcm"
    moved_file = new_root / "present.dcm"
    for path in (old_file, archive_file, moved_file):
        path.write_bytes(b"DICM")

    db = tmp_path / "prefix.sqlite"
    store = StudyIndexStore(str(db), "pw-prefix")
    store.init_schema()
    old = os.path.abspath(str(old_root))
    store.upsert_rows(
        [
            _row(old, os.path.abspath(str(old_file)), "1.2.3"),
            _row(
                old,
                os.path.abspath(str(archive_file)),
                "1.2.3",
                sop_instance_uid="1.2.3.archive",
            ),
        ]
    )

    svc = _service_for(store)
    assert svc.relocate_study("1.2.3", old + os.sep + ".", str(new_root)) == 2
    paths = store.get_file_paths_for_study(
        "1.2.3", os.path.abspath(str(new_root))
    )
    assert os.path.abspath(str(moved_file)) in paths
    assert os.path.abspath(str(archive_file)) in paths


def test_relocate_no_commit_when_target_missing(tmp_path) -> None:
    store, root, files = _seed(tmp_path)
    for f in files:
        os.remove(f)
    os.rmdir(root)
    svc = _service_for(store)
    # New root has no matching files -> nothing relocated, no rows changed.
    empty_target = tmp_path / "empty_target"
    empty_target.mkdir()
    n = svc.relocate_study(
        "1.2.3", os.path.abspath(str(root)), os.path.abspath(str(empty_target))
    )
    assert n == 0
    # Original rows untouched.
    assert store.get_file_paths_for_study("1.2.3", os.path.abspath(str(root)))


def test_relocate_rejects_blank_inputs(tmp_path) -> None:
    store, root, _files = _seed(tmp_path)
    svc = _service_for(store)
    assert svc.relocate_study("", os.path.abspath(str(root)), "/x") == 0
    assert svc.relocate_study("1.2.3", "", "/x") == 0
    assert svc.relocate_study("1.2.3", os.path.abspath(str(root)), "") == 0


def test_remove_purges_rows(tmp_path) -> None:
    store, root, _files = _seed(tmp_path)
    svc = _service_for(store)
    deleted = svc.delete_grouped_study("1.2.3", os.path.abspath(str(root)))
    assert deleted == 3
    assert store.iter_study_groups() == []
