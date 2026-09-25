"""The MPR render path forwards the source series' polarity to the PIL builder.

Unit tests for ``array_to_pil`` prove the inversion itself; this pins the wiring, which is the
part that silently breaks when a new render path is added.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from pydicom.dataset import Dataset
from pydicom.uid import generate_uid

from core.mpr_builder import MprResult
from core.mpr_view_math import array_to_pil
from core.slice_geometry import SlicePlane, SliceStack
from gui.mpr_controller import MprController


def _source_dataset() -> Dataset:
    ds = Dataset()
    ds.StudyInstanceUID = generate_uid()
    ds.SeriesInstanceUID = generate_uid()
    ds.SOPInstanceUID = generate_uid()
    ds.InstanceNumber = 1
    ds.Modality = "CR"
    ds.SliceThickness = 2.0
    ds.PixelSpacing = [1.0, 1.0]
    ds.ImageOrientationPatient = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ds.ImagePositionPatient = [0.0, 0.0, 0.0]
    ds.SliceLocation = 0.0
    return ds


def _make_result(photometric_interpretation: str, n_slices: int = 3) -> MprResult:
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
    return MprResult(
        slices=slices,
        slice_stack=stack,
        output_spacing_mm=(0.5, 0.5),
        output_thickness_mm=1.25,
        source_volume=SimpleNamespace(source_datasets=[_source_dataset()]),  # type: ignore[arg-type]
        interpolation="linear",
        rescale_slope=1.0,
        rescale_intercept=0.0,
        photometric_interpretation=photometric_interpretation,
    )


def _make_controller() -> tuple[MprController, Any]:
    config = MagicMock()
    config.get_mpr_cache_enabled.return_value = False

    image_viewer = MagicMock()
    image_viewer.scene = MagicMock()
    image_viewer.viewport.return_value = MagicMock()
    subwindow = SimpleNamespace(image_viewer=image_viewer, setFocus=MagicMock())
    layout = MagicMock()
    layout.get_subwindow.return_value = subwindow

    view_state_manager = MagicMock()
    view_state_manager.use_rescaled_values = True
    view_state_manager.get_series_identifier.return_value = "series-id"
    overlay_manager = MagicMock()
    overlay_manager.should_show_text_overlays.return_value = True

    app = SimpleNamespace(
        config_manager=config,
        subwindow_data={0: {}},
        subwindow_managers={
            0: {
                "measurement_tool": MagicMock(),
                "view_state_manager": view_state_manager,
                "slice_display_manager": MagicMock(),
                "overlay_manager": overlay_manager,
                "roi_coordinator": MagicMock(),
            }
        },
        multi_window_layout=layout,
        window_level_controls=None,
        focused_subwindow_index=0,
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
    return MprController(app), app  # type: ignore[arg-type]


@pytest.mark.parametrize("photometric_interpretation", ["MONOCHROME1", "MONOCHROME2", ""])
def test_display_forwards_result_photometric_interpretation(photometric_interpretation):
    ctrl, app = _make_controller()
    result = _make_result(photometric_interpretation)
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
    raw = np.ones((4, 4), dtype=np.float32)
    with (
        patch("gui.mpr_controller.apply_mpr_stack_combine", return_value=raw),
        patch.object(ctrl, "_array_to_pil", return_value=MagicMock()) as to_pil,
        patch.object(ctrl, "_get_preferred_mpr_window_level", return_value=(40.0, 400.0)),
        patch("gui.mpr_controller.QTimer.singleShot"),
    ):
        ctrl.display_mpr_slice(0, 1)

    to_pil.assert_called_once()
    assert to_pil.call_args.kwargs["photometric_interpretation"] == photometric_interpretation


def test_wrapper_delegates_polarity_to_the_shared_builder():
    """The static wrapper must not drop the keyword on its way to mpr_view_math."""
    arr = np.array([[0.0, 128.0, 255.0]], dtype=np.float32)
    via_wrapper = MprController._array_to_pil(
        arr, 127.5, 255.0, photometric_interpretation="MONOCHROME1"
    )
    direct = array_to_pil(arr, 127.5, 255.0, photometric_interpretation="MONOCHROME1")
    assert via_wrapper is not None and direct is not None
    assert np.array_equal(np.array(via_wrapper), np.array(direct))
    assert not np.array_equal(
        np.array(via_wrapper), np.array(array_to_pil(arr, 127.5, 255.0))
    )
