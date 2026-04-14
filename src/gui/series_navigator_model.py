"""
Pure helpers for the series navigator (study labels, instance grouping).

No Qt dependencies. Used by gui.series_navigator.SeriesNavigator.

Inputs: pydicom Dataset lists.
Outputs: Display strings and (slice_index, dataset, label) tuples.
Requirements: pydicom.
"""

from __future__ import annotations

from datetime import date
from typing import List, Tuple

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
    datasets: List[Dataset],
) -> List[Tuple[int, Dataset, str]]:
    """Return one entry per original instance in a flattened series list."""
    entries: List[Tuple[int, Dataset, str]] = []
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
