"""
ROI Export Service

Aggregates ROI, crosshair, and distance/angle measurement data from all subwindows,
recomputes ROI statistics per slice, and writes TXT, CSV, or XLSX export files.

Inputs:
    - current_studies: {study_uid: {series_uid: [Dataset]}}
    - subwindow_managers: {idx: {'roi_manager', 'crosshair_manager', 'measurement_tool', ...}}
    - selected_series: list of (study_uid, series_uid)
    - use_rescale: whether to use rescale slope/intercept (e.g. HU)
    - file path and format (TXT, CSV, XLSX)

Outputs:
    - Written files (TXT, CSV, or XLSX) with series → slice → ROI/crosshair/measurement hierarchy

Requirements:
    - core.dicom_processor.DICOMProcessor (get_pixel_array, get_rescale_parameters)
    - utils.dicom_utils (get_pixel_spacing, pixel_to_patient_coordinates)
    - tools.roi_manager.ROIManager.calculate_statistics (stateless per call)
    - tools.measurement_items.MeasurementItem, tools.angle_measurement_items.AngleMeasurementItem
    - openpyxl for XLSX, csv for CSV
"""

from __future__ import annotations

import math
import re
from typing import Any

from pydicom.dataset import Dataset

from core.dicom_processor import DICOMProcessor
from tools.angle_measurement_items import AngleMeasurementItem
from tools.measurement_items import MeasurementItem
from utils.dicom_utils import get_pixel_spacing, pixel_to_patient_coordinates

# Type aliases for keys and data structures
SeriesKey = tuple[str, str]  # (study_uid, series_uid)
SliceData = tuple[int, list[Any], list[Any], list[Any]]  # (z, rois, crosshairs, measurements)
CollectedSeries = list[tuple[SeriesKey, list[SliceData]]]

# Trailing CSV columns for distance/angle rows (ROI and crosshair rows leave these blank).
MEASUREMENT_CSV_HEADERS: list[str] = [
    "Measurement Type",
    "Measurement Index",
    "Distance (mm)",
    "Distance (pixels)",
    "Angle (degrees)",
    "Measurement display",
    "P1 scene X",
    "P1 scene Y",
    "P2 scene X",
    "P2 scene Y",
    "P3 scene X",
    "P3 scene Y",
]



_TAG_SERIES_DESCRIPTION = "SeriesDescription"
_DEFAULT_UNKNOWN_SERIES = "Unknown Series"

def _sanitize_filename(s: str) -> str:
    """Replace characters invalid in filenames with underscore."""
    return re.sub(r'[/\\:*?"<>|]', '_', s).strip()


def collect_roi_data(
    selected_series: list[SeriesKey],
    current_studies: dict[str, dict[str, list[Dataset]]],
    subwindow_managers: dict[int, dict[str, Any]],
) -> CollectedSeries:
    """
    Collect ROI, crosshair, and measurement items for selected series from all subwindow managers.

    For each (study_uid, series_uid), for each slice index z in the series,
    aggregates all ROIItem, CrosshairItem, and measurement graphics items from every
    subwindow's roi_manager, crosshair_manager, and measurement_tool using key
    (study_uid, series_uid, z). No deduplication: each subwindow holds separate instances.

    Args:
        selected_series: List of (study_uid, series_uid) to export.
        current_studies: App studies dict {study_uid: {series_uid: [datasets]}}.
        subwindow_managers: Dict of {idx: {'roi_manager', 'crosshair_manager', 'measurement_tool', ...}}.

    Returns:
        List of ((study_uid, series_uid), [(z, rois, crosshairs, measurements), ...]) where each
        slice tuple is kept only if at least one of rois, crosshairs, or measurements is non-empty.
    """
    result: CollectedSeries = []

    for study_uid, series_uid in selected_series:
        series_dict = current_studies.get(study_uid, {}).get(series_uid)
        if not series_dict:
            continue
        num_slices = len(series_dict)
        slice_data_list: list[SliceData] = []

        for z in range(num_slices):
            key = (study_uid, series_uid, z)
            rois: list[Any] = []
            crosshairs: list[Any] = []
            measurements: list[Any] = []

            for idx in sorted(subwindow_managers.keys()):
                managers = subwindow_managers[idx]
                roi_mgr = managers.get("roi_manager")
                crosshair_mgr = managers.get("crosshair_manager")
                meas_tool = managers.get("measurement_tool")
                if roi_mgr and hasattr(roi_mgr, "rois"):
                    rois.extend(roi_mgr.rois.get(key, []))
                if crosshair_mgr and hasattr(crosshair_mgr, "crosshairs"):
                    crosshairs.extend(crosshair_mgr.crosshairs.get(key, []))
                if meas_tool is not None and hasattr(meas_tool, "get_measurements_for_slice"):
                    measurements.extend(
                        meas_tool.get_measurements_for_slice(study_uid, series_uid, z)
                    )

            if rois or crosshairs or measurements:
                slice_data_list.append((z, rois, crosshairs, measurements))

        # Include every selected series (even with no annotations) per plan E14
        result.append(((study_uid, series_uid), slice_data_list))

    return result


