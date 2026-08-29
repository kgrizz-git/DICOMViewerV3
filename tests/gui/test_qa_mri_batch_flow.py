"""
Unit tests for P4-M3 — multi-series ACR MRI Large batch flow.

Exercises ``gui.qa_mri_batch_flow.open_acr_mri_batch_analysis`` with the
selection dialog, MRI options, and ``QAMRIBatchWorker`` all mocked. Verifies
the flow calls selection + options + stamp + worker, that ``compare_request``
is ignored (OQ-7), that progress/cancel wire ``worker.cancel()``, and that
temp-dir cleanup matches the CT batch lifecycle (immediate on empty batch,
deferred to dialog destroy otherwise). No live ``analyze()`` runs.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import Qt

import gui.qa_mri_batch_flow as flow_mod
from gui.qa_mri_batch_flow import (
    _start_acr_mri_series_batch_worker,
    open_acr_mri_batch_analysis,
)
from qa.analysis_types import ACRMBatchResult, QARequest, QAResult

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
        self._value = 0
        self._label = ""

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

    def setValue(self, value) -> None:
        self._value = value

    def setLabelText(self, text) -> None:
        self._label = text


class _Worker:
    def __init__(self, *args, **kwargs) -> None:
        self.series_completed = _Signal()
        self.batch_result_ready = _Signal()
        self.finished = _Signal()
        self.image_temp_dir = MagicMock()
        self.module_images_temp_dir = MagicMock()
        self.started = False
        self.cancelled = False
        self.requests = args[0] if args else []

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


def _make_app() -> SimpleNamespace:
    app = SimpleNamespace()
    app.main_window = MagicMock()
    app.dicom_organizer = MagicMock()
    app.file_dialog = MagicMock()
    app._file_series_coordinator = MagicMock()
    app._file_series_coordinator.get_file_path_for_dataset = MagicMock(return_value="/p.dcm")
    app._qa_mri_batch_worker = None
    app._mri_batch_result_dialog = None
    app.config_manager = MagicMock()
    app.config_manager.get_acr_qa_vanilla_pylinac.return_value = False
    app.config_manager.get_acr_qa_embed_module_images_in_xlsx.return_value = True
    app.config_manager.get_acr_mri_low_contrast_method.return_value = "rose"
    app.config_manager.get_acr_mri_low_contrast_visibility_threshold.return_value = 0.001
    app.config_manager.get_acr_mri_low_contrast_visibility_sanity_multiplier.return_value = 1.0
    return app


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


def test_menu_action_exists() -> None:
    """The ACR MRI Batch menu action is registered next to ACR MRI Phantom."""
    from gui import main_window_menu_builder as mb

    assert hasattr(mb, "build_menu_bar")
    src = mb.build_menu_bar.__code__.co_consts
    # The distinct label string is present in the module constants.
    found = any(c == "ACR MRI Batch (pylinac)..." for c in src if isinstance(c, str))
    assert found, "ACR MRI Batch (pylinac)... menu label not found in builder"


def test_flow_calls_selection_options_stamp_and_worker(monkeypatch) -> None:
    """Full flow: selection → options → stamp → QAMRIBatchWorker.start()."""
    app = _make_app()
    requests = _make_requests(2)
    labels = ["Series 0", "Series 1"]

    monkeypatch.setattr(
        flow_mod,
        "prompt_mri_batch_series_selection",
        lambda *_a, **_k: (requests, labels),
    )
    # prompt_acr_mri_options returns a 10-tuple; compare_request is index 7.
    monkeypatch.setattr(
        flow_mod,
        "prompt_acr_mri_options",
        lambda *_a, **_k: (1, False, 1, 0.0, "rose", 0.001, 1.0, MagicMock(), False, True),
    )
    stamped = []

    def fake_stamp(reqs, **kwargs) -> list[QARequest]:
        stamped.append(kwargs)
        return reqs

    monkeypatch.setattr(flow_mod, "stamp_mri_batch_options", fake_stamp)
    start = MagicMock()
    monkeypatch.setattr(flow_mod, "_start_acr_mri_series_batch_worker", start)

    open_acr_mri_batch_analysis(app)

    start.assert_called_once()
    args = start.call_args.args
    assert args[0] is app
    assert len(args[1]) == 2  # stamped requests
    assert args[2] == labels
    # stamp was called with the MRI options (no compare field).
    assert len(stamped) == 1
    assert "echo_number" in stamped[0]
    assert stamped[0]["echo_number"] == 1


def test_compare_request_is_ignored(monkeypatch) -> None:
    """OQ-7: compare_request from prompt_acr_mri_options is dropped in batch."""
    app = _make_app()
    requests = _make_requests(1)
    labels = ["Series 0"]
    compare_obj = MagicMock()

    monkeypatch.setattr(
        flow_mod,
        "prompt_mri_batch_series_selection",
        lambda *_a, **_k: (requests, labels),
    )
    monkeypatch.setattr(
        flow_mod,
        "prompt_acr_mri_options",
        lambda *_a, **_k: (1, False, 1, 0.0, "rose", 0.001, 1.0, compare_obj, False, True),
    )
    stamped = []

    def fake_stamp(reqs, **kwargs) -> list[QARequest]:
        stamped.append(kwargs)
        return reqs

    monkeypatch.setattr(flow_mod, "stamp_mri_batch_options", fake_stamp)
    start = MagicMock()
    monkeypatch.setattr(flow_mod, "_start_acr_mri_series_batch_worker", start)

    open_acr_mri_batch_analysis(app)

    start.assert_called_once()
    # stamp kwargs carry no compare field.
    assert "compare_request" not in stamped[0]
    # The compare object was passed by the options dialog but never reaches the worker.
    args = start.call_args.args
    assert args[1] == requests  # stamped == requests (identity preserved by fake_stamp)


def test_flow_bails_when_selection_cancelled(monkeypatch) -> None:
    """Returns cleanly when the selection dialog is cancelled."""
    app = _make_app()
    monkeypatch.setattr(
        flow_mod,
        "prompt_mri_batch_series_selection",
        lambda *_a, **_k: None,
    )
    start = MagicMock()
    monkeypatch.setattr(flow_mod, "_start_acr_mri_series_batch_worker", start)

    open_acr_mri_batch_analysis(app)

    start.assert_not_called()


def test_flow_bails_when_options_cancelled(monkeypatch) -> None:
    """Returns cleanly when the MRI options dialog is cancelled."""
    app = _make_app()
    requests = _make_requests(1)
    labels = ["Series 0"]
    monkeypatch.setattr(
        flow_mod,
        "prompt_mri_batch_series_selection",
        lambda *_a, **_k: (requests, labels),
    )
    monkeypatch.setattr(
        flow_mod,
        "prompt_acr_mri_options",
        lambda *_a, **_k: None,
    )
    start = MagicMock()
    monkeypatch.setattr(flow_mod, "_start_acr_mri_series_batch_worker", start)

    open_acr_mri_batch_analysis(app)

    start.assert_not_called()


def test_worker_progress_and_cancel_wire_cancel(qapp, monkeypatch) -> None:
    """Progress dialog wires Cancel → worker.cancel(); series drives N-of-M."""
    app = _make_app()
    requests = _make_requests(3)
    labels = ["S0", "S1", "S2"]
    progress = _Progress()
    worker = _Worker(requests, labels)

    monkeypatch.setattr(flow_mod, "QProgressDialog", lambda *a: progress)
    monkeypatch.setattr(flow_mod, "QAMRIBatchWorker", lambda *a, **kw: worker)
    monkeypatch.setattr(flow_mod, "_show_acr_mri_batch_summary", MagicMock())

    _start_acr_mri_series_batch_worker(app, requests, labels)

    assert worker.started
    assert app._qa_mri_batch_worker is worker

    # Simulate one series completing.
    result = QAResult(success=True, analysis_type="acr_mri_large")
    worker.series_completed.emit(1, 3, result)
    assert progress._value == 1
    assert "1 of 3" in progress._label

    # Simulate cancel.
    progress.canceled.emit()
    assert worker.cancelled
    assert app.main_window.update_status.call_args_list[-1][0][0].startswith(
        "ACR MRI batch analysis cancelled"
    )


def test_empty_batch_cleans_temps_immediately(qapp, monkeypatch) -> None:
    """An empty batch (all cancelled before any series) cleans up temps now."""
    app = _make_app()
    progress = _Progress()
    worker = _Worker([], [])
    monkeypatch.setattr(flow_mod, "QProgressDialog", lambda *a: progress)
    monkeypatch.setattr(flow_mod, "QAMRIBatchWorker", lambda *a, **kw: worker)
    # Let the real summary function run; mock only the dialog builder.
    monkeypatch.setattr(
        flow_mod, "_create_mri_batch_result_dialog", lambda *a, **k: MagicMock()
    )

    _start_acr_mri_series_batch_worker(app, [], [])
    # Emit an empty batch (no series ran).
    worker.batch_result_ready.emit(ACRMBatchResult())

    # Empty batch → worker.image_temp_dir.cleanup() called immediately.
    assert worker.image_temp_dir.cleanup.called
    assert worker.module_images_temp_dir.cleanup.called


def test_dialog_actions_entry_calls_flow() -> None:
    """dialog_actions.open_acr_mri_batch_analysis delegates to the flow module."""
    import gui.qa_mri_batch_flow as real_flow
    from gui.actions import dialog_actions

    app = _make_app()
    with patch.object(real_flow, "open_acr_mri_batch_analysis") as mocked:
        dialog_actions.open_acr_mri_batch_analysis(app)
        mocked.assert_called_once_with(app)
