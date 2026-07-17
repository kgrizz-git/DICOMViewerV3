"""Focused tests for foundational privacy classification and sink boundaries."""

from __future__ import annotations

import logging
from io import StringIO
from pathlib import Path

import pytest

from utils.privacy.classification import (
    PATIENT_PII_FIELDS,
    SENSITIVE_DICOM_FIELDS,
)
from utils.privacy.logging_filter import PrivacyLogFilter, install_privacy_filter
from utils.privacy.redaction import (
    redact_diagnostic_value,
    redact_exception,
    redact_text,
    redact_value,
    safe_event_fields,
)
from utils.privacy.safe_storage import (
    RETENTION_METADATA_FILENAME,
    RetentionPolicy,
    assert_safe_internal_path,
    atomic_write_private_text,
    ensure_private_directory,
    is_user_private,
    write_retention_metadata,
)
from utils.privacy.streams import PrivacyTextStream


def _contains_candidate(payload: object, candidate: str) -> bool:
    return candidate in str(payload)


@pytest.mark.parametrize(
    "value",
    [
        "/Users/privacy-canary/Desktop/patient-name_123.dcm",
        r"C:\Users\privacy-canary\Desktop\patient-name_123.dcm",
        r"\\clinical-host\share\patient-name_123.dcm",
        '"/Users/privacy canary/Desktop/patient name_123.dcm"',
    ],
)
def test_redact_text_removes_entire_path_including_basename(value: str) -> None:
    result = redact_text(f"Failed file_path={value}", redact_paths=False)

    assert "privacy-canary" not in result
    assert "patient-name_123.dcm" not in result
    assert "[PATH]" in result or "[REDACTED]" in result


def test_canonical_registry_includes_indirect_dicom_identifiers() -> None:
    assert PATIENT_PII_FIELDS <= SENSITIVE_DICOM_FIELDS
    assert {
        "AccessionNumber",
        "StudyInstanceUID",
        "SeriesInstanceUID",
        "SOPInstanceUID",
        "InstitutionName",
        "StationName",
    } <= SENSITIVE_DICOM_FIELDS


def test_redact_text_removes_contextual_identifiers_and_network_values() -> None:
    canaries = [
        "PATIENT-CANARY",
        "MRN-CANARY-9001",
        "2.25.999999999999999999",
        "10.22.33.44",
        "clinical-host.internal",
        "annotation-canary-value",
    ]
    message = (
        "PatientName=PATIENT-CANARY; MRN=MRN-CANARY-9001; "
        "StudyUID=2.25.999999999999999999; ip=10.22.33.44; "
        "host=clinical-host.internal; annotation=annotation-canary-value"
    )

    result = redact_text(message)

    for canary in canaries:
        assert canary not in result


def test_redact_value_uses_structural_key_policy() -> None:
    payload = {
        "patient_name": "UNSTRUCTURED-CANARY",
        "series_uid": "2.25.12345678901234567890",
        "count": 4,
        "nested": {"filename": "patient-canary.dcm"},
    }

    result = redact_value(payload)

    assert result["patient_name"] == "[REDACTED]"
    assert result["series_uid"] == "[REDACTED]"
    assert result["count"] == 4
    assert result["nested"]["filename"] == "[REDACTED]"


def test_diagnostic_value_fail_closed_preserves_only_safe_structure() -> None:
    marker = "-".join(("SYNTHETIC", "NESTED", "TEXT"))
    result = redact_diagnostic_value(
        {
            "operation": "diagnostic.test",
            "error_class": "ValueError",
            "count": 2,
            "nested": {"error": marker, marker: marker},
        }
    )

    assert result["operation"] == "diagnostic.test"
    assert result["error_class"] == "ValueError"
    assert result["count"] == 2
    assert result["nested"]["error"] == "[REDACTED]"
    assert not _contains_candidate(result, marker)


def test_privacy_log_filter_redacts_format_args_exceptions_and_extras() -> None:
    record = logging.LogRecord(
        "privacy-test",
        logging.ERROR,
        __file__,
        10,
        "Failed to open %s for %s",
        ("/Users/privacy-canary/Desktop/patient-canary.dcm", "PatientID=ABC-9999"),
        None,
    )
    try:
        raise ValueError("PatientName=PATIENT-CANARY")
    except ValueError:
        record.exc_info = __import__("sys").exc_info()
    record.patient_name = "EXTRA-CANARY"

    assert PrivacyLogFilter().filter(record) is True
    output = record.getMessage()

    for canary in (
        "privacy-canary",
        "patient-canary.dcm",
        "ABC-9999",
        "PATIENT-CANARY",
        "EXTRA-CANARY",
    ):
        assert canary not in output
        assert canary not in str(record.__dict__)
    assert record.exc_info is None


