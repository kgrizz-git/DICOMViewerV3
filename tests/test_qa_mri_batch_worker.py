"""
Unit tests for P4-M1 — QAMRIBatchWorker.

Exercises the batch worker's ``run()`` directly (not via QThread.start()) so
tests stay Qt-light: per-series error isolation, the ``series_completed``
count sequence, and cooperative cancellation producing a partial
``ACRMBatchResult``. ``qa.pylinac_runner.run_acr_mri_large_analysis``
(re-exported into ``qa.worker``) is monkeypatched so no real pylinac analysis
runs.
"""

from __future__ import annotations

import pytest

import qa.worker as worker_mod
from qa.analysis_types import ACRMBatchResult, QARequest, QAResult


def _make_requests(n: int) -> list[QARequest]:
    return [
        QARequest(
            analysis_type="acr_mri_large",
            dicom_paths=[f"/fake/series-{i}/file.dcm"],
            study_uid=f"study-{i}",
            series_uid=f"series-{i}",
            modality="MR",
        )
        for i in range(n)
    ]


def test_series_completed_sequence(qapp, monkeypatch) -> None:
    """series_completed fires once per series with a correct (done, total) sequence."""
    n = 3
    requests = _make_requests(n)
    labels = [f"Series {i}" for i in range(n)]

    def fake_run(request: QARequest) -> QAResult:
        return QAResult(success=True, analysis_type=request.analysis_type)

    monkeypatch.setattr(worker_mod, "run_acr_mri_large_analysis", fake_run)

    w = worker_mod.QAMRIBatchWorker(requests, labels)
    seen: list[tuple[int, int]] = []
    batches: list[ACRMBatchResult] = []
    w.series_completed.connect(lambda done, total, result: seen.append((done, total)))
    w.batch_result_ready.connect(batches.append)

    w.run()

    assert seen == [(1, n), (2, n), (3, n)]
    assert len(batches) == 1
    batch = batches[0]
    assert len(batch.run_results) == n
    assert batch.run_labels == labels
    assert all(r.success for r in batch.run_results)
    w.image_temp_dir.cleanup()


def test_per_series_error_isolation(qapp, monkeypatch) -> None:
    """One failing series does not abort the batch; it becomes a failed QAResult."""
    n = 3
    requests = _make_requests(n)
    labels = [f"Series {i}" for i in range(n)]

    def fake_run(request: QARequest) -> QAResult:
        if request.series_uid == "series-1":
            raise RuntimeError("boom")
        return QAResult(success=True, analysis_type=request.analysis_type)

    monkeypatch.setattr(worker_mod, "run_acr_mri_large_analysis", fake_run)

    w = worker_mod.QAMRIBatchWorker(requests, labels)
    batches: list[ACRMBatchResult] = []
    w.batch_result_ready.connect(batches.append)

    w.run()

    assert len(batches) == 1
    batch = batches[0]
    assert len(batch.run_results) == n
    statuses = [r.success for r in batch.run_results]
    assert statuses == [True, False, True]
    assert "boom" in batch.run_results[1].errors[0]
    # The batch continued and completed the remaining series.
    assert batch.run_labels == labels
    w.image_temp_dir.cleanup()


def test_cooperative_cancellation_produces_partial_result(qapp, monkeypatch) -> None:
    """Cancelling between series finishes the in-flight run and skips the rest."""
    n = 4
    requests = _make_requests(n)
    labels = [f"Series {i}" for i in range(n)]

    w = worker_mod.QAMRIBatchWorker(requests, labels)

    def fake_run(request: QARequest) -> QAResult:
        # Cancel after the first series has started/finished processing --
        # simulates a user clicking Cancel mid-batch. The in-flight series
        # (this one) still completes and is included in the result.
        if request.series_uid == "series-0":
            w.cancel()
        return QAResult(success=True, analysis_type=request.analysis_type)

    monkeypatch.setattr(worker_mod, "run_acr_mri_large_analysis", fake_run)

    batches: list[ACRMBatchResult] = []
    seen: list[tuple[int, int]] = []
    w.batch_result_ready.connect(batches.append)
    w.series_completed.connect(lambda done, total, result: seen.append((done, total)))

    w.run()

    assert len(batches) == 1
    batch = batches[0]
    # Only the in-flight (first) series ran; the remaining 3 were skipped.
    assert len(batch.run_results) == 1
    assert batch.run_labels == ["Series 0"]
    assert seen == [(1, n)]
    w.image_temp_dir.cleanup()


def test_series_labels_must_be_parallel_to_requests() -> None:
    """Constructor validates that series_labels and requests are the same length."""
    requests = _make_requests(2)
    with pytest.raises(ValueError, match="parallel"):
        worker_mod.QAMRIBatchWorker(requests, ["only-one-label"])


def test_qarequest_cloning_prevents_side_effect(qapp, monkeypatch) -> None:
    """Worker clones QARequest so input request analyzed_image_out_path remains unmodified."""
    requests = _make_requests(1)
    original_req = requests[0]
    assert original_req.analyzed_image_out_path is None

    received_requests: list[QARequest] = []

    def fake_run(request: QARequest) -> QAResult:
        received_requests.append(request)
        return QAResult(success=True, analysis_type=request.analysis_type)

    monkeypatch.setattr(worker_mod, "run_acr_mri_large_analysis", fake_run)

    w = worker_mod.QAMRIBatchWorker(requests, ["Series 0"])
    w.run()

    assert original_req.analyzed_image_out_path is None
    assert len(received_requests) == 1
    assert received_requests[0].analyzed_image_out_path is not None
    assert received_requests[0] is not original_req
    w.image_temp_dir.cleanup()


def test_two_series_get_distinct_module_images_subdir(qapp, monkeypatch) -> None:
    """Each series gets its own per-series module-images subdirectory (no collision)."""
    n = 2
    requests = _make_requests(n)
    labels = [f"Series {i}" for i in range(n)]

    received_module_dirs: list[str | None] = []

    def fake_run(request: QARequest) -> QAResult:
        received_module_dirs.append(request.module_images_out_dir)
        return QAResult(success=True, analysis_type=request.analysis_type)

    monkeypatch.setattr(worker_mod, "run_acr_mri_large_analysis", fake_run)

    w = worker_mod.QAMRIBatchWorker(requests, labels)
    w.run()

    assert w.module_images_temp_dir is not None
    assert received_module_dirs[0] != received_module_dirs[1]
    # Both subdirs live under the worker-owned module-images temp dir.
    assert received_module_dirs[0].startswith(w.module_images_temp_dir.name)
    assert received_module_dirs[1].startswith(w.module_images_temp_dir.name)
    w.image_temp_dir.cleanup()
    w.module_images_temp_dir.cleanup()


def test_no_module_images_dir_when_embed_off(qapp, monkeypatch) -> None:
    """When embed_module_images_in_xlsx is False for all requests, no module dir is created."""
    n = 2
    requests = _make_requests(n)
    for r in requests:
        r.embed_module_images_in_xlsx = False
    labels = [f"Series {i}" for i in range(n)]

    received_module_dirs: list[str | None] = []

    def fake_run(request: QARequest) -> QAResult:
        received_module_dirs.append(request.module_images_out_dir)
        return QAResult(success=True, analysis_type=request.analysis_type)

    monkeypatch.setattr(worker_mod, "run_acr_mri_large_analysis", fake_run)

    w = worker_mod.QAMRIBatchWorker(requests, labels)
    w.run()

    assert w.module_images_temp_dir is None
    assert received_module_dirs == [None, None]
    w.image_temp_dir.cleanup()
