"""In-window slice sliders of linked MPR views follow the group (real viewers, real slider seam).

Panes carry real ``ImageViewer`` widgets and the app's own
``_sync_navigation_slider_for_subwindow`` (the seam the display path uses), so
the assertions read the actual slider overlay value, not a mock. Sliders are
updated with signals blocked: no ``slider_navigate_callback``, no second
``on_slice_changed`` pass, no extra outbound global sync.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from mpr_lifecycle_harness import (
    LinkWorld,
    _make_link_world,
    _make_result,
    _seed_mpr_pane,
)

from gui.image_viewer import ImageViewer
from main_app_subwindow_management import SubwindowManagementMixin


def _slider(world: LinkWorld, pane: int):
    return world.app.multi_window_layout.get_subwindow(pane).image_viewer._slider_overlay._slider


def _slider_value(world: LinkWorld, pane: int) -> int:
    """The slider's 1-based position as the user would see it."""
    return int(_slider(world, pane).value())


@pytest.fixture
def world(qapp) -> LinkWorld:
    w = _make_link_world(pane_count=3, n_slices=12)
    app = w.app
    for pane in (0, 1, 2):
        app.multi_window_layout.get_subwindow(pane).image_viewer = ImageViewer()
    host = SubwindowManagementMixin.__new__(SubwindowManagementMixin)
    host.multi_window_layout = app.multi_window_layout
    host._mpr_controller = w.ctrl
    host.subwindow_data = app.subwindow_data
    host.current_studies = {}
    app._sync_navigation_slider_for_subwindow = host._sync_navigation_slider_for_subwindow
    _seed_mpr_pane(app, 0, _make_result(n_slices=12), study="ST")
    w.ctrl.set_pane_slice(0, 3)
    assert w.ctrl.duplicate_view(w.ctrl.attached_view_id(0), 1, linked=True) is True
    w.focus(0)
    return w


@pytest.mark.qt
class TestPeerSlidersFollow:
    def test_both_views_sliders_show_the_new_slice_after_a_wheel_step(self, world) -> None:
        world.nav.handle_wheel_event(-120)  # next slice, from the focused view A
        assert (world.live(0), world.live(1)) == (4, 4)
        assert (_slider_value(world, 0), _slider_value(world, 1)) == (5, 5)  # 1-based
        assert (_slider(world, 0).maximum(), _slider(world, 1).maximum()) == (12, 12)

    def test_the_unfocused_view_initiating_the_move_still_updates_both_sliders(self, world) -> None:
        world.focus(1)  # the shared navigator belongs to B
        world.ctrl.set_pane_slice(0, 9)  # A (unfocused) is the initiator
        assert (_slider_value(world, 0), _slider_value(world, 1)) == (10, 10)

    def test_a_peer_whose_redraw_fails_still_shows_the_group_slice_on_its_slider(self, world) -> None:
        original = world.ctrl.display_mpr_slice

        def flaky(pane, index):
            if pane == 1:
                raise RuntimeError("render")  # the display path's own slider sync never runs
            return original(pane, index)

        with patch.object(world.ctrl, "display_mpr_slice", side_effect=flaky):
            world.ctrl.set_pane_slice(0, 7)
        assert _slider_value(world, 1) == 8  # explicit per-pane sync after the redraw attempt

    def test_a_redraw_that_returns_false_still_syncs_the_slider(self, world) -> None:
        with patch.object(world.ctrl, "display_mpr_slice", return_value=False):
            world.ctrl.set_pane_slice(0, 6)
        assert (_slider_value(world, 0), _slider_value(world, 1)) == (7, 7)

    def test_only_attached_members_have_sliders_and_the_detached_one_follows_silently(self, world) -> None:
        group = world.ctrl._registry.get_view(world.ctrl.attached_view_id(0)).link_group_id
        b = world.ctrl.attached_view_id(1)
        world.ctrl.detach_mpr_from_subwindow(1)
        world.nav.next_slice()
        assert _slider_value(world, 0) == 5
        assert world.ctrl._registry.get_view(b).slice_index == 4
        assert world.ctrl._registry.get_view(b).link_group_id == group


@pytest.mark.qt
class TestSliderUpdatesAreSilent:
    def test_no_slider_callback_and_no_extra_navigation_or_outbound_sync(self, world) -> None:
        for pane in (0, 1):
            world.app.multi_window_layout.get_subwindow(pane).image_viewer.slider_navigate_callback = MagicMock()
        emitted: list[int] = []
        world.nav.slice_changed.connect(emitted.append)
        world.coord.set_enabled(True)
        world.coord.set_groups([[0, 2]])

        with (
            patch.object(world.coord, "on_slice_changed", wraps=world.coord.on_slice_changed) as outbound,
            patch.object(world.ctrl, "set_pane_slice", wraps=world.ctrl.set_pane_slice) as setter,
        ):
            world.nav.next_slice()

        for pane in (0, 1):
            viewer = world.app.multi_window_layout.get_subwindow(pane).image_viewer
            viewer.slider_navigate_callback.assert_not_called()
        assert emitted == [4]  # exactly the one user step; sliders did not re-emit
        assert [c.args for c in setter.call_args_list] == [(0, 4)]  # no re-entry from the slider sync
        outbound.assert_called_once_with(0)
        assert (_slider_value(world, 0), _slider_value(world, 1)) == (5, 5)

    def test_a_failing_slider_seam_cannot_break_the_group(self, world) -> None:
        world.app._sync_navigation_slider_for_subwindow = MagicMock(side_effect=RuntimeError("secret-xyz"))
        with patch("gui.mpr_view_links.print_redacted") as log:
            update = world.ctrl.set_pane_slice(0, 8)
        assert update.changed is True and (world.live(0), world.live(1)) == (8, 8)
        assert world.ctrl._slice_propagating is False
        assert log.called
        for call in log.call_args_list:
            assert "RuntimeError" not in call.args[0] and "secret" not in call.args[0]

    def test_a_missing_slider_seam_is_tolerated(self, world) -> None:
        del world.app._sync_navigation_slider_for_subwindow
        assert world.ctrl.set_pane_slice(0, 8).changed is True
        assert (world.live(0), world.live(1)) == (8, 8)

    def test_cine_through_the_linked_pair_keeps_both_sliders_current(self, world) -> None:
        world.cine.is_playing = True
        for _ in range(3):
            world.cine._advance_frame()
        assert (world.live(0), world.live(1)) == (6, 6)
        assert (_slider_value(world, 0), _slider_value(world, 1)) == (7, 7)
        assert world.cine.is_playing is True
