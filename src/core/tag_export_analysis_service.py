"""
DICOM Tag Export Analysis Service

Analyses which DICOM tags vary across instances within each selected series.
This module is pure logic with no Qt dependency.
"""


from typing import Any

from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser


def analyze_tag_variations(
    studies: dict[str, dict[str, list[Dataset]]],
    selected_series: dict[str, dict[str, list[int]]],
    selected_tags: list[str],
    include_private: bool,
    include_sequences: bool = False,
) -> dict[str, dict[str, list[str]]]:
    """
    Analyze which tags vary across instances within each selected series.

    ``include_sequences`` must match what the writer is given. Without it, an SQ
    tag is absent from every instance's tag dict, so it collects no values and
    falls into the "constant" bucket by default — which would export one value
    per series for a sequence that genuinely differs per instance (e.g.
    SourceImageSequence). Constant-by-invisibility is not constant.

    Args:
        studies: Full studies dict {study_uid: {series_uid: [Dataset, ...]}}
        selected_series: {study_uid: {series_uid: [instance_indices]}}
        selected_tags: List of tag strings selected by the user
        include_private: Whether to include private tags
        include_sequences: Whether SQ parent tags are visible (must match the writer)

    Returns:
        {series_uid: {'varying_tags': [...], 'constant_tags': [...]}}
    """
    variation_analysis: dict[str, dict[str, list[str]]] = {}

    for study_uid, series_dict in selected_series.items():
        for series_uid, instance_indices in series_dict.items():
            if not instance_indices:
                continue

            datasets = studies[study_uid][series_uid]
            varying_tags: list[str] = []
            constant_tags: list[str] = []

            # Parse each instance ONCE, not once per (tag, instance). With sequences on,
            # an enhanced multi-frame instance is a ~24k-row parse; re-running it for
            # every selected tag made a 30-tag export 30x slower than it needed to be.
            parsed_instances: dict[int, dict[str, Any]] = {
                instance_idx: DICOMParser(datasets[instance_idx]).get_all_tags(
                    include_private=include_private,
                    include_sequences=include_sequences,
                )
                for instance_idx in instance_indices
                if instance_idx < len(datasets)
            }

            for tag_str in selected_tags:
                tag_values: list[str] = []

                for instance_idx in instance_indices:
                    all_tags = parsed_instances.get(instance_idx)
                    if all_tags is None:
                        continue

                    if tag_str in all_tags:
                        tag_data = all_tags[tag_str]
                        value = tag_data.get('value', '')

                        if isinstance(value, list):
                            value_str = ', '.join(str(v) for v in value)
                        elif value is None:
                            value_str = ''
                        else:
                            value_str = str(value)

                        tag_values.append(value_str)

                if len(tag_values) > 1:
                    first_value = tag_values[0]
                    varies = any(val != first_value for val in tag_values[1:])
                    if varies:
                        varying_tags.append(tag_str)
                    else:
                        constant_tags.append(tag_str)
                else:
                    # Single instance or no values — treat as constant
                    constant_tags.append(tag_str)

            variation_analysis[series_uid] = {
                'varying_tags': varying_tags,
                'constant_tags': constant_tags,
            }

    return variation_analysis
