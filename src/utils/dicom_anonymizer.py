"""
DICOM Anonymizer Utility

This module provides functionality for anonymizing DICOM datasets by replacing
or removing patient-related tags.

Inputs:
    - pydicom.Dataset objects
    
Outputs:
    - Anonymized pydicom.Dataset objects
    
Requirements:
    - pydicom library
    - utils.dicom_utils for patient tag identification
"""

import copy

from pydicom.dataset import Dataset

from utils.dicom_utils import is_patient_tag
from utils.dicom_vr_helpers import is_date_vr, is_text_vr


class DICOMAnonymizer:
    """
    Anonymizes DICOM datasets by replacing or removing patient-related tags.
    
    Features:
    - Replaces text-valued patient tags with "ANONYMIZED"
    - Removes date/time patient tags
    - Removes other non-text patient tags
    - Preserves all other tags and image data
    """

    def __init__(self):
        """Initialize the anonymizer."""
        pass

    def anonymize_dataset(self, dataset: Dataset) -> Dataset:
        """
        Anonymize a DICOM dataset by replacing or removing patient-related tags.

        Creates a copy of the dataset and modifies patient (group 0010) tags
        **at every level of the dataset tree**, descending into sequences so PHI
        nested in items (e.g. Referenced Patient Sequence, Request Attributes
        Sequence, SR ContentSequence) is anonymized too:
        - Text-valued tags: replaced with "ANONYMIZED" (a dummy value satisfies the
          PS3.15 Z/D actions).
        - Date/time tags: **blanked** (zero-length value) rather than deleted, so
          Type-2 attributes such as PatientBirthDate (0010,0030) stay present and
          IOD-conformant per PS3.15 action Z.
        - Other patient tags: removed.

        Args:
            dataset: pydicom Dataset to anonymize

        Returns:
            Anonymized Dataset (copy of original)
        """
        # Deep copy: a shallow Dataset.copy() shares DataElement objects, so
        # setting .value would mutate the caller's in-memory dataset (corrupting
        # the loaded study). deepcopy isolates the export copy fully.
        anonymized = copy.deepcopy(dataset)
        self._anonymize_in_place(anonymized)
        return anonymized

    def _anonymize_in_place(self, ds: Dataset) -> None:
        """Apply the patient-tag rule to ``ds`` and recurse into every sequence."""
        tags_to_remove = []

        for elem in ds:
            # Descend into sequences regardless of the sequence's own group, so
            # patient PHI nested anywhere in the tree is caught.
            if elem.VR == "SQ" and elem.value:
                for item in elem.value:
                    if isinstance(item, Dataset):
                        self._anonymize_in_place(item)

            if not is_patient_tag(str(elem.tag)):
                continue

            vr = elem.VR if hasattr(elem, "VR") else ""
            if is_text_vr(vr):
                # Text-valued tags: replace with "ANONYMIZED" dummy.
                try:
                    ds[elem.tag].value = "ANONYMIZED"
                except Exception:
                    tags_to_remove.append(elem.tag)
            elif is_date_vr(vr):
                # Date/time tags: blank (keep element present for Type-2 conformance).
                try:
                    ds[elem.tag].value = ""
                except Exception:
                    tags_to_remove.append(elem.tag)
            elif vr != "SQ":
                # Other patient VR types: remove.
                tags_to_remove.append(elem.tag)

        for tag in tags_to_remove:
            try:
                if tag in ds:
                    del ds[tag]
            except Exception:
                try:
                    ds[tag].value = ""
                except Exception:
                    pass

