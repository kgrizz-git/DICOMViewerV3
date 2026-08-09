"""
Unit tests for ``core.study_index.index_folder_thread.StudyIndexFolderThread``.

Mocks ``pydicom.dcmread``, ``StudyIndexStore``, and ``os.walk`` to exercise the
success, cancel, and failure signal paths without touching disk or SQLCipher.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QTimer

from core.study_index.index_folder_thread import StudyIndexFolderThread

pytestmark = pytest.mark.qt


def _run(thread: StudyIndexFolderThread, qapp) -> str:
    """Run the thread and return which terminal signal fired ('ok'/'failed'/'')."""
    outcome: dict[str, str] = {"signal": ""}

    def _on_ok(n: int) -> None:
        outcome["signal"] = "ok"
        qapp.exit()

    def _on_fail(msg: str) -> None:
        outcome["signal"] = "failed"
        qapp.exit()

    thread.finished_ok.connect(_on_ok)
    thread.failed.connect(_on_fail)
    thread.start()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(qapp.exit)
    timer.start(5000)
    qapp.exec()
    assert thread.wait(5000), "indexing thread did not finish within five seconds"
    return outcome["signal"]


def _make_thread(cancel_predicate=lambda: False):
    return StudyIndexFolderThread(
        root_dir="/data/studies",
        db_path="/data/idx.sqlite",
        passphrase="secret",
        should_cancel=cancel_predicate,
    )


class TestStudyIndexFolderThread:
    def test_indexes_files_and_emits_finished(self, qapp):
        walk_paths = [("/data/studies", [], ["a.dcm", "b.dcm"])]
        thread = _make_thread()
        fake_ds = MagicMock()
        fake_ds.filename = "/data/studies/a.dcm"
        captured_rows: list[dict] = []
        with patch("core.study_index.index_folder_thread.os.walk", return_value=walk_paths), patch(
            "core.study_index.index_folder_thread.pydicom.dcmread",
            return_value=fake_ds,
        ) as dcmread, patch(
            "core.study_index.index_folder_thread.StudyIndexStore"
        ) as store_cls, patch(
            "core.study_index.index_folder_thread.dataset_to_index_row",
            side_effect=lambda ds, **kw: captured_rows.append(kw) or {"file_path": kw["file_path"]},
        ) as to_row:
            store = store_cls.return_value
            signal = _run(thread, qapp)
        assert signal == "ok"
        assert dcmread.call_count == 2
        # Delegation: each file is converted via dataset_to_index_row with the
        # file_path fallback and the configured study root.
        assert to_row.call_count == 2
        assert captured_rows[0]["study_root_path"] == os.path.abspath("/data/studies")
        store.init_schema.assert_called_once()
        store.upsert_rows.assert_called_once()
        rows = store.upsert_rows.call_args.args[0]
        assert len(rows) == 2

    def test_cancel_early_emits_failed(self, qapp):
        walk_paths = [("/data/studies", [], ["a.dcm"])]
        cancel = {"flag": True}
        thread = _make_thread(cancel_predicate=lambda: cancel["flag"])
        with patch("core.study_index.index_folder_thread.os.walk", return_value=walk_paths), patch(
            "core.study_index.index_folder_thread.pydicom.dcmread"
        ) as dcmread, patch(
            "core.study_index.index_folder_thread.StudyIndexStore"
        ) as store_cls:
            signal = _run(thread, qapp)
        assert signal == "failed"
        dcmread.assert_not_called()
        store_cls.assert_not_called()

    def test_cancel_before_first_read_emits_failed(self, qapp):
        # should_cancel is checked once before the path loop and again before each
        # read, so cancellation always precedes reads; with 2 files the second
        # check (call #2) cancels before any dcmread occurs.
        walk_paths = [("/data/studies", [], ["a.dcm", "b.dcm"])]
        calls = {"n": 0}

        def cancel_predicate() -> bool:
            calls["n"] += 1
            return calls["n"] >= 2

        thread = _make_thread(cancel_predicate=cancel_predicate)
        fake_ds = MagicMock()
        with patch("core.study_index.index_folder_thread.os.walk", return_value=walk_paths), patch(
            "core.study_index.index_folder_thread.pydicom.dcmread",
            return_value=fake_ds,
        ) as dcmread, patch("core.study_index.index_folder_thread.StudyIndexStore") as store_cls:
            signal = _run(thread, qapp)
        assert signal == "failed"
        assert dcmread.call_count == 0
        store_cls.assert_not_called()

    def test_read_errors_skipped(self, qapp):
        walk_paths = [("/data/studies", [], ["good.dcm", "bad.dcm"])]
        thread = _make_thread()
        good = MagicMock()
        good.filename = "/data/studies/good.dcm"

        def _dcmread(path, **kwargs):
            if "bad" in path:
                raise ValueError("unreadable")
            return good

        with patch("core.study_index.index_folder_thread.os.walk", return_value=walk_paths), patch(
            "core.study_index.index_folder_thread.pydicom.dcmread",
            side_effect=_dcmread,
        ), patch("core.study_index.index_folder_thread.StudyIndexStore") as store_cls:
            signal = _run(thread, qapp)
        assert signal == "ok"
        rows = store_cls.return_value.upsert_rows.call_args.args[0]
        assert len(rows) == 1

    def test_store_constructor_receives_db_and_passphrase(self, qapp):
        walk_paths = [("/data/studies", [], ["a.dcm"])]
        thread = _make_thread()
        fake_ds = MagicMock()
        with patch("core.study_index.index_folder_thread.os.walk", return_value=walk_paths), patch(
            "core.study_index.index_folder_thread.pydicom.dcmread",
            return_value=fake_ds,
        ), patch("core.study_index.index_folder_thread.StudyIndexStore") as store_cls:
            assert _run(thread, qapp) == "ok"
        assert store_cls.call_args.args[0] == "/data/idx.sqlite"
        assert store_cls.call_args.args[1] == "secret"

    def test_unexpected_store_error_emits_failed(self, qapp):
        walk_paths = [("/data/studies", [], ["a.dcm"])]
        thread = _make_thread()
        fake_ds = MagicMock()
        with patch("core.study_index.index_folder_thread.os.walk", return_value=walk_paths), patch(
            "core.study_index.index_folder_thread.pydicom.dcmread",
            return_value=fake_ds,
        ), patch(
            "core.study_index.index_folder_thread.StudyIndexStore"
        ) as store_cls:
            store_cls.return_value.upsert_rows.side_effect = RuntimeError("db down")
            signal = _run(thread, qapp)
        assert signal == "failed"
