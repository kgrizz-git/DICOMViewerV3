"""Source-generation fence, isolated: a source close alone must reject a stale callback.

A build callback is current only if its worker is still registered, its pane
generation is unchanged AND its source generation is unchanged. These tests
change *only* the source generation (worker identity and pane generation stay
put), so they prove the third condition does real work and that the closure
path bumps through the shared helper.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from mpr_lifecycle_harness import (
    FakeWorker,
    _make_controller,
    _register_worker,
    _result_for,
)

from gui.mpr_source_closure import _bump_closed_source_generations
from gui.mpr_worker_fencing import (
    bump_source_generation,
    is_current_pane_build,
    note_build_started,
)

KEY = ("ST", "SE")


def _started(ctrl, idx: int = 0, key=KEY):
    """A registered worker plus the generations captured when its build started."""
    worker = FakeWorker()
    _register_worker(ctrl, idx, worker)
    pane_generation, source_generation = note_build_started(ctrl, idx, key)
    return worker, pane_generation, source_generation


class TestSourceGenerationAloneInvalidates:
    def test_helper_bump_rejects_a_callback_whose_worker_and_pane_are_unchanged(self) -> None:
        ctrl, _app = _make_controller()
        worker, pane_gen, source_gen = _started(ctrl)
        assert is_current_pane_build(ctrl, 0, worker, pane_gen, KEY, source_gen) is True

        new_generation = bump_source_generation(ctrl, *KEY)

        assert new_generation == source_gen + 1
        assert ctrl._workers[0] is worker  # same worker identity
        assert ctrl._build_generations[0] == pane_gen  # same pane generation
        assert is_current_pane_build(ctrl, 0, worker, pane_gen, KEY, source_gen) is False

    def test_bumping_another_source_leaves_the_callback_current(self) -> None:
        ctrl, _app = _make_controller()
        worker, pane_gen, source_gen = _started(ctrl)
        bump_source_generation(ctrl, "ST", "OTHER")
        bump_source_generation(ctrl, "OTHER-ST", "SE")
        assert is_current_pane_build(ctrl, 0, worker, pane_gen, KEY, source_gen) is True

    def test_each_bump_advances_exactly_one(self) -> None:
        ctrl, _app = _make_controller()
        assert [bump_source_generation(ctrl, *KEY) for _ in range(3)] == [1, 2, 3]

    def test_stale_finish_and_error_callbacks_do_nothing_and_keep_the_worker_registered(self) -> None:
        ctrl, app = _make_controller()
        worker, pane_gen, source_gen = _started(ctrl)
        assert ctrl._registry.reserve_build(*KEY) is not None
        bump_source_generation(ctrl, *KEY)  # only the source generation changes
        dialog = MagicMock()

        with patch.object(ctrl, "_activate_mpr") as activate, patch("gui.mpr_controller.QMessageBox") as box:
            ctrl._on_mpr_build_finished(
                0, worker, pane_gen, KEY, source_gen, _result_for(*KEY), MagicMock(), "Axial", dialog
            )
            ctrl._on_mpr_build_error(0, worker, pane_gen, KEY, source_gen, "boom", dialog)

        activate.assert_not_called()
        box.critical.assert_not_called()  # the stale error is not reported either
        assert ctrl._workers[0] is worker  # stale callbacks never pop a worker they do not own
        assert app.subwindow_data[0] == {}

    def test_positive_control_the_same_callback_activates_when_nothing_was_bumped(self) -> None:
        ctrl, _app = _make_controller()
        worker, pane_gen, source_gen = _started(ctrl)
        with patch.object(ctrl, "_activate_mpr") as activate:
            ctrl._on_mpr_build_finished(
                0, worker, pane_gen, KEY, source_gen, _result_for(*KEY), MagicMock(), "Axial", MagicMock()
            )
        activate.assert_called_once()


class TestClosureBumpsThroughTheHelper:
    def _generations(self, ctrl):
        for key in (("ST", "SE-1"), ("ST", "SE-2"), ("OTHER", "SE-1")):
            ctrl._source_generations[key] = 5
        return dict(ctrl._source_generations)

    def test_series_close_bumps_only_the_matching_key_once(self) -> None:
        ctrl, _app = _make_controller()
        before = self._generations(ctrl)
        with patch("gui.mpr_source_closure.bump_source_generation", wraps=bump_source_generation) as helper:
            _bump_closed_source_generations(ctrl, "ST", "SE-1")
        assert [c.args[1:] for c in helper.call_args_list] == [("ST", "SE-1")]
        after = ctrl._source_generations
        assert after[("ST", "SE-1")] == before[("ST", "SE-1")] + 1
        assert after[("ST", "SE-2")] == before[("ST", "SE-2")]
        assert after[("OTHER", "SE-1")] == before[("OTHER", "SE-1")]

    def test_study_close_bumps_every_series_of_that_study_only(self) -> None:
        ctrl, _app = _make_controller()
        before = self._generations(ctrl)
        _bump_closed_source_generations(ctrl, "ST", None)
        after = ctrl._source_generations
        assert after[("ST", "SE-1")] == after[("ST", "SE-2")] == 6
        assert after[("OTHER", "SE-1")] == before[("OTHER", "SE-1")]

    def test_a_close_rejects_a_stale_callback_without_touching_worker_or_pane(self) -> None:
        ctrl, _app = _make_controller()
        worker, pane_gen, source_gen = _started(ctrl)
        _bump_closed_source_generations(ctrl, *KEY)
        assert ctrl._workers[0] is worker and ctrl._build_generations[0] == pane_gen
        assert is_current_pane_build(ctrl, 0, worker, pane_gen, KEY, source_gen) is False

    def test_close_all_bumps_every_key_exactly_once_through_the_helper(self) -> None:
        ctrl, _app = _make_controller()
        before = self._generations(ctrl)
        with patch("gui.mpr_source_closure.bump_source_generation", wraps=bump_source_generation) as helper:
            ctrl.release_all_mpr()
        assert helper.call_count == len(before)
        assert all(ctrl._source_generations[k] == v + 1 for k, v in before.items())

    def test_real_source_close_with_a_pending_build_fences_its_late_callback(self) -> None:
        ctrl, _app = _make_controller()
        worker, pane_gen, source_gen = _started(ctrl)
        ctrl._build_sources[0] = KEY
        ctrl.release_mpr_for_closed_source(*KEY)
        assert ctrl._source_generations[KEY] == source_gen + 1
        with patch.object(ctrl, "_activate_mpr") as activate:
            ctrl._on_mpr_build_finished(
                0, worker, pane_gen, KEY, source_gen, _result_for(*KEY), MagicMock(), "Axial", MagicMock()
            )
        activate.assert_not_called()
