"""Unit tests for utils.log_sanitizer."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, Mock

from utils.log_sanitizer import (
    SafeExceptionLogger,
    sanitize_exception,
    sanitize_message,
    sanitized_format_exc,
    validate_no_pii_in_output,
)


class TestSanitizeMessage:
    def test_empty(self):
        assert sanitize_message("") == ""

    def test_clean_passthrough(self):
        msg = "Loaded 42 frames in 1.2 seconds"
        assert sanitize_message(msg) == msg

    def test_redacts_patient_fields_and_ids(self):
        message = "PatientName=John Patient ID: ABC1234 dob=01/02/1980"
        sanitized = sanitize_message(message)
        assert "John" not in sanitized
        assert "ABC1234" not in sanitized
        assert "01/02/1980" not in sanitized
        assert sanitized.count("[REDACTED]") >= 2

    def test_redacts_dicom_uid(self):
        uid = "1.2.840.10008.5.1.4.1.1.2"
        msg = f"Study UID: {uid}"
        result = sanitize_message(msg)
        assert uid not in result
        assert "[REDACTED]" in result or "REDACTED" in result

    def test_redacts_known_uid_root(self):
        uid = "2.25.123456789.0.12345"
        result = sanitize_message(uid)
        assert uid not in result

    def test_redacts_file_uri(self):
        msg = "Loaded file://C:/Users/JohnDoe/patient.dcm successfully"
        result = sanitize_message(msg)
        assert "JohnDoe" not in result

    def test_redacts_posix_home_path(self):
        msg = "Loading /Users/kevingrizzard/data/patient.dcm"
        result = sanitize_message(msg)
        assert "kevingrizzard" not in result

    def test_context_value_pattern(self):
        msg = "patient name = Smith^John"
        result = sanitize_message(msg)
        assert "Smith^John" not in result

    def test_redact_paths_flag(self):
        msg = "Operation successful"
        assert sanitize_message(msg, redact_paths=True) == msg
        assert sanitize_message(msg, redact_paths=False) == msg

    def test_returns_str(self):
        for val in ("", "  ", "some text", "1.2.3.4.5.6.7.8"):
            assert isinstance(sanitize_message(val), str)


class TestSanitizeException:
    def test_empty(self):
        result = sanitize_exception("")
        assert isinstance(result, str)

    def test_redacts_path_in_traceback(self):
        tb = 'File "/Users/jdoe/myapp/core/loader.py", line 42, in load_file\n  raise IOError("fail")'
        result = sanitize_exception(tb)
        assert "jdoe" not in result

    def test_clean_traceback(self):
        tb = 'File "tests/test_core.py", line 10, in test_fn\n  assert False'
        result = sanitize_exception(tb)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_redacts_file_lines_and_preserves_structure(self):
        traceback_str = 'Traceback\n  File "/Users/john/Documents/case.py", line 4\nValueError: PatientName=John'
        sanitized = sanitize_exception(traceback_str)
        assert "Traceback" in sanitized
        assert "/Users/john/Documents/case.py" not in sanitized
        assert "PatientName=John" not in sanitized
        assert "[REDACTED" in sanitized


class TestSanitizedFormatExc:
    def test_outside_exception_context(self):
        result = sanitized_format_exc()
        assert isinstance(result, str)


class TestValidateNoPiiInOutput:
    def test_clean_message(self):
        is_safe, issues = validate_no_pii_in_output("Server started successfully")
        assert is_safe is True
        assert issues == []

    def test_dob_pattern_flagged(self):
        is_safe, issues = validate_no_pii_in_output("DOB: 01-01-1980")
        assert is_safe is False
        assert len(issues) > 0

    def test_mrn_pattern_flagged(self):
        is_safe, issues = validate_no_pii_in_output("MRN: 12345ABC")
        assert is_safe is False
        assert len(issues) > 0

    def test_date_without_keyword_not_flagged(self):
        is_safe, issues = validate_no_pii_in_output("Count: 12-34-5678")
        assert is_safe is True

    def test_accepts_safe_message(self):
        safe, issues = validate_no_pii_in_output("Loaded 12 DICOM files successfully")
        assert safe is True
        assert issues == []


class TestSafeExceptionLogger:
    def test_logs_error(self):
        mock_logger = MagicMock(spec=logging.Logger)
        sel = SafeExceptionLogger(mock_logger, debug_enabled=False)
        sel.log_exception(ValueError("test error"), context="unit_test")
        mock_logger.error.assert_called_once()
        logged_msg = mock_logger.error.call_args[0][0]
        assert isinstance(logged_msg, str)

    def test_debug_mode(self):
        mock_logger = MagicMock(spec=logging.Logger)
        sel = SafeExceptionLogger(mock_logger, debug_enabled=True)
        try:
            raise RuntimeError("debug mode test")
        except RuntimeError as exc:
            sel.log_exception(exc, context="debug_test")
        mock_logger.error.assert_called_once()
        mock_logger.debug.assert_called_once()

    def test_no_context(self):
        mock_logger = MagicMock(spec=logging.Logger)
        sel = SafeExceptionLogger(mock_logger)
        sel.log_exception(TypeError("no context"))
        mock_logger.error.assert_called_once()

    def test_sanitized_error_without_debug_trace(self):
        logger = Mock()
        safe_logger = SafeExceptionLogger(logger, debug_enabled=False)
        try:
            raise ValueError("patient id=ABC12345")
        except Exception as exc:
            safe_logger.log_exception(exc, context="load /Users/john/Desktop/study.dcm")
        error_message = logger.error.call_args[0][0]
        assert "ABC12345" not in error_message
        assert "john" not in error_message.lower()
        assert "[REDACTED]" in error_message
        logger.debug.assert_not_called()

    def test_sanitized_debug_trace_when_enabled(self):
        logger = Mock()
        safe_logger = SafeExceptionLogger(logger, debug_enabled=True)
        try:
            raise RuntimeError("PatientName=John")
        except Exception as exc:
            safe_logger.log_exception(exc, context="sync")
        debug_message = logger.debug.call_args[0][0]
        assert "PatientName=John" not in debug_message
        assert "john" not in debug_message.lower()
        assert "Debug traceback:" in debug_message
