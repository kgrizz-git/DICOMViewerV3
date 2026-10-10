"""Live MPR registry: clearing one view; closure releases everything.

Source closure and close-all release sessions, views and reservations; a
per-view clear discards only that view; release is idempotent. Transfer
(detach/move/reattach) coverage arrives with the parking slice.
"""

from __future__ import annotations

from unittest.mock import patch

from mpr_lifecycle_harness import (
    FakeWorker,
    _add_detached_view,
    _build_flow,
    _counts,
    _finish,
    _make_controller,
    _make_result,
    _register_worker,
    _request,
    _result_for,
    _seed_mpr_pane,
    _signals,
)


def _view_exists(ctrl, view_id: int) -> bool:
    try:
        ctrl._registry.get_view(view_id)
        return True
    except Exception:
        return False


class TestClearOneView:
    def test_clear_mpr_discards_only_that_view(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        keeper = ctrl.attached_view_id(1)
        floating = _add_detached_view(ctrl, _make_result())
        ctrl.clear_mpr(0)
        assert ctrl.attached_view_id(0) is None
        assert ctrl.attached_view_id(1) == keeper
        assert ctrl.detached_view_ids() == [floating]
        assert _counts(ctrl) == (2, 2, 0, 0)
        assert fired["cleared"] == [0]


class TestSourceClosureAndCloseAll:
    def test_close_source_discards_all_its_sessions_and_keeps_foreign_ones(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result(), study="ST")  # pane displays ST/SE
        detached_a = _add_detached_view(ctrl, _make_result(), "ST", "SE")  # same-source session
        detached_b = _add_detached_view(ctrl, _make_result(), "ST", "SE")  # another independent one
        foreign = _add_detached_view(ctrl, _make_result(), "ST", "OTHER-SE")
        other_study = _add_detached_view(ctrl, _make_result(), "OTHER-ST", "SE")

        released = ctrl.release_mpr_for_closed_source("ST", "SE")

        assert released["detached"] == 2
        assert ctrl.attached_view_id(0) is None
        assert ctrl.detached_view_ids() == [foreign, other_study]
        assert ctrl._registry.session_count == 2
        assert not _view_exists(ctrl, detached_a)
        assert not _view_exists(ctrl, detached_b)

    def test_close_study_discards_every_series_of_it(self) -> None:
        ctrl, _app = _make_controller()
        _add_detached_view(ctrl, _make_result(), "ST", "SE-1")
        _add_detached_view(ctrl, _make_result(), "ST", "SE-2")
        keeper = _add_detached_view(ctrl, _make_result(), "OTHER", "SE-1")
        ctrl.release_mpr_for_closed_source("ST")
        assert ctrl.detached_view_ids() == [keeper]

    def test_close_source_releases_pending_reservation_and_fences_late_finish(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers):
            ctrl._on_mpr_requested(0, _request(result))
            assert _counts(ctrl) == (0, 0, 1, 1)
            ctrl.release_mpr_for_closed_source("ST", "SE")
            assert _counts(ctrl) == (0, 0, 0, 0)
            with patch.object(ctrl, "_activate_mpr") as activate:
                _finish(workers[0], result)
            activate.assert_not_called()

    def test_foreign_pending_build_survives_closure_of_another_source(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result):
            ctrl._on_mpr_requested(0, _request(result))
            ctrl.release_mpr_for_closed_source("ST", "SOMETHING-ELSE")
        assert _counts(ctrl) == (0, 0, 1, 1)

    def test_close_all_releases_every_session_view_and_reservation(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        floating = _add_detached_view(ctrl, _make_result())
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers):
            ctrl._on_mpr_requested(1, _request(result))
            released = ctrl.release_all_mpr()
            with patch.object(ctrl, "_activate_mpr") as activate:
                _finish(workers[0], result)
            activate.assert_not_called()
        assert _counts(ctrl) == (0, 0, 0, 0)
        assert ctrl._build_reservations == {}
        assert released["detached"] == 1 and released["workers"] == 1
        assert not _view_exists(ctrl, floating)

    def test_release_is_idempotent(self) -> None:
        ctrl, _app = _make_controller()
        _add_detached_view(ctrl, _make_result(), "ST", "SE")
        ctrl.release_mpr_for_closed_source("ST", "SE")
        again = ctrl.release_mpr_for_closed_source("ST", "SE")
        assert again["detached"] == 0 and _counts(ctrl) == (0, 0, 0, 0)

    def test_pane_registered_worker_is_still_tracked_for_registered_fake(self) -> None:
        ctrl, _app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 1, worker)
        ctrl.release_all_mpr()
        assert worker.cancel_calls == 1 and 1 not in ctrl._workers
