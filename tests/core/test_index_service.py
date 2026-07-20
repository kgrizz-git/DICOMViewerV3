"""Tests for core.study_index.index_service.LocalStudyIndexService.

Store, threads, keyring, and secure-unlink dependencies are stubbed so the
service's own orchestration/masking logic is exercised without a real
encrypted database.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from core.study_index import index_service as isvc
from core.study_index.index_service import LocalStudyIndexService


def _service() -> LocalStudyIndexService:
    return LocalStudyIndexService(config_manager=MagicMock())


class _FakeStore:
    def __init__(self, rows=None) -> None:
        self._rows = rows or [{"patient_name": "Doe", "patient_id": "P1", "accession_number": "A1"}]

    def search(self, **kwargs):
        return list(self._rows)

    search_grouped_studies = search

    def delete_study_group(self, study_uid, root):
        return 3

    def get_file_paths_for_study(self, study_uid, root):
        return ["/a.dcm", "/b.dcm"]


def test_search_without_privacy_returns_rows() -> None:
    svc = _service()
    svc._get_ready_store = lambda: _FakeStore()
    rows = svc.search()
    assert rows[0]["patient_name"] == "Doe"


def test_search_privacy_masks_identifiers() -> None:
    svc = _service()
    svc._get_ready_store = lambda: _FakeStore()
    rows = svc.search(privacy_mode=True)
    assert rows[0]["patient_name"] == "***"
    assert rows[0]["patient_id"] == "***"
    assert rows[0]["accession_number"] == "***"


def test_search_grouped_privacy_masks() -> None:
    svc = _service()
    svc._get_ready_store = lambda: _FakeStore()
    rows = svc.search_grouped_studies(privacy_mode=True)
    assert rows[0]["patient_name"] == "***"


def test_delete_grouped_backend_unavailable(monkeypatch) -> None:
    svc = _service()
    monkeypatch.setattr(svc, "is_backend_available", lambda: False)
    assert svc.delete_grouped_study("s", "/root") == 0


def test_delete_grouped_available(monkeypatch) -> None:
    svc = _service()
    monkeypatch.setattr(svc, "is_backend_available", lambda: True)
    svc._get_ready_store = lambda: _FakeStore()
    assert svc.delete_grouped_study("s", "/root") == 3


def test_get_file_paths_unavailable(monkeypatch) -> None:
    svc = _service()
    monkeypatch.setattr(svc, "is_backend_available", lambda: False)
    assert svc.get_file_paths_for_study("s", "/root") == []


def test_get_file_paths_available(monkeypatch) -> None:
    svc = _service()
    monkeypatch.setattr(svc, "is_backend_available", lambda: True)
    svc._get_ready_store = lambda: _FakeStore()
    assert svc.get_file_paths_for_study("s", "/root") == ["/a.dcm", "/b.dcm"]


def test_schedule_skips_when_cancelled() -> None:
    svc = _service()
    svc.schedule_index_after_load([], [], "/src", MagicMock(), was_cancelled=True)
    assert svc._write_thread is None


def test_schedule_skips_when_auto_add_off() -> None:
    svc = _service()
    svc._config.get_study_index_auto_add_on_open.return_value = False
    svc.schedule_index_after_load([MagicMock()], ["/x.dcm"], "/src", MagicMock())
    assert svc._write_thread is None


def test_schedule_force_indexes_when_auto_add_off(monkeypatch) -> None:
    svc = _service()
    svc._config.get_study_index_auto_add_on_open.return_value = False
    monkeypatch.setattr(svc, "is_backend_available", lambda: True)
    monkeypatch.setattr(svc, "_passphrase", lambda: "pw")
    monkeypatch.setattr(isvc.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(isvc, "dataset_to_index_row", lambda ds, **k: {"row": 1})
    started = {}

    class _FakeThread:
        def __init__(self, *a, **k) -> None:
            started["created"] = True

        def isRunning(self):
            return False

        def start(self):
            started["started"] = True

    monkeypatch.setattr(isvc, "StudyIndexWriteThread", _FakeThread)
    # "Add this one time" path: force=True indexes despite auto-add being off.
    svc.schedule_index_after_load(
        [MagicMock()], ["/x.dcm"], "/src", MagicMock(), force=True
    )
    assert started.get("started") is True


def test_schedule_builds_rows_and_starts_thread(monkeypatch) -> None:
    svc = _service()
    svc._config.get_study_index_auto_add_on_open.return_value = True
    monkeypatch.setattr(svc, "is_backend_available", lambda: True)
    monkeypatch.setattr(svc, "_passphrase", lambda: "pw")
    monkeypatch.setattr(isvc.os.path, "isfile", lambda p: True)
    monkeypatch.setattr(isvc, "dataset_to_index_row", lambda ds, **k: {"row": 1})
    started = {}

    class _FakeThread:
        def __init__(self, *a, **k) -> None:
            started["created"] = True

        def isRunning(self):
            return False

        def start(self):
            started["started"] = True

    monkeypatch.setattr(isvc, "StudyIndexWriteThread", _FakeThread)
    svc.schedule_index_after_load([MagicMock()], ["/x.dcm"], "/src", MagicMock())
    assert started.get("started") is True


def test_start_index_folder_connects_and_starts(monkeypatch) -> None:
    svc = _service()
    monkeypatch.setattr(svc, "_passphrase", lambda: "pw")
    created = {}

    class _FakeFolderThread:
        def __init__(self, *a, **k) -> None:
            self.progress = MagicMock()
            self.finished_ok = MagicMock()
            self.failed = MagicMock()

        def isRunning(self):
            return False

        def start(self):
            created["started"] = True

    monkeypatch.setattr(isvc, "StudyIndexFolderThread", _FakeFolderThread)
    svc.start_index_folder("/root", on_progress=lambda n: None,
                           on_finished=lambda n: None, on_failed=lambda e: None)
    assert created.get("started") is True
    assert svc._folder_cancel is False


def test_cancel_folder_index_sets_flag() -> None:
    svc = _service()
    svc.cancel_folder_index()
    assert svc._folder_cancel is True


def test_clear_all_data_blocked_by_write_thread() -> None:
    svc = _service()
    svc._write_thread = MagicMock()
    svc._write_thread.isRunning.return_value = True
    result = svc.clear_all_data()
    assert result.failed == 1


def test_clear_all_data_removes_files(monkeypatch) -> None:
    svc = _service()
    svc._config.get_study_index_db_path.return_value = "/tmp/idx.db"
    monkeypatch.setattr(isvc, "secure_unlink", lambda p: True)
    result = svc.clear_all_data()
    assert result.removed == 4  # db + journal + wal + shm
    assert svc._schema_initialized is False


def test_is_backend_available_returns_bool() -> None:
    assert isinstance(LocalStudyIndexService.is_backend_available(), bool)
