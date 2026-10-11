"""Engine-slice rollback checks: pending-build cancel and viewer-restore order.

Relocate/attach transfer rollback coverage arrives with the parking slice;
this file keeps the two engine-level contracts: Clear Window cancels a
pending-only build, and the viewer snapshot restores the mode override
before the mouse mode.
"""

from __future__ import annotations

from typing import Any

from mpr_lifecycle_harness import FakeWorker, _make_controller, _register_worker


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


class TestPendingOnlyBuild:
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


class TestSnapshotRestoreOrder:
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