def test_privacy_log_filter_redacts_f_string_and_mapping_args() -> None:
    direct = logging.makeLogRecord(
        {"msg": "PatientName=FSTRING-CANARY", "levelno": logging.WARNING}
    )
    mapped = logging.makeLogRecord(
        {
            "msg": "Failed %(filename)s",
            "args": {"filename": "mapping-patient-canary.dcm"},
            "levelno": logging.WARNING,
        }
    )

    privacy_filter = PrivacyLogFilter()
    assert privacy_filter.filter(direct)
    assert privacy_filter.filter(mapped)
    assert "FSTRING-CANARY" not in direct.getMessage()
    assert "mapping-patient-canary.dcm" not in mapped.getMessage()


def test_install_privacy_filter_covers_handlers_added_between_calls() -> None:
    logger = logging.getLogger("privacy-install-test")
    logger.handlers.clear()
    logger.filters.clear()
    first = logging.NullHandler()
    logger.addHandler(first)

    installed = install_privacy_filter(logger)
    second = logging.NullHandler()
    logger.addHandler(second)
    reinstalled = install_privacy_filter(logger)

    assert installed is reinstalled
    assert any(isinstance(item, PrivacyLogFilter) for item in first.filters)
    assert any(isinstance(item, PrivacyLogFilter) for item in second.filters)


def test_safe_event_fields_allow_only_structural_values() -> None:
    assert safe_event_fields("dicom.load", count=4, error=ValueError("canary")) == {
        "operation": "dicom.load",
        "count": 4,
        "error_class": "ValueError",
    }
    with pytest.raises(ValueError, match="stable non-sensitive"):
        safe_event_fields("load /Users/patient-canary/study.dcm")


def test_privacy_text_stream_redacts_stdout_and_stderr_payloads() -> None:
    output = StringIO()
    stream = PrivacyTextStream(output)

    written = stream.write(
        "Failed /Users/stream-canary/patient-file.dcm PatientID=STREAM-9999"
    )
    stream.flush()

    assert written == len(output.getvalue())
    assert "stream-canary" not in output.getvalue()
    assert "patient-file.dcm" not in output.getvalue()
    assert "STREAM-9999" not in output.getvalue()


def test_redact_exception_preserves_structure_not_values() -> None:
    raw = (
        "Traceback (most recent call last):\n"
        '  File "/Users/privacy-canary/patient-canary.py", line 9, in load\n'
        "    raise ValueError('PatientName=PATIENT-CANARY')\n"
        "ValueError: PatientName=PATIENT-CANARY"
    )

    result = redact_exception(raw)

    assert "Traceback" in result
    assert "ValueError" in result
    assert "privacy-canary" not in result
    assert "patient-canary.py" not in result
    assert "PATIENT-CANARY" not in result


def test_safe_storage_rejects_checkout_and_writes_private_file(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    with pytest.raises(ValueError, match="source checkout"):
        assert_safe_internal_path(checkout / "privacy.log", source_root=checkout)

    protected = ensure_private_directory(tmp_path / "outside" / "logs")
    written = atomic_write_private_text(
        protected / "privacy.log",
        "redacted diagnostic",
        source_root=checkout,
    )

    assert written.read_text(encoding="utf-8") == "redacted diagnostic"
    assert is_user_private(protected)
    assert is_user_private(written)

    metadata = write_retention_metadata(
        protected,
        RetentionPolicy(max_age_days=7, max_files=3, delete_on_exit=True),
        source_root=checkout,
    )
    assert metadata.name == RETENTION_METADATA_FILENAME
    assert "patient" not in metadata.read_text(encoding="utf-8").lower()
    assert is_user_private(metadata)


def test_safe_storage_allows_private_destination_below_launch_directory(
    monkeypatch, tmp_path: Path
) -> None:
    checkout = tmp_path / "checkout"
    launch_dir = tmp_path / "launcher-home"
    private_dir = launch_dir / "private-state"
    checkout.mkdir()
    launch_dir.mkdir()
    monkeypatch.chdir(launch_dir)

    written = atomic_write_private_text(
        private_dir / "settings.json",
        "{}",
        source_root=checkout,
    )

    assert written.read_text(encoding="utf-8") == "{}"
    with pytest.raises(ValueError, match="source checkout"):
        atomic_write_private_text(
            checkout / "tracked-sensitive.json",
            "{}",
            source_root=checkout,
        )
