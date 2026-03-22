"""
Log Sanitization Utility

Provides functions to redact sensitive information from log messages and exceptions
before output. This prevents accidental exposure of:
- Patient PII (name, ID, DOB, age)
- File paths that may contain user/patient identifiers
- Exception details that may leak system information

Usage:
    from utils.log_sanitizer import sanitize_message, sanitize_exception
    
    # Sanitize a generic message
    safe_msg = sanitize_message(f"Error for patient {patient_name}")
    
    # Sanitize an exception traceback
    safe_traceback = sanitize_exception(traceback.format_exc())
"""

import re
import os
from pathlib import Path
from typing import Optional, Dict, Any


# DICOM fields containing patient PII that should never appear in logs
PATIENT_PII_FIELDS = {
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "PatientAge",
    "PatientSex",
    "PatientAddress",
    "PatientTelephoneNumbers",
    "PatientComments",
    "ResponsiblePerson",
    "ResponsiblePersonRole",
    "EmergencyContactTelephoneNumber",
}

# Regex patterns for PII that should be redacted
PII_PATTERNS = {
    # Common patient name patterns (varies by DICOM source)
    "patient_name": r"(?:patient\s*(?:name|id|mrn|identifier)[\s:=]*['\"]?(?P<value>[A-Za-z\s\-\.]+?)(?:['\"]|\s|$|,))",
    # Patient IDs / MRN patterns
    "patient_id": r"(?:(?:mrn|patient\s*id|pid|external\s*id)[\s:=]*['\"]?(?P<value>[A-Z0-9\-]+?)(?:['\"]|$|\s))",
    # Dates of birth
    "dob": r"(?:(?:dob|birth\s*date|birthdate)[\s:=]*(?P<value>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}))",
    # Absolute file paths (Windows and Unix)
    "file_path": r"(?:[A-Z]:\\|/)(?:Users|home|root|Documents|Downloads|Desktop)(?:\\|/)[^\s\"]*",
    # User home directories
    "home_dir": r"(?:Users|home)[\\/][A-Za-z0-9_\-\.]+",
}


def sanitize_message(message: str, redact_paths: bool = False) -> str:
    """
    Redact sensitive information from a log message.
    
    Args:
        message: The message to sanitize
        redact_paths: If True, also redact file paths (slower, use sparingly)
        
    Returns:
        Sanitized message with PII replaced with [REDACTED]
    """
    if not message:
        return message
    
    sanitized = message
    
    # Redact known PII fields referenced in the message
    for field in PATIENT_PII_FIELDS:
        # Match: field = "value" or field: value or field='value'
        pattern = rf"(?:{field}\s*[=:]?\s*['\"]?)([^'\"=:\s,;\]\}}]+)"
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
    
    # Redact common PII patterns
    for pattern_name, pattern in PII_PATTERNS.items():
        if pattern_name == "file_path" and not redact_paths:
            continue  # Skip path redaction by default (noisy)
        sanitized = re.sub(pattern, "[REDACTED]", sanitized, flags=re.IGNORECASE)
    
    # Redact anything that looks like a date (YYYY-MM-DD, MM/DD/YYYY, etc.)
    # with conservative application to avoid over-redaction
    # Only redact if preceded by known date field names
    date_pattern = r"(?:(?:date|dob|birth)[\s:=]*)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
    matches = re.finditer(date_pattern, sanitized, re.IGNORECASE)
    for match in reversed(list(matches)):
        if "date" in sanitized[max(0, match.start() - 20):match.start()].lower():
            sanitized = sanitized[:match.start()] + "[REDACTED]" + sanitized[match.end():]
    
    return sanitized


def sanitize_exception(traceback_str: str) -> str:
    """
    Redact sensitive information from an exception traceback.
    
    Args:
        traceback_str: The full traceback string
        
    Returns:
        Sanitized traceback with paths and PII redacted
    """
    if not traceback_str:
        return traceback_str
    
    lines = traceback_str.split("\n")
    sanitized_lines = []
    
    for line in lines:
        # Redact absolute paths in File lines
        # Before: File "/Users/john/Documents/DICOM/study.dcm"
        # After:  File "[REDACTED]/study.dcm"
        if "File \"" in line or "File '" in line:
            line = re.sub(
                r"""File ["']([A-Z]:\\|/)(?:Users|home|root|Documents)[^\\"']*["']""",
                r"File \"[REDACTED]/...[filename]\"",
                line,
                flags=re.IGNORECASE
            )
        
        # Redact patient data from exception messages
        line = sanitize_message(line, redact_paths=False)
        
        sanitized_lines.append(line)
    
    return "\n".join(sanitized_lines)


def create_safe_exception_handler(func_name: str = "") -> str:
    """
    Template for a safe exception handler that logs without leaking PII.
    
    Usage:
        try:
            risky_operation()
        except Exception as e:
            safe_msg = create_safe_exception_message(exc, "operation_name")
            logger.error(safe_msg)
    
    Args:
        func_name: Name of the function where error occurred
        
    Returns:
        Code template for safe exception handling
    """
    return """
try:
    # Your code here
    pass
except Exception as e:
    error_msg = f"Error in {func_name}: {{type(e).__name__}}: {{str(e)[:100]}}"
    safe_msg = sanitize_message(error_msg)
    # Use logger instead of print for production
    logger.error(safe_msg)
    # Debug mode only (not in production builds):
    if DEBUG_MODE:
        logger.debug(f"Full traceback: {{sanitize_exception(traceback.format_exc())}}")
"""


def validate_no_pii_in_output(message: str) -> tuple[bool, list[str]]:
    """
    Validate that a message doesn't contain obvious PII before logging.
    
    Args:
        message: The message to validate
        
    Returns:
        Tuple of (is_safe: bool, issues: list of found PII patterns)
    """
    issues = []
    
    # Check for patient fields
    for field in PATIENT_PII_FIELDS:
        if field in message:
            issues.append(f"Contains patient field name: {field}")
    
    # Check for date patterns with context clues
    date_pattern = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    if re.search(date_pattern, message):
        # Check if preceded by date-related keywords
        if any(kw in message.lower() for kw in ["dob", "birth", "date", "age"]):
            issues.append("Potential date of birth or age information")
    
    # Check for common ID patterns
    if re.search(r"(?:mrn|patient.?id|pid)[:\s=]+[A-Z0-9\-]{5,}", message, re.IGNORECASE):
        issues.append("Potential patient ID or MRN")
    
    return len(issues) == 0, issues


# Example production-ready exception handler
class SafeExceptionLogger:
    """Wrapper to log exceptions safely without leaking PII."""
    
    def __init__(self, logger, debug_enabled: bool = False):
        """
        Args:
            logger: Logger instance (e.g., from logging module)
            debug_enabled: If True, include full traceback in debug logs only
        """
        self.logger = logger
        self.debug_enabled = debug_enabled
    
    def log_exception(self, exc: Exception, context: str = ""):
        """
        Log an exception with automatic PII redaction.
        
        Args:
            exc: The exception to log
            context: Brief context about what was happening
        """
        msg = f"Error"
        if context:
            msg += f" ({context})"
        msg += f": {type(exc).__name__}: {str(exc)[:150]}"
        
        safe_msg = sanitize_message(msg)
        self.logger.error(safe_msg)
        
        if self.debug_enabled:
            # Only log full traceback in debug mode
            import traceback
            safe_trace = sanitize_exception(traceback.format_exc())
            self.logger.debug(f"Debug traceback:\n{safe_trace}")
