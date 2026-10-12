"""Shared fakes for MPR lifecycle tests (chunk 3).

Fake native workers, two-pane controller harness, and MPR seeding used by
both the worker-fencing and transfer-rollback suites. Not a test module
(filenames not starting with ``test_`` are not collected).
"""


from __future__ import annotations

import warnings
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import numpy as np
from pydicom.dataset import Dataset
from pydicom.uid import generate_uid

from core.mpr_builder import MprResult
from core.slice_geometry import SlicePlane, SliceStack
from gui.mpr_controller import MprController


def _source_dataset() -> Dataset:
    ds = Dataset()
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.InstanceNumber = 3
    ds.Modality = "CT"
    ds.SliceThickness = 2.0
    ds.PixelSpacing = [1.0, 1.0]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.ImagePositionPatient = [0.0, 0.0, 0.0]
    ds.SliceLocation = 0.0
    return ds


def _make_result(*, n_slices: int = 3) -> MprResult:
    source_ds = _source_dataset()
    slices = [np.zeros((4, 4), dtype=np.float32) + float(i) for i in range(n_slices)]
    planes = [
        SlicePlane(
            np.array([0.0, 0.0, float(i)], dtype=float),
            np.array([1.0, 0.0, 0.0], dtype=float),
            np.array([0.0, 1.0, 0.0], dtype=float),
            0.5,
            0.5,
        )
        for i in range(n_slices)
    ]
    stack = SliceStack(
        planes=planes,
        original_indices=list(range(n_slices)),
        stack_normal=np.array([0.0, 0.0, 1.0], dtype=float),
        positions=[float(i) for i in range(n_slices)],
        slice_thickness=1.25,
    )
    volume = SimpleNamespace(source_datasets=[source_ds])
    return MprResult(
        slices=slices,
        slice_stack=stack,
        output_spacing_mm=(0.5, 0.5),
        output_thickness_mm=1.25,
        source_volume=cast(Any, volume),
        interpolation="linear",
        rescale_slope=1.0,
        rescale_intercept=0.0,
    )


class FakeWorker:
    """Native-worker stand-in with observable cancel/quit/termination."""

    progress: Any = None
    error: Any = None

    def __init__(self, *, finished: bool = False):
        self.cancel_calls = 0
        self.quit_calls = 0
        self.start_calls: list[bool] = []
        self._finished = finished
        self.finished = MagicMock()

    def cancel(self) -> None:
        self.cancel_calls += 1

    def quit(self) -> None:
        self.quit_calls += 1

    def start(self) -> None:
        self.start_calls.append(True)

    def isFinished(self) -> bool:
        return self._finished

    def terminate_thread(self) -> None:
        """Simulate actual native termination, firing retained callbacks."""
        self._finished = True
        for args, _kwargs in self.finished.connect.call_args_list:
            args[0]()


