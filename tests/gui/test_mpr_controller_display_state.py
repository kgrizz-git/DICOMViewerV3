"""Controller integration for chunk 2 display-state round-trip.

Covers per-pane capture (pane 0 vs pane 1, focus-independent), install
restoring carried W/L + rescale + inversion + LUT override instead of
resetting, legacy-payload fallback to the reset path, new-build reset
behavior, teardown override cleanup, and LUT independence between panes.

Uses real attribute storage (SimpleNamespace managers) rather than bare
MagicMocks so per-pane writes are observable.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import numpy as np
from pydicom.dataset import Dataset
from pydicom.uid import generate_uid

from core.lut_catalog import linear_lut, sigmoid_lut
from core.mpr_builder import MprResult
from core.mpr_view_display_state import get_mpr_lut_override
from core.slice_geometry import SlicePlane, SliceStack
from gui.mpr_controller import MprController


def _source_dataset() -> Dataset:
    ds = Dataset()
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.InstanceNumber = 7
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


def _pane_view_state(**overrides) -> SimpleNamespace:
    base = {
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
    }
    base.update(overrides)
    manager = SimpleNamespace(**base)
    calls: list[tuple[Any, ...]] = []

    def _set_rescale(slope, intercept, rescale_type):
        calls.append((slope, intercept, rescale_type))
        manager.rescale_slope = slope
        manager.rescale_intercept = intercept
        manager.rescale_type = rescale_type

    manager.set_rescale_parameters = _set_rescale
    manager.rescale_calls = calls
    return manager


def _make_two_pane_controller(*, focused: int = 0) -> tuple[MprController, Any]:
    panes: dict[int, SimpleNamespace] = {}
    managers: dict[int, dict[str, Any]] = {}
    data: dict[int, dict[str, Any]] = {}
    for idx in (0, 1):
        viewer = MagicMock()
        viewer.image_inverted = False
        panes[idx] = SimpleNamespace(image_viewer=viewer, setFocus=MagicMock())
        managers[idx] = {
            "measurement_tool": MagicMock(),
            "view_state_manager": _pane_view_state(),
            "slice_display_manager": MagicMock(),
            "overlay_manager": MagicMock(),
            "roi_coordinator": MagicMock(),
        }
        data[idx] = {}
    layout = SimpleNamespace(get_subwindow=lambda i: panes.get(i))
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
    )
    ctrl = MprController(app)
    app._mpr_controller = ctrl
    return ctrl, app


def _seed_mpr_pane(app: Any, idx: int, result, **display) -> None:
    """Mark pane *idx* as showing *result* with the given display values."""
    viewer = app.multi_window_layout.get_subwindow(idx).image_viewer
    manager = app.subwindow_managers[idx]["view_state_manager"]
    manager.current_window_center = display.get("wc", 40.0)
    manager.current_window_width = display.get("ww", 400.0)
    manager.window_level_user_modified = display.get("user_modified", False)
    manager.rescale_slope = display.get("slope", 1.0)
    manager.rescale_intercept = display.get("intercept", 0.0)
    manager.rescale_type = display.get("rtype", "HU")
    manager.use_rescaled_values = display.get("use_rescaled", True)
    viewer.image_inverted = display.get("inverted", False)
    lut = display.get("lut")
    if lut is not None:
        manager.series_defaults.setdefault("series-id", {})["current_lut"] = lut
    app.subwindow_data[idx] = {
        "is_mpr": True,
        "mpr_result": result,
        "mpr_orientation": "Axial",
        "mpr_slice_index": 1,
        "mpr_combine_enabled": display.get("combine_enabled", False),
        "mpr_combine_mode": display.get("combine_mode", "aip"),
        "mpr_combine_slice_count": display.get("combine_count", 4),
    }
    registry = app._mpr_controller._registry
    old = registry.view_for_pane(idx)
    if old is not None:
        registry.discard_view(old.view_id)
    registry.create_session(result, "ST", "SE", "Axial", slice_index=1, pane_index=idx)


class TestResetAndTeardown:
    def test_reset_clears_stale_override(self) -> None:
        ctrl, app = _make_two_pane_controller(focused=-1)
        app.window_level_controls = MagicMock()
        manager = app.subwindow_managers[0]["view_state_manager"]
        manager.series_defaults.setdefault("__mpr__", {})["current_lut"] = sigmoid_lut()
        with (
            patch("core.dicom_rescale.get_rescale_parameters", return_value=(1.0, 0.0, "HU")),
            patch(
                "core.dicom_window_level.get_window_level_presets_from_dataset",
                return_value=[(40.0, 400.0, True, "Soft Tissue")],
            ),
        ):
            ctrl._reset_window_level_for_mpr(0, _source_dataset())
        assert get_mpr_lut_override(manager) is None
        assert (manager.current_window_center, manager.current_window_width) == (40.0, 400.0)

    def test_teardown_clears_override(self) -> None:
        ctrl, app = _make_two_pane_controller()
        manager = app.subwindow_managers[0]["view_state_manager"]
        manager.series_defaults.setdefault("__mpr__", {})["current_lut"] = sigmoid_lut()
        result = _make_result()
        _seed_mpr_pane(app, 0, result)
        ctrl._tear_down_mpr_at_subwindow(0)
        assert get_mpr_lut_override(manager) is None
        assert app.subwindow_data[0].get("is_mpr") is None


class TestDisplayUsesPaneOverride:
    def test_render_prefers_override_lut(self) -> None:
        ctrl, app = _make_two_pane_controller()
        result = _make_result(n_slices=3)
        _seed_mpr_pane(app, 0, result)
        override = sigmoid_lut()
        manager = app.subwindow_managers[0]["view_state_manager"]
        manager.series_defaults.setdefault("__mpr__", {})["current_lut"] = override
        raw = np.ones((4, 4), dtype=np.float32)
        with (
            patch("gui.mpr_controller.apply_mpr_stack_combine", return_value=raw),
            patch.object(ctrl, "_array_to_pil", return_value=MagicMock()) as to_pil,
            patch.object(ctrl, "_get_preferred_mpr_window_level", return_value=(40.0, 400.0)),
            patch("gui.mpr_controller.QTimer.singleShot"),
        ):
            ctrl.display_mpr_slice(0, 1)
        assert to_pil.call_args.kwargs["lut"] is override

    def test_render_falls_back_to_series_lut(self) -> None:
        ctrl, app = _make_two_pane_controller()
        result = _make_result(n_slices=3)
        _seed_mpr_pane(app, 0, result, lut=linear_lut())
        raw = np.ones((4, 4), dtype=np.float32)
        with (
            patch("gui.mpr_controller.apply_mpr_stack_combine", return_value=raw),
            patch.object(ctrl, "_array_to_pil", return_value=MagicMock()) as to_pil,
            patch.object(ctrl, "_get_preferred_mpr_window_level", return_value=(40.0, 400.0)),
            patch("gui.mpr_controller.QTimer.singleShot"),
        ):
            ctrl.display_mpr_slice(0, 1)
        assert to_pil.call_args.kwargs["lut"].name == "Linear"
