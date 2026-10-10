"""One tiles-changed announcement per controller transaction; view metadata; bounded pixels."""

from __future__ import annotations

from unittest.mock import patch

import numpy as np
from mpr_lifecycle_harness import (
    _add_detached_view,
    _build_flow,
    _light_display,
    _make_controller,
    _make_result,
    _request,
    _result_for,
    _seed_mpr_pane,
    _tile_events,
)

from gui.mpr_controller_sessions import THUMBNAIL_MAX_SIDE


class TestOneAnnouncementPerTransaction:
    def test_activation(self) -> None:
        ctrl, _app = _make_controller()
        tiles = _tile_events(ctrl)
        with _light_display(ctrl):
            ctrl._activate_mpr(0, _make_result(), "Axial")
        assert tiles == [frozenset({ctrl.attached_view_id(0)})]

    def test_activation_over_an_occupied_pane_is_still_one(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        tiles = _tile_events(ctrl)
        with _light_display(ctrl):
            ctrl._activate_mpr(0, _make_result(), "Coronal")
        assert len(tiles) == 1

    def test_relocate_over_an_occupied_pane_emits_three_signals_but_one_tile_batch(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        _seed_mpr_pane(app, 1, _make_result())
        mover = ctrl.attached_view_id(0)
        tiles = _tile_events(ctrl)
        with _light_display(ctrl):
            ctrl.relocate_mpr_subwindow(0, 1)
        assert tiles == [frozenset({mover})]

    def test_attach_detach_move_clear_and_discard_each_announce_once(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        view = ctrl.attached_view_id(0)
        floating = _add_detached_view(ctrl, _make_result())
        tiles = _tile_events(ctrl)
        with _light_display(ctrl):
            ctrl.detach_mpr_from_subwindow(0)
            assert len(tiles) == 1
            ctrl.move_view(view, 1)
            assert len(tiles) == 2
            ctrl.duplicate_view(view, 0)
            assert len(tiles) == 3
        ctrl.clear_mpr(1)
        assert len(tiles) == 4
        assert ctrl.discard_detached_view(floating) is True
        assert len(tiles) == 5
        assert ctrl.clear_view(ctrl.attached_view_id(0)) is True
        assert len(tiles) == 6

    def test_failed_transactions_and_stale_ids_announce_nothing(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        view = ctrl.attached_view_id(0)
        tiles = _tile_events(ctrl)
        with (
            patch.object(ctrl, "display_mpr_slice", return_value=False),
            patch.object(ctrl, "_set_tools_enabled"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch("gui.mpr_controller.QMessageBox"),
            patch("gui.mpr_controller_sessions.QMessageBox"),
            patch("gui.mpr_controller_transactions.QMessageBox"),
        ):
            ctrl.move_view(view, 1)
            ctrl.duplicate_view(view, 1)
            ctrl._activate_mpr(1, _make_result(), "Axial")
        ctrl.move_view(404, 1)
        assert ctrl.clear_view(404) is False and ctrl.discard_detached_view(404) is False
        assert tiles == []

    def test_source_closure_and_close_all_each_announce_once(self) -> None:
        ctrl, app = _make_controller()
        _add_detached_view(ctrl, _make_result(), "ST", "SE")
        tiles = _tile_events(ctrl)
        ctrl.release_mpr_for_closed_source("ST", "SE")
        assert len(tiles) == 1
        ctrl.release_all_mpr()
        assert len(tiles) == 2

    def test_pane_reset_safety_net_announces_once(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result())
        tiles = _tile_events(ctrl)
        ctrl.detach_view_for_pane_reset(0)
        ctrl.detach_view_for_pane_reset(1)  # no view: silent
        assert len(tiles) == 1

    def test_a_finished_build_announces_only_when_it_activates(self) -> None:
        ctrl, _app = _make_controller()
        tiles = _tile_events(ctrl)
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers), _light_display(ctrl):
            ctrl._on_mpr_requested(0, _request(result))
            assert tiles == []  # reserving a slot changes no tile
            workers[0].finished.connect.call_args_list[0].args[0](result)
        assert len(tiles) == 1


class TestViewMetadataForLabelsAndStamps:
    def test_view_numbers_follow_creation_order_within_a_session(self) -> None:
        ctrl, _app = _make_controller()
        session_id, first = ctrl._registry.create_session(_make_result(), "ST", "SE", "Axial")
        second = ctrl._registry.create_view(session_id)
        other = ctrl._registry.create_session(_make_result(), "ST", "SE", "Axial")[1]
        assert [(m.view_number, m.view_count) for m in map(ctrl.get_view_metadata, (first, second))] == [
            (1, 2), (2, 2),
        ]
        solo = ctrl.get_view_metadata(other)
        assert (solo.view_number, solo.view_count) == (1, 1)
        assert solo.session_id != ctrl.get_view_metadata(first).session_id  # same source, other session

    def test_link_state_is_exposed_for_labels(self) -> None:
        ctrl, _app = _make_controller()
        session_id, first = ctrl._registry.create_session(_make_result())
        second = ctrl._registry.create_view(session_id)
        group = ctrl._registry.create_link_group(session_id, [first, second])
        assert ctrl.get_view_metadata(first).link_group_id == group
        ctrl._registry.leave_link_group(first)
        assert ctrl.get_view_metadata(first).link_group_id is None

    def test_content_stamp_tracks_pixel_relevant_state_only(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _make_result(n_slices=5))
        view = ctrl.attached_view_id(0)
        base = ctrl.get_view_metadata(view).content_stamp
        assert ctrl.get_view_metadata(view).content_stamp == base  # stable across reads
        ctrl.detach_mpr_from_subwindow(0)
        assert ctrl.get_view_metadata(view).content_stamp == base  # pane moves are not pixel changes
        ctrl._registry.set_view_slice(view, 3)
        slice_changed = ctrl.get_view_metadata(view).content_stamp
        assert slice_changed != base  # e.g. a linked scroll while detached
        display = ctrl.get_view_display_state(view)
        display.window_width = 123.0
        ctrl._registry.set_view_display(view, display)
        assert ctrl.get_view_metadata(view).content_stamp not in (base, slice_changed)


class TestBoundedThumbnailPixels:
    def test_large_planes_are_subsampled_into_a_new_small_array(self) -> None:
        ctrl, _app = _make_controller()
        big = _make_result(n_slices=3)
        big.slices = [np.full((1200, 900), float(i), dtype=np.float32) for i in range(3)]
        view = _add_detached_view(ctrl, big)

        pixels = ctrl.get_view_thumbnail_pixels(view, use_rescaled=False)

        assert pixels is not None and max(pixels.shape) <= THUMBNAIL_MAX_SIDE
        assert pixels.dtype == np.float32 and float(pixels[0, 0]) == 1.0  # mid-stack slice
        assert not np.shares_memory(pixels, big.slices[1])

    def test_small_planes_are_still_copied_not_aliased(self) -> None:
        ctrl, _app = _make_controller()
        result = _make_result(n_slices=3)
        view = _add_detached_view(ctrl, result)
        pixels = ctrl.get_view_thumbnail_pixels(view, use_rescaled=False)
        assert pixels is not None and pixels.shape == result.slices[1].shape
        assert not np.shares_memory(pixels, result.slices[1])

    def test_rescale_is_applied_to_the_subsampled_array_only(self) -> None:
        ctrl, _app = _make_controller()
        big = _make_result(n_slices=3)
        big.slices = [np.ones((1024, 1024), dtype=np.float32) for _ in range(3)]
        big.rescale_slope, big.rescale_intercept = 2.0, -1.0
        view = _add_detached_view(ctrl, big)
        with patch.object(type(big), "apply_rescale", autospec=True, side_effect=lambda _s, a: a * 2.0 - 1.0) as rescale:
            pixels = ctrl.get_view_thumbnail_pixels(view, use_rescaled=True)
        assert max(rescale.call_args.args[1].shape) <= THUMBNAIL_MAX_SIDE
        assert pixels is not None and float(pixels[0, 0]) == 1.0
