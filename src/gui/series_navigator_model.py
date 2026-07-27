"""
Pure helpers for the series navigator (study labels, instance grouping).

No Qt dependencies. Used by gui.series_navigator.SeriesNavigator.

Inputs: pydicom Dataset lists.
Outputs: Display strings and (slice_index, dataset, label) tuples.
Requirements: pydicom.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydicom.dataset import Dataset

# Must match ``DICOMParser.get_all_tags`` / overlay privacy display when masking
# patient-related values (group 0010 only in ``is_patient_tag``).
PRIVACY_TAG_DISPLAY_VALUE = "PRIVACY MODE"


def study_label_from_dataset(dataset: Dataset) -> str:
    """
    Extract study label from a dataset.

    Returns StudyDescription if present, otherwise truncated StudyInstanceUID.
    """
    study_desc = getattr(dataset, "StudyDescription", None)
    if study_desc and str(study_desc).strip():
        desc_str = str(study_desc).strip()
        if len(desc_str) > 30:
            return desc_str[:27] + "..."
        return desc_str

    study_uid = getattr(dataset, "StudyInstanceUID", None)
    if study_uid:
        uid_str = str(study_uid)
        if len(uid_str) > 30:
            return uid_str[:27] + "..."
        return uid_str

    return "Unknown Study"


def format_study_date(value: object, *, unknown: str = "Unknown") -> str:
    """
    Format DICOM StudyDate (typically DA as YYYYMMDD) for navigator tooltips.

    Returns ``YYYY-MM-DD`` when the value is an 8-digit calendar date that
    passes ``datetime.date`` validation; otherwise returns the stripped raw
    string, or *unknown* when missing/empty.
    """
    if value is None:
        return unknown
    raw = str(value).strip()
    if not raw:
        return unknown
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) >= 8:
        y_s, m_s, d_s = digits[0:4], digits[4:6], digits[6:8]
        try:
            yi, mi, di = int(y_s, 10), int(m_s, 10), int(d_s, 10)
            date(yi, mi, di)
            return f"{y_s}-{m_s}-{d_s}"
        except ValueError:
            pass
    return raw


def safe_dicom_attribute_text(
    dataset: Dataset,
    attribute_name: str,
    *,
    unknown: str = "Unknown",
) -> str:
    """
    Return a single-line display string for *dataset*'s *attribute_name*.

    PersonName and other non-scalars are converted with ``str()``; empty
    results map to *unknown*.
    """
    if not hasattr(dataset, attribute_name):
        return unknown
    elem = getattr(dataset, attribute_name, None)
    if elem is None:
        return unknown
    text = str(elem).strip()
    return text if text else unknown


def format_patient_name_for_tooltip(value: object, *, privacy_mode: bool) -> str:
    """Patient name line for tooltips; matches metadata privacy string when enabled."""
    if privacy_mode:
        return PRIVACY_TAG_DISPLAY_VALUE
    if value is None:
        return "Unknown"
    text = str(value).strip()
    return text if text else "Unknown"


def build_study_navigator_tooltip(dataset: Dataset, *, privacy_mode: bool) -> str:
    """
    Plain-text tooltip body for a study label (study + patient fields).

    Study / series descriptions are left cleartext in privacy mode so behavior
    matches ``DICOMParser.get_all_tags`` (only group ``0010`` is masked there).
    """
    study_desc = safe_dicom_attribute_text(dataset, "StudyDescription")
    study_date = format_study_date(getattr(dataset, "StudyDate", None))
    patient = format_patient_name_for_tooltip(
        getattr(dataset, "PatientName", None),
        privacy_mode=privacy_mode,
    )
    return (
        f"Study description: {study_desc}\n"
        f"Study date: {study_date}\n"
        f"Patient name: {patient}"
    )


def build_series_navigator_tooltip(dataset: Dataset, *, privacy_mode: bool) -> str:
    """Series thumbnail tooltip: study block plus series description."""
    series_desc = safe_dicom_attribute_text(dataset, "SeriesDescription")
    return build_study_navigator_tooltip(dataset, privacy_mode=privacy_mode) + (
        f"\nSeries description: {series_desc}"
    )


def build_instance_navigator_tooltip(
    series_first_dataset: Dataset,
    instance_label: str,
    *,
    privacy_mode: bool,
) -> str:
    """Per-instance thumbnail: full series tooltip plus an instance label line."""
    base = build_series_navigator_tooltip(series_first_dataset, privacy_mode=privacy_mode)
    label = (instance_label or "").strip() or "Unknown"
    return f"{base}\nInstance: {label}"


def build_instance_entries_for_navigator(
    datasets: list[Dataset],
) -> list[tuple[int, Dataset, str]]:
    """Return one entry per original instance in a flattened series list."""
    entries: list[tuple[int, Dataset, str]] = []
    seen_original_ids: set[int] = set()
    used_instance_numbers: set[str] = set()
    ordinal = 1

    for slice_index, dataset in enumerate(datasets):
        original_dataset = getattr(dataset, "_original_dataset", dataset)
        original_id = id(original_dataset)
        if original_id in seen_original_ids:
            continue
        seen_original_ids.add(original_id)

        instance_number = getattr(original_dataset, "InstanceNumber", None)
        label = None
        if instance_number is not None:
            instance_number_str = str(instance_number).strip()
            if instance_number_str and instance_number_str not in used_instance_numbers:
                label = f"I{instance_number_str}"
                used_instance_numbers.add(instance_number_str)
        if not label:
            label = f"#{ordinal}"

        entries.append((slice_index, dataset, label))
        ordinal += 1

    return entries


def first_nonempty_series_dataset(
    study_series: dict[str, list[Dataset]],
) -> Dataset | None:
    """Return the first dataset from the first non-empty series, if any."""
    for datasets in study_series.values():
        if datasets:
            return datasets[0]
    return None


def sorted_series_entries(
    study_series: dict[str, list[Dataset]],
) -> list[tuple[int, str, Dataset]]:
    """
    Build ``(series_number, series_uid, first_dataset)`` rows sorted by series number.

    Empty series are omitted. Non-integer SeriesNumber values sort as ``0``.
    """
    series_list: list[tuple[int, str, Dataset]] = []
    for series_uid, datasets in study_series.items():
        if not datasets:
            continue
        first_dataset = datasets[0]
        series_number = getattr(first_dataset, "SeriesNumber", None)
        try:
            series_num = int(series_number) if series_number is not None else 0
        except (ValueError, TypeError):
            series_num = 0
        series_list.append((series_num, series_uid, first_dataset))
    series_list.sort(key=lambda row: row[0])
    return series_list


def series_thumbnail_display_label(first_dataset: Dataset, series_num: int) -> str:
    """
    Human-readable series thumbnail caption.

    Prefer SeriesDescription (truncated); else Modality + series number; else ``S{n}``.
    """
    desc = getattr(first_dataset, "SeriesDescription", None)
    modality = getattr(first_dataset, "Modality", None)
    if desc and str(desc).strip():
        label_raw = str(desc).strip()
        return label_raw[:16] + "…" if len(label_raw) > 16 else label_raw
    if modality:
        return f"{str(modality).strip()} S{series_num}"
    return f"S{series_num}"


def compute_study_section_width(
    series_list: list[tuple[int, str, Dataset]],
    study_uid: str,
    *,
    show_instances_separately: bool,
    multiframe_info_map: dict[tuple[str, str], Any],
    mpr_thumbnail_specs: dict[Any, dict[str, Any]],
    thumbnail_width: int = 68,
    thumbnail_spacing: int = 5,
    instance_thumbnail_width: int = 48,
    instance_spacing: int = 4,
) -> int:
    """
    Pixel width for one study section from visible thumbnail groups and MPR slots.

    When no series contribute width, returns *thumbnail_width* as a minimum.
    """
    section_width = 0
    for _, series_uid, _ in series_list:
        group_width = thumbnail_width
        multiframe_info = multiframe_info_map.get((study_uid, series_uid))
        if (
            show_instances_separately
            and multiframe_info is not None
            and multiframe_info.instance_count > 1
            and multiframe_info.max_frame_count > 1
        ):
            instance_count = multiframe_info.instance_count
            group_width += (
                instance_spacing
                + (instance_count * instance_thumbnail_width)
                + ((instance_count - 1) * instance_spacing)
            )
        if section_width > 0:
            section_width += thumbnail_spacing
        section_width += group_width
        mpr_count = sum(
            1
            for spec in mpr_thumbnail_specs.values()
            if spec.get("study_uid") == study_uid
            and spec.get("source_series_uid") == series_uid
        )
        if mpr_count > 0:
            section_width += mpr_count * (thumbnail_spacing + thumbnail_width)
    if section_width <= 0:
        return thumbnail_width
    return section_width
