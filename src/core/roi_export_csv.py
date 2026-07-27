"""
CSV writers for ROI / crosshair / measurement export.

Extracted from ``roi_export_service.write_csv`` to clear Sonar ``python:S3776``
(cognitive complexity) while preserving one-row-per-annotation layout,
dynamic multichannel columns, and formula-safe cell neutralization.

Inputs:
    - Collected series/slice annotation tuples
    - DICOM datasets and optional ROI manager for statistics

Outputs:
    - UTF-8 CSV file with base columns, optional channel stats, measurement tail

Requirements:
    - ``core.roi_export_service`` helpers for stats / crosshair / measurements
    - ``core.roi_export_xlsx.resolve_export_roi_manager`` for manager lookup
"""

from __future__ import annotations

import csv
from typing import Any

from pydicom.dataset import Dataset

from core.dicom_color import multichannel_axis_labels
from core.roi_export_xlsx import resolve_export_roi_manager
from core.spreadsheet_safety import (
    neutralize_spreadsheet_value as _safe_spreadsheet_value,
)

# Late-bound helpers from roi_export_service (avoid circular import at load).

CSV_BASE_HEADERS: list[str] = [
    "Study UID",
    "Series Number",
    "Series Description",
    "Slice Index (0-based)",
    "ROI Type",
    "ROI Index",
    "Mean",
    "Std Dev",
    "Min",
    "Max",
    "Pixels",
    "Area (pixels)",
    "Area (mm²)",
    "Rescale Unit",
    "Pixel X",
    "Pixel Y",
    "Pixel Z",
    "Pixel Value",
    "Patient X (mm)",
    "Patient Y (mm)",
    "Patient Z (mm)",
]

CSV_BASE_COLUMN_COUNT = len(CSV_BASE_HEADERS)

RowPayload = tuple[list[str], dict[str, str], list[str]]


def _svc():
    """Late-bind service helpers without a static import cycle for basedpyright."""
    import importlib

    return importlib.import_module("core.roi_export_service")


def truncate_study_uid_for_csv(study_uid: str) -> str:
    """Shorten study UID for CSV base column (same rule as prior ``write_csv``)."""
    return (study_uid[:36] + "..") if len(study_uid) > 38 else study_uid


def empty_csv_base_row() -> list[str]:
    """Blank base columns (21 fields) for ROI/crosshair/measurement skeleton rows."""
    return [""] * CSV_BASE_COLUMN_COUNT


def csv_series_identity_columns(
    study_uid_short: str,
    series_num: Any,
    series_desc: str,
    z: int,
) -> list[str]:
    """First four CSV base columns shared by every annotation row."""
    return [study_uid_short, str(series_num), series_desc, str(z)]


def populate_roi_stats_in_row(
    row: list[str],
    *,
    stats: dict[str, float | int | None],
    rescale_unit: str | None,
) -> tuple[dict[str, str], int]:
    """
    Fill ROI stat columns (indices 6–13) and return channel values + count.

    Mutates ``row`` in place to match prior ``write_csv`` formatting.
    """
    mean_v = stats.get("mean")
    std_v = stats.get("std")
    min_v = stats.get("min")
    max_v = stats.get("max")
    count_v = stats.get("count")
    area_px_v = stats.get("area_pixels")
    area_mm2_v = stats.get("area_mm2")

    mean_f = float(mean_v) if mean_v is not None else 0.0
    std_f = float(std_v) if std_v is not None else 0.0
    min_f = float(min_v) if min_v is not None else 0.0
    max_f = float(max_v) if max_v is not None else 0.0
    count_i = int(count_v) if count_v is not None else 0
    area_px_f = float(area_px_v) if area_px_v is not None else 0.0

    row[6] = f"{mean_f:.4f}"
    row[7] = f"{std_f:.4f}"
    row[8] = f"{min_f:.4f}"
    row[9] = f"{max_f:.4f}"
    row[10] = str(count_i)
    row[11] = f"{area_px_f:.1f}"
    row[12] = f"{float(area_mm2_v):.4f}" if area_mm2_v is not None else ""
    row[13] = rescale_unit or ""

    svc = _svc()
    channel_count, channel_values = svc._extract_channel_stats(stats)
    return channel_values, channel_count


