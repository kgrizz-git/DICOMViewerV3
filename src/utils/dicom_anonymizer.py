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
from pydicom.tag import BaseTag, Tag

from utils.dicom_utils import is_patient_tag

# These attributes are Type 2 in the common Patient Module and have PS3.15
# Basic Profile actions Z and Z/D. Keeping them present with a zero-length value
# both satisfies their Type-2 requirement and stays legal for their VRs. In
# particular, ``ANONYMIZED`` is not a legal CS value for PatientSex.
TYPE_2_PATIENT_TAGS: frozenset[BaseTag] = frozenset(
    {
        Tag(0x0010, 0x0010),  # PatientName (PN, Z)
        Tag(0x0010, 0x0020),  # PatientID (LO, Z/D)
        Tag(0x0010, 0x0030),  # PatientBirthDate (DA, Z)
        Tag(0x0010, 0x0040),  # PatientSex (CS, Z)
        Tag(0x0010, 0x1010),  # PatientAge (IS, Z)
    }
)


class DICOMAnonymizer:
    """
    Anonymizes DICOM datasets by replacing or removing patient-related tags.
    
    Features:
    - Blanks common Type-2 patient attributes with zero-length VR-legal values
    - Removes other patient attributes
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
        - Common Type-2 Patient Module attributes (PatientName, PatientID,
          PatientBirthDate, PatientSex, and PatientAge): **blanked** with a
          zero-length value.
          This preserves required attributes while remaining VR-legal (notably,
          PatientSex is CS and cannot contain the old ``ANONYMIZED`` dummy).
        - All other patient tags: removed. This includes IssuerOfPatientID,
          whose PS3.15 Basic Profile action is X.

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

            if elem.tag in TYPE_2_PATIENT_TAGS:
                # PS3.15 action Z: keep common Type-2 Patient Module attributes
                # present with a zero-length value. This works for PN, LO, DA,
                # and CS without relying on a dummy that may violate a VR's
                # defined terms.
                try:
                    ds[elem.tag].value = ""
                except Exception:
                    tags_to_remove.append(elem.tag)
            else:
                # Other group-0010 attributes, including IssuerOfPatientID, use
                # the conservative remove path rather than a generic text dummy.
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