def _pane_view_state(**overrides) -> SimpleNamespace:
    base: dict[str, Any] = {
        "current_window_center": 40.0,
        "current_window_width": 400.0,
        "window_level_user_modified": False,
        "use_rescaled_values": True,
        "rescale_slope": 1.0,
        "rescale_intercept": 0.0,
        "rescale_type": "HU",
        "series_defaults": {},
        "current_series_identifier": "series-id",
        "set_current_data_context": MagicMock(),
        "set_current_series_identifier": MagicMock(),
        "set_rescale_parameters": MagicMock(),
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_controller(*, focused: int = 0, pane_count: int = 2) -> tuple[MprController, Any]:
    panes: dict[int, SimpleNamespace] = {}
    managers: dict[int, dict[str, Any]] = {}
    data: dict[int, dict[str, Any]] = {}
    for idx in range(pane_count):
        viewer = MagicMock()
        viewer.image_inverted = False
        viewer.use_rescaled_values = True
        viewer.mouse_mode = "select"
        viewer._mpr_mode_override = False
        panes[idx] = SimpleNamespace(image_viewer=viewer, setFocus=MagicMock())
        managers[idx] = {
            "measurement_tool": MagicMock(),
            "view_state_manager": _pane_view_state(),
            "slice_display_manager": MagicMock(),
            "overlay_manager": MagicMock(),
            "roi_coordinator": MagicMock(),
        }
        data[idx] = {}
    layout = SimpleNamespace(
        get_subwindow=lambda i: panes.get(i), get_all_subwindows=lambda: list(panes.values())
    )
    app = SimpleNamespace(
        config_manager=MagicMock(),
        subwindow_data=data,
        subwindow_managers=managers,
        multi_window_layout=layout,
        window_level_controls=None,
        main_window=MagicMock(),
        focused_subwindow_index=focused,
        current_studies={},
        current_dataset=None,
        current_slice_index=0,
        current_study_uid="",
        current_series_uid="",
        current_datasets=[],
        slice_navigator=MagicMock(),
        series_navigator=MagicMock(),
        dialog_coordinator=MagicMock(),
        _sync_navigation_slider_for_subwindow=MagicMock(),
        _sync_intensity_projection_widget_from_mpr_data=MagicMock(),
        _get_subwindow_assignments=MagicMock(return_value={}),
        _refresh_window_slot_map_widgets=MagicMock(),
        _slice_location_line_coordinator=MagicMock(),
        _reset_fusion_handler_for_subwindow=MagicMock(),
    )
    ctrl = MprController(app)
    app._mpr_controller = ctrl  # real app exposes the controller here
    return ctrl, app


def _register_pane_view(
    ctrl: MprController, idx: int, result, study: str = "ST", series: str = "SE",
    orientation: str = "Axial", slice_index: int = 1,
) -> int:
    """Give pane *idx* a registry session+view for *result*; returns the view ID.

    Replaces any view already attached to the pane (test re-seeding) without
    going through admission, mirroring what a completed activation leaves.
    """
    old = ctrl._registry.view_for_pane(idx)
    if old is not None:
        ctrl._registry.discard_view(old.view_id)
    _sid, view_id = ctrl._registry.create_session(
        result, study, series, orientation, slice_index=slice_index, pane_index=idx
    )
    return view_id


def _add_detached_view(
    ctrl: MprController, result, study: str = "ST", series: str = "SE",
    orientation: str = "Axial", slice_index: int = 0,
) -> int:
    """Register an independent session whose only view is detached; returns its view ID."""
    _sid, view_id = ctrl._registry.create_session(
        result, study, series, orientation, slice_index=slice_index
    )
    return view_id


def _seed_mpr_pane(app: Any, idx: int, result, study: str = "ST", **display) -> None:
    viewer = app.multi_window_layout.get_subwindow(idx).image_viewer
    manager = app.subwindow_managers[idx]["view_state_manager"]
    manager.current_window_center = display.get("wc", 40.0)
    manager.current_window_width = display.get("ww", 400.0)
    manager.window_level_user_modified = display.get("user_modified", False)
    viewer.image_inverted = display.get("inverted", False)
    app.subwindow_data[idx] = {
        "is_mpr": True,
        "mpr_result": result,
        "mpr_orientation": "Axial",
        "mpr_slice_index": 1,
        "mpr_source_dataset": result.source_volume.source_datasets[0],
        "current_study_uid": study,
        "current_series_uid": "SE",
        "current_datasets": result.source_volume.source_datasets,
        "mpr_combine_enabled": False,
        "mpr_combine_mode": "aip",
        "mpr_combine_slice_count": 4,
        # Real MPR panes always carry their pre-MPR 2-D state for teardown.
        "mpr_previous_state": {
            "current_dataset": "prior-ds",
            "current_slice_index": 0,
            "current_series_uid": "PRIOR-SE",
            "current_study_uid": study,
            "current_datasets": ["prior-ds"],
        },
    }
    ctrl = getattr(app, "_mpr_controller", None)
    if ctrl is not None:
        _register_pane_view(ctrl, idx, result, study)


def _register_worker(ctrl: MprController, idx: int, worker: Any) -> None:
    """Register a fake native worker (typed dict needs a cast for fakes)."""
    ctrl._workers[idx] = cast(Any, worker)


def _tile_events(ctrl: MprController) -> list[frozenset[int]]:
    """Record every ``mpr_tiles_changed`` emission (one per controller transaction)."""
    events: list[frozenset[int]] = []
    ctrl.mpr_tiles_changed.connect(events.append)
    return events


def _signals(ctrl: MprController) -> dict[str, list[Any]]:
    fired: dict[str, list[Any]] = {"activated": [], "cleared": [], "detached": []}
    ctrl.mpr_activated.connect(fired["activated"].append)
    ctrl.mpr_cleared.connect(fired["cleared"].append)
    ctrl.mpr_detached.connect(fired["detached"].append)
    return fired


# ---------------------------------------------------------------------------
# Build-flow and registry helpers (chunk 4: live session ownership)
# ---------------------------------------------------------------------------


def _result_for(study: str, series: str, *, n_slices: int = 3):
    """Synthetic result whose source dataset carries the given study/series."""
    result = _make_result(n_slices=n_slices)
    dataset = result.source_volume.source_datasets[0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)  # short labels are not valid UIDs
        dataset.StudyInstanceUID = study
        dataset.SeriesInstanceUID = series
    return result


@contextmanager
def _light_display(ctrl: MprController):
    """Skip real rendering; activation/install bookkeeping still runs."""
    with (
        patch.object(ctrl, "display_mpr_slice") as display,
        patch.object(ctrl, "_set_tools_enabled"),
        patch.object(ctrl, "_reset_window_level_for_mpr"),
    ):
        yield display


def _request(result) -> SimpleNamespace:
    dataset = result.source_volume.source_datasets[0]
    return SimpleNamespace(
        orientation_label="Axial", output_spacing_mm=0.5, output_thickness_mm=1.0,
        interpolation="linear", output_plane=SimpleNamespace(normal=np.array([0.0, 0.0, 1.0])),
        combine_mode="none", slab_thickness_mm=0.0, datasets=[dataset],
    )


@contextmanager
def _build_flow(ctrl: MprController, result, workers: list[FakeWorker] | None = None):
    """Drive ``_on_mpr_requested`` with a fake volume and native worker."""
    dataset = result.source_volume.source_datasets[0]
    created: list[FakeWorker] = workers if workers is not None else []

    def _make_worker(**_kwargs: Any) -> FakeWorker:
        worker = FakeWorker()
        worker.progress = MagicMock()
        worker.error = MagicMock()
        created.append(worker)
        return worker

    with (
        patch.object(ctrl, "_mpr_request_resolve_datasets", return_value=([dataset], False)),
        patch.object(ctrl, "_mpr_request_build_volume", return_value=result.source_volume) as volume,
        patch("gui.mpr_controller.MprBuilder.create_worker", side_effect=_make_worker),
        patch("gui.mpr_controller.QProgressDialog"),
    ):
        yield volume, created


def _finish(worker: FakeWorker, result) -> None:
    """Deliver the worker's queued ``finished`` callback."""
    worker.finished.connect.call_args_list[0].args[0](result)


def _fail(worker: FakeWorker, message: str) -> None:
    worker.error.connect.call_args_list[0].args[0](message)


def _counts(ctrl: MprController) -> tuple[int, int, int, int]:
    reg = ctrl._registry
    return reg.session_count, reg.view_count, reg.pending_session_count, reg.pending_view_count


# ---------------------------------------------------------------------------
# Linked scrolling world: real controller + coordinator + navigator + cine
# ---------------------------------------------------------------------------


def _native_series(n: int, study: str = "NST", series: str = "NSE") -> list[Dataset]:
    """A native axial series whose slice *i* lies at z = i (matches ``_make_result`` planes)."""
    datasets = []
    for i in range(n):
        ds = _source_dataset()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)  # short labels are not valid UIDs
            ds.StudyInstanceUID = study
            ds.SeriesInstanceUID = series
        ds.InstanceNumber = i + 1
        ds.ImagePositionPatient = [0.0, 0.0, float(i)]
        ds.SliceLocation = float(i)
        ds.SliceThickness = 1.0
        ds.Rows = ds.Columns = 4
        datasets.append(ds)
    return datasets


