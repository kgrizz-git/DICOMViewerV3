"""
Unit tests for StudyIndex background threads.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("sqlcipher3", reason="sqlcipher3 not installed")
pytest.importorskip("keyring", reason="keyring not installed")

from core.study_index.index_write_thread import StudyIndexWriteThread


def test_study_index_write_thread(tmp_path):
    db_path = str(tmp_path / "thread.sqlite")
    thread = StudyIndexWriteThread(db_path, "pw-write", [])

    finished_called = False

    def on_finished():
        nonlocal finished_called
        finished_called = True

    thread.finished_ok.connect(on_finished)
    # Direct execution of run() to avoid thread timing/asynchrony issues in unit tests
    thread.run()
    assert finished_called is True


def test_study_index_write_thread_failure():
    # Pass None as db_path to trigger an exception
    thread = StudyIndexWriteThread(None, "pw-write", [])
    failed_reason = None

    def on_failed(reason):
        nonlocal failed_reason
        failed_reason = reason

    thread.failed.connect(on_failed)
    thread.run()
    assert failed_reason is not None
    assert "TypeError" in failed_reason or "AttributeError" in failed_reason


def test_study_index_integrity_thread():
    from core.study_index.index_integrity_thread import StudyIndexIntegrityThread

    mock_service = MagicMock()

    thread = StudyIndexIntegrityThread(mock_service)
    finished_records = None
    progress_update = None

    def on_finished(records):
        nonlocal finished_records
        finished_records = records

    def on_progress(done, total):
        nonlocal progress_update
        progress_update = (done, total)

    def scan_with_progress(*, progress):
        progress(1, 2)
        return ["dummy_record"]

    mock_service.integrity_scan.side_effect = scan_with_progress

    thread.finished_ok.connect(on_finished)
    thread.progress.connect(on_progress)

    thread.run()

    assert finished_records == ["dummy_record"]
    mock_service.integrity_scan.assert_called_once()
    assert progress_update == (1, 2)


def test_study_index_integrity_thread_failure():
    from core.study_index.index_integrity_thread import StudyIndexIntegrityThread

    mock_service = MagicMock()
    mock_service.integrity_scan.side_effect = RuntimeError("scan failed")

    thread = StudyIndexIntegrityThread(mock_service)
    failed_reason = None

    def on_failed(reason):
        nonlocal failed_reason
        failed_reason = reason

    thread.failed.connect(on_failed)
    thread.run()
    assert failed_reason == "RuntimeError: scan failed"


def test_study_index_folder_thread(tmp_path):
    from core.study_index.index_folder_thread import StudyIndexFolderThread

    # Create an empty dummy study folder
    root_dir = tmp_path / "study_root"
    root_dir.mkdir()

    db_path = str(tmp_path / "folder.sqlite")
    thread = StudyIndexFolderThread(str(root_dir), db_path, "pw-folder", lambda: False)

    finished_count = None

    def on_finished(count):
        nonlocal finished_count
        finished_count = count

    thread.finished_ok.connect(on_finished)
    thread.run()

    assert finished_count == 0


def test_study_index_folder_thread_cancelled(tmp_path):
    from core.study_index.index_folder_thread import StudyIndexFolderThread

    root_dir = tmp_path / "study_root"
    root_dir.mkdir()

    db_path = str(tmp_path / "folder.sqlite")
    thread = StudyIndexFolderThread(str(root_dir), db_path, "pw-folder", lambda: True)

    failed_reason = None

    def on_failed(reason):
        nonlocal failed_reason
        failed_reason = reason

    thread.failed.connect(on_failed)
    thread.run()

    assert failed_reason == "Cancelled"


def test_study_index_folder_thread_failure(tmp_path, monkeypatch):
    from core.study_index import index_folder_thread

    monkeypatch.setattr(
        index_folder_thread,
        "StudyIndexStore",
        MagicMock(side_effect=RuntimeError("store unavailable")),
    )
    thread = index_folder_thread.StudyIndexFolderThread(
        str(tmp_path), "folder.sqlite", "pw-folder", lambda: False
    )

    failed_reason = None

    def on_failed(reason):
        nonlocal failed_reason
        failed_reason = reason

    thread.failed.connect(on_failed)
    thread.run()

    assert failed_reason == "RuntimeError: store unavailable"
