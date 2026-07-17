"""Canonical sensitive-field registry used by privacy enforcement layers.

The registry intentionally includes indirect identifiers such as DICOM UIDs,
filenames, paths, station data, and free-text annotations.  Callers should use
the registry to omit or redact values; matching a field name is not evidence
that the associated value is safe to emit.
"""

from __future__ import annotations

# Retained as the compatibility name imported by ``utils.log_sanitizer`` and
# the staged privacy checker.  New code should prefer ``SENSITIVE_DICOM_FIELDS``.
PATIENT_PII_FIELDS = frozenset(
    {
        "PatientName",
        "PatientID",
        "PatientBirthDate",
        "PatientBirthTime",
        "PatientAge",
        "PatientSex",
        "PatientAddress",
        "PatientTelephoneNumbers",
        "PatientComments",
        "ResponsiblePerson",
        "ResponsiblePersonRole",
        "EmergencyContactTelephoneNumber",
        "OtherPatientIDs",
        "OtherPatientNames",
        "IssuerOfPatientID",
    }
)

SENSITIVE_DICOM_FIELDS = PATIENT_PII_FIELDS | frozenset(
    {
        "AccessionNumber",
        "InstitutionAddress",
        "InstitutionName",
        "OperatorsName",
        "PerformingPhysicianName",
        "ReferringPhysicianName",
        "StationName",
        "StudyDate",
        "StudyDescription",
        "StudyID",
        "StudyInstanceUID",
        "SeriesInstanceUID",
        "SOPInstanceUID",
        "FrameOfReferenceUID",
        "DeviceSerialNumber",
    }
)

SENSITIVE_CONTEXT_KEYS = frozenset(
    {
        "accession",
        "ae_title",
        "annotation",
        "called_ae",
        "calling_ae",
        "dataset",
        "dicom_endpoint",
        "directory",
        "detail",
        "details",
        "error",
        "error_message",
        "exception",
        "file",
        "file_name",
        "file_path",
        "filename",
        "folder",
        "free_text",
        "host",
        "hostname",
        "ip",
        "ip_address",
        "label",
        "last_export_path",
        "last_path",
        "last_pylinac_output_path",
        "mrn",
        "message",
        "patient",
        "patient_id",
        "patient_name",
        "path",
        "recent_files",
        "remote_url",
        "reason",
        "series_uid",
        "sop_uid",
        "study_uid",
        "text",
        "uid",
        "user",
        "username",
    }
)


def normalized_sensitive_names() -> frozenset[str]:
    """Return normalized names suitable for case-insensitive key checks."""

    names = set(SENSITIVE_CONTEXT_KEYS)
    names.update(field.lower() for field in SENSITIVE_DICOM_FIELDS)
    return frozenset(name.replace("-", "_").replace(" ", "_") for name in names)


NORMALIZED_SENSITIVE_NAMES = normalized_sensitive_names()
