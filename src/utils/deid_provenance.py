"""Factual record for a metadata-deidentification transformation.

Deep DICOM export records ``DeidentificationMethod (0012,0063)`` so a
recipient can see that the application transformed metadata. Until the active
PS3.15 assessment is complete, it intentionally does not emit
``PatientIdentityRemoved (0012,0062)`` or CID 7050 profile/option codes. Those
values would overstate the scope of a metadata-only transformation when
identifying pixel content or unsupported object types can remain.
"""

from __future__ import annotations

from pydicom.dataset import Dataset


def apply_deidentification_provenance(ds: Dataset, *, method_text: str) -> None:
    """Record the scoped transformation and clear unsupported profile assertions."""
    _clear_profile_assertions(ds)
    ds.DeidentificationMethod = method_text


def _clear_profile_assertions(ds: Dataset) -> None:
    """Remove inherited assertions from every item in a dataset tree."""
    for elem in list(ds):
        if elem.VR == "SQ" and elem.value:
            for item in elem.value:
                if isinstance(item, Dataset):
                    _clear_profile_assertions(item)

    for keyword in ("PatientIdentityRemoved", "DeidentificationMethodCodeSequence"):
        if keyword in ds:
            del ds[keyword]
