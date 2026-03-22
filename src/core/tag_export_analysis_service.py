"""
DICOM Tag Export Analysis Service

Analyses which DICOM tags vary across instances within each selected series.
This module is pure logic with no Qt dependency.
"""

from typing import Dict, List

from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser


def analyze_tag_variations(
    studies: Dict[str, Dict[str, List[Dataset]]],
    selected_series: Dict[str, Dict[str, List[int]]],
    selected_tags: List[str],
    include_private: bool,
) -> Dict[str, Dict[str, List[str]]]:
    """
    Analyze which tags vary across instances within each selected series.

    Args:
        studies: Full studies dict {study_uid: {series_uid: [Dataset, ...]}}
        selected_series: {study_uid: {series_uid: [instance_indices]}}
        selected_tags: List of tag strings selected by the user
        include_private: Whether to include private tags

    Returns:
        {series_uid: {'varying_tags': [...], 'constant_tags': [...]}}
    """
    variation_analysis: Dict[str, Dict[str, List[str]]] = {}

    for study_uid, series_dict in selected_series.items():
        for series_uid, instance_indices in series_dict.items():
            if not instance_indices:
                continue

            datasets = studies[study_uid][series_uid]
            varying_tags: List[str] = []
            constant_tags: List[str] = []

            for tag_str in selected_tags:
                tag_values: List[str] = []

                for instance_idx in instance_indices:
                    if instance_idx >= len(datasets):
                        continue

                    dataset = datasets[instance_idx]
                    parser = DICOMParser(dataset)
                    all_tags = parser.get_all_tags(include_private=include_private)

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
