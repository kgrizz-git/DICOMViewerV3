"""Single-view canonical MPR slice setter (engine slice).

Pins the trimmed setter's contract: clamp, no-op early return, drift
repair, registry+pane writes before redraw, re-entrancy guard release,
and the detached-view rule (registry-only update; no pane callbacks with
``None``). Group traversal and linked scrolling arrive with the
duplicates-and-links slice.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from mpr_lifecycle_harness import (
    _counts,
    _make_controller,
    _make_result,
    _seed_mpr_pane,
)


def _world(*, n_slices: int = 8, start: int = 2):
    ctrl, app = _make_controller()
    _seed_mpr_pane(app, 0, _make_result(n_slices=n_slices))
    app.subwindow_data[0]["mpr_slice_index"] = start
    view_id = ctrl.attached_view_id(0)
    assert view_id is not None
    ctrl._registry.set_view_slice(view_id, start)  # registry matches the pane
    ctrl.display_mpr_slice = MagicMock(return_value=True)  # spy; redraw is tested structurally
    return ctrl, app, view_id


class TestClampAndNoOp:
    def test_index_is_clamped_to_the_stack(self) -> None:
        ctrl, _app, view_id = _world(n_slices=8)
        update = ctrl.set_view_slice(view_id, 99)
        assert update is not None and update.index == 7

    def test_negative_index_clamps_to_zero(self) -> None:
        ctrl, _app, view_id = _world(n_slices=8)
        update = ctrl.set_view_slice(view_id, -5)
        assert update is not None and update.index == 0

    def test_unknown_view_changes_nothing(self) -> None:
        ctrl, _app, _view_id = _world()
        assert ctrl.set_view_slice(999, 3) is None

    def test_equal_index_is_an_early_return_without_a_redraw(self) -> None:
        ctrl, _app, view_id = _world(start=3)
        assert ctrl.set_view_slice(view_id, 3).changed is False
        ctrl.display_mpr_slice.assert_not_called()


class TestDriftRepair:
    def test_pane_on_target_but_stale_registry_is_corrected_without_a_redraw(self) -> None:
        ctrl, app, view_id = _world(start=5)
        app.subwindow_data[0]["mpr_slice_index"] = 5
        ctrl._registry.set_view_slice(view_id, 1)  # stale registry index
        assert ctrl.set_view_slice(view_id, 5).changed is True
        ctrl.display_mpr_slice.assert_not_called()  # pane already showed the target
        assert ctrl._registry.get_view(view_id).slice_index == 5

    def test_fully_consistent_view_is_still_an_early_return(self) -> None:
        ctrl, app, view_id = _world(start=4)
        app.subwindow_data[0]["mpr_slice_index"] = 4
        assert ctrl.set_view_slice(view_id, 4).changed is False


class TestWritesBeforeRedraw:
    def test_the_redraw_observes_the_registry_already_at_the_target(self) -> None:
        ctrl, _app, view_id = _world(start=0)
        seen: dict[str, int] = {}

        def inspect(idx, slice_index):
            seen["registry"] = ctrl._registry.get_view(view_id).slice_index
            seen["pane"] = slice_index

        ctrl.display_mpr_slice.side_effect = inspect
        ctrl.set_view_slice(view_id, 6)
        assert seen == {"registry": 6, "pane": 6}
        ctrl.display_mpr_slice.assert_called_once_with(0, 6)

    def test_a_failing_redraw_leaves_registry_and_pane_consistent_and_releases_the_guard(self) -> None:
        ctrl, app, view_id = _world(start=0)
        ctrl.display_mpr_slice.side_effect = RuntimeError("render failed")
        update = ctrl.set_view_slice(view_id, 6)
        assert update is not None and update.index == 6
        assert ctrl._registry.get_view(view_id).slice_index == 6
        assert app.subwindow_data[0]["mpr_slice_index"] == 6
        assert ctrl._slice_propagating is False


class TestSetterGuard:
    def test_reentrant_calls_are_ignored_and_the_guard_is_always_released(self) -> None:
        ctrl, _app, view_id = _world(start=0)
        calls: list[int] = []

        def reenter(idx, slice_index):
            calls.append(slice_index)
            ctrl.set_view_slice(view_id, 0)  # re-entrant from inside the redraw

        ctrl.display_mpr_slice.side_effect = reenter
        assert ctrl.set_view_slice(view_id, 5) is not None
        assert calls == [5]  # the redraw ran once; the re-entry did not re-enter
        assert ctrl._slice_propagating is False
        assert ctrl._registry.get_view(view_id).slice_index == 5

    def test_guard_is_independent_of_global_sync_state(self) -> None:
        ctrl, _app, view_id = _world(start=0)
        app_sync = MagicMock()
        ctrl._app._slice_sync_coordinator = app_sync
        ctrl.set_view_slice(view_id, 5)
        app_sync.on_slice_changed.assert_not_called()  # the setter never calls the coordinator


class TestDetachedViewRule:
    def test_a_detached_view_updates_the_registry_only_with_no_pane_callbacks(self) -> None:
        ctrl, app, view_id = _world(start=2, n_slices=8)
        app.multi_window_layout.get_subwindow = lambda i: None
        ctrl._registry.detach_view(view_id)
        assert ctrl.attached_view_id(0) is None

        ctrl.set_view_slice(view_id, 5)

        assert ctrl._registry.get_view(view_id).slice_index == 5
        ctrl.display_mpr_slice.assert_not_called()
        app._sync_navigation_slider_for_subwindow.assert_not_called()

    def test_displaced_view_keeps_its_state_until_discarded(self) -> None:
        # Displacement (build over an occupied pane) keeps the earlier view in
        # the registry; it is bounded by the admission caps and not navigable
        # in this slice.
        ctrl, app, _view_id = _world(n_slices=6)
        old_view = ctrl.attached_view_id(0)
        with patch("gui.mpr_controller_sessions.QMessageBox"):
            ctrl._activate_mpr(0, _make_result(n_slices=4), "Coronal")
        assert old_view in ctrl.detached_view_ids()
        assert _counts(ctrl) == (2, 2, 0, 0)
