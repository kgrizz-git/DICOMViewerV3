"""Tests for collect_roi_data, compute_roi_statistics, crosshair export, and CSV crosshair rows.

Stage 1b: exercises the data-gathering and statistics paths of
core/roi_export_service using lightweight fakes (no Qt, no real pixel data).
"""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from pydicom.dataset import Dataset

from core import roi_export_service


class _FakeProcessor:
    """Stand-in for DICOMProcessor with the two classmethods compute_roi_statistics uses."""

    pixel_array: np.ndarray | None = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    rescale = (2.0, -1024.0, "HU")

    @classmethod
    def get_pixel_array(cls, dataset):
        _ = dataset
        return cls.pixel_array

    @classmethod
    def get_rescale_parameters(cls, dataset):
        _ = dataset
        return cls.rescale


class _RecordingROIManager:
    """Records the kwargs calculate_statistics was called with and returns canned stats."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def calculate_statistics(self, roi_item, pixel_array, **kwargs):
        _ = (roi_item, pixel_array)
        self.calls.append(kwargs)
        return {"mean": 5.0, "std": 1.0, "min": 4.0, "max": 6.0, "count": 4}


def test_collect_roi_data_skips_unloaded_series() -> None:
    out = roi_export_service.collect_roi_data(
        [("missing", "series")], current_studies={}, subwindow_managers={}
    )
    assert out == []


def test_collect_roi_data_gathers_rois_and_crosshairs() -> None:
    ds = Dataset()
    current_studies = {"st": {"sr": [ds, ds]}}
    roi_mgr = SimpleNamespace(rois={("st", "sr", 0): ["roiA"]})
    cross_mgr = SimpleNamespace(crosshairs={("st", "sr", 1): ["crossB"]})
    subwindow_managers = {0: {"roi_manager": roi_mgr, "crosshair_manager": cross_mgr}}

    out = roi_export_service.collect_roi_data(
        [("st", "sr")], current_studies, subwindow_managers
    )
    (_key, slice_list) = out[0]
    by_z = {z: (rois, crosshairs, meas) for z, rois, crosshairs, meas in slice_list}
    assert by_z[0][0] == ["roiA"]
    assert by_z[1][1] == ["crossB"]


def test_compute_roi_statistics_no_pixel_array_returns_zeros() -> None:
    class _NoPixels(_FakeProcessor):
        pixel_array = None

    stats, unit = roi_export_service.compute_roi_statistics(
        roi_item=object(),
        dataset=Dataset(),
        use_rescale=True,
        roi_manager=_RecordingROIManager(),
        dicom_processor=_NoPixels,
    )
    assert unit is None
    assert stats["count"] == 0
    assert stats["area_mm2"] is None


def test_compute_roi_statistics_passes_rescale_when_requested() -> None:
    mgr = _RecordingROIManager()
    stats, unit = roi_export_service.compute_roi_statistics(
        roi_item=object(),
        dataset=Dataset(),
        use_rescale=True,
        roi_manager=mgr,
        dicom_processor=_FakeProcessor,
    )
    assert unit == "HU"
    assert stats["mean"] == 5.0
    assert mgr.calls[0]["rescale_slope"] == 2.0
    assert mgr.calls[0]["rescale_intercept"] == -1024.0


def test_compute_roi_statistics_skips_rescale_when_not_requested() -> None:
    mgr = _RecordingROIManager()
    roi_export_service.compute_roi_statistics(
        roi_item=object(),
        dataset=Dataset(),
        use_rescale=False,
        roi_manager=mgr,
        dicom_processor=_FakeProcessor,
    )
    assert mgr.calls[0]["rescale_slope"] is None
    assert mgr.calls[0]["rescale_intercept"] is None


def test_get_crosshair_export_data_structure() -> None:
    cross = SimpleNamespace(x_coord=12, y_coord=34, z_coord=2, pixel_value_str="123 HU")
    data = roi_export_service.get_crosshair_export_data(cross, Dataset())
    assert data["pixel_x"] == 12
    assert data["pixel_y"] == 34
    assert data["slice_index"] == 2
    assert data["pixel_value_str"] == "123 HU"
    # Empty dataset has no geometry -> patient coords are None.
    assert data["patient_x"] is None


def test_write_csv_crosshair_row(tmp_path: Path) -> None:
    ds = Dataset()
    ds.SeriesNumber = "3"
    ds.SeriesDescription = "Axial"
    cross = SimpleNamespace(x_coord=5, y_coord=7, z_coord=0, pixel_value_str="42")
    collected = [(("study", "series"), [(0, [], [cross], [])])]
    out_path = tmp_path / "cross.csv"

    roi_export_service.write_csv(
        file_path=str(out_path),
        collected=collected,
        current_studies={"study": {"series": [ds]}},
        subwindow_managers={0: {"roi_manager": None}},
        use_rescale=False,
        dicom_processor=_FakeProcessor,
    )
    with out_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["Pixel X"] == "5"
    assert rows[0]["Pixel Y"] == "7"
    assert rows[0]["Pixel Value"] == "42"
    assert rows[0]["ROI Type"] == ""


def test_write_csv_skips_unloaded_series(tmp_path: Path) -> None:
    out_path = tmp_path / "skip.csv"
    roi_export_service.write_csv(
        file_path=str(out_path),
        collected=[(("missing", "series"), [(0, [], [], [])])],
        current_studies={},
        subwindow_managers={0: {"roi_manager": None}},
        use_rescale=False,
        dicom_processor=_FakeProcessor,
    )
    with out_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    # Only the header row is written.
    assert len(rows) == 1
