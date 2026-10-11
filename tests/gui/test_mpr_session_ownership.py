"""Live MPR registry ownership: configured caps, build admission, activation.

Synthetic results and fake panes only (``mpr_lifecycle_harness``). A
reservation is taken before volume construction and released exactly once;
activation confirms it only on success; older and displaced views survive a
new build; a failed activation rolls back atomically. Transfers and closure
live in ``test_mpr_session_transfers``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
from mpr_lifecycle_harness import (
    _add_detached_view,
    _build_flow,
    _counts,
    _fail,
    _finish,
    _light_display,
    _make_controller,
    _make_result,
    _request,
    _result_for,
    _seed_mpr_pane,
    _signals,
)

from core.mpr_session_types import DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP
from gui.mpr_controller import MprController

_BOX = "gui.mpr_controller_sessions.QMessageBox"


class TestConfiguredCaps:
    def test_registry_uses_config_caps(self) -> None:
        ctrl, app = _make_controller()
        # A stubbed (MagicMock) config is not a valid pair: compiled defaults.
        assert (ctrl._registry.session_cap, ctrl._registry.view_cap) == (
            DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP,
        )
        app.config_manager.get_mpr_caps.return_value = (2, 5)
        configured = MprController(app)._registry
        assert (configured.session_cap, configured.view_cap) == (2, 5)

    def test_invalid_config_caps_fall_back_to_defaults(self) -> None:
        for bad in ((0, 4), (5, 3), (True, 9), ("2", 4), None):
            app = _make_controller()[1]
            app.config_manager.get_mpr_caps.return_value = bad
            reg = MprController(app)._registry
            assert (reg.session_cap, reg.view_cap) == (DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP)


class TestBuildAdmission:
    def test_reservation_is_held_before_volume_construction(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        seen: list[tuple[int, int, int, int]] = []

        with _build_flow(ctrl, result) as (volume, _workers):
            volume.side_effect = lambda *_a, **_k: (seen.append(_counts(ctrl)), result.source_volume)[1]
            ctrl._on_mpr_requested(0, _request(result))

        assert seen == [(0, 0, 1, 1)]
        assert _counts(ctrl) == (0, 0, 1, 1)  # still pending while the worker runs

    def test_at_cap_refuses_before_any_volume_or_cache_work(self) -> None:
        ctrl, _app = _make_controller()
        ctrl._registry.set_caps(1, 4)
        _seed_mpr_pane(_app, 1, _make_result())
        cache = MagicMock()
        ctrl._cache = cache
        result = _result_for("ST", "SE")

        with _build_flow(ctrl, result) as (volume, workers), patch(_BOX) as box:
            ctrl._on_mpr_requested(0, _request(result))

        volume.assert_not_called()
        cache.load.assert_not_called()
        assert workers == [] and 0 not in ctrl._workers
        text = box.warning.call_args.args[2]
        assert "session limit" in text and "1/1" in text
        assert _counts(ctrl) == (1, 1, 0, 0)

    def test_pending_reservations_count_toward_the_cap(self) -> None:
        ctrl, _app = _make_controller()
        ctrl._registry.set_caps(1, 4)
        first, second = _result_for("ST", "SE"), _result_for("ST", "SE")
        with _build_flow(ctrl, first) as (_v, workers), patch(_BOX) as box:
            ctrl._on_mpr_requested(0, _request(first))
            ctrl._on_mpr_requested(1, _request(second))
        assert len(workers) == 1 and 1 not in ctrl._workers
        assert _counts(ctrl) == (0, 0, 1, 1)
        assert "session limit" in box.warning.call_args.args[2]

    def test_view_cap_is_reported_when_it_is_the_limit(self) -> None:
        ctrl, app = _make_controller()
        ctrl._registry.set_caps(2, 2)
        _add_detached_view(ctrl, _make_result())
        ctrl._registry.create_view(1)  # duplicate view: uses a view slot only
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result), patch(_BOX) as box:
            ctrl._on_mpr_requested(0, _request(result))
        assert "view limit" in box.warning.call_args.args[2]

    def test_cancel_releases_the_reservation_once(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers):
            ctrl._on_mpr_requested(0, _request(result))
            ctrl._cancel_mpr_worker(0)
            ctrl._cancel_mpr_worker(0)
        assert _counts(ctrl) == (0, 0, 0, 0)
        assert workers[0].cancel_calls == 1

    def test_error_and_cancelled_callbacks_release(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers), patch("gui.mpr_controller.QMessageBox"):
            ctrl._on_mpr_requested(0, _request(result))
            _fail(workers[0], "boom")
            assert _counts(ctrl) == (0, 0, 0, 0)
            ctrl._on_mpr_requested(0, _request(result))
            _fail(workers[1], "Build cancelled")
        assert _counts(ctrl) == (0, 0, 0, 0)

    def test_stale_callback_does_not_release_a_newer_reservation(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers):
            ctrl._on_mpr_requested(0, _request(result))
            ctrl._on_mpr_requested(0, _request(result))  # replaces: old retired, new reserved
            assert _counts(ctrl) == (0, 0, 1, 1)
            with patch.object(ctrl, "_activate_mpr") as activate:
                _finish(workers[0], result)  # stale
            activate.assert_not_called()
        assert _counts(ctrl) == (0, 0, 1, 1)

    def test_volume_build_failure_releases(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (volume, workers):
            volume.return_value = None
            ctrl._on_mpr_requested(0, _request(result))
        assert workers == [] and _counts(ctrl) == (0, 0, 0, 0)

    def test_unexpected_exception_after_reservation_releases(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (volume, _workers):
            volume.side_effect = RuntimeError("alloc")
            try:
                ctrl._on_mpr_requested(0, _request(result))
            except RuntimeError:
                pass
        assert _counts(ctrl) == (0, 0, 0, 0)

    def test_finished_build_confirms_one_session_and_view(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers), _light_display(ctrl):
            ctrl._on_mpr_requested(0, _request(result))
            _finish(workers[0], result)
        assert _counts(ctrl) == (1, 1, 0, 0)
        view_id = ctrl.attached_view_id(0)
        assert view_id is not None
        session = ctrl._registry.get_session(ctrl._registry.get_view(view_id).session_id)
        assert session.result is result  # owned, not copied
        assert app.subwindow_data[0]["mpr_result"] is result
        assert (session.source_study_uid, session.source_series_uid) == ("ST", "SE")
        assert fired == {"activated": [0], "cleared": [], "detached": []}

    def test_cache_hit_goes_through_admission_and_confirms(self) -> None:
        ctrl, app = _make_controller()
        result = _result_for("ST", "SE")
        slices = [np.zeros((4, 4), dtype=np.float32)] * 3
        cache = MagicMock()
        cache.load.return_value = (
            slices, result.slice_stack,
            {"output_spacing_mm": [0.5, 0.5], "output_thickness_mm": 1.0, "interpolation": "linear"},
        )
        ctrl._cache = cache
        with _build_flow(ctrl, result) as (_v, workers), _light_display(ctrl):
            ctrl._on_mpr_requested(0, _request(result))
        assert workers == []  # cache hit starts no worker
        assert _counts(ctrl) == (1, 1, 0, 0)
        assert ctrl.attached_view_id(0) is not None

    def test_cache_hit_at_cap_is_refused_without_loading(self) -> None:
        ctrl, _app = _make_controller()
        ctrl._registry.set_caps(1, 1)
        _add_detached_view(ctrl, _make_result())
        cache = MagicMock()
        ctrl._cache = cache
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result), patch(_BOX):
            ctrl._on_mpr_requested(0, _request(result))
        cache.load.assert_not_called()
        assert _counts(ctrl) == (1, 1, 0, 0)

    def test_direct_activation_without_reservation_still_obeys_the_cap(self) -> None:
        ctrl, app = _make_controller()
        ctrl._registry.set_caps(1, 1)
        _add_detached_view(ctrl, _make_result())
        with _light_display(ctrl), patch(_BOX):
            ctrl._activate_mpr(0, _make_result(), "Axial")
        assert ctrl.attached_view_id(0) is None
        assert app.subwindow_data[0] == {}
        assert _counts(ctrl) == (1, 1, 0, 0)

    def test_worker_finish_without_viewer_releases(self) -> None:
        ctrl, app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers), patch("gui.mpr_controller.QMessageBox"):
            ctrl._on_mpr_requested(0, _request(result))
            app.multi_window_layout.get_subwindow = lambda _i: None
            _finish(workers[0], result)
        assert _counts(ctrl) == (0, 0, 0, 0)


class TestActivationPreservesViews:
    def test_new_build_keeps_detached_views_including_same_source(self) -> None:
        ctrl, _app = _make_controller()
        older = _add_detached_view(ctrl, _result_for("ST", "SE"))
        newer = _add_detached_view(ctrl, _result_for("ST", "SE"))
        with _light_display(ctrl):
            ctrl._activate_mpr(0, _result_for("ST", "SE"), "Axial")
        assert ctrl.detached_view_ids() == [older, newer]
        attached = ctrl.attached_view_id(0)
        assert attached is not None and attached not in (older, newer)
        # Three independent same-source sessions; none shares a result.
        assert len(ctrl._registry.sessions_for_series("SE")) == 3
        assert _counts(ctrl) == (3, 3, 0, 0)

    def test_build_over_occupied_pane_preserves_displaced_view_as_detached(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        old_result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, old_result)
        old_view = ctrl.attached_view_id(0)
        assert old_view is not None
        # Live pane edits since activation must reach the displaced view.
        app.subwindow_data[0]["mpr_slice_index"] = 3
        app.subwindow_managers[0]["view_state_manager"].current_window_center = 99.0
        new_result = _result_for("ST2", "SE2")

        with _light_display(ctrl):
            ctrl._activate_mpr(0, new_result, "Coronal")

        assert ctrl.detached_view_ids() == [old_view]
        assert ctrl.get_view_metadata(old_view).slice_index == 3
        assert ctrl.get_view_display_state(old_view).window_center == 99.0
        assert app.subwindow_data[0]["mpr_result"] is new_result
        assert ctrl.attached_view_id(0) not in (None, old_view)
        assert _counts(ctrl) == (2, 2, 0, 0)
        assert fired["detached"] == [0] and fired["activated"] == [0]

    def test_failed_replacement_restores_pane_and_registry(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        old_result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, old_result)
        old_view = ctrl.attached_view_id(0)
        before = dict(app.subwindow_data[0])
        with (
            patch.object(ctrl, "display_mpr_slice", side_effect=RuntimeError("render")),
            patch.object(ctrl, "_set_tools_enabled"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch(_BOX) as box,
        ):
            ctrl._activate_mpr(0, _make_result(), "Coronal")
        assert app.subwindow_data[0] == before
        assert ctrl.attached_view_id(0) == old_view
        assert ctrl.detached_view_ids() == []
        assert _counts(ctrl) == (1, 1, 0, 0)
        assert fired == {"activated": [], "cleared": [], "detached": []}
        box.warning.assert_called_once()

    def test_failed_build_activation_releases_its_reservation(self) -> None:
        ctrl, app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers):
            ctrl._on_mpr_requested(0, _request(result))
            with (
                patch.object(ctrl, "display_mpr_slice", side_effect=RuntimeError("render")),
                patch.object(ctrl, "_set_tools_enabled"),
                patch.object(ctrl, "_reset_window_level_for_mpr"),
                patch(_BOX),
            ):
                _finish(workers[0], result)
        assert _counts(ctrl) == (0, 0, 0, 0)
        assert app.subwindow_data[0].get("is_mpr") is None