def build_csv_roi_row(
    *,
    study_uid_short: str,
    series_num: Any,
    series_desc: str,
    z: int,
    roi_idx: int,
    roi_item: Any,
    dataset: Dataset | None,
    roi_manager: Any,
    use_rescale: bool,
    dicom_processor: type,
) -> tuple[list[str], dict[str, str], int]:
    """Build one ROI CSV row payload and track multichannel column count."""
    shape = getattr(roi_item, "shape_type", "ellipse")
    row = empty_csv_base_row()
    row[0:4] = csv_series_identity_columns(study_uid_short, series_num, series_desc, z)
    row[4] = shape
    row[5] = str(roi_idx)

    channel_values: dict[str, str] = {}
    channel_count = 0
    if dataset and roi_manager:
        svc = _svc()
        stats, rescale_unit = svc.compute_roi_statistics(
            roi_item, dataset, use_rescale, roi_manager, dicom_processor
        )
        channel_values, channel_count = populate_roi_stats_in_row(
            row, stats=stats, rescale_unit=rescale_unit
        )
    return row, channel_values, channel_count


def build_csv_crosshair_row(
    *,
    study_uid_short: str,
    series_num: Any,
    series_desc: str,
    z: int,
    cross_item: Any,
    dataset: Dataset | None,
) -> list[str]:
    """Build one crosshair CSV row (ROI stat columns blank)."""
    svc = _svc()
    data = svc.get_crosshair_export_data(cross_item, dataset) if dataset else {}
    row = empty_csv_base_row()
    row[0:4] = csv_series_identity_columns(study_uid_short, series_num, series_desc, z)
    row[14] = str(data.get("pixel_x", ""))
    row[15] = str(data.get("pixel_y", ""))
    row[16] = str(data.get("slice_index", ""))
    row[17] = data.get("pixel_value_str", "")
    row[18] = svc._format_float(data.get("patient_x"))
    row[19] = svc._format_float(data.get("patient_y"))
    row[20] = svc._format_float(data.get("patient_z"))
    return row


def build_csv_measurement_row(
    *,
    study_uid_short: str,
    series_num: Any,
    series_desc: str,
    z: int,
    meas_idx: int,
    m_item: Any,
) -> list[str]:
    """Build base columns for one measurement CSV row."""
    row = empty_csv_base_row()
    row[0:4] = csv_series_identity_columns(study_uid_short, series_num, series_desc, z)
    return row


