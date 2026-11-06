"""
Export path naming shared by the overwrite preview and the export itself.

Includes slab-width checks aligned with ``create_projection_for_export`` (gui.export_rendering)
so PNG/JPG preview paths and on-disk names omit ``_MIP_`` / ``_AIP_`` / ``_MINIP_`` when no
projection image can be built.

Requirements: pydicom (Dataset).
"""

from __future__ import annotations

import os
from typing import Any

from pydicom.dataset import Dataset

from core.projection_dicom_export import (
    create_projection_dataset,
    projection_folder_dataset,
    save_projection_dataset,
)


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
    instance_num: Any,
    export_format: str,
    projection_enabled: bool,
    projection_type: str,
    projection_slice_count: int,
) -> str:
    suffix = ""
    if projection_enabled:
        suffix = f"_{projection_type.upper()}_{projection_slice_count}slices"
    extension = {"DICOM": "dcm", "PNG": "png"}.get(export_format, "jpg")
    return f"Instance_{instance_num:04d}{suffix}.{extension}"


def export_projection_slab_is_buildable(
    studies: dict[str, dict[str, list[Any]]],
    study_uid: str,
    series_uid: str,
    slice_index: int,
    projection_slice_count: int,
) -> bool:
    """Return True when ``create_projection_for_export`` would use a multi-slice slab."""
    if study_uid not in studies or series_uid not in studies[study_uid]:
        return False
    series_datasets = studies[study_uid][series_uid]
    total_slices = len(series_datasets)
    if total_slices < 2:
        return False
    start_slice = max(0, slice_index)
    end_slice = min(total_slices - 1, slice_index + projection_slice_count - 1)
    return end_slice - start_slice + 1 >= 2


def projection_suffix_for_preview_path(
    projection_enabled: bool,
    export_format: str,
    studies: dict[str, dict[str, list[Any]]] | None,
    study_uid: str,
    series_uid: str,
    slice_index: int,
    projection_slice_count: int,
) -> bool:
    """Whether the overwrite preview includes a projection token for this item.

    When ``studies`` is None, DICOM keeps the legacy projection token. PNG and
    JPG omit it, matching the file ``export_selected`` writes: without
    ``studies`` that file is one slice and must not use a projection name.
    When ``studies`` is set, PNG/JPG paths use the slab rule; DICOM preview
    naming is unchanged.
    """
    if not projection_enabled:
        return False
    if studies is None:
        return export_format not in ("PNG", "JPG")
    if export_format not in ("PNG", "JPG"):
        return True
    return export_projection_slab_is_buildable(
        studies, study_uid, series_uid, slice_index, projection_slice_count
    )


def png_jpg_projection_filename_for_disk(
    projection_enabled: bool,
    export_format: str,
    studies: dict[str, dict[str, list[Any]]] | None,
    study_uid: str | None,
    series_uid: str | None,
    slice_index: int | None,
    projection_slice_count: int,
) -> bool:
    """Whether on-disk ``export_filename`` should include a projection token.

    PNG/JPG omit the suffix when the slab cannot be built or ``studies`` is missing.
    DICOM keeps the projection suffix whenever projection is enabled (fail-closed
    naming unchanged).
    """
    if not projection_enabled:
        return False
    if export_format not in ("PNG", "JPG"):
        return True
    if not (studies and study_uid and series_uid and slice_index is not None):
        return False
    return export_projection_slab_is_buildable(
        studies, study_uid, series_uid, slice_index, projection_slice_count
    )


def png_jpg_fallback_output_path(
    projection_output_path: str, single_slice_basename: str | None
) -> str:
    """When projection rasterization falls back to one slice, use non-projection basename."""
    if single_slice_basename is None:
        return projection_output_path
    return os.path.join(os.path.dirname(projection_output_path), single_slice_basename)


