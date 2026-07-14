"""
Deep anonymization tag profile for DICOM export.

Defines tag inventories and actions aligned with DICOM PS3.15 Basic Application
Level Confidentiality Profile (patient, institution, device, operator, UIDs,
dates, private tags, and free-text comments).

Inputs:
    Imported by ``deep_anonymizer.DeepDICOMAnonymizer``.

Outputs:
    Python constants: tag tuples grouped by category and ``DEIDENTIFICATION_METHOD``.

Requirements:
    pydicom (``Tag``)
"""

from __future__ import annotations

from typing import Literal, cast

from pydicom.tag import BaseTag, Tag

# Action applied when a category is enabled in DeepAnonymizerOptions.
ProfileAction = Literal["remove", "replace", "patient_anonymize", "uid_remap", "date_shift"]

# (Tag, action) — optional third element is replacement string for ``replace``.
ProfileEntry = (
    tuple[BaseTag, ProfileAction]
    | tuple[BaseTag, Literal["replace"], str]
)

# Institution / site identifiers (0008 group unless noted).
INSTITUTION_SITE_TAGS: tuple[BaseTag, ...] = (
    Tag(0x0008, 0x0080),  # InstitutionName
    Tag(0x0008, 0x0081),  # InstitutionAddress
    Tag(0x0008, 0x0082),  # InstitutionCodeSequence (removed as whole element)
    Tag(0x0008, 0x1040),  # InstitutionalDepartmentName
)

# Station / device identifiers (0008 / 0018 groups).
STATION_DEVICE_TAGS: tuple[BaseTag, ...] = (
    Tag(0x0008, 0x0070),  # Manufacturer
    Tag(0x0008, 0x1010),  # StationName
    Tag(0x0008, 0x1090),  # ManufacturerModelName
    Tag(0x0018, 0x1000),  # DeviceSerialNumber
    Tag(0x0018, 0x1008),  # GantryID
    Tag(0x0018, 0x1020),  # SoftwareVersions
    Tag(0x0018, 0x700A),  # DetectorID
)

# Operator and physician name / contact / identification tags.
OPERATOR_PHYSICIAN_TAGS: tuple[BaseTag, ...] = (
    Tag(0x0008, 0x0090),  # ReferringPhysicianName
    Tag(0x0008, 0x0092),  # ReferringPhysicianAddress
    Tag(0x0008, 0x0094),  # ReferringPhysicianTelephoneNumbers
    Tag(0x0008, 0x0096),  # ReferringPhysicianIdentificationSequence
    Tag(0x0008, 0x009C),  # ConsultingPhysicianName
    Tag(0x0008, 0x009D),  # ConsultingPhysicianIdentificationSequence
    Tag(0x0008, 0x1048),  # PhysiciansOfRecord
    Tag(0x0008, 0x1049),  # PhysiciansOfRecordIdentificationSequence
    Tag(0x0008, 0x1050),  # PerformingPhysicianName
    Tag(0x0008, 0x1052),  # PerformingPhysicianIdentificationSequence
    Tag(0x0008, 0x1060),  # NameOfPhysiciansReadingStudy
    Tag(0x0008, 0x1062),  # PhysiciansReadingStudyIdentificationSequence
    Tag(0x0008, 0x1070),  # OperatorsName
    Tag(0x0008, 0x1072),  # OperatorIdentificationSequence
    Tag(0x0032, 0x1032),  # RequestingPhysician
    Tag(0x0032, 0x1033),  # RequestingService
)

# Study/order identifiers — PS3.15 Table E.1-1 action Z (blank, not delete: these
# are Type 2 in their IODs). Strong re-identification / RIS-PACS linkage vectors.
# Always blanked by the base profile (no retain option), independent of strip flags.
IDENTIFIER_TAGS: tuple[BaseTag, ...] = (
    Tag(0x0008, 0x0050),  # AccessionNumber (Z)
    Tag(0x0020, 0x0010),  # StudyID (Z)
    Tag(0x0040, 0x2016),  # PlacerOrderNumberImagingServiceRequest
    Tag(0x0040, 0x2017),  # FillerOrderNumberImagingServiceRequest
    Tag(0x0040, 0x1001),  # RequestedProcedureID
    Tag(0x0040, 0x0009),  # ScheduledProcedureStepID
    Tag(0x0040, 0x0253),  # PerformedProcedureStepID
)

# Free-text fields that commonly leak identifying information.
FREE_TEXT_TAGS: tuple[BaseTag, ...] = (
    Tag(0x0008, 0x1030),  # StudyDescription
    Tag(0x0008, 0x103E),  # SeriesDescription
    Tag(0x0010, 0x4000),  # PatientComments
    Tag(0x0010, 0x21B0),  # AdditionalPatientHistory
    Tag(0x0032, 0x1060),  # RequestedProcedureDescription
    Tag(0x0020, 0x4000),  # ImageComments
)

# Structured Report content items can embed names and narrative PHI deep inside
# ContentSequence trees; strip them under the same free-text option.
SR_NARRATIVE_TAGS: tuple[BaseTag, ...] = (
    Tag(0x0040, 0xA123),  # PersonName
    Tag(0x0040, 0xA160),  # TextValue
)

# Primary UID tags remapped as a batch (intra-export consistency).
UID_TAGS: tuple[BaseTag, ...] = (
    Tag(0x0008, 0x0018),  # SOPInstanceUID
    Tag(0x0020, 0x000D),  # StudyInstanceUID
    Tag(0x0020, 0x000E),  # SeriesInstanceUID
    Tag(0x0020, 0x0052),  # FrameOfReferenceUID
    Tag(0x0020, 0x0200),  # SynchronizationFrameOfReferenceUID
)

# PS3.15 de-identification provenance written on export.
PATIENT_IDENTITY_REMOVED_TAG = Tag(0x0012, 0x0062)
DEIDENTIFICATION_METHOD_TAG = Tag(0x0012, 0x0063)
DEIDENTIFICATION_METHOD = "Deep anonymization (DICOM Viewer V3)"

# Tags retained when ``retain_manufacturer`` is True (subset of STATION_DEVICE_TAGS).
MANUFACTURER_RETAIN_TAGS: tuple[BaseTag, ...] = (
    Tag(0x0008, 0x0070),  # Manufacturer
    Tag(0x0008, 0x1090),  # ManufacturerModelName
)

# Flat profile entries for unit tests and documentation cross-checks.
# ``cast`` because the bare string actions infer as ``str`` rather than the
# ``Literal`` members of ``ProfileAction`` inside the tuple comprehensions.
DEEP_ANONYMIZER_PROFILE: tuple[ProfileEntry, ...] = cast(
    "tuple[ProfileEntry, ...]",
    tuple((tag, "remove") for tag in INSTITUTION_SITE_TAGS)
    + tuple((tag, "remove") for tag in STATION_DEVICE_TAGS)
    + tuple((tag, "remove") for tag in OPERATOR_PHYSICIAN_TAGS)
    + tuple((tag, "remove") for tag in FREE_TEXT_TAGS)
    + tuple((tag, "remove") for tag in SR_NARRATIVE_TAGS)
    + tuple((tag, "uid_remap") for tag in UID_TAGS),
)