def _seed_native_pane(app: Any, idx: int, datasets: list[Dataset], current: int = 0) -> None:
    app.subwindow_data[idx] = {
        "current_dataset": datasets[current],
        "current_slice_index": current,
        "current_series_uid": str(datasets[0].SeriesInstanceUID),
        "current_study_uid": str(datasets[0].StudyInstanceUID),
        "current_datasets": datasets,
    }


class LinkWorld(SimpleNamespace):
    """Real controller, slice navigator, cine player and global sync coordinator."""

    ctrl: MprController
    app: Any
    nav: Any
    cine: Any
    coord: Any

    def focus(self, idx: int) -> None:
        """Focus pane *idx* and point the shared navigator at its position (as the app does)."""
        data = self.app.subwindow_data[idx]
        self.app.focused_subwindow_index = idx
        total = len(data["mpr_result"].slices) if data.get("is_mpr") else len(data["current_datasets"])
        self.nav.blockSignals(True)
        self.nav.set_total_slices(total)
        self.nav.current_slice_index = int(data.get("mpr_slice_index", data.get("current_slice_index", 0)))
        self.nav.blockSignals(False)

    def live(self, idx: int) -> int:
        return int(self.app.subwindow_data[idx]["mpr_slice_index"])

    def redraws(self) -> dict[int, int]:
        """Panes redrawn so far (pane -> count) since the spy was installed."""
        counts: dict[int, int] = {}
        for call in self.display_spy.call_args_list:
            counts[call.args[0]] = counts.get(call.args[0], 0) + 1
        return counts