def collect_csv_row_payloads(
    collected: list[Any],
    current_studies: dict[str, dict[str, list[Dataset]]],
    roi_manager: Any,
    use_rescale: bool,
    dicom_processor: type,
) -> tuple[list[RowPayload], int, Dataset | None, list[str]]:
    """
    Walk collected data and gather row payloads plus max channel count.

    Returns:
        (payloads, max_channel_count, label_ref_dataset, headers)
    """
    svc = _svc()
    headers = list(CSV_BASE_HEADERS)
    row_payloads: list[RowPayload] = [
        (headers, {}, svc._empty_measurement_csv_row())
    ]
    max_channel_count = 0
    label_ref_dataset: Dataset | None = None

    for (study_uid, series_uid), slice_list in collected:
        series_dict = current_studies.get(study_uid, {}).get(series_uid, [])
        if not series_dict:
            continue
        first_ds = series_dict[0]
        study_uid_short = truncate_study_uid_for_csv(study_uid)
        series_num = getattr(first_ds, "SeriesNumber", "")
        series_desc = getattr(
            first_ds, svc._TAG_SERIES_DESCRIPTION, svc._DEFAULT_UNKNOWN_SERIES
        )

        for z, rois, crosshairs, measurements in slice_list:
            dataset = series_dict[z] if z < len(series_dict) else None
            for roi_idx, roi_item in enumerate(rois, start=1):
                row, channel_values, channel_count = build_csv_roi_row(
                    study_uid_short=study_uid_short,
                    series_num=series_num,
                    series_desc=series_desc,
                    z=z,
                    roi_idx=roi_idx,
                    roi_item=roi_item,
                    dataset=dataset,
                    roi_manager=roi_manager,
                    use_rescale=use_rescale,
                    dicom_processor=dicom_processor,
                )
                max_channel_count = max(max_channel_count, channel_count)
                if channel_count > 0 and label_ref_dataset is None:
                    label_ref_dataset = dataset
                row_payloads.append((row, channel_values, svc._empty_measurement_csv_row()))

            for cross_item in crosshairs:
                row = build_csv_crosshair_row(
                    study_uid_short=study_uid_short,
                    series_num=series_num,
                    series_desc=series_desc,
                    z=z,
                    cross_item=cross_item,
                    dataset=dataset,
                )
                row_payloads.append((row, {}, svc._empty_measurement_csv_row()))

            for meas_idx, m_item in enumerate(measurements, start=1):
                row = build_csv_measurement_row(
                    study_uid_short=study_uid_short,
                    series_num=series_num,
                    series_desc=series_desc,
                    z=z,
                    meas_idx=meas_idx,
                    m_item=m_item,
                )
                row_payloads.append(
                    (row, {}, svc.serialize_measurement_for_export(m_item, meas_idx))
                )

    return row_payloads, max_channel_count, label_ref_dataset, headers


def finalize_csv_rows(
    row_payloads: list[RowPayload],
    *,
    headers: list[str],
    max_channel_count: int,
    label_ref_dataset: Dataset | None,
) -> list[list[str]]:
    """Expand channel and measurement tail columns; neutralize data cells."""
    svc = _svc()
    dynamic_headers: list[str] = []
    if max_channel_count > 0:
        hdr_labels = multichannel_axis_labels(label_ref_dataset, max_channel_count)
        dynamic_headers = svc._channel_stat_csv_headers_from_labels(hdr_labels)

    rows: list[list[str]] = []
    for base_row, channel_values, meas_part in row_payloads:
        out_row = list(base_row)
        if base_row is headers:
            out_row.extend(dynamic_headers)
            out_row.extend(svc.MEASUREMENT_CSV_HEADERS)
            rows.append(out_row)
            continue
        for c in range(max_channel_count):
            out_row.extend(
                [
                    channel_values.get(f"mean_ch{c}", ""),
                    channel_values.get(f"std_ch{c}", ""),
                    channel_values.get(f"min_ch{c}", ""),
                    channel_values.get(f"max_ch{c}", ""),
                ]
            )
        out_row.extend(meas_part)
        rows.append([_safe_spreadsheet_value(cell) for cell in out_row])
    return rows


def write_csv_report(
    file_path: str,
    collected: list[Any],
    current_studies: dict[str, dict[str, list[Dataset]]],
    subwindow_managers: dict[int, dict[str, Any]],
    use_rescale: bool,
    dicom_processor: type,
) -> None:
    """
    Write one data row per ROI, crosshair, or measurement.

    ROI rows fill stat columns; crosshair and measurement rows leave ROI stats blank.
    Trailing columns hold per-channel ROI stats (when present) then distance/angle fields.
    """
    roi_manager = resolve_export_roi_manager(subwindow_managers)
    row_payloads, max_channel_count, label_ref_dataset, headers = collect_csv_row_payloads(
        collected,
        current_studies,
        roi_manager,
        use_rescale,
        dicom_processor,
    )
    rows = finalize_csv_rows(
        row_payloads,
        headers=headers,
        max_channel_count=max_channel_count,
        label_ref_dataset=label_ref_dataset,
    )

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
