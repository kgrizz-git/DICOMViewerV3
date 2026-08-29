"""
Tests for P2-I3: facade/worker temp-dir lifecycle for module image directories.

Covers CT single (nested under composite dir), CT batch (worker-owned sibling
dir), and MRI single (standalone dir). No live analyze, no DICOM.
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt

import gui.qa_app_facade as facade_module
import qa.worker as worker_mod
from gui.qa_app_facade import QAAppFacade
from gui.qa_module_image_tempdir import assign_module_images_out_dir
from qa.analysis_types import CTBatchResult, QARequest, QAResult

pytestmark = pytest.mark.qt


class _Signal:
    def __init__(self) -> None:
        self.callbacks = []

    def connect(self, callback) -> None:
        self.callbacks.append(callback)

    def emit(self, *args) -> None:
        for callback in self.callbacks:
            callback(*args)


class _Progress:
    def __init__(self, *_args) -> None:
        self.canceled = _Signal()
        self.closed = False

    def setWindowTitle(self, _value) -> None:
        pass

    def setWindowModality(self, _value) -> None:
        pass

    def setWindowFlags(self, value):
        return value

    def windowFlags(self):
        return Qt.WindowType.Widget

    def show(self) -> None:
        pass

    def activateWindow(self) -> None:
        pass

    def raise_(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class _FakeWorker:
    def __init__(self, *_args, **_kwargs) -> None:
        self.result_ready = _Signal()
        self.batch_result_ready = _Signal()
        self.series_completed = _Signal()
        self.finished = _Signal()
        self.image_temp_dir = MagicMock()
        self.module_images_temp_dir = MagicMock()
        self.started = False
        self.cancelled = False

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


def _result() -> QAResult:
    return QAResult(
        success=True,
        analysis_type="acr_ct",
        metrics={"num_images": 1},
        raw_pylinac={"num_images": 1},
    )


def _app(save_path: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        main_window=MagicMock(),
        _prompt_save_path=MagicMock(return_value=save_path),
        _qa_worker=None,
        _qa_batch_worker=None,
        _qa_ct_batch_worker=None,
        _ct_batch_result_dialog=None,
        _mri_compare_result_dialog=None,
    )


# ---------------------------------------------------------------------------
# assign_module_images_out_dir helper
# ---------------------------------------------------------------------------


def test_assign_embed_off_leaves_dir_unset() -> None:
    """When embed is False, module_images_out_dir stays None, no cleanup."""
    req = QARequest(analysis_type="acr_ct", embed_module_images_in_xlsx=False)
    cleanup = assign_module_images_out_dir(req)
    assert cleanup is None
    assert req.module_images_out_dir is None


def test_assign_standalone_creates_dir_and_returns_cleanup() -> None:
    """Without a composite dir, a standalone temp dir is created + cleanup returned."""
    req = QARequest(analysis_type="acr_mri_large", embed_module_images_in_xlsx=True)
    cleanup = assign_module_images_out_dir(req)
    assert cleanup is not None
    assert req.module_images_out_dir is not None
    assert os.path.isdir(req.module_images_out_dir)
    assert "module-images" in req.module_images_out_dir
    cleanup()
    assert not os.path.isdir(req.module_images_out_dir)


def test_assign_nested_under_composite_no_cleanup() -> None:
    """With a composite dir, module dir nests under it; no cleanup returned."""
    import tempfile

    req = QARequest(analysis_type="acr_ct", embed_module_images_in_xlsx=True)
    composite = tempfile.TemporaryDirectory(prefix="qa-test-composite-")
    cleanup = assign_module_images_out_dir(req, composite_image_temp_dir=composite)
    assert cleanup is None
    assert req.module_images_out_dir is not None
    assert req.module_images_out_dir.startswith(composite.name)
    assert os.path.isdir(req.module_images_out_dir)
    composite.cleanup()


# ---------------------------------------------------------------------------
# start_qa_worker: module_images_cleanup invoked on result and cancel
# ---------------------------------------------------------------------------


def test_start_qa_worker_cleans_module_images_on_result(qapp, monkeypatch) -> None:
    """module_images_cleanup is called after export (MRI single path)."""
    app = _app()
    facade = QAAppFacade(app)
    progress = _Progress()
    worker = _FakeWorker()
    module_cleanup = MagicMock()
    monkeypatch.setattr(facade_module, "QProgressDialog", lambda *args: progress)
    monkeypatch.setattr(facade_module, "QAAnalysisWorker", lambda request: worker)
    monkeypatch.setattr(QAAppFacade, "show_qa_result_dialog", MagicMock())
    monkeypatch.setattr(QAAppFacade, "offer_open_single_run_pdf", MagicMock())
    monkeypatch.setattr(QAAppFacade, "export_qa_results", MagicMock())

    facade.start_qa_worker(
        QARequest("acr_mri_large"),
        progress_title="Synthetic",
        progress_label="Synthetic run",
        result_dialog_title="Synthetic result",
        json_default_stem="synthetic",
        module_images_cleanup=module_cleanup,
    )
    worker.result_ready.emit(_result())

    module_cleanup.assert_called_once()


def test_start_qa_worker_cleans_module_images_on_cancel(qapp, monkeypatch) -> None:
    """module_images_cleanup is called even when the run is cancelled."""
    app = _app()
    facade = QAAppFacade(app)
    progress = _Progress()
    worker = _FakeWorker()
    module_cleanup = MagicMock()
    monkeypatch.setattr(facade_module, "QProgressDialog", lambda *args: progress)
    monkeypatch.setattr(facade_module, "QAAnalysisWorker", lambda request: worker)
    monkeypatch.setattr(QAAppFacade, "show_qa_result_dialog", MagicMock())
    monkeypatch.setattr(QAAppFacade, "offer_open_single_run_pdf", MagicMock())
    monkeypatch.setattr(QAAppFacade, "export_qa_results", MagicMock())

    facade.start_qa_worker(
        QARequest("acr_mri_large"),
        progress_title="Synthetic",
        progress_label="Synthetic run",
        result_dialog_title="Synthetic result",
        json_default_stem="synthetic",
        module_images_cleanup=module_cleanup,
    )
    # Simulate cancel before result arrives.
    progress.canceled.emit()
    worker.result_ready.emit(_result())

    module_cleanup.assert_called_once()


def test_start_qa_worker_no_cleanup_when_embed_off(qapp, monkeypatch) -> None:
    """When embed is off, no module_images_cleanup is passed; nothing to call."""
    app = _app()
    facade = QAAppFacade(app)
    progress = _Progress()
    worker = _FakeWorker()
    monkeypatch.setattr(facade_module, "QProgressDialog", lambda *args: progress)
    monkeypatch.setattr(facade_module, "QAAnalysisWorker", lambda request: worker)
    monkeypatch.setattr(QAAppFacade, "show_qa_result_dialog", MagicMock())
    monkeypatch.setattr(QAAppFacade, "offer_open_single_run_pdf", MagicMock())
    monkeypatch.setattr(QAAppFacade, "export_qa_results", MagicMock())

    # embed off → assign_module_images_out_dir returns None → no cleanup passed
    req = QARequest("acr_mri_large", embed_module_images_in_xlsx=False)
    facade.start_qa_worker(
        req,
        progress_title="Synthetic",
        progress_label="Synthetic run",
        result_dialog_title="Synthetic result",
        json_default_stem="synthetic",
        module_images_cleanup=None,
    )
    worker.result_ready.emit(_result())
    # No assertion needed — just verifying no crash with None cleanup.


# ---------------------------------------------------------------------------
# CT batch worker: module_images_temp_dir created when embed on
# ---------------------------------------------------------------------------


def test_batch_worker_creates_module_images_dir_when_embed_on(qapp, monkeypatch) -> None:
    """QACTBatchWorker creates module_images_temp_dir when embed is on."""
    requests = [
        QARequest(
            analysis_type="acr_ct",
            dicom_paths=["/fake/a.dcm"],
            embed_module_images_in_xlsx=True,
        )
    ]
    labels = ["Series 0"]

    def fake_run(request: QARequest) -> QAResult:
        # module_images_out_dir must be set on the cloned request
        assert request.module_images_out_dir is not None
        assert os.path.isdir(request.module_images_out_dir)
        return QAResult(success=True, analysis_type=request.analysis_type)

    monkeypatch.setattr(worker_mod, "run_acr_ct_analysis", fake_run)

    w = worker_mod.QACTBatchWorker(requests, labels)
    assert w.module_images_temp_dir is not None
    assert os.path.isdir(w.module_images_temp_dir.name)

    batches: list[CTBatchResult] = []
    w.batch_result_ready.connect(batches.append)
    w.run()

    assert len(batches) == 1
    w.image_temp_dir.cleanup()
    w.module_images_temp_dir.cleanup()


def test_batch_worker_per_series_module_image_subdirs(qapp, monkeypatch) -> None:
    """Each series gets its own subdirectory so hu.png cannot collide."""
    requests = [
        QARequest(
            analysis_type="acr_ct",
            dicom_paths=["/fake/a.dcm"],
            embed_module_images_in_xlsx=True,
        ),
        QARequest(
            analysis_type="acr_ct",
            dicom_paths=["/fake/b.dcm"],
            embed_module_images_in_xlsx=True,
        ),
    ]
    labels = ["Series 0", "Series 1"]
    seen_dirs: list[str] = []

    def fake_run(request: QARequest) -> QAResult:
        assert request.module_images_out_dir is not None
        out = request.module_images_out_dir
        os.makedirs(out, exist_ok=True)
        hu = os.path.join(out, "hu.png")
        with open(hu, "wb") as handle:
            handle.write(b"\x89PNG" + os.path.basename(out).encode("ascii"))
        seen_dirs.append(out)
        return QAResult(
            success=True,
            analysis_type=request.analysis_type,
            analyzed_module_images={"hu": hu},
        )

    monkeypatch.setattr(worker_mod, "run_acr_ct_analysis", fake_run)

    w = worker_mod.QACTBatchWorker(requests, labels)
    batches: list[CTBatchResult] = []
    w.batch_result_ready.connect(batches.append)
    w.run()

    assert len(seen_dirs) == 2
    assert seen_dirs[0] != seen_dirs[1]
    assert os.path.commonpath(seen_dirs) == w.module_images_temp_dir.name
    assert batches[0].run_results[0].analyzed_module_images["hu"] != (
        batches[0].run_results[1].analyzed_module_images["hu"]
    )
    w.image_temp_dir.cleanup()
    w.module_images_temp_dir.cleanup()


def test_batch_worker_no_module_images_dir_when_embed_off(qapp, monkeypatch) -> None:
    """QACTBatchWorker leaves module_images_temp_dir None when embed is off."""
    requests = [
        QARequest(
            analysis_type="acr_ct",
            dicom_paths=["/fake/a.dcm"],
            embed_module_images_in_xlsx=False,
        )
    ]
    labels = ["Series 0"]

    def fake_run(request: QARequest) -> QAResult:
        assert request.module_images_out_dir is None
        return QAResult(success=True, analysis_type=request.analysis_type)

    monkeypatch.setattr(worker_mod, "run_acr_ct_analysis", fake_run)

    w = worker_mod.QACTBatchWorker(requests, labels)
    assert w.module_images_temp_dir is None

    batches: list[CTBatchResult] = []
    w.batch_result_ready.connect(batches.append)
    w.run()

    assert len(batches) == 1
    w.image_temp_dir.cleanup()


# ---------------------------------------------------------------------------
# show_ct_batch_result_dialog: cleans module_images_temp_dir on destroy
# ---------------------------------------------------------------------------


def test_batch_dialog_destroy_cleans_module_images_temp_dir(qapp, monkeypatch) -> None:
    """on_destroyed cleans both image_temp_dir and module_images_temp_dir."""
    app = _app()
    facade = QAAppFacade(app)
    worker = _FakeWorker()  # provides image_temp_dir + module_images_temp_dir mocks
    batch = CTBatchResult(
        run_results=[QAResult(success=True, analysis_type="acr_ct")],
        run_labels=["Series 0"],
    )
    dialog = MagicMock()
    captured: dict = {}

    def _capture(*args, **kw):
        captured.update(kw)
        return dialog

    monkeypatch.setattr(facade_module, "create_ct_batch_result_dialog", _capture)

    facade.show_ct_batch_result_dialog(worker, batch)

    captured["on_destroyed"]()

    worker.image_temp_dir.cleanup.assert_called_once()
    worker.module_images_temp_dir.cleanup.assert_called_once()


def test_batch_dialog_empty_batch_cleans_module_images(qapp, monkeypatch) -> None:
    """Empty batch result cleans module_images_temp_dir immediately."""
    app = _app()
    facade = QAAppFacade(app)
    worker = _FakeWorker()
    batch = CTBatchResult(run_results=[], run_labels=[])

    facade.show_ct_batch_result_dialog(worker, batch)

    worker.image_temp_dir.cleanup.assert_called_once()
    worker.module_images_temp_dir.cleanup.assert_called_once()
