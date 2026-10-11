"""Live MPR registry: transfers consume no admission; closure releases everything.

Detach, move and reattach move existing views (zero session/view admission);
a displaced destination view is preserved as detached with its live state;
failures leave the registry and signals untouched; stale IDs are no-ops;
source closure and close-all release sessions, views, tiles and reservations.
"""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
from mpr_lifecycle_harness import (
    FakeWorker,
    _add_detached_view,
    _build_flow,
    _counts,
    _finish,
    _light_display,
    _make_controller,
    _make_result,
    _register_worker,
    _request,
    _result_for,
    _seed_mpr_pane,
    _signals,
)

_BOX = "gui.mpr_controller_sessions.QMessageBox"


class TestTransfersConsumeNoAdmission:
    def test_multiple_detach_keeps_every_view_in_creation_order(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        first, second = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        counts = _counts(ctrl)

        ctrl.detach_mpr_from_subwindow(1)
        ctrl.detach_mpr_from_subwindow(0)

        assert ctrl.detached_view_ids() == [first, second]  # creation order, not detach order
        assert _counts(ctrl) == counts
        assert fired["detached"] == [1, 0]
        assert app.subwindow_data[0].get("is_mpr") is None

    def test_detach_of_empty_or_non_mpr_pane_creates_nothing(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        app.subwindow_data[1] = {"current_dataset": object()}
        ctrl.detach_mpr_from_subwindow(0)
        ctrl.detach_mpr_from_subwindow(1)
        ctrl.detach_mpr_from_subwindow(99)
        assert _counts(ctrl) == (0, 0, 0, 0)
        assert fired["detached"] == []

    def test_detach_flushes_live_pane_state_into_the_view(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result(n_slices=5))
        view_id = ctrl.attached_view_id(0)
        data = app.subwindow_data[0]
        data["mpr_slice_index"] = 4
        data["mpr_combine_enabled"] = True
        data["mpr_combine_mode"] = "mip"
        data["mpr_combine_slice_count"] = 6
        vsm = app.subwindow_managers[0]["view_state_manager"]
        vsm.current_window_width = 123.0
        vsm.use_rescaled_values = False
        app.multi_window_layout.get_subwindow(0).image_viewer.image_inverted = True

        ctrl.detach_mpr_from_subwindow(0)

        view = ctrl._registry.get_view(view_id)
        assert view.slice_index == 4
        assert (view.combine.enabled, view.combine.mode, view.combine.slice_count) == (True, "mip", 6)
        assert (view.display.window_width, view.display.use_rescaled, view.display.inverted) == (
            123.0, False, True,
        )

    def test_reattach_keeps_identity_and_restores_state_selectively(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result(n_slices=5))
        _seed_mpr_pane(app, 1, _make_result(n_slices=5))
        first, second = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        app.subwindow_data[0]["mpr_slice_index"] = 3
        ctrl.detach_mpr_from_subwindow(0)
        ctrl.detach_mpr_from_subwindow(1)
        counts = _counts(ctrl)

        with _light_display(ctrl):
            ctrl.attach_detached_view(second, 1)

        assert ctrl.attached_view_id(1) == second  # identity survives
        assert ctrl.detached_view_ids() == [first]  # the other stays detached
        assert _counts(ctrl) == counts
        assert app.subwindow_data[1]["mpr_result"] is ctrl._registry.get_session(
            ctrl._registry.get_view(second).session_id
        ).result

        with _light_display(ctrl):
            ctrl.attach_detached_view(first, 0)
        assert app.subwindow_data[0]["mpr_slice_index"] == 3
        assert ctrl.detached_view_ids() == []

    def test_moves_work_at_the_caps(self) -> None:
        ctrl, app = _make_controller()
        ctrl._registry.set_caps(2, 2)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        with _light_display(ctrl):
            ctrl.detach_mpr_from_subwindow(0)
            view_id = ctrl.detached_view_ids()[0]
            ctrl.attach_detached_view(view_id, 0)
            ctrl.relocate_mpr_subwindow(0, 1)
        assert _counts(ctrl) == (2, 2, 0, 0)
        assert ctrl.attached_view_id(1) == view_id and len(ctrl.detached_view_ids()) == 1

    def test_relocate_over_occupied_pane_preserves_displaced_view(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        mover, displaced = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        counts = _counts(ctrl)
        # The occupant's live edits must be flushed before the pane is reused.
        app.subwindow_data[1]["mpr_slice_index"] = 2
        app.subwindow_managers[1]["view_state_manager"].current_window_center = 77.0

        with _light_display(ctrl):
            ctrl.relocate_mpr_subwindow(0, 1)

        assert ctrl._registry.get_view(displaced).slice_index == 2
        assert ctrl.get_view_display_state(displaced).window_center == 77.0
        assert ctrl.attached_view_id(1) == mover
        assert ctrl.attached_view_id(0) is None
        assert ctrl.detached_view_ids() == [displaced]
        assert _counts(ctrl) == counts
        assert fired == {"activated": [1], "cleared": [0], "detached": [1]}

    def test_attach_over_occupied_pane_preserves_displaced_view(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 1, _make_result())
        displaced = ctrl.attached_view_id(1)
        floating = _add_detached_view(ctrl, _make_result())
        app.subwindow_data[1]["mpr_slice_index"] = 2
        app.subwindow_managers[1]["view_state_manager"].current_window_center = 77.0

        with _light_display(ctrl):
            ctrl.attach_detached_view(floating, 1)

        assert ctrl._registry.get_view(displaced).slice_index == 2
        assert ctrl.get_view_display_state(displaced).window_center == 77.0
        assert ctrl.attached_view_id(1) == floating
        assert ctrl.detached_view_ids() == [displaced]
        assert fired == {"activated": [1], "cleared": [], "detached": [1]}
        assert ctrl.get_view_metadata(floating) is not None

    def test_failed_relocate_leaves_registry_and_signals_untouched(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        mover, resident = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        with (
            patch.object(ctrl, "display_mpr_slice", side_effect=RuntimeError("render")),
            patch.object(ctrl, "_set_tools_enabled"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch("gui.mpr_controller.QMessageBox"),
        ):
            ctrl.relocate_mpr_subwindow(0, 1)
        assert (ctrl.attached_view_id(0), ctrl.attached_view_id(1)) == (mover, resident)
        assert ctrl.detached_view_ids() == []
        assert fired == {"activated": [], "cleared": [], "detached": []}

    def test_failed_attach_leaves_view_detached_and_destination_intact(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 1, _make_result())
        resident = ctrl.attached_view_id(1)
        floating = _add_detached_view(ctrl, _make_result())
        with (
            patch.object(ctrl, "display_mpr_slice", side_effect=RuntimeError("render")),
            patch.object(ctrl, "_set_tools_enabled"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch("gui.mpr_controller.QMessageBox"),
            patch("gui.mpr_controller_transactions.QMessageBox"),
        ):
            ctrl.attach_detached_view(floating, 1)
        assert ctrl.attached_view_id(1) == resident
        assert ctrl.detached_view_ids() == [floating]
        assert fired == {"activated": [], "cleared": [], "detached": []}

    def test_stale_and_foreign_ids_are_harmless_no_ops(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        attached = ctrl.attached_view_id(0)
        counts = _counts(ctrl)
        with patch(_BOX) as box, patch("gui.mpr_controller_transactions.QMessageBox") as txn_box:
            ctrl.attach_detached_view(999, 1)
            ctrl.attach_detached_view(attached, 1)  # attached, not detached
            ctrl.attach_detached_view(-3, 1)  # type: ignore[arg-type]
            assert ctrl.discard_detached_view(999) is False
            assert ctrl.discard_detached_view(attached) is False  # attached must clear via pane
        assert _counts(ctrl) == counts and ctrl.attached_view_id(0) == attached
        assert fired == {"activated": [], "cleared": [], "detached": []}
        box.warning.assert_not_called()
        txn_box.warning.assert_not_called()

    def test_discard_detached_releases_session_with_last_view_only(self) -> None:
        ctrl, _app = _make_controller()
        solo = _add_detached_view(ctrl, _make_result())
        shared_session, first = ctrl._registry.create_session(_make_result())
        second = ctrl._registry.create_view(shared_session)
        assert ctrl.discard_detached_view(solo) is True
        assert ctrl._registry.session_count == 1
        assert ctrl.discard_detached_view(first) is True
        assert ctrl._registry.session_count == 1  # sibling keeps the session alive
        assert ctrl.discard_detached_view(second) is True
        assert _counts(ctrl) == (0, 0, 0, 0)

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


class TestPublicViewAccess:
    def test_metadata_and_thumbnail_pixels_for_attached_and_detached_views(self) -> None:
        ctrl, app = _make_controller()
        result = _make_result(n_slices=5)
        _seed_mpr_pane(app, 0, result, study="ST")
        view_id = ctrl.attached_view_id(0)
        app.subwindow_data[0]["mpr_slice_index"] = 2

        meta = ctrl.get_view_metadata(view_id)
        assert (meta.view_id, meta.pane_index, meta.slice_index, meta.n_slices) == (view_id, 0, 2, 5)
        assert (meta.source_study_uid, meta.source_series_uid, meta.orientation) == ("ST", "SE", "Axial")
        assert ctrl.get_pane_view_metadata(0) == meta
        mid = ctrl.get_view_thumbnail_pixels(view_id, use_rescaled=False)
        assert mid is not None and float(mid[0, 0]) == 2.0  # n_slices // 2

        ctrl.detach_mpr_from_subwindow(0)
        assert ctrl.get_view_metadata(view_id).pane_index is None
        assert ctrl.get_pane_view_metadata(0) is None
        assert ctrl.get_view_display_state(view_id).window_center == 40.0

    def test_unknown_view_ids_return_none(self) -> None:
        ctrl, _app = _make_controller()
        assert ctrl.get_view_metadata(42) is None
        assert ctrl.get_view_display_state(42) is None
        assert ctrl.get_view_thumbnail_pixels(42) is None

    def test_thumbnail_honours_the_views_own_combine_state(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result(n_slices=5))
        view_id = ctrl.attached_view_id(0)
        app.subwindow_data[0].update(
            mpr_combine_enabled=True, mpr_combine_mode="mip", mpr_combine_slice_count=4
        )
        with patch("gui.mpr_controller_sessions.apply_mpr_stack_combine", return_value=np.ones((2, 2))) as combine:
            ctrl.get_view_thumbnail_pixels(view_id, use_rescaled=False)
        assert combine.call_args.kwargs == {"enabled": True, "mode": "mip", "n_planes": 4}


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
        assert ctrl.get_view_metadata(detached_a) is None
        assert ctrl.get_view_metadata(detached_b) is None

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

    def test_close_all_releases_every_session_view_tile_and_reservation(self) -> None:
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
        assert ctrl.get_view_metadata(floating) is None

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
