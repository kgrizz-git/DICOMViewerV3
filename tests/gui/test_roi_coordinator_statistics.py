"""
Characterize ROICoordinator statistics pixel-array and overlay update contracts.

Covers MPR vs projection vs original-slice paths, fallback when projection cannot
run, foreign-ROI ownership rejection, and bulk overlay rebuild behavior.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from gui.roi_coordinator import ROICoordinator


def _make_coordinator(**overrides) -> ROICoordinator:
    """Build a coordinator with MagicMock collaborators for unit tests."""
    kwargs = {
        "roi_manager": MagicMock(),
        "roi_list_panel": MagicMock(),
        "roi_statistics_panel": MagicMock(),
        "image_viewer": MagicMock(),
        "dicom_processor": MagicMock(),
        "window_level_controls": MagicMock(),
        "main_window": MagicMock(),
        "get_current_dataset": MagicMock(return_value=None),
        "get_current_slice_index": MagicMock(return_value=0),
        "get_rescale_params": MagicMock(return_value=(1.0, 0.0, "HU", True)),
        "get_projection_enabled": MagicMock(return_value=False),
        "get_projection_type": MagicMock(return_value="aip"),
        "get_projection_slice_count": MagicMock(return_value=4),
        "get_current_studies": MagicMock(return_value={}),
        "get_mpr_pixel_array": MagicMock(return_value=None),
        "get_mpr_output_pixel_spacing": MagicMock(return_value=None),
    }
    kwargs.update(overrides)
    kwargs["image_viewer"].scene = MagicMock()
    kwargs["image_viewer"].is_mpr_view_callback = MagicMock(return_value=False)
    return ROICoordinator(**kwargs)


def _dataset(study: str = "study-1", series: str = "series-1") -> SimpleNamespace:
    return SimpleNamespace(StudyInstanceUID=study, SeriesInstanceUID=series)


@pytest.mark.qt
def test_pixel_array_uses_mpr_callback_and_skips_projection(qapp) -> None:
    mpr_arr = np.zeros((4, 4), dtype=np.float32)
    coord = _make_coordinator(
        get_mpr_pixel_array=MagicMock(return_value=mpr_arr),
        get_projection_enabled=MagicMock(return_value=True),
    )
    coord.image_viewer.is_mpr_view_callback = MagicMock(return_value=True)

    result = coord._get_pixel_array_for_statistics()

    assert result is mpr_arr
    coord.get_projection_enabled.assert_not_called()
    coord.dicom_processor.get_pixel_array.assert_not_called()


@pytest.mark.qt
def test_pixel_array_projection_disabled_uses_original_slice(qapp) -> None:
    ds = _dataset()
    original = np.ones((3, 3), dtype=np.float32)
    coord = _make_coordinator(
        get_current_dataset=MagicMock(return_value=ds),
        get_projection_enabled=MagicMock(return_value=False),
    )
    coord.dicom_processor.get_pixel_array.return_value = original

    result = coord._get_pixel_array_for_statistics()

    assert result is original
    coord.dicom_processor.get_pixel_array.assert_called_once_with(ds)
    coord.dicom_processor.average_intensity_projection.assert_not_called()


@pytest.mark.qt
def test_pixel_array_projection_aip_with_enough_slices(qapp) -> None:
    ds = _dataset()
    slices = [SimpleNamespace(i=i) for i in range(5)]
    studies = {"study-1": {"series-1": slices}}
    projected = np.full((2, 2), 7.0, dtype=np.float32)
    coord = _make_coordinator(
        get_current_dataset=MagicMock(return_value=ds),
        get_current_slice_index=MagicMock(return_value=1),
        get_projection_enabled=MagicMock(return_value=True),
        get_projection_type=MagicMock(return_value="aip"),
        get_projection_slice_count=MagicMock(return_value=3),
        get_current_studies=MagicMock(return_value=studies),
    )
    coord.dicom_processor.average_intensity_projection.return_value = projected

    result = coord._get_pixel_array_for_statistics()

    assert result is projected
    gathered = coord.dicom_processor.average_intensity_projection.call_args[0][0]
    assert gathered == slices[1:4]


@pytest.mark.qt
def test_pixel_array_projection_falls_back_when_too_few_slices(qapp) -> None:
    ds = _dataset()
    studies = {"study-1": {"series-1": [SimpleNamespace(i=0)]}}
    original = np.zeros((2, 2), dtype=np.float32)
    coord = _make_coordinator(
        get_current_dataset=MagicMock(return_value=ds),
        get_projection_enabled=MagicMock(return_value=True),
        get_current_studies=MagicMock(return_value=studies),
    )
    coord.dicom_processor.get_pixel_array.return_value = original

    result = coord._get_pixel_array_for_statistics()

    assert result is original
    coord.dicom_processor.average_intensity_projection.assert_not_called()


@pytest.mark.qt
def test_update_roi_statistics_skips_foreign_roi(qapp) -> None:
    ds = _dataset()
    foreign = MagicMock()
    owned = MagicMock()
    coord = _make_coordinator(get_current_dataset=MagicMock(return_value=ds))
    coord.roi_manager.rois = {("study-1", "series-1", 0): [owned]}

    coord.update_roi_statistics(foreign)

    coord.roi_manager.calculate_statistics.assert_not_called()
    coord.roi_statistics_panel.update_statistics.assert_not_called()


@pytest.mark.qt
def test_update_roi_statistics_mpr_passes_none_rescale_slopes(qapp) -> None:
    ds = _dataset()
    roi = MagicMock()
    roi.shape_type = "rectangle"
    roi.statistics_overlay_visible = False
    pixel = np.ones((4, 4), dtype=np.float32)
    stats = {"mean": 1.0, "count": 1}
    coord = _make_coordinator(
        get_current_dataset=MagicMock(return_value=ds),
        get_mpr_pixel_array=MagicMock(return_value=pixel),
        get_mpr_output_pixel_spacing=MagicMock(return_value=(1.0, 1.0)),
        get_rescale_params=MagicMock(return_value=(2.0, -100.0, "HU", True)),
    )
    coord.image_viewer.is_mpr_view_callback = MagicMock(return_value=True)
    coord.roi_manager.rois = {("study-1", "series-1", 0): [roi]}
    coord.roi_manager.get_rois_for_slice.return_value = [roi]
    coord.roi_manager.calculate_statistics.return_value = stats

    coord.update_roi_statistics(roi)

    kwargs = coord.roi_manager.calculate_statistics.call_args.kwargs
    assert kwargs["rescale_slope"] is None
    assert kwargs["rescale_intercept"] is None
    coord.roi_statistics_panel.update_statistics.assert_called_once()


@pytest.mark.qt
def test_update_roi_statistics_overlays_rebuilds_visible_only(qapp) -> None:
    ds = _dataset()
    visible = MagicMock()
    visible.statistics_overlay_visible = True
    visible.on_moved_callback = None
    hidden = MagicMock()
    hidden.statistics_overlay_visible = False
    hidden.on_moved_callback = MagicMock()
    pixel = np.ones((3, 3), dtype=np.float32)
    stats = {"mean": 2.0, "count": 4}
    coord = _make_coordinator(
        get_current_dataset=MagicMock(return_value=ds),
        get_projection_enabled=MagicMock(return_value=False),
    )
    coord.dicom_processor.get_pixel_array.return_value = pixel
    coord.roi_manager.get_rois_for_slice.return_value = [visible, hidden]
    coord.roi_manager.calculate_statistics.return_value = stats

    coord.update_roi_statistics_overlays()

    coord.roi_manager.remove_all_statistics_overlays_from_scene.assert_called_once()
    assert visible.on_moved_callback is not None
    assert hidden.on_moved_callback is not None  # pre-existing mock kept
    coord.roi_manager.create_statistics_overlay.assert_called_once()
    assert coord.roi_manager.create_statistics_overlay.call_args[0][0] is visible
