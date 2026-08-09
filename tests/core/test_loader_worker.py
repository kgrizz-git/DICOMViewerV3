"""
Tests for ``core.loader_worker`` — LoaderWorker QThread.

Uses a QApplication; no DICOM files required (all data is synthetic/mocked).
"""

from __future__ import annotations

import pytest

from core.loader_worker import LoaderWorker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loader_fn(datasets, *, raise_exc=None):
    """Return a synchronous loader function that mimics DICOMLoader.load_files."""

    def loader_fn(progress_callback):
        if raise_exc:
            raise raise_exc
        progress_callback(1, max(len(datasets), 1), "file.dcm")
        return datasets

    return loader_fn


def _make_organize_fn(result):
    """Return a synchronous organizer function returning a fixed result."""

    def organize_fn(datasets):
        return result

    return organize_fn


def _run_worker(worker, timeout_ms=5000):
    """Start worker, run event loop until it emits any terminal signal."""
    from PySide6.QtCore import QEventLoop, QTimer

    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    worker.finished.connect(loop.quit)  # type: ignore[arg-type]
    worker.organized.connect(loop.quit)  # type: ignore[arg-type]
    worker.error.connect(loop.quit)  # type: ignore[arg-type]
    timer.start(timeout_ms)
    worker.start()
    loop.exec()
    # Ensure run() has returned before the caller drops its reference,
    # otherwise Qt aborts on destroying a still-running QThread.
    worker.wait(timeout_ms)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.qt
class TestLoaderWorkerFinishedSignal:
    """LoaderWorker without an organize_fn emits ``finished``."""

    def test_finished_emitted_with_datasets(self, qapp):
        """Worker emits finished(datasets, []) when loader succeeds."""
        fake_ds = [object(), object()]
        received: list = []

        worker = LoaderWorker(_make_loader_fn(fake_ds))
        worker.finished.connect(lambda ds, failed: received.extend([ds, failed]))
        _run_worker(worker)

        assert received, "finished signal was not emitted"
        assert received[0] == fake_ds
        assert received[1] == []

    def test_progress_callback_is_forwarded(self, qapp):
        """Worker emits progress(current, total, filename) during loading."""
        progress_calls: list[tuple] = []
        fake_ds = [object()]

        worker = LoaderWorker(_make_loader_fn(fake_ds))
        worker.progress.connect(lambda c, t, f: progress_calls.append((c, t, f)))
        _run_worker(worker)

        assert any(call[2] == "file.dcm" for call in progress_calls)

    def test_error_signal_on_exception(self, qapp):
        """Worker emits error(msg) when loader_fn raises."""
        errors: list[str] = []

        worker = LoaderWorker(_make_loader_fn([], raise_exc=RuntimeError("boom")))
        worker.error.connect(errors.append)
        _run_worker(worker)

        assert errors, "error signal was not emitted"
        assert "RuntimeError" in errors[0]
        assert "boom" in errors[0]

    def test_empty_dataset_list_still_emits_finished(self, qapp):
        """Worker handles empty dataset list gracefully."""
        received: list = []

        worker = LoaderWorker(_make_loader_fn([]))
        worker.finished.connect(lambda ds, failed: received.extend([ds, failed]))
        _run_worker(worker)

        assert len(received) == 2
        assert received[0] == []


@pytest.mark.qt
class TestLoaderWorkerOrganizedSignal:
    """LoaderWorker with organize_fn emits ``organized``."""

    def test_organized_emitted_with_merge_result(self, qapp):
        """Worker emits organized(datasets, merge_result) when both fns succeed."""
        fake_ds = [object(), object(), object()]

        class _FakeMerge:
            new_series = (1,)
            appended_series = ()
            added_file_count = 3

        merge = _FakeMerge()
        received: list = []

        worker = LoaderWorker(
            _make_loader_fn(fake_ds),
            organize_fn=_make_organize_fn(merge),
        )
        worker.organized.connect(lambda ds, r: received.extend([ds, r]))
        _run_worker(worker)

        assert received, "organized signal was not emitted"
        assert received[0] == fake_ds
        assert received[1] is merge

    def test_organize_fn_not_called_on_empty_datasets(self, qapp):
        """When datasets is empty, organize_fn is skipped; finished is emitted."""
        organize_called: list[bool] = []

        def organize_fn(ds):
            organize_called.append(True)
            return None

        worker = LoaderWorker(_make_loader_fn([]), organize_fn=organize_fn)

        received_finished: list = []
        worker.finished.connect(
            lambda ds, failed: received_finished.extend([ds, failed])
        )
        _run_worker(worker)

        assert not organize_called, "organize_fn must not be called on empty datasets"
        assert received_finished[0] == []

    def test_organize_error_emits_error_signal(self, qapp):
        """If organize_fn raises, the error signal is emitted."""
        fake_ds = [object()]
        errors: list[str] = []

        def bad_organize(ds):
            raise ValueError("organize failed")

        worker = LoaderWorker(_make_loader_fn(fake_ds), organize_fn=bad_organize)
        worker.error.connect(errors.append)
        _run_worker(worker)

        assert errors
        assert "organize failed" in errors[0]