def _make_link_world(*, pane_count: int = 5, n_slices: int = 12) -> LinkWorld:
    """Panes 0/1: MPR views of ONE session (linked when ``link`` is used); others native.

    The shared navigator, a real ``CinePlayer`` (linear MPR mode), a real
    ``SliceSyncCoordinator`` and the real ``on_slice_changed`` are wired the way
    the app wires them, so wheel/keys/slider/cine all travel the production path.
    """
    from core.cine_app_facade import CineAppFacade
    from core.slice_display_handlers import on_slice_changed
    from core.slice_sync_coordinator import SliceSyncCoordinator
    from gui.cine_player import CinePlayer
    from gui.slice_navigator import SliceNavigator

    ctrl, app = _make_controller(pane_count=pane_count)
    nav = SliceNavigator()
    app.slice_navigator = nav
    app.cine_player = CinePlayer(nav, lambda: nav.total_slices, lambda: nav.current_slice_index)
    app.cine_player.set_use_linear_cine_navigation(True)
    app.cine_controls_widget = MagicMock()
    app.image_viewer = MagicMock()
    app._slice_location_line_coordinator = MagicMock()
    coord = SliceSyncCoordinator(app)
    app._slice_sync_coordinator = coord
    app.current_studies = {}
    facade = CineAppFacade(app)
    app.cine_app_facade = facade
    nav.slice_changed.connect(lambda i: on_slice_changed(app, i))
    nav.slice_changed.connect(facade.on_manual_slice_navigation)
    app.cine_player.frame_advance_requested.connect(facade.on_cine_frame_advance)
    world = LinkWorld(ctrl=ctrl, app=app, nav=nav, cine=app.cine_player, coord=coord)
    world.n_slices = n_slices
    world.display_spy = None
    return world


def _spy_redraws(world: LinkWorld):
    """Count ``display_mpr_slice`` calls (real redraw still runs)."""
    spy = patch.object(world.ctrl, "display_mpr_slice", wraps=world.ctrl.display_mpr_slice)
    world.display_spy = spy.start()
    return spy
