"""MPR activation/install preconditions and the render-success contract.

A session may be confirmed only for a real pane with a viewer, a usable result,
a resolved source matching the held reservation, and a first slice that
actually rendered. Every rejection happens before reserve/snapshot/mutation
(direct activation) or releases the pending reservation (build/cache paths),
and never leaves a ghost view in the registry.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from mpr_lifecycle_harness import (
    _add_detached_view,
    _build_flow,
    _counts,
    _finish,
    _light_display,
    _make_controller,
    _make_result,
    _request,
    _result_for,
    _seed_mpr_pane,
    _signals,
)

_BOX = "gui.mpr_controller_sessions.QMessageBox"
_NO_SIGNALS = {"activated": [], "cleared": [], "detached": []}


def _empty_result() -> object:
    result = _make_result()
    result.slices = []
    return result


def _datasetless_result() -> object:
    result = _make_result()
    result.source_volume = SimpleNamespace(source_datasets=[])
    return result


def _remove_viewer(app, idx: int) -> None:
    original = app.multi_window_layout.get_subwindow
    app.multi_window_layout.get_subwindow = lambda i: None if i == idx else original(i)


class TestDirectActivationRejections:
    @pytest.mark.parametrize("make", [_empty_result, _datasetless_result], ids=["no-slices", "no-datasets"])
    def test_unusable_result_is_rejected_before_any_reservation(self, make) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        before = dict(app.subwindow_data[0])
        with patch.object(ctrl._registry, "reserve_build") as reserve, patch(_BOX) as box:
            ctrl._activate_mpr(0, make(), "Axial")
        reserve.assert_not_called()
        assert _counts(ctrl) == (0, 0, 0, 0)
        assert app.subwindow_data[0] == before
        assert fired == _NO_SIGNALS
        box.warning.assert_called_once()

    def test_missing_viewer_is_rejected_before_any_reservation(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _remove_viewer(app, 0)
        with patch.object(ctrl._registry, "reserve_build") as reserve, patch(_BOX):
            ctrl._activate_mpr(0, _make_result(), "Axial")
        reserve.assert_not_called()
        assert _counts(ctrl) == (0, 0, 0, 0) and app.subwindow_data[0] == {}
        assert fired == _NO_SIGNALS

    def test_missing_pane_data_is_rejected(self) -> None:
        ctrl, app = _make_controller()
        with patch(_BOX):
            ctrl._activate_mpr(7, _make_result(), "Axial")
        assert _counts(ctrl) == (0, 0, 0, 0) and 7 not in app.subwindow_data

    def test_rejection_leaves_an_occupied_pane_and_its_view_alone(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        resident = ctrl.attached_view_id(0)
        before = dict(app.subwindow_data[0])
        with patch(_BOX):
            ctrl._activate_mpr(0, _empty_result(), "Axial")
        assert ctrl.attached_view_id(0) == resident and ctrl.detached_view_ids() == []
        assert app.subwindow_data[0] == before


class TestPendingBuildRejections:
    @pytest.mark.parametrize("make", [_empty_result, _datasetless_result], ids=["no-slices", "no-datasets"])
    def test_unusable_finished_result_releases_the_reservation(self, make) -> None:
        ctrl, app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers), patch(_BOX):
            ctrl._on_mpr_requested(0, _request(result))
            assert _counts(ctrl) == (0, 0, 1, 1)
            _finish(workers[0], make())
        assert _counts(ctrl) == (0, 0, 0, 0) and ctrl._build_reservations == {}
        assert app.subwindow_data[0] == {}

    def test_viewer_lost_before_activation_releases_the_reservation(self) -> None:
        ctrl, app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers), patch(_BOX):
            ctrl._on_mpr_requested(0, _request(result))
            _remove_viewer(app, 0)
            ctrl._activate_mpr(0, result, "Axial")  # e.g. a cache hit racing a layout change
        assert _counts(ctrl) == (0, 0, 0, 0)
        del workers

    def test_resolved_source_must_match_the_reserved_source(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        reserved = _result_for("ST", "SE")
        other_series = _result_for("ST", "SE-OTHER")
        with _build_flow(ctrl, reserved) as (_v, workers), patch(_BOX) as box:
            ctrl._on_mpr_requested(0, _request(reserved))
            _finish(workers[0], other_series)
        assert _counts(ctrl) == (0, 0, 0, 0)
        assert app.subwindow_data[0] == {}
        assert fired == _NO_SIGNALS
        assert "does not match" in box.warning.call_args.args[2]

    def test_session_source_is_the_reserved_and_resolved_source(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers), _light_display(ctrl):
            ctrl._on_mpr_requested(0, _request(result))
            _finish(workers[0], result)
        view = ctrl._registry.get_view(ctrl.attached_view_id(0))
        session = ctrl._registry.get_session(view.session_id)
        assert (session.source_study_uid, session.source_series_uid) == ("ST", "SE")


class TestRenderContract:
    def test_display_mpr_slice_reports_whether_it_rendered(self) -> None:
        ctrl, app = _make_controller()
        assert ctrl.display_mpr_slice(0, 0) is False  # not an MPR pane
        _seed_mpr_pane(app, 0, _make_result(n_slices=3))
        assert ctrl.display_mpr_slice(0, 1) is True
        assert ctrl.display_mpr_slice(0, 9) is False  # beyond the stack
        assert ctrl.display_mpr_slice(0, -1) is False  # before the stack
        with patch.object(ctrl, "_array_to_pil", return_value=None):
            assert ctrl.display_mpr_slice(0, 1) is False  # image could not be built
        _remove_viewer(app, 0)
        assert ctrl.display_mpr_slice(0, 1) is False

    def test_unrenderable_first_slice_confirms_no_ghost_view(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        app.subwindow_data[0] = {"current_dataset": "ordinary", "current_slice_index": 2}
        before = dict(app.subwindow_data[0])
        result = _result_for("ST", "SE")
        with (
            _build_flow(ctrl, result) as (_v, workers),
            patch.object(ctrl, "_array_to_pil", return_value=None),
            patch.object(ctrl, "_set_tools_enabled"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch(_BOX) as box,
        ):
            ctrl._on_mpr_requested(0, _request(result))
            _finish(workers[0], result)
        assert _counts(ctrl) == (0, 0, 0, 0)
        assert ctrl.attached_view_id(0) is None
        assert app.subwindow_data[0] == before
        assert fired == _NO_SIGNALS
        box.warning.assert_called_once()

    def test_unrenderable_replacement_keeps_the_resident_view(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        resident = ctrl.attached_view_id(0)
        before = dict(app.subwindow_data[0])
        with (
            patch.object(ctrl, "_array_to_pil", return_value=None),
            patch.object(ctrl, "_set_tools_enabled"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch(_BOX),
        ):
            ctrl._activate_mpr(0, _make_result(), "Coronal")
        assert ctrl.attached_view_id(0) == resident and ctrl.detached_view_ids() == []
        assert _counts(ctrl) == (1, 1, 0, 0)
        assert app.subwindow_data[0] == before

    def test_install_over_unrenderable_target_rolls_back_relocate_and_attach(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        mover, resident = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        floating = _add_detached_view(ctrl, _make_result())
        with (
            patch.object(ctrl, "display_mpr_slice", return_value=False),
            patch.object(ctrl, "_set_tools_enabled"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch("gui.mpr_controller.QMessageBox"),
            patch("gui.mpr_controller_transactions.QMessageBox"),
        ):
            ctrl.relocate_mpr_subwindow(0, 1)
            ctrl.attach_detached_view(floating, 1)
        assert (ctrl.attached_view_id(0), ctrl.attached_view_id(1)) == (mover, resident)
        assert ctrl.detached_view_ids() == [floating]
        assert fired == _NO_SIGNALS


class TestConfirmFailure:
    def test_confirm_failure_restores_pane_and_preserves_registry(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        resident = ctrl.attached_view_id(0)
        floating = _add_detached_view(ctrl, _make_result())
        before = dict(app.subwindow_data[0])
        result = _result_for("ST", "SE")
        with (
            _build_flow(ctrl, result) as (_v, workers),
            _light_display(ctrl),
            patch.object(ctrl._registry, "confirm_build", side_effect=ValueError("malformed")),
            patch(_BOX),
        ):
            ctrl._on_mpr_requested(0, _request(result))
            assert _counts(ctrl) == (2, 2, 1, 1)
            _finish(workers[0], result)
        assert _counts(ctrl) == (2, 2, 0, 0)  # reservation released, nothing created
        assert ctrl.attached_view_id(0) == resident and ctrl.detached_view_ids() == [floating]
        assert app.subwindow_data[0] == before
        assert fired == _NO_SIGNALS


class TestPreInstallFailure:
    """A failure between the reservation pop and the first pane write.

    The pane state flush and destination snapshot run inside the failure
    bracket: a raise there must release the admission slot exactly once and
    never leak a pending session/view token into the registry.
    """

    def test_snapshot_capture_failure_releases_the_reservation_and_leaves_the_pane(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        before = dict(app.subwindow_data[0])
        result = _result_for("ST", "SE")
        with (
            _build_flow(ctrl, result) as (_v, workers),
            patch("gui.mpr_activation.capture_destination_snapshot", side_effect=RuntimeError("deleted")),
            patch(_BOX) as box,
        ):
            ctrl._on_mpr_requested(0, _request(result))
            _finish(workers[0], result)
        assert _counts(ctrl) == (0, 0, 0, 0)  # no leaked session, view, or pending slot
        assert ctrl._build_reservations == {}
        assert app.subwindow_data[0] == before
        assert fired == _NO_SIGNALS
        box.warning.assert_called_once()

    def test_snapshot_capture_failure_on_replacement_keeps_the_resident_view(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        resident = ctrl.attached_view_id(0)
        before = dict(app.subwindow_data[0])
        with (
            patch("gui.mpr_activation.capture_destination_snapshot", side_effect=RuntimeError("deleted")),
            patch(_BOX) as box,
        ):
            ctrl._activate_mpr(0, _result_for("ST", "SE"), "Axial")
        assert ctrl.attached_view_id(0) == resident and ctrl.detached_view_ids() == []
        assert _counts(ctrl) == (1, 1, 0, 0)  # the resident session, no leaked token
        assert app.subwindow_data[0] == before
        box.warning.assert_called_once()

    def test_state_flush_failure_also_releases_the_reservation(self) -> None:
        ctrl, app = _make_controller()
        result = _result_for("ST", "SE")
        with (
            _build_flow(ctrl, result) as (_v, workers),
            patch("gui.mpr_activation.refresh_view_from_pane", side_effect=RuntimeError("deleted")),
            patch(_BOX),
        ):
            ctrl._on_mpr_requested(0, _request(result))
            _finish(workers[0], result)
        assert _counts(ctrl) == (0, 0, 0, 0)
        assert ctrl._build_reservations == {}
        assert app.subwindow_data[0] == {}
