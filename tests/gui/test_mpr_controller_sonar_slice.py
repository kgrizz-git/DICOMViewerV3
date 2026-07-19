"""
Characterize MprController contracts targeted by the Sonar S3776 slices.

Covers display / activate / tear-down / install / overlay helpers from the
first slice, plus save / attach / request / W-L helpers from the finish slice.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
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
        source_volume=volume,  # type: ignore[arg-type]
        interpolation="linear",
        rescale_slope=1.0,
        rescale_intercept=0.0,
    )


def _make_controller(idx: int = 0, *, focused: int = 0) -> tuple[MprController, Any]:
    config = MagicMock()
    config.get_mpr_cache_enabled.return_value = False
    config.clear_mpr_cache_storage.return_value = SimpleNamespace(
        success=True, removed=0, failed=0
    )

    image_viewer = MagicMock()
    image_viewer.scene = MagicMock()
    image_viewer.viewport.return_value = MagicMock()

    subwindow = SimpleNamespace(image_viewer=image_viewer, setFocus=MagicMock())
    layout = MagicMock()
    layout.get_subwindow.return_value = subwindow

    measurement_tool = MagicMock()
    view_state_manager = MagicMock()
    view_state_manager.use_rescaled_values = True
    view_state_manager.get_series_identifier.return_value = "series-id"
    slice_display_manager = MagicMock()
    overlay_manager = MagicMock()
    overlay_manager.should_show_text_overlays.return_value = True
    roi_coordinator = MagicMock()

    app = SimpleNamespace(
        config_manager=config,
        subwindow_data={idx: {}},
        subwindow_managers={
            idx: {
                "measurement_tool": measurement_tool,
                "view_state_manager": view_state_manager,
                "slice_display_manager": slice_display_manager,
                "overlay_manager": overlay_manager,
                "roi_coordinator": roi_coordinator,
            }
        },
        multi_window_layout=layout,
        window_level_controls=None,
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
    return ctrl, app


def test_display_mpr_slice_early_return_when_not_mpr() -> None:
    ctrl, app = _make_controller()
    with patch("gui.mpr_controller.apply_mpr_stack_combine") as combine:
        ctrl.display_mpr_slice(0, 0)
    combine.assert_not_called()
    assert app.subwindow_data[0] == {}


def test_display_mpr_slice_early_return_bad_index() -> None:
    ctrl, app = _make_controller()
    result = _make_result(n_slices=2)
    app.subwindow_data[0] = {"is_mpr": True, "mpr_result": result}
    with patch("gui.mpr_controller.apply_mpr_stack_combine") as combine:
        ctrl.display_mpr_slice(0, 5)
    combine.assert_not_called()


def test_display_mpr_slice_updates_index_and_renders() -> None:
    ctrl, app = _make_controller()
    result = _make_result(n_slices=3)
    app.subwindow_data[0] = {
        "is_mpr": True,
        "mpr_result": result,
        "current_study_uid": "study",
        "current_series_uid": "series",
        "mpr_orientation": "Axial",
        "mpr_combine_enabled": False,
        "mpr_combine_mode": "aip",
        "mpr_combine_slice_count": 4,
    }
    pil = MagicMock()
    raw = np.ones((4, 4), dtype=np.float32)
    with (
        patch("gui.mpr_controller.apply_mpr_stack_combine", return_value=raw) as combine,
        patch.object(ctrl, "_array_to_pil", return_value=pil) as to_pil,
        patch.object(ctrl, "_get_preferred_mpr_window_level", return_value=(40.0, 400.0)),
        patch("gui.mpr_controller.QTimer.singleShot") as single_shot,
    ):
        ctrl.display_mpr_slice(0, 1)

    combine.assert_called_once()
    to_pil.assert_called_once()
    data = app.subwindow_data[0]
    assert data["mpr_slice_index"] == 1
    assert data["current_slice_index"] == 1
    assert data["current_dataset"] is not None
    managers = app.subwindow_managers[0]
    managers["measurement_tool"].set_pixel_spacing.assert_called_once_with(
        result.output_spacing_mm
    )
    managers["slice_display_manager"].display_rois_for_slice.assert_called_once()
    managers["overlay_manager"].create_overlay_items.assert_called_once()
    app._sync_navigation_slider_for_subwindow.assert_called_once_with(0)
    single_shot.assert_called_once()


def test_activate_mpr_sets_state_and_displays_first_slice() -> None:
    ctrl, app = _make_controller()
    result = _make_result()
    app.subwindow_data[0] = {
        "current_dataset": "prior-ds",
        "current_slice_index": 2,
        "current_series_uid": "prior-series",
        "current_study_uid": "prior-study",
        "current_datasets": ["a"],
    }
    with (
        patch.object(ctrl, "display_mpr_slice") as display,
        patch.object(ctrl, "_reset_window_level_for_mpr") as reset_wl,
        patch.object(ctrl, "_set_tools_enabled") as tools,
    ):
        ctrl._activate_mpr(0, result, "Sagittal")

    data = app.subwindow_data[0]
    assert data["is_mpr"] is True
    assert data["mpr_result"] is result
    assert data["mpr_orientation"] == "Sagittal"
    assert data["mpr_slice_index"] == 0
    assert data["mpr_previous_state"]["current_dataset"] == "prior-ds"
    assert data["mpr_previous_state"]["current_slice_index"] == 2
    tools.assert_called_once_with(0, enabled=False)
    reset_wl.assert_called_once()
    display.assert_called_once_with(0, 0)
    app.slice_navigator.set_total_slices.assert_called_once_with(result.n_slices)
    app._sync_intensity_projection_widget_from_mpr_data.assert_called_once_with(data)


def test_activate_mpr_does_not_overwrite_existing_previous_state() -> None:
    ctrl, app = _make_controller()
    result = _make_result()
    prior = {"current_dataset": "kept"}
    app.subwindow_data[0] = {"mpr_previous_state": prior}
    with (
        patch.object(ctrl, "display_mpr_slice"),
        patch.object(ctrl, "_reset_window_level_for_mpr"),
        patch.object(ctrl, "_set_tools_enabled"),
    ):
        ctrl._activate_mpr(0, result, "Axial")
    assert app.subwindow_data[0]["mpr_previous_state"] is prior


def test_tear_down_restores_previous_state() -> None:
    ctrl, app = _make_controller()
    prior_ds = object()
    app.subwindow_data[0] = {
        "is_mpr": True,
        "mpr_result": object(),
        "mpr_orientation": "Axial",
        "mpr_slice_index": 1,
        "mpr_combine_enabled": True,
        "mpr_previous_state": {
            "current_dataset": prior_ds,
            "current_slice_index": 3,
            "current_study_uid": "st",
            "current_series_uid": "se",
            "current_datasets": [prior_ds],
        },
    }
    sdm = MagicMock()
    app.subwindow_managers[0]["slice_display_manager"] = sdm
    with patch.object(ctrl, "_set_tools_enabled") as tools:
        ctrl._tear_down_mpr_at_subwindow(0)

    data = app.subwindow_data[0]
    assert "is_mpr" not in data
    assert "mpr_result" not in data
    assert data["current_dataset"] is prior_ds
    assert data["current_slice_index"] == 3
    tools.assert_called_once_with(0, enabled=True)
    sdm.display_slice.assert_called_once()
    app.series_navigator.set_subwindow_assignments.assert_called_once()


def test_tear_down_clears_view_when_no_previous_state() -> None:
    ctrl, app = _make_controller()
    app.subwindow_data[0] = {"is_mpr": True, "mpr_result": object()}
    with patch.object(ctrl, "_set_tools_enabled"):
        ctrl._tear_down_mpr_at_subwindow(0)
    data = app.subwindow_data[0]
    assert data["current_dataset"] is None
    assert data["current_datasets"] == []
    viewer = app.multi_window_layout.get_subwindow(0).image_viewer
    viewer.scene.clear.assert_called_once()


def test_install_payload_writes_fields_and_displays() -> None:
    ctrl, app = _make_controller()
    result = _make_result(n_slices=4)
    app.subwindow_data[0] = {
        "current_dataset": "old",
        "current_slice_index": 1,
        "current_series_uid": "old-se",
        "current_study_uid": "old-st",
        "current_datasets": [],
    }
    payload = {
        "mpr_result": result,
        "mpr_orientation": "Coronal",
        "mpr_slice_index": 2,
        "current_study_uid": "st",
        "current_series_uid": "se",
        "current_datasets": result.source_volume.source_datasets,
        "mpr_combine_enabled": True,
        "mpr_combine_mode": "mip",
        "mpr_combine_slice_count": 8,
    }
    with (
        patch.object(ctrl, "display_mpr_slice") as display,
        patch.object(ctrl, "_reset_window_level_for_mpr"),
        patch.object(ctrl, "_set_tools_enabled"),
    ):
        ok = ctrl._install_mpr_payload_at_subwindow(0, payload)

    assert ok is True
    data = app.subwindow_data[0]
    assert data["is_mpr"] is True
    assert data["mpr_orientation"] == "Coronal"
    assert data["mpr_slice_index"] == 2
    assert data["mpr_combine_mode"] == "mip"
    assert data["mpr_previous_state"]["current_dataset"] == "old"
    display.assert_called_once_with(0, 2)


def test_install_payload_rejects_empty_result() -> None:
    ctrl, app = _make_controller()
    result = _make_result(n_slices=1)
    # Force empty stack length via a stub
    empty = SimpleNamespace(
        n_slices=0,
        source_volume=result.source_volume,
    )
    app.subwindow_data[0] = {}
    assert ctrl._install_mpr_payload_at_subwindow(0, {"mpr_result": empty}) is False


def test_build_overlay_dataset_sets_geometry_and_strips_location() -> None:
    ctrl, _app = _make_controller()
    result = _make_result(n_slices=2)
    source_uid = result.source_volume.source_datasets[0].SOPInstanceUID
    overlay = ctrl._build_overlay_dataset(result, 1)

    assert overlay.InstanceNumber == 2
    assert float(overlay.SliceThickness) == 1.25
    assert list(overlay.PixelSpacing) == [0.5, 0.5]
    assert list(overlay.ImageOrientationPatient) == [
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
    ]
    assert not hasattr(overlay, "SliceLocation") or overlay.SliceLocation in ("", None)
    assert not hasattr(overlay, "ImagePositionPatient") or overlay.ImagePositionPatient in (
        "",
        None,
    )
    # Source study slice must remain unchanged (deep copy).
    assert result.source_volume.source_datasets[0].InstanceNumber == 7
    assert result.source_volume.source_datasets[0].SOPInstanceUID == source_uid


def test_prompt_save_mpr_rejects_non_mpr_focus() -> None:
    ctrl, app = _make_controller()
    app.get_focused_subwindow_index = MagicMock(return_value=0)
    app.main_window = MagicMock()
    app.subwindow_data[0] = {}
    with patch("gui.mpr_controller.QMessageBox.information") as info:
        ctrl.prompt_save_mpr_as_dicom()
    info.assert_called_once()
    assert "not an MPR" in info.call_args[0][2]


def test_prompt_save_mpr_rejects_empty_stack() -> None:
    ctrl, app = _make_controller()
    app.get_focused_subwindow_index = MagicMock(return_value=0)
    app.main_window = MagicMock()
    empty = SimpleNamespace(n_slices=0)
    app.subwindow_data[0] = {"is_mpr": True, "mpr_result": empty}
    with patch("gui.mpr_controller.QMessageBox.information") as info:
        ctrl.prompt_save_mpr_as_dicom()
    info.assert_called_once()
    assert "No MPR slice stack" in info.call_args[0][2]


def test_attach_floating_mpr_noop_without_payload() -> None:
    ctrl, app = _make_controller()
    ctrl._detached_mpr_payload = None
    with patch.object(ctrl, "_install_mpr_payload_at_subwindow") as install:
        ctrl.attach_floating_mpr(0)
    install.assert_not_called()


def test_attach_floating_mpr_clears_detached_on_success() -> None:
    ctrl, app = _make_controller()
    result = _make_result()
    payload = {"mpr_result": result, "mpr_orientation": "Axial", "mpr_slice_index": 0}
    ctrl._detached_mpr_payload = payload
    activated: list[int] = []
    ctrl.mpr_activated.connect(activated.append)
    with patch.object(ctrl, "_install_mpr_payload_at_subwindow", return_value=True):
        ctrl.attach_floating_mpr(0)
    assert ctrl._detached_mpr_payload is None
    assert activated == [0]
    app.series_navigator.clear_mpr_thumbnail.assert_called_once_with(-1)


def test_attach_floating_mpr_restores_backup_on_install_failure() -> None:
    ctrl, app = _make_controller()
    result = _make_result()
    payload = {"mpr_result": result, "mpr_orientation": "Axial", "mpr_slice_index": 0}
    ctrl._detached_mpr_payload = payload
    app.subwindow_data[0] = {
        "is_mpr": True,
        "mpr_result": result,
        "mpr_orientation": "Old",
        "mpr_slice_index": 1,
        "current_study_uid": "st",
        "current_series_uid": "se",
        "current_datasets": [],
        "mpr_combine_enabled": False,
        "mpr_combine_mode": "aip",
        "mpr_combine_slice_count": 1,
    }
    app.main_window = MagicMock()
    installs: list[Any] = []

    def _install(idx: int, p: dict[str, Any]) -> bool:
        installs.append(p)
        return len(installs) != 1

    with (
        patch.object(ctrl, "_install_mpr_payload_at_subwindow", side_effect=_install),
        patch.object(ctrl, "clear_mpr"),
        patch.object(ctrl, "_capture_mpr_payload", return_value={"backup": True}),
        patch("gui.mpr_controller.QMessageBox.warning") as warn,
    ):
        ctrl.attach_floating_mpr(0)

    assert len(installs) == 2
    assert installs[0] is payload
    assert installs[1] == {"backup": True}
    warn.assert_called_once()
    assert "previous MPR" in warn.call_args[0][2]


def test_on_mpr_requested_errors_when_no_orientation_groups() -> None:
    ctrl, app = _make_controller()
    app.main_window = MagicMock()
    request = SimpleNamespace(datasets=[_source_dataset()], orientation_label="Axial")
    with (
        patch("gui.mpr_controller.get_orientation_groups", return_value=[]),
        patch(
            "gui.mpr_controller.has_slice_location_fallback_available",
            return_value=False,
        ),
        patch("gui.mpr_controller.QMessageBox.critical") as critical,
        patch.object(ctrl, "_activate_mpr") as activate,
    ):
        ctrl._on_mpr_requested(0, request)
    critical.assert_called_once()
    activate.assert_not_called()


def test_on_mpr_requested_activates_from_cache_hit() -> None:
    ctrl, app = _make_controller()
    app.main_window = MagicMock()
    ds = _source_dataset()
    request = SimpleNamespace(
        datasets=[ds],
        orientation_label="Coronal",
        output_spacing_mm=0.5,
        output_thickness_mm=1.0,
        interpolation="linear",
        combine_mode="none",
        slab_thickness_mm=0.0,
        output_plane=SimpleNamespace(normal=np.array([0.0, 1.0, 0.0])),
    )
    result = _make_result(n_slices=2)
    volume = SimpleNamespace(source_datasets=[ds])
    cache = MagicMock()
    cache.load.return_value = (
        result.slices,
        result.slice_stack,
        {
            "output_spacing_mm": result.output_spacing_mm,
            "output_thickness_mm": result.output_thickness_mm,
            "interpolation": "linear",
            "rescale_slope": 1.0,
            "rescale_intercept": 0.0,
            "combine_mode": "none",
            "slab_thickness_mm": 0.0,
        },
    )
    ctrl._cache = cache
    with (
        patch(
            "gui.mpr_controller.get_orientation_groups",
            return_value=[("Axial", [ds])],
        ),
        patch("gui.mpr_controller.MprVolume.from_datasets", return_value=volume),
        patch.object(ctrl, "_activate_mpr") as activate,
        patch("gui.mpr_controller.MprBuilder.create_worker") as create_worker,
    ):
        ctrl._on_mpr_requested(0, request)
    activate.assert_called_once()
    assert activate.call_args[0][0] == 0
    assert activate.call_args[0][2] == "Coronal"
    create_worker.assert_not_called()


def test_reset_window_level_updates_pane_even_when_unfocused() -> None:
    ctrl, app = _make_controller(focused=-1)
    app.window_level_controls = MagicMock()
    app.main_window = MagicMock()
    ds = _source_dataset()
    vsm = app.subwindow_managers[0]["view_state_manager"]
    with (
        patch(
            "core.dicom_rescale.get_rescale_parameters",
            return_value=(1.0, -1024.0, "HU"),
        ),
        patch(
            "core.dicom_window_level.get_window_level_presets_from_dataset",
            return_value=[(40.0, 400.0, True, "Soft Tissue")],
        ),
    ):
        ctrl._reset_window_level_for_mpr(0, ds)

    vsm.set_rescale_parameters.assert_called_once_with(1.0, -1024.0, "HU")
    assert vsm.use_rescaled_values is True
    assert vsm.current_window_center == 40.0
    assert vsm.current_window_width == 400.0
    app.window_level_controls.set_window_level.assert_not_called()
    viewer = app.multi_window_layout.get_subwindow(0).image_viewer
    viewer.set_rescale_toggle_state.assert_called_once_with(True)


def test_reset_window_level_syncs_toolbar_when_focused() -> None:
    ctrl, app = _make_controller(focused=0)
    app.window_level_controls = MagicMock()
    app.main_window = MagicMock()
    ds = _source_dataset()
    with (
        patch(
            "core.dicom_rescale.get_rescale_parameters",
            return_value=(1.0, 0.0, "HU"),
        ),
        patch(
            "core.dicom_window_level.get_window_level_presets_from_dataset",
            return_value=[],
        ),
        patch(
            "core.dicom_window_level.get_window_level_from_dataset",
            return_value=(50.0, 350.0, True),
        ),
    ):
        ctrl._reset_window_level_for_mpr(0, ds)

    app.window_level_controls.set_window_level.assert_called_once()
    args = app.window_level_controls.set_window_level.call_args
    assert args[0][:2] == (50.0, 350.0)
    app.main_window.set_rescale_toggle_state.assert_called_once_with(True)
