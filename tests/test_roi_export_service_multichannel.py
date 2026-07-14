"""Tests for multichannel ROI statistics export and computation helpers."""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from pydicom.dataset import Dataset

from core import roi_export_service
from tools.roi_manager import ROIManager


class _Bounds:
    def __init__(self, left: float, top: float, right: float, bottom: float) -> None:
        self._left = left
        self._top = top
        self._right = right
        self._bottom = bottom

    def left(self) -> float:
        return self._left

    def right(self) -> float:
        return self._right

    def top(self) -> float:
        return self._top

    def bottom(self) -> float:
        return self._bottom


class _FakeROI:
    def __init__(self) -> None:
        self.statistics = {}

    def get_bounds(self) -> _Bounds:
        return _Bounds(0.0, 0.0, 2.0, 2.0)

    def get_mask(self, width: int, height: int) -> np.ndarray:
        _ = (width, height)
        return np.array([[True, True], [True, True]], dtype=bool)


def test_calculate_statistics_populates_multichannel_fields() -> None:
    roi = _FakeROI()
    pixel_array = np.array(
        [
            [[10, 20, 30], [11, 21, 31]],
            [[12, 22, 32], [13, 23, 33]],
        ],
        dtype=np.float32,
    )
    fake_manager = SimpleNamespace(
        config_manager=SimpleNamespace(get_roi_show_per_channel_statistics=lambda: True)
    )

    stats = ROIManager.calculate_statistics(fake_manager, roi, pixel_array)

    assert stats["multichannel_count"] == 3
    assert stats["mean_ch0"] == 11.5
    assert stats["mean_ch1"] == 21.5
    assert stats["mean_ch2"] == 31.5
    assert stats.get("channel_labels") == ("Ch0", "Ch1", "Ch2")

    ds_rgb = Dataset()
    ds_rgb.PhotometricInterpretation = "RGB"
    stats_rgb = ROIManager.calculate_statistics(
        fake_manager, roi, pixel_array, dataset=ds_rgb
    )
    assert stats_rgb.get("channel_labels") == ("R", "G", "B")


def test_write_csv_includes_multichannel_columns(tmp_path: Path, monkeypatch) -> None:
    def _fake_stats(*args, **kwargs):
        _ = (args, kwargs)
        return (
            {
                "mean": 10.0,
                "std": 1.0,
                "min": 8.0,
                "max": 12.0,
                "count": 4,
                "area_pixels": 4.0,
                "area_mm2": None,
                "multichannel_count": 3,
                "mean_ch0": 10.5,
                "std_ch0": 0.5,
                "min_ch0": 10.0,
                "max_ch0": 11.0,
                "mean_ch1": 20.5,
                "std_ch1": 0.7,
                "min_ch1": 20.0,
                "max_ch1": 21.0,
                "mean_ch2": 30.5,
                "std_ch2": 0.9,
                "min_ch2": 30.0,
                "max_ch2": 31.0,
            },
            "HU",
        )

    monkeypatch.setattr(roi_export_service, "compute_roi_statistics", _fake_stats)

    ds = Dataset()
    ds.SeriesNumber = "1"
    ds.SeriesDescription = "RGB"
    ds.PhotometricInterpretation = "RGB"
    current_studies = {"study": {"series": [ds]}}
    collected = [(("study", "series"), [(0, [SimpleNamespace(shape_type="rectangle")], [], [])])]
    subwindow_managers = {0: {"roi_manager": object()}}
    out_path = tmp_path / "roi.csv"

    roi_export_service.write_csv(
        file_path=str(out_path),
        collected=collected,
        current_studies=current_studies,
        subwindow_managers=subwindow_managers,
        use_rescale=False,
        dicom_processor=object,
    )

    with out_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert "Mean (R)" in rows[0]
    assert "Std Dev (G)" in rows[0]
    assert "Max (B)" in rows[0]
    assert rows[0]["Mean (R)"] == "10.5000"
    assert rows[0]["Max (G)"] == "21.0000"
    assert rows[0]["Std Dev (B)"] == "0.9000"


