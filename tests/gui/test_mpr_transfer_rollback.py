"""Transfer rollback tests for chunk 3.

Render failures with full destination rollback (2-D and occupied-MPR),
invalid targets/payloads leaving state untouched, Clear-Window pending-only
cancellation, and source-closure release. Transfer tests use the real
install/state path with only the pixel-render step stubbed.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from mpr_lifecycle_harness import (
    FakeWorker,
    _make_controller,
    _make_result,
    _register_worker,
    _seed_mpr_pane,
    _signals,
)

from core.lut_catalog import sigmoid_lut
from core.mpr_view_display_state import get_mpr_lut_override


class TestInstallRollback:
    def test_invalid_install_leaves_destination_untouched(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        before = {
            "current_dataset": "ds",
            "current_slice_index": 2,
            "current_series_uid": "se",
            "current_study_uid": "st",
            "current_datasets": [],
        }
        app.subwindow_data[0] = dict(before)
        assert ctrl._install_mpr_payload_at_subwindow(99, {"mpr_result": _make_result()}) is False
        assert ctrl._install_mpr_payload_at_subwindow(0, {"no_result": True}) is False
        empty = _make_result(n_slices=1)
        empty.slices = []
        assert ctrl._install_mpr_payload_at_subwindow(0, {"mpr_result": empty}) is False
        assert app.subwindow_data[0] == before
        assert "mpr_previous_state" not in app.subwindow_data[0]
        assert fired == {"activated": [], "cleared": [], "detached": []}

    def test_failed_relocate_restores_2d_destination_and_source(self) -> None:
        ctrl, app = _make_controller(focused=1)
        fired = _signals(ctrl)
        app.window_level_controls = MagicMock(window_center=40.0, window_width=400.0, unit="HU")
        source = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, source, wc=50.0, ww=350.0, user_modified=True)
        dest_manager = app.subwindow_managers[1]["view_state_manager"]
        dest_manager.current_window_center = 60.0
        dest_manager.current_window_width = 600.0
        dest_manager.rescale_slope = 2.0
        dest_manager.window_level_user_modified = True
        dest_viewer = app.multi_window_layout.get_subwindow(1).image_viewer
        dest_viewer.image_inverted = True
        app.subwindow_data[1] = {
            "current_dataset": "ds2",
            "current_slice_index": 1,
            "current_series_uid": "se2",
            "current_study_uid": "st2",
            "current_datasets": ["ds2"],
        }
        with (
            patch.object(ctrl, "display_mpr_slice", side_effect=RuntimeError("render")),
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            ctrl.relocate_mpr_subwindow(0, 1)
        # Source preserved.
        assert app.subwindow_data[0].get("is_mpr") is True
        assert app.subwindow_data[0]["mpr_result"] is source
        # Destination rolled back to ordinary 2-D.
        dest = app.subwindow_data[1]
        assert dest.get("is_mpr") is not True
        assert "mpr_previous_state" not in dest
        assert dest["current_dataset"] == "ds2"
        assert (dest_manager.current_window_center, dest_manager.current_window_width) == (60.0, 600.0)
        assert dest_manager.rescale_slope == 2.0
        assert dest_manager.window_level_user_modified is True
        assert dest_viewer.image_inverted is True
        app.window_level_controls.set_window_level.assert_called_with(
            40.0, 400.0, block_signals=True, unit="HU"
        )
        assert fired == {"activated": [], "cleared": [], "detached": []}

    def test_failed_relocate_recovers_occupied_mpr(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        source = _make_result(n_slices=4)
        dest_result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, source)
        _seed_mpr_pane(app, 1, dest_result, wc=70.0, ww=700.0)
        with (
            patch.object(
                ctrl, "display_mpr_slice", side_effect=[RuntimeError("render"), None]
            ),
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            ctrl.relocate_mpr_subwindow(0, 1)
        assert app.subwindow_data[0].get("is_mpr") is True
        dest = app.subwindow_data[1]
        assert dest.get("is_mpr") is True
        assert dest["mpr_result"] is dest_result
        dest_manager = app.subwindow_managers[1]["view_state_manager"]
        assert (dest_manager.current_window_center, dest_manager.current_window_width) == (70.0, 700.0)
        assert fired == {"activated": [], "cleared": [], "detached": []}

    def test_failed_attach_keeps_detached_and_restores_dest(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        floating = _make_result(n_slices=4)
        ctrl._detached_mpr_payload = {
            "mpr_result": floating,
            "mpr_orientation": "Axial",
            "mpr_slice_index": 0,
            "mpr_combine_enabled": False,
            "mpr_combine_mode": "aip",
            "mpr_combine_slice_count": 4,
            "current_study_uid": "st",
            "current_series_uid": "se",
            "current_datasets": [],
        }
        dest_result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 1, dest_result)
        with (
            patch.object(
                ctrl, "display_mpr_slice", side_effect=[RuntimeError("render"), None]
            ),
            patch.object(ctrl, "_set_tools_enabled"),
            patch("gui.mpr_controller_transactions.QMessageBox") as box,
        ):
            ctrl.attach_floating_mpr(1)
        assert ctrl._detached_mpr_payload["mpr_result"] is floating
        assert app.subwindow_data[1]["mpr_result"] is dest_result
        box.warning.assert_called_once()
        assert fired["activated"] == []


class TestClearWindowAndClosure:
    def test_clear_window_cancels_pending_only_build(self) -> None:
        from core.study_navigation_handlers import clear_subwindow_content

        ctrl, app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 1, worker)
        app._mpr_controller = ctrl
        app.subwindow_data[1] = {}
        app.focused_subwindow_index = 0
        app.cine_player = None
        clear_subwindow_content(app, 1)
        assert worker.cancel_calls == 1
        assert 1 not in ctrl._workers
        assert app.subwindow_data[1] == {}

    def test_release_for_closed_source(self) -> None:
        ctrl, app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 0, worker)
        result = _make_result()
        _seed_mpr_pane(app, 0, result, study="ST")
        manager = app.subwindow_managers[0]["view_state_manager"]
        manager.series_defaults.setdefault("__mpr__", {})["current_lut"] = sigmoid_lut()
        app.multi_window_layout.get_subwindow(0).image_viewer._mpr_mode_override = True
        ctrl._detached_mpr_payload = {
            "mpr_result": _make_result(),
            "current_study_uid": "ST",
            "current_series_uid": "SE",
        }
        _seed_mpr_pane(app, 1, _make_result(), study="OTHER")

        released = ctrl.release_mpr_for_closed_source("ST", "SE")

        assert released == {"panes": 1, "workers": 1, "detached": 1, "specs": 1}
        assert worker.cancel_calls == 1
        assert ctrl._detached_mpr_payload is None
        assert get_mpr_lut_override(manager) is None
        assert app.multi_window_layout.get_subwindow(0).image_viewer._mpr_mode_override is False
        app.series_navigator.clear_mpr_thumbnail.assert_any_call(0)
        app.series_navigator.clear_mpr_thumbnail.assert_any_call(-1)
        # Other-study pane untouched.
        assert app.subwindow_data[1].get("is_mpr") is True
        # Late callback for the closed source is dropped.
        with patch.object(ctrl, "_activate_mpr") as activate:
            ctrl._on_mpr_build_finished(
                0, worker, 0, ("ST", "SE"), 0, _make_result(), MagicMock(),
                "Axial", MagicMock(),
            )
        activate.assert_not_called()


class FakeViewer:
    """Viewer fake recording inversion/toggle/mode event order."""

    def __init__(self):
        self.events: list[tuple[Any, ...]] = []
        self.image_inverted = False
        self.use_rescaled_values = True
        self.mouse_mode = "select"
        self._mpr_mode_override = False
        self.original_image = None

    def __setattr__(self, name, value):
        if name in ("_mpr_mode_override", "image_inverted", "use_rescaled_values", "mouse_mode"):
            self.__dict__.setdefault("events", []).append((name, value))
        super().__setattr__(name, value)

    def set_mouse_mode(self, mode):
        self.events.append(("set_mouse_mode", mode))
        self.mouse_mode = mode

    def set_rescale_toggle_state(self, value):
        self.events.append(("toggle", bool(value)))

    def set_display_final_image(self, image, preserve_view=False, image_inverted=False):
        self.events.append(("paint", image, preserve_view, image_inverted))
        self.original_image = image
        self.image_inverted = image_inverted


class TestSnapshotCompleteness:
    def test_write_fields_exception_leaves_data_identical(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, result)
        before = dict(app.subwindow_data[1])
        app.subwindow_data[1] = {
            "current_dataset": "ds",
            "current_slice_index": 0,
            "current_series_uid": "se",
            "current_study_uid": "st",
            "current_datasets": [],
        }
        before = dict(app.subwindow_data[1])
        payload = ctrl._capture_mpr_payload(0)
        assert payload is not None
        with patch.object(
            ctrl, "_install_write_payload_fields", side_effect=RuntimeError("write")
        ):
            assert ctrl._install_mpr_payload_at_subwindow(1, payload) is False
        assert app.subwindow_data[1] == before
        assert "mpr_previous_state" not in app.subwindow_data[1]
        assert fired["activated"] == []

    def test_direct_restore_preserves_state_without_rendering(self) -> None:
        ctrl, app = _make_controller()
        source = _make_result(n_slices=4)
        dest_result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, source)
        _seed_mpr_pane(app, 1, dest_result, wc=70.0, ww=700.0, user_modified=True)
        seen: list[tuple[float, float]] = []
        calls = {"n": 0}

        def counting_probe(idx, slice_index):
            calls["n"] += 1
            manager = app.subwindow_managers[idx]["view_state_manager"]
            seen.append(
                (manager.current_window_center, manager.current_window_width)
            )
            if calls["n"] == 1:
                raise RuntimeError("render")

        with (
            patch.object(ctrl, "display_mpr_slice", side_effect=counting_probe),
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            ctrl.relocate_mpr_subwindow(0, 1)
        # The failed render sees source state; rollback restores values and
        # last-good pixels without re-running the failed renderer.
        assert seen[0] == (40.0, 400.0)
        assert len(seen) == 1  # rollback bypasses the failed renderer
        manager = app.subwindow_managers[1]["view_state_manager"]
        assert (manager.current_window_center, manager.current_window_width) == (70.0, 700.0)
        assert app.subwindow_data[1]["mpr_result"] is dest_result

    def test_repeated_render_failure_preserves_original_mpr(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        source = _make_result(n_slices=4)
        dest_result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, source)
        _seed_mpr_pane(app, 1, dest_result, wc=70.0, ww=700.0)
        with (
            patch.object(ctrl, "display_mpr_slice", side_effect=RuntimeError("render")),
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            ctrl.relocate_mpr_subwindow(0, 1)
        # Even a persistent render failure keeps the original MPR intact.
        dest = app.subwindow_data[1]
        assert dest.get("is_mpr") is True
        assert dest["mpr_result"] is dest_result
        assert dest["mpr_slice_index"] == 1
        assert app.subwindow_data[0].get("is_mpr") is True
        assert fired == {"activated": [], "cleared": [], "detached": []}

    def test_late_banner_failure_restores_mpr_picture(self) -> None:
        ctrl, app = _make_controller()
        fired = _signals(ctrl)
        source = _make_result(n_slices=4)
        dest_result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, source)
        _seed_mpr_pane(app, 1, dest_result, wc=70.0, ww=700.0)
        dest_viewer = app.multi_window_layout.get_subwindow(1).image_viewer
        dest_viewer.original_image = "frame-70"

        def painting_display(idx, slice_index):
            manager = app.subwindow_managers[idx]["view_state_manager"]
            dest_viewer.original_image = (
                f"frame-{manager.current_window_center:g}"
            )

        with (
            patch.object(ctrl, "display_mpr_slice", side_effect=painting_display),
            patch.object(ctrl, "_set_tools_enabled"),
            patch.object(
                ctrl, "_apply_mpr_banner",
                side_effect=[RuntimeError("banner"), None],
            ),
        ):
            ctrl.relocate_mpr_subwindow(0, 1)
        # The failed install painted frame-40 first; rollback restored values
        # and re-rendered, so the viewer shows the destination's own frame.
        assert dest_viewer.original_image == "frame-70"
        dest = app.subwindow_data[1]
        assert dest.get("is_mpr") is True
        assert dest["mpr_result"] is dest_result
        assert app.subwindow_data[0].get("is_mpr") is True
        assert fired == {"activated": [], "cleared": [], "detached": []}

    def test_unfocused_rollback_leaves_shared_controls_untouched(self) -> None:
        ctrl, app = _make_controller(focused=0)
        app.window_level_controls = MagicMock(window_center=40.0, window_width=400.0, unit="HU")
        app.main_window = MagicMock()
        source = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, source)
        app.subwindow_data[1] = {
            "current_dataset": "ds",
            "current_slice_index": 0,
            "current_series_uid": "se",
            "current_study_uid": "st",
            "current_datasets": [],
        }
        with (
            patch.object(ctrl, "display_mpr_slice", side_effect=RuntimeError("render")),
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            ctrl.relocate_mpr_subwindow(0, 1)
        app.window_level_controls.set_window_level.assert_not_called()
        app.window_level_controls.set_unit.assert_not_called()
        app.main_window.set_rescale_toggle_state.assert_not_called()

    def test_mode_override_restores_before_mouse_mode(self) -> None:
        from gui.mpr_controller_transactions import _restore_viewer_snapshot

        viewer = FakeViewer()
        viewer._mpr_mode_override = True
        viewer.mouse_mode = "pan"
        saved = {
            "inverted": False,
            "rescale_toggle": True,
            "mouse_mode": "select",
            "mode_override": False,
        }
        _restore_viewer_snapshot(lambda _idx: viewer, 0, saved)
        kinds = [kind for kind, _value in viewer.events]
        assert kinds.index("_mpr_mode_override") < kinds.index("set_mouse_mode")
        assert viewer.mouse_mode == "select"
        assert viewer._mpr_mode_override is False


class TestTransferTargetValidation:
    def test_invalid_destination_cancels_nothing_and_keeps_focus(self) -> None:
        ctrl, app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 1, worker)
        app.subwindow_data[1] = {"current_datasets": []}
        layout = app.multi_window_layout
        layout.get_subwindow = MagicMock(return_value=None)
        ctrl._detached_mpr_payload = {"mpr_result": _make_result()}
        with patch("gui.mpr_controller_transactions.QMessageBox") as box:
            ctrl.attach_floating_mpr(1)
        assert worker.cancel_calls == 0
        assert 1 in ctrl._workers
        assert ctrl._detached_mpr_payload is not None
        box.warning.assert_called_once()

    def test_invalid_destination_cancels_nothing(self) -> None:
        ctrl, app = _make_controller()
        worker = FakeWorker()
        _register_worker(ctrl, 0, worker)
        result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, result)
        app.subwindow_data[1] = {"current_datasets": []}
        with patch("gui.mpr_controller_transactions.QMessageBox"):
            ctrl.relocate_mpr_subwindow(0, 99)
        assert worker.cancel_calls == 0
        assert app.subwindow_data[0].get("is_mpr") is True


class TestRollbackFramePreservation:
    def test_failed_2d_install_repaints_original_frame(self) -> None:
        from gui.mpr_controller_transactions import restore_failed_install

        ctrl, app = _make_controller()
        viewer = FakeViewer()
        viewer.original_image = "old-frame"
        viewer.image_inverted = True
        panes = {0: SimpleNamespace(image_viewer=viewer, setFocus=MagicMock())}

        def get_viewer(i):
            pane = panes.get(i)
            assert pane is not None
            return pane.image_viewer
        manager = app.subwindow_managers[0]["view_state_manager"]
        manager.current_window_center = 60.0
        manager.current_window_width = 600.0
        app.subwindow_data[0] = {
            "current_dataset": "ds",
            "current_slice_index": 0,
            "current_series_uid": "se",
            "current_study_uid": "st",
            "current_datasets": [],
            "unrelated_key": "kept",
        }
        from gui.mpr_controller_transactions import capture_destination_snapshot

        snapshot = capture_destination_snapshot(app, get_viewer, 0)
        # Simulate a failed install that painted new pixels and 2-D state.
        viewer.original_image = "new-frame"
        app.subwindow_data[0]["is_mpr"] = True

        assert restore_failed_install(ctrl, 0, snapshot, get_viewer) is True

        paints = [e for e in viewer.events if e[0] == "paint"]
        assert paints, "rollback must repaint"
        assert paints[-1][1] == "old-frame"
        assert paints[-1][3] is True
        assert viewer.original_image == "old-frame"
        assert app.subwindow_data[0]["unrelated_key"] == "kept"
        assert app.subwindow_data[0].get("is_mpr") is not True

    def test_rollback_redraw_failure_is_explicit(self) -> None:
        from gui.mpr_controller_transactions import restore_failed_install

        ctrl, app = _make_controller()
        app.subwindow_data[0] = {
            "current_dataset": "ds",
            "current_slice_index": 0,
            "current_series_uid": "se",
            "current_study_uid": "st",
            "current_datasets": [],
        }
        from gui.mpr_controller_transactions import capture_destination_snapshot

        original_viewer = ctrl._get_image_viewer(0)
        original_viewer.original_image = "old-frame"
        snapshot = capture_destination_snapshot(app, ctrl._get_image_viewer, 0)
        broken = MagicMock()
        broken.set_display_final_image.side_effect = RuntimeError("paint")
        app.multi_window_layout.get_subwindow = lambda _i: SimpleNamespace(
            image_viewer=broken, setFocus=MagicMock()
        )

        assert restore_failed_install(ctrl, 0, snapshot, ctrl._get_image_viewer) is False
