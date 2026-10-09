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
from core.mpr_session_types import MprCombineState, MprDisplayState
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
    return MprController(app), app


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


class TestPayloadCapture:
    def test_capture_carries_per_pane_display_and_combine(self) -> None:
        ctrl, app = _make_two_pane_controller()
        result = _make_result()
        custom = sigmoid_lut()
        _seed_mpr_pane(app, 0, result, wc=50.0, ww=350.0, user_modified=True,
                       slope=1.0, intercept=-1024.0, inverted=True, lut=custom,
                       combine_enabled=True, combine_mode="mip", combine_count=6)
        _seed_mpr_pane(app, 1, result, wc=70.0, ww=700.0)
        first = ctrl._capture_mpr_payload(0)
        second = ctrl._capture_mpr_payload(1)
        assert first is not None and second is not None
        assert isinstance(first["mpr_combine"], MprCombineState)
        assert (first["mpr_combine"].enabled, first["mpr_combine"].mode,
                first["mpr_combine"].slice_count) == (True, "mip", 6)
        display = first["mpr_display"]
        assert isinstance(display, MprDisplayState)
        assert (display.window_center, display.window_width) == (50.0, 350.0)
        assert display.wl_user_modified is True
        assert (display.rescale_slope, display.rescale_intercept, display.rescale_type) == (1.0, -1024.0, "HU")
        assert display.inverted is True
        assert display.lut is custom
        assert (second["mpr_display"].window_center, second["mpr_display"].window_width) == (70.0, 700.0)
        assert second["mpr_display"].inverted is False

    def test_capture_ignores_focus(self) -> None:
        ctrl, app = _make_two_pane_controller(focused=1)
        result = _make_result()
        _seed_mpr_pane(app, 0, result, wc=51.0, ww=351.0)
        payload = ctrl._capture_mpr_payload(0)
        assert payload is not None
        assert (payload["mpr_display"].window_center, payload["mpr_display"].window_width) == (51.0, 351.0)

    def test_capture_none_when_not_mpr(self) -> None:
        ctrl, _app = _make_two_pane_controller()
        assert ctrl._capture_mpr_payload(0) is None