def test_write_csv_ybr_uses_y_cb_cr_headers(tmp_path: Path, monkeypatch) -> None:
    def _fake_stats(*args, **kwargs):
        _ = (args, kwargs)
        return (
            {
                "mean": 10.0,
                "std": 1.0,
                "min": 8.0,
                "max": 12.0,
                "count": 4,
                "area_pixels": 4.0,
                "area_mm2": None,
                "multichannel_count": 3,
                "mean_ch0": 10.5,
                "std_ch0": 0.5,
                "min_ch0": 10.0,
                "max_ch0": 11.0,
                "mean_ch1": 20.5,
                "std_ch1": 0.7,
                "min_ch1": 20.0,
                "max_ch1": 21.0,
                "mean_ch2": 30.5,
                "std_ch2": 0.9,
                "min_ch2": 30.0,
                "max_ch2": 31.0,
            },
            "HU",
        )

    monkeypatch.setattr(roi_export_service, "compute_roi_statistics", _fake_stats)

    ds = Dataset()
    ds.SeriesNumber = "1"
    ds.SeriesDescription = "YBR"
    ds.PhotometricInterpretation = "YBR_FULL_422"
    current_studies = {"study": {"series": [ds]}}
    collected = [(("study", "series"), [(0, [SimpleNamespace(shape_type="rectangle")], [], [])])]
    subwindow_managers = {0: {"roi_manager": object()}}
    out_path = tmp_path / "roi_ybr.csv"

    roi_export_service.write_csv(
        file_path=str(out_path),
        collected=collected,
        current_studies=current_studies,
        subwindow_managers=subwindow_managers,
        use_rescale=False,
        dicom_processor=object,
    )

    with out_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert "Mean (Y)" in rows[0]
    assert "Std Dev (Cb)" in rows[0]
    assert "Max (Cr)" in rows[0]
    assert rows[0]["Mean (Y)"] == "10.5000"
    assert rows[0]["Max (Cb)"] == "21.0000"
    assert rows[0]["Std Dev (Cr)"] == "0.9000"


def test_write_csv_two_channel_uses_ch0_ch1_headers(tmp_path: Path, monkeypatch) -> None:
    """Non-RGB multichannel exports use Ch0, Ch1, … in CSV headers (not R/G/B)."""

    def _fake_stats(*args, **kwargs):
        _ = (args, kwargs)
        return (
            {
                "mean": 1.0,
                "std": 0.1,
                "min": 0.0,
                "max": 2.0,
                "count": 1,
                "area_pixels": 1.0,
                "area_mm2": None,
                "multichannel_count": 2,
                "mean_ch0": 1.0,
                "std_ch0": 0.1,
                "min_ch0": 0.0,
                "max_ch0": 2.0,
                "mean_ch1": 3.0,
                "std_ch1": 0.2,
                "min_ch1": 2.0,
                "max_ch1": 4.0,
            },
            "",
        )

    monkeypatch.setattr(roi_export_service, "compute_roi_statistics", _fake_stats)

    ds = Dataset()
    ds.SeriesNumber = "1"
    ds.SeriesDescription = "TwoCh"
    current_studies = {"study": {"series": [ds]}}
    collected = [(("study", "series"), [(0, [SimpleNamespace(shape_type="rectangle")], [], [])])]
    subwindow_managers = {0: {"roi_manager": object()}}
    out_path = tmp_path / "roi2ch.csv"

    roi_export_service.write_csv(
        file_path=str(out_path),
        collected=collected,
        current_studies=current_studies,
        subwindow_managers=subwindow_managers,
        use_rescale=False,
        dicom_processor=object,
    )

    with out_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert "Mean (Ch0)" in rows[0]
    assert "Max (Ch1)" in rows[0]
    assert rows[0]["Mean (Ch0)"] == "1.0000"
    assert rows[0]["Std Dev (Ch1)"] == "0.2000"


def test_write_csv_escapes_formula_like_text_cells(tmp_path: Path, monkeypatch) -> None:
    def _fake_stats(*args, **kwargs):
        _ = (args, kwargs)
        return (
            {
                "mean": 10.0,
                "std": 1.0,
                "min": 8.0,
                "max": 12.0,
                "count": 4,
                "area_pixels": 4.0,
                "area_mm2": None,
            },
            "",
        )

    monkeypatch.setattr(roi_export_service, "compute_roi_statistics", _fake_stats)

    ds = Dataset()
    ds.SeriesNumber = "1"
    ds.SeriesDescription = "=bad"
    current_studies = {"study": {"series": [ds]}}
    collected = [(("study", "series"), [(0, [SimpleNamespace(shape_type="rectangle")], [], [])])]
    subwindow_managers = {0: {"roi_manager": object()}}
    out_path = tmp_path / "roi_safe.csv"

    roi_export_service.write_csv(
        file_path=str(out_path),
        collected=collected,
        current_studies=current_studies,
        subwindow_managers=subwindow_managers,
        use_rescale=False,
        dicom_processor=object,
    )

    with out_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["Series Description"] == "'=bad"