def compute_roi_statistics(
    roi_item: Any,
    dataset: Dataset,
    use_rescale: bool,
    roi_manager: Any,
    dicom_processor: type,
) -> tuple[dict[str, float | int | None], str | None]:
    """
    Recompute ROI statistics for an ROI item (never use roi_item.statistics cache).

    calculate_statistics does not use manager-level state; any ROIManager instance is fine.

    Args:
        roi_item: ROIItem with shape_type, get_bounds, get_mask.
        dataset: DICOM dataset for the slice.
        use_rescale: If True, use rescale slope/intercept for values (e.g. HU).
        roi_manager: Any ROIManager instance to call calculate_statistics.
        dicom_processor: DICOMProcessor class for get_pixel_array, get_rescale_parameters.

    Returns:
        (stats_dict, rescale_unit). rescale_unit is e.g. "HU" or None.
    """
    pixel_array = dicom_processor.get_pixel_array(dataset)
    if pixel_array is None:
        return (
            {
                "mean": 0.0,
                "std": 0.0,
                "min": 0.0,
                "max": 0.0,
                "count": 0,
                "area_pixels": 0.0,
                "area_mm2": None,
            },
            None,
        )

    pixel_spacing = get_pixel_spacing(dataset)
    rescale_slope: float | None = None
    rescale_intercept: float | None = None
    rescale_type: str | None = None

    if use_rescale:
        rescale_slope, rescale_intercept, rescale_type = dicom_processor.get_rescale_parameters(dataset)

    stats = roi_manager.calculate_statistics(
        roi_item,
        pixel_array,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
        pixel_spacing=pixel_spacing,
        dataset=dataset,
    )
    return (stats, rescale_type)


def get_crosshair_export_data(
    crosshair_item: Any,
    dataset: Dataset,
) -> dict[str, Any]:
    """
    Get crosshair data for export: pixel coords, pixel value string, patient coords.

    Uses item.x_coord, item.y_coord, item.z_coord (raw). Does not parse
    item.pixel_value_str for coordinates; patient coords are computed fresh via
    pixel_to_patient_coordinates. If patient coords are unavailable, use None → "N/A" in output.

    Args:
        crosshair_item: CrosshairItem with x_coord, y_coord, z_coord, pixel_value_str.
        dataset: DICOM dataset for the slice.

    Returns:
        Dict with pixel_x, pixel_y, slice_index, pixel_value_str, patient_x, patient_y, patient_z
        (patient_* are float or None).
    """
    # slice_index=0: dataset is the crosshair's slice, so its
    # ImagePositionPatient already encodes the slice z. Passing z_coord here
    # would double-count the out-of-plane offset.
    patient = pixel_to_patient_coordinates(
        dataset,
        crosshair_item.x_coord,
        crosshair_item.y_coord,
        0,
    )
    return {
        "pixel_x": crosshair_item.x_coord,
        "pixel_y": crosshair_item.y_coord,
        "slice_index": crosshair_item.z_coord,
        "pixel_value_str": getattr(crosshair_item, "pixel_value_str", ""),
        "patient_x": patient[0] if patient else None,
        "patient_y": patient[1] if patient else None,
        "patient_z": patient[2] if patient else None,
    }