def append_png_jpg_fallback_preview_path(
    paths: list[str],
    series_dir: str,
    instance_num: int,
    export_format: str,
    projection_type: str,
    projection_slice_count: int,
    *,
    use_projection_suffix: bool,
    studies: dict[str, dict[str, list[Any]]] | None,
    study_uid: str,
    series_uid: str,
    slice_index: int,
) -> None:
    """Also list the single-slice path a buildable PNG/JPG slab may fall back to.

    ``export_slice`` keeps the projection name when the slab renders, and
    rewrites to this basename when rendering returns no image. The overwrite
    prompt has to see both.
    """
    if not use_projection_suffix or export_format not in ("PNG", "JPG") or studies is None:
        return
    if not export_projection_slab_is_buildable(
        studies, study_uid, series_uid, slice_index, projection_slice_count
    ):
        return
    fallback_name = export_filename(
        instance_num, export_format, False, projection_type, projection_slice_count
    )
    paths.append(os.path.join(series_dir, fallback_name))


def append_export_preview_paths(
    paths: list[str],
    items_by_study_series: dict[tuple[str, str], list[tuple[int, Dataset]]],
    output_dir: str,
    export_format: str,
    projection_enabled: bool,
    projection_type: str,
    projection_slice_count: int,
    studies: dict[str, dict[str, list[Dataset]]] | None,
    deep_dicom: bool,
    projection_dicom: bool,
    projection_anon: bool,
    pre_anonymized: dict[tuple[str, str, int], Dataset],
) -> None:
    """Extend ``paths`` with one absolute path per item (overwrite-preview contract)."""
    for (study_uid, series_uid), items in items_by_study_series.items():
        folder_dataset = series_folder_dataset(
            study_uid,
            series_uid,
            items,
            pre_anonymized,
            deep_dicom,
            projection_anon,
            projection_type if projection_dicom else None,
        )
        if folder_dataset is None:
            continue
        series_dir = series_directory(output_dir, folder_dataset)
        for position, (slice_index, dataset) in enumerate(items, start=1):
            slice_key = (study_uid, series_uid, slice_index)
            if projection_anon and slice_key not in pre_anonymized:
                continue
            output_dataset = pre_anonymized.get(slice_key, dataset)
            instance_num = instance_number_for(
                position, output_dataset, slice_index, projection_dicom
            )
            use_projection_suffix = projection_suffix_for_preview_path(
                projection_enabled,
                export_format,
                studies,
                study_uid,
                series_uid,
                slice_index,
                projection_slice_count,
            )
            filename = export_filename(
                instance_num,
                export_format,
                use_projection_suffix,
                projection_type,
                projection_slice_count,
            )
            paths.append(os.path.join(series_dir, filename))
            append_png_jpg_fallback_preview_path(
                paths,
                series_dir,
                instance_num,
                export_format,
                projection_type,
                projection_slice_count,
                use_projection_suffix=use_projection_suffix,
                studies=studies,
                study_uid=study_uid,
                series_uid=series_uid,
                slice_index=slice_index,
            )


def reported_export_basename(resolved_output_path: str | None, output_path: str) -> str:
    """Basename for a downgrade notice. Prefer the path actually written."""
    path = output_path
    if resolved_output_path:
        path = resolved_output_path
    return os.path.basename(path)


def write_export_dicom_slice(request: Any) -> bool:
    """Write one DICOM slice or projection (fail-closed when projection cannot be built).

    ``request`` is an ``ExportSliceRequest``. It is typed as ``Any`` so this
    module does not import ``export_manager``.
    """
    dataset = request.dataset
    output_path = request.output_path
    if request.prebuilt_projection is not None:
        save_projection_dataset(request.prebuilt_projection, output_path)
        return True
    studies = request.studies
    if not (
        request.projection_enabled
        and studies
        and request.study_uid
        and request.series_uid
        and request.slice_index is not None
    ):
        dataset.save_as(output_path)
        return True
    if request.dataset_pre_anonymized:
        return False  # fail closed: never build from raw source and write it
    projection_dataset = create_projection_dataset(
        dataset,
        studies,
        request.study_uid,
        request.series_uid,
        request.slice_index,
        request.projection_type,
        request.projection_slice_count,
        request.use_rescaled_values,
        new_series_uid=request.projection_series_uid,
        instance_number=request.projection_instance_number,
    )
    if projection_dataset is None:
        return False
    save_projection_dataset(projection_dataset, output_path)
    return True


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
