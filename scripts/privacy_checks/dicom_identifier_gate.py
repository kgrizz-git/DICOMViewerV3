"""DICOM identifier keywords and de-id dummy values for the artifact gate.

Tracked fixtures must not carry real identifier tags. The de-id export engine
writes ``ANONYMIZED`` into text patient tags; the gate allows that string only
when the entire stripped value matches (case-sensitive). PS3.15 action Z also
permits a zero-length value; a later engine change should prefer blanks for
Type-2 / CS attributes (see TO_DO).

Inputs: tag keyword, identifier string, optional JSON/content regex match.
Outputs: allow/skip decisions for ``check_no_phi_artifacts``.
"""

from __future__ import annotations

import re
from typing import Protocol

# Exact dummy written by ``DICOMAnonymizer`` for text patient tags.
DEIDENTIFIED_DUMMY_VALUE = "ANONYMIZED"

# These DICOM attributes must never hold a real value in a tracked fixture,
# including when nested in a sequence.  ``Dataset.iterall()`` visits sequence
# items recursively.
DICOM_IDENTIFIER_KEYWORDS = {
    "AccessionNumber",
    "InstitutionAddress",
    "InstitutionName",
    "IssuerOfPatientID",
    "OperatorsName",
    "OtherPatientIDs",
    "OtherPatientNames",
    "PatientAddress",
    "PatientBirthDate",
    "PatientBirthTime",
    "PatientComments",
    "PatientID",
    "PatientName",
    "PatientSex",
    "PatientTelephoneNumbers",
    "PerformingPhysicianName",
    "ReferringPhysicianName",
    "StationName",
    "StudyID",
}

# Synthetic test fixtures that intentionally carry recognizable, non-identifying
# placeholder identifiers. Each directory prefix maps to the exact literal values
# permitted for it; any other populated identifier still fails the gate.
SYNTHETIC_FIXTURE_IDENTIFIERS: dict[str, frozenset[str]] = {
    "tests/fixtures/dicom_rdsr/": frozenset({"Synthetic^RDSR", "SYN-RDSR-001"}),
    "tests/fixtures/dicom_nuclear/": frozenset(
        {"Synthetic^NuclearFixture", "SYNTHETIC-NM-001"}
    ),
}


def is_exact_deidentified_dummy(value: str) -> bool:
    """True when *value* is exactly the de-id placeholder after strip."""
    return value.strip() == DEIDENTIFIED_DUMMY_VALUE


def skip_populated_patient_tag_match(match: re.Match[str]) -> bool:
    """True when a CONTENT_RULES patient-tag match is only the dummy."""
    dummy = match.groupdict().get("patient_tag_value")
    return dummy is not None and is_exact_deidentified_dummy(dummy)


class _PatientTagPattern(Protocol):
    """Minimal regex-like surface used by the JSON patient-tag CONTENT_RULE."""

    def search(self, string: str, /) -> re.Match[str] | None: ...


def populated_patient_tag_finding(pattern: _PatientTagPattern, text: str) -> bool:
    """True when any patient-tag match on *text* is not the de-id dummy.

    Inspects every match so a dummy tag cannot hide a real tag on the same line.
    """
    finditer = getattr(pattern, "finditer", None)
    if finditer is None:
        match = pattern.search(text)
        return match is not None and not skip_populated_patient_tag_match(match)
    return any(
        not skip_populated_patient_tag_match(tag_match)
        for tag_match in finditer(text)
    )
