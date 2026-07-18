"""Tests for TXT/XLSX writers, run_export dispatch, and helpers in roi_export_service.

The ROI-statistics paths are exercised by monkeypatching ``compute_roi_statistics``
to return canned payloads (same approach as the multichannel CSV tests), so these
tests need neither real pixel data nor Qt for the ROI/crosshair/helper paths.
Measurement paths require the real Qt item classes and are guarded with
``pytest.importorskip("PySide6")``.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from pydicom.dataset import Dataset

from core import roi_export_service


def _canned_stats(*, area_mm2, multichannel: bool = False):
    """Return a (stats, unit) factory value for monkeypatching compute_roi_statistics."""
    stats: dict[str, float | int | None] = {
        "mean": 10.0,
        "std": 1.0,
        "min": 8.0,
        "max": 12.0,
        "count": 4,
        "area_pixels": 4.0,
        "area_mm2": area_mm2,
    }
    if multichannel:
        stats.update(
            {
                "multichannel_count": 3,
                "mean_ch0": 10.5, "std_ch0": 0.5, "min_ch0": 10.0, "max_ch0": 11.0,
                "mean_ch1": 20.5, "std_ch1": 0.7, "min_ch1": 20.0, "max_ch1": 21.0,
                "mean_ch2": 30.5, "std_ch2": 0.9, "min_ch2": 30.0, "max_ch2": 31.0,
            }
        )
    return stats, "HU"


def _one_roi_collected():
    return [(("study", "series"), [(0, [SimpleNamespace(shape_type="rectangle")], [], [])])]


def _rgb_dataset() -> Dataset:
    ds = Dataset()
    ds.SeriesNumber = "1"
    ds.SeriesDescription = "RGB"
    ds.StudyDescription = "Study A"
    ds.PhotometricInterpretation = "RGB"
    return ds


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #

def test_format_float_none_and_value() -> None:
    assert roi_export_service._format_float(None) == "N/A"
    assert roi_export_service._format_float(1.23456) == "1.2346"


def test_extract_channel_stats() -> None:
    stats = {
        "multichannel_count": 2,
        "mean_ch0": 1.0, "std_ch0": 0.1, "min_ch0": 0.0, "max_ch0": 2.0,
        "mean_ch1": 3.0, "std_ch1": None, "min_ch1": 2.0, "max_ch1": 4.0,
    }
    count, values = roi_export_service._extract_channel_stats(stats)
    assert count == 2
    assert values["mean_ch0"] == "1.0000"
    assert values["std_ch1"] == ""  # None -> blank
    assert values["max_ch1"] == "4.0000"


def test_extract_channel_stats_no_channels() -> None:
    count, values = roi_export_service._extract_channel_stats({})
    assert count == 0
    assert values == {}


def test_channel_stat_csv_headers_from_labels() -> None:
    headers = roi_export_service._channel_stat_csv_headers_from_labels(("R", "G"))
    assert headers == [
        "Mean (R)", "Std Dev (R)", "Min (R)", "Max (R)",
        "Mean (G)", "Std Dev (G)", "Min (G)", "Max (G)",
    ]


def test_sanitize_filename() -> None:
    assert roi_export_service._sanitize_filename("a/b:c*?.txt") == "a_b_c__.txt"


def test_serialize_measurement_unknown_returns_empty() -> None:
    row = roi_export_service.serialize_measurement_for_export(object(), 1)
    assert row == [""] * len(roi_export_service.MEASUREMENT_CSV_HEADERS)


def test_measurement_txt_block_lines_unknown() -> None:
    lines = roi_export_service.measurement_txt_block_lines(object(), 3)
    assert "  Measurement 3" in lines
    assert any("(unknown)" in ln for ln in lines)


def test_measurement_xlsx_pairs_unknown() -> None:
    pairs = roi_export_service._measurement_xlsx_label_value_pairs(object())
    assert pairs == [("Type", "unknown")]


# --------------------------------------------------------------------------- #
# write_txt
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    ("area_mm2", "expected"),
    [(150.0, "cm²"), (50.0, "mm²"), (None, "pixels")],
)
def test_write_txt_roi_area_units(tmp_path: Path, monkeypatch, area_mm2, expected) -> None:
    monkeypatch.setattr(
        roi_export_service, "compute_roi_statistics",
        lambda *a, **k: _canned_stats(area_mm2=area_mm2),
    )
    ds = _rgb_dataset()
    out = tmp_path / "r.txt"
    roi_export_service.write_txt(
        file_path=str(out),
        collected=_one_roi_collected(),
        current_studies={"study": {"series": [ds]}},
        subwindow_managers={0: {"roi_manager": object()}},
        use_rescale=False,
        dicom_processor=object,
    )
    text = out.read_text(encoding="utf-8")
    assert "Series 1: RGB" in text
    assert "Rectangle ROI 1" in text
    assert "Mean       10.00" in text
    assert expected in text


def test_write_txt_multichannel(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        roi_export_service, "compute_roi_statistics",
        lambda *a, **k: _canned_stats(area_mm2=None, multichannel=True),
    )
    ds = _rgb_dataset()
    out = tmp_path / "mc.txt"
    roi_export_service.write_txt(
        file_path=str(out),
        collected=_one_roi_collected(),
        current_studies={"study": {"series": [ds]}},
        subwindow_managers={0: {"roi_manager": object()}},
        use_rescale=False,
        dicom_processor=object,
    )
    text = out.read_text(encoding="utf-8")
    assert "R Mean" in text and "B Max" in text


def test_write_txt_empty_slice_list_writes_no_annotations(tmp_path: Path) -> None:
    ds = _rgb_dataset()
    out = tmp_path / "empty.txt"
    roi_export_service.write_txt(
        file_path=str(out),
        collected=[(("study", "series"), [])],
        current_studies={"study": {"series": [ds]}},
        subwindow_managers={0: {"roi_manager": object()}},
        use_rescale=False,
        dicom_processor=object,
    )
    assert "No annotations" in out.read_text(encoding="utf-8")


def test_write_txt_skips_series_not_loaded(tmp_path: Path) -> None:
    out = tmp_path / "skip.txt"
    roi_export_service.write_txt(
        file_path=str(out),
        collected=[(("missing", "series"), [(0, [], [], [])])],
        current_studies={},  # series not present
        subwindow_managers={0: {"roi_manager": object()}},
        use_rescale=False,
        dicom_processor=object,
    )
    assert out.read_text(encoding="utf-8").strip() == ""


# --------------------------------------------------------------------------- #
# write_xlsx
# --------------------------------------------------------------------------- #

def _read_xlsx_col_a(path: Path) -> list[str]:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    return [str(row[0].value) for row in ws.iter_rows() if row[0].value is not None]


@pytest.mark.parametrize(
    ("area_mm2", "expected_unit"),
    [(150.0, "cm²"), (50.0, "mm²"), (None, "pixels")],
)
def test_write_xlsx_roi_area_units(tmp_path: Path, monkeypatch, area_mm2, expected_unit) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    monkeypatch.setattr(
        roi_export_service, "compute_roi_statistics",
        lambda *a, **k: _canned_stats(area_mm2=area_mm2),
    )
    ds = _rgb_dataset()
    out = tmp_path / "r.xlsx"
    roi_export_service.write_xlsx(
        file_path=str(out),
        collected=_one_roi_collected(),
        current_studies={"study": {"series": [ds]}},
        subwindow_managers={0: {"roi_manager": object()}},
        use_rescale=False,
        dicom_processor=object,
    )
    ws = openpyxl.load_workbook(out).active
    col_a = [str(row[0].value) for row in ws.iter_rows() if row[0].value is not None]
    col_c = [row[2].value for row in ws.iter_rows() if row[2].value]
    assert "Series 1: RGB" in col_a
    assert "  Rectangle ROI 1" in col_a
    assert expected_unit in col_c


def test_write_xlsx_multichannel(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("openpyxl")
    monkeypatch.setattr(
        roi_export_service, "compute_roi_statistics",
        lambda *a, **k: _canned_stats(area_mm2=None, multichannel=True),
    )
    ds = _rgb_dataset()
    out = tmp_path / "mc.xlsx"
    roi_export_service.write_xlsx(
        file_path=str(out),
        collected=_one_roi_collected(),
        current_studies={"study": {"series": [ds]}},
        subwindow_managers={0: {"roi_manager": object()}},
        use_rescale=False,
        dicom_processor=object,
    )
    col_a = _read_xlsx_col_a(out)
    assert "R Mean" in col_a and "B Max" in col_a


def test_write_xlsx_empty_slice_list(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    ds = _rgb_dataset()
    out = tmp_path / "empty.xlsx"
    roi_export_service.write_xlsx(
        file_path=str(out),
        collected=[(("study", "series"), [])],
        current_studies={"study": {"series": [ds]}},
        subwindow_managers={0: {"roi_manager": object()}},
        use_rescale=False,
        dicom_processor=object,
    )
    assert "No annotations" in _read_xlsx_col_a(out)


def test_write_xlsx_skips_series_not_loaded(tmp_path: Path) -> None:
    pytest.importorskip("openpyxl")
    out = tmp_path / "skip.xlsx"
    roi_export_service.write_xlsx(
        file_path=str(out),
        collected=[(("missing", "series"), [(0, [], [], [])])],
        current_studies={},
        subwindow_managers={0: {"roi_manager": object()}},
        use_rescale=False,
        dicom_processor=object,
    )
    assert _read_xlsx_col_a(out) == []


# --------------------------------------------------------------------------- #
# run_export dispatch
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("fmt", ["TXT", "csv", "XLSX"])
def test_run_export_dispatch_creates_file(tmp_path: Path, fmt) -> None:
    if fmt.upper() == "XLSX":
        pytest.importorskip("openpyxl")
    out = tmp_path / f"export.{fmt.lower()}"
    roi_export_service.run_export(
        file_path=str(out),
        format_key=fmt,
        selected_series=[],  # -> empty collected
        current_studies={},
        subwindow_managers={},
        use_rescale=False,
    )
    assert out.exists()


def test_run_export_unsupported_format_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unsupported format"):
        roi_export_service.run_export(
            file_path=str(tmp_path / "x.pdf"),
            format_key="PDF",
            selected_series=[],
            current_studies={},
            subwindow_managers={},
            use_rescale=False,
        )


# --------------------------------------------------------------------------- #
# Measurement paths (require the real Qt item classes)
# --------------------------------------------------------------------------- #

def _make_measurement_items():
    from PySide6.QtCore import QLineF, QPointF
    from PySide6.QtWidgets import QApplication, QGraphicsLineItem, QGraphicsTextItem

    from tools.angle_measurement_items import AngleMeasurementItem
    from tools.measurement_items import MeasurementItem

    _ = QApplication.instance() or QApplication([])
    dist = MeasurementItem(
        QPointF(10.0, 20.0), QPointF(13.0, 24.0),
        QGraphicsLineItem(QLineF(0.0, 0.0, 3.0, 4.0)), QGraphicsTextItem(),
        pixel_spacing=(1.0, 1.0),
    )
    angle = AngleMeasurementItem(
        QPointF(0.0, 0.0), QPointF(1.0, 0.0), QPointF(1.0, 1.0),
        QGraphicsLineItem(QLineF(0, 0, 1, 0)), QGraphicsLineItem(QLineF(0, 0, 0, 1)),
        QGraphicsTextItem(),
    )
    return dist, angle


def test_write_txt_distance_and_angle_measurements(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    dist, angle = _make_measurement_items()
    ds = _rgb_dataset()
    out = tmp_path / "meas.txt"
    roi_export_service.write_txt(
        file_path=str(out),
        collected=[(("study", "series"), [(0, [], [], [dist, angle])])],
        current_studies={"study": {"series": [ds]}},
        subwindow_managers={0: {"roi_manager": None}},
        use_rescale=False,
        dicom_processor=object,
    )
    text = out.read_text(encoding="utf-8")
    assert "Type            Distance" in text
    assert "Distance (mm)   5.0000" in text
    assert "Type            Angle" in text


def test_write_xlsx_measurements(tmp_path: Path) -> None:
    pytest.importorskip("PySide6")
    pytest.importorskip("openpyxl")
    dist, angle = _make_measurement_items()
    ds = _rgb_dataset()
    out = tmp_path / "meas.xlsx"
    roi_export_service.write_xlsx(
        file_path=str(out),
        collected=[(("study", "series"), [(0, [], [], [dist, angle])])],
        current_studies={"study": {"series": [ds]}},
        subwindow_managers={0: {"roi_manager": None}},
        use_rescale=False,
        dicom_processor=object,
    )
    col_a = _read_xlsx_col_a(out)
    assert "  Measurement 1" in col_a
    assert "Distance (px)" in col_a
    assert "Angle (deg)" in col_a
