"""
Union of DICOM tag maps across many datasets (Export DICOM Tags dialog).

Builds a merged flat tag dictionary from multiple :class:`pydicom.dataset.Dataset`
instances so the export tree lists every tag key seen on any loaded slice.

This module lives separately from :mod:`core.tag_export_catalog` so the catalog
module does not import :mod:`core.dicom_parser`. That breaks a static import
cycle: ``dicom_parser`` lazily imports the catalog for
:func:`~core.tag_export_catalog.supplement_export_tags_dict` only when
``supplement_standard_tags`` is True.

Inputs:
    - List of pydicom ``Dataset`` objects (e.g. all instances in a series).

Outputs:
    - Merged ``dict`` keyed by canonical ``str(Tag)``, same shape as
      :meth:`core.dicom_parser.DICOMParser.get_all_tags`.

Requirements:
    - pydicom, :class:`core.dicom_parser.DICOMParser`,
      :func:`core.tag_export_catalog.supplement_export_tags_dict`.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydicom.dataset import Dataset

from core.dicom_parser import DICOMParser
from core.tag_export_catalog import supplement_export_tags_dict


def union_tags_across_datasets(
    datasets: List[Dataset],
    *,
    include_private: bool,
    supplement_standard_tags: bool = False,
) -> Dict[str, Any]:
    """
    Build the union of tag keys across many datasets (nested elements included).

    For each canonical ``str(Tag)``, the **first** occurrence in *datasets* order
    supplies display metadata (name, sample value in the tree). Later instances
    can still contribute **new** keys not present on earlier slices.

    Args:
        datasets: All instances from loaded studies/series (any order; typically
            study → series → instance).
        include_private: Passed to :meth:`~core.dicom_parser.DICOMParser.get_all_tags`.
        supplement_standard_tags: If True, apply :func:`supplement_export_tags_dict`
            after the union.

    Returns:
        Merged tag dict suitable for the export dialog tree.
    """
    merged: Dict[str, Any] = {}
    for ds in datasets:
        parser = DICOMParser(ds)
        part = parser.get_all_tags(
            include_private=include_private,
            supplement_standard_tags=False,
        )
        for tag_str, tag_data in part.items():
            if tag_str not in merged:
                merged[tag_str] = tag_data
    if supplement_standard_tags:
        supplement_export_tags_dict(merged)
    return merged
