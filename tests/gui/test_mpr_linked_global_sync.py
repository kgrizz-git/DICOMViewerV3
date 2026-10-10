"""Linked MPR views with anatomic global slice sync (outbound, incoming, dedup, no cascade).

Panes: 0 = MPR A, 1 = MPR B (linked to A), 2 = native C, 3/4 = native D/E.
The coordinator, controller, navigator and ``on_slice_changed`` are the real
ones; native panes are driven by calling the coordinator exactly as the
native branch of ``on_slice_changed`` does. Native slice *i* sits at z = i,
the same as MPR plane *i*, so anatomic matches are identities.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from mpr_lifecycle_harness import (
    LinkWorld,
    _add_detached_view,
    _make_link_world,
    _make_result,
    _native_series,
    _seed_mpr_pane,
    _seed_native_pane,
    _spy_redraws,
)


@pytest.fixture
def world() -> LinkWorld:
    w = _make_link_world(pane_count=5, n_slices=12)
    app = w.app
    _seed_mpr_pane(app, 0, _make_result(n_slices=12), study="ST")
    w.ctrl.set_pane_slice(0, 3)
    a = w.ctrl.attached_view_id(0)
    assert w.ctrl.duplicate_view(a, 1, linked=True) is True
    for idx in (2, 3, 4):
        _seed_native_pane(app, idx, _native_series(12, series=f"NSE{idx}"), current=3)
    w.focus(0)
    w.coord.set_enabled(True)
    return w


def _native_scroll(world: LinkWorld, pane: int, index: int) -> None:
    """What the native branch of ``on_slice_changed`` does, then outbound sync once."""
    world.app.subwindow_data[pane]["current_slice_index"] = index
    world.coord.on_slice_changed(pane)


def _native_displays(world: LinkWorld, pane: int) -> list:
    return world.app.subwindow_managers[pane]["slice_display_manager"].display_slice.call_args_list


class TestOutboundFromALinkedPane:
    def test_user_scroll_moves_the_peer_by_link_and_the_global_target_by_sync(self, world) -> None:
        world.coord.set_groups([[0, 1, 2]])
        spy = _spy_redraws(world)
        try:
            with (
                patch.object(world.ctrl, "set_pane_slice", wraps=world.ctrl.set_pane_slice) as setter,
                patch.object(world.coord, "_update_target", wraps=world.coord._update_target) as update,
            ):
                world.nav.next_slice()
            assert [c.args[0] for c in update.call_args_list] == [2]  # B never even evaluated
            assert (world.live(0), world.live(1)) == (4, 4)
            assert world.app.subwindow_data[2]["current_slice_index"] == 4
            assert len(_native_displays(world, 2)) == 1
            # Only the initiating pane went through the setter: B is a source-group member,
            # already moved by the link, and is deduplicated out of the global targets.
            assert [c.args for c in setter.call_args_list] == [(0, 4)]
            assert world.redraws() == {0: 1, 1: 1}
        finally:
            spy.stop()

    def test_the_peers_other_global_group_is_not_cascaded_into(self, world) -> None:
        world.coord.set_groups([[0, 2], [1, 3]])  # B's own global group contains native D
        world.nav.next_slice()
        assert (world.live(0), world.live(1)) == (4, 4)
        assert world.app.subwindow_data[2]["current_slice_index"] == 4  # A's group followed
        assert world.app.subwindow_data[3]["current_slice_index"] == 3  # B's group did NOT
        assert _native_displays(world, 3) == []

    def test_outbound_sync_runs_once_per_user_change(self, world) -> None:
        world.coord.set_groups([[0, 1, 2]])
        with patch.object(world.coord, "on_slice_changed", wraps=world.coord.on_slice_changed) as outbound:
            world.nav.next_slice()
        outbound.assert_called_once_with(0)
        assert world.coord._syncing is False

    def test_linking_is_independent_of_the_global_sync_toggle(self, world) -> None:
        world.coord.set_groups([[0, 1, 2]])
        world.coord.set_enabled(False)
        world.nav.next_slice()
        assert (world.live(0), world.live(1)) == (4, 4)  # explicit link still applies
        assert world.app.subwindow_data[2]["current_slice_index"] == 3  # global sync did not


class TestIncomingGlobalSync:
    def test_incoming_update_moves_the_whole_linked_group_exactly_once(self, world) -> None:
        world.coord.set_groups([[0, 1, 2]])
        world.focus(2)
        spy = _spy_redraws(world)
        try:
            with (
                patch.object(world.ctrl, "set_pane_slice", wraps=world.ctrl.set_pane_slice) as setter,
                patch.object(world.coord, "on_slice_changed", wraps=world.coord.on_slice_changed) as outbound,
                patch.object(world.coord, "_update_target", wraps=world.coord._update_target) as update,
            ):
                _native_scroll(world, 2, 7)
            assert [c.args[0] for c in update.call_args_list] == [0]  # one target for the group
            assert (world.live(0), world.live(1)) == (7, 7)
            assert [c.args for c in setter.call_args_list] == [(0, 7)]  # B deduplicated: one target
            assert world.redraws() == {0: 1, 1: 1}  # no double redraw
            outbound.assert_called_once_with(2)  # the setter never re-entered global sync
        finally:
            spy.stop()

    def test_a_peer_outside_the_global_group_still_follows_the_link(self, world) -> None:
        world.coord.set_groups([[0, 2]])  # B is not in any global group
        _native_scroll(world, 2, 6)
        assert (world.live(0), world.live(1)) == (6, 6)

    def test_incoming_update_does_not_cascade_into_the_peers_global_group(self, world) -> None:
        world.coord.set_groups([[0, 2], [1, 3]])
        _native_scroll(world, 2, 8)
        assert (world.live(0), world.live(1)) == (8, 8)
        assert world.app.subwindow_data[3]["current_slice_index"] == 3
        assert _native_displays(world, 3) == []

    def test_detached_member_follows_incoming_sync(self, world) -> None:
        world.coord.set_groups([[0, 2]])
        b = world.ctrl.attached_view_id(1)
        world.ctrl.detach_mpr_from_subwindow(1)
        _native_scroll(world, 2, 9)
        assert world.live(0) == 9 and world.ctrl._registry.get_view(b).slice_index == 9

    def test_a_source_outside_the_stack_coverage_leaves_the_group_alone(self, world) -> None:
        world.coord.set_groups([[0, 1, 2]])
        far = _native_series(12, series="FAR")
        for i, ds in enumerate(far):
            ds.ImagePositionPatient = [0.0, 0.0, 500.0 + i]
        _seed_native_pane(world.app, 2, far, current=0)
        _native_scroll(world, 2, 5)
        assert (world.live(0), world.live(1)) == (3, 3)

    def test_unlinked_mpr_panes_in_one_global_group_are_each_updated(self, world) -> None:
        world.ctrl.unlink_view(world.ctrl.attached_view_id(0))
        world.coord.set_groups([[0, 1, 2]])
        with patch.object(world.ctrl, "set_pane_slice", wraps=world.ctrl.set_pane_slice) as setter:
            _native_scroll(world, 2, 5)
        assert [c.args for c in setter.call_args_list] == [(0, 5), (1, 5)]
        assert (world.live(0), world.live(1)) == (5, 5)

    def test_two_linked_targets_of_another_group_cost_one_setter_call(self, world) -> None:
        # Source is B-less pane E (native); targets A and B are one explicit group.
        world.coord.set_groups([[4, 0, 1]])
        with patch.object(world.ctrl, "set_pane_slice", wraps=world.ctrl.set_pane_slice) as setter:
            _native_scroll(world, 4, 10)
        assert [c.args for c in setter.call_args_list] == [(0, 10)]
        assert (world.live(0), world.live(1)) == (10, 10)


class TestDedupeHelper:
    def test_without_a_link_aware_controller_targets_are_untouched(self, world) -> None:
        world.app._mpr_controller = object()
        assert world.coord._dedupe_by_link_group(0, [1, 2]) == [1, 2]

    def test_non_integer_group_ids_from_a_duck_typed_controller_are_ignored(self, world) -> None:
        from unittest.mock import MagicMock

        world.app._mpr_controller = MagicMock()  # every pane "has" the same mock group id
        assert world.coord._dedupe_by_link_group(0, [1, 2, 4]) == [1, 2, 4]

    def test_source_group_and_repeat_groups_are_dropped_in_order(self, world) -> None:
        # 0,1 linked (source group); 4 native; 2 native.
        assert world.coord._dedupe_by_link_group(0, [1, 2, 4]) == [2, 4]
        assert world.coord._dedupe_by_link_group(2, [0, 1, 4]) == [0, 4]


def test_unlinked_detached_views_are_unaffected_by_scrolling(world) -> None:
    other = _add_detached_view(world.ctrl, _make_result(n_slices=12), slice_index=2)
    world.nav.next_slice()
    assert world.ctrl._registry.get_view(other).slice_index == 2
