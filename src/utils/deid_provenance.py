"""
PS3.15 de-identification provenance tags.

Builds and applies the de-identification provenance required by PS3.15 Annex E
(E.1.1 step 6): ``PatientIdentityRemoved (0012,0062) = "YES"``, a free-text
``DeidentificationMethod (0012,0063)``, and a coded
``DeidentificationMethodCodeSequence (0012,0064)`` whose items come from
PS3.16 CID 7050, reflecting the profile + options actually applied.

Shared by every de-identification path so each produces conformant, accurately
declared output.

Inputs:
    A target pydicom Dataset and the set of applied options (date handling +
    retain flags).

Outputs:
    Provenance Attributes set on the Dataset in place.

Requirements:
    pydicom
"""

from __future__ import annotations

from typing import Literal

from pydicom.dataset import Dataset

# CID 7050 De-identification Method codes (DCM scheme). Verified 2026-06-16
# against PS3.16 (https://dicom.nema.org/medical/dicom/current/output/chtml/part16/sect_CID_7050.html).
CodeTriple = tuple[str, str, str]  # (CodeValue, CodingSchemeDesignator, CodeMeaning)

CODE_BASIC_PROFILE: CodeTriple = ("113100", "DCM", "Basic Application Confidentiality Profile")
CODE_RETAIN_FULL_DATES: CodeTriple = (
    "113106", "DCM", "Retain Longitudinal Temporal Information Full Dates Option",
)
CODE_RETAIN_MODIFIED_DATES: CodeTriple = (
    "113107", "DCM", "Retain Longitudinal Temporal Information Modified Dates Option",
)
CODE_RETAIN_DEVICE_IDENTITY: CodeTriple = ("113109", "DCM", "Retain Device Identity Option")
CODE_RETAIN_UIDS: CodeTriple = ("113110", "DCM", "Retain UIDs Option")
CODE_RETAIN_INSTITUTION_IDENTITY: CodeTriple = (
    "113112", "DCM", "Retain Institution Identity Option",
)

DateMode = Literal["shift", "remove", "keep"]


def build_method_codes(
    *,
    date_mode: DateMode,
    retain_device_identity: bool = False,
    retain_institution_identity: bool = False,
    retain_uids: bool = False,
) -> list[CodeTriple]:
    """Return the CID 7050 codes for the applied profile + options.

    The Basic Application Confidentiality Profile (113100) is always present. Each
    enabled retain option, and the date-handling choice, adds its declaration:

    - date_mode "keep"   → 113106 (Retain Full Dates)
    - date_mode "shift"  → 113107 (Retain Modified Dates)
    - date_mode "remove" → no temporal code (pure base profile)
    """
    codes: list[CodeTriple] = [CODE_BASIC_PROFILE]
    if date_mode == "keep":
        codes.append(CODE_RETAIN_FULL_DATES)
    elif date_mode == "shift":
        codes.append(CODE_RETAIN_MODIFIED_DATES)
    if retain_device_identity:
        codes.append(CODE_RETAIN_DEVICE_IDENTITY)
    if retain_institution_identity:
        codes.append(CODE_RETAIN_INSTITUTION_IDENTITY)
    if retain_uids:
        codes.append(CODE_RETAIN_UIDS)
    return codes


def _code_item(code: CodeTriple) -> Dataset:
    """Build a single Code Sequence item Dataset from a (value, scheme, meaning)."""
    item = Dataset()
    item.CodeValue = code[0]
    item.CodingSchemeDesignator = code[1]
    item.CodeMeaning = code[2]
    return item


def apply_deidentification_provenance(
    ds: Dataset,
    *,
    method_text: str,
    date_mode: DateMode,
    retain_device_identity: bool = False,
    retain_institution_identity: bool = False,
    retain_uids: bool = False,
) -> None:
    """Write PS3.15 provenance Attributes on ``ds`` in place.

    Sets ``PatientIdentityRemoved = "YES"``, the free-text method, and the coded
    ``DeidentificationMethodCodeSequence`` for the applied profile/options.
    """
    ds.PatientIdentityRemoved = "YES"
    ds.DeidentificationMethod = method_text
    codes = build_method_codes(
        date_mode=date_mode,
        retain_device_identity=retain_device_identity,
        retain_institution_identity=retain_institution_identity,
        retain_uids=retain_uids,
    )
    ds.DeidentificationMethodCodeSequence = [_code_item(c) for c in codes]