def _empty_measurement_csv_row() -> list[str]:
    """Blank measurement columns for ROI and crosshair CSV rows."""
    return [""] * len(MEASUREMENT_CSV_HEADERS)


def serialize_measurement_for_export(item: Any, index: int) -> list[str]:
    """
    Build trailing measurement columns for CSV (same order as MEASUREMENT_CSV_HEADERS).

    Scene coordinates are QGraphics scene units (image-plane) at export time.
    """
    empty = _empty_measurement_csv_row()
    idx_str = str(index)

    if isinstance(item, AngleMeasurementItem):
        p1, p2, p3 = item.p1, item.p2, item.p3
        display = getattr(item, "angle_formatted", "") or ""
        deg = float(getattr(item, "angle_degrees", 0.0))
        return [
            "angle",
            idx_str,
            "",
            "",
            f"{deg:.4f}",
            display,
            f"{p1.x():.4f}",
            f"{p1.y():.4f}",
            f"{p2.x():.4f}",
            f"{p2.y():.4f}",
            f"{p3.x():.4f}",
            f"{p3.y():.4f}",
        ]

    if isinstance(item, MeasurementItem):
        dx = item.end_point.x() - item.start_point.x()
        dy = item.end_point.y() - item.start_point.y()
        dist_px = math.sqrt(dx * dx + dy * dy)
        spacing = getattr(item, "pixel_spacing", None)
        dist_mm_str = ""
        if spacing is not None and len(spacing) >= 2:
            dx_scaled = dx * float(spacing[1])
            dy_scaled = dy * float(spacing[0])
            dist_mm = math.sqrt(dx_scaled * dx_scaled + dy_scaled * dy_scaled)
            dist_mm_str = f"{dist_mm:.6f}"
        p1, p2 = item.start_point, item.end_point
        display = getattr(item, "distance_formatted", "") or ""
        return [
            "distance",
            idx_str,
            dist_mm_str,
            f"{dist_px:.6f}",
            "",
            display,
            f"{p1.x():.4f}",
            f"{p1.y():.4f}",
            f"{p2.x():.4f}",
            f"{p2.y():.4f}",
            "",
            "",
        ]

    return empty


def measurement_txt_block_lines(item: Any, index: int) -> list[str]:
    """Human-readable lines for one measurement in TXT export."""
    lines: list[str] = []
    lines.append(f"  Measurement {index}")
    if isinstance(item, AngleMeasurementItem):
        p1, p2, p3 = item.p1, item.p2, item.p3
        lines.append("    Type            Angle")
        lines.append(f"    Display         {getattr(item, 'angle_formatted', '')}")
        lines.append(f"    Angle (deg)     {float(getattr(item, 'angle_degrees', 0.0)):.4f}")
        lines.append(
            f"    P1 scene        ({p1.x():.2f}, {p1.y():.2f})"
        )
        lines.append(
            f"    P2 (vertex)     ({p2.x():.2f}, {p2.y():.2f})"
        )
        lines.append(
            f"    P3 scene        ({p3.x():.2f}, {p3.y():.2f})"
        )
    elif isinstance(item, MeasurementItem):
        dx = item.end_point.x() - item.start_point.x()
        dy = item.end_point.y() - item.start_point.y()
        dist_px = math.sqrt(dx * dx + dy * dy)
        spacing = getattr(item, "pixel_spacing", None)
        lines.append("    Type            Distance")
        lines.append(f"    Display         {getattr(item, 'distance_formatted', '')}")
        if spacing is not None and len(spacing) >= 2:
            dx_scaled = dx * float(spacing[1])
            dy_scaled = dy * float(spacing[0])
            dist_mm = math.sqrt(dx_scaled * dx_scaled + dy_scaled * dy_scaled)
            lines.append(f"    Distance (mm)   {dist_mm:.4f}")
        lines.append(f"    Distance (px)   {dist_px:.4f}")
        lines.append(
            f"    Start scene     ({item.start_point.x():.2f}, {item.start_point.y():.2f})"
        )
        lines.append(
            f"    End scene       ({item.end_point.x():.2f}, {item.end_point.y():.2f})"
        )
    else:
        lines.append("    Type            (unknown)")
    lines.append("")
    return lines


