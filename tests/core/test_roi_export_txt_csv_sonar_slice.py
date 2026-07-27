"""
Characterization tests for ROI TXT/CSV export helpers (Sonar S3776 slice).

Covers area line formatting, study UID truncation, and ROI stat column
population extracted from ``roi_export_service.write_txt`` / ``write_csv``.
"""

from __future__ import annotations

from core.roi_export_csv import (
    CSV_BASE_COLUMN_COUNT,
    empty_csv_base_row,
    populate_roi_stats_in_row,
    truncate_study_uid_for_csv,
)
from core.roi_export_txt import txt_area_line


def test_txt_area_line_thresholds() -> None:
    assert txt_area_line(150.0, 99.0) == "    Area       1.50    cm²"
    assert txt_area_line(100.0, 99.0) == "    Area       1.00    cm²"
    assert txt_area_line(99.9, 10.0) == "    Area       99.90    mm²"
    assert txt_area_line(None, 12.5) == "    Area       12.5    pixels"


def test_truncate_study_uid_for_csv() -> None:
    short = "1.2.3"
    assert truncate_study_uid_for_csv(short) == short
    long_uid = "1.2.840.113619.2.55.3.123456789012345678901234567890"
    assert len(long_uid) > 38
    assert truncate_study_uid_for_csv(long_uid) == long_uid[:36] + ".."


def test_populate_roi_stats_in_row_formats_columns() -> None:
    row = empty_csv_base_row()
    assert len(row) == CSV_BASE_COLUMN_COUNT
    stats = {
        "mean": 10.0,
        "std": 1.5,
        "min": 8.0,
        "max": 12.0,
        "count": 4,
        "area_pixels": 4.0,
        "area_mm2": 2.5,
        "multichannel_count": 1,
        "mean_ch0": 10.5,
        "std_ch0": 0.5,
        "min_ch0": 10.0,
        "max_ch0": 11.0,
    }
    channel_values, channel_count = populate_roi_stats_in_row(
        row, stats=stats, rescale_unit="HU"
    )
    assert channel_count == 1
    assert row[6] == "10.0000"
    assert row[7] == "1.5000"
    assert row[10] == "4"
    assert row[11] == "4.0"
    assert row[12] == "2.5000"
    assert row[13] == "HU"
    assert channel_values["mean_ch0"] == "10.5000"


def test_populate_roi_stats_in_row_blank_area_mm2() -> None:
    row = empty_csv_base_row()
    stats = {
        "mean": 0.0,
        "std": 0.0,
        "min": 0.0,
        "max": 0.0,
        "count": 0,
        "area_pixels": 0.0,
        "area_mm2": None,
    }
    _, channel_count = populate_roi_stats_in_row(row, stats=stats, rescale_unit=None)
    assert channel_count == 0
    assert row[12] == ""
    assert row[13] == ""
