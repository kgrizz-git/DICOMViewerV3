"""Linked duplicate views: canonical slice setter, input paths, display independence.

Real controller, real slice navigator, real ``CinePlayer`` and the real
``on_slice_changed`` (wired as the app wires them), so wheel, keyboard,
slider and cine all travel the production path. Synthetic data only.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from mpr_lifecycle_harness import (
    LinkWorld,
    _add_detached_view,
    _make_link_world,
    _make_result,
    _seed_mpr_pane,
    _signals,
    _spy_redraws,
    _tile_events,
)
from PySide6.QtCore import Qt

from core.lut_catalog import sigmoid_lut
from core.mpr_session_types import LinkGroupError
from core.mpr_view_display_state import set_mpr_lut_override

_BOX = "gui.mpr_controller_sessions.QMessageBox"


@pytest.fixture
def world() -> LinkWorld:
    return _make_link_world(pane_count=3, n_slices=12)


def _linked_pair(world: LinkWorld, start: int = 3) -> tuple[int, int]:
    """A (pane 0) and a linked duplicate B (pane 1) of one session, both at *start*."""
    _seed_mpr_pane(world.app, 0, _make_result(n_slices=world.n_slices), study="ST")
    world.ctrl.set_pane_slice(0, start)
    a = world.ctrl.attached_view_id(0)
    assert world.ctrl.duplicate_view(a, 1, linked=True) is True
    b = world.ctrl.attached_view_id(1)
    world.focus(0)
    return a, b


def _scroll(world: LinkWorld, how: str) -> None:
    """One step forward through the named production input path."""
    if how == "wheel":
        assert world.nav.handle_wheel_event(-120) is True  # negative delta = next slice
    elif how == "keyboard":
        assert world.nav.handle_key_event(Qt.Key.Key_Up) is True
    elif how == "slider":
        world.nav.set_current_slice(world.nav.current_slice_index + 1)  # slider_navigate_callback target
    elif how == "cine":
        world.cine.is_playing = True
        world.cine._advance_frame()
    else:  # pragma: no cover
        raise AssertionError(how)


class TestLinkedDuplicate:
    def test_linked_duplicate_creates_the_group_atomically_and_shares_the_session(self, world) -> None:
        a, b = _linked_pair(world)
        reg = world.ctrl._registry
        group = reg.get_view(a).link_group_id
        assert group is not None and reg.get_view(b).link_group_id == group
        assert reg.link_members(group) == sorted([a, b])
        assert reg.get_view(a).session_id == reg.get_view(b).session_id
        assert world.live(1) == 3 == world.live(0)  # starts at the source's current slice

    def test_a_third_linked_duplicate_joins_the_existing_group(self, world) -> None:
        a, b = _linked_pair(world)
        group = world.ctrl._registry.get_view(a).link_group_id
        assert world.ctrl.duplicate_view(b, 2, linked=True) is True
        c = world.ctrl.attached_view_id(2)
        assert world.ctrl._registry.link_members(group) == sorted([a, b, c])
        assert world.ctrl._registry._link_groups.keys() == {group}  # no second group created

    def test_plain_duplicate_stays_unlinked_and_scrolls_independently(self, world) -> None:
        _seed_mpr_pane(world.app, 0, _make_result(n_slices=12), study="ST")
        a = world.ctrl.attached_view_id(0)
        world.ctrl.duplicate_view(a, 1)
        assert world.ctrl._registry.get_view(a).link_group_id is None
        world.ctrl.set_pane_slice(0, 7)
        assert world.live(1) != 7

    def test_link_state_reaches_the_metadata_for_labels(self, world) -> None:
        a, b = _linked_pair(world)
        assert world.ctrl.get_view_metadata(b).link_group_id == world.ctrl.get_view_metadata(a).link_group_id


class TestEveryInputPathMovesTheGroupOnce:
    @pytest.mark.parametrize("how", ["wheel", "keyboard", "slider", "cine"])
    def test_forward_step_moves_both_views_and_redraws_each_exactly_once(self, world, how) -> None:
        a, b = _linked_pair(world, start=3)
        spy = _spy_redraws(world)
        try:
            _scroll(world, how)
            assert (world.live(0), world.live(1)) == (4, 4)
            assert world.ctrl._registry.get_view(a).slice_index == 4  # registry canonical for both
            assert world.ctrl._registry.get_view(b).slice_index == 4
            assert world.redraws() == {0: 1, 1: 1}
        finally:
            spy.stop()

    @pytest.mark.parametrize("how", ["wheel", "keyboard", "slider", "cine"])
    def test_it_is_bidirectional(self, world, how) -> None:
        _linked_pair(world, start=3)
        world.focus(1)
        _scroll(world, how)
        assert (world.live(0), world.live(1)) == (4, 4)

    def test_cine_keeps_playing_through_a_linked_scroll(self, world) -> None:
        _linked_pair(world)
        world.cine.is_playing = True
        world.cine._advance_frame()
        assert world.cine.is_playing is True  # cine-driven moves do not look like manual navigation
        world.cine.reset_cine_advancing_flag()  # the app resets it on the next event-loop turn
        world.nav.next_slice()  # a manual step does pause it
        assert world.cine.is_playing is False

    def test_focus_change_during_cine_is_safe(self, world) -> None:
        _linked_pair(world, start=3)
        world.cine.is_playing = True
        world.cine._advance_frame()
        world.focus(1)  # the singleton player now follows pane 1
        world.cine._advance_frame()
        assert (world.live(0), world.live(1)) == (5, 5)

    def test_a_focused_peer_moved_by_a_link_updates_the_shared_navigator_without_reentry(self, world) -> None:
        _linked_pair(world, start=3)
        world.focus(1)  # the navigator now belongs to B
        emitted: list[int] = []
        world.nav.slice_changed.connect(emitted.append)
        world.app.cine_controls_widget.reset_mock()

        world.ctrl.set_pane_slice(0, 9)  # the initiator is the unfocused pane A

        assert world.nav.current_slice_index == 9  # shared navigator followed the focused peer
        assert emitted == []  # silently: no second on_slice_changed pass
        world.app.cine_controls_widget.update_frame_position.assert_called_with(9, 12)
        assert world.live(1) == 9

    def test_index_is_clamped_to_the_shared_stack(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        update = world.ctrl.set_pane_slice(0, 999)
        assert (update.index, update.changed, update.peers) == (11, True, (b,))
        assert (world.live(0), world.live(1)) == (11, 11)
        assert world.ctrl.set_pane_slice(0, -50).index == 0
        assert (world.live(0), world.live(1)) == (0, 0)

    def test_bad_indices_and_unknown_targets_change_nothing(self, world) -> None:
        a, _b = _linked_pair(world, start=3)
        assert world.ctrl.set_view_slice(a, "x") is None  # type: ignore[arg-type]
        assert world.ctrl.set_view_slice(a, None) is None  # type: ignore[arg-type]
        assert world.ctrl.set_view_slice(9999, 5) is None
        assert world.ctrl.set_pane_slice(2, 5) is None  # pane without a view
        assert (world.live(0), world.live(1)) == (3, 3)

    def test_equal_index_is_an_early_return_without_a_redraw(self, world) -> None:
        _linked_pair(world, start=3)
        spy = _spy_redraws(world)
        try:
            update = world.ctrl.set_pane_slice(0, 3)
            assert update.changed is False and world.redraws() == {}
        finally:
            spy.stop()

    def test_a_lagging_peer_alone_is_repaired_without_redrawing_the_source(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        world.app.subwindow_data[1]["mpr_slice_index"] = 1  # peer drifted
        spy = _spy_redraws(world)
        try:
            update = world.ctrl.set_pane_slice(0, 3)
            assert update.changed is True and world.redraws() == {1: 1}
            assert world.live(1) == 3
        finally:
            spy.stop()


class TestRedrawOnlyNeverPropagates:
    def test_display_mpr_slice_on_one_linked_pane_leaves_its_peer_alone(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        with patch.object(world.ctrl, "set_view_slice", wraps=world.ctrl.set_view_slice) as setter:
            assert world.ctrl.display_mpr_slice(0, 9) is True
        setter.assert_not_called()
        assert world.live(1) == 3 and world.ctrl._registry.get_view(b).slice_index == 3

    def test_overlay_wl_combine_and_reset_redraws_do_not_move_the_group(self, world) -> None:
        from core.slice_display_handlers import redisplay_current_slice

        a, b = _linked_pair(world, start=3)
        world.app.subwindow_data[0]["mpr_combine_enabled"] = True
        world.app.subwindow_managers[0]["view_state_manager"].current_window_center = 99.0
        for _ in range(3):
            redisplay_current_slice(world.app)  # the redraw-only path used by W/L, combine, overlay
        world.ctrl.display_mpr_slice(0, world.live(0))
        assert (world.live(0), world.live(1)) == (3, 3)
        with patch.object(world.ctrl, "set_view_slice") as setter:
            redisplay_current_slice(world.app)
        setter.assert_not_called()

    def test_peer_redraw_never_reenters_the_setter_or_global_sync(self, world) -> None:
        _linked_pair(world, start=3)
        calls: list[tuple] = []
        original = world.ctrl.set_pane_slice

        def reenter(pane, index):
            calls.append((pane, index, world.ctrl._slice_propagating))
            return original(pane, index)

        with (
            patch.object(world.coord, "on_slice_changed", wraps=world.coord.on_slice_changed) as outbound,
            patch.object(world.ctrl, "set_pane_slice", side_effect=reenter),
        ):
            world.nav.next_slice()
        assert calls == [(0, 4, False)]  # one top-level call, nothing from the peer redraw
        outbound.assert_called_once_with(0)  # outbound global sync started once, from the initiator


class TestRegistryDriftRepair:
    def test_attached_live_on_target_but_stale_registry_is_corrected_without_a_redraw(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        world.ctrl._registry.set_view_slice(a, 1)  # registry drifted; the pane still shows 3
        spy = _spy_redraws(world)
        try:
            update = world.ctrl.set_pane_slice(0, 3)
            assert update.changed is True and world.redraws() == {}
            assert world.ctrl._registry.get_view(a).slice_index == 3
            assert world.live(0) == world.live(1) == 3
        finally:
            spy.stop()

    def test_detached_peer_with_a_stale_registry_index_is_corrected_without_a_redraw(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        world.ctrl.detach_mpr_from_subwindow(1)
        world.ctrl._registry.set_view_slice(b, 0)
        tiles = _tile_events(world.ctrl)
        spy = _spy_redraws(world)
        try:
            update = world.ctrl.set_pane_slice(0, 3)
            assert update.changed is True and world.redraws() == {}
            assert world.ctrl._registry.get_view(b).slice_index == 3
            world.ctrl.flush_tile_refresh()
            assert tiles == [frozenset({b})]
        finally:
            spy.stop()

    def test_a_fully_consistent_group_is_still_an_early_return(self, world) -> None:
        _linked_pair(world, start=3)
        world.ctrl.detach_mpr_from_subwindow(1)
        tiles = _tile_events(world.ctrl)
        assert world.ctrl.set_pane_slice(0, 3).changed is False
        world.ctrl.flush_tile_refresh()
        assert tiles == []


class TestGroupIsWrittenBeforeAnyRedraw:
    def test_every_redraw_observes_every_member_already_at_the_target(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        assert world.ctrl.duplicate_view(b, 2, linked=True) is True
        c = world.ctrl.attached_view_id(2)
        # A fourth, detached member of the same group.
        assert world.ctrl.duplicate_view(a, 1, linked=True) is True  # displaces B into the detached list
        reg = world.ctrl._registry
        members = reg.link_members(reg.get_view(a).link_group_id)
        assert len(members) == 4
        observed: list[tuple[int, list[int], list[int]]] = []
        original = world.ctrl.display_mpr_slice

        def inspecting(pane, index):
            live = [
                int(world.app.subwindow_data[reg.get_view(m).pane_index]["mpr_slice_index"])
                for m in members if reg.get_view(m).pane_index is not None
            ]
            observed.append((pane, live, [reg.get_view(m).slice_index for m in members]))
            return original(pane, index)

        with patch.object(world.ctrl, "display_mpr_slice", side_effect=inspecting):
            world.ctrl.set_pane_slice(0, 9)

        assert {p for p, _l, _r in observed} == {0, 1, 2}  # every attached member redrawn
        assert len(observed) == 3
        for _pane, live, registry in observed:
            assert live == [9] * len(live) and registry == [9] * 4  # nothing half-updated
        assert world.ctrl.get_view_metadata(b).slice_index == 9  # the detached member too
        assert c is not None

    def test_a_failing_redraw_leaves_the_whole_group_consistent_and_logs_a_constant_message(self, world) -> None:
        a, b = _linked_pair(world, start=3)

        def explode(pane, index):
            raise RuntimeError("sensitive-detail-123")

        with (
            patch.object(world.ctrl, "display_mpr_slice", side_effect=explode),
            patch("gui.mpr_view_links.print_redacted") as log,
        ):
            world.ctrl.set_pane_slice(0, 8)

        reg = world.ctrl._registry
        assert reg.get_view(a).slice_index == reg.get_view(b).slice_index == 8
        assert world.live(0) == world.live(1) == 8
        assert log.call_count == 2
        for call in log.call_args_list:
            message = call.args[0]
            assert "RuntimeError" not in message and "sensitive" not in message  # no exception content


class TestSetterGuard:
    def test_reentrant_calls_are_ignored_and_the_guard_is_always_released(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        results: list = []

        def redraw_that_tries_to_navigate(pane, index):
            results.append(world.ctrl.set_view_slice(a, 0))  # re-entry from inside a redraw

        with patch.object(world.ctrl, "display_mpr_slice", side_effect=redraw_that_tries_to_navigate):
            world.ctrl.set_pane_slice(0, 8)
        assert results and all(r is None for r in results)
        assert world.ctrl._slice_propagating is False
        assert (world.live(0), world.live(1)) == (8, 8)

    def test_guard_is_released_even_if_a_redraw_raises(self, world) -> None:
        _linked_pair(world, start=3)
        with patch.object(world.ctrl, "display_mpr_slice", side_effect=RuntimeError("render")):
            update = world.ctrl.set_pane_slice(0, 6)
        assert update.changed is True and world.ctrl._slice_propagating is False

    def test_guard_is_independent_of_global_sync_state(self, world) -> None:
        _linked_pair(world, start=3)
        world.coord._syncing = True  # a global sync pass is mid-flight
        assert world.ctrl.set_pane_slice(0, 5).changed is True
        world.coord._syncing = False
        world.ctrl._slice_propagating = True  # and the reverse: setter busy does not block sync state
        assert world.coord._syncing is False
        world.ctrl._slice_propagating = False

    def test_linking_works_with_global_sync_off(self, world) -> None:
        _linked_pair(world, start=3)
        assert world.coord.enabled is False
        world.nav.next_slice()
        assert (world.live(0), world.live(1)) == (4, 4)


class TestIndependentDisplayState:
    def test_scrolling_changes_position_only(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        app = world.app
        custom = sigmoid_lut()
        set_mpr_lut_override(app.subwindow_managers[0]["view_state_manager"], custom)
        app.subwindow_managers[0]["view_state_manager"].current_window_center = 50.0
        app.subwindow_managers[1]["view_state_manager"].current_window_center = 70.0
        app.subwindow_managers[1]["view_state_manager"].current_window_width = 700.0
        app.subwindow_data[0].update(mpr_combine_enabled=True, mpr_combine_mode="mip", mpr_combine_slice_count=6)
        app.subwindow_data[1].update(mpr_combine_enabled=False)
        app.multi_window_layout.get_subwindow(1).image_viewer.image_inverted = True

        world.nav.next_slice()
        world.nav.next_slice()

        assert (world.live(0), world.live(1)) == (5, 5)
        assert app.subwindow_managers[0]["view_state_manager"].current_window_center == 50.0
        assert (app.subwindow_managers[1]["view_state_manager"].current_window_center,
                app.subwindow_managers[1]["view_state_manager"].current_window_width) == (70.0, 700.0)
        assert app.subwindow_data[0]["mpr_combine_enabled"] is True
        assert app.subwindow_data[1]["mpr_combine_enabled"] is False
        assert app.multi_window_layout.get_subwindow(1).image_viewer.image_inverted is True
        flushed_a = world.ctrl.get_view_display_state(a)
        flushed_b = world.ctrl.get_view_display_state(b)
        assert flushed_a.lut is custom and flushed_b.lut is not custom
        assert (flushed_a.window_center, flushed_b.window_center) == (50.0, 70.0)


class TestDetachedMembers:
    def test_detached_peer_adopts_the_canonical_slice_and_schedules_one_tile_refresh(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        tiles = _tile_events(world.ctrl)
        world.ctrl.detach_mpr_from_subwindow(1)
        tiles.clear()

        for _ in range(3):
            world.nav.next_slice()  # a burst of scrolling

        assert world.ctrl._registry.get_view(b).slice_index == 6  # canonical while dormant
        assert world.ctrl.get_view_metadata(b).slice_index == 6
        assert tiles == []  # debounced: nothing yet
        world.ctrl.flush_tile_refresh()
        assert tiles == [frozenset({b})]  # exactly one refresh, naming the detached member
        world.ctrl.flush_tile_refresh()
        assert len(tiles) == 1  # nothing left to flush

    def test_attached_only_scrolling_schedules_no_tile_refresh(self, world) -> None:
        _linked_pair(world)
        tiles = _tile_events(world.ctrl)
        world.nav.next_slice()
        world.ctrl.flush_tile_refresh()
        assert tiles == []

    def test_reattach_shows_the_current_canonical_slice_and_the_flush_cannot_revert_it(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        world.ctrl.detach_mpr_from_subwindow(1)
        world.nav.next_slice()
        world.nav.next_slice()  # group canonical is now 5; B was detached at 3
        assert world.ctrl._registry.get_view(b).slice_index == 5

        world.ctrl.attach_detached_view(b, 1)

        assert world.live(1) == 5 and world.live(0) == 5
        # Flushing either pane afterwards must keep both registry indices canonical.
        world.ctrl.get_view_metadata(a)
        world.ctrl.get_view_metadata(b)
        assert world.ctrl._registry.get_view(a).slice_index == world.ctrl._registry.get_view(b).slice_index == 5

    def test_an_unlinked_detached_view_keeps_its_own_slice_on_reattach(self, world) -> None:
        _seed_mpr_pane(world.app, 0, _make_result(n_slices=12), study="ST")
        world.ctrl.set_pane_slice(0, 9)
        solo = _add_detached_view(world.ctrl, _make_result(n_slices=12), slice_index=2)
        world.ctrl.attach_detached_view(solo, 1)
        assert world.live(1) == 2

    def test_failed_peer_redraw_cannot_leave_a_stale_index_that_a_flush_would_spread(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        original = world.ctrl.display_mpr_slice

        def flaky(pane, index):
            if pane == 1:
                raise RuntimeError("render")
            return original(pane, index)

        with patch.object(world.ctrl, "display_mpr_slice", side_effect=flaky):
            world.ctrl.set_pane_slice(0, 8)
        world.ctrl.get_view_metadata(b)  # flush the lagging-looking peer
        world.ctrl.get_view_metadata(a)
        assert world.ctrl._registry.get_view(b).slice_index == 8
        assert world.ctrl._registry.get_view(a).slice_index == 8

    def _stale_detached_member(self, world):
        """B detached with a stale registry index (1) while attached A is canonical at 7."""
        a, b = _linked_pair(world, start=3)
        world.ctrl.detach_mpr_from_subwindow(1)
        world.ctrl.set_pane_slice(0, 7)
        world.ctrl._registry.set_view_slice(b, 1)  # deliberately stale
        group = world.ctrl._registry.get_view(a).link_group_id
        return a, b, group

    def _view_state(self, world, b, group):
        reg = world.ctrl._registry
        snap = reg.capture_view_snapshot(b)
        return (snap.slice_index, snap.combine, snap.display, reg.get_view(b).pane_index,
                reg.get_view(b).link_group_id, reg.link_members(group), reg.view_count)

    def test_an_invalid_drop_leaves_the_detached_view_exactly_as_it_was(self, world) -> None:
        a, b, group = self._stale_detached_member(world)
        before = self._view_state(world, b, group)
        with patch("gui.mpr_controller_transactions.QMessageBox") as box:
            world.ctrl.attach_detached_view(b, 99)  # no such pane
            world.app.multi_window_layout.get_subwindow = lambda i: None  # pane without a viewer
            world.ctrl.attach_detached_view(b, 2)
        assert self._view_state(world, b, group) == before
        assert world.ctrl._registry.get_view(b).slice_index == 1  # the stale index was NOT touched
        assert box.warning.called  # the user is told why each drop was refused

    def test_a_render_failed_drop_leaves_the_detached_view_exactly_as_it_was(self, world) -> None:
        a, b, group = self._stale_detached_member(world)
        before = self._view_state(world, b, group)
        fired = _signals(world.ctrl)
        with (
            patch.object(world.ctrl, "display_mpr_slice", return_value=False),
            patch("gui.mpr_controller.QMessageBox"),
            patch("gui.mpr_controller_transactions.QMessageBox") as txn_box,
        ):
            world.ctrl.attach_detached_view(b, 2)
        assert self._view_state(world, b, group) == before
        assert world.ctrl.detached_view_ids() == [b] and world.ctrl.attached_view_id(2) is None
        assert fired == {"activated": [], "cleared": [], "detached": []}
        assert txn_box.warning.called  # the failure is reported, not silently swallowed

    def test_a_successful_reattach_adopts_and_commits_the_canonical_slice(self, world) -> None:
        a, b, group = self._stale_detached_member(world)
        with (
            patch("gui.mpr_controller.QMessageBox") as ctrl_box,
            patch("gui.mpr_controller_transactions.QMessageBox") as txn_box,
        ):
            world.ctrl.attach_detached_view(b, 2)
        ctrl_box.warning.assert_not_called()
        txn_box.warning.assert_not_called()
        assert world.live(2) == 7 and world.live(0) == 7
        assert world.ctrl._registry.get_view(b).slice_index == 7  # committed only now
        assert world.ctrl._registry.get_view(a).slice_index == 7

    def test_displaced_linked_occupant_stays_a_dormant_member_that_still_follows(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        _seed_mpr_pane(world.app, 2, _make_result(n_slices=12), study="ST")
        mover = world.ctrl.attached_view_id(2)
        world.ctrl.relocate_mpr_subwindow(2, 1)  # displaces linked B into the detached list
        assert world.ctrl.detached_view_ids() == [b]
        world.nav.next_slice()
        assert world.ctrl._registry.get_view(b).slice_index == 4
        assert world.ctrl._registry.get_view(mover).link_group_id is None


class TestMembershipLifecycle:
    def test_unlink_dissolves_a_pair_and_stops_following(self, world) -> None:
        a, b = _linked_pair(world, start=3)
        tiles = _tile_events(world.ctrl)
        assert world.ctrl.unlink_view(a) is True
        reg = world.ctrl._registry
        assert reg.get_view(a).link_group_id is None and reg.get_view(b).link_group_id is None
        assert tiles == [frozenset()]
        world.nav.next_slice()
        assert (world.live(0), world.live(1)) == (4, 3)

    def test_unlinking_one_of_three_keeps_the_other_two_linked(self, world) -> None:
        a, b = _linked_pair(world)
        world.ctrl.duplicate_view(b, 2, linked=True)
        c = world.ctrl.attached_view_id(2)
        world.ctrl.unlink_view(c)
        reg = world.ctrl._registry
        assert reg.get_view(a).link_group_id == reg.get_view(b).link_group_id is not None
        assert reg.get_view(c).link_group_id is None
        world.nav.next_slice()
        assert (world.live(0), world.live(1), world.live(2)) == (4, 4, 3)

    def test_unlink_of_an_unlinked_or_unknown_view_is_a_no_op(self, world) -> None:
        _seed_mpr_pane(world.app, 0, _make_result(), study="ST")
        solo = world.ctrl.attached_view_id(0)
        tiles = _tile_events(world.ctrl)
        assert world.ctrl.unlink_view(solo) is False and world.ctrl.unlink_view(404) is False
        assert tiles == []

    def test_clearing_one_view_dissolves_the_pair(self, world) -> None:
        a, b = _linked_pair(world)
        world.ctrl.clear_mpr(1)
        assert world.ctrl._registry.get_view(a).link_group_id is None
        world.nav.next_slice()
        assert world.live(0) == 4

    def test_move_and_detach_preserve_membership(self, world) -> None:
        a, b = _linked_pair(world)
        group = world.ctrl._registry.get_view(a).link_group_id
        world.ctrl.relocate_mpr_subwindow(1, 2)
        world.ctrl.detach_mpr_from_subwindow(2)
        assert world.ctrl._registry.get_view(b).link_group_id == group

    def test_source_closure_removes_every_member_and_group(self, world) -> None:
        a, b = _linked_pair(world)
        group = world.ctrl._registry.get_view(a).link_group_id
        world.ctrl.release_mpr_for_closed_source("ST", "SE")
        assert world.ctrl._registry.view_count == 0
        with pytest.raises(LinkGroupError):
            world.ctrl._registry.link_members(group)

    def test_close_all_clears_groups(self, world) -> None:
        a, _b = _linked_pair(world)
        group = world.ctrl._registry.get_view(a).link_group_id
        world.ctrl.release_all_mpr()
        with pytest.raises(LinkGroupError):
            world.ctrl._registry.link_members(group)


class TestLinkedDuplicateRollback:
    def _setup(self, world):
        a, b = _linked_pair(world)
        _seed_mpr_pane(world.app, 2, _make_result(n_slices=12), study="ST")
        occupant = world.ctrl.attached_view_id(2)
        return a, b, occupant

    def test_link_failure_rolls_back_the_duplicate_and_restores_the_occupant(self, world) -> None:
        a, b, occupant = self._setup(world)
        reg = world.ctrl._registry
        group = reg.get_view(a).link_group_id
        before = dict(world.app.subwindow_data[2])
        fired = _signals(world.ctrl)
        tiles = _tile_events(world.ctrl)
        counts = (reg.session_count, reg.view_count)
        with (
            patch("gui.mpr_view_duplication.link_after_duplicate", side_effect=RuntimeError("link")),
            patch(_BOX) as box,
        ):
            assert world.ctrl.duplicate_view(a, 2, linked=True) is False
        assert (reg.session_count, reg.view_count) == counts and reg.pending_view_count == 0
        assert world.ctrl.attached_view_id(2) == occupant  # displaced occupant is back
        assert world.ctrl.detached_view_ids() == []
        assert reg.link_members(group) == sorted([a, b])  # existing links untouched
        assert world.app.subwindow_data[2] == before
        assert fired == {"activated": [], "cleared": [], "detached": []} and tiles == []
        assert "left as it was" in box.warning.call_args.args[2]

    def test_group_creation_failure_leaves_the_source_unlinked(self, world) -> None:
        _seed_mpr_pane(world.app, 0, _make_result(n_slices=12), study="ST")
        a = world.ctrl.attached_view_id(0)
        reg = world.ctrl._registry
        with patch.object(reg, "create_link_group", side_effect=ValueError("bad")), patch(_BOX):
            assert world.ctrl.duplicate_view(a, 1, linked=True) is False
        assert reg.get_view(a).link_group_id is None and world.ctrl.attached_view_id(1) is None
        assert (reg.session_count, reg.view_count, reg.pending_view_count) == (1, 1, 0)
        assert reg._link_groups == {}

    def test_join_failure_leaves_the_group_membership_unchanged(self, world) -> None:
        a, b = _linked_pair(world)
        reg = world.ctrl._registry
        group = reg.get_view(a).link_group_id
        with patch.object(reg, "join_link_group", side_effect=ValueError("bad")), patch(_BOX):
            assert world.ctrl.duplicate_view(b, 2, linked=True) is False
        assert reg.link_members(group) == sorted([a, b]) and world.ctrl.attached_view_id(2) is None

    def test_view_cap_refuses_a_linked_duplicate_without_touching_links(self, world) -> None:
        a, b = _linked_pair(world)
        reg = world.ctrl._registry
        reg.set_caps(1, 2)
        group = reg.get_view(a).link_group_id
        with patch(_BOX) as box:
            assert world.ctrl.duplicate_view(a, 2, linked=True) is False
        assert "view limit" in box.warning.call_args.args[2]
        assert reg.link_members(group) == sorted([a, b])
