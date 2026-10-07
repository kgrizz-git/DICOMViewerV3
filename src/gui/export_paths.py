"""
Export path naming shared by the overwrite preview and the export itself.

Requirements: pydicom (Dataset).
"""

from __future__ import annotations

import os
from typing import Any

from pydicom.dataset import Dataset

from core.projection_dicom_export import projection_folder_dataset


def sanitize_name(name: Any) -> str:
    text = str(name)
    for char in '<>:"/\\|?*':
        text = text.replace(char, "_")
    text = text.replace(" ", "_").strip(". ")
    return text or "UNKNOWN"


def series_directory(output_dir: str, folder_dataset: Dataset) -> str:
    """Patient ID / Study Date-Description / Series Number-Description directory."""
    clean = sanitize_name
    series_number = getattr(folder_dataset, "SeriesNumber", None)
    if series_number is None or series_number == "":
        series_number = "UNKNOWN_SERIES_NUM"
    elif isinstance(series_number, (int, float)):
        series_number = str(int(series_number))
    study_dir = os.path.join(
        output_dir,
        clean(getattr(folder_dataset, "PatientID", "UNKNOWN_PATIENT")),
        f"{clean(getattr(folder_dataset, 'StudyDate', 'UNKNOWN_DATE'))}-"
        f"{clean(getattr(folder_dataset, 'StudyDescription', 'UNKNOWN_STUDY'))}",
    )
    return os.path.join(
        study_dir,
        f"{clean(series_number)}-"
        f"{clean(getattr(folder_dataset, 'SeriesDescription', 'UNKNOWN_SERIES'))}",
    )


def export_filename(
    instance_num: Any, export_format: str, projection_enabled: bool,
    projection_type: str, projection_slice_count: int,
) -> str:
    suffix = ""
    if projection_enabled:
        suffix = f"_{projection_type.upper()}_{projection_slice_count}slices"
    extension = {"DICOM": "dcm", "PNG": "png"}.get(export_format, "jpg")
    return f"Instance_{instance_num:04d}{suffix}.{extension}"


def instance_number_for(
    position: int, output_dataset: Dataset, slice_index: int, projection_dicom: bool
) -> Any:
    """Projection DICOM files are numbered 1..N within the derived series."""
    if projection_dicom:
        return position
    return getattr(output_dataset, "InstanceNumber", slice_index + 1)


def series_folder_dataset(
    study_uid: str,
    series_uid: str,
    items: list[tuple[int, Dataset]],
    pre_anonymized: dict[tuple[str, str, int], Dataset],
    deep_dicom: bool,
    projection_anon: bool,
    projection_type: str | None = None,
) -> Dataset | None:
    """Dataset whose tags name the series folder; None when nothing is written."""
    if projection_anon:
        for slice_index, _ in items:
            built = pre_anonymized.get((study_uid, series_uid, slice_index))
            if built is not None:
                return built
        return None
    first_index, first_dataset = items[0]
    if projection_type is not None:
        # Non-anonymized projection DICOM: name the folder after the derived series.
        return projection_folder_dataset(first_dataset, projection_type)
    if deep_dicom:
        return pre_anonymized.get((study_uid, series_uid, first_index), first_dataset)
    return first_dataset
