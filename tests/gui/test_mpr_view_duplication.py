"""Unlinked shared-result duplication into a pane.

A duplicate is a new view of an existing session: same result object, its own
copy of the source view's slice/combine/display state, one view slot and no
session slot. Failure rolls back and releases the reservation; nothing is
confirmed until the target pane really rendered.
"""

from __future__ import annotations

from unittest.mock import patch

from mpr_lifecycle_harness import (
    FakeWorker,
    _add_detached_view,
    _counts,
    _light_display,
    _make_controller,
    _make_result,
    _register_worker,
    _seed_mpr_pane,
    _signals,
    _tile_events,
)

from core.lut_catalog import sigmoid_lut

_BOX = "gui.mpr_controller_sessions.QMessageBox"
_NO_SIGNALS = {"activated": [], "cleared": [], "detached": []}


def _session_of(ctrl, view_id):
    return ctrl._registry.get_session(ctrl._registry.get_view(view_id).session_id)


class TestSharedResultDuplicate:
    def test_duplicate_shares_the_result_and_adds_only_a_view(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        tiles = _tile_events(ctrl)
        result = _make_result(n_slices=5)
        _seed_mpr_pane(app, 0, result)
        source = ctrl.attached_view_id(0)
        before = _counts(ctrl)

        with _light_display(ctrl):
            assert ctrl.duplicate_view(source, 1) is True

        duplicate = ctrl.attached_view_id(1)
        assert duplicate not in (None, source)
        assert _counts(ctrl) == (before[0], before[1] + 1, 0, 0)  # +1 view, no new session
        assert _session_of(ctrl, duplicate) is _session_of(ctrl, source)
        assert _session_of(ctrl, duplicate).result is result  # one result object, never copied
        assert app.subwindow_data[1]["mpr_result"] is result
        assert ctrl.attached_view_id(0) == source  # the source is untouched
        assert fired == {"activated": [1], "cleared": [], "detached": []}
        assert tiles == [frozenset({duplicate})]
        meta = ctrl.get_view_metadata(duplicate)
        assert (meta.view_number, meta.view_count, meta.link_group_id) == (2, 2, None)

    def test_duplicate_snapshots_source_state_then_the_two_views_are_independent(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result(n_slices=6), wc=55.0, ww=555.0, inverted=True)
        custom = sigmoid_lut()
        from core.mpr_view_display_state import set_mpr_lut_override

        set_mpr_lut_override(app.subwindow_managers[0]["view_state_manager"], custom)
        data = app.subwindow_data[0]
        data.update(mpr_slice_index=4, mpr_combine_enabled=True, mpr_combine_mode="mip",
                    mpr_combine_slice_count=6)
        source = ctrl.attached_view_id(0)

        with _light_display(ctrl):
            ctrl.duplicate_view(source, 1)
        duplicate = ctrl.attached_view_id(1)

        view = ctrl._registry.get_view(duplicate)
        src_view = ctrl._registry.get_view(source)
        assert view.slice_index == 4
        assert (view.combine.enabled, view.combine.mode, view.combine.slice_count) == (True, "mip", 6)
        assert (view.display.window_center, view.display.window_width, view.display.inverted) == (55.0, 555.0, True)
        assert view.display.lut is custom  # frozen LUT handle shared by reference, never mutated
        assert view.combine is not src_view.combine and view.display is not src_view.display

        # Edit the SOURCE pane afterwards: the duplicate is unchanged.
        data.update(mpr_slice_index=1, mpr_combine_enabled=False)
        app.subwindow_managers[0]["view_state_manager"].current_window_width = 10.0
        ctrl.get_view_metadata(source)  # flush
        assert ctrl._registry.get_view(duplicate).slice_index == 4
        assert ctrl._registry.get_view(duplicate).display.window_width == 555.0
        # Edit the DUPLICATE pane: the source is unchanged.
        app.subwindow_data[1]["mpr_slice_index"] = 2
        app.subwindow_managers[1]["view_state_manager"].current_window_center = -9.0
        ctrl.get_view_metadata(duplicate)  # flush
        assert ctrl._registry.get_view(source).slice_index == 1
        assert ctrl._registry.get_view(source).display.window_center == 55.0

    def test_a_detached_view_can_be_duplicated_and_stays_detached(self) -> None:
        ctrl, app = _make_controller()
        result = _make_result()
        source = _add_detached_view(ctrl, result, slice_index=2)

        with _light_display(ctrl):
            assert ctrl.duplicate_view(source, 0) is True

        assert ctrl.detached_view_ids() == [source]
        duplicate = ctrl.attached_view_id(0)
        assert _session_of(ctrl, duplicate).result is result
        assert ctrl._registry.get_view(duplicate).slice_index == 2
        assert ctrl._registry.session_count == 1 and ctrl._registry.view_count == 2

    def test_duplicate_into_an_occupied_pane_preserves_the_occupant_as_detached(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        source, occupant = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        app.subwindow_data[1]["mpr_slice_index"] = 2  # live edit that must survive the swap
        before = _counts(ctrl)

        with _light_display(ctrl):
            assert ctrl.duplicate_view(source, 1) is True

        assert ctrl.detached_view_ids() == [occupant]
        assert ctrl._registry.get_view(occupant).slice_index == 2
        assert _session_of(ctrl, ctrl.attached_view_id(1)) is _session_of(ctrl, source)
        assert _counts(ctrl) == (before[0], before[1] + 1, 0, 0)  # +1 view: the occupant is retained
        assert fired == {"activated": [1], "cleared": [], "detached": [1]}

    def test_the_sources_own_pane_is_never_a_target(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        source = ctrl.attached_view_id(0)
        with patch.object(ctrl._registry, "reserve_view") as reserve:
            assert ctrl.duplicate_view(source, 0) is False
        reserve.assert_not_called()
        assert _counts(ctrl) == (1, 1, 0, 0)

    def test_stale_or_invalid_ids_and_targets_do_nothing(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        source = ctrl.attached_view_id(0)
        with patch.object(ctrl._registry, "reserve_view") as reserve, patch(_BOX) as box:
            assert ctrl.duplicate_view(999, 1) is False
            assert ctrl.duplicate_view(source, 7) is False  # no such pane
            app.multi_window_layout.get_subwindow = lambda i: None
            assert ctrl.duplicate_view(source, 1) is False  # pane without a viewer
        reserve.assert_not_called()
        box.warning.assert_not_called()
        assert _counts(ctrl) == (1, 1, 0, 0) and fired == _NO_SIGNALS

    def test_discarding_views_releases_the_session_with_the_last_one(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        source = ctrl.attached_view_id(0)
        with _light_display(ctrl):
            ctrl.duplicate_view(source, 1)
        ctrl.clear_mpr(0)
        assert ctrl._registry.session_count == 1  # the duplicate keeps the shared session alive
        assert ctrl.attached_view_id(1) is not None
        ctrl.clear_mpr(1)
        assert _counts(ctrl) == (0, 0, 0, 0)


class TestDuplicateAdmission:
    def test_at_the_view_cap_duplication_is_refused_naming_the_limit(self) -> None:
        ctrl, app = _make_controller()
        ctrl._registry.set_caps(8, 16)
        for _ in range(8):  # 8 sessions
            _add_detached_view(ctrl, _make_result())
        first_session = ctrl._registry.get_view(ctrl.detached_view_ids()[0]).session_id
        for _ in range(8):  # +8 duplicate views = 16
            ctrl._registry.create_view(first_session)
        assert ctrl._registry.view_count == 16
        source = ctrl.detached_view_ids()[0]
        fired = _signals(ctrl)

        with patch(_BOX) as box, _light_display(ctrl):
            assert ctrl.duplicate_view(source, 0) is False

        text = box.warning.call_args.args[2]
        assert "view limit" in text and "16/16" in text
        assert ctrl._registry.view_count == 16 and app.subwindow_data[0] == {}
        assert fired == _NO_SIGNALS and _counts(ctrl)[2:] == (0, 0)

    def test_at_the_cap_detach_move_and_reattach_still_work(self) -> None:
        ctrl, app = _make_controller()
        ctrl._registry.set_caps(2, 2)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        with _light_display(ctrl):
            ctrl.detach_mpr_from_subwindow(0)
            view = ctrl.detached_view_ids()[0]
            ctrl.move_view(view, 0)  # attach
            ctrl.move_view(view, 1)  # relocate over the occupant
            with patch(_BOX):
                assert ctrl.duplicate_view(view, 0) is False  # growth refused
        assert _counts(ctrl) == (2, 2, 0, 0)

    def test_admission_refusal_leaves_a_pending_destination_build_untouched(self) -> None:
        ctrl, app = _make_controller()
        ctrl._registry.set_caps(1, 1)
        source = _add_detached_view(ctrl, _make_result())
        worker = FakeWorker()
        _register_worker(ctrl, 1, worker)
        with patch(_BOX):
            ctrl.duplicate_view(source, 1)
        assert worker.cancel_calls == 0 and 1 in ctrl._workers

    def test_success_cancels_a_pending_build_in_the_target_pane(self) -> None:
        ctrl, app = _make_controller()
        source = _add_detached_view(ctrl, _make_result())
        worker = FakeWorker()
        _register_worker(ctrl, 1, worker)
        with _light_display(ctrl):
            assert ctrl.duplicate_view(source, 1) is True
        assert worker.cancel_calls == 1 and 1 not in ctrl._workers


class TestDuplicateFailure:
    def test_unrenderable_target_rolls_back_without_a_ghost_view(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        tiles = _tile_events(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        source, occupant = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        before = dict(app.subwindow_data[1])
        with (
            patch.object(ctrl, "display_mpr_slice", return_value=False),
            patch.object(ctrl, "_set_tools_enabled"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch(_BOX),
            patch("gui.mpr_controller.QMessageBox"),
        ):
            assert ctrl.duplicate_view(source, 1) is False
        assert _counts(ctrl) == (2, 2, 0, 0)  # reservation released, nothing created
        assert ctrl.attached_view_id(1) == occupant and ctrl.detached_view_ids() == []
        assert app.subwindow_data[1] == before
        assert fired == _NO_SIGNALS and tiles == []

    def test_confirm_failure_restores_the_target_and_releases_the_slot(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        source, occupant = ctrl.attached_view_id(0), ctrl.attached_view_id(1)
        before = dict(app.subwindow_data[1])
        with (
            _light_display(ctrl),
            patch.object(ctrl._registry, "confirm_view", side_effect=ValueError("malformed")),
            patch(_BOX),
        ):
            assert ctrl.duplicate_view(source, 1) is False
        assert _counts(ctrl) == (2, 2, 0, 0)
        assert ctrl.attached_view_id(1) == occupant and app.subwindow_data[1] == before
        assert fired == _NO_SIGNALS
        assert ctrl._registry.get_view(source).pane_index == 0


class TestReservationNeverStranded:
    """Every post-reservation step is inside one cleanup bracket."""

    def _seeded(self):
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        return ctrl, app, fired, ctrl.attached_view_id(0), ctrl.attached_view_id(1)

    def _assert_clean(self, ctrl, app, fired, occupant, before) -> None:
        assert _counts(ctrl) == (2, 2, 0, 0)  # reservation cancelled, nothing created
        assert ctrl.attached_view_id(1) == occupant and ctrl.detached_view_ids() == []
        assert app.subwindow_data[1] == before
        assert fired == _NO_SIGNALS

    def test_install_raising_cancels_the_reservation_and_restores_the_target(self) -> None:
        ctrl, app, fired, source, occupant = self._seeded()
        before = dict(app.subwindow_data[1])
        with (
            patch.object(ctrl, "_install_mpr_payload_at_subwindow", side_effect=RuntimeError("boom")),
            patch(_BOX) as box,
        ):
            assert ctrl.duplicate_view(source, 1) is False
        self._assert_clean(ctrl, app, fired, occupant, before)
        assert "left as it was" in box.warning.call_args.args[2]

    def test_snapshot_failure_cancels_the_reservation_before_anything_is_touched(self) -> None:
        ctrl, app, fired, source, occupant = self._seeded()
        before = dict(app.subwindow_data[1])
        with (
            patch("gui.mpr_view_duplication.capture_destination_snapshot", side_effect=RuntimeError("snap")),
            patch.object(ctrl, "_install_mpr_payload_at_subwindow") as install,
            patch("gui.mpr_view_duplication.restore_failed_install") as restore,
            patch(_BOX),
        ):
            assert ctrl.duplicate_view(source, 1) is False
        install.assert_not_called()  # nothing was installed...
        restore.assert_not_called()  # ...so nothing needed restoring
        self._assert_clean(ctrl, app, fired, occupant, before)

    def test_focus_or_worker_cancel_failure_cancels_the_reservation(self) -> None:
        ctrl, app, fired, source, occupant = self._seeded()
        before = dict(app.subwindow_data[1])
        with patch("gui.mpr_view_duplication.focus_destination", side_effect=RuntimeError("focus")), patch(_BOX):
            assert ctrl.duplicate_view(source, 1) is False
        self._assert_clean(ctrl, app, fired, occupant, before)
        with patch.object(ctrl, "_cancel_mpr_worker", side_effect=RuntimeError("cancel")), patch(_BOX):
            assert ctrl.duplicate_view(source, 1) is False
        self._assert_clean(ctrl, app, fired, occupant, before)

    def test_incomplete_restore_after_confirm_failure_is_reported_accurately(self) -> None:
        ctrl, app, fired, source, occupant = self._seeded()
        with (
            _light_display(ctrl),
            patch.object(ctrl._registry, "confirm_view", side_effect=ValueError("malformed")),
            patch("gui.mpr_view_duplication.restore_failed_install", return_value=False) as restore,
            patch(_BOX) as box,
        ):
            assert ctrl.duplicate_view(source, 1) is False
        restore.assert_called_once()
        text = box.warning.call_args.args[2]
        assert "could not be fully restored" in text and "left as it was" not in text
        assert _counts(ctrl) == (2, 2, 0, 0) and fired == _NO_SIGNALS

    def test_complete_restore_says_the_window_was_left_as_it_was(self) -> None:
        ctrl, app, fired, source, occupant = self._seeded()
        with (
            _light_display(ctrl),
            patch.object(ctrl._registry, "confirm_view", side_effect=ValueError("malformed")),
            patch("gui.mpr_view_duplication.restore_failed_install", return_value=True),
            patch(_BOX) as box,
        ):
            ctrl.duplicate_view(source, 1)
        text = box.warning.call_args.args[2]
        assert "left as it was" in text and "could not be fully restored" not in text

    def test_a_restore_that_itself_raises_counts_as_incomplete(self) -> None:
        ctrl, app, fired, source, occupant = self._seeded()
        with (
            _light_display(ctrl),
            patch.object(ctrl._registry, "confirm_view", side_effect=ValueError("malformed")),
            patch("gui.mpr_view_duplication.restore_failed_install", side_effect=RuntimeError("restore")),
            patch(_BOX) as box,
        ):
            assert ctrl.duplicate_view(source, 1) is False
        assert "could not be fully restored" in box.warning.call_args.args[2]
        assert _counts(ctrl) == (2, 2, 0, 0)

    def test_install_refusal_makes_no_claim_about_the_window_state(self) -> None:
        """The install helper rolls itself back and warns on a failed restore; we add no false claim."""
        ctrl, app, fired, source, occupant = self._seeded()
        with patch.object(ctrl, "_install_mpr_payload_at_subwindow", return_value=False), patch(_BOX) as box:
            assert ctrl.duplicate_view(source, 1) is False
        text = box.warning.call_args.args[2]
        assert "left as it was" not in text
        assert _counts(ctrl) == (2, 2, 0, 0)