class TestInstallRestore:
    def test_install_restores_carried_state_without_reset(self) -> None:
        ctrl, app = _make_two_pane_controller(focused=1)
        app.window_level_controls = MagicMock()
        result = _make_result(n_slices=4)
        custom = sigmoid_lut()
        _seed_mpr_pane(app, 0, result, wc=50.0, ww=350.0, user_modified=True,
                       slope=1.0, intercept=-1024.0, inverted=True, lut=custom,
                       combine_enabled=True, combine_mode="mip", combine_count=6)
        payload = ctrl._capture_mpr_payload(0)
        assert payload is not None
        app.subwindow_data[1] = {"current_datasets": []}
        with (
            patch.object(ctrl, "display_mpr_slice"),
            patch.object(ctrl, "_reset_window_level_for_mpr") as reset,
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            assert ctrl._install_mpr_payload_at_subwindow(1, payload) is True
        reset.assert_not_called()
        dest = app.subwindow_managers[1]["view_state_manager"]
        assert (dest.current_window_center, dest.current_window_width) == (50.0, 350.0)
        assert dest.window_level_user_modified is True
        assert dest.rescale_calls == [(1.0, -1024.0, "HU")]
        assert dest.use_rescaled_values is True
        dest_viewer = app.multi_window_layout.get_subwindow(1).image_viewer
        assert dest_viewer.image_inverted is True
        assert get_mpr_lut_override(dest) is custom
        data = app.subwindow_data[1]
        assert (data["mpr_combine_enabled"], data["mpr_combine_mode"],
                data["mpr_combine_slice_count"]) == (True, "mip", 6)
        # Focused pane: shared toolbar follows the carried values with signals
        # blocked, so window_changed handlers cannot snap or clobber them.
        app.window_level_controls.set_window_level.assert_called_once_with(
            50.0, 350.0, block_signals=True, unit="HU"
        )
        app.window_level_controls.set_unit.assert_not_called()
        app.main_window.set_rescale_toggle_state.assert_called_with(True)
        # The carried user-modified flag survives the focused install.
        assert dest.window_level_user_modified is True

    def test_focused_sync_hides_unit_when_not_rescaled(self) -> None:
        ctrl, app = _make_two_pane_controller(focused=1)
        app.window_level_controls = MagicMock()
        result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, result, wc=50.0, ww=350.0, use_rescaled=False)
        payload = ctrl._capture_mpr_payload(0)
        assert payload is not None
        app.subwindow_data[1] = {"current_datasets": []}
        with (
            patch.object(ctrl, "display_mpr_slice"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            assert ctrl._install_mpr_payload_at_subwindow(1, payload) is True
        app.window_level_controls.set_window_level.assert_called_once_with(
            50.0, 350.0, block_signals=True, unit=None
        )
        dest_viewer = app.multi_window_layout.get_subwindow(1).image_viewer
        dest_viewer.set_rescale_toggle_state.assert_called_with(False)

    def test_focused_sync_clears_stale_unit_for_raw_state(self) -> None:
        ctrl, app = _make_two_pane_controller(focused=1)
        app.window_level_controls = MagicMock()
        result = _make_result(n_slices=4)
        _seed_mpr_pane(
            app, 0, result, wc=50.0, ww=350.0, use_rescaled=False,
            slope=None, intercept=None, rtype="",
        )
        payload = ctrl._capture_mpr_payload(0)
        assert payload is not None
        app.subwindow_data[1] = {"current_datasets": []}
        with (
            patch.object(ctrl, "display_mpr_slice"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            assert ctrl._install_mpr_payload_at_subwindow(1, payload) is True
        # Prior toolbar unit (e.g. HU) must not linger on raw state:
        # set_window_level(unit=None) alone does not clear it.
        app.window_level_controls.set_window_level.assert_called_once_with(
            50.0, 350.0, block_signals=True, unit=None
        )
        app.window_level_controls.set_unit.assert_called_once_with(None)

    def test_install_skips_shared_toolbar_when_unfocused(self) -> None:
        ctrl, app = _make_two_pane_controller(focused=0)
        app.window_level_controls = MagicMock()
        result = _make_result(n_slices=4)
        _seed_mpr_pane(app, 0, result, wc=50.0, ww=350.0)
        payload = ctrl._capture_mpr_payload(0)
        assert payload is not None
        app.subwindow_data[1] = {"current_datasets": []}
        with (
            patch.object(ctrl, "display_mpr_slice"),
            patch.object(ctrl, "_reset_window_level_for_mpr") as reset,
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            assert ctrl._install_mpr_payload_at_subwindow(1, payload) is True
        reset.assert_not_called()
        dest = app.subwindow_managers[1]["view_state_manager"]
        assert (dest.current_window_center, dest.current_window_width) == (50.0, 350.0)
        app.window_level_controls.set_window_level.assert_not_called()
        app.main_window.set_rescale_toggle_state.assert_not_called()

    def test_install_legacy_payload_falls_back_to_reset(self) -> None:
        ctrl, app = _make_two_pane_controller()
        result = _make_result(n_slices=4)
        payload = {
            "mpr_result": result,
            "mpr_orientation": "Axial",
            "mpr_slice_index": 0,
            "current_study_uid": "st",
            "current_series_uid": "se",
            "current_datasets": [],
            "mpr_combine_enabled": True,
            "mpr_combine_mode": "mip",
            "mpr_combine_slice_count": 8,
        }
        app.subwindow_data[1] = {"current_datasets": []}
        with (
            patch.object(ctrl, "display_mpr_slice"),
            patch.object(ctrl, "_reset_window_level_for_mpr") as reset,
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            assert ctrl._install_mpr_payload_at_subwindow(1, payload) is True
        reset.assert_called_once()
        data = app.subwindow_data[1]
        assert (data["mpr_combine_mode"], data["mpr_combine_slice_count"]) == ("mip", 8)

    def test_source_pane_series_lut_untouched_by_move(self) -> None:
        ctrl, app = _make_two_pane_controller()
        result = _make_result(n_slices=4)
        custom = sigmoid_lut()
        _seed_mpr_pane(app, 0, result, wc=50.0, ww=350.0, lut=custom)
        payload = ctrl._capture_mpr_payload(0)
        assert payload is not None
        app.subwindow_data[1] = {"current_datasets": []}
        with (
            patch.object(ctrl, "display_mpr_slice"),
            patch.object(ctrl, "_reset_window_level_for_mpr"),
            patch.object(ctrl, "_set_tools_enabled"),
        ):
            assert ctrl._install_mpr_payload_at_subwindow(1, payload) is True
        source = app.subwindow_managers[0]["view_state_manager"]
        assert source.series_defaults["series-id"]["current_lut"] is custom
        assert get_mpr_lut_override(source) is None
        dest = app.subwindow_managers[1]["view_state_manager"]
        assert "current_lut" not in dest.series_defaults.get("series-id", {})
        assert get_mpr_lut_override(dest) is custom


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
