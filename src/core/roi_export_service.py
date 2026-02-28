"""
ROI Export Service

Aggregates ROI and crosshair data from all subwindows, recomputes ROI statistics
per slice, and writes TXT, CSV, or XLSX export files.

Inputs:
    - current_studies: {study_uid: {series_uid: [Dataset]}}
    - subwindow_managers: {idx: {'roi_manager', 'crosshair_manager', ...}}
    - selected_series: list of (study_uid, series_uid)
    - use_rescale: whether to use rescale slope/intercept (e.g. HU)
    - file path and format (TXT, CSV, XLSX)

Outputs:
    - Written files (TXT, CSV, or XLSX) with series → slice → ROI/crosshair hierarchy

Requirements:
    - core.dicom_processor.DICOMProcessor (get_pixel_array, get_rescale_parameters)
    - utils.dicom_utils (get_pixel_spacing, pixel_to_patient_coordinates)
    - tools.roi_manager.ROIManager.calculate_statistics (stateless per call)
    - openpyxl for XLSX, csv for CSV
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydicom.dataset import Dataset

from core.dicom_processor import DICOMProcessor
from utils.dicom_utils import get_pixel_spacing, pixel_to_patient_coordinates


# Type aliases for keys and data structures
SeriesKey = Tuple[str, str]  # (study_uid, series_uid)
SliceData = Tuple[int, List[Any], List[Any]]  # (z, rois, crosshairs)
CollectedSeries = List[Tuple[SeriesKey, List[SliceData]]]


def _sanitize_filename(s: str) -> str:
    """Replace characters invalid in filenames with underscore."""
    return re.sub(r'[/\\:*?"<>|]', '_', s).strip()


def collect_roi_data(
    selected_series: List[SeriesKey],
    current_studies: Dict[str, Dict[str, List[Dataset]]],
    subwindow_managers: Dict[int, Dict[str, Any]],
) -> CollectedSeries:
    """
    Collect ROI and crosshair items for selected series from all subwindow managers.

    For each (study_uid, series_uid), for each slice index z in the series,
    aggregates all ROIItem and CrosshairItem objects from every subwindow's
    roi_manager and crosshair_manager using key (study_uid, series_uid, z).
    No deduplication: each subwindow holds separate annotation instances.

    Args:
        selected_series: List of (study_uid, series_uid) to export.
        current_studies: App studies dict {study_uid: {series_uid: [datasets]}}.
        subwindow_managers: Dict of {idx: {'roi_manager', 'crosshair_manager', ...}}.

    Returns:
        List of ((study_uid, series_uid), [(z, rois, crosshairs), ...]) where each
        (z, rois, crosshairs) has at least one ROI or crosshair (slices with none are omitted).
    """
    result: CollectedSeries = []

    for study_uid, series_uid in selected_series:
        series_dict = current_studies.get(study_uid, {}).get(series_uid)
        if not series_dict:
            continue
        num_slices = len(series_dict)
        slice_data_list: List[SliceData] = []

        for z in range(num_slices):
            key = (study_uid, series_uid, z)
            rois: List[Any] = []
            crosshairs: List[Any] = []

            for idx in sorted(subwindow_managers.keys()):
                managers = subwindow_managers[idx]
                roi_mgr = managers.get("roi_manager")
                crosshair_mgr = managers.get("crosshair_manager")
                if roi_mgr and hasattr(roi_mgr, "rois"):
                    rois.extend(roi_mgr.rois.get(key, []))
                if crosshair_mgr and hasattr(crosshair_mgr, "crosshairs"):
                    crosshairs.extend(crosshair_mgr.crosshairs.get(key, []))

            if rois or crosshairs:
                slice_data_list.append((z, rois, crosshairs))

        # Include every selected series (even with no annotations) per plan E14
        result.append(((study_uid, series_uid), slice_data_list))

    return result


def compute_roi_statistics(
    roi_item: Any,
    dataset: Dataset,
    use_rescale: bool,
    roi_manager: Any,
    dicom_processor: type,
) -> Tuple[Dict[str, float], Optional[str]]:
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
    rescale_slope: Optional[float] = None
    rescale_intercept: Optional[float] = None
    rescale_type: Optional[str] = None

    if use_rescale:
        rescale_slope, rescale_intercept, rescale_type = dicom_processor.get_rescale_parameters(dataset)

    stats = roi_manager.calculate_statistics(
        roi_item,
        pixel_array,
        rescale_slope=rescale_slope,
        rescale_intercept=rescale_intercept,
        pixel_spacing=pixel_spacing,
    )
    return (stats, rescale_type)


def get_crosshair_export_data(
    crosshair_item: Any,
    dataset: Dataset,
) -> Dict[str, Any]:
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
    patient = pixel_to_patient_coordinates(
        dataset,
        crosshair_item.x_coord,
        crosshair_item.y_coord,
        crosshair_item.z_coord,
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


def _format_float(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:.4f}"


def write_txt(
    file_path: str,
    collected: CollectedSeries,
    current_studies: Dict[str, Dict[str, List[Dataset]]],
    subwindow_managers: Dict[int, Dict[str, Any]],
    use_rescale: bool,
    dicom_processor: type,
) -> None:
    """
    Write export in TXT format: series header, slice header, ROI/crosshair sections with key-value lines.
    Skips slices with no annotations. Labels z as "Slice Index (0-based)".
    """
    roi_manager = None
    for idx in sorted(subwindow_managers.keys()):
        if subwindow_managers[idx].get("roi_manager"):
            roi_manager = subwindow_managers[idx]["roi_manager"]
            break
    if roi_manager is None:
        roi_manager = list(subwindow_managers.values())[0].get("roi_manager") if subwindow_managers else None

    lines: List[str] = []
    sep = "=" * 60
    subsep = "-" * 40

    for (study_uid, series_uid), slice_list in collected:
        series_dict = current_studies.get(study_uid, {}).get(series_uid, [])
        if not series_dict:
            continue
        first_ds = series_dict[0]
        series_num = getattr(first_ds, "SeriesNumber", "")
        series_desc = getattr(first_ds, "SeriesDescription", "Unknown Series")
        lines.append(sep)
        lines.append(f"Series {series_num}: {series_desc}")
        lines.append(sep)
        if not slice_list:
            lines.append("  No annotations")
            lines.append("")
            continue
        for z, rois, crosshairs in slice_list:
            dataset = series_dict[z] if z < len(series_dict) else None
            lines.append(f"  Slice Index (0-based): {z}")
            lines.append(subsep)
            roi_idx = 0
            for roi_item in rois:
                roi_idx += 1
                shape = getattr(roi_item, "shape_type", "ellipse").capitalize()
                lines.append(f"  {shape} ROI {roi_idx}")
                if dataset and roi_manager:
                    stats, rescale_unit = compute_roi_statistics(
                        roi_item, dataset, use_rescale, roi_manager, dicom_processor
                    )
                    unit_str = rescale_unit or ""
                    lines.append(f"    Mean       {stats.get('mean', 0):.2f}    {unit_str}")
                    lines.append(f"    Std Dev    {stats.get('std', 0):.2f}    {unit_str}")
                    lines.append(f"    Min        {stats.get('min', 0):.2f}    {unit_str}")
                    lines.append(f"    Max        {stats.get('max', 0):.2f}    {unit_str}")
                    lines.append(f"    Pixels     {int(stats.get('count', 0))}    ")
                    area_mm2 = stats.get("area_mm2")
                    area_px = stats.get("area_pixels", 0)
                    if area_mm2 is not None:
                        if area_mm2 >= 100.0:
                            area_cm2 = area_mm2 / 100.0
                            lines.append(f"    Area       {area_cm2:.2f}    cm²")
                        else:
                            lines.append(f"    Area       {area_mm2:.2f}    mm²")
                    else:
                        lines.append(f"    Area       {area_px:.1f}    pixels")
                lines.append("")
            cross_idx = 0
            for cross_item in crosshairs:
                cross_idx += 1
                lines.append(f"  Crosshair {cross_idx}")
                if dataset:
                    data = get_crosshair_export_data(cross_item, dataset)
                    lines.append(f"    Pixel X        {data['pixel_x']}    ")
                    lines.append(f"    Pixel Y        {data['pixel_y']}    ")
                    lines.append(f"    Slice Index    {data['slice_index']}    ")
                    lines.append(f"    Pixel Value    {data['pixel_value_str']}    ")
                    lines.append(f"    Patient X (mm) {_format_float(data['patient_x'])}    ")
                    lines.append(f"    Patient Y (mm) {_format_float(data['patient_y'])}    ")
                    lines.append(f"    Patient Z (mm) {_format_float(data['patient_z'])}    ")
                lines.append("")
        lines.append("")

    Path(file_path).write_text("\n".join(lines), encoding="utf-8")


def write_csv(
    file_path: str,
    collected: CollectedSeries,
    current_studies: Dict[str, Dict[str, List[Dataset]]],
    subwindow_managers: Dict[int, Dict[str, Any]],
    use_rescale: bool,
    dicom_processor: type,
) -> None:
    """
    Write one data row per ROI or per crosshair. Columns per plan E12.
    ROI rows fill stat columns and leave coordinate columns blank; crosshair rows do the opposite.
    """
    roi_manager = None
    for idx in sorted(subwindow_managers.keys()):
        if subwindow_managers[idx].get("roi_manager"):
            roi_manager = subwindow_managers[idx]["roi_manager"]
            break
    if roi_manager is None and subwindow_managers:
        roi_manager = list(subwindow_managers.values())[0].get("roi_manager")

    headers = [
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
    rows: List[List[str]] = [headers]

    for (study_uid, series_uid), slice_list in collected:
        series_dict = current_studies.get(study_uid, {}).get(series_uid, [])
        if not series_dict:
            continue
        first_ds = series_dict[0]
        study_uid_short = (study_uid[:36] + "..") if len(study_uid) > 38 else study_uid
        series_num = getattr(first_ds, "SeriesNumber", "")
        series_desc = getattr(first_ds, "SeriesDescription", "Unknown Series")

        for z, rois, crosshairs in slice_list:
            dataset = series_dict[z] if z < len(series_dict) else None
            for roi_idx, roi_item in enumerate(rois, start=1):
                shape = getattr(roi_item, "shape_type", "ellipse")
                row = [
                    study_uid_short,
                    str(series_num),
                    series_desc,
                    str(z),
                    shape,
                    str(roi_idx),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
                if dataset and roi_manager:
                    stats, rescale_unit = compute_roi_statistics(
                        roi_item, dataset, use_rescale, roi_manager, dicom_processor
                    )
                    row[6] = f"{stats.get('mean', 0):.4f}"
                    row[7] = f"{stats.get('std', 0):.4f}"
                    row[8] = f"{stats.get('min', 0):.4f}"
                    row[9] = f"{stats.get('max', 0):.4f}"
                    row[10] = str(int(stats.get("count", 0)))
                    row[11] = f"{stats.get('area_pixels', 0):.1f}"
                    row[12] = f"{stats.get('area_mm2') or ''}"
                    row[13] = rescale_unit or ""
                rows.append(row)

            for cross_item in crosshairs:
                data = get_crosshair_export_data(cross_item, dataset) if dataset else {}
                row = [
                    study_uid_short,
                    str(series_num),
                    series_desc,
                    str(z),
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    str(data.get("pixel_x", "")),
                    str(data.get("pixel_y", "")),
                    str(data.get("slice_index", "")),
                    data.get("pixel_value_str", ""),
                    _format_float(data.get("patient_x")),
                    _format_float(data.get("patient_y")),
                    _format_float(data.get("patient_z")),
                ]
                rows.append(row)

    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)


def write_xlsx(
    file_path: str,
    collected: CollectedSeries,
    current_studies: Dict[str, Dict[str, List[Dataset]]],
    subwindow_managers: Dict[int, Dict[str, Any]],
    use_rescale: bool,
    dicom_processor: type,
) -> None:
    """
    Write one sheet per study (name from StudyDescription, max 31 chars, sanitized).
    Bold merged series headers, indented slice headers, bold ROI/crosshair headings, data rows.
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError as e:
        raise ImportError(
            "openpyxl is required for XLSX export. Install with: pip install openpyxl"
        ) from e

    roi_manager = None
    for idx in sorted(subwindow_managers.keys()):
        if subwindow_managers[idx].get("roi_manager"):
            roi_manager = subwindow_managers[idx]["roi_manager"]
            break
    if roi_manager is None and subwindow_managers:
        roi_manager = list(subwindow_managers.values())[0].get("roi_manager")

    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("Workbook has no active sheet")
    ws.title = "ROI Statistics"[:31]

    bold_font = Font(bold=True)
    row = 1

    for (study_uid, series_uid), slice_list in collected:
        series_dict = current_studies.get(study_uid, {}).get(series_uid, [])
        if not series_dict:
            continue
        first_ds = series_dict[0]
        series_num = getattr(first_ds, "SeriesNumber", "")
        series_desc = getattr(first_ds, "SeriesDescription", "Unknown Series")
        study_desc = getattr(first_ds, "StudyDescription", "Study")[:31]
        study_desc = _sanitize_filename(study_desc) or "Study"

        ws.cell(row=row, column=1, value=f"Series {series_num}: {series_desc}")
        ws.cell(row=row, column=1).font = bold_font
        row += 1

        if not slice_list:
            ws.cell(row=row, column=1, value="No annotations")
            row += 2
            continue

        for z, rois, crosshairs in slice_list:
            dataset = series_dict[z] if z < len(series_dict) else None
            ws.cell(row=row, column=1, value=f"  Slice Index (0-based): {z}")
            row += 1
            for roi_idx, roi_item in enumerate(rois, start=1):
                shape = getattr(roi_item, "shape_type", "ellipse").capitalize()
                ws.cell(row=row, column=1, value=f"  {shape} ROI {roi_idx}")
                ws.cell(row=row, column=1).font = bold_font
                row += 1
                if dataset and roi_manager:
                    stats, rescale_unit = compute_roi_statistics(
                        roi_item, dataset, use_rescale, roi_manager, dicom_processor
                    )
                    unit_str = rescale_unit or ""
                    ws.cell(row=row, column=1, value="Mean"); ws.cell(row=row, column=2, value=round(stats.get('mean', 0), 2)); ws.cell(row=row, column=3, value=unit_str)
                    row += 1
                    ws.cell(row=row, column=1, value="Std Dev"); ws.cell(row=row, column=2, value=round(stats.get('std', 0), 2)); ws.cell(row=row, column=3, value=unit_str)
                    row += 1
                    ws.cell(row=row, column=1, value="Min"); ws.cell(row=row, column=2, value=round(stats.get('min', 0), 2)); ws.cell(row=row, column=3, value=unit_str)
                    row += 1
                    ws.cell(row=row, column=1, value="Max"); ws.cell(row=row, column=2, value=round(stats.get('max', 0), 2)); ws.cell(row=row, column=3, value=unit_str)
                    row += 1
                    ws.cell(row=row, column=1, value="Pixels"); ws.cell(row=row, column=2, value=int(stats.get("count", 0))); ws.cell(row=row, column=3, value="")
                    row += 1
                    area_mm2 = stats.get("area_mm2")
                    area_px = stats.get("area_pixels", 0)
                    if area_mm2 is not None:
                        if area_mm2 >= 100.0:
                            ws.cell(row=row, column=1, value="Area"); ws.cell(row=row, column=2, value=round(area_mm2 / 100.0, 2)); ws.cell(row=row, column=3, value="cm²")
                        else:
                            ws.cell(row=row, column=1, value="Area"); ws.cell(row=row, column=2, value=round(area_mm2, 2)); ws.cell(row=row, column=3, value="mm²")
                    else:
                        ws.cell(row=row, column=1, value="Area"); ws.cell(row=row, column=2, value=area_px); ws.cell(row=row, column=3, value="pixels")
                    row += 1
            for cross_idx, cross_item in enumerate(crosshairs, start=1):
                ws.cell(row=row, column=1, value=f"  Crosshair {cross_idx}")
                ws.cell(row=row, column=1).font = bold_font
                row += 1
                if dataset:
                    data = get_crosshair_export_data(cross_item, dataset)
                    ws.cell(row=row, column=1, value="Pixel X"); ws.cell(row=row, column=2, value=data["pixel_x"]); ws.cell(row=row, column=3, value="")
                    row += 1
                    ws.cell(row=row, column=1, value="Pixel Y"); ws.cell(row=row, column=2, value=data["pixel_y"]); ws.cell(row=row, column=3, value="")
                    row += 1
                    ws.cell(row=row, column=1, value="Slice Index (0-based)"); ws.cell(row=row, column=2, value=data["slice_index"]); ws.cell(row=row, column=3, value="")
                    row += 1
                    ws.cell(row=row, column=1, value="Pixel Value"); ws.cell(row=row, column=2, value=data["pixel_value_str"]); ws.cell(row=row, column=3, value="")
                    row += 1
                    ws.cell(row=row, column=1, value="Patient X (mm)"); ws.cell(row=row, column=2, value=_format_float(data["patient_x"])); ws.cell(row=row, column=3, value="")
                    row += 1
                    ws.cell(row=row, column=1, value="Patient Y (mm)"); ws.cell(row=row, column=2, value=_format_float(data["patient_y"])); ws.cell(row=row, column=3, value="")
                    row += 1
                    ws.cell(row=row, column=1, value="Patient Z (mm)"); ws.cell(row=row, column=2, value=_format_float(data["patient_z"])); ws.cell(row=row, column=3, value="")
                    row += 1
        row += 1

    wb.save(file_path)


def run_export(
    file_path: str,
    format_key: str,
    selected_series: List[SeriesKey],
    current_studies: Dict[str, Dict[str, List[Dataset]]],
    subwindow_managers: Dict[int, Dict[str, Any]],
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
