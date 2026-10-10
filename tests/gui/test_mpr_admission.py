"""Runtime MPR admission: live caps, usage/memory visibility, pending estimates.

Real controller and registry with synthetic results. Caps changes come from
the persisted config (a real ``ConfigManager`` where persistence matters);
the memory figure is the approximate estimate, never a limit or a prompt.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from mpr_lifecycle_harness import (
    _add_detached_view,
    _build_flow,
    _counts,
    _light_display,
    _make_controller,
    _make_result,
    _request,
    _result_for,
    _seed_mpr_pane,
)

from core.mpr_memory_estimate import THUMBNAIL_BYTES_PER_VIEW
from core.mpr_session_types import DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP
from gui.mpr_admission import (
    PaneReservation,
    admission_summary,
    memory_estimate,
    refresh_session_caps,
    strict_session_caps,
)
from gui.mpr_controller import MprController
from utils.config_manager import ConfigManager

_BOX = "gui.mpr_controller_sessions.QMessageBox"
MIB = 1024 * 1024


class _Image:
    def __init__(self, voxels: int) -> None:
        self._v = voxels

    def GetNumberOfPixels(self) -> int:
        return self._v

    def GetNumberOfComponentsPerPixel(self) -> int:
        return 1

    def GetPixelIDTypeAsString(self) -> str:
        return "32-bit float"


def _sized_result(voxels: int = 1000, plane: int = 8, n_slices: int = 3):
    """A result whose volume and slice buffers have known sizes."""
    result = _make_result(n_slices=n_slices)
    result.slices = [np.zeros((plane, plane), np.float32) for _ in range(n_slices)]
    result.source_volume.sitk_image = _Image(voxels)
    return result


def _config_caps(app, caps) -> None:
    app.config_manager.get_mpr_caps.return_value = caps


class TestSummaryAndEstimate:
    def test_summary_shows_counts_limits_and_an_approximate_figure(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _sized_result(voxels=MIB))  # 4 MiB volume
        text = admission_summary(ctrl)
        assert text.startswith("MPR: 1/8 sessions, 1/16 views, about ")
        assert text.endswith("MiB (estimate)")
        assert "4 MiB" in text  # the volume dominates; the tile copy is ~0.25 MiB

    def test_a_duplicate_view_shares_the_estimate_apart_from_its_tile(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _sized_result(voxels=MIB, plane=256, n_slices=20))
        before = memory_estimate(ctrl)
        with _light_display(ctrl):
            assert ctrl.duplicate_view(ctrl.attached_view_id(0), 1) is True
        after = memory_estimate(ctrl)
        assert (after.volume_bytes, after.result_bytes) == (before.volume_bytes, before.result_bytes)
        assert after.total_bytes - before.total_bytes == THUMBNAIL_BYTES_PER_VIEW  # no result copy
        assert ctrl._registry.session_count == 1

    def test_independent_sessions_of_one_series_are_charged_separately(self) -> None:
        ctrl, _app = _make_controller()
        _add_detached_view(ctrl, _sized_result(voxels=MIB))
        one = memory_estimate(ctrl).volume_bytes
        _add_detached_view(ctrl, _sized_result(voxels=MIB))
        assert memory_estimate(ctrl).volume_bytes == 2 * one

    def test_discarding_the_last_view_releases_the_estimate(self) -> None:
        ctrl, _app = _make_controller()
        view = _add_detached_view(ctrl, _sized_result(voxels=MIB))
        assert memory_estimate(ctrl).volume_bytes == 4 * MIB
        ctrl.discard_detached_view(view)
        assert memory_estimate(ctrl).total_bytes == 0

    def test_status_messages_never_leak_implementation_names(self) -> None:
        ctrl, _app = _make_controller()
        text = admission_summary(ctrl)
        for word in ("sitk", "ndarray", "buffer", "registry", "reservation"):
            assert word not in text.lower()


class TestPendingBuildVisibility:
    def _start(self, ctrl, result, pane=0):
        ds = result.source_volume.source_datasets[0]
        ds.Rows, ds.Columns = 64, 64
        return _build_flow(ctrl, result), _request(result), pane

    def test_admission_reports_usage_and_counts_the_pending_volume(self) -> None:
        ctrl, app = _make_controller()
        result = _result_for("ST", "SE")
        flow, request, pane = self._start(ctrl, result)
        with flow:
            ctrl._on_mpr_requested(pane, request)
        status = app.main_window.update_status.call_args.args[0]
        assert status.startswith("Building MPR. MPR: 0/8 sessions (+1 building), 0/16 views")
        held = ctrl._build_reservations[0]
        assert isinstance(held, PaneReservation) and held.pending_bytes == 64 * 64 * 1 * 4
        assert memory_estimate(ctrl).pending_bytes == 64 * 64 * 4

    def test_cancel_releases_the_count_and_the_estimate_exactly_once(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        flow, request, pane = self._start(ctrl, result)
        with flow:
            ctrl._on_mpr_requested(pane, request)
            assert _counts(ctrl)[2:] == (1, 1) and memory_estimate(ctrl).pending_bytes > 0
            ctrl._cancel_mpr_worker(pane)
            ctrl._cancel_mpr_worker(pane)
        assert _counts(ctrl)[2:] == (0, 0)
        assert memory_estimate(ctrl).pending_bytes == 0

    def test_a_finished_build_replaces_its_pending_estimate_with_real_buffers(self) -> None:
        ctrl, app = _make_controller()
        result = _sized_result(voxels=MIB)
        result.source_volume.source_datasets[0].Rows = 64
        result.source_volume.source_datasets[0].Columns = 64
        with _build_flow(ctrl, result) as (_v, workers), _light_display(ctrl):
            ctrl._on_mpr_requested(0, _request(result))
            workers[0].finished.connect.call_args_list[0].args[0](result)
        est = memory_estimate(ctrl)
        assert est.pending_bytes == 0 and est.volume_bytes == 4 * MIB
        status = app.main_window.update_status.call_args.args[0]
        assert status.startswith("MPR added. MPR: 1/8 sessions, 1/16 views, about 4 MiB")

    def test_source_closure_and_close_all_release_pending_estimates(self) -> None:
        ctrl, _app = _make_controller()
        result = _result_for("ST", "SE")
        flow, request, pane = self._start(ctrl, result)
        with flow:
            ctrl._on_mpr_requested(pane, request)
            ctrl.release_mpr_for_closed_source("ST", "SE")
            assert memory_estimate(ctrl).pending_bytes == 0
            ctrl._on_mpr_requested(pane, request)
            ctrl.release_all_mpr()
        assert memory_estimate(ctrl).pending_bytes == 0 and _counts(ctrl) == (0, 0, 0, 0)

    def test_a_plain_two_tuple_reservation_counts_as_no_estimate(self) -> None:
        ctrl, _app = _make_controller()
        ctrl._build_reservations[0] = (ctrl._registry.reserve_build("ST", "SE"), ("ST", "SE"))  # type: ignore[assignment]
        assert memory_estimate(ctrl).pending_bytes == 0


class TestRefusalAndDuplicateVisibility:
    def test_refusal_names_the_limit_counts_and_estimate_without_a_second_prompt(self) -> None:
        ctrl, app = _make_controller()
        ctrl._registry.set_caps(1, 4)
        _seed_mpr_pane(app, 1, _sized_result(voxels=MIB))
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result), patch(_BOX) as box:
            ctrl._on_mpr_requested(0, _request(result))
        box.warning.assert_called_once()  # one informational message, nothing to confirm
        text = box.warning.call_args.args[2]
        assert "session limit" in text and "(1/1)" in text
        assert "MPR: 1/1 sessions, 1/4 views, about 4 MiB (estimate)" in text

    def test_view_cap_refusal_of_a_duplicate_shows_usage(self) -> None:
        ctrl, app = _make_controller()
        ctrl._registry.set_caps(1, 1)
        source = _add_detached_view(ctrl, _sized_result(voxels=MIB))
        with patch(_BOX) as box:
            assert ctrl.duplicate_view(source, 0) is False
        text = box.warning.call_args.args[2]
        assert "view limit" in text and "1/1 views" in text and "(estimate)" in text

    def test_successful_duplicate_reports_that_it_shares_the_result(self) -> None:
        ctrl, app = _make_controller()
        _seed_mpr_pane(app, 0, _sized_result(voxels=MIB))
        with _light_display(ctrl):
            ctrl.duplicate_view(ctrl.attached_view_id(0), 1)
        status = app.main_window.update_status.call_args.args[0]
        assert "shares the existing result" in status and "1/8 sessions, 2/16 views" in status


class TestLiveCaps:
    def test_defaults_are_8_sessions_16_views(self) -> None:
        ctrl, _app = _make_controller()
        assert (ctrl._registry.session_cap, ctrl._registry.view_cap) == (DEFAULT_SESSION_CAP, DEFAULT_VIEW_CAP) == (8, 16)

    def test_a_persisted_change_governs_the_next_build_without_a_restart(self) -> None:
        ctrl, app = _make_controller()
        _config_caps(app, (1, 2))
        ctrl = MprController(app)
        _add_detached_view(ctrl, _make_result())
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result), patch(_BOX) as box:
            ctrl._on_mpr_requested(0, _request(result))
        assert "session limit" in box.warning.call_args.args[2]
        _config_caps(app, (3, 6))  # the user raises the limits in Settings
        with _build_flow(ctrl, result) as (_v, workers), patch(_BOX) as box:
            ctrl._on_mpr_requested(0, _request(result))
        box.warning.assert_not_called()
        assert len(workers) == 1 and (ctrl._registry.session_cap, ctrl._registry.view_cap) == (3, 6)

    def test_a_persisted_change_governs_the_next_duplicate(self) -> None:
        ctrl, app = _make_controller()
        _config_caps(app, (1, 1))
        ctrl = MprController(app)
        source = _add_detached_view(ctrl, _make_result())
        with patch(_BOX):
            assert ctrl.duplicate_view(source, 0) is False
        _config_caps(app, (1, 3))
        with _light_display(ctrl):
            assert ctrl.duplicate_view(source, 0) is True

    def test_settings_applied_callback_path_applies_the_pair(self) -> None:
        ctrl, app = _make_controller()
        _config_caps(app, (2, 5))
        assert ctrl.apply_session_caps() is True
        assert (ctrl._registry.session_cap, ctrl._registry.view_cap) == (2, 5)
        assert ctrl.apply_session_caps() is False  # unchanged: nothing to do

    def test_lowering_caps_evicts_nothing_and_only_blocks_growth(self) -> None:
        ctrl, app = _make_controller()
        views = [_add_detached_view(ctrl, _make_result()) for _ in range(4)]
        _config_caps(app, (1, 1))
        assert ctrl.apply_session_caps() is True
        assert ctrl.detached_view_ids() == views and ctrl._registry.session_count == 4
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result), patch(_BOX) as box:
            ctrl._on_mpr_requested(0, _request(result))
        assert "limit" in box.warning.call_args.args[2]
        # Usage falls below the limit: growth is allowed again.
        for view in views[:-1]:
            ctrl.discard_detached_view(view)
        ctrl.discard_detached_view(views[-1])
        with _build_flow(ctrl, result) as (_v, workers):
            ctrl._on_mpr_requested(0, _request(result))
        assert len(workers) == 1

    def test_already_admitted_pending_builds_are_honored_when_caps_drop(self) -> None:
        ctrl, app = _make_controller()
        result = _result_for("ST", "SE")
        with _build_flow(ctrl, result) as (_v, workers), _light_display(ctrl):
            ctrl._on_mpr_requested(0, _request(result))
            _config_caps(app, (1, 1))
            _add_detached_view(ctrl, _make_result())  # usage now exceeds the lowered cap
            ctrl.apply_session_caps()
            workers[0].finished.connect.call_args_list[0].args[0](result)
        assert ctrl.attached_view_id(0) is not None  # the pending confirmation was honored
        assert ctrl._registry.session_count == 2  # over the new cap, nothing evicted

    def test_malformed_persisted_values_fall_back_to_the_defaults(self, tmp_path: Path) -> None:
        ctrl, app = _make_controller()
        config = ConfigManager(config_dir=tmp_path / "config")
        app.config_manager = config
        assert config.set_mpr_caps(2, 3) is True
        ctrl = MprController(app)
        assert (ctrl._registry.session_cap, ctrl._registry.view_cap) == (2, 3)
        config.config["mpr_session_cap"] = "lots"
        config.config["mpr_view_cap"] = True
        assert ctrl.apply_session_caps() is True
        assert (ctrl._registry.session_cap, ctrl._registry.view_cap) == (8, 16)

    @pytest.mark.parametrize("bad", [None, (0, 4), (5, 3), (True, 9), ("2", 4), (2,), MagicMock()])
    def test_an_unreadable_or_invalid_pair_leaves_the_live_caps_alone(self, bad) -> None:
        ctrl, app = _make_controller()
        ctrl._registry.set_caps(3, 5)
        _config_caps(app, bad)
        assert strict_session_caps(app) is None
        assert refresh_session_caps(ctrl) is False
        assert (ctrl._registry.session_cap, ctrl._registry.view_cap) == (3, 5)

    def test_unchanged_config_does_not_clobber_a_directly_set_registry_value(self) -> None:
        ctrl, app = _make_controller()
        _config_caps(app, (2, 4))
        ctrl = MprController(app)
        ctrl._registry.set_caps(5, 9)
        refresh_session_caps(ctrl)
        assert (ctrl._registry.session_cap, ctrl._registry.view_cap) == (5, 9)

    def test_config_manager_without_caps_api_is_tolerated(self) -> None:
        app = SimpleNamespace(config_manager=object())
        assert strict_session_caps(app) is None
