"""Unit tests for utils.log_sanitizer."""

from __future__ import annotations

import os
import sys
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.log_sanitizer import (
    SafeExceptionLogger,
    sanitize_exception,
    sanitize_message,
    validate_no_pii_in_output,
)


def test_sanitize_message_redacts_patient_fields_and_ids() -> None:
    message = "PatientName=John Patient ID: ABC1234 dob=01/02/1980"
    sanitized = sanitize_message(message)
    assert "John" not in sanitized
    assert "ABC1234" not in sanitized
    assert "01/02/1980" not in sanitized
    assert sanitized.count("[REDACTED]") >= 2


def test_sanitize_message_redacts_paths_only_when_requested() -> None:
    message = 'Failed to open /Users/john/Desktop/study.dcm'
    partially_redacted = sanitize_message(message, redact_paths=False)
    assert "/Users/john/Desktop/study.dcm" not in partially_redacted
    assert "/[REDACTED]/Desktop/study.dcm" in partially_redacted
    redacted = sanitize_message(message, redact_paths=True)
    assert "/Users/john/Desktop/study.dcm" not in redacted
    assert "[REDACTED]" in redacted


def test_sanitize_exception_redacts_file_lines_and_preserves_traceback_structure() -> None:
    traceback_str = 'Traceback\n  File "/Users/john/Documents/case.py", line 4\nValueError: PatientName=John'
    sanitized = sanitize_exception(traceback_str)
    assert "Traceback" in sanitized
    assert "/Users/john/Documents/case.py" not in sanitized
    assert "PatientName=John" not in sanitized
    assert "[REDACTED]" in sanitized


def test_validate_no_pii_in_output_detects_problem_patterns() -> None:
    safe, issues = validate_no_pii_in_output("dob=01/02/1980 patient id=ABC12345")
    assert safe is False
    assert issues


def test_validate_no_pii_in_output_accepts_safe_message() -> None:
    safe, issues = validate_no_pii_in_output("Loaded 12 DICOM files successfully")
    assert safe is True
    assert issues == []


def test_safe_exception_logger_logs_sanitized_error_without_debug_trace() -> None:
    logger = Mock()
    safe_logger = SafeExceptionLogger(logger, debug_enabled=False)
    try:
        raise ValueError("patient id=ABC12345")
    except Exception as exc:
        safe_logger.log_exception(exc, context="load /Users/john/Desktop/study.dcm")

    error_message = logger.error.call_args[0][0]
    assert "ABC12345" not in error_message
    assert "[REDACTED]" in error_message
    logger.debug.assert_not_called()


def test_safe_exception_logger_logs_sanitized_debug_trace_when_enabled() -> None:
    logger = Mock()
    safe_logger = SafeExceptionLogger(logger, debug_enabled=True)
    try:
        raise RuntimeError("PatientName=John")
    except Exception as exc:
        safe_logger.log_exception(exc, context="sync")

    debug_message = logger.debug.call_args[0][0]
    assert "PatientName=John" not in debug_message
    assert "Debug traceback:" in debug_message
