"""Tests for measurement export in roi_export_service (distance + angle rows)."""

from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydicom.dataset import Dataset

from core import roi_export_service


class _FakeMeasurementTool:
    """Returns canned measurements per (study, series, z)."""

    def __init__(self, items_by_key):
        self._items_by_key = items_by_key

    def get_measurements_for_slice(self, study_uid: str, series_uid: str, z: int):
        return list(self._items_by_key.get((study_uid, series_uid, z), []))


def test_collect_roi_data_merges_measurement_tool() -> None:
    m_tool = _FakeMeasurementTool({("st", "sr", 1): ["meas_a", "meas_b"]})
    subwindow_managers = {
        0: {
            "roi_manager": SimpleNamespace(rois={}),
            "crosshair_manager": SimpleNamespace(crosshairs={}),
            "measurement_tool": m_tool,
        }
    }
    ds = Dataset()
    current_studies = {"st": {"sr": [ds, ds, ds]}}
    selected = [("st", "sr")]
    out = roi_export_service.collect_roi_data(selected, current_studies, subwindow_managers)
    assert len(out) == 1
    _key, slice_list = out[0]
    assert len(slice_list) == 1
    z, rois, crosshairs, measurements = slice_list[0]
    assert z == 1
    assert rois == []
    assert crosshairs == []
    assert measurements == ["meas_a", "meas_b"]


def test_write_csv_measurement_distance_row(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QLineF, QPointF
    from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsTextItem

    from tools.measurement_items import MeasurementItem

    _ = QApplication.instance() or QApplication([])
    line = QGraphicsLineItem(QLineF(0.0, 0.0, 3.0, 4.0))
    text = QGraphicsTextItem()
    spacing = (1.0, 1.0)
    dist_item = MeasurementItem(
        QPointF(10.0, 20.0),
        QPointF(13.0, 24.0),
        line,
        text,
        pixel_spacing=spacing,
    )
    collected = [(("study", "series"), [(0, [], [], [dist_item])])]
    ds = Dataset()
    ds.SeriesNumber = "2"
    ds.SeriesDescription = "Axial"
    current_studies = {"study": {"series": [ds]}}
    subwindow_managers = {0: {"roi_manager": None}}
    out_path = tmp_path / "meas.csv"

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
    assert len(rows) == 1
    r0 = rows[0]
    assert r0["Measurement Type"] == "distance"
    assert r0["Measurement Index"] == "1"
    assert r0["Distance (mm)"] == "5.000000"
    assert r0["Angle (degrees)"] == ""
    assert "mm" in r0["Measurement display"]
    assert r0["P1 scene X"] == "10.0000"
    assert r0["P2 scene X"] == "13.0000"


def test_write_csv_measurement_angle_row(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QLineF, QPointF
    from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsTextItem

    from tools.angle_measurement_items import AngleMeasurementItem

    _ = QApplication.instance() or QApplication([])
    line1 = QGraphicsLineItem(QLineF(0, 0, 1, 0))
    line2 = QGraphicsLineItem(QLineF(0, 0, 0, 1))
    text = QGraphicsTextItem()
    ang = AngleMeasurementItem(
        QPointF(0.0, 0.0),
        QPointF(1.0, 0.0),
        QPointF(1.0, 1.0),
        line1,
        line2,
        text,
    )
    collected = [(("study", "series"), [(0, [], [], [ang])])]
    ds = Dataset()
    ds.SeriesNumber = "1"
    ds.SeriesDescription = "Test"
    current_studies = {"study": {"series": [ds]}}
    subwindow_managers = {0: {"roi_manager": None}}
    out_path = tmp_path / "angle.csv"

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
    assert len(rows) == 1
    r0 = rows[0]
    assert r0["Measurement Type"] == "angle"
    assert r0["Measurement Index"] == "1"
    assert r0["Distance (mm)"] == ""
    assert float(r0["Angle (degrees)"]) == pytest.approx(90.0, rel=1e-3)
    assert r0["P2 scene X"] == "1.0000"
