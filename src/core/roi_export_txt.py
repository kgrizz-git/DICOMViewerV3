"""
TXT report writers for ROI / crosshair / measurement export.

Extracted from ``roi_export_service.write_txt`` to clear Sonar ``python:S3776``
(cognitive complexity) while preserving series → slice → annotation layout,
area unit thresholds, and multichannel lines.

Inputs:
    - Collected series/slice annotation tuples
    - DICOM datasets and optional ROI manager for statistics

Outputs:
    - UTF-8 text file with section headers and key-value lines

Requirements:
    - ``core.roi_export_service`` helpers for stats / crosshair / measurements
    - ``core.roi_export_xlsx.resolve_export_roi_manager`` for manager lookup
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydicom.dataset import Dataset

from core.dicom_color import multichannel_axis_labels
from core.roi_export_xlsx import resolve_export_roi_manager

# Late-bound helpers from roi_export_service (avoid circular import at load).


def _svc():
    """Late-bind service helpers without a static import cycle for basedpyright."""
    import importlib

    return importlib.import_module("core.roi_export_service")


def txt_area_line(area_mm2: float | int | None, area_px_f: float) -> str:
    """
    Format one Area line for TXT export (cm² / mm² / pixels).

    Threshold matches prior ``write_txt``: ``area_mm2 >= 100.0`` → cm².
    """
    if area_mm2 is not None:
        area_mm2_f = float(area_mm2)
        if area_mm2_f >= 100.0:
            area_cm2 = area_mm2_f / 100.0
            return f"    Area       {area_cm2:.2f}    cm²"
        return f"    Area       {area_mm2_f:.2f}    mm²"
    return f"    Area       {area_px_f:.1f}    pixels"


def txt_roi_statistics_lines(
    *,
    roi_item: Any,
    dataset: Dataset,
    use_rescale: bool,
    roi_manager: Any,
    dicom_processor: type,
) -> list[str]:
    """Append mean/std/min/max/pixels/area and optional per-channel lines."""
    svc = _svc()
    stats, rescale_unit = svc.compute_roi_statistics(
        roi_item, dataset, use_rescale, roi_manager, dicom_processor
    )
    unit_str = rescale_unit or ""
    mean_v = stats.get("mean")
    std_v = stats.get("std")
    min_v = stats.get("min")
    max_v = stats.get("max")
    count_v = stats.get("count")
    area_px_v = stats.get("area_pixels")

    mean_f = float(mean_v) if mean_v is not None else 0.0
    std_f = float(std_v) if std_v is not None else 0.0
    min_f = float(min_v) if min_v is not None else 0.0
    max_f = float(max_v) if max_v is not None else 0.0
    count_i = int(count_v) if count_v is not None else 0
    area_px_f = float(area_px_v) if area_px_v is not None else 0.0

    lines = [
        f"    Mean       {mean_f:.2f}    {unit_str}",
        f"    Std Dev    {std_f:.2f}    {unit_str}",
        f"    Min        {min_f:.2f}    {unit_str}",
        f"    Max        {max_f:.2f}    {unit_str}",
        f"    Pixels     {count_i}    ",
        txt_area_line(stats.get("area_mm2"), area_px_f),
    ]

    channel_count, channel_values = svc._extract_channel_stats(stats)
    ch_labels = multichannel_axis_labels(dataset, channel_count)
    for c in range(channel_count):
        lab = ch_labels[c]
        lines.extend(
            [
                f"    {lab} Mean   {channel_values.get(f'mean_ch{c}', '')}    {unit_str}",
                f"    {lab} Std    {channel_values.get(f'std_ch{c}', '')}    {unit_str}",
                f"    {lab} Min    {channel_values.get(f'min_ch{c}', '')}    {unit_str}",
                f"    {lab} Max    {channel_values.get(f'max_ch{c}', '')}    {unit_str}",
            ]
        )
    return lines


def txt_crosshair_block_lines(cross_item: Any, cross_idx: int, dataset: Dataset | None) -> list[str]:
    """Human-readable lines for one crosshair in TXT export."""
    lines = [f"  Crosshair {cross_idx}"]
    if dataset:
        svc = _svc()
        data = svc.get_crosshair_export_data(cross_item, dataset)
        lines.extend(
            [
                f"    Pixel X        {data.get('pixel_x', '')}    ",
                f"    Pixel Y        {data.get('pixel_y', '')}    ",
                f"    Slice Index    {data.get('slice_index', '')}    ",
                f"    Pixel Value    {data.get('pixel_value_str', '')}    ",
                f"    Patient X (mm) {svc._format_float(data.get('patient_x'))}    ",
                f"    Patient Y (mm) {svc._format_float(data.get('patient_y'))}    ",
                f"    Patient Z (mm) {svc._format_float(data.get('patient_z'))}    ",
            ]
        )
    lines.append("")
    return lines


def write_txt_slice_annotations(
    lines: list[str],
    *,
    z: int,
    rois: list[Any],
    crosshairs: list[Any],
    measurements: list[Any],
    series_dict: list[Dataset],
    roi_manager: Any,
    use_rescale: bool,
    dicom_processor: type,
    subsep: str,
) -> None:
    """Append one slice header plus ROI / crosshair / measurement blocks."""
    dataset = series_dict[z] if z < len(series_dict) else None
    lines.append(f"  Slice Index (0-based): {z}")
    lines.append(subsep)

    for roi_idx, roi_item in enumerate(rois, start=1):
        shape = getattr(roi_item, "shape_type", "ellipse").capitalize()
        lines.append(f"  {shape} ROI {roi_idx}")
        if dataset and roi_manager:
            lines.extend(
                txt_roi_statistics_lines(
                    roi_item=roi_item,
                    dataset=dataset,
                    use_rescale=use_rescale,
                    roi_manager=roi_manager,
                    dicom_processor=dicom_processor,
                )
            )
        lines.append("")

    for cross_idx, cross_item in enumerate(crosshairs, start=1):
        lines.extend(txt_crosshair_block_lines(cross_item, cross_idx, dataset))

    svc = _svc()
    for meas_idx, m_item in enumerate(measurements, start=1):
        lines.extend(svc.measurement_txt_block_lines(m_item, meas_idx))


def write_txt_series_block(
    lines: list[str],
    *,
    study_uid: str,
    series_uid: str,
    slice_list: list[Any],
    current_studies: dict[str, dict[str, list[Dataset]]],
    roi_manager: Any,
    use_rescale: bool,
    dicom_processor: type,
    sep: str,
    subsep: str,
) -> None:
    """Append one series header and its slices (skip when series not loaded)."""
    svc = _svc()
    series_dict = current_studies.get(study_uid, {}).get(series_uid, [])
    if not series_dict:
        return

    first_ds = series_dict[0]
    series_num = getattr(first_ds, "SeriesNumber", "")
    series_desc = getattr(
        first_ds, svc._TAG_SERIES_DESCRIPTION, svc._DEFAULT_UNKNOWN_SERIES
    )
    lines.extend([sep, f"Series {series_num}: {series_desc}", sep])

    if not slice_list:
        lines.extend(["  No annotations", ""])
        return

    for z, rois, crosshairs, measurements in slice_list:
        write_txt_slice_annotations(
            lines,
            z=z,
            rois=rois,
            crosshairs=crosshairs,
            measurements=measurements,
            series_dict=series_dict,
            roi_manager=roi_manager,
            use_rescale=use_rescale,
            dicom_processor=dicom_processor,
            subsep=subsep,
        )
    lines.append("")


def write_txt_report(
    file_path: str,
    collected: list[Any],
    current_studies: dict[str, dict[str, list[Dataset]]],
    subwindow_managers: dict[int, dict[str, Any]],
    use_rescale: bool,
    dicom_processor: type,
) -> None:
    """
    Write export in TXT format: series header, slice header, ROI/crosshair sections.

    Skips slices with no annotations. Labels z as "Slice Index (0-based)".
    """
    roi_manager = resolve_export_roi_manager(subwindow_managers)

    lines: list[str] = []
    sep = "=" * 60
    subsep = "-" * 40

    for (study_uid, series_uid), slice_list in collected:
        write_txt_series_block(
            lines,
            study_uid=study_uid,
            series_uid=series_uid,
            slice_list=slice_list,
            current_studies=current_studies,
            roi_manager=roi_manager,
            use_rescale=use_rescale,
            dicom_processor=dicom_processor,
            sep=sep,
            subsep=subsep,
        )

    Path(file_path).write_text("\n".join(lines), encoding="utf-8")