def _measurement_xlsx_label_value_pairs(item: Any) -> list[tuple[str, Any]]:
    """Key/value rows for one measurement in XLSX export (columns 1–2)."""
    pairs: list[tuple[str, Any]] = []
    if isinstance(item, AngleMeasurementItem):
        p1, p2, p3 = item.p1, item.p2, item.p3
        pairs.append(("Type", "Angle"))
        pairs.append(("Display", getattr(item, "angle_formatted", "")))
        pairs.append(("Angle (deg)", round(float(getattr(item, "angle_degrees", 0.0)), 4)))
        pairs.append(("P1 scene X", round(p1.x(), 4)))
        pairs.append(("P1 scene Y", round(p1.y(), 4)))
        pairs.append(("P2 vertex X", round(p2.x(), 4)))
        pairs.append(("P2 vertex Y", round(p2.y(), 4)))
        pairs.append(("P3 scene X", round(p3.x(), 4)))
        pairs.append(("P3 scene Y", round(p3.y(), 4)))
    elif isinstance(item, MeasurementItem):
        dx = item.end_point.x() - item.start_point.x()
        dy = item.end_point.y() - item.start_point.y()
        dist_px = math.sqrt(dx * dx + dy * dy)
        spacing = getattr(item, "pixel_spacing", None)
        pairs.append(("Type", "Distance"))
        pairs.append(("Display", getattr(item, "distance_formatted", "")))
        if spacing is not None and len(spacing) >= 2:
            dx_scaled = dx * float(spacing[1])
            dy_scaled = dy * float(spacing[0])
            dist_mm = math.sqrt(dx_scaled * dx_scaled + dy_scaled * dy_scaled)
            pairs.append(("Distance (mm)", round(dist_mm, 4)))
        pairs.append(("Distance (px)", round(dist_px, 4)))
        pairs.append(("Start scene X", round(item.start_point.x(), 4)))
        pairs.append(("Start scene Y", round(item.start_point.y(), 4)))
        pairs.append(("End scene X", round(item.end_point.x(), 4)))
        pairs.append(("End scene Y", round(item.end_point.y(), 4)))
    else:
        pairs.append(("Type", "unknown"))
    return pairs


def _format_float(v: float | None) -> str:
    if v is None:
        return "N/A"
    return f"{v:.4f}"


def _channel_stat_csv_headers_from_labels(labels: tuple[str, ...]) -> list[str]:
    """CSV column titles for per-channel columns (mean/std/min/max each), given axis labels."""
    out: list[str] = []
    for lab in labels:
        out.extend(
            [
                f"Mean ({lab})",
                f"Std Dev ({lab})",
                f"Min ({lab})",
                f"Max ({lab})",
            ]
        )
    return out


