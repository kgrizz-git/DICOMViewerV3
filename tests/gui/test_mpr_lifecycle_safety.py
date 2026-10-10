"""Worker fencing tests for chunk 3.

Late build callbacks after replacement/cancellation/closure, worker
retirement until true native termination (real QThread), progress-cancel
routing, and build-source close matching.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mpr_lifecycle_harness import (
    FakeWorker,
    _add_detached_view,
    _make_controller,
    _make_result,
    _register_worker,
    _seed_mpr_pane,
    _source_dataset,
)
from PySide6.QtCore import QThread, Signal

from core.lut_catalog import sigmoid_lut


class TestLateBuildCallbacks:
    def test_late_finished_after_replacement_is_dropped(self) -> None:
        ctrl, app = _make_controller()
        old, new = FakeWorker(), FakeWorker()
        _register_worker(ctrl, 0, old)
        from gui.mpr_worker_fencing import bump_pane_generation

        bump_pane_generation(ctrl, 0)
        _register_worker(ctrl, 0, new)
        dlg = MagicMock()
        with patch.object(ctrl, "_activate_mpr") as activate:
            ctrl._on_mpr_build_finished(
                0, old, 0, ("ST", "SE"), 0, _make_result(), MagicMock(),
                "Axial", dlg,
            )
        assert ctrl._workers[0] is new
        activate.assert_not_called()
        dlg.close.assert_called_once_with()

    def test_late_error_after_cancel_is_dropped(self) -> None:
        ctrl, _app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 0, worker)
        ctrl._cancel_mpr_worker(0)
        dlg = MagicMock()
        with patch("gui.mpr_controller.QMessageBox") as box:
            ctrl._on_mpr_build_error(0, worker, 0, ("ST", "SE"), 0, "boom", dlg)
        box.critical.assert_not_called()
        assert 0 not in ctrl._workers

    def test_matching_finished_activates_and_pops(self) -> None:
        ctrl, _app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 0, worker)
        dlg = MagicMock()
        with patch.object(ctrl, "_activate_mpr") as activate:
            ctrl._on_mpr_build_finished(
                0, worker, 0, ("ST", "SE"), 0, _make_result(), MagicMock(),
                "Axial", dlg,
            )
        activate.assert_called_once()
        assert 0 not in ctrl._workers

    def test_stale_callback_after_source_close_is_dropped(self) -> None:
        ctrl, app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 0, worker)
        app.subwindow_data[0] = {"current_study_uid": "ST", "current_series_uid": "SE"}
        ctrl.release_mpr_for_closed_source("ST", "SE")
        dlg = MagicMock()
        with patch.object(ctrl, "_activate_mpr") as activate:
            ctrl._on_mpr_build_finished(
                0, worker, 0, ("ST", "SE"), 0, _make_result(), MagicMock(),
                "Axial", dlg,
            )
        activate.assert_not_called()


class TestWorkerRetirement:
    def test_retire_keeps_worker_until_termination(self) -> None:
        ctrl, _app = _make_controller()
        worker = FakeWorker(finished=False)
        _register_worker(ctrl, 0, worker)
        assert ctrl._cancel_mpr_worker(0) is None
        assert worker.cancel_calls == 1 and worker.quit_calls == 1
        assert 0 not in ctrl._workers
        assert worker in ctrl._retiring_builds
        worker.terminate_thread()
        assert worker not in ctrl._retiring_builds

    def test_retire_finished_worker_does_not_retain(self) -> None:
        ctrl, _app = _make_controller()
        worker = FakeWorker(finished=True)
        _register_worker(ctrl, 0, worker)
        ctrl._cancel_mpr_worker(0)
        assert worker not in ctrl._retiring_builds

    def test_retire_without_worker_is_safe(self) -> None:
        ctrl, _app = _make_controller()
        ctrl._cancel_mpr_worker(3)
        assert ctrl._build_generations[3] == 1

    def test_relocate_cancels_destination_build(self) -> None:
        ctrl, app = _make_controller()
        result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, result)
        dest_worker = FakeWorker()
        _register_worker(ctrl, 1, dest_worker)
        app.subwindow_data[1] = {"current_datasets": []}
        with (
            patch.object(ctrl, "display_mpr_slice"),
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            ctrl.relocate_mpr_subwindow(0, 1)
        assert dest_worker.cancel_calls == 1
        assert app.subwindow_data[1].get("is_mpr") is True


class ProbeWorker(QThread):
    """Real QThread that stays alive until the test releases it.

    ``run`` signals ``started_evt``, optionally emits the custom payload
    signal (which fires BEFORE the native thread returns, like a real build),
    then blocks on ``release_evt``. ``cancel`` only records the request: a
    native build may keep running after being asked to stop, which is exactly
    the retire-while-alive case under test. Nothing here depends on timing;
    the wait is bounded only so a broken test cannot hang the suite.
    """

    done = Signal(object)
    SAFETY_TIMEOUT_S = 30.0

    def __init__(self, *, emit_result: bool = False):
        super().__init__()
        self.started_evt = threading.Event()
        self.release_evt = threading.Event()
        self._emit_result = emit_result
        self.cancel_calls = 0

    def cancel(self) -> None:
        self.cancel_calls += 1

    def run(self) -> None:
        self.started_evt.set()
        if self._emit_result:
            self.done.emit({"ok": True})
        self.release_evt.wait(self.SAFETY_TIMEOUT_S)

    def start_and_wait_running(self) -> None:
        self.start()
        assert self.started_evt.wait(10), "worker thread never started"

    def release_and_join(self) -> bool:
        self.release_evt.set()
        return self.wait(10000)


class TestTrueTermination:
    def test_retired_live_thread_retained_until_stopped(self) -> None:
        from gui.mpr_worker_fencing import sweep_retired_builds, truly_terminated

        ctrl, _app = _make_controller()
        worker = ProbeWorker()
        try:
            worker.start_and_wait_running()
            assert worker.isRunning() and not truly_terminated(worker)
            _register_worker(ctrl, 0, worker)
            ctrl._cancel_mpr_worker(0)
            assert worker.cancel_calls == 1
            assert worker in ctrl._retiring_builds
            assert ctrl._retire_poller is not None and ctrl._retire_poller.isActive()
            # A sweep while the native thread is still alive must keep it.
            sweep_retired_builds(ctrl)
            assert worker.isRunning()
            assert worker in ctrl._retiring_builds
        finally:
            assert worker.release_and_join() is True
        sweep_retired_builds(ctrl)
        assert worker not in ctrl._retiring_builds
        assert ctrl._retire_poller is not None and not ctrl._retire_poller.isActive()

    def test_completed_worker_retained_until_join(self) -> None:
        from gui.mpr_worker_fencing import retain_build_worker, sweep_retired_builds

        ctrl, _app = _make_controller()
        # The custom payload signal fires while the native thread is still alive.
        worker = ProbeWorker(emit_result=True)
        try:
            worker.start_and_wait_running()
            retain_build_worker(ctrl, worker)
            assert worker.isRunning()
            assert worker in ctrl._retiring_builds
            sweep_retired_builds(ctrl)
            assert worker in ctrl._retiring_builds
        finally:
            assert worker.release_and_join() is True
        sweep_retired_builds(ctrl)
        assert worker not in ctrl._retiring_builds

    def test_unknown_termination_state_retains(self) -> None:
        from gui.mpr_worker_fencing import retain_build_worker, truly_terminated

        ctrl, _app = _make_controller()
        broken = MagicMock()
        broken.isFinished.side_effect = RuntimeError("unknown")
        assert truly_terminated(broken) is False
        retain_build_worker(ctrl, broken)
        assert broken in ctrl._retiring_builds

    def test_backup_lambda_ignores_result_payload(self) -> None:
        from gui.mpr_worker_fencing import sweep_retired_builds

        ctrl, _app = _make_controller()
        worker = FakeWorker()
        worker.isFinished = MagicMock(return_value=False)
        _register_worker(ctrl, 0, worker)
        ctrl._cancel_mpr_worker(0)
        # Simulate the custom finished(result) firing while native alive.
        (args, _kwargs) = worker.finished.connect.call_args
        args[0]({"ok": True})
        sweep_retired_builds(ctrl)
        assert worker in ctrl._retiring_builds


class TestProgressCancelRouting:
    def _start_fake_build(self, ctrl, app, idx=0):
        from core.mpr_builder import MprBuilder

        request = SimpleNamespace(
            datasets=[_source_dataset()],
            output_plane=MagicMock(),
            output_spacing_mm=1.0,
            output_thickness_mm=1.0,
            interpolation="linear",
            orientation_label="Axial",
            combine_mode="none",
            slab_thickness_mm=0.0,
        )
        worker = FakeWorker()
        worker.progress = MagicMock()
        worker.error = MagicMock()
        dlg = MagicMock()
        volume = SimpleNamespace(source_datasets=[_source_dataset()])
        with (
            patch.object(MprBuilder, "create_worker", return_value=worker),
            patch("gui.mpr_controller.QProgressDialog", return_value=dlg),
        ):
            ctrl._mpr_request_start_worker(idx, request, volume)
        return worker, dlg

    def test_dialog_cancel_retires_build(self) -> None:
        ctrl, app = _make_controller()
        worker, dlg = self._start_fake_build(ctrl, app)
        assert ctrl._workers[0] is worker
        assert ctrl._build_progress[0] is dlg
        (args, _kwargs) = dlg.canceled.connect.call_args
        args[0]()  # user pressed Cancel
        assert worker.cancel_calls == 1
        assert 0 not in ctrl._workers
        dlg.close.assert_called_once_with()
        assert 0 not in ctrl._build_progress

    def test_queued_finish_after_dialog_cancel_is_dropped(self) -> None:
        ctrl, app = _make_controller()
        worker, dlg = self._start_fake_build(ctrl, app)
        (args, _kwargs) = dlg.canceled.connect.call_args
        args[0]()
        with patch.object(ctrl, "_activate_mpr") as activate:
            ctrl._on_mpr_build_finished(
                0, worker, 0, ("ST", "SE"), 0, _make_result(), MagicMock(),
                "Axial", dlg,
            )
        activate.assert_not_called()


class TestBuildSourceCloseMatching:
    def test_close_matches_worker_source_not_display(self) -> None:
        ctrl, app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 0, worker)
        ctrl._build_sources[0] = ("ST-A", "SE-A")
        # Pane displays an unrelated source while building the closed one.
        app.subwindow_data[0] = {"current_study_uid": "ST-B", "current_series_uid": "SE-B"}
        manager = app.subwindow_managers[0]["view_state_manager"]
        manager.series_defaults.setdefault("SE-B", {})["current_lut"] = sigmoid_lut()

        released = ctrl.release_mpr_for_closed_source("ST-A", "SE-A")

        assert released["workers"] == 1
        assert worker.cancel_calls == 1
        assert released["panes"] == 0  # display chrome belongs to ST-B
        assert manager.series_defaults["SE-B"]["current_lut"].name == "Sigmoid"
        app.series_navigator.clear_mpr_thumbnail.assert_not_called()

    def test_foreign_build_survives_close(self) -> None:
        ctrl, app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 0, worker)
        ctrl._build_sources[0] = ("ST-A", "SE-A")
        app.subwindow_data[0] = {"current_study_uid": "ST-A", "current_series_uid": "SE-A"}

        released = ctrl.release_mpr_for_closed_source("ST-A", "SE-OTHER")

        assert released == {"panes": 0, "workers": 0, "detached": 0, "specs": 0}
        assert 0 in ctrl._workers

    def test_split_series_closure(self) -> None:
        ctrl, app = _make_controller()
        worker_a, worker_b = FakeWorker(), FakeWorker()
        _register_worker(ctrl, 0, worker_a)
        _register_worker(ctrl, 1, worker_b)
        ctrl._build_sources[0] = ("ST", "SE-1")
        ctrl._build_sources[1] = ("ST", "SE-2")
        app.subwindow_data[0] = {"current_study_uid": "ST", "current_series_uid": "SE-1"}
        app.subwindow_data[1] = {"current_study_uid": "ST", "current_series_uid": "SE-2"}

        released = ctrl.release_mpr_for_closed_source("ST", "SE-1")

        assert released["workers"] == 1
        assert worker_a.cancel_calls == 1 and worker_b.cancel_calls == 0
        assert 1 in ctrl._workers

    def test_close_all_cancels_everything(self) -> None:
        ctrl, app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 1, worker)
        ctrl._build_sources[1] = ("ST-X", "SE-X")
        app.subwindow_data[1] = {}  # pending on an empty pane
        detached_view = _add_detached_view(ctrl, _make_result(), "ST-Y", "SE-Y")
        ctrl._source_generations[("ST-Y", "SE-Y")] = 3

        released = ctrl.release_all_mpr()

        assert released["workers"] == 1
        assert released["detached"] == 1
        assert worker.cancel_calls == 1
        assert ctrl.detached_view_ids() == []
        assert ctrl._registry.view_count == 0 and ctrl._registry.session_count == 0
        app.series_navigator.clear_mpr_thumbnail.assert_any_call(-detached_view)
        assert ctrl._source_generations[("ST-Y", "SE-Y")] == 4


