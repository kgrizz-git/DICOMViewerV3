"""
Pure helpers for the series navigator (study labels, instance grouping).

No Qt dependencies. Used by gui.series_navigator.SeriesNavigator.

Inputs: pydicom Dataset lists.
Outputs: Display strings and (slice_index, dataset, label) tuples.
Requirements: pydicom.
"""

from typing import List, Tuple

from pydicom.dataset import Dataset


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