def _extract_channel_stats(
    stats: dict[str, float | int | None],
) -> tuple[int, dict[str, str]]:
    """
    Extract per-channel statistics from ROI stats payload.

    Returns:
        (channel_count, values) where values maps keys like ``mean_ch0`` to
        formatted strings for export.
    """
    channel_count = int(stats.get("multichannel_count") or 0)
    values: dict[str, str] = {}
    for c in range(channel_count):
        for metric in ("mean", "std", "min", "max"):
            k = f"{metric}_ch{c}"
            v = stats.get(k)
            values[k] = f"{float(v):.4f}" if v is not None else ""
    return channel_count, values


def write_txt(
    file_path: str,
    collected: CollectedSeries,
    current_studies: dict[str, dict[str, list[Dataset]]],
    subwindow_managers: dict[int, dict[str, Any]],
    use_rescale: bool,
    dicom_processor: type,
) -> None:
    """
    Write export in TXT format: series header, slice header, ROI/crosshair sections with key-value lines.
    Skips slices with no annotations. Labels z as "Slice Index (0-based)".

    Implementation lives in ``core.roi_export_txt`` (Sonar S3776 complexity slice).
    """
    from core.roi_export_txt import write_txt_report

    write_txt_report(
        file_path,
        collected,
        current_studies,
        subwindow_managers,
        use_rescale,
        dicom_processor,
    )


def write_csv(
    file_path: str,
    collected: CollectedSeries,
    current_studies: dict[str, dict[str, list[Dataset]]],
    subwindow_managers: dict[int, dict[str, Any]],
    use_rescale: bool,
    dicom_processor: type,
) -> None:
    """
    Write one data row per ROI, crosshair, or measurement. Base columns per plan E12.
    ROI rows fill stat columns; crosshair and measurement rows leave ROI stats blank.
    Trailing columns hold per-channel ROI stats (when present) then distance/angle fields.

    Implementation lives in ``core.roi_export_csv`` (Sonar S3776 complexity slice).
    """
    from core.roi_export_csv import write_csv_report

    write_csv_report(
        file_path,
        collected,
        current_studies,
        subwindow_managers,
        use_rescale,
        dicom_processor,
    )


def write_xlsx(
    file_path: str,
    collected: CollectedSeries,
    current_studies: dict[str, dict[str, list[Dataset]]],
    subwindow_managers: dict[int, dict[str, Any]],
    use_rescale: bool,
    dicom_processor: type,
) -> None:
    """
    Write one sheet per study (name from StudyDescription, max 31 chars, sanitized).
    Bold merged series headers, indented slice headers, bold ROI/crosshair headings, data rows.

    Implementation lives in ``core.roi_export_xlsx`` (Sonar S3776 complexity slice).
    """
    from core.roi_export_xlsx import write_xlsx_workbook

    write_xlsx_workbook(
        file_path,
        collected,
        current_studies,
        subwindow_managers,
        use_rescale,
        dicom_processor,
    )


def run_export(
    file_path: str,
    format_key: str,
    selected_series: list[SeriesKey],
    current_studies: dict[str, dict[str, list[Dataset]]],
    subwindow_managers: dict[int, dict[str, Any]],
    use_rescale: bool,
) -> None:
    """
    Run the export: collect data and call the appropriate writer.

    format_key: "TXT", "CSV", or "XLSX".
    Raises on write error (caller should show dialog and keep dialog open).
    """
    collected = collect_roi_data(selected_series, current_studies, subwindow_managers)
    if format_key.upper() == "TXT":
        write_txt(
            file_path,
            collected,
            current_studies,
            subwindow_managers,
            use_rescale,
            DICOMProcessor,
        )
    elif format_key.upper() == "CSV":
        write_csv(
            file_path,
            collected,
            current_studies,
            subwindow_managers,
            use_rescale,
            DICOMProcessor,
        )
    elif format_key.upper() == "XLSX":
        write_xlsx(
            file_path,
            collected,
            current_studies,
            subwindow_managers,
            use_rescale,
            DICOMProcessor,
        )
    else:
        raise ValueError(f"Unsupported format: {format_key}")
